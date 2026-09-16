#!/usr/bin/env python3
"""检查锚点是否要求了**裁判看不到的事实**（R2 违例）。

为什么这是最硬的一类缺陷
------------------------
前面的区分度/操纵检验都在问"裁判判得稳不稳"。但有一类缺陷**不需要任何裁判**就能判定：

> 裁判能看到的只有【问题】+【待评的回答】+【评分标准】三块（见 judge_prompt_v1.md）。
> 若某条锚点把**问题里根本没出现的事实**当作得分要件，那么无论回答怎么写，
> 裁判都无法核实它 —— 这一档**不可判**。

这不是"措辞含糊"，是**结构性不可判**。而且它是可机械检查的：
把锚点里的**具体事实**（数字、实测值）抽出来，逐个到题面里找。找不到就是违例。

⚠️ 与 `check_numeric_fidelity.py` 的区别
---------------------------------------
那个查的是"**题目**引用的数字是否真在**原文论文**里"（防编造）。
这个查的是"**锚点**要求的事实是否在**题面**里"（防不可判）。
两者方向相反：前者要求数字**必须**来自原文，后者要求要件**必须**出现在题面。
所以同一个数字"在原文里"但"不在题面里"，恰恰就是 R2 违例的典型形态。

局限
----
- 只抓**数字型**事实。纯文字型的事实（如"未按泪液流率归一化"）抓不到，
  需要人工或 LLM 复核 —— 本脚本会把这些条目标为"需人工看"。
- "题面里没有这个数字" ≠ 一定是违例：也可能锚点用的是一个**可由题面推出**
  的派生量（如"约 30 例"来自"n=27"）。所以输出是**待确认清单**，不是判决。

用法：
    python3 check_anchor_grounding.py --items ../items/items.jsonl \
        --out ../items/anchor_grounding.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 锚点里出现的"具体事实"形态：p 值、百分比、小数、4 位以上整数、单位量
FACT_PATTERNS = [
    (r"[pP]\s*[=＝<>≤≥]\s*(\d+\.\d+)", "p 值"),
    (r"(\d+\.\d+)\s*%", "百分比"),
    (r"(\d+)\s*%", "整百分比"),
    (r"(\d+\.\d+)", "小数"),
    (r"\b(\d{3,})\b", "整数"),
]


def facts(text: str) -> list[tuple[str, str]]:
    out = []
    for pat, kind in FACT_PATTERNS:
        for m in re.finditer(pat, text):
            out.append((m.group(1), kind))
    return out


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="锚点事实可判性检查（R2）")
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    rows = [json.loads(l) for l in Path(args.items).read_text(encoding="utf-8").splitlines() if l.strip()]
    report = []
    n_viol = 0
    for it in rows:
        iid = it["item_id"]
        # 裁判能看到的就是这两块（题面 + 背景）
        visible = (it.get("question") or "") + "\n" + (it.get("context") or "")
        vis_norm = visible.replace(",", "").replace("，", "")
        for c in it["criteria"]:
            cid = c["criterion_id"]
            # ⚠️ 必须同时查**标准正文**，不能只查锚点。
            #    第一版只查锚点，于是漏掉了 R-0020/c1 —— 它把
            #    "文中 P 值在 0.01–0.06 之间"写在了 **text** 里（题面根本没给 p 值），
            #    而裁判同样看得到 text，所以这条照样不可判。
            missing = []
            for field, label in (("text", "正文"), ("anchors", "锚点")):
                if field == "text":
                    chunks = [(c.get("text", ""), label)]
                else:
                    chunks = [((c.get("anchors") or {}).get(k, ""), f"{k} 分档")
                              for k in ("0", "1", "2")]
                for content, where in chunks:
                    for tok, kind in facts(content):
                        if tok in vis_norm:
                            continue
                        try:
                            if len(tok) >= 4 and f"{int(tok):,}" in visible:
                                continue
                        except ValueError:
                            pass
                        if not any(x[0] == tok and x[2] == where for x in missing):
                            missing.append((tok, kind, where))
            if missing:
                n_viol += 1
                print(f"❌ {iid}/{cid}  含题面里没有的数字：")
                for tok, kind, where in missing:
                    print(f"      {where}：{tok}（{kind}）")
            report.append({"item_id": iid, "criterion_id": cid,
                           "criterion_text": c["text"][:100],
                           "ungrounded": [{"value": t, "kind": kd, "where": w} for t, kd, w in missing]})

    total = len(report)
    print()
    print("=" * 70)
    print(f"检查 {total} 条标准的**正文与三档锚点**："
          f"**{n_viol} 条含题面里查不到的数字**")
    if n_viol:
        print()
        print("解释：这些档位要求裁判核对一个题面里没有给出的事实。")
        print("裁判**无法核实**它 → 该档不可判。这不是措辞问题，是结构问题。")
        print("修法只有两条（见 REVISION_RULES_V1.1 的 R2）：")
        print("  · 把该要件从锚点里删掉；或")
        print("  · 把该事实补进题面，再要求")
    else:
        print("✅ 没有发现『锚点要求题面外事实』的数字型证据。")
        print("   ⚠️ 但文字型要件（如『未按泪液流率归一化』）抓不到，仍需人工复核。")

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="")
    print(f"\n明细 → {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
