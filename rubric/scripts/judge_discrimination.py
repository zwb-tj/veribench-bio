#!/usr/bin/env python3
"""裁判区分度检验：同一个裁判，对同一题的三档答案（浅/中/优）是否给出递增分数？

为什么需要这个检验（它不需要人类标注）
--------------------------------------
本项目的核心方法论主张是"人类一致率是裁判可靠性的上限"，但那条链需要
**两个真人**标注才能算，当前卡在人上（见 SPEC §13.2）。

不过有一条**不依赖人类**的效度证据可以先做：**区分度**。
如果一份 rubric + 一个裁判，连"专家级回答"和"敷衍回答"都分不开，
那么无论它跟人类一致率是多少，它都不可能在测量推理能力。

检验设计（防止三类假阳性）
--------------------------
1. **档位必须对裁判不可见**：输入文件名是散列 ID，裁判看不到 weak/strong
   （由 make_blind_judge_set.py 保证）。否则测的是"裁判会不会顺着文件名给分"。
2. **答案必须对评分标准不可见地写成**：写答案的子agent 只拿到题面，没拿到
   criteria（由 make_blind_items.py 保证）。否则答案是照着得分点凑的，
   测的是"裁判会不会照着标准打分"，而不是"标准能否区分真实好坏"。
3. **同一题的三档必须由同一批裁判评**：否则差异可能来自裁判间方差而不是答案质量。
   （由 make_blind_judge_set.py 的打乱 + 这里按 item_id 汇总保证。）

局限（必须随结果一起报告）
--------------------------
- 答案由模型生成，不是真实考生作答。**这是"区分度"证据，不是"效度"证据。**
- 写答案的与当裁判的是同一模型家族 → 存在**自我偏好偏差**风险。
  本检验只能证明"能分开"，不能证明"分得对"。

用法：
    python3 judge_discrimination.py --blind ../fixtures/answers/judge_blind \
        --outdir ../fixtures/answers/judge_out --out ../fixtures/answers/discrimination.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

LEVELS = ["weak", "medium", "strong"]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="裁判区分度检验")
    ap.add_argument("--blind", required=True, help="judge_blind 目录（含 _mapping.json）")
    ap.add_argument("--outdir", required=True, help="裁判输出目录")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    blind = Path(args.blind)
    mapping = json.loads((blind / "_mapping.json").read_text(encoding="utf-8"))
    outdir = Path(args.outdir)

    # item_id -> level -> [scores]
    data: dict[str, dict[str, list[int]]] = {}
    crit_ids: dict[str, list[str]] = {}   # item_id -> 标准编号（按顺序，与 scores 对齐）
    missing: list[str] = []
    for m in mapping:
        p = outdir / f"{m['blind_id']}.json"
        if not p.is_file():
            missing.append(f"{m['item_id']}/{m['level']}")
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        scores = [s["score"] for s in j.get("scores", [])]
        ids = [s["criterion_id"] for s in j.get("scores", [])]
        if not scores:
            missing.append(f"{m['item_id']}/{m['level']}（无分数）")
            continue
        bad = [s for s in scores if s not in (0, 1, 2)]
        if bad:
            print(f"⚠️ {m['item_id']}/{m['level']}: 非 0/1/2 的分数 {bad}")
        # 同一题的不同档位必须覆盖同一组标准，否则逐条对比无意义
        if m["item_id"] in crit_ids and crit_ids[m["item_id"]] != ids:
            print(f"❌ {m['item_id']}/{m['level']}: 标准编号与同题其它档位不一致 "
                  f"{ids} vs {crit_ids[m['item_id']]}")
            return 1
        crit_ids[m["item_id"]] = ids
        data.setdefault(m["item_id"], {})[m["level"]] = scores

    print(f"盲评输入 {len(mapping)} 份；已评 {sum(len(v) for v in data.values())} 份")
    if missing:
        print(f"❌ 缺 {len(missing)} 份：{missing[:10]}{' …' if len(missing) > 10 else ''}")
        return 1

    items = sorted(data)
    max_per_crit = 2
    rows = []
    for iid in items:
        d = data[iid]
        means = {lv: statistics.fmean(d[lv]) for lv in LEVELS}
        ncrit = len(d["strong"])
        rows.append({
            "item_id": iid,
            "n_criteria": ncrit,
            "max_score": ncrit * max_per_crit,
            "mean": {lv: round(means[lv], 3) for lv in LEVELS},
            "norm": {lv: round(means[lv] / max_per_crit, 3) for lv in LEVELS},
            "gap_strong_minus_weak": round(means["strong"] - means["weak"], 3),
            "strict_monotonic": means["weak"] < means["medium"] < means["strong"],
            "weak_lt_strong": means["weak"] < means["strong"],
        })

    # 汇总
    overall = {lv: statistics.fmean([r["mean"][lv] for r in rows]) for lv in LEVELS}
    n_strict = sum(1 for r in rows if r["strict_monotonic"])
    n_pairs = sum(1 for r in rows if r["weak_lt_strong"])
    # 归一化到 0–1（满分为 2/条）
    norm_overall = {lv: overall[lv] / max_per_crit for lv in LEVELS}

    print("\n" + "=" * 78)
    print("每档平均分（满分 2 分/条）")
    for lv in LEVELS:
        print(f"  {lv:7} {overall[lv]:6.3f}   （归一化 {norm_overall[lv]:.3f}）")
    print(f"\n  优 - 浅 差距：{overall['strong'] - overall['weak']:.3f} 分"
          f"（归一化 {(norm_overall['strong'] - norm_overall['weak']):.3f}）")
    print(f"\n严格单调（浅<中<优）的题：{n_strict}/{len(rows)}  = {n_strict / len(rows) * 100:.1f}%")
    print(f"至少 优>浅 的题：      {n_pairs}/{len(rows)}  = {n_pairs / len(rows) * 100:.1f}%")

    weak_items = [r for r in rows if not r["weak_lt_strong"]]
    nonmono = [r for r in rows if not r["strict_monotonic"]]
    if weak_items:
        print(f"\n❌ 裁判**分不开**优与浅的题（{len(weak_items)} 道）——这些题的 rubric 需要重写：")
        for r in weak_items:
            print(f"   {r['item_id']}  浅{r['mean']['weak']:.2f} 中{r['mean']['medium']:.2f} 优{r['mean']['strong']:.2f}")
    if nonmono and not weak_items:
        print(f"\n⚠️ 非严格单调但优>浅（{len(nonmono)} 道）：")
        for r in nonmono:
            print(f"   {r['item_id']}  浅{r['mean']['weak']:.2f} 中{r['mean']['medium']:.2f} 优{r['mean']['strong']:.2f}")

    print("\n逐题明细（浅 / 中 / 优，及优-浅差距）：")
    for r in rows:
        mark = "✅" if r["strict_monotonic"] else ("⚠️" if r["weak_lt_strong"] else "❌")
        print(f"  {mark} {r['item_id']}  {r['mean']['weak']:5.2f} {r['mean']['medium']:5.2f} "
              f"{r['mean']['strong']:5.2f}   Δ{r['gap_strong_minus_weak']:+5.2f}  (满分 {r['max_score']})")

    # ---- 标准级诊断 ----------------------------------------------------------
    # 上面是"整题"层面。但真正要改的是**单条标准**：一条标准若对三档答案都给
    # 同一个分，它对总分毫无贡献，只是噪声；若给浅档的分 ≥ 优档，它就是在反向计分。
    # 这两种缺陷在整题平均里会被稀释掉，所以必须单独列出来。
    crit_rows: list[dict] = []
    for iid in items:
        d = data[iid]
        for k, cid in enumerate(crit_ids[iid]):
            vals = [d[lv][k] for lv in LEVELS]
            w, m_, s_ = vals
            if w < m_ < s_:
                verdict = "healthy"
            elif len(set(vals)) == 1:
                verdict = "saturated"        # 三档同分：零区分度
            elif w >= s_:
                verdict = "inverted"         # 浅档不低于优档：反向计分
            else:
                verdict = "weak_signal"      # 有方向但不单调
            crit_rows.append({"item_id": iid, "criterion_id": cid,
                              "weak": w, "medium": m_, "strong": s_, "verdict": verdict})

    by_verdict: dict[str, list[dict]] = {}
    for r in crit_rows:
        by_verdict.setdefault(r["verdict"], []).append(r)

    print(f"\n{'=' * 78}")
    print(f"标准级诊断（共 {len(crit_rows)} 条标准）")
    for v, label in [("healthy", "健康：三档递增"),
                     ("weak_signal", "信号弱：有方向但不单调"),
                     ("saturated", "**饱和：三档同分，零区分度**"),
                     ("inverted", "**反向：浅档不低于优档**")]:
        rs = by_verdict.get(v, [])
        print(f"  {label:34} {len(rs):3d} 条")
        for r in rs:
            if v in ("saturated", "inverted"):
                print(f"      {r['item_id']}/{r['criterion_id']}  浅{r['weak']} 中{r['medium']} 优{r['strong']}")

    needs_revision = by_verdict.get("saturated", []) + by_verdict.get("inverted", [])
    if needs_revision:
        print(f"\n→ {len(needs_revision)} 条标准需要改写（饱和或反向）。这些是最该动的，"
              f"因为它们在总分里只加噪声，不带来区分。")
    sat_items = sorted({r["item_id"] for r in by_verdict.get("saturated", [])})
    if sat_items:
        print(f"→ 含饱和标准的题：{sat_items}")

    result = {
        "n_items": len(rows),
        "n_criteria_total": sum(r["n_criteria"] for r in rows),
        "overall_mean": {lv: round(overall[lv], 4) for lv in LEVELS},
        "overall_normalized": {lv: round(norm_overall[lv], 4) for lv in LEVELS},
        "gap_strong_minus_weak": round(overall["strong"] - overall["weak"], 4),
        "strict_monotonic_rate": round(n_strict / len(rows), 4),
        "weak_lt_strong_rate": round(n_pairs / len(rows), 4),
        "criterion_verdict_counts": {k: len(v) for k, v in by_verdict.items()},
        "criteria": crit_rows,
        "needs_revision": needs_revision,
        "items": rows,
        "limitations": [
            "答案由模型生成、非真实考生作答：这是区分度证据，不是效度证据",
            "写答案与当裁判为同一模型家族：存在自我偏好偏差风险，只能证明『能分开』不能证明『分得对』",
            "**每个 (题, 档) 只有 1 次裁判判定（n=1）**：单条标准的『饱和』可能是单次判定的噪声，"
            "不宜直接判为该标准无效。要区分『系统性饱和』与『抽样噪声』，需要对同一批输入做第二次"
            "独立裁判，比较两次的稳定性。当前结果应作为**改写候选清单**，不是结论。",
            "本题集 n=24 题 / 101 条标准，样本量小",
            "缺失人类标注天花板，无法回答『裁判相对人类天花板表现如何』（见 SPEC §13.2）",
        ],
    }
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="")
    print(f"\n结果 → {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
