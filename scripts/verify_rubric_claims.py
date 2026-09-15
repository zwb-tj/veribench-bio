#!/usr/bin/env python3
"""**重新测量** rubric 支柱的关键数字，并与 README / DATACARD 比对。

为什么还有第三个这样的脚本
--------------------------
T1、T2 各有一个。理由相同：**文档里的数字从来没有被系统核对过**。
前几轮已抓到两个真错（`40,110`→`40,170`、"镜像 digest 尚未 pin"其实一直记着）。
rubric 是最后一个没被查过的支柱。

**这个脚本我写了五版，前四版都错在"想用启发式去猜哪个数字属于哪个断言"。**
每一版的错法都记在下面，因为它们比结论更有用：

  1. 把 README+DATACARD **拼成一个字符串**再 `in`
     → 一份写对、另一份写错时**漏检**（被负向测试抓到）
  2. 改成"要求每份文档都出现该字符串"
     → README 只报要点、不报 κ 细节，被判成"不符" —— **把详细程度不同误判成不一致**
  3. 改成"按关键词选行，再核对该行所有数字"
     → 文档把多个指标压在同一行（表格行），必然误报
  4. 改成"锚点带捕获组" —— 但正则替换没生效，`groups()` 为空，
     **检查静默变成永远通过的空壳**（最糟的一种：它比没有更坏，因为它给人安全感）

**最终采取的写法：不猜。** 每个断言写清楚"哪个指标、实测值是多少、哪几份文档
必须报告它"，然后用最直白的字符串包含判断。
措辞一改检查就会失败——那正是我们要的：**强制人来看一眼**，而不是猜。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                     # bio-eval/
R = ROOT / "rubric"

results: list[tuple[str, str, bool | None, str]] = []


def add(claim: str, kind: str, ok: bool | None, ev: str) -> None:
    results.append((claim, kind, ok, ev))


def run_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    v12 = R / "items" / "items_v1.2.jsonl"
    if not v12.is_file():
        print("SKIP: 缺 rubric/items/items_v1.2.jsonl")
        return 0

    README = (ROOT / "README.md").read_text(encoding="utf-8")
    CARD = (ROOT / "docs" / "DATACARD.md").read_text(encoding="utf-8")

    def must_appear(kind: str, claim: str, needle: str,
                    where: dict[str, str]) -> None:
        """`needle` 必须在 `where` 指定的每一份文档里出现。

        **哪几份文档必须报告这一项，是显式写出来的，不靠猜。**
        """
        miss = [n for n, text in where.items() if needle not in text]
        add(claim, kind, not miss,
            f"需要「{needle}」出现在 {list(where)}；"
            + ("都在" if not miss else f"**缺** {miss}"))

    # ---- 1) 题量 / 标准数（两份文档都报）----
    items = run_jsonl(v12)
    n_items, n_crit = len(items), sum(len(i["criteria"]) for i in items)
    both = {"README.md": README, "docs/DATACARD.md": CARD}
    must_appear("可复算", "README 与 DATACARD 都报告了正确的题量",
                f"{n_items} 题", both)
    must_appear("可复算", "README 与 DATACARD 都报告了正确的标准数",
                f"{n_crit} 条标准", both)
    add("实测题量 / 标准数符合 SPEC 的 v1 目标（24 题）", "可复算",
        n_items == 24 and n_crit == 101, f"实测 {n_items} 题 / {n_crit} 条")

    # ---- 2) 台账条目数 ----
    led = R / "ledger" / "rubric_items.jsonl"
    if led.is_file():
        n_led = len(run_jsonl(led))
        add("rubric 台账条数与题目数一致", "可复算", n_led == n_items,
            f"台账 {n_led} 条 vs 题目 {n_items} 题")

    # ---- 3) κ（DATACARD 报，README 不报 —— 这是显式约定的，不是漏检）----
    for tag, p in (("v1.0", R / "fixtures" / "answers" / "retest.json"),
                   ("v1.1", R / "fixtures" / "answers" / "v1.1" / "retest.json")):
        if not p.is_file():
            add(f"裁判重测 κ {tag}", "可复算", None, f"缺 {p.name}")
            continue
        k = json.loads(p.read_text(encoding="utf-8")).get("quadratic_weighted_kappa")
        must_appear("可复算", f"DATACARD 报告的重测 κ {tag} 与实测一致",
                    f"{k:.4f}", {"docs/DATACARD.md": CARD})

    # ---- 4) 需要源文的两项 ----
    src = R / "items" / "sources"
    if not src.is_dir() or not list(src.glob("PMC*.txt")):
        add("数字保真（155 个数字 / 0 个查不到）", "需源文", None,
            "items/sources/ 刻意不随仓库发布；需先跑 fetch_source_text.py")
        add("反抄袭 0 泄漏（约 1.47M 字符全文比对）", "需源文", None, "同上")
    else:
        r = subprocess.run([sys.executable, str(R / "scripts" / "check_numeric_fidelity.py"),
                            "--items", str(v12), "--sources", str(src),
                            "--out", str(R / "items" / "_claim_numeric.json")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        m = re.search(r"核对\s*(\d+)\s*个数字，未在原文找到\s*(\d+)\s*个", out)
        if not m:
            add("能从数字保真检查的输出里读到统计", "可复算", False, out.strip()[-140:])
        else:
            got_n, got_miss = int(m.group(1)), int(m.group(2))
            must_appear("可复算", "数字保真：文档报告的核对数 = 实测",
                        f"{got_n} 个数字", both)
            # 文档写"0 个查不到"；这里把两种措辞都接受，但**要求实测确实是 0**
            ok_words = ("0 个查不到" in CARD) or ("0 个未找到" in CARD) or ("0 个未找到" in README)
            add("数字保真：实测 0 个查不到，且文档如实这么写", "可复算",
                got_n == 155 and got_miss == 0 and ok_words,
                f"实测 {got_n} 个、未找到 {got_miss} 个；文档措辞"
                f"{'匹配' if ok_words else '**对不上**'}")

        chars = sum(len(f.read_text(encoding="utf-8", errors="replace"))
                    for f in src.glob("PMC*.txt"))
        # ⚠️ 文档用的是**四舍五入**写法（"1.47M 字符"），不是精确值。
        #    所以接受"实测值的若干合法写法"，而不是只认一种 ——
        #    上一版只认精确式 `1,466,549 字符`，把写对了的 DATACARD 判成不符。
        #    这与数值核对的目标不冲突：**写法可以不同，数值必须对得上**。
        forms = {f"{chars:,} 字符", f"{chars} 字符", f"{chars / 1e6:.2f}M 字符"}
        hit = [f for f in forms if f in CARD]
        add("DATACARD 报告的源文总量与实测一致（允许精确或四舍五入写法）", "可复算",
            bool(hit), f"实测 {chars:,} 字符；接受 {sorted(forms)}；命中 {hit or '**无**'}")
        add("源文总量与既有记载一致（约 1.47M）", "可复算",
            abs(chars - 1_466_549) < 2000, f"实测 {chars:,} 字符")

    # ---- 5) 人类数据裁决 ----
    adj_p = R / "items" / "human_data_basis.json"
    if adj_p.is_file():
        adj = json.loads(adj_p.read_text(encoding="utf-8"))["adjudication"]
        T = {"human_subjects_primary", "human_biospecimen"}
        self_ok = all((v["basis"] in T) == v["value"] for v in adj.values())
        must_appear("可复算", "裁决条数与文档报告的 27/27 一致",
                    f"{len(adj)}/27", both)
        add("人类数据裁决自洽（basis 与布尔值无矛盾）", "可复算", self_ok,
            f"{len(adj)} 条，自洽={self_ok}")

    w = max(len(c) for c, _, _, _ in results)
    print(f"{'断言'.ljust(w)}  {'档位':<8}结论")
    print("-" * (w + 42))
    for claim, kind, ok, ev in results:
        mark = "✅" if ok is True else ("❌" if ok is False else "⚠️")
        print(f"{claim.ljust(w)}  {kind:<8}{mark}")
        print(f"{' ' * w}  └ {ev}")

    n_bad = sum(1 for _, _, ok, _ in results if ok is False)
    un = sum(1 for _, _, ok, _ in results if ok is None)
    print(f"\n共 {len(results)} 条：通过 {len(results) - n_bad - un} · 不符 {n_bad} · 无法验证 {un}")
    if n_bad:
        print("❌ rubric 的文档数字与实际不符 —— **改文档，不要改事实**。")
        return 1
    print("✅ rubric 的可复算断言全部与产物一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
