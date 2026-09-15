#!/usr/bin/env python3
"""三档 0/1/2 真的比二档更可靠吗？——用现有数据做**免费的**量表比较。

动机
----
`boundary_analysis.py` 测出：v1.1 的评判分歧有 55.6% 落在 1↔2、**44.4% 落在 0↔1**。
后一半不是"后果分句"造成的，改题面救不了——它是"回答质量连续、档位离散"的固有困难。

既然中间那档最难切，一个自然的疑问是：**三档是不是比二档更不可靠？**
如果不是，"把量表改粗"就不是解法；如果是，那更粗的量表反而是更诚实的选择。

关键在于：**这个问题不需要新数据**。同一个裁判对同一份回答给的 0/1/2，
可以事后合并成二档，然后重算一致性。三种编码各算一遍：

  · 三档（原始）          0 / 1 / 2
  · 二档 A「有没有谈到」   0 → 0；1,2 → 1
  · 二档 B「有没有做全」   0,1 → 0；2 → 1

注意这是**同一个裁判的重测一致性**，不是与人金标准的一致性。
合并档位一定会提高表面一致率（分歧被折进同一档），所以必须同时看 κ——
κ 扣掉了"碰巧一致"的部分，只有 κ 上升才说明**真的**更可靠，而不只是更粗。

用法：
    python3 scale_reliability.py --out ../fixtures/answers/scale_reliability.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def quad_kappa(pairs: list[tuple[int, int]], k: int) -> tuple[float, float, float]:
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    num = sum(((a - b) ** 2) / (k ** 2) for a, b in pairs)
    po = 1 - num / n
    ma: dict[int, int] = {}
    mb: dict[int, int] = {}
    for a, b in pairs:
        ma[a] = ma.get(a, 0) + 1
        mb[b] = mb.get(b, 0) + 1
    pe = sum((ma.get(c, 0) / n) * (mb.get(c, 0) / n) for c in set(ma) | set(mb))
    if abs(1 - pe) < 1e-12:
        return float("nan"), po, pe
    return (po - pe) / (1 - pe), po, pe


def load_pairs(mapping_path: Path, run1: Path, run2: Path) -> list[tuple[int, int]]:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    pairs = []
    for m in mapping:
        f1, f2 = run1 / f"{m['blind_id']}.json", run2 / f"{m['blind_id']}.json"
        if not (f1.is_file() and f2.is_file()):
            continue
        s1 = {s["criterion_id"]: s["score"] for s in json.loads(f1.read_text(encoding="utf-8"))["scores"]}
        s2 = {s["criterion_id"]: s["score"] for s in json.loads(f2.read_text(encoding="utf-8"))["scores"]}
        for cid in sorted(set(s1) & set(s2)):
            pairs.append((s1[cid], s2[cid]))
    return pairs


def report(tag: str, pairs: list[tuple[int, int]]) -> dict:
    n = len(pairs)
    if n == 0:
        # ⚠️ 原来这里直接往下走，`exact / n` 触发 ZeroDivisionError —— 清室检验抓到的。
        #    成因：`judge_blind/_mapping.json` 会随仓库发布（小），但 `judge_out*/`
        #    **刻意不发布**（那是我们的判分产出）。于是映射在、打分不在 → n=0。
        #    这是"没跑"，不是"跑错了"。
        print(f"\n{tag}: SKIP: 没有任何可配对的评判结果"
              f"（judge_blind 映射在，但 judge_out*/ 未随仓库发布；需先跑裁判）")
        return {"n": 0, "skipped": True}
    exact = sum(1 for a, b in pairs if a == b)
    k3, po3, pe3 = quad_kappa(pairs, 2)            # 三档，二次加权
    # 二档 A：0 → 0；1,2 → 1
    pa = [(0 if a == 0 else 1, 0 if b == 0 else 1) for a, b in pairs]
    ka, poa, pea = quad_kappa(pa, 1)
    # 二档 B：0,1 → 0；2 → 1
    pb = [(1 if a == 2 else 0, 1 if b == 2 else 0) for a, b in pairs]
    kb, pob, peb = quad_kappa(pb, 1)
    ea = sum(1 for a, b in pa if a == b) / n
    eb = sum(1 for a, b in pb if a == b) / n
    print(f"\n{tag}（{n} 个单元）")
    print(f"  {'编码':<22}{'完全一致':>10}{'κ':>10}")
    print(f"  {'三档 0/1/2（二次加权）':<20}{exact / n * 100:>9.1f}%{k3:>10.4f}")
    print(f"  {'二档A 有没有谈到':<22}{ea * 100:>9.1f}%{ka:>10.4f}")
    print(f"  {'二档B 有没有做全':<22}{eb * 100:>9.1f}%{kb:>10.4f}")
    return {
        "n": n,
        "three_level": {"exact": round(exact / n, 4), "kappa": round(k3, 4)},
        "binary_engaged": {"exact": round(ea, 4), "kappa": round(ka, 4)},
        "binary_complete": {"exact": round(eb, 4), "kappa": round(kb, 4)},
    }


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="量表粒度比较")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    out: dict[str, dict] = {}
    specs = [
        ("v1.0", ROOT / "fixtures" / "answers" / "judge_blind" / "_mapping.json",
         ROOT / "fixtures" / "answers" / "judge_out",
         ROOT / "fixtures" / "answers" / "judge_out_run2"),
        ("v1.1", ROOT / "fixtures" / "answers" / "v1.1" / "judge_blind" / "_mapping.json",
         ROOT / "fixtures" / "answers" / "v1.1" / "judge_out_run1",
         ROOT / "fixtures" / "answers" / "v1.1" / "judge_out_run2"),
    ]
    for tag, mp, r1, r2 in specs:
        if not mp.is_file():
            print(f"{tag}: 缺数据，跳过")
            continue
        out[tag] = report(tag, load_pairs(mp, r1, r2))

    print("\n" + "=" * 62)
    print("怎么读这张表")
    print("  合并档位**一定**会抬高表面一致率（分歧被折进同一档），")
    print("  所以只有 **κ 上升**才说明真的更可靠，而不只是更粗。")
    for tag in out:
        r = out[tag]
        if r.get("skipped"):
            print(f"  {tag}: SKIP（无评判结果）")
            continue
        k3 = r["three_level"]["kappa"]
        best = max((("二档A 有没有谈到", r["binary_engaged"]["kappa"]),
                    ("二档B 有没有做全", r["binary_complete"]["kappa"])), key=lambda x: x[1])
        delta = best[1] - k3
        verdict = ("二档更可靠（κ 上升）" if delta > 0.01 else
                   "三档更好或持平（κ 未上升）" if delta < -0.01 else "两者接近")
        print(f"  {tag}: 三档 κ={k3:.4f} vs 最佳二档 {best[0]} κ={best[1]:.4f} "
              f"→ Δ{delta:+.4f}　**{verdict}**")

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 → {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
