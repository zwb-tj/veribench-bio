#!/usr/bin/env python3
"""生成**人工质量复核表**。

为什么需要它
-----------
结构检查（条数/锚点/身份泄露）能自动验，但**质量**验不了：
题目在科学上成不成立、rubric 是否真的可判定、锚点是否切得开 0/1/2 ——
这些必须由**领域专家**判断。

本表的目标是让复核**尽量省力**：每题一屏，题面、rubric、锚点、来源论文并列，
复核者只需在对应 JSONL 里填 `verdict`。

⚠️ 复核表里**会显示来源论文**（否则无法判断题目是否忠实于原文），
   所以**复核表本身不进公开仓库** —— 公开的只有 `items.jsonl`。

用法：
    python3 make_review_sheet.py --items ../items/items.jsonl \
        --mapping ../items/mapping.jsonl --out ../items/review_sheet.md \
        --template ../items/review_verdicts.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="生成 rubric 题人工复核表")
    ap.add_argument("--items", required=True)
    ap.add_argument("--mapping", help="item_id ↔ 来源论文（复核可见，不公开）")
    ap.add_argument("--out", required=True, help="Markdown 复核表路径")
    ap.add_argument("--template", help="生成待填的复核结果 JSONL")
    args = ap.parse_args(argv)

    items = load(Path(args.items))
    mapping = {m["item_id"]: m for m in load(Path(args.mapping))} if args.mapping else {}

    lines = [
        "# rubric 题 · 人工质量复核表",
        "",
        f"共 **{len(items)}** 道题。每题请给一个判定：",
        "",
        "| 判定 | 含义 |",
        "|---|---|",
        "| `accept` | 科学上成立，rubric 可判定，锚点能切开档位 |",
        "| `revise` | 方向对但需改（在 comment 里写清怎么改） |",
        "| `reject` | 题目不成立 / 与原文不符 / 无法客观评分 |",
        "",
        "**复核重点（结构检查查不出来的那部分）**：",
        "1. 情景描述**是否忠实于原文**（有没有把作者的结论改错）",
        "2. rubric 是否**真的可判定** —— 换一位专家来打，会不会得到同一个分",
        "3. 三个锚点**是否切得开** —— `0`/`1`/`2` 的界线清楚吗，还是凭感觉",
        "4. 题目是否**真的在考推理**，而不是在考「知不知道某个名词」",
        "5. 若原文本身没有明显薄弱环节 → 该题应 `reject`（不要为了凑数留）",
        "",
        "---",
        "",
    ]

    for it in items:
        iid = it["item_id"]
        m = mapping.get(iid, {})
        lines.append(f"## {iid}")
        lines.append("")
        if m:
            lines.append(f"> **来源（仅复核可见，不公开）**：{m.get('source_ref')} · "
                         f"{m.get('license_spdx')} · <{m.get('source_url')}>")
            lines.append("")
        lines.append("**题目**：")
        lines.append("")
        for para in (it.get("question") or "").split("\n"):
            lines.append(f"> {para}")
        lines.append("")
        if it.get("context"):
            lines.append("**背景**：")
            lines.append("")
            for para in (it.get("context") or "").split("\n"):
                lines.append(f"> {para}")
            lines.append("")
        lines.append("**评分标准**：")
        lines.append("")
        for c in it.get("criteria") or []:
            a = c.get("anchors") or {}
            lines.append(f"- **{c['criterion_id']}** {c.get('text','')}")
            lines.append(f"  - `0` {a.get('0','')}")
            lines.append(f"  - `1` {a.get('1','')}")
            lines.append(f"  - `2` {a.get('2','')}")
        lines.append("")
        lines.append(f"**判定**：`accept` / `revise` / `reject` ｜ **备注**：")
        lines.append("")
        lines.append("---")
        lines.append("")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8", newline="")
    print(f"复核表 → {out}（{len(items)} 题）")

    if args.template:
        t = Path(args.template)
        with t.open("w", encoding="utf-8", newline="") as fh:
            for it in items:
                fh.write(json.dumps({
                    "item_id": it["item_id"],
                    "verdict": None,      # accept / revise / reject
                    "comment": "",
                    "reviewer": "",
                }, ensure_ascii=False) + "\n")
        print(f"待填模板 → {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
