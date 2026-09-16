#!/usr/bin/env python3
"""Cohen's κ 计算器 —— 第二支柱的测量核心。

为什么这是核心
-------------
"用 LLM 当裁判"这件事，如果不报**一致性**，那么整张榜都不可信。
而当前生态的普遍缺陷正是：**要么不发榜，要么用 judge 但不报 κ**。
所以这个脚本是整个第二支柱的地基。

三个必须一起报的量（缺一个都不够）
--------------------------------
1. **未加权 κ** —— 严格一致
2. **加权 κ（线性 / 二次）** —— 评分是**有序**的（0 未满足 / 1 部分 / 2 满足），
   "0 vs 2" 比 "0 vs 1" 严重得多，未加权 κ 把两者等同看待，会低估真实一致性
3. **自助法置信区间** —— **只报点估计是弱证据**。κ=0.6 在 n=30 与 n=500 上的可信度天差地别

还有一个必须说清的方法学要点（写进报告里）
----------------------------------------
> **人类之间的 κ 是 judge 可靠性的上限。**
> 如果两位人类标注者自己只有 κ=0.5，那么 judge 达到 0.5 就已经"到顶了"，
> 此时说"judge 不够可靠"是不公平的。
> 所以 `judge_eval.py` 必须同时报 human-human κ 与 judge-human κ，**并给出相对值**。

输入格式（JSONL，每行一个「条目 × 评分项」的标注）
------------------------------------------------
    {"item_id": "R-0001", "criterion_id": "c1", "score": 2}

用法
----
    python3 kappa.py --a ann_a.jsonl --b ann_b.jsonl --out kappa.json
    python3 kappa.py --self-test
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

#: Landis & Koch (1977) 的解释区间 —— 报告时必须同时给出所处档位，
#: 否则"κ=0.55"对非统计背景的人毫无意义
LANDIS_KOCH = [
    (0.00, "poor", "差"),
    (0.20, "slight", "轻微"),
    (0.40, "fair", "一般"),
    (0.60, "moderate", "中等"),
    (0.80, "substantial", "显著"),
    (1.01, "almost perfect", "几乎完全一致"),
]

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260912  # 固定种子 —— 否则每次跑出的 CI 都不一样，不可复现


def band(k: float | None) -> str:
    if k is None:
        return "无法判定"
    for upper, en, zh in LANDIS_KOCH:
        if k < upper:
            return f"{zh}（{en}）"
    return "几乎完全一致（almost perfect）"


#: 当标注行没有 `answer_id` 时用的占位值。
#: ⚠️ 配对键必须包含**被评的那份回答**，否则同一题的多份回答会互相覆盖。
#: 本项目此前只按 (item_id, criterion_id) 配对 —— 那是"一题一答"的假设，
#: 而实际的裁判实验是**一题三答**（浅/中/优）。这个不一致一直没被发现，
#: 因为人工标注那一步从来没真正跑过（见 make_annotation_sheets.py 的修复记录）。
DEFAULT_ANSWER = "default"


def load_pairs(path: Path) -> dict[tuple[str, str, str], int]:
    """读标注文件，返回 {(item_id, answer_id, criterion_id): score}。

    `answer_id` 缺失时记为 DEFAULT_ANSWER —— 这样旧的夹具文件仍然可用，
    而新写的、一题多答的标注文件不会被静默压成一条。
    """
    out: dict[tuple[str, str, str], int] = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        key = (str(r["item_id"]), str(r.get("answer_id") or DEFAULT_ANSWER),
               str(r["criterion_id"]))
        if key in out:
            raise SystemExit(f"[错误] {path}:{i} 重复标注：{key}")
        out[key] = int(r["score"])
    return out


def confusion(pairs: list[tuple[int, int]], k: int) -> list[list[int]]:
    m = [[0] * k for _ in range(k)]
    for a, b in pairs:
        m[a][b] += 1
    return m


def kappa_unweighted(pairs: list[tuple[int, int]], k: int) -> float | None:
    n = len(pairs)
    if n == 0:
        return None
    m = confusion(pairs, k)
    po = sum(m[i][i] for i in range(k)) / n
    row = [sum(m[i]) / n for i in range(k)]
    col = [sum(m[i][j] for i in range(k)) / n for j in range(k)]
    pe = sum(row[i] * col[i] for i in range(k))
    if abs(1.0 - pe) < 1e-12:
        return None  # 退化：全都标成同一档，κ 无定义（0/0）
    return (po - pe) / (1.0 - pe)


def kappa_weighted(pairs: list[tuple[int, int]], k: int, kind: str) -> float | None:
    """加权 κ。权重是**分歧**权重：w_ij = ((i-j)/(k-1))^2（二次）或 |i-j|/(k-1)（线性）。

    κ_w = 1 - Σ w_ij·O_ij / Σ w_ij·E_ij
    """
    n = len(pairs)
    if n == 0 or k < 2:
        return None
    m = confusion(pairs, k)
    row = [sum(m[i]) / n for i in range(k)]
    col = [sum(m[i][j] for i in range(k)) / n for j in range(k)]

    def w(i: int, j: int) -> float:
        d = abs(i - j) / (k - 1)
        return d * d if kind == "quadratic" else d

    obs = sum(w(i, j) * m[i][j] / n for i in range(k) for j in range(k))
    exp = sum(w(i, j) * row[i] * col[j] for i in range(k) for j in range(k))
    if abs(exp) < 1e-12:
        return None
    return 1.0 - obs / exp


def bootstrap_ci(
    pairs: list[tuple[int, int]], k: int, kind: str | None, n_boot: int, seed: int
) -> tuple[float | None, float | None]:
    """自助法百分位区间。固定种子 → 结果可复现。"""
    if not pairs:
        return None, None
    rng = random.Random(seed)
    n = len(pairs)
    vals: list[float] = []
    for _ in range(n_boot):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        v = kappa_unweighted(sample, k) if kind is None else kappa_weighted(sample, k, kind)
        if v is not None:
            vals.append(v)
    if len(vals) < 50:
        return None, None
    vals.sort()
    lo = vals[int(0.025 * len(vals))]
    hi = vals[int(0.975 * len(vals)) - 1]
    return round(lo, 4), round(hi, 4)


def analyze(
    a: dict[tuple[str, str], int],
    b: dict[tuple[str, str], int],
    score_max: int = 2,
    n_boot: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
    label_a: str = "A",
    label_b: str = "B",
) -> dict:
    k = score_max + 1
    keys = sorted(set(a) & set(b))
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    pairs = [(a[t], b[t]) for t in keys]

    unweighted = kappa_unweighted(pairs, k)
    quad = kappa_weighted(pairs, k, "quadratic")
    lin = kappa_weighted(pairs, k, "linear")

    # 每个评分项的分项一致性（哪一条 rubric 本身就有歧义？）
    by_crit: dict[str, list[tuple[int, int]]] = {}
    for (item, ans, crit) in keys:
        by_crit.setdefault(crit, []).append((a[(item, ans, crit)], b[(item, ans, crit)]))
    per_criterion = {}
    for crit, ps in sorted(by_crit.items()):
        ku = kappa_unweighted(ps, k)
        ea = sum(1 for x, y in ps if x == y) / len(ps)
        # ⚠️ κ 需要**方差**。若某评分项所有标注同分，则 Pe=1 → κ 数学上无定义（0/0）。
        #    这时必须说清原因，否则读者看到"无法判定"会以为这一项有问题，
        #    其实它可能 100% 一致（例如所有答案都完全满足该条 rubric）。
        note = ""
        if ku is None:
            note = "no_variance（该评分项所有标注同分，κ 无定义）→ 请看严格一致率"
        per_criterion[crit] = {
            "n": len(ps),
            "kappa": None if ku is None else round(ku, 4),
            "exact_agreement": round(ea, 4),
            "band": band(ku),
            "note": note,
        }

    # 每个「条目 × 回答」的总分一致性
    # ⚠️ 必须按 (item, answer) 汇总，不能只按 item —— 否则同一题的多份回答
    #    会被加总成一个数，总分一致率就成了无意义的量。
    by_item: dict[tuple[str, str], dict[str, int]] = {}
    for (item, ans, _crit) in keys:
        by_item.setdefault((item, ans), {label_a: 0, label_b: 0})
    for (item, ans, _crit) in keys:
        by_item[(item, ans)][label_a] += a[(item, ans, _crit)]
        by_item[(item, ans)][label_b] += b[(item, ans, _crit)]
    exact = sum(1 for v in by_item.values() if v[label_a] == v[label_b])
    within1 = sum(1 for v in by_item.values() if abs(v[label_a] - v[label_b]) <= 1)

    return {
        "pairs_scored": len(pairs),
        "items": len(by_item),
        "criteria": len(by_crit),
        "only_in_a": len(only_a),
        "only_in_b": len(only_b),
        "kappa_unweighted": None if unweighted is None else round(unweighted, 4),
        "kappa_unweighted_ci95": bootstrap_ci(pairs, k, None, n_boot, seed),
        "kappa_linear_weighted": None if lin is None else round(lin, 4),
        "kappa_quadratic_weighted": None if quad is None else round(quad, 4),
        "kappa_quadratic_weighted_ci95": bootstrap_ci(pairs, k, "quadratic", n_boot, seed),
        "band_unweighted": band(unweighted),
        "band_quadratic": band(quad),
        "exact_agreement": round(sum(1 for x, y in pairs if x == y) / len(pairs), 4) if pairs else None,
        "item_total_exact_agreement": round(exact / len(by_item), 4) if by_item else None,
        "item_total_within_1": round(within1 / len(by_item), 4) if by_item else None,
        "per_criterion": per_criterion,
        "bootstrap": {"n": n_boot, "seed": seed, "method": "percentile"},
        "note": "人类之间的 κ 是 LLM 裁判可靠性的上限 —— 比较时请看相对值，不要只看绝对值",
    }


# ---------------------------------------------------------------------------
# 自检：用**手算得出的已知答案**验证实现（不是"跑通了就算对"）
# ---------------------------------------------------------------------------


def self_test() -> int:
    failures: list[str] = []

    def expect(cond: bool, msg: str) -> None:
        print(f"  [{'ok' if cond else 'FAIL'}] {msg}")
        if not cond:
            failures.append(msg)

    print("=== κ 计算器自检 ===")

    # 案例 1：经典混淆矩阵，手算 κ = 0.4
    #      B1   B2
    # A1   20    5
    # A2   10   15      n=50, Po=0.7, Pe=0.5 → κ=(0.7-0.5)/(1-0.5)=0.4
    pairs = [(0, 0)] * 20 + [(0, 1)] * 5 + [(1, 0)] * 10 + [(1, 1)] * 15
    k2 = kappa_unweighted(pairs, 2)
    expect(k2 is not None and abs(k2 - 0.4) < 1e-9, f"手算案例 κ=0.4（实得 {k2}）")

    # 案例 2：完全一致 → κ = 1
    kp = kappa_unweighted([(0, 0), (1, 1), (2, 2)], 3)
    expect(kp == 1.0, f"完全一致 → κ=1.0（实得 {kp}）")

    # 案例 3：完全不一致（k=2）→ κ = -1
    kn = kappa_unweighted([(0, 1), (1, 0)], 2)
    expect(kn == -1.0, f"完全不一致(k=2) → κ=-1.0（实得 {kn}）")

    # 案例 4：当分歧**只集中在相邻档**时，二次加权 κ 应高于未加权
    # （教训：我第一版断言"加权必然更高"，那是错的 —— 掺入跨两档的分歧后方向会反。
    #   所以这里用对称样本，让性质真正成立。）
    pairs_w = ([(0, 0)] * 10 + [(1, 1)] * 10 + [(2, 2)] * 10
               + [(0, 1)] * 5 + [(1, 2)] * 5)
    ku = kappa_unweighted(pairs_w, 3)
    kq = kappa_weighted(pairs_w, 3, "quadratic")
    expect(kq is not None and ku is not None and kq > ku,
           f"仅相邻分歧时，二次加权 κ 应高于未加权（未加权 {ku:.4f} vs 二次 {kq:.4f}）")

    # 案例 4b：掺入跨两档的分歧后，方向**可以**反过来 —— 记录这个反直觉事实
    pairs_far = [(0, 0)] * 10 + [(1, 1)] * 10 + [(0, 2)] * 12
    ku2 = kappa_unweighted(pairs_far, 3)
    kq2 = kappa_weighted(pairs_far, 3, "quadratic")
    expect(ku2 is not None and kq2 is not None and kq2 < ku2,
           f"跨两档分歧为主时，加权 κ 可以**低于**未加权（未加权 {ku2:.4f} vs 二次 {kq2:.4f}）"
           " —— 所以必须两个都报，不能只报一个")

    # 案例 5：退化情形（全部同一档）→ κ 无定义，返回 None 而不是崩或 0
    kd = kappa_unweighted([(1, 1)] * 10, 3)
    expect(kd is None, f"全部同一档 → κ=None（实得 {kd}）")

    # 案例 6：换种子不影响固定种子的 CI（可复现）
    ci1 = bootstrap_ci(pairs, 2, None, 300, 12345)
    ci2 = bootstrap_ci(pairs, 2, None, 300, 12345)
    expect(ci1 == ci2, f"固定种子的自助 CI 可复现（{ci1} vs {ci2}）")

    # 案例 7：分项一致性 —— 构造一条"有歧义"的评分项，与一条"全同分"的评分项
    aa = {}
    bb = {}
    for i in range(20):
        aa[(f"R-{i:04d}", DEFAULT_ANSWER, "c1")] = 2
        bb[(f"R-{i:04d}", DEFAULT_ANSWER, "c1")] = 2   # c1 全同分 → κ 无定义，但一致率 100%
        aa[(f"R-{i:04d}", DEFAULT_ANSWER, "c2")] = i % 3
        bb[(f"R-{i:04d}", DEFAULT_ANSWER, "c2")] = (i + 1) % 3  # c2 几乎随机
    res = analyze(aa, bb, score_max=2, n_boot=200)
    c1 = res["per_criterion"]["c1"]
    expect(c1["kappa"] is None and c1["exact_agreement"] == 1.0 and "no_variance" in c1["note"],
           f"c1 全同分 → κ 无定义但一致率 100%，且必须说明原因（实得 κ={c1['kappa']}, "
           f"一致率={c1['exact_agreement']}, note={c1['note'][:20]!r}）")
    expect(res["per_criterion"]["c2"]["kappa"] is not None
           and res["per_criterion"]["c2"]["kappa"] < 0.5,
           f"c2 应明显不一致（实得 {res['per_criterion']['c2']['kappa']}）")

    # 案例 8：**一题多答**必须被分开配对，不能被压成一条。
    # 这是本轮修掉的一个真实缺陷：配对键原来只有 (item_id, criterion_id)，
    # 是"一题一答"的假设；而实际的裁判实验是一题三答（浅/中/优）。
    # 没有这个用例，别人可以把键改回两元组而自检照样通过。
    a8, b8 = {}, {}
    a8[("R-0001", "weak", "c1")] = 0
    b8[("R-0001", "weak", "c1")] = 0
    a8[("R-0001", "strong", "c1")] = 2
    b8[("R-0001", "strong", "c1")] = 2
    a8[("R-0001", "absent", "c1")] = 1      # 故意与上面不同分，验证三条各占一格
    b8[("R-0001", "absent", "c1")] = 2
    res8 = analyze(a8, b8, score_max=2, n_boot=100)
    expect(res8["pairs_scored"] == 3,
           f"同一题的 3 份回答必须算 3 个配对（实得 {res8['pairs_scored']}）—— "
           f"若为 1，说明配对键丢了 answer_id")
    expect(res8["items"] == 3,
           f"3 份回答应算 3 个『条目×回答』组（实得 {res8['items']}）—— "
           f"若为 1，说明按 item_id 汇总时把多份回答加到了一起")

    print()
    if failures:
        print(f"❌ 自检未通过（{len(failures)} 项）")
        return 1
    print("✅ κ 计算器自检通过")
    return 0


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="Cohen's κ 计算器（含加权与自助 CI）")
    ap.add_argument("--a", help="标注者 A 的 JSONL")
    ap.add_argument("--b", help="标注者 B 的 JSONL")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--score-max", type=int, default=2, help="单条 rubric 的最高分（默认 2）")
    ap.add_argument("--n-boot", type=int, default=BOOTSTRAP_N)
    ap.add_argument("--out", help="结果 JSON 输出路径")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not (args.a and args.b):
        ap.error("需要 --a 与 --b，或使用 --self-test")

    a = load_pairs(Path(args.a))
    b = load_pairs(Path(args.b))
    res = analyze(a, b, args.score_max, args.n_boot,
                  label_a=args.label_a, label_b=args.label_b)
    res["label_a"], res["label_b"] = args.label_a, args.label_b

    print(f"配对评分点：{res['pairs_scored']}  条目：{res['items']}  评分项：{res['criteria']}")
    print(f"  未加权 κ      = {res['kappa_unweighted']}  {res['band_unweighted']}")
    print(f"  二次加权 κ    = {res['kappa_quadratic_weighted']}  {res['band_quadratic']}")
    print(f"  线性加权 κ    = {res['kappa_linear_weighted']}")
    print(f"  95% CI（二次）= {res['kappa_quadratic_weighted_ci95']}")
    print(f"  条目总分完全一致 = {res['item_total_exact_agreement']}，±1 以内 = {res['item_total_within_1']}")
    print("  分项一致性（哪条 rubric 本身有歧义）：")
    for crit, d in res["per_criterion"].items():
        print(f"    {crit}: κ={d['kappa']}  严格一致={d['exact_agreement']}  n={d['n']}  {d['band']}")
    if res["only_in_a"] or res["only_in_b"]:
        print(f"  ⚠️ 未配对：仅 A {res['only_in_a']} 条，仅 B {res['only_in_b']} 条")
    print(f"\n{res['note']}")

    if args.out:
        Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8", newline="")
        print(f"结果写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
