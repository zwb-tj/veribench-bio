#!/usr/bin/env python3
"""操纵检验的结果分析：每条标准对它自己声称要测的维度敏感吗？

判读规则（**先看对照组，再看目标组**）
------------------------------------
  A+ 得分 > A−  → 该标准**敏感**（分得出这个差别）
  A+ 得分 = A−  → 该标准**不敏感**（测不出它声称要测的东西）
  A+ 得分 < A−  → **反向**（加上该要素反而扣分，说明锚点写反了）

关键在于**对照组的通过率**：
  · 若对照组通过率很高、目标组很低 → 检验本身有效，目标组的缺陷是真的
  · 若对照组就大量不通过 → **是这个检验不成立**，不能据此判标准有罪
    （上一轮的教训：先证明检验能区分好坏，再用它定罪）

用法：
    python3 manip_analysis.py --plan ../fixtures/answers/manip_plan.json \
        --inputs ../fixtures/answers/manip_inputs \
        --judge ../fixtures/answers/manip_out_run1 ../fixtures/answers/manip_out_run2 \
        --out ../fixtures/answers/manip_result.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def read_scores(outdir: Path, blind_id: str, cid: str) -> int | None:
    """从盲评输出里取**目标标准**的分数。

    ⚠️ 输出文件名是散列 ID（盲评要求），不是 `R-0007_c3`。
    所以必须先经 _mapping.json 把 (item_id_composite, level) → blind_id 再读。
    第一版直接拿 `{iid}_{cid}_Aplus.json` 去找，会全部读不到而静默变成"缺结果"。
    """
    f = outdir / f"{blind_id}.json"
    if not f.is_file():
        return None
    for s in json.loads(f.read_text(encoding="utf-8"))["scores"]:
        if s["criterion_id"] == cid:
            return s["score"]
    return None


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="操纵检验分析")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--judge", nargs="+", required=True)
    ap.add_argument("--variants", nargs="*", default=[],
                    help="变体文件，用于长度偏差诊断。**不做这一步会有严重混淆**："
                         # ⚠️ argparse 会对 help 文本做 `%` 插值，裸写 `%` 会让 `--help` 直接抛
                         #    `ValueError: unsupported format character`。所以这里必须写 `%%`。
                         #    这个错一直没暴露，是因为 run_all_checks 从来只传真实参数、不跑 --help
                         #    —— 由 scripts/smoke_test_scripts.py 的冒烟测试抓到。
                         "A+ 天然比 A− 长（中位数 +22%%），而裁判有已知的长度偏好，"
                         "所以 A+ > A− 可能只是长度造成的，与标准是否敏感无关。")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    # 盲评映射： (composite_item_id, level) -> blind_id   例 ("R-0007_c3", "plus")
    bmap = json.loads((Path(args.inputs).parent / "manip_blind" / "_mapping.json")
                      .read_text(encoding="utf-8")) \
        if (Path(args.inputs).parent / "manip_blind" / "_mapping.json").is_file() else []
    bid = {(m["item_id"], m["level"]): m["blind_id"] for m in bmap}
    runs = [Path(d) for d in args.judge]

    rows = []
    # 长度偏差诊断用：A+ 与 A− 的字数差
    lenmap: dict[tuple[str, str], int] = {}
    for vp in args.variants:
        vf = Path(vp)
        if not vf.is_file():
            continue
        for l in vf.read_text(encoding="utf-8").splitlines():
            if l.strip():
                v = json.loads(l)
                lenmap[(v["item_id"], v["criterion_id"])] = len(v["A_plus"]) - len(v["A_minus"])

    for spec in plan:
        iid, cid = spec["item_id"], spec["criterion_id"]
        key = f"{iid}_{cid}"
        pb, mb = bid.get((key, "plus")), bid.get((key, "minus"))
        if not pb or not mb:
            print(f"⚠️ {key}: 盲评映射里找不到 plus/minus，跳过")
            continue
        per_run = []
        for rd in runs:
            p, m = read_scores(rd, pb, cid), read_scores(rd, mb, cid)
            if p is not None and m is not None:
                per_run.append((p, m))
        if not per_run:
            print(f"⚠️ {iid}/{cid}: 缺评判结果，跳过")
            continue
        # 两轮都要求同向才算"稳定敏感"；单轮同向只算"倾向"
        verdicts = []
        for p, m in per_run:
            verdicts.append("sensitive" if p > m else ("insensitive" if p == m else "reverse"))
        if all(v == "sensitive" for v in verdicts):
            verdict = "sensitive"
        elif all(v == "insensitive" for v in verdicts):
            verdict = "insensitive"
        elif all(v == "reverse" for v in verdicts):
            verdict = "reverse"
        else:
            verdict = "unstable"
        rows.append({"item_id": iid, "criterion_id": cid, "group": spec["group"],
                     "class": spec.get("class"), "pairs": per_run,
                     "verdict_runs": verdicts, "verdict": verdict,
                     "len_gap": lenmap.get((iid, cid)),
                     "criterion_text": spec.get("criterion_text", "")[:120]})

    by_group: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_group[r["group"]][r["verdict"]] += 1
        by_group[r["group"]]["total"] += 1

    print(f"{'组':<10}{'条数':>5}{'敏感':>6}{'不敏感':>8}{'反向':>6}{'不稳':>6}{'敏感率':>9}")
    print("-" * 52)
    for g in ("control", "defect"):
        d = by_group.get(g)
        if not d:
            continue
        t = d["total"]
        print(f"{g:<10}{t:>5}{d['sensitive']:>6}{d['insensitive']:>8}{d['reverse']:>6}"
              f"{d['unstable']:>6}{d['sensitive'] / t * 100:>8.0f}%")

    print()
    ctl, dfc = by_group.get("control"), by_group.get("defect")
    if ctl and dfc:
        cs = ctl["sensitive"] / ctl["total"]
        ds = dfc["sensitive"] / dfc["total"]
        print("=" * 62)
        print(f"对照组敏感率 {cs * 100:.0f}%　目标组敏感率 {ds * 100:.0f}%")
        if cs >= 0.7 and ds < cs - 0.2:
            print("✅ **检验有效，且目标组的缺陷是真的**：对照组大多能通过，")
            print("   目标组大多通不过 → 那些标准确实测不出自己声称要测的东西。")
        elif cs < 0.5:
            print("❌ **检验本身不成立**：对照组自己就大量通不过。")
            print("   说明这套 A+/A− 变体没有造出干净的单要素差异，")
            print("   或者裁判根本读不出这个差别 —— **不能据此判定任何标准有罪**。")
        else:
            print("⚠️ 证据不充分：对照组敏感率不够高，无法干净地把责任推给标准。")
        print()
        print("逐条明细（目标组）:")
        for r in rows:
            if r["group"] == "defect":
                mark = {"sensitive": "✅", "insensitive": "❌", "reverse": "🔴", "unstable": "🟡"}[r["verdict"]]
                print(f"  {mark} {r['item_id']}/{r['criterion_id']:4} {r['pairs']}  {r['verdict']}")
        print()
        print("逐条明细（对照组）:")
        for r in rows:
            if r["group"] == "control":
                mark = {"sensitive": "✅", "insensitive": "❌", "reverse": "🔴", "unstable": "🟡"}[r["verdict"]]
                print(f"  {mark} {r['item_id']}/{r['criterion_id']:4} {r['pairs']}  {r['verdict']}")

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps({"rows": rows, "by_group": {k: dict(v) for k, v in by_group.items()}},
                             ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 → {op}")

    # ---- 长度偏差诊断 ----------------------------------------------------
    # A+ 天然比 A− 长（中位数约 +22%），而裁判有已知的长度偏好。
    # 所以"敏感"可能是长度造成的假象。判据：把条目按长度差分成大小两组，
    # 若大长度差组的敏感率明显更高 → 长度是混淆变量，结论要打折。
    withlen = [r for r in rows if r.get("len_gap") is not None]
    if len(withlen) >= 8:
        med = sorted(r["len_gap"] for r in withlen)[len(withlen) // 2]
        big = [r for r in withlen if r["len_gap"] > med]
        small = [r for r in withlen if r["len_gap"] <= med]
        print("\n" + "=" * 62)
        print(f"长度偏差诊断（A+ 与 A− 的字数差中位数 = {med}）")
        for tag, grp in (("长度差大的一半", big), ("长度差小的一半", small)):
            if grp:
                s = sum(1 for r in grp if r["verdict"] == "sensitive")
                print(f"  {tag}: 敏感率 {s}/{len(grp)} = {s / len(grp) * 100:.0f}%")
        if big and small:
            rb = sum(1 for r in big if r["verdict"] == "sensitive") / len(big)
            rs = sum(1 for r in small if r["verdict"] == "sensitive") / len(small)
            if rb - rs > 0.3:
                print("  ⚠️ **长度差大的一组敏感率明显更高 → 长度是混淆变量**，")
                print("     观察到的'敏感'有一部分来自'A+ 更长'，不是标准真的敏感。")
                print("     解读时必须把这一条写出来。")
            else:
                print("  ✅ 两组的敏感率接近 → 没有明显证据表明结论由长度驱动。")
    else:
        print("\n（未提供 --variants，跳过长度偏差诊断 —— 这会留下已知混淆）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
