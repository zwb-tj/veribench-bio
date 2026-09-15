#!/usr/bin/env python3
"""打印项目的**全部规模数字**，供文档/简历/README 引用时直接复算。

为什么要单独写这个
------------------
2026-09 实测发现：README 里写"5 个不存在的路径"、DATACARD 写 40,110（实际 40,170）、
T1 覆盖区间被写错 5 倍（10–20 Mb vs 实际 10–12 Mb）……
**每一个都是"数字写下来之后没人再算过"。**

更麻烦的是：同一个数字（如发布文件数、检查步数）会出现在 README、DATACARD、
项目速览、简历等多个地方，靠手抄必然漂移。

所以这里把"我们对外说的那些数字"集中在一处**实测**出来。
改文档前先跑它 —— 而不是凭记忆写。

用法
----
    python3 print_project_stats.py            # 人读
    python3 print_project_stats.py --json     # 机器读（给脚本/CI 用）
    python3 print_project_stats.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

SKIP_PARTS = {".git", "__pycache__", "_artifacts", "_scratch", "_fixtures",
              "judge_out", "judge_out_run1", "judge_out_run2",
              "manip_out_run1", "manip_out_run2", "judge_outputs"}


def publishable() -> list[tuple[str, int]]:
    """**委托给唯一实现**（`publishable_files.py`），返回值加上字节数。

    ⚠️ 这里原本自己抄了一份遍历+过滤逻辑。它第一版**漏排除 `.git/`**，
    把 615 个 git 对象文件算成发布内容，报出 1308 文件 / 79.3 MB
    （真实 693 / 65.2 MB）—— 而那个错数字**看起来完全正常**，
    要不是另有一份核对脚本给出 693，根本不会发现。

    那正是"同一段逻辑抄三份"的必然结果：三份会漂移，而漂移不报警。
    现在过滤只有一份，**统计与安全检查看到的是同一个文件集合**。
    """
    from publishable_files import publishable as _pub
    return [(p.relative_to(ROOT).as_posix(), p.stat().st_size) for p in _pub()]


def count_self_tests() -> tuple[int, int]:
    """返回 (带 argparse 的脚本数, 带 --self-test 的脚本数)。"""
    n_arg = n_self = 0
    for p in ROOT.rglob("*.py"):
        if any(x in p.parts for x in SKIP_PARTS):
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "add_argument" in t:
            n_arg += 1
        if re.search(r'add_argument\(\s*["\']--self-test', t):
            n_self += 1
    return n_arg, n_self


def collect() -> dict:
    st: dict = {}

    # --- 发布集 ---
    pub = publishable()
    st["published_files"] = len(pub)
    st["published_py"] = sum(1 for r, _ in pub if r.endswith(".py"))
    st["published_md"] = sum(1 for r, _ in pub if r.endswith(".md"))
    st["published_mb"] = round(sum(s for _, s in pub) / 1e6, 1)

    # --- 检查体系 ---
    suite = (ROOT / "run_all_checks.py").read_text(encoding="utf-8")
    st["check_steps"] = len(re.findall(r"results\.append\(run\(", suite))
    st["argparse_scripts"], st["self_test_scripts"] = count_self_tests()

    # --- 台账 / rubric ---
    st["ledger_entries"] = sum(
        1 for l in (ROOT / "ledger/items.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip())

    items = [json.loads(l) for l in
             (ROOT / "rubric/items/items_v1.2.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    st["rubric_items"] = len(items)
    st["rubric_criteria"] = sum(len(i.get("criteria") or []) for i in items)

    # --- T1 实跑 ---
    runs = []
    for d in sorted((ROOT / "tasks/T1").glob("_runs*")):
        rp, tp = d / "result.json", d / "timing_call.json"
        if not rp.is_file():
            continue
        try:
            r = json.loads(rp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        n = None
        if tp.is_file():
            try:
                n = json.loads(tp.read_text(encoding="utf-8")).get("variants")
            except (OSError, ValueError):
                pass
        runs.append({"dir": d.name, "score": r.get("score"), "variants": n,
                     "wall_sec": r.get("wall_clock_sec"),
                     "peak_rss_mb": r.get("peak_rss_mb"),
                     "image_digest": r.get("image_digest")})
    st["t1_runs"] = len(runs)
    st["t1_scores"] = sorted({str(r["score"]) for r in runs})
    st["t1_variants"] = sorted({str(r["variants"]) for r in runs})
    walls = [r["wall_sec"] for r in runs if r.get("wall_sec")]
    rsss = [r["peak_rss_mb"] for r in runs if r.get("peak_rss_mb")]
    st["t1_wall_min"], st["t1_wall_max"] = (min(walls), max(walls)) if walls else (None, None)
    st["t1_rss_min"], st["t1_rss_max"] = (min(rsss), max(rsss)) if rsss else (None, None)

    # --- T2 ---
    for task, path, key in (("t2", "tasks/T2/data/items.jsonl", "t2_items"),
                            ("t2c", "tasks/T2/data/items.jsonl", "t2_canary")):
        p = ROOT / path
        if not p.is_file():
            st[key] = None
            continue
        rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        if key == "t2_items":
            st[key] = len(rows)
        else:
            st[key] = sum(1 for r in rows if r.get("canary") is True)
    if st.get("t2_items"):
        st["t2_canary_pct"] = round(st["t2_canary"] / st["t2_items"] * 100, 1)

    # --- 轮换池 ---
    pub_items = ROOT / "tasks/T2/data/public/items.jsonl"
    rot_items = ROOT / "tasks/T2/data/rotation/items.jsonl"
    for key, p in (("t2_public", pub_items), ("t2_rotation", rot_items)):
        st[key] = (sum(1 for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
                   if p.is_file() else None)
    return st


def self_test() -> int:
    """负向测试：数字必须是**算出来的**，且随产物变化而变化。

    这里验的是"脚本确实在读产物"，而不是读了一个写死的常量。
    手法：断言几个关键数字非空、且集合关系自洽（如公开+轮换 == 全量）。
    """
    st = collect()
    ok = True
    checks = [
        ("published_files > 0", st["published_files"] > 0, st["published_files"]),
        ("check_steps > 0", st["check_steps"] > 0, st["check_steps"]),
        ("self_test_scripts > 0", st["self_test_scripts"] > 0, st["self_test_scripts"]),
        ("ledger_entries >= 30", st["ledger_entries"] >= 30, st["ledger_entries"]),
        ("rubric 24 题", st["rubric_items"] == 24, st["rubric_items"]),
        ("rubric 101 条", st["rubric_criteria"] == 101, st["rubric_criteria"]),
        ("T1 六次实跑", st["t1_runs"] == 6, st["t1_runs"]),
        ("T1 得分唯一 0.84655", st["t1_scores"] == ["0.84655"], st["t1_scores"]),
        ("T1 变异数唯一 12254", st["t1_variants"] == ["12254"], st["t1_variants"]),
        ("T2 4726 条", st["t2_items"] == 4726, st["t2_items"]),
        ("T2 金丝雀 1181", st["t2_canary"] == 1181, st["t2_canary"]),
    ]
    # 公开 + 轮换 == 全量（不重不漏）—— 只有产物都在时才能验
    if st.get("t2_public") and st.get("t2_rotation"):
        s = st["t2_public"] + st["t2_rotation"]
        checks.append(("公开 + 轮换 == 全量", s == st["t2_items"], f"{s} vs {st['t2_items']}"))

    for label, cond, val in checks:
        if not cond:
            ok = False
        print(f"  {'✅' if cond else '❌'} {label}  → {val}")

    # ⚠️ **关键负向测试**：发布集里绝不能出现 `.git/` 或运行期目录。
    #    这条来自一个真实 bug —— 第一版漏了排除 `.git`，
    #    于是把 615 个 git 对象文件算进"发布内容"，报出 1308 文件 / 79.3 MB
    #    （真实 692 / 65.2 MB）。**它看起来像个正常数字**，
    #    要不是另一份核对脚本给出 692，根本不会发现。
    pub = publishable()
    leaked = [r for r, _ in pub
              if r.startswith(".git/") or "/.git/" in r
              or r.startswith("__pycache__/") or "/__pycache__/" in r]
    for label, cond in (
        ("发布集不含 .git/ 或 __pycache__/", not leaked),
        ("发布文件数在合理区间（500–1000）", 500 <= len(pub) <= 1000),
    ):
        if not cond:
            ok = False
        print(f"  {'✅' if cond else '❌'} {label}"
              + (f"  → 泄漏样例 {leaked[:3]}" if leaked else f"  → {len(pub)} 个文件"))

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="实测并打印项目的规模数字")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--self-test", action="store_true", help="负向测试")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    st = collect()
    if args.json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0

    print("=== 发布集（GitHub 上会看到的）===")
    print(f"  文件           : {st['published_files']}（.py {st['published_py']} / .md {st['published_md']}）")
    print(f"  体积           : {st['published_mb']} MB")
    print()
    print("=== 检查体系 ===")
    print(f"  run_all_checks : {st['check_steps']} 步")
    print(f"  带 argparse    : {st['argparse_scripts']} 个脚本")
    print(f"  带 --self-test : {st['self_test_scripts']} 个（能证明自己会失败）")
    print()
    print("=== 数据规模 ===")
    print(f"  台账           : {st['ledger_entries']} 条")
    print(f"  rubric         : {st['rubric_items']} 题 / {st['rubric_criteria']} 条标准")
    if st.get("t2_items"):
        print(f"  T2             : {st['t2_items']} 条（金丝雀 {st['t2_canary']} = {st.get('t2_canary_pct')}%）")
    if st.get("t2_public"):
        print(f"  T2 公开/轮换   : {st['t2_public']} / {st['t2_rotation']}")
    print()
    print("=== T1 实跑 ===")
    print(f"  次数           : {st['t1_runs']}")
    print(f"  得分集合       : {st['t1_scores']}   ← 必须只有一个值")
    print(f"  变异数集合     : {st['t1_variants']}   ← 必须只有一个值")
    print(f"  耗时区间       : {st['t1_wall_min']}–{st['t1_wall_max']} 秒")
    print(f"  内存区间       : {st['t1_rss_min']:.1f}–{st['t1_rss_max']:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
