#!/usr/bin/env python3
"""生成"只看题面、看不到评分标准"的视图，供撰写答案用。

为什么必须去掉 criteria
----------------------
要给裁判做**区分度检验**（好答案得分 > 差答案得分），写答案的人就
**不能看到 rubric**。否则答案是照着得分点凑的，裁判当然能打对分——
那测的是"裁判会不会照着标准打分"，而不是"这个标准能否区分真实的好坏答案"。

这个区分很重要：
  · 看得到 criteria → 测的是裁判的**执行**能力
  · 看不到 criteria → 测的是 rubric 的**构念效度**（criteria 是否抓住了
    专家真正在意的东西）

我们要的是后者。

用法：
    python3 make_blind_items.py --items ../items/items.jsonl --out ../items/items_blind.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="去掉 criteria 的盲态题面")
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    rows = [json.loads(l) for l in Path(args.items).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for r in rows:
        # 只保留题面本身。criteria 里含 criterion_id 与锚点，一律不出现。
        dropped = [k for k in r if k not in ("item_id", "question", "context")]
        out.append({"item_id": r["item_id"], "question": r["question"],
                    "context": r.get("context") or ""})
        if dropped:
            pass

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8", newline="")

    blob = op.read_text(encoding="utf-8")
    leaked = [k for k in ("criteria", "criterion_id", "anchors", "provenance", "source_ref") if k in blob]
    print(f"盲态题面：{len(out)} 题 → {op}")
    print(f"  泄漏检查（不应出现 criteria/anchors/source_ref 等）：{leaked or '无'}")
    if leaked:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
