#!/usr/bin/env python3
"""生成 T2 的对照作答（基线），用来标定评分尺度的**天花板与地板**。

为什么必须有这个
--------------
有序尺度的部分分有个天然性质：**"总答中间那一档"能拿到不低的分数**。
所以如果有人只贴一个 headline `score` 而不报地板，读者会高估难度。
我们把地板明确算出来并公开，让任何人都能判断"某模型 0.7 到底算好还是算差"。

生成三份：
  · oracle       完美作答（分类与判据都照抄真值）→ 应该接近 1.0，用于确认判分器没算错
  · all_vus      永远答 "Uncertain significance"、不给判据 → **退化解地板**
  · all_pathogenic 永远答 "Pathogenic" → 另一个方向的退化参考

用法：
    python3 make_baseline_answers.py --truth truth.jsonl --outdir ../baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="生成 T2 对照作答")
    ap.add_argument("--truth", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args(argv)

    truth = load(Path(args.truth))
    out = Path(args.outdir)
    print(f"读入真值 {len(truth)} 条")

    # 1) oracle：完全照抄真值
    write(out / "answers_oracle.jsonl", [
        {
            "item_id": t["item_id"],
            "classification": t["assertion_normalized"],
            "criteria_met": t.get("criteria_met") or [],
        }
        for t in truth
    ])

    # 2) 退化解：永远 VUS，不给判据
    write(out / "answers_all_vus.jsonl", [
        {"item_id": t["item_id"], "classification": "Uncertain significance", "criteria_met": []}
        for t in truth
    ])

    # 3) 另一个方向的退化解
    write(out / "answers_all_pathogenic.jsonl", [
        {"item_id": t["item_id"], "classification": "Pathogenic", "criteria_met": []}
        for t in truth
    ])

    print(f"已写出到 {out}：answers_oracle.jsonl / answers_all_vus.jsonl / answers_all_pathogenic.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
