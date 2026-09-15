#!/usr/bin/env python3
"""把多个判分结果并排显示，用于标定评分尺度的天花板/地板。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

COLS = [
    ("score", "主分"),
    ("classification_credit", "分类部分分"),
    ("exact_accuracy", "精确命中"),
    ("criteria_f1", "判据F1"),
    ("directional_error_rate", "方向性错误"),
    ("canary_consistency", "金丝雀一致"),
]

rows = []
_ap = argparse.ArgumentParser(
    description="把多个判分结果并排显示，用于标定评分尺度的天花板/地板",
    epilog="例：python3 show_baselines.py baseline/result_oracle.json")
_ap.add_argument("results", nargs="*",
                 help="判分结果 JSON（默认读同目录 baseline/ 下的全部）")
_args = _ap.parse_args()

for f in _args.results:
    p = Path(f)
    d = json.loads(p.read_text(encoding="utf-8"))
    rows.append((p.stem.replace("result_", ""), d))

w = max(len(n) for n, _ in rows) + 2
header = f"{'基线':<{w}}" + "".join(f"{label:>14}" for _, label in COLS)
print(header)
print("-" * len(header))
for name, d in rows:
    line = f"{name:<{w}}"
    for key, _ in COLS:
        v = d.get(key)
        line += f"{'n/a':>14}" if v is None else f"{v:>14.4f}"
    print(line)

print()
print("说明：主分 = 0.6×分类部分分 + 0.4×判据F1。")
print("      「分类部分分」在有序尺度上给部分分，因此**永远答中间那一档（VUS）会拿到不低的分**")
print("      —— 这就是为什么必须同时报「精确命中」与「判据F1」，也是为什么地板必须公开。")
