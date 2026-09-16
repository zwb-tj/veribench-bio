#!/usr/bin/env python3
"""T4 判分器：比对作答与 OBO 原文重算出的真值。

设计依据 `tasks/T4/DESIGN.md` §3。**真值来自权威公开源、由原文确定性重算**
—— 本文件**不产生**真值，只做比对。

判分规则（对每道题、每个量独立判定）：

  · name —— 字符串**精确相等**（去首尾空白后）
  · namespace —— 字符串精确相等
  · direct_parent_count —— **精确相等**（不接受 bool）
  · depth_to_root —— **精确相等**（整数；纯图距离，无浮点，无需容差）

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

#: 判分量。**由常量推导每题量数**，不写字面量 ——
#: T3 曾把 `n_metric += 5` 写死，加一个判分量就静默算错总数，
#: 而错的总数看起来仍像个正常数字。
COUNT_METRICS = ("direct_parent_count", "depth_to_root")
STR_METRICS = ("name", "namespace")
N_METRICS_PER_ITEM = len(COUNT_METRICS) + len(STR_METRICS)


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


def _int_ok(v) -> bool:
    """严格的整数判定 —— **bool 不算**（`True == 1` 是 Python 陷阱）。"""
    return isinstance(v, int) and not isinstance(v, bool)


def grade_one(truth: dict, ans: dict | None) -> tuple[float, list[str]]:
    """返回 (该题得分 0..1, 问题列表)。"""
    if ans is None:
        return 0.0, ["未作答"]

    problems: list[str] = []
    hits = 0
    total = 0

    for k in STR_METRICS:
        total += 1
        want, got = truth.get(k), ans.get(k)
        if not isinstance(got, str):
            problems.append(f"{k}: 期望字符串，得到 {type(got).__name__}")
            continue
        if got.strip() == str(want).strip():
            hits += 1
        else:
            problems.append(f"{k}: {got!r} ≠ {want!r}")

    for k in COUNT_METRICS:
        total += 1
        want, got = truth.get(k), ans.get(k)
        if not _int_ok(got):
            problems.append(f"{k}: 期望整数，得到 {type(got).__name__}")
            continue
        if got == want:
            hits += 1
        else:
            problems.append(f"{k}: {got} ≠ {want}")

    return (hits / total if total else 0.0), problems


def run(items: list[dict], truth: list[dict], answers: list[dict]) -> dict:
    tmap = {t["item_id"]: t for t in truth}
    amap = {a.get("item_id"): a for a in answers}

    per_item: list[dict] = []
    all_problems: list[str] = []

    for it in sorted(items, key=lambda r: r["item_id"]):
        iid = it["item_id"]
        t = tmap.get(iid)
        if t is None:
            all_problems.append(f"{iid}: 题面在，真值缺失")
            continue
        score, probs = grade_one(t, amap.get(iid))
        per_item.append({"item_id": iid, "go_id": it.get("go_id"),
                         "score": round(score, 4), "problems": probs})
        all_problems += [f"{iid}: {p}" for p in probs]

    extra = sorted(set(amap) - set(tmap))
    if extra:
        all_problems.append(f"作答含未知 item_id：{extra[:5]}")

    hits = sum(round(p["score"] * N_METRICS_PER_ITEM) for p in per_item)
    macro = (sum(p["score"] for p in per_item) / len(per_item)) if per_item else 0.0
    return {
        "task_id": "T4",
        "score": round(macro, 5),
        "metric": "macro_mean_of_metric_accuracy",
        "status": "ok" if per_item else "error",
        "counts": {"items": len(items), "truths": len(truth), "answers": len(answers),
                   "graded": len(per_item),
                   "metric_hits": hits,
                   "metric_total": len(per_item) * N_METRICS_PER_ITEM},
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

    truth = [{"item_id": "T4-GO:0000022", "go_id": "GO:0000022",
              "name": "mitotic spindle elongation",
              "namespace": "biological_process",
              "direct_parent_count": 2, "depth_to_root": 6}]
    items = [{"item_id": "T4-GO:0000022", "go_id": "GO:0000022"}]

    print("=== T4 判分器自检 ===")

    exact = {"item_id": "T4-GO:0000022", "name": "mitotic spindle elongation",
             "namespace": "biological_process",
             "direct_parent_count": 2, "depth_to_root": 6}
    r = run(items, truth, [exact])
    check("完美作答 → 1.0", r["score"] == 1.0, str(r["score"]))

    # 负向：错一个计数
    bad = dict(exact); bad["direct_parent_count"] = 3
    r = run(items, truth, [bad])
    check("错 1 个计数 → < 1.0", r["score"] < 1.0, str(r["score"]))

    # 负向：**bool 不能冒充 int**
    bad2 = dict(exact); bad2["depth_to_root"] = True
    r = run(items, truth, [bad2])
    check("depth_to_root=True 不算对（bool 陷阱）", r["score"] < 1.0, str(r["score"]))

    # 负向：名字差一个字符
    bad3 = dict(exact); bad3["name"] = "mitotic spindle elongatio"
    r = run(items, truth, [bad3])
    check("name 差一个字符 → 不算对", r["score"] < 1.0, str(r["score"]))

    # 正向：首尾空白应被容忍（作答常带空格）
    pads = dict(exact); pads["name"] = "  mitotic spindle elongation  "
    r = run(items, truth, [pads])
    check("name 首尾空白 → 仍算对", r["score"] == 1.0, str(r["score"]))

    # 负向：未作答 → 0
    r = run(items, truth, [])
    check("未作答 → 0.0", r["score"] == 0.0, str(r["score"]))
    check("未作答会记录 problem", any("未作答" in p for p in r["problems"]))

    # 负向：空作答对象 → 0（不能静默通过）
    r = run(items, truth, [{"item_id": "T4-GO:0000022"}])
    check("空作答对象 → 0.0", r["score"] == 0.0, str(r["score"]))

    # 量数由常量推导 —— 防止 T3 那个 `n_metric += 5` 的坑
    check("每题量数由常量推导", N_METRICS_PER_ITEM == 4, str(N_METRICS_PER_ITEM))

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="T4 判分器")
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

    res = run(load_jsonl(Path(args.items)), load_jsonl(Path(args.truth)),
              load_jsonl(Path(args.answers)))
    print(f"T4: score={res['score']}  "
          f"量命中 {res['counts']['metric_hits']}/{res['counts']['metric_total']}  "
          f"已判 {res['counts']['graded']}/{res['counts']['items']} 题")
    if res["problems"]:
        print(f"  问题 {len(res['problems'])} 条，前 5：")
        for p in res["problems"][:5]:
            print(f"    · {p}")
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        # ⚠️ newline="" —— 见 fetch_go.py 的说明
        op.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="")
        print(f"  → {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
