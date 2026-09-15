#!/usr/bin/env python3
"""T3 判分器：比对作答与 mmCIF 重算出的真值。

设计依据 `tasks/T3/DESIGN.md` §3/§4。**真值来自权威公开源、由原文确定性重算**
——本文件**不产生**真值，只做比对。

判分规则（对每道题、每个量独立判定）：

  · 计数类（atom_count / hetatm_count / chain_count）—— **精确相等**才算对
  · element_histogram —— **字典完全相等**才算对（元素集合与每个计数都必须一致）
  · ca_distance —— 按契约**四舍五入到 3 位小数后精确比较**（见下）

⚠️ **距离不能用 `abs(got-want) <= 0.001` 这种 epsilon 比较。**
实测过：`abs(3.801 - 3.8) = 0.001000000000000334` —— 比 0.001 大一点点
（差 3.3e-16），于是"容差内的正确作答"被判错。
根因是 **epsilon 恰好设在浮点噪声的量级上**，边界由 IEEE-754 舍入噪声决定，
不可依赖。契约说作答保留 3 位小数，那就该比 `round(got,3) == round(want,3)`：
精确、无 epsilon、且与契约一致。

得分 = 该题各量命中数 / 该题量数，再对所有题取平均（macro）。

用法：
    python3 grade.py --items items.jsonl --truth truth.jsonl \
                     --answers answers.jsonl --out result.json
    python3 grade.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: 计数类量：必须精确相等
COUNT_METRICS = ("atom_count", "hetatm_count", "chain_count")
#: 距离的**小数位数**（契约：作答按 3 位小数提交）
DIST_DECIMALS = 3


def load_jsonl(p: Path) -> list[dict]:
    out = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"[错误] {p}:{i} 不是合法 JSON：{e}") from None
    return out


def grade_one(truth: dict, ans: dict | None) -> tuple[float, list[str]]:
    """返回 (该题得分 0..1, 问题列表)。"""
    if ans is None:
        return 0.0, ["未作答"]

    problems: list[str] = []
    hits = 0
    total = 0

    for k in COUNT_METRICS:
        total += 1
        want = truth.get(k)
        got = ans.get(k)
        # ⚠️ 不接受 bool：`True == 1` 在 Python 里成立，会让错答案侥幸得分
        if isinstance(got, bool) or not isinstance(got, int):
            problems.append(f"{k}: 期望整数，得到 {type(got).__name__}")
            continue
        if got == want:
            hits += 1
        else:
            problems.append(f"{k}: {got} ≠ {want}")

    # element_histogram：字典完全相等
    total += 1
    want_h = truth.get("element_histogram") or {}
    got_h = ans.get("element_histogram")
    if not isinstance(got_h, dict):
        problems.append(f"element_histogram: 期望 dict，得到 {type(got_h).__name__}")
    elif {str(k): v for k, v in got_h.items()} == {str(k): v for k, v in want_h.items()}:
        hits += 1
    else:
        problems.append("element_histogram: 与真值不同")

    # ca_distance：按契约四舍五入到 3 位小数后**精确**比较（不用 epsilon，见模块注释）
    total += 1
    want_d = truth.get("ca_distance")
    got_d = ans.get("ca_distance")
    if isinstance(got_d, bool) or not isinstance(got_d, (int, float)):
        problems.append(f"ca_distance: 期望数值，得到 {type(got_d).__name__}")
    elif want_d is None:
        problems.append("ca_distance: 真值为空（该题不应出现在题池里）")
    elif round(float(got_d), DIST_DECIMALS) == round(float(want_d), DIST_DECIMALS):
        hits += 1
    else:
        problems.append(f"ca_distance: {got_d} 与真值 {want_d} 在 3 位小数上不等")

    return hits / total if total else 0.0, problems


def run(items: list[dict], truth: list[dict], answers: list[dict]) -> dict:
    tmap = {t["item_id"]: t for t in truth}
    amap = {a.get("item_id"): a for a in answers}

    per_item = []
    n_hit_metric = 0
    n_metric = 0
    all_problems: list[str] = []

    for it in sorted(items, key=lambda r: r["item_id"]):
        iid = it["item_id"]
        t = tmap.get(iid)
        if t is None:
            all_problems.append(f"{iid}: 题面在，真值缺失")
            continue
        score, probs = grade_one(t, amap.get(iid))
        n_metric += 5
        n_hit_metric += round(score * 5)
        per_item.append({"item_id": iid, "pdb_id": it.get("pdb_id"),
                         "score": round(score, 4), "problems": probs})
        all_problems += [f"{iid}: {p}" for p in probs]

    #: 题面里有、作答里没有的
    extra = sorted(set(amap) - set(tmap))
    if extra:
        all_problems.append(f"作答含未知 item_id：{extra[:5]}")

    macro = (sum(p["score"] for p in per_item) / len(per_item)) if per_item else 0.0
    return {
        "task_id": "T3",
        "score": round(macro, 5),
        "metric": "macro_mean_of_metric_accuracy",
        "status": "ok" if per_item else "error",
        "counts": {"items": len(items), "truths": len(truth), "answers": len(answers),
                   "graded": len(per_item),
                   "metric_hits": n_hit_metric, "metric_total": n_metric},
        "per_item": per_item,
        "problems": all_problems[:50],
    }


def self_test() -> int:
    """自检：**证明判分器在错答案上会扣分**，而不是恒真。"""
    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            ok = False
        print(f"  {'✅' if cond else '❌'} {label}" + (f"  {detail}" if detail else ""))

    truth = [{"item_id": "T3-XXXX", "pdb_id": "XXXX", "atom_count": 10,
              "hetatm_count": 2, "chain_count": 1,
              "element_histogram": {"C": 6, "N": 2, "O": 2}, "ca_distance": 3.8}]
    items = [{"item_id": "T3-XXXX", "pdb_id": "XXXX"}]

    print("=== T3 判分器自检 ===")

    # ① 完美作答 → 1.0
    exact = {"item_id": "T3-XXXX", "atom_count": 10, "hetatm_count": 2,
             "chain_count": 1, "element_histogram": {"C": 6, "N": 2, "O": 2},
             "ca_distance": 3.8}
    r = run(items, truth, [exact])
    check("完美作答 → 1.0", r["score"] == 1.0, str(r["score"]))

    # ② 负向：错一个计数 → 必须掉分
    bad = dict(exact); bad["atom_count"] = 11
    r = run(items, truth, [bad])
    check("错 1 个计数 → < 1.0", r["score"] < 1.0, f"{r['score']}")

    # ③ 负向：**bool 不能冒充 int**（True == 1 是 Python 陷阱）
    bad2 = dict(exact); bad2["chain_count"] = True
    r = run(items, truth, [bad2])
    check("chain_count=True 不算对（bool 陷阱）", r["score"] < 1.0, f"{r['score']}")

    # ④ 负向：直方图差一个元素 → 不算对
    bad3 = dict(exact); bad3["element_histogram"] = {"C": 6, "N": 2, "O": 3}
    r = run(items, truth, [bad3])
    check("直方图不同 → 不算对", r["score"] < 1.0, f"{r['score']}")

    # ⑤ 距离：按 3 位小数**精确**比较。
    #    ⚠️ 这里刻意保留两个"看起来该算对、但按契约不该算对"的用例，
    #    它们正是我用 epsilon 比较时踩坑的地方：
    same = dict(exact); same["ca_distance"] = 3.8000   # 写法不同、值相同 → 算对
    r = run(items, truth, [same])
    check("距离 3.8000（同值不同写法）→ 1.0", r["score"] == 1.0, str(r["score"]))

    near = dict(exact); near["ca_distance"] = 3.7999   # 3 位小数后 == 3.8 → 算对
    r = run(items, truth, [near])
    check("距离 3.7999（3 位小数后为 3.800）→ 1.0", r["score"] == 1.0, str(r["score"]))

    far = dict(exact); far["ca_distance"] = 3.801      # 3 位小数后 != 3.8 → 不算对
    r = run(items, truth, [far])
    check("距离 3.801（3 位小数后为 3.801）→ < 1.0", r["score"] < 1.0, f"{r['score']}")

    far2 = dict(exact); far2["ca_distance"] = 3.81
    r = run(items, truth, [far2])
    check("距离 3.81（明显不同）→ < 1.0", r["score"] < 1.0, f"{r['score']}")

    # ⑥ 负向：未作答 → 0
    r = run(items, truth, [])
    check("未作答 → 0.0", r["score"] == 0.0, str(r["score"]))
    check("未作答会记录 problem", any("未作答" in p for p in r["problems"]))

    # ⑦ 负向：缺字段 → 不算对（不能静默通过）
    r = run(items, truth, [{"item_id": "T3-XXXX"}])
    check("空作答对象 → 0.0", r["score"] == 0.0, str(r["score"]))

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="T3 判分器")
    ap.add_argument("--items", help="题面 JSONL")
    ap.add_argument("--truth", help="真值 JSONL")
    ap.add_argument("--answers", help="作答 JSONL")
    ap.add_argument("--out", help="结果输出路径")
    ap.add_argument("--self-test", action="store_true", help="自检判分逻辑")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not (args.items and args.truth and args.answers):
        ap.error("需要 --items / --truth / --answers，或使用 --self-test")

    items = load_jsonl(Path(args.items))
    truth = load_jsonl(Path(args.truth))
    answers = load_jsonl(Path(args.answers))

    res = run(items, truth, answers)
    line = (f"T3: score={res['score']}  "
            f"量命中 {res['counts']['metric_hits']}/{res['counts']['metric_total']}  "
            f"已判 {res['counts']['graded']}/{res['counts']['items']} 题")
    print(line)
    if res["problems"]:
        print(f"  问题 {len(res['problems'])} 条，前 5：")
        for p in res["problems"][:5]:
            print(f"    · {p}")

    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  → {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
