#!/usr/bin/env python3
"""裁判的**重测信度**：同一批输入、同一协议，跑两次，两次一致吗？

为什么这一步不能省
------------------
第一轮跑完发现 101 条标准里 11 条"饱和"（三档同分）、13 条"反向"（浅档不低于优档）。
但每个 (题, 档) 只有 **1 次**裁判判定。单次判定的波动与真实的标准缺陷，
在没有重复测量的情况下**无法区分**——尤其那些"浅1 中0 优1"式的中间塌陷，
更像噪声而不是系统性反向。

所以做第二次独立评判（另起一批裁判，不看第一轮结果），然后：

  · 两次**完全一致**的条目 → 该标准是**稳定的** → 若饱和/反向，是**真缺陷**
  · 两次**不一致**的条目 → 该标准**本身难以判定** → 是 rubric 的措辞问题，
    也可能只是抽样噪声

这个量本身就是**裁判的重测信度**，是可报告的指标：它给出"同一裁判重复评同一
东西能有多稳"的上界。它也是人类天花板讨论的前提——连自己都测不稳的裁判，
谈不上跟人类一致。

用法：
    python3 judge_retest.py --mapping ../fixtures/answers/judge_blind/_mapping.json \
        --run1 ../fixtures/answers/judge_out --run2 ../fixtures/answers/judge_out_run2 \
        --out ../fixtures/answers/retest.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

LEVELS = ["weak", "medium", "strong"]


def load_run(d: Path, mapping: list[dict]) -> dict[str, dict[str, int]]:
    """返回 {blind_id: {criterion_id: score}}"""
    out: dict[str, dict[str, int]] = {}
    for m in mapping:
        p = d / f"{m['blind_id']}.json"
        if not p.is_file():
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        out[m["blind_id"]] = {s["criterion_id"]: s["score"] for s in j.get("scores", [])}
    return out


def quad_kappa(pairs: list[tuple[int, int]], k: int = 2) -> tuple[float, float, float]:
    """二次加权 Cohen's κ，返回 (κ, Po, Pe)。

    ⚠️ 这里不用 kappa.py 是因为输入形态不同（那边是标注者×标准的 JSONL）。
    公式与 kappa.py 保持一致，且 kappa.py 的 --self-test 已验证过那套实现。
    """
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    cats = list(range(k + 1))
    # 观察一致度（二次加权）
    num = sum(((a - b) ** 2) / (k ** 2) for a, b in pairs)
    po = 1 - num / n
    # 期望一致度
    ma = {c: 0 for c in cats}
    mb = {c: 0 for c in cats}
    for a, b in pairs:
        ma[a] += 1
        mb[b] += 1
    pe = sum((ma[c] / n) * (mb[c] / n) for c in cats)
    if pe == 1.0:
        return float("nan"), po, pe  # 无方差，κ 无定义
    return (po - pe) / (1 - pe), po, pe


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="裁判重测信度")
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--run1", required=True)
    ap.add_argument("--run2", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    r1 = load_run(Path(args.run1), mapping)
    r2 = load_run(Path(args.run2), mapping)

    common = sorted(set(r1) & set(r2))
    print(f"重测比对：run1 {len(r1)} 份，run2 {len(r2)} 份，共同 {len(common)} 份")
    if len(common) < len(mapping):
        miss = len(mapping) - len(common)
        print(f"❌ 有 {miss} 份两边不齐，无法比对")
        return 1

    pairs: list[tuple[int, int]] = []
    exact = adjacent = 0
    diffs: list[int] = []
    per_item: dict[str, list[tuple[int, int]]] = {}
    per_crit: dict[tuple[str, str], tuple[int, int]] = {}

    for m in mapping:
        bid, iid = m["blind_id"], m["item_id"]
        a_all, b_all = r1[bid], r2[bid]
        if set(a_all) != set(b_all):
            print(f"❌ {bid} ({iid}/{m['level']}): 两次的标准编号不一致 "
                  f"{sorted(a_all)} vs {sorted(b_all)}")
            return 1
        for cid in sorted(a_all):
            a, b = a_all[cid], b_all[cid]
            pairs.append((a, b))
            per_item.setdefault(iid, []).append((a, b))
            per_crit[(iid, m["level"], cid)] = (a, b)
            diffs.append(abs(a - b))
            if a == b:
                exact += 1
            if abs(a - b) <= 1:
                adjacent += 1

    n = len(pairs)
    kappa, po, pe = quad_kappa(pairs, k=2)

    print(f"\n{'=' * 74}")
    print(f"重测结果（{n} 个 标准×答案 单元，每单元两次独立判定）")
    print(f"  完全一致        {exact}/{n} = {exact / n * 100:.1f}%")
    print(f"  相差 ≤1 分      {adjacent}/{n} = {adjacent / n * 100:.1f}%")
    print(f"  平均绝对差      {statistics.fmean(diffs):.4f} 分（满分 2）")
    if kappa != kappa:  # NaN
        print(f"  二次加权 κ      **无定义**（Pe={pe:.4f}，两次评分无方差）")
    else:
        print(f"  二次加权 κ      {kappa:.4f}   (Po={po:.4f}, Pe={pe:.4f})")
    if kappa == kappa and kappa < 0.40:
        print("  ⚠️ κ < 0.40：同一裁判重复评同一输入都测不稳，**人类天花板之前先要修 rubric**")

    # ---- 逐条标准：区分"真缺陷"与"噪声" ----
    print(f"\n{'=' * 74}")
    print("饱和 / 反向 标准的复现情况（这才是『该不该改』的依据）")
    unstable = stable_defect = 0
    detail = []
    for iid in sorted(per_item):
        levels = {}
        for lv in LEVELS:
            levels[lv] = {cid: per_crit[(iid, lv, cid)] for (i2, l2, cid) in per_crit
                          if i2 == iid and l2 == lv}
        if not all(levels.values()):
            continue
        for cid in sorted(levels["weak"]):
            a_vals = [levels[lv][cid][0] for lv in LEVELS]   # 第一次
            b_vals = [levels[lv][cid][1] for lv in LEVELS]   # 第二次

            def classify(v: list[int]) -> str:
                if v[0] < v[1] < v[2]:
                    return "healthy"
                if len(set(v)) == 1:
                    return "saturated"
                if v[0] >= v[2]:
                    return "inverted"
                return "weak_signal"
            c1, c2 = classify(a_vals), classify(b_vals)
            if c1 in ("saturated", "inverted") or c2 in ("saturated", "inverted"):
                reproduced = (c1 == c2)
                if reproduced:
                    stable_defect += 1
                else:
                    unstable += 1
                detail.append({"item_id": iid, "criterion_id": cid,
                               "run1": a_vals, "run2": b_vals,
                               "verdict_run1": c1, "verdict_run2": c2,
                               "reproduced": reproduced})
    print(f"  两次都判为缺陷（**真缺陷，应改写**）：{stable_defect} 条")
    print(f"  只有一次判为缺陷（**不稳定，多半是噪声**）：{unstable} 条")
    print()
    for d in detail:
        mark = "🔴真缺陷" if d["reproduced"] else "🟡不稳定"
        print(f"  {mark} {d['item_id']}/{d['criterion_id']}  "
              f"run1 {d['run1']} ({d['verdict_run1']})  run2 {d['run2']} ({d['verdict_run2']})")

    result = {
        "n_units": n,
        "_note": "⚠️ criteria_detail **只含**在任一轮被判为 saturated/inverted 的标准，"
                 "healthy 的条目不在里面（所以它里面『两轮都 healthy』恒为 0，那是构造使然，"
                 "不是结论）。要看全部 101 条的判定请用 discrimination.json 的 criteria 字段。",
        "exact_agreement": round(exact / n, 4),
        "adjacent_agreement": round(adjacent / n, 4),
        "mean_abs_diff": round(statistics.fmean(diffs), 4),
        "quadratic_weighted_kappa": None if kappa != kappa else round(kappa, 4),
        "po": round(po, 4),
        "pe": round(pe, 4),
        "stable_defects": stable_defect,
        "unstable_candidates": unstable,
        "criteria_detail": detail,
        "interpretation": (
            "重测信度是**同一裁判重复评同一输入**的稳定性上界。它不涉及对错，"
            "只回答『这份 rubric 能否被稳定地判读』。κ 低说明标准措辞本身有歧义，"
            "此时讨论『裁判与人类是否一致』为时过早。"),
        "limitations": [
            "两轮都由同一模型家族评判，测的是自一致性，不是跨裁判间一致性",
            "每个单元仍只有 2 次观测，置信区间宽",
            "同一批输入顺序相同，未消除顺序效应",
        ],
    }
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 → {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
