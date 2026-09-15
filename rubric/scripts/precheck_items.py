#!/usr/bin/env python3
"""items_draft.jsonl 的额外自检（在 make_annotation_sheets.py --check-only 之外）。

覆盖 make_annotation_sheets.py 不检查的东西：
  1. provenance 字段与 candidates.jsonl / manifest.jsonl 是否一致（防编造）
  2. 结构字段是否齐全、枚举值是否合法
  3. 除正则身份标识外的"软身份线索"：期刊名 / 出版社 / 论文标题片段 / 品牌名 / 公司名
  4. item_id 是否 R-0001 起连续
  5. 题面长度、是否含疑似原文长句（与 source 的 n-gram 重合检测）

用法：
    python precheck_items.py --items ../items/items_draft.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ITEMS_DIR = HERE.parent / "items"
CANDIDATES = ITEMS_DIR / "candidates.jsonl"
MANIFEST = ITEMS_DIR / "sources" / "manifest.jsonl"
SOURCES = ITEMS_DIR / "sources"

# 期刊 / 出版社 / 平台名（出现即视为身份线索）
JOURNAL_TOKENS = [
    "Int J Mol Sci", "International Journal of Molecular Sciences", "MDPI",
    "Multidisciplinary Digital Publishing", "Cureus", "PLoS", "Frontiers in",
    "Scientific Reports", "Nature Communications", "PubMed", "Scopus",
    "Cochrane", "bioRxiv", "medRxiv", "ClinicalTrials.gov", "PMC", "PMID",
    "doi:", "DOI:",
]

PROVENANCE_FIELDS = [
    "source_type", "source_ref", "source_url", "source_license_code",
    "license_spdx", "license_url", "retrieval_date", "redistribution_ok",
    "commercial_ok", "contains_human_data", "contains_restricted_data",
    "visibility", "derivation_note",
]

# 许可判定字段：一个来源只有一份许可结论，题目**必须**与 candidates 逐字一致。
# 这些字段错了就是合规事故，所以强锁。
LICENSE_FIELDS = [
    "source_license_code", "license_spdx", "license_url", "retrieval_date",
    "redistribution_ok", "commercial_ok", "contains_restricted_data", "visibility",
]

# 事实判定字段：**不能**锁死在 candidates 上（见下）。
# 教训：candidates.jsonl 曾把 27 篇一律标成 contains_human_data=true（含蜜蜂、
# 大鼠、综述）。本脚本当时强制"与 candidates 一致"，于是把同一个未经核实的
# 值复制进 24 道题，并在有人试图改成正确值时报"禁止编造"——一个把错误
# 冻结起来、还堵住纠正路径的校验。事实字段的单一真值源应当是**裁决文件**
# （items/human_data_basis.json，带证据），而不是上一版数据本身。
FACT_FIELDS = ["contains_human_data"]
ADJUDICATION = ITEMS_DIR / "human_data_basis.json"


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def norm_words(s: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", s.lower())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    args = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    items = load_jsonl(Path(args.items))
    cands = {c["item_id"]: c for c in load_jsonl(CANDIDATES)}
    # ⚠️ `items/sources/`（含 manifest.jsonl）是**刻意不发布**的 —— 那是别人的论文全文。
    #    第三方 clone 下来这里必然为空，于是标题比对与 n-gram 重合检查**无法执行**。
    #    这不是失败，是"那两项没跑"。必须**明说**，不能静默跳过 ——
    #    静默跳过会让人以为"所有检查都过了"（本项目原则 7）。
    manifest = {m["pmcid"]: m for m in load_jsonl(MANIFEST)} if MANIFEST.is_file() else {}
    titles = [m.get("title", "") for m in manifest.values()]
    if not manifest:
        print(f"⚠️ 找不到 {MANIFEST.relative_to(HERE.parent)} —— "
              f"**标题比对与原文 n-gram 重合检查本次未执行**")
        print(f"   （items/sources/ 不随仓库发布；需先跑 fetch_source_text.py 才能做这两项）")

    adj = {}
    if ADJUDICATION.is_file():
        adj = json.loads(ADJUDICATION.read_text(encoding="utf-8")).get("adjudication", {})
    else:
        print(f"⚠️ 找不到裁决文件 {ADJUDICATION}，contains_human_data 将不做核验")

    problems: list[str] = []
    notes: list[str] = []

    # item_id 连续性：批次文件天然从中间号段开始，不算问题。
    is_batch = "batch" in Path(args.items).name.lower()
    expect = [f"R-{i:04d}" for i in range(1, len(items) + 1)]
    got = [it.get("item_id") for it in items]
    if got != expect:
        msg = f"item_id 不是 R-0001 起连续：{got[:5]}... vs 期望 {expect[:5]}..."
        if is_batch:
            notes.append(msg + "（批次文件，合并后校验；assemble 会重编号）")
        else:
            problems.append(msg)

    for it in items:
        iid = it.get("item_id", "?")
        # 结构字段
        for f in ("question", "context", "criteria", "provenance", "safety_review"):
            if f not in it:
                problems.append(f"{iid}: 缺字段 {f}")
        prov = it.get("provenance") or {}
        for f in PROVENANCE_FIELDS:
            if f not in prov:
                problems.append(f"{iid}: provenance 缺 {f}")
        if it.get("safety_review") != "not-applicable":
            notes.append(f"{iid}: safety_review={it.get('safety_review')!r}（预期 not-applicable）")

        src = prov.get("source_ref")
        c = cands.get(src or "")
        m = manifest.get(src or "")
        if not c:
            problems.append(f"{iid}: source_ref={src!r} 不在 candidates.jsonl 中")
        else:
            # 许可判定：强锁，与 candidates 逐字一致（一个来源一份许可结论）
            for f in LICENSE_FIELDS:
                if prov.get(f) != c.get(f):
                    problems.append(
                        f"{iid}: provenance.{f}={prov.get(f)!r} 与 candidates 的 {c.get(f)!r} "
                        f"不一致——许可结论是每个来源一份，改动必须回到 candidates.jsonl")

            # 事实判定：核对**裁决文件**，不是核对上一版数据。
            # 若与 candidates 不一致但与裁决文件一致 → 说明 candidates 是旧值，
            # 提示同步（不是"编造"）。
            a = adj.get(src or "")
            for f in FACT_FIELDS:
                if a is None:
                    continue
                if prov.get(f) != a.get("value"):
                    problems.append(
                        f"{iid}: provenance.{f}={prov.get(f)!r}，但裁决文件 {src} 判定为 "
                        f"{a.get('value')!r}（{a.get('basis')}）。以裁决文件为准")
                if prov.get(f) != c.get(f):
                    notes.append(
                        f"{iid}: {f}={prov.get(f)!r} 与 candidates 的旧值 {c.get(f)!r} 不同"
                        f"（裁决依据：{a.get('basis')}）——candidates.jsonl 需同步更新")
                if not prov.get("human_data_basis") and f == "contains_human_data":
                    notes.append(f"{iid}: 建议写入 human_data_basis={a.get('basis')!r} 以便审计")
        if m and prov.get("source_url") != f"https://www.ncbi.nlm.nih.gov/pmc/articles/{src}/":
            problems.append(f"{iid}: source_url 与 source_ref 不匹配：{prov.get('source_url')!r}")
        if prov.get("source_type") != "derived_from_paper":
            problems.append(f"{iid}: source_type 必须是 derived_from_paper")

        # 软身份线索
        blob = (it.get("question", "") + "\n" + (it.get("context") or ""))
        for tok in JOURNAL_TOKENS:
            if tok.lower() in blob.lower():
                problems.append(f"{iid}: 题干/背景含期刊或平台线索 {tok!r}")

        # 与原文的 n-gram 重合（>=12 词的连续重合视为复制原文）
        srcfile = SOURCES / f"{src}.txt"
        if srcfile.exists():
            src_words = norm_words(srcfile.read_text(encoding="utf-8", errors="replace"))
            src_ngrams = set(tuple(src_words[i:i + 12]) for i in range(max(0, len(src_words) - 12)))
            for fieldname in ("question", "context"):
                w = norm_words(it.get(fieldname) or "")
                for i in range(max(0, len(w) - 12)):
                    g = tuple(w[i:i + 12])
                    if g in src_ngrams:
                        problems.append(
                            f"{iid}/{fieldname}: 与原文有 12 词连续重合 {' '.join(g[:8])}... —— 疑似复制原文")
                        break

        # 论文标题片段
        for t in titles:
            tw = norm_words(t)
            for i in range(max(0, len(tw) - 6)):
                g = " ".join(tw[i:i + 6])
                if g and g in blob.lower():
                    problems.append(f"{iid}: 题干/背景与某论文标题有 6 词重合 {g!r}")
                    break

        # 题面长度
        q = it.get("question") or ""
        if len(q) > 1600:
            notes.append(f"{iid}: 题干 {len(q)} 字符，偏长")

    print(f"补充预检：{len(items)} 题 —— 硬问题 {len(problems)}，提示 {len(notes)}")
    for p in problems:
        print(f"  ❌ {p}")
    for n in notes:
        print(f"  ℹ️ {n}")
    if not problems:
        print("  ✅ 无额外硬问题")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
