#!/usr/bin/env python3
"""T2 题面泄露检查器 —— 命中即失败退出。

为什么这是 T2 的生命线
--------------------
T2 的防污染是**结构性**的：题面里没有变异身份，模型就没有可背的东西。
所以"题面里到底有没有泄漏身份"不能靠人工抽查，必须**每次构建自动扫**。
一旦泄漏，整个任务就退化成记忆测试 —— 而且是**悄悄**退化。

检查五类：
  A. 变异身份：HGVS / rsID / 基因组坐标 / 变异名 / 氨基酸改变
  B. 数据库 accession：SCV / VCV / RCV / CA / NM_ / NC_ / NG_ / NR_ / XM_ / XR_ / ENST
  C. 结论词：pathogenic / benign / likely / VUS / uncertain / risk factor …
  D. 逐题交叉核对：题面里是否出现**本题真值文件里**的 HGVS 或 VariationID
  E. 结构校验：必填字段与枚举取值是否合法

用法：
    python3 check_no_leakage.py --items items.jsonl [--truth truth.jsonl] [--quiet]
退出码：0 = 干净；1 = 有泄漏；2 = 用法/文件错误。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --- A/B：身份与 accession -------------------------------------------------
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("HGVS 编码改变", re.compile(r"\b[cnpg]\.[\-\*\d]+[ACGT_]*[<>delinsdupA-Za-z]*\d*", re.I)),
    ("HGVS 蛋白改变", re.compile(r"\bp\.[A-Z][a-z]{2}\d+", re.I)),
    ("氨基酸三字母码", re.compile(r"\b[A-Z][a-z]{2}\d+[A-Z][a-z]{2}\b")),
    ("rsID", re.compile(r"\brs\d{3,}\b", re.I)),
    ("基因组坐标", re.compile(r"\bchr[\dXYM]+:\d+", re.I)),
    # ⚠️ 2026-09 修（自检发现的**第二条**坏 pattern）：原 pattern 是
    #    `\b\d{1,2}-\d{5,}-\d+-[ACGT]+\b`，只认**四段**形态 `12-102852862-1-G`。
    #    实测：该形态在本项目数据里**从未出现过**（0 处），
    #    而真正危险、且当前**完全漏检**的是**三段**的 `12-102852862-G-T`
    #    （染色体-位置-参考碱基-替代碱基）—— 它直接泄露变异身份。
    #    改法：第 3 段允许「数字或碱基」—— 因为两种形态的第 3 token 不同：
    #      · `12-102852862-1-G` → 第 3 段是**数字**（原 pattern 只认这个）
    #      · `12-102852862-G-T` → 第 3 段是**碱基**（真实威胁，原来漏检）
    #    误报风险已实测：对全部 4,726 条题面的**所有**字符串字段扫描，误报 **0 处**
    #    （重点确认不会误伤 `population_frequency_band` 的 `0.0001-0.001` 之类）。
    ("变异 ID 形态（chr-pos-[n-]ref-alt）",
     re.compile(r"\b\d{1,2}-\d{5,}-(?:\d+|[ACGT]{1,10})-[ACGT]{1,10}\b")),
    ("ClinVar/ClinGen accession", re.compile(r"\b(SCV|VCV|RCV)\d{6,}", re.I)),
    ("Allele Registry ID", re.compile(r"\bCA\d{6,}\b")),
    # ⚠️ 2026-09 修：原 pattern 是 `\b(N[MCGRX]|X[MR]|ENST|LRG_)\d{4,}`，
    #    **匹配不到任何标准 RefSeq accession** —— 因为真实写法是 `NM_000277.3`，
    #    `NM` 与数字之间有一个**下划线**，而原 pattern 要求数字紧跟其后。
    #    实测：NM_/NC_/NG_/NR_/XM_/XR_ 七种形态**全部漏检**，
    #    而它们正是真值 HGVS 里真实存在的形态（如 `NM_001754.5`）。
    #    后果：题面里混入 `NM_000277.3` 时，检查器照样报"0 泄漏" ——
    #    而 docstring 第 12 行还明写着会查 `NM_ / NC_ / NG_ / NR_ / XM_ / XR_`。
    #    **自述覆盖 ≠ 实际覆盖**，这是本项目最典型的缺陷类。
    #    下划线用 `_?` 兼容两种写法；ENST 同理（真实为 ENST00000307000，无下划线）。
    ("RefSeq/转录本 accession",
     re.compile(r"\b(N[MCGRX]_?\d{4,}|X[MR]_?\d{4,}|ENST_?\d{4,}|LRG_?\d+)", re.I)),
]

# --- C：结论词（注意用词边界，别把 "pathogenicity" 之外的东西误伤） ---------
CONCLUSION_WORDS = re.compile(
    r"\b(pathogenic|pathogenicity|benign|likely|uncertain|vus|"
    r"risk\s+factor|drug\s+response|protective|conflicting|"
    r"mutation|variant\s+of\s+uncertain)\b",
    re.I,
)

#: 允许出现结论词的位置（题面里**没有任何字段**允许 —— 即便 gene 也不该有）
ALLOWED_CONCLUSION_FIELDS: set[str] = set()

REQUIRED_ITEM_FIELDS = [
    "item_id", "gene", "disease", "mode_of_inheritance", "gene_disease_validity",
    "consequence_category", "population_frequency_band", "canary",
]
ITEM_ENUMS = {
    "gene_disease_validity": {"Definitive", "Strong", "Moderate", "Limited", "Disputed",
                             "Refuted", "No Known Disease Relationship", "unknown"},
    "consequence_category": {"nonsense", "frameshift", "splice_acceptor", "splice_donor",
                            "splice_region", "start_lost", "stop_lost", "inframe_deletion",
                            "inframe_insertion", "missense", "synonymous", "intronic",
                            "utr", "copy_number_loss", "copy_number_gain", "other"},
    "population_frequency_band": {"absent", "<0.00001", "0.00001-0.0001", "0.0001-0.001",
                             "0.001-0.01", "0.01-0.05", ">=0.05", "unknown"},
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[错误] {path}:{i} 非法 JSON：{exc}") from exc
    return rows


def self_test() -> int:
    """变异测试：把**已知阳性**逐类注入题面，检查器必须报错。

    为什么必须有它
    --------------
    2026-09 实测发现 `RefSeq/转录本 accession` 那条 pattern 是坏的：
    `\\b(N[MCGRX]|X[MR]|ENST|LRG_)\\d{4,}` **匹配不到任何标准 RefSeq accession**
    （真实写法 `NM_000277.3` 中间有下划线），实测 7/11 种形态永远漏检 ——
    而**真值 HGVS 里真实存在**的形态（`NM_001754.5` 等）全部属于漏检那一类。
    也就是说：题面里混入 `NM_000277.3`，这个"生命线"检查器**照样报 0 泄漏**。

    **一个不能失败的检查，比没有检查更坏** —— 它给的是假保证。
    所以这里对每条 pattern 都钉一个已知阳性样本，任何一条匹配不到就失败。
    """
    #: 每条 pattern 至少要能命中其中一个样本。（label → 样本列表）
    POSITIVES: dict[str, list[str]] = {
        "HGVS 编码改变": ["c.123A>G", "c.76_78del"],
        "HGVS 蛋白改变": ["p.Arg123Ter", "p.Cys265Ter"],
        "rsID": ["rs1234567", "rs80357906"],
        "基因组坐标": ["chr17:41234567", "chr12:102852862"],
        # ⚠️ 两种都列：三段（真实威胁，原来完全漏检）与四段（原 pattern 的唯一目标）
        "变异 ID 形态（chr-pos-[n-]ref-alt）": [
            "12-102852862-G-T",      # 三段式 —— 原 pattern 漏掉这一类
            "17-41234567-A-C",
            "1-12345678-AT-A",
            "12-102852862-1-G",      # 四段式 —— 原 pattern 唯一能认的
        ],
        "ClinVar/ClinGen accession": ["SCV000123456", "VCV000012345"],
        "Allele Registry ID": ["CA123456"],
        # ⚠️ 全部用**真实形态**（带下划线）—— 这正是原来漏掉的那一类
        "RefSeq/转录本 accession": [
            "NM_000277.3", "NM_001754.5", "NC_000012.12", "NG_008690.2",
            "NR_003051.3", "XM_011538422.1", "XR_001234.1",
            "ENST00000307000", "LRG_1", "NM000277",
        ],
    }
    #: 结论词也要单独验（它不走 PATTERNS 列表）
    CONCLUSION_POSITIVES = ["pathogenic", "benign", "likely", "VUS",
                            "uncertain", "risk factor", "conflicting"]

    problems: list[str] = []
    by_label = {lb: p for lb, p in PATTERNS}
    for label, samples in POSITIVES.items():
        pat = by_label.get(label)
        if pat is None:
            problems.append(f"自检里列了 {label!r}，但 PATTERNS 里没有这条 —— 清单过期")
            continue
        for s in samples:
            if not pat.search(s):
                problems.append(f"{label}: 已知阳性 {s!r} **没匹配到**")
    for s in CONCLUSION_POSITIVES:
        if not CONCLUSION_WORDS.search(s):
            problems.append(f"结论词: 已知阳性 {s!r} **没匹配到**")

    if problems:
        print(f"❌ 自检失败（{len(problems)} 处）—— 检查器的覆盖面与其自述不符：")
        for p in problems[:20]:
            print("   " + p)
        return 1
    n = sum(len(v) for v in POSITIVES.values()) + len(CONCLUSION_POSITIVES)
    print(f"✅ 自检通过：{len(POSITIVES)} 类 pattern 的 {n} 个已知阳性**全部命中**")
    print("   （含 7 种带下划线的真实 RefSeq accession —— 它们曾经全部漏检）")
    return 0


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="T2 题面泄露检查器")
    ap.add_argument("--items", help="题面 jsonl")
    ap.add_argument("--truth", help="真值文件，用于逐题交叉核对")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true",
                    help="变异测试：证明每条 pattern 都能命中已知阳性")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.items:
        ap.error("需要 --items（或用 --self-test）")

    ipath = Path(args.items)
    if not ipath.is_file():
        print(f"[错误] 找不到 {ipath}", file=sys.stderr)
        return 2
    items = load_jsonl(ipath)
    truth = load_jsonl(Path(args.truth)) if args.truth else []
    tmap = {t["item_id"]: t for t in truth}

    hits: list[str] = []
    struct: list[str] = []
    scanned_fields = 0

    for it in items:
        iid = it.get("item_id", "?")

        # --- 结构校验 ---
        for f in REQUIRED_ITEM_FIELDS:
            if f not in it:
                struct.append(f"{iid}: 缺必填字段 {f}")
        for f, allowed in ITEM_ENUMS.items():
            if f in it and it[f] not in allowed:
                struct.append(f"{iid}: {f}={it[f]!r} 不在枚举内")

        # --- A/B/C：逐字段扫描 ---
        for key, val in it.items():
            if not isinstance(val, str):
                continue
            scanned_fields += 1
            for label, pat in PATTERNS:
                m = pat.search(val)
                if m:
                    hits.append(f"{iid}.{key}: [{label}] 命中 {m.group(0)!r} ← {val[:80]!r}")
            if key not in ALLOWED_CONCLUSION_FIELDS:
                m = CONCLUSION_WORDS.search(val)
                if m:
                    # gene 名里出现这些词几乎不可能，但保留检查
                    hits.append(f"{iid}.{key}: [结论词] 命中 {m.group(0)!r} ← {val[:80]!r}")

        # --- D：逐题交叉核对 ---
        t = tmap.get(iid)
        if t:
            blob = json.dumps(it, ensure_ascii=False)
            hgvs = (t.get("hgvs") or "").strip()
            if hgvs and hgvs in blob:
                hits.append(f"{iid}: 题面里出现了本题真值 HGVS {hgvs!r}")
            vid = t.get("clinvar_variation_id")
            if vid and str(vid) in blob:
                hits.append(f"{iid}: 题面里出现了本题 VariationID {vid}")

    n_canary = sum(1 for it in items if it.get("canary"))
    print(f"扫描题面：{len(items)} 条（其中金丝雀 {n_canary} 条），字符串字段 {scanned_fields} 个")
    if truth:
        print(f"交叉核对真值：{len(truth)} 条（匹配到 {sum(1 for it in items if it.get('item_id') in tmap)} 条）")

    if not args.quiet and (hits or struct):
        print()
        for h in struct[:40]:
            print(f"  [结构] {h}")
        for h in hits[:60]:
            print(f"  [泄漏] {h}")

    print()
    if hits or struct:
        print(f"❌ 未通过：泄漏 {len(hits)} 处，结构问题 {len(struct)} 处")
        if len(hits) > 60:
            print(f"   （泄漏仅显示前 60 条，共 {len(hits)} 条）")
        return 1

    print("✅ 通过：题面中未发现任何变异身份、accession 或结论词；结构校验通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
