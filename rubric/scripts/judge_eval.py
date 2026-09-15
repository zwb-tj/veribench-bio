#!/usr/bin/env python3
"""LLM 裁判元评测 —— 第二支柱的本体。

核心方法学主张（也是本项目认为最容易被引用的一点）
------------------------------------------------
> **人类之间的 κ 是 LLM 裁判可靠性的上限。**
> 如果两位人类标注者自己只有 κ=0.55，那么 judge 达到 0.55 就已经"到顶了"；
> 此时说"judge 不够可靠"是不公平的，而只说"judge 与人类一致性 0.6"则是**假精确**。
> 所以本脚本一律报：**人类上限 / judge 绝对值 / judge 相对上限的比例**。

三层工作流（对应 SPEC §6）
------------------------
1. **双盲标注**：A 与 B 各自独立打分（`make_annotation_sheets.py` 生成盲表）
2. **分歧仲裁**：人工解决 A≠B 的条目，得到**金标准**（这是 judge 的比较基准）
3. **judge 元评测**：judge 对同一批条目打分，与金标准比；并统计**系统性偏差**与**失效案例**

若没有仲裁文件，则退化为"仅用 A==B 的条目作金标准"，并**如实报出被排除的比例**
（这个比例本身就是"rubric 写得清不清楚"的指标）。

用法
----
    python3 judge_eval.py --items items.jsonl --ann-a a.jsonl --ann-b b.jsonl \
        --judge judge.jsonl [--arb arbitrated.jsonl] \
        --out judge_eval.json --failure-out failure_cases.jsonl
    python3 judge_eval.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kappa import DEFAULT_ANSWER, analyze, load_pairs  # noqa: E402

#: 人类上限低于这个值时，评判 judge 意义不大，应先修 rubric
HUMAN_CEILING_WARN = 0.40
#: 相对上限的判定档
RELATIVE_BANDS = [
    (0.95, "几乎等同于人类（差异不显著）"),
    (0.90, "达到人类上限的 90% 以上"),
    (0.75, "接近人类上限"),
    (0.50, "明显低于人类上限"),
    (0.00, "远低于人类上限"),
]


def load_items(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            it = json.loads(line)
            out[it["item_id"]] = it
    return out


def build_gold(
    a: dict, b: dict, arb: dict | None
) -> tuple[dict, dict]:
    """返回 (金标准 pairs, 统计)。有仲裁文件就用它；否则只用 A==B 的条目。"""
    keys = sorted(set(a) & set(b))
    gold: dict[tuple[str, str], int] = {}
    stats = {"pairs_common": len(keys), "from_arbitration": 0,
             "from_agreement": 0, "excluded_disagreement": 0, "arb_missing": 0}

    if arb:
        for k in keys:
            if k in arb:
                gold[k] = arb[k]
                stats["from_arbitration"] += 1
            else:
                stats["arb_missing"] += 1
        return gold, stats

    for k in keys:
        if a[k] == b[k]:
            gold[k] = a[k]
            stats["from_agreement"] += 1
        else:
            stats["excluded_disagreement"] += 1
    return gold, stats


def judge_vs_gold(
    judge: dict, gold: dict, score_max: int, n_boot: int, seed: int
) -> dict:
    keys = sorted(set(judge) & set(gold))
    pairs = [(judge[k], gold[k]) for k in keys]
    return analyze({k: judge[k] for k in keys}, {k: gold[k] for k in keys},
                   score_max=score_max, n_boot=n_boot, seed=seed,
                   label_a="judge", label_b="gold")


def bias_report(judge: dict, gold: dict, items: dict[str, dict]) -> dict:
    """系统性偏差：judge 是偏松还是偏严？哪条 rubric 偏得最厉害？"""
    keys = sorted(set(judge) & set(gold))
    if not keys:
        return {"n": 0}
    diffs = [judge[k] - gold[k] for k in keys]
    mean = sum(diffs) / len(diffs)
    per_crit: dict[str, list[int]] = {}
    for k in keys:
        per_crit.setdefault(k[1], []).append(judge[k] - gold[k])
    per_crit_out = {
        c: {"n": len(d), "mean_diff": round(sum(d) / len(d), 4)}
        for c, d in sorted(per_crit.items())
    }
    # 哪种"人类的打分"最容易被 judge 判偏（0/1/2 各自的平均偏差）
    per_gold: dict[int, list[int]] = {}
    for k in keys:
        per_gold.setdefault(gold[k], []).append(judge[k] - gold[k])
    per_gold_out = {
        str(g): {"n": len(d), "mean_diff": round(sum(d) / len(d), 4)}
        for g, d in sorted(per_gold.items())
    }
    return {
        "n": len(keys),
        "mean_diff_judge_minus_gold": round(mean, 4),
        "direction": "偏松（给分更高）" if mean > 0.05 else ("偏严（给分更低）" if mean < -0.05 else "无明显偏移"),
        "exact_match_rate": round(sum(1 for d in diffs if d == 0) / len(diffs), 4),
        "off_by_2_rate": round(sum(1 for d in diffs if abs(d) >= 2) / len(diffs), 4),
        "per_criterion_mean_diff": per_crit_out,
        "per_gold_score_mean_diff": per_gold_out,
    }


def collect_failures(
    judge: dict, gold: dict, items: dict[str, dict]
) -> list[dict]:
    """失效案例：judge 与金标准差距 ≥1 的地方，按严重度排序。"""
    out: list[dict] = []
    for (iid, aid, cid) in sorted(set(judge) & set(gold)):
        d = judge[(iid, aid, cid)] - gold[(iid, aid, cid)]
        if abs(d) < 1:
            continue
        it = items.get(iid) or {}
        crit = next((c for c in (it.get("criteria") or [])
                     if c.get("criterion_id") == cid), {})
        out.append({
            "item_id": iid,
            "answer_id": aid,
            "criterion_id": cid,
            "judge_score": judge[(iid, aid, cid)],
            "gold_score": gold[(iid, aid, cid)],
            "delta": d,
            "severity": abs(d),
            "criterion_text": crit.get("text", ""),
            "anchor_at_gold": (crit.get("anchors") or {}).get(str(gold[(iid, aid, cid)]), ""),
            "anchor_at_judge": (crit.get("anchors") or {}).get(str(judge[(iid, aid, cid)]), ""),
            "question": (it.get("question") or "")[:200],
        })
    out.sort(key=lambda x: -x["severity"])
    return out


def evaluate(
    items: dict[str, dict],
    a: dict, b: dict, judge: dict, arb: dict | None,
    score_max: int = 2, n_boot: int = 2000, seed: int = 20260912,
) -> dict:
    hh = analyze(a, b, score_max=score_max, n_boot=n_boot, seed=seed,
                 label_a="human_A", label_b="human_B")
    ceiling = hh["kappa_quadratic_weighted"]
    ceiling_unw = hh["kappa_unweighted"]

    gold, gold_stats = build_gold(a, b, arb)
    jg = judge_vs_gold(judge, gold, score_max, n_boot, seed)
    judge_kappa = jg["kappa_quadratic_weighted"]
    judge_kappa_unw = jg["kappa_unweighted"]

    # --- 相对上限 ---
    relative = None
    if ceiling is not None and judge_kappa is not None and ceiling > 1e-9:
        relative = round(judge_kappa / ceiling, 4)

    if ceiling is None:
        verdict = "无法评判：人类之间的一致性无法计算（可能全同分或方差不足）"
    elif ceiling < HUMAN_CEILING_WARN:
        verdict = (f"⚠️ 人类之间的一致性过低（κ={ceiling}）—— 此时评判 judge 意义不大。"
                   "应先修 rubric 锚点（锚点不清会让标注者各按各的理解打分），而不是调 judge")
    elif relative is None:
        verdict = "无法计算相对上限"
    else:
        verdict = next(txt for thr, txt in RELATIVE_BANDS if relative >= thr)

    failures = collect_failures(judge, gold, items)
    bias = bias_report(judge, gold, items)

    return {
        "task": "rubric_judge_meta_eval",
        "human_human": {
            "kappa_unweighted": hh["kappa_unweighted"],
            "kappa_quadratic_weighted": ceiling,
            "kappa_quadratic_weighted_ci95": hh["kappa_quadratic_weighted_ci95"],
            "band": hh["band_quadratic"],
            "exact_agreement": hh["exact_agreement"],
            "item_total_exact_agreement": hh["item_total_exact_agreement"],
            "per_criterion": hh["per_criterion"],
            "note": "**这就是 judge 的上限。**",
        },
        "judge_vs_gold": {
            "kappa_unweighted": judge_kappa_unw,
            "kappa_quadratic_weighted": judge_kappa,
            "kappa_quadratic_weighted_ci95": jg["kappa_quadratic_weighted_ci95"],
            "band": jg["band_quadratic"],
            "exact_agreement": jg["exact_agreement"],
            "per_criterion": jg["per_criterion"],
            "n_pairs": jg["pairs_scored"],
        },
        "relative_to_human_ceiling": relative,
        "relative_note": "judge 的加权 κ ÷ 人类之间的加权 κ。**只报 judge 的绝对值是假精确。**",
        "verdict": verdict,
        "gold_standard": gold_stats,
        "bias": bias,
        "failure_cases": {
            "n": len(failures),
            "off_by_1": sum(1 for f in failures if f["severity"] == 1),
            "off_by_2": sum(1 for f in failures if f["severity"] >= 2),
            "top": failures[:10],
        },
    }, failures


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------


def self_test() -> int:
    failures: list[str] = []

    def expect(cond: bool, msg: str) -> None:
        print(f"  [{'ok' if cond else 'FAIL'}] {msg}")
        if not cond:
            failures.append(msg)

    print("=== 裁判元评测自检 ===")

    items = {f"R-{i:04d}": {
        "item_id": f"R-{i:04d}",
        "question": "示例问题" * 3,
        "criteria": [{"criterion_id": "c1", "text": "示例标准",
                      "anchors": {"0": "无", "1": "部分", "2": "完整"}}],
    } for i in range(40)}

    # 场景 1：人类高度一致，judge 也高度一致 → 相对上限应接近 1
    a, b, j = {}, {}, {}
    for i in range(40):
        s = i % 3
        k = (f"R-{i:04d}", DEFAULT_ANSWER, "c1")
        a[k] = s
        b[k] = s            # 完全一致
        j[k] = s            # judge 也完全一致
    res, fails = evaluate(items, a, b, j, None, n_boot=200)
    expect(res["human_human"]["kappa_quadratic_weighted"] is None
           or res["human_human"]["kappa_quadratic_weighted"] >= 0.99,
           f"人类完全一致 → 上限≈1（实得 {res['human_human']['kappa_quadratic_weighted']}）")
    expect(res["relative_to_human_ceiling"] is not None
           and res["relative_to_human_ceiling"] >= 0.99,
           f"judge 完全一致 → 相对上限≈1（实得 {res['relative_to_human_ceiling']}）")
    expect(len(fails) == 0, f"无失效案例（实得 {len(fails)}）")

    # 场景 2：judge 系统性偏松 → 偏差方向应被识别
    a2, b2, j2 = {}, {}, {}
    for i in range(40):
        s = i % 3
        k = (f"R-{i:04d}", DEFAULT_ANSWER, "c1")
        a2[k] = s
        b2[k] = s
        j2[k] = min(2, s + 1)      # 永远高一档
    res2, fails2 = evaluate(items, a2, b2, j2, None, n_boot=200)
    expect("偏松" in res2["bias"]["direction"],
           f"应识别为偏松（实得 {res2['bias']['direction']}）")
    expect(res2["bias"]["mean_diff_judge_minus_gold"] > 0.5,
           f"平均偏差应接近 +1（实得 {res2['bias']['mean_diff_judge_minus_gold']}）")
    expect(len(fails2) > 0, f"应收集到失效案例（实得 {len(fails2)}）")

    # 场景 3：人类之间一致性很低 → verdict 必须警告"先修 rubric"，而不是骂 judge
    a3, b3, j3 = {}, {}, {}
    for i in range(40):
        k = (f"R-{i:04d}", DEFAULT_ANSWER, "c1")
        a3[k] = i % 3
        b3[k] = (i + 1) % 3
        j3[k] = i % 3
    res3, _ = evaluate(items, a3, b3, j3, None, n_boot=200)
    expect("先修 rubric" in res3["verdict"],
           f"人类一致性低时必须提示先修 rubric（实得 verdict={res3['verdict'][:40]!r}）")

    # 场景 4：有仲裁文件时，金标准来自仲裁而不是 A==B
    arb = {(f"R-{i:04d}", DEFAULT_ANSWER, "c1"): 1 for i in range(40)}
    res4, _ = evaluate(items, a3, b3, j3, arb, n_boot=200)
    expect(res4["gold_standard"]["from_arbitration"] == 40,
           f"仲裁文件应被使用（实得 {res4['gold_standard']}）")

    print()
    if failures:
        print(f"❌ 自检未通过（{len(failures)} 项）")
        return 1
    print("✅ 裁判元评测自检通过")
    return 0


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="LLM 裁判元评测")
    ap.add_argument("--items", help="rubric 题目 JSONL")
    ap.add_argument("--ann-a", help="人类标注者 A")
    ap.add_argument("--ann-b", help="人类标注者 B")
    ap.add_argument("--judge", help="judge 标注")
    ap.add_argument("--arb", help="仲裁后的金标准（可选但推荐）")
    ap.add_argument("--score-max", type=int, default=2)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--out", help="结果 JSON")
    ap.add_argument("--failure-out", help="失效案例 JSONL")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not (args.items and args.ann_a and args.ann_b and args.judge):
        ap.error("需要 --items / --ann-a / --ann-b / --judge，或使用 --self-test")

    items = load_items(Path(args.items))
    a = load_pairs(Path(args.ann_a))
    b = load_pairs(Path(args.ann_b))
    j = load_pairs(Path(args.judge))
    arb = load_pairs(Path(args.arb)) if args.arb else None

    res, fails = evaluate(items, a, b, j, arb, args.score_max, args.n_boot)

    hh, jg = res["human_human"], res["judge_vs_gold"]
    print(f"配对条目：人类 {hh.get('exact_agreement')} 严格一致 · judge 对金标准 {jg['n_pairs']} 点")
    print(f"  **人类上限**（二次加权 κ） = {hh['kappa_quadratic_weighted']}  {hh['band']}")
    print(f"    95% CI = {hh['kappa_quadratic_weighted_ci95']}")
    print(f"  judge vs 金标准            = {jg['kappa_quadratic_weighted']}  {jg['band']}")
    print(f"    95% CI = {jg['kappa_quadratic_weighted_ci95']}")
    print(f"  **相对上限** = {res['relative_to_human_ceiling']}  → {res['verdict']}")
    print(f"  偏差：{res['bias']['direction']}（均值 {res['bias']['mean_diff_judge_minus_gold']}）"
          f"  完全命中率 {res['bias']['exact_match_rate']}")
    print(f"  金标准来源：{res['gold_standard']}")
    print(f"  失效案例：{res['failure_cases']['n']} 条"
          f"（差1档 {res['failure_cases']['off_by_1']}，差2档 {res['failure_cases']['off_by_2']}）")

    if args.out:
        Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
        print(f"结果写入 {args.out}")
    if args.failure_out:
        Path(args.failure_out).write_text(
            "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in fails), encoding="utf-8")
        print(f"失效案例写入 {args.failure_out}（{len(fails)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
