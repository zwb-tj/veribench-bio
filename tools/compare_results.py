#!/usr/bin/env python3
"""比对两次评测结果，判断是否等价。

为什么需要它
-----------
"我这边跑出来一样"不能靠肉眼比。这个脚本把两次结果的关键字段逐项比对，
并**区分"必须完全一致"的字段**与"本来就会波动"的字段：

  必须一致（不一致 = 复现失败）：
    status、score、per_type 的 tp/fp/fn/precision/sensitivity/f1、检出变异数
  允许波动（环境相关，不是错）：
    wall_clock_sec、grade_sec、peak_rss_mb

用法：
    python compare_results.py run_a.json run_b.json
    python compare_results.py run_a.json run_b.json --label-a 基线 --label-b 第三方复现

退出码：0 = 关键字段一致；1 = 有不一致；2 = 用法/文件错误。

注意：用这个脚本而不是 PowerShell 的 ConvertFrom-Json ——
后者默认按 ANSI 读 UTF-8 文件，遇到中文字段会解析失败。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: 必须逐位一致的字段（复现性的判据）
CRITICAL_TOP = ("status", "score", "metric")
CRITICAL_PER_TYPE = ("tp_baseline", "tp_call", "fp", "fn", "precision", "sensitivity", "f1")
#: 允许波动的字段（计时/内存随机器与调度变化，不构成复现失败）
VOLATILE = ("wall_clock_sec", "grade_sec", "peak_rss_mb")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(v: object) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="比对两次评测结果")
    ap.add_argument("a", help="结果 A（通常是基线）")
    ap.add_argument("b", help="结果 B（通常是复现）")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--tolerance", type=float, default=0.0,
                    help="数值容差，默认 0（要求逐位一致）")
    args = ap.parse_args(argv)

    pa, pb = Path(args.a), Path(args.b)
    for p in (pa, pb):
        if not p.is_file():
            print(f"[错误] 文件不存在：{p}", file=sys.stderr)
            return 2

    a, b = load(pa), load(pb)
    mismatches: list[str] = []
    rows: list[tuple[str, str, str, bool, bool]] = []  # 名称, A, B, 一致?, 是否关键

    for key in CRITICAL_TOP:
        va, vb = a.get(key), b.get(key)
        same = fmt(va) == fmt(vb)
        rows.append((key, fmt(va), fmt(vb), same, True))
        if not same:
            mismatches.append(f"{key}: {fmt(va)} vs {fmt(vb)}")

    for vtype in sorted(set(a.get("per_type", {})) | set(b.get("per_type", {}))):
        sa = a.get("per_type", {}).get(vtype) or {}
        sb = b.get("per_type", {}).get(vtype) or {}
        for key in CRITICAL_PER_TYPE:
            va, vb = sa.get(key), sb.get(key)
            same = fmt(va) == fmt(vb)
            rows.append((f"{vtype}.{key}", fmt(va), fmt(vb), same, True))
            if not same:
                mismatches.append(f"{vtype}.{key}: {fmt(va)} vs {fmt(vb)}")

    for key in VOLATILE:
        va, vb = a.get(key), b.get(key)
        rows.append((key, fmt(va), fmt(vb), fmt(va) == fmt(vb), False))

    width = max(len(r[0]) for r in rows) + 2
    print(f"{'字段':<{width}} {args.label_a:>14} {args.label_b:>14}   一致")
    print("-" * (width + 36))
    for name, va, vb, same, critical in rows:
        mark = "✅" if same else ("❌" if critical else "～")
        suffix = "" if critical else "  (允许波动)"
        print(f"{name:<{width}} {va:>14} {vb:>14}   {mark}{suffix}")

    print()
    if mismatches:
        print(f"❌ 关键字段不一致（{len(mismatches)} 项）—— 这不是环境波动，是复现失败：")
        for m in mismatches:
            print(f"   - {m}")
        return 1

    print("✅ 关键字段完全一致（status / score / 逐类型 TP·FP·FN 与 P·R·F1 逐位相同）。")
    print("   计时与内存有差异属正常（调度与缓存导致），不构成复现失败。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
