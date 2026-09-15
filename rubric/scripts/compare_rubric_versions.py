#!/usr/bin/env python3
"""v1.0 与 v1.1 two-version rubric 的对照：改写到底有没有让标准更能区分好坏答案？

为什么这个对照是干净的
----------------------
**同一批 72 份答案**（它们是在**看不到 v1.0 评分标准**的条件下写的，
同样看不到 v1.1），**同一批题目**，唯一变化的是 criteria 的锚点结构。

所以区分度指标的任何变化，都能归因到**改写本身**，而不是答案或题目变了。
这是一个受控的前后对照，不是"改完感觉好点了"。

公平性要求：两版都必须用**两轮**评判，因为单轮会把"标准坏"和"这次手抖"混在一起。
（v1.0 已跑两轮；v1.1 也必须跑两轮，否则比较不公平。）

用法：
    python3 compare_rubric_versions.py \
        --v10-disc ../fixtures/answers/discrimination.json \
        --v10-retest ../fixtures/answers/retest.json \
        --v11-disc ../fixtures/answers/v1.1/discrimination.json \
        --v11-retest ../fixtures/answers/v1.1/retest.json \
        --out ../docs/V1.0_VS_V1.1.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(p: str | None) -> dict | None:
    if not p:
        return None
    f = Path(p)
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def defect_counts(retest: dict) -> tuple[int, int, int]:
    """返回 (复现的真缺陷数, 饱和数, 反向数)"""
    real = [d for d in retest["criteria_detail"] if d["reproduced"]]
    sat = [d for d in real if "saturated" in (d["verdict_run1"], d["verdict_run2"])]
    return len(real), len(sat), len(real) - len(sat)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="v1.0 vs v1.1 对照")
    ap.add_argument("--v10-disc", required=True)
    ap.add_argument("--v10-retest", required=True)
    ap.add_argument("--v11-disc", required=True)
    ap.add_argument("--v11-retest", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    d10, r10 = load(args.v10_disc), load(args.v10_retest)
    d11, r11 = load(args.v11_disc), load(args.v11_retest)
    if not all((d10, r10)):
        print("❌ v1.0 结果不齐（需要 discrimination.json 与 retest.json）")
        return 1
    if not all((d11, r11)):
        print("❌ v1.1 结果还不齐——改写后必须重跑两轮评判才能比较")
        return 1

    n10, sat10, inv10 = defect_counts(r10)
    n11, sat11, inv11 = defect_counts(r11)

    rows = [
        ("标准总数", d10["n_criteria_total"], d11["n_criteria_total"]),
        ("严格单调的题", f"{d10['strict_monotonic_rate'] * 100:.1f}%",
         f"{d11['strict_monotonic_rate'] * 100:.1f}%"),
        ("至少 优>浅", f"{d10['weak_lt_strong_rate'] * 100:.1f}%",
         f"{d11['weak_lt_strong_rate'] * 100:.1f}%"),
        ("归一化 浅", f"{d10['overall_normalized']['weak']:.3f}",
         f"{d11['overall_normalized']['weak']:.3f}"),
        ("归一化 中", f"{d10['overall_normalized']['medium']:.3f}",
         f"{d11['overall_normalized']['medium']:.3f}"),
        ("归一化 优", f"{d10['overall_normalized']['strong']:.3f}",
         f"{d11['overall_normalized']['strong']:.3f}"),
        ("优−浅 差距", f"{d10['gap_strong_minus_weak']:.3f}",
         f"{d11['gap_strong_minus_weak']:.3f}"),
        ("**确认缺陷标准数**", n10, n11),
        ("　其中饱和", sat10, sat11),
        ("　其中反向", inv10, inv11),
        ("裁判重测 κ", r10["quadratic_weighted_kappa"], r11["quadratic_weighted_kappa"]),
        ("两次完全一致", f"{r10['exact_agreement'] * 100:.1f}%",
         f"{r11['exact_agreement'] * 100:.1f}%"),
    ]

    L: list[str] = []
    A = L.append
    A("# rubric v1.0 → v1.1 前后对照")
    A("")
    A("> 由 `rubric/scripts/compare_rubric_versions.py` 生成。**同一批 72 份答案**（写答案时看不到任何一版的")
    A("> 评分标准）、同一批题目，唯一变量是 criteria 的锚点结构 → 差异可归因到改写本身。")
    A("")
    A("| 指标 | v1.0 | v1.1 | 变化 |")
    A("|---|---|---|---|")
    for name, a, b in rows:
        try:
            fa, fb = float(str(a).rstrip("%")), float(str(b).rstrip("%"))
            delta = fb - fa
            arrow = "→" if abs(delta) < 1e-9 else ("↑" if delta > 0 else "↓")
            dv = f"{delta:+.3f} {arrow}"
        except ValueError:
            dv = "—"
        A(f"| {name} | {a} | {b} | {dv} |")
    A("")

    improved = n10 - n11
    if improved > 0:
        A(f"**确认缺陷标准从 {n10} 条降到 {n11} 条（少 {improved} 条）。**")
    elif improved == 0:
        A(f"**确认缺陷标准数没变（{n10} → {n11}）。改写没有减少结构性缺陷。**")
    else:
        A(f"⚠️ **确认缺陷标准反而增加了（{n10} → {n11}）。改写引入了新问题。**")
    A("")

    # 哪些修好了、哪些还在
    real10 = {f"{d['item_id']}/{d['criterion_id']}" for d in r10["criteria_detail"] if d["reproduced"]}
    real11 = {f"{d['item_id']}/{d['criterion_id']}" for d in r11["criteria_detail"] if d["reproduced"]}
    fixed = sorted(real10 - real11)
    still = sorted(real10 & real11)
    new = sorted(real11 - real10)

    A(f"## 修好了（{len(fixed)} 条）")
    A("")
    A("　" + ("、".join(fixed) if fixed else "（无）"))
    A("")
    A(f"## 仍然有缺陷（{len(still)} 条）—— 改写未生效，需要人工重写")
    A("")
    A("　" + ("、".join(still) if still else "（无）"))
    A("")
    A(f"## 新出现的缺陷（{len(new)} 条）—— 改写引入了新问题，必须复查")
    A("")
    A("　" + ("、".join(new) if new else "（无）"))
    A("")
    A("## 局限")
    A("")
    for x in r11.get("limitations", []):
        A(f"- {x}")
    A("- 两版的裁判都来自同一模型家族，改写后的标准可能对**该家族的措辞习惯**更友好，")
    A("  这会让 v1.1 看起来比实际更好。真正中立的检验仍需人类标注。")
    A("")

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text("\n".join(L), encoding="utf-8")
    print(f"确认缺陷：v1.0 {n10} 条 → v1.1 {n11} 条")
    print(f"  修好 {len(fixed)} · 仍在 {len(still)} · 新增 {len(new)}")
    print(f"→ {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
