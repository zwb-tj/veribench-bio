#!/usr/bin/env python3
"""核对 `tasks/T1/run.sh` 的默认值与 `tasks/T1/data/prepare_data.sh` 的产物**是否一致**。

为什么需要它
------------
2026-09 实测发现 `run.sh` 的两个默认值**都是错的**：

    run.sh:16  BAM="${BAM:-${DATA_DIR}/aln/HG002.chr20.bam}"        ← 少了 .30x
    run.sh:13  REGION="${REGION:-chr20:10000000-20000000}"          ← 数据只有 10–12 Mb

而数据准备脚本产出的文件名是 `$ALN_DIR/HG002.$CONTIG.${TARGET_COV}x.bam`
（默认即 `aln/HG002.chr20.30x.bam`）。

**为什么以前没被发现**：历史上每一个 driver 都写着
`export REGION=...` / `export BAM=...`，把 `run.sh` 的默认值**整个覆盖掉了**。
于是这两个默认值从来没有被执行过 —— 一段"从没跑过的代码"，错不错没人知道。
新人照 README 走默认路径，第一步就 `exit 2`（缺少输入文件）。

本脚本检查的是一条**纯粹的约定不变量**，不需要 Docker、不需要数据：
**生产方（prepare_data.sh）与消费方（run.sh）必须对同一个文件名和同一个区间达成一致。**

用法
----
    python3 check_t1_scripts_agree.py
    python3 check_t1_scripts_agree.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
T1 = ROOT / "tasks" / "T1"
PREPARE = T1 / "data" / "prepare_data.sh"
RUN = T1 / "run.sh"

#: 一段允许出现**一层嵌套**的 ${...} 的取值表达式。
#: ⚠️ 两个坑，都是 --self-test 抓出来的：
#:    1. 不能写成 `[^}]*` —— `BAM="${BAM:-${DATA_DIR}/aln/x.bam}"` 里的
#:       `${DATA_DIR}` 自带一个 `}`，那样会在错误的位置截断。
#:    2. 必须排除 `"` 与换行 —— 否则 `ALN_DIR="$DATA_DIR/aln"` 会一路吃到
#:       后面几行的引号去，解析出一个跨行的"文件名"。
_VALUE = r'((?:[^{}"\n]|\$\{[^{}]*\})*)'


def _patterns(var: str) -> tuple[str, str]:
    v = re.escape(var)
    return (
        r"^" + v + r'="\$\{' + v + r":-" + _VALUE + r'\}"',   # VAR="${VAR:-default}"
        r"^" + v + r'="' + _VALUE + r'"',                      # VAR="value"
    )


def bash_value(text: str, var: str) -> str | None:
    """取 bash 变量的值：优先 `${VAR:-default}`，其次普通赋值。"""
    for pat in _patterns(var):
        m = re.search(pat, text, re.M)
        if m:
            return m.group(1)
    return None


def expand(expr: str, subs: dict[str, str]) -> str:
    """按给定替换表展开，并且**允许 $VAR 与 ${VAR} 两种写法**。"""
    for name, val in subs.items():
        expr = expr.replace("${" + name + "}", val).replace("$" + name, val)
    return expr.lstrip("/")


def check(prepare_text: str, run_text: str) -> tuple[list[str], list[str]]:
    """返回 (问题列表, 说明列表)。两段文本分开传入，方便负向测试。"""
    problems: list[str] = []
    notes: list[str] = []

    p_region = bash_value(prepare_text, "REGION")
    p_contig = bash_value(prepare_text, "CONTIG")
    p_cov = bash_value(prepare_text, "TARGET_COV")
    r_region = bash_value(run_text, "REGION")
    r_bam = bash_value(run_text, "BAM")

    for name, val in (("prepare_data.sh REGION", p_region), ("prepare_data.sh CONTIG", p_contig),
                      ("prepare_data.sh TARGET_COV", p_cov), ("run.sh REGION", r_region),
                      ("run.sh BAM", r_bam)):
        if val is None:
            problems.append(f"{name}: 解析不到默认值（脚本结构变了？本检查的解析需要同步更新）")
    if problems:
        return problems, notes

    # ① 区间必须一致
    notes.append(f"prepare_data.sh REGION = {p_region}")
    notes.append(f"run.sh          REGION = {r_region}")
    if p_region != r_region:
        problems.append(
            f"区间不一致：prepare_data.sh 取 {p_region}，而 run.sh 默认在 {r_region} 上找变异。"
            "两者必须相同 —— 否则默认路径会跑在数据没有覆盖的区间上。"
        )

    # ② BAM 文件名必须与生产方拼出来的名字一致
    sampled = re.search(r'^SAMPLED="' + _VALUE + r'"', prepare_text, re.M)
    if not sampled:
        problems.append('prepare_data.sh 里找不到 SAMPLED="..." —— 无法推导产物文件名')
        return problems, notes
    aln_dir = bash_value(prepare_text, "ALN_DIR") or ""
    aln_rel = expand(aln_dir, {"DATA_DIR": ""})
    expected = expand(sampled.group(1), {
        "ALN_DIR": aln_rel, "DATA_DIR": "", "CONTIG": p_contig, "TARGET_COV": p_cov,
    })
    actual = expand(r_bam, {"DATA_DIR": ""})
    notes.append(f"prepare_data.sh 产出 → {expected}")
    notes.append(f"run.sh 默认读取    → {actual}")
    if expected != actual:
        problems.append(
            f"BAM 文件名不一致：数据准备脚本产出 {expected!r}，"
            f"而 run.sh 默认读 {actual!r}。"
            "默认路径下 run.sh 会直接 exit 2（缺少输入文件）—— 这就是曾经真实存在的 bug。"
        )
    return problems, notes


def self_test() -> int:
    """负向测试：既证明**原来的错值会被抓到**，也保护解析器本身。"""
    prep = PREPARE.read_text(encoding="utf-8")
    run_ok = RUN.read_text(encoding="utf-8")

    cases = [
        ("当前真实的两个脚本", prep, run_ok, True),
        ("回归：run.sh 原来的错 BAM（少 .30x）",
         prep, run_ok.replace("HG002.chr20.30x.bam", "HG002.chr20.bam"), False),
        ("回归：run.sh 原来的错区间（10–20 Mb）",
         prep, run_ok.replace("10000000-12000000", "10000000-20000000"), False),
        ("两个都错（历史原状）",
         prep, run_ok.replace("HG002.chr20.30x.bam", "HG002.chr20.bam")
                    .replace("10000000-12000000", "10000000-20000000"), False),
        # 解析器自保：改成 prepare_data.sh 单方面换覆盖率，也必须被抓到
        ("覆盖率变了（TARGET_COV 30→40）",
         prep.replace('TARGET_COV="${TARGET_COV:-30}"', 'TARGET_COV="${TARGET_COV:-40}"'),
         run_ok, False),
    ]
    ok = True
    for name, p, r, want_ok in cases:
        probs, _ = check(p, r)
        passed = (not probs) == want_ok
        if not passed:
            ok = False
        detail = "通过" if not probs else f"抓到 {len(probs)} 处"
        print(f"  {'✅' if passed else '❌'} {name}: {detail}，期望{'通过' if want_ok else '失败'}")
        if probs and not want_ok:
            for pr in probs:
                print(f"       └ {pr[:110]}")
    print("负向测试 " + ("全部通过（含 4 个必须失败的用例）" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="核对 run.sh 默认值与 prepare_data.sh 产物是否一致")
    ap.add_argument("--self-test", action="store_true", help="跑的负向测试，证明检查会失败")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not PREPARE.is_file() or not RUN.is_file():
        print(f"SKIP: 缺 {PREPARE} 或 {RUN}")
        return 0
    problems, notes = check(PREPARE.read_text(encoding="utf-8"),
                            RUN.read_text(encoding="utf-8"))
    for n in notes:
        print("  · " + n)
    if problems:
        print(f"❌ {len(problems)} 处不一致：")
        for pr in problems:
            print("   " + pr)
        return 1
    print("✅ run.sh 的默认值与 prepare_data.sh 的产物完全一致（区间 + BAM 文件名）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
