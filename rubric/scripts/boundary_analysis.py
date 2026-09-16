#!/usr/bin/env python3
"""不稳定性到底住在哪一档边界？——把"该改题面还是该改锚点"从判断题变成测量题。

问题
----
v1.1 改完之后仍有 16 条确认缺陷，新增 5 条。两轮裁判的**独立**反馈高度一致地说：
不稳定集中在"回答点出了缺陷、但没写出它的后果"这一情形。
但那只是**主观描述**。它可以被证伪：如果属实，那么两次评判的分歧应当
**几乎全部落在 1↔2 边界上**，而 0↔1 边界应当很稳。

于是本脚本回答三个可直接测量的问题：
  Q1 两次评判的分歧，按"跨了几档"分布如何？（0↔1 / 1↔2 / 0↔2）
  Q2 分歧是否集中在 1↔2？
  Q3 这一模式在 v1.0 与 v1.1 之间有没有变化？

为什么这决定了下一步怎么改
--------------------------
  · 若分歧**几乎全在 1↔2** → 问题在"中间档"的划分。这时两种修法都可行：
      (a) 改题面，要求回答说明后果（制造出该维度的方差）
      (b) 改锚点，承认"点名即满分"（取消该维度）
    选哪个**取决于答案在该维度上有没有方差** —— 见 `--answers` 可选的进一步分析。
  · 若分歧**大量落在 0↔1** → 问题在"完全没提到"与"提到了但很浅"的划分，
    那属于"回答质量连续、档位离散"的固有困难，改题面也救不了。

用法：
    python3 boundary_analysis.py --out ../fixtures/answers/boundary_analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def analyse(name: str, mapping_path: Path, run1: Path, run2: Path) -> dict:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    pairs: list[dict] = []
    for m in mapping:
        f1, f2 = run1 / f"{m['blind_id']}.json", run2 / f"{m['blind_id']}.json"
        if not (f1.is_file() and f2.is_file()):
            continue
        s1 = {s["criterion_id"]: s["score"] for s in json.loads(f1.read_text(encoding="utf-8"))["scores"]}
        s2 = {s["criterion_id"]: s["score"] for s in json.loads(f2.read_text(encoding="utf-8"))["scores"]}
        for cid in sorted(set(s1) & set(s2)):
            a, b = s1[cid], s2[cid]
            pairs.append({
                "item_id": m["item_id"], "level": m["level"], "criterion_id": cid,
                "run1": a, "run2": b, "gap": abs(a - b),
            })
    n = len(pairs)
    gaps = Counter(p["gap"] for p in pairs)
    # 按涉及的最低档归类：0↔1 还是 1↔2
    lo_mid = [p for p in pairs if p["gap"] == 1 and min(p["run1"], p["run2"]) == 0]
    mid_hi = [p for p in pairs if p["gap"] == 1 and min(p["run1"], p["run2"]) == 1]
    big = [p for p in pairs if p["gap"] == 2]
    return {
        "name": name,
        "n_units": n,
        "exact": gaps[0],
        "exact_rate": round(gaps[0] / n, 4) if n else None,
        "gap1_0_to_1": len(lo_mid),
        "gap1_1_to_2": len(mid_hi),
        "gap2_0_to_2": len(big),
        "mid_hi_share_of_disagreements": round(len(mid_hi) / (n - gaps[0]), 4) if n - gaps[0] else None,
        "details_mid_hi": mid_hi,
        "details_0_to_1": lo_mid,
        "details_gap2": big,
    }


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="档位边界分歧分析")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    runs = [
        ("v1.0", ROOT / "fixtures" / "answers" / "judge_blind" / "_mapping.json",
         ROOT / "fixtures" / "answers" / "judge_out",
         ROOT / "fixtures" / "answers" / "judge_out_run2"),
        ("v1.1", ROOT / "fixtures" / "answers" / "v1.1" / "judge_blind" / "_mapping.json",
         ROOT / "fixtures" / "answers" / "v1.1" / "judge_out_run1",
         ROOT / "fixtures" / "answers" / "v1.1" / "judge_out_run2"),
    ]

    out = {}
    print(f"{'版本':<8}{'单元':>6}{'完全一致':>10}{'0↔1':>7}{'1↔2':>7}{'0↔2':>7}{'1↔2 占分歧':>12}")
    print("-" * 62)
    for name, mp, r1, r2 in runs:
        if not mp.is_file() or not r1.is_dir() or not r2.is_dir():
            print(f"{name:<8}  缺数据，跳过")
            continue
        res = analyse(name, mp, r1, r2)
        out[name] = res
        share = res["mid_hi_share_of_disagreements"]
        print(f"{name:<8}{res['n_units']:>6}{res['exact']:>10}{res['gap1_0_to_1']:>7}"
              f"{res['gap1_1_to_2']:>7}{res['gap2_0_to_2']:>7}"
              f"{(f'{share * 100:.1f}%' if share is not None else '—'):>12}")

    if len(out) == 2:
        a, b = out["v1.0"], out["v1.1"]
        print()
        print("Q1/Q2 结论：")
        for k in ("v1.0", "v1.1"):
            r = out[k]
            tot = r["gap1_0_to_1"] + r["gap1_1_to_2"] + r["gap2_0_to_2"]
            if tot:
                print(f"  {k}: 分歧 {tot} 处 → 0↔1 有 {r['gap1_0_to_1']}，"
                      f"1↔2 有 {r['gap1_1_to_2']}，跨两档 {r['gap2_0_to_2']}")
        print()
        mh = out["v1.1"]["mid_hi_share_of_disagreements"]
        if mh is not None:
            if mh >= 0.7:
                print(f"  ✅ 假设成立：v1.1 的分歧有 {mh * 100:.1f}% 落在 **1↔2 边界**，")
                print("     0↔1 边界相对稳定 → 问题确实在'中间档怎么切'，")
                print("     而不是'完全没提到 vs 提到了一点'。")
            elif mh <= 0.4:
                print(f"  ❌ 假设不成立：v1.1 只有 {mh * 100:.1f}% 分歧在 1↔2，"
                      f"0↔1 有 {out['v1.1']['gap1_0_to_1']} 处。")
                print("     问题更多在'完全没提到 vs 提到了一点'，改题面救不了。")
            else:
                print(f"  ⚠️ 假设只部分成立：1↔2 占 {mh * 100:.1f}%，"
                      f"0↔1 也占 {out['v1.1']['gap1_0_to_1'] / (out['v1.1']['gap1_0_to_1'] + out['v1.1']['gap1_1_to_2'] + out['v1.1']['gap2_0_to_2']) * 100:.1f}%。")
                print("     两类边界都要处理。")
        print()
        print(f"Q3 v1.1 相对 v1.0：完全一致率 "
              f"{a['exact_rate'] * 100:.1f}% → {b['exact_rate'] * 100:.1f}%；"
              f"1↔2 分歧 {a['gap1_1_to_2']} → {b['gap1_1_to_2']}；"
              f"0↔1 分歧 {a['gap1_0_to_1']} → {b['gap1_0_to_1']}")

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8", newline="")
    print(f"\n明细 → {op}")

    if "v1.1" in out:
        print("\n仍会漂移的 1↔2 单元（按题目汇总）：")
        c = Counter(p["item_id"] for p in out["v1.1"]["details_mid_hi"])
        for iid, k in c.most_common():
            print(f"   {iid}: {k} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
