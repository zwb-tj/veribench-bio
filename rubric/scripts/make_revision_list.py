#!/usr/bin/env python3
"""把区分度 + 重测信度的结果，落成一份**可执行的 rubric 改写清单**。

为什么要落成文档
----------------
跑完两轮裁判，手里有：整题区分度、标准级诊断、重测信度。但这些是数字，
不是行动项。真正要交给人的是："**哪一条标准要改、改成什么样、依据是什么**"。

判据（两级筛选，避免把噪声当缺陷）
----------------------------------
1. **区分度**：同一裁判对三档答案给出递增分 → 该条标准有效
2. **重测信度**：同一批输入跑两遍，两遍都把该条判为缺陷 → **真缺陷**
   只有一遍判为缺陷的 → 归为噪声，**不出现在改写清单里**（但记账）

第 2 步是关键：第一轮有 11 条"饱和"、13 条"反向"，看起来触目惊心；
第二轮跑完发现其中 13 条并不复现——那正是单次判定的抖动。
**没有重复测量就分不清"标准坏了"和"这次手抖了"。**

用法：
    python3 make_revision_list.py --retest ../fixtures/answers/retest.json \
        --items ../items/items.jsonl --out ../docs/RUBRIC_V1.1_REVISION_LIST.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# 出题/判分过程中反复出现的结构缺陷模式。
# 内容来自两轮共 12 个裁判的独立反馈——**多人独立指向同一模式**才算数，
# 单个人的抱怨不进这张表。
PATTERNS = [
    {
        "name": "合取式 2 分锚点，没有部分给分规则",
        "hits": "两轮 12 个裁判中 9 个独立提出，且是稳定性损失的头号来源",
        "what": "2 分锚点用『且』串起 3–5 个要件，1 分锚点却只描述『笼统/泛泛』的最弱情形。"
                "于是最常见的那类回答——**切题具体、但缺 1–2 个子要件**——落在两档之间，"
                "没有锚点描述它，裁判只能按『不确定给低分』压到 1。",
        "example": "R-0024/c3 要求『未讨论正常增殖组织与免疫细胞依赖』且『未区分肿瘤自发糖酵解优势"
                   "与基质细胞供能假说』。多数回答实质性覆盖了前半、没碰后半 → 一律 1 分，"
                   "质量差很多的两份回答被抹平。R-0021/c3、R-0017/c1、R-0007/c3、R-0011/c3 同型。",
        "fix": "2 分锚点改成『核心论断 + 至少 N 项』；或把合取拆成两条独立标准；"
               "或把次要要件降为『如…』的举例。**必须让『具体但缺一项』有明确落点。**",
    },
    {
        "name": "跨标准重复计分（同一条标准之间不独立）",
        "hits": "两轮 12 个裁判中 6 个独立提出",
        "what": "同一句回答文本同时满足两条标准，协议没规定能否双记。"
                "后果是放大某些能力维度的权重，让总分不再是各维度的和。",
        "example": "R-0007 的 c1（无对照→自然病程/回归均值/**安慰剂效应**）与 c4"
                   "（未设盲→**期望效应**）落在同一句上；R-0011 的 c1/c4 都落在"
                   "『计算预测存在假阳性』；c2/c5 都落在『建议补细胞与动物实验』。",
        "fix": "在标准里明文规定某片段的归属；或把两条合并为一条带权重的标准。"
               "**尤其 c1（最薄弱环节）与 c4（只补一项实验）常把同一个实验算两次。**",
    },
    {
        "name": "1 分锚点用『否定式清单』而不是正面描述",
        "hits": "两轮 12 个裁判中 7 个独立提出",
        "what": "1 分锚点写成『提到 X 但未说明 Y、也未涉及 Z』。回答如果提到了 Y，"
                "这条锚点字面上就不适用；而 2 分锚点又要求 Y+Z 齐全 → 档位出现空档。",
        "example": "R-0023/c1 的 1 分档写『未说明因此不能归因、未涉及等效剂量匹配』，"
                   "而两份回答**恰好做了**这两件事，只是没凑齐 2 分档的四项列举 → 同一份"
                   "回答按锚点字面读是 2、按条目齐备度读是 1。",
        "fix": "1 分锚点改成正面描述：『提到了该议题，但没有点出具体缺陷/机制』。",
    },
    {
        "name": "锚点要求题面里根本推不出的事实",
        "hits": "两轮 12 个裁判中 4 个独立提出",
        "what": "锚点把一个**题面没有交代**的事实当作得分要件，回答无论怎么写都够不上，"
                "或只能靠猜。这类标准的部分档位**不可判**。",
        "example": "R-0013/c1 的 2 分档要求『如更正说明未展示任何原始数据』——但情景从未说明"
                   "更正说明里有没有原始数据；R-0012/c2 要求指出『分组由 CAP 定义』，"
                   "而题面没说用了哪个严重度终点。",
        "fix": "从锚点里删掉题面未交代的要件；或把缺的前提补进题面。",
    },
    {
        "name": "『若只能补做一项实验』的 0 分档不可达",
        "hits": "两轮 12 个裁判中 4 个独立提出",
        "what": "0 分锚点＝『未给出任何单一实验选择』。回答列了 3–4 条**都合理**的建议但没收敛到"
                "一项时，一律记 0；而同样的内容在 c3 上能记 1。同一个回答在不同条上被差别对待。",
        "example": "R-0001/c4、R-0006/c4、R-0003/c4。",
        "fix": "增设『方向合理但未收敛为单一实验 = 1』这一档。",
    },
    {
        "name": "枚举式锚点（要求列全 N 项）",
        "hits": "两轮 12 个裁判中 5 个独立提出",
        "what": "2 分锚点要求同时枚举若干个变量。回答抓到实质但没列全 → 判 1。"
                "这类锚点最容易人为压低一致性。",
        "example": "R-0023/c1 要求同时提『浓度、时长、起算时点、累积剂量』四项；"
                   "两份回答都完全没写『浓度』（而浓度恰恰与暴露方式共变），实质判断到位仍只能按字面降档。",
        "fix": "要求『至少 M 项』，并把其余降为举例。",
    },
]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="生成 rubric 改写清单")
    ap.add_argument("--retest", required=True)
    ap.add_argument("--discrimination")
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    retest = json.loads(Path(args.retest).read_text(encoding="utf-8"))
    items = {json.loads(l)["item_id"]: json.loads(l)
             for l in Path(args.items).read_text(encoding="utf-8").splitlines() if l.strip()}
    disc = json.loads(Path(args.discrimination).read_text(encoding="utf-8")) if args.discrimination \
        and Path(args.discrimination).is_file() else None

    detail = retest["criteria_detail"]
    real = [d for d in detail if d["reproduced"]]
    noisy = [d for d in detail if not d["reproduced"]]
    sat = [d for d in real if "saturated" in (d["verdict_run1"], d["verdict_run2"])]
    inv = [d for d in real if d not in sat]

    # 每条标准具体是**哪一档边界**在漂 —— 由 boundary_analysis 提供。
    # 这决定了该改哪个锚点：0↔1 漂要改 0/1 锚点的措辞；1↔2 漂要改 1/2 锚点。
    # 不做这一步，改写者只能瞎猜该动哪一档。
    bnd: dict[str, str] = {}
    bp = ROOT / "fixtures" / "answers" / "boundary_analysis.json"
    if bp.is_file():
        ba = json.loads(bp.read_text(encoding="utf-8"))
        v = ba.get("v1.1") or ba.get("v1.0") or {}
        for d in v.get("details_mid_hi", []):
            bnd[f"{d['item_id']}/{d['criterion_id']}"] = "1↔2"
        for d in v.get("details_0_to_1", []):
            k = f"{d['item_id']}/{d['criterion_id']}"
            bnd[k] = "1↔2 & 0↔1" if k in bnd else "0↔1"

    L: list[str] = []
    A = L.append
    A("# rubric v1.1 改写清单")
    A("")
    A("> 本文件由 `rubric/scripts/make_revision_list.py` 从 "
      "`rubric/fixtures/answers/retest.json` + `discrimination.json` 生成，**不要手改**；")
    A("> 改了数据就重新生成。定量结论全部可复算。")
    A(">")
    A("> ⚠️ 路径一律写成**相对仓库根**（`rubric/...`），不是相对本文件所在目录。")
    A("")
    A("## 一、先看证据：这份清单凭什么可信")
    A("")
    A("| 指标 | 值 | 含义 |")
    A("|---|---|---|")
    A(f"| 二次加权 κ（裁判自己 vs 自己，两轮） | **{retest['quadratic_weighted_kappa']}** | 同一裁判重复评同一输入的稳定性 |")
    A(f"| 两次完全一致 | {retest['exact_agreement'] * 100:.1f}% | {retest['n_units']} 个『标准×答案』单元 |")
    A(f"| 相差 ≤1 分 | {retest['adjacent_agreement'] * 100:.1f}% | 没有出现跨两档的翻转 |")
    A(f"| 平均绝对差 | {retest['mean_abs_diff']} 分（满分 2） | |")
    if disc:
        A(f"| 整题严格单调（浅<中<优） | {disc['strict_monotonic_rate'] * 100:.1f}% | {disc['n_items']} 题 |")
        A(f"| 至少 优>浅 | {disc['weak_lt_strong_rate'] * 100:.1f}% | |")
        A(f"| 归一化得分 浅/中/优 | {disc['overall_normalized']['weak']:.3f} / "
          f"{disc['overall_normalized']['medium']:.3f} / {disc['overall_normalized']['strong']:.3f} | 满分 1.0 |")
    A("")
    A("**这两组数字要一起读**，单看哪一组都会得出错误结论：")
    A("")
    A(f"- 只看区分度：11 条『饱和』+ 13 条『反向』，像是 rubric 大面积失效。")
    A(f"- 只看重测：κ={retest['quadratic_weighted_kappa']}，裁判稳得很。")
    A(f"- **合起来**：裁判稳定 → 那些失败**不是手抖，是标准本身判不动**。")
    A(f"  再跑第二轮一筛，第一轮的 24 条里只有 **{len(real)} 条复现** → 那 {len(noisy)} 条是噪声，")
    A(f"  剩下 {len(real)} 条才是真缺陷。**没有重复测量，这两类根本分不开。**")
    A("")
    A(f"## 二、确认报废的标准：{len(real)} 条（两轮都判为缺陷）")
    A("")
    if sat:
        A(f"### 2.1 饱和型（三档同分，对总分只加噪声）：{len(sat)} 条")
        A("")
        A("| 题目 | 标准 | 两轮得分（浅/中/优） | 问题 |")
        A("|---|---|---|---|")
        for d in sat:
            A(f"| {d['item_id']} | {d['criterion_id']} | run1 {d['run1']} · run2 {d['run2']} | "
              f"{'恒为满分，白送分' if d['run1'][0] == 2 else ('恒为 0，无人能得' if d['run1'][0] == 0 else '恒定中间分')} |")
        A("")
    if inv:
        A(f"### 2.2 反向型（浅档不低于优档）：{len(inv)} 条")
        A("")
        A("| 题目 | 标准 | 两轮得分（浅/中/优） |")
        A("|---|---|---|")
        for d in inv:
            A(f"| {d['item_id']} | {d['criterion_id']} | run1 {d['run1']} · run2 {d['run2']} |")
        A("")
    A("### 2.3 逐条原文（改写时直接对着改）")
    A("")
    for d in real:
        it = items.get(d["item_id"], {})
        crit = next((c for c in it.get("criteria", []) if c.get("criterion_id") == d["criterion_id"]), {})
        A(f"#### {d['item_id']} / {d['criterion_id']}  —— {d['verdict_run1']} + {d['verdict_run2']}")
        A("")
        A(f"- 两轮得分：run1 `{d['run1']}` · run2 `{d['run2']}`（浅/中/优，满分 2/条）")
        b = bnd.get(f"{d['item_id']}/{d['criterion_id']}")
        if b:
            A(f"- **漂移边界：{b}** ← 只改这一档的锚点措辞，别动另一档")
        A(f"- 标准正文：{crit.get('text', '（未找到）')}")
        for k in ("0", "1", "2"):
            a = (crit.get("anchors") or {}).get(k)
            if a:
                A(f"  - `{k}` 分：{a}")
        A("")
    A(f"## 三、结构缺陷模式（{len(PATTERNS)} 类，改 v1.1 时优先处理）")
    A("")
    A("这些不是某一条标准的问题，而是**写法**的问题——它们会在新写的标准里复发。")
    A("每条都标注了有多少个裁判**独立**提出（多人独立指向同一模式才算数）。")
    A("")
    for i, p in enumerate(PATTERNS, 1):
        A(f"### 3.{i} {p['name']}")
        A("")
        A(f"- **佐证**：{p['hits']}")
        A(f"- **是什么**：{p['what']}")
        A(f"- **实例**：{p['example']}")
        A(f"- **改法**：{p['fix']}")
        A("")
    A(f"## 四、判为噪声、不改的 {len(noisy)} 条（记账，不改）")
    A("")
    A("第一轮看着像缺陷、第二轮不复现。**改这些等于对着噪声调参。**")
    A("")
    A("| 题目 | 标准 | run1 | run2 |")
    A("|---|---|---|---|")
    for d in noisy:
        A(f"| {d['item_id']} | {d['criterion_id']} | {d['run1']} ({d['verdict_run1']}) | "
          f"{d['run2']} ({d['verdict_run2']}) |")
    A("")
    A("## 五、必须随本清单一起报告的局限")
    A("")
    for x in retest.get("limitations", []):
        A(f"- {x}")
    if disc:
        for x in disc.get("limitations", []):
            A(f"- {x}")
    A("- **本清单是改写候选，不是判决。** 每条仍需人工判断该标准是否值得保留、还是应当整条删除。")
    A("")

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text("\n".join(L), encoding="utf-8", newline="")

    print(f"真缺陷 {len(real)} 条（饱和 {len(sat)} + 反向 {len(inv)}），噪声 {len(noisy)} 条")
    print(f"结构缺陷模式 {len(PATTERNS)} 类")
    print(f"→ {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
