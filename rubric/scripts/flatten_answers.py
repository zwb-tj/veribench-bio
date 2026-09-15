#!/usr/bin/env python3
"""把"一题三档"的嵌套答案摊平成 judge 链要的一行一答格式。

嵌套（便于人工阅读）:
    {"item_id": "R-0001", "answers": [{"answer_id": "weak", "text": "…"}, …]}

摊平（judge 链的输入，见 fixtures/io/answers_fake.jsonl）:
    {"item_id": "R-0001", "answer": "…", "model": "BLIND-weak", "run": 1}

`model` 字段用来标记答案档位，**裁判看不到它**（build_judge_inputs 只把
题面与答案正文写进提示词），所以不会污染评分。它只用于事后分析。

用法：
    python3 flatten_answers.py --in ../fixtures/answers/answers_blind_1.jsonl \
        ../fixtures/answers/answers_blind_2.jsonl --out ../fixtures/answers/answers_flat.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LEVELS = ["weak", "medium", "strong"]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="摊平嵌套答案")
    ap.add_argument("--in", dest="inputs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="BLIND")
    ap.add_argument("--only-level", choices=LEVELS,
                    help="只输出某一档。⚠️ judge 链的 build_judge_inputs.py 按 item_id 去重"
                         "（它假定一题一答），所以三档答案必须分三次构造输入")
    args = ap.parse_args(argv)

    rows: list[dict] = []
    for p in args.inputs:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            for a in r["answers"]:
                if a["answer_id"] not in LEVELS:
                    print(f"❌ {r['item_id']}: 未知档位 {a['answer_id']!r}")
                    return 1
                if args.only_level and a["answer_id"] != args.only_level:
                    continue
                rows.append({
                    "item_id": r["item_id"],
                    "answer": a["text"],
                    "model": f"{args.tag}-{a['answer_id']}",
                    "run": 1,
                })

    # 顺序固定为 题号 → 档位，便于人工核对；judge 侧不看顺序
    rows.sort(key=lambda r: (r["item_id"], LEVELS.index(r["model"].split("-")[-1])))

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    by_item: dict[str, int] = {}
    for r in rows:
        by_item[r["item_id"]] = by_item.get(r["item_id"], 0) + 1
    counts = {v for v in by_item.values()}
    # --only-level 时每题自然是 1 条；全量时必须是 3 条（weak/medium/strong 齐全）
    expect = {1} if args.only_level else {3}
    print(f"摊平 {len(rows)} 条答案，覆盖 {len(by_item)} 题 → {op}")
    print(f"  每题答案数：{sorted(counts)}（应为 {sorted(expect)}）")
    if counts != expect:
        print(f"❌ 有题目的答案数不是 {sorted(expect)}")
        return 1
    for lv in LEVELS:
        n = sum(1 for r in rows if r["model"].endswith(lv))
        print(f"  {lv:7}: {n} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
