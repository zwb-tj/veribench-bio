#!/usr/bin/env python3
"""合并多个批次写出的 rubric 题，并做**跨批次一致性检查**。

为什么需要
---------
题目是分批并行写的，所以必须检查批次之间不会打架：
  · `item_id` 重复（两个批次撞了同一个编号）
  · 编号超出该批次被分配的区间（说明它没按契约来）
  · 缺字段 / 结构不合规

**任何一项不合格都不许静默合并** —— 否则会带着脏数据一路走到标注现场。

用法：
    python3 merge_batches.py --indir ../items --out ../items/items_merged.jsonl \
        --expect "batch_1:R-0001,R-0006" "batch_2:R-0007,R-0012"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_TOP = ("item_id", "question", "criteria", "provenance")
ID_RE = re.compile(r"^R-(\d{4})$")


def load(path: Path) -> list[dict]:
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


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="合并 rubric 题批次")
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--glob", default="batch_*.jsonl")
    ap.add_argument("--expect", nargs="*", default=[],
                    help="形如 batch_1:R-0001,R-0006 的编号区间契约")
    args = ap.parse_args(argv)

    indir = Path(args.indir)
    files = sorted(indir.glob(args.glob))
    if not files:
        print(f"[错误] {indir} 下没有匹配 {args.glob} 的文件", file=sys.stderr)
        return 2

    ranges: dict[str, tuple[int, int]] = {}
    for e in args.expect:
        name, rng = e.split(":", 1)
        lo, hi = rng.split(",")
        ranges[name.removesuffix(".jsonl")] = (int(lo[2:]), int(hi[2:]))

    problems: list[str] = []
    warnings: list[str] = []
    merged: list[dict] = []
    seen: dict[str, str] = {}   # item_id → 来源文件
    per_file: dict[str, int] = {}

    for f in files:
        rows = load(f)
        per_file[f.name] = len(rows)
        print(f"{f.name}: {len(rows)} 题")
        for r in rows:
            iid = r.get("item_id", "")
            m = ID_RE.match(iid)
            if not m:
                problems.append(f"{f.name}: item_id 格式不合规 {iid!r}（应为 R-0000）")
                continue
            n = int(m.group(1))
            if iid in seen:
                problems.append(f"item_id 冲突：{iid} 同时出现在 {seen[iid]} 与 {f.name}")
                continue
            seen[iid] = f.name
            if f.stem in ranges:
                lo, hi = ranges[f.stem]
                if not (lo <= n <= hi):
                    problems.append(f"{f.name}: {iid} 超出分配区间 R-{lo:04d}..R-{hi:04d}")
            for k in REQUIRED_TOP:
                if k not in r:
                    problems.append(f"{iid}: 缺字段 {k}")
            crits = r.get("criteria") or []
            if not (3 <= len(crits) <= 5):
                problems.append(f"{iid}: rubric 条数 {len(crits)}，要求 3–5")
            for c in crits:
                a = c.get("anchors") or {}
                for lvl in ("0", "1", "2"):
                    if not (a.get(lvl) or "").strip():
                        problems.append(f"{iid}/{c.get('criterion_id')}: 缺 {lvl} 锚点")
            merged.append(r)

    merged.sort(key=lambda r: r["item_id"])
    out = Path(args.out)
    with out.open("w", encoding="utf-8", newline="") as fh:
        for r in merged:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n合并 {len(files)} 个文件 → {len(merged)} 题")
    ids = [r["item_id"] for r in merged]
    print(f"题号范围：{ids[0] if ids else '—'} .. {ids[-1] if ids else '—'}")
    # 号段空洞不是错误，但值得知道（说明某些批次少写了）
    nums = sorted(int(ID_RE.match(i).group(1)) for i in ids)
    if nums:
        gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in set(nums)]
        if gaps:
            warnings.append(f"题号有空洞（{len(gaps)} 个）：{[f'R-{g:04d}' for g in gaps[:10]]}"
                            f"{' …' if len(gaps) > 10 else ''} —— 说明某些批次少写了题")

    if warnings:
        for w in warnings:
            print(f"  ⚠️ {w}")
    if problems:
        print(f"\n❌ {len(problems)} 个问题（**不静默合并**）：")
        for p in problems[:20]:
            print(f"   {p}")
        return 1
    print(f"\n✅ 合并完成，无冲突 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
