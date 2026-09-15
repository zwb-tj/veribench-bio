#!/usr/bin/env python3
"""校验一份提交（submission）是否**自洽**、以及它是否诚实标注了自己的证据。

这个脚本能做什么、不能做什么（**必须写清楚**）
--------------------------------------------
**能**：检查提交内部自洽 —— 分数与逐类结果对得上、数据哈希与本仓库锁定的 manifest 一致、
      关键字段齐全、运行时长在预算内。
**不能**：证明这个分数是**真的跑出来的**。自报分数在不重跑的前提下无法验证。

所以本项目的立场是：**榜单不声称"已验证"，而是提供让别人能复查的一切**。
每条提交都会被标上 `self_reported_unverified`，并且带上
manifest 哈希、镜像 digest、工具链版本 —— 任何人拿同样的数据与镜像都能自己重跑。
这正是本项目"可证明没编造"的做法：**不是要求你信，而是让你能查**。

（参照：bioagent-bench 作者自承真值不敢保证 —— 那是"要你信"；
我们不做那种榜。）

用法：
    python3 verify_submission.py --submission submissions/example.json
    python3 verify_submission.py --submission ... --task T1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                     # bio-eval/

REQUIRED = ["task_id", "submitter", "result"]

#: 运行预算（与 SPEC §4.1 的"30 分钟 CPU-only"一致）
BUDGET_SEC = {"T1": 1800, "T2": 1800}


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="校验一份提交")
    ap.add_argument("--submission", required=True)
    ap.add_argument("--task", help="期望的 task_id（可选，用于交叉核对）")
    ap.add_argument("--json", help="把校验结论写成 JSON（供榜单使用）")
    args = ap.parse_args(argv)

    p = Path(args.submission)
    if not p.is_file():
        print(f"❌ 找不到 {p}")
        return 1

    problems: list[str] = []
    notes: list[str] = []

    try:
        sub = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ 不是合法 JSON：{exc}")
        return 1

    for f in REQUIRED:
        if f not in sub:
            problems.append(f"缺字段 {f!r}")

    tid = sub.get("task_id")
    if args.task and tid != args.task:
        problems.append(f"task_id 是 {tid!r}，期望 {args.task!r}")

    res = sub.get("result") or {}
    if not isinstance(res, dict) or not res:
        problems.append("result 不是非空对象")
        res = {}

    # ---- 内部自洽：分数必须能由逐类结果复算出来 ----
    # 这是本脚本最有价值的一条：它挡不住"没跑就报分"，但能挡住
    # "分数与详细结果对不上"（无论是算错还是手改）。
    pt = res.get("per_type") or {}
    if set(pt) == {"snps", "indels"} and isinstance(res.get("score"), (int, float)):
        try:
            recomputed = (pt["snps"]["f1"] + pt["indels"]["f1"]) / 2
        except (KeyError, TypeError):
            problems.append("per_type 里缺 f1，无法复算 score")
        else:
            if abs(recomputed - res["score"]) > 1e-6:
                problems.append(
                    f"score={res['score']} 与 mean(F1_snp, F1_indel)={recomputed:.5f} 对不上")
            else:
                notes.append(f"score 可由逐类 F1 复算：{res['score']}")
    else:
        notes.append("没提供 per_type.snps/indels 的 f1 —— 只做结构校验，不做分数复算")

    # ---- 数据哈希必须与本仓库锁定的 manifest 一致 ----
    man = ROOT / "tasks" / tid / "_data" / "manifest.json" if tid else None
    if man and man.is_file():
        want = hashlib.sha256(man.read_bytes()).hexdigest()
        got = res.get("manifest_hash")
        if not got or got == "unknown":
            problems.append("没提供 manifest_hash —— 无法确认用的是同一份数据")
        elif got != want:
            problems.append(f"manifest_hash 不一致：提交 {str(got)[:16]}… vs 本仓库 {want[:16]}…")
        else:
            notes.append("manifest_hash 与本仓库锁定的一致")
    else:
        notes.append("本仓库里没有该任务的 manifest（数据未生成？），跳过哈希核对")

    if not res.get("image_digest") or res.get("image_digest") == "unknown":
        problems.append("没提供 image_digest —— 别人无法用同一个镜像复现")

    if res.get("problems"):
        problems.append(f"结果里记录了问题，不应作为成绩提交：{res['problems']}")

    sec = res.get("wall_clock_sec")
    if tid in BUDGET_SEC:
        if not isinstance(sec, (int, float)):
            problems.append("没提供 wall_clock_sec")
        elif sec > BUDGET_SEC[tid]:
            problems.append(f"运行 {sec}s 超出该任务预算 {BUDGET_SEC[tid]}s")

    # ---- 结论 ----
    print(f"提交：{p}")
    print(f"  task_id  = {tid}")
    print(f"  submitter= {sub.get('submitter')}")
    print(f"  模型     = {sub.get('model') or '（未填）'}")
    print(f"  分数     = {res.get('score')}  指标 {res.get('metric')}")
    print()
    for n in notes:
        print(f"  ℹ️ {n}")
    if problems:
        print()
        for x in problems:
            print(f"  ❌ {x}")

    verdict = {
        "submission": p.as_posix(),
        "task_id": tid,
        "submitter": sub.get("submitter"),
        "model": sub.get("model"),
        "score": res.get("score"),
        "metric": res.get("metric"),
        "image_digest": res.get("image_digest"),
        "manifest_hash": res.get("manifest_hash"),
        "wall_clock_sec": sec,
        # 这一行是**刻意**的：榜单不声称验证过分数，只声称"内部自洽"。
        "status": "internally_consistent_unverified" if not problems else "rejected",
        "verification_scope": [
            "检查了提交内部自洽（分数可由逐类结果复算）",
            "检查了数据哈希与本仓库锁定的 manifest 一致",
            "检查了镜像 digest 与运行时长字段存在",
            "**未**重跑 —— 自报分数在不重跑的前提下无法验证",
        ],
        "problems": problems,
    }
    if args.json:
        op = Path(args.json)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结论 → {op}")

    print()
    if problems:
        print(f"❌ 拒绝：{len(problems)} 个问题")
        return 1
    print("✅ 通过（**内部自洽**，不代表分数已被验证）")
    print("   榜单会把它标为 self-reported；重跑所需的哈希与镜像 digest 都在上面，")
    print("   任何人可以据此自行复查。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
