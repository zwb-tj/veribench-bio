#!/usr/bin/env python3
"""检查**写文本文件的代码是否指定了 `newline=""`** —— 跨平台可复现性的一部分。

为什么需要这个检查
------------------
实测（2026-09）：`Path.write_text()` / `open("w")` 默认 `newline=None`，
Python 在 **Windows 把 `\\n` 翻译成 `\\r\\n`，在 Linux 不翻译**。
于是**同一份代码在两平台产出不同字节**。

这直接打击本项目的核心主张（"每一步都能被你自己验一遍"）：
  · `tasks/T2/data/items.jsonl` 与 `tasks/T3/data/items.jsonl` 都是
    `record_image_digest.py` 的**构建输入**
  · 它们含 CRLF 还是 LF，会改变 `source_sha256`
  · 实测：T2 的 CRLF 版算 `400fe720…`、LF 版算 `be5da56d…` —— **同一条 pin
    记录在 Windows 报 ✅、在 Linux 报 ❌**

更麻烦的是 **CI 抓不到**：生成物在 clone 里不存在，`--check-all` 会 SKIP。
只有真正按 README 跑取数 + 构建镜像的人才会撞上 —— 而那正是任务要求的操作。

判据
----
不是"每个写文件都必须加"（那会产生大量噪音），而是：
**写出来的东西会被哈希、或会被跨机比对的**，必须加。
本检查维护一份**明确清单**（`RETURNS_HASHED`），并验证：
  ① 清单里的脚本确实带了 `newline=""`
  ② 清单本身没有过期（文件还在）

用法
----
    python3 check_newline_hygiene.py
    python3 check_newline_hygiene.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: 这些脚本写出的产物**会被哈希或跨机比对**，必须 `newline=""`。
#: 每条都要写清楚"为什么它在清单里" —— 理由为空等于把检查关掉。
RETURNS_HASHED: dict[str, str] = {
    "tasks/T2/data/build_t2.py":
        "写 T2 的 items/truth/audit；items.jsonl 是镜像 pin 的构建输入",
    "tasks/T3/data/fetch_mmcif.py":
        "写 T3 的 items/truth；items.jsonl 是镜像 pin 的构建输入",
    "scripts/build_master_ledger.py":
        "写 ledger/items.jsonl；台账被 audit_licenses 与 CI 逐字节比较",
    "scripts/record_image_digest.py":
        "写 IMAGE_DIGEST.json（**已提交文件**，.gitattributes 要求 LF）；"
        "实测：不加 newline 时它每次运行都会把工作区污染成 CRLF，"
        "而 autocrlf 让 git status 看不见",
    "rubric/scripts/build_judge_inputs.py":
        "写 judge 输入；跨机器复现时要比对",
    "rubric/scripts/build_manip_inputs.py":
        "写操纵检验输入；跨机器复现时要比对",
    "rubric/scripts/make_annotation_sheets.py":
        "写 ann_*.jsonl / _blind_mapping.json / ann_*_sheet.md —— "
        "**都是已提交文件**。实测：不加 newline 时一条 make_pilot.py 调用链"
        "污染 7 个文件，累积后全仓 31 个文件变成工作区 CRLF（而 git status 看不见）",
    "rubric/scripts/make_pilot.py":
        "写 annotation/pilot/items.jsonl 与 answers.jsonl（**已提交文件**）；"
        "它还会调用 make_annotation_sheets.py，两者都曾造成污染",
}

#: 允许的写法（任一命中即算合规）。
#:
#: ⚠️ 匹配必须**跨越换行**：`write_text()` 常写成多行
#: （`(out / "items.jsonl").write_text(\n  ...,\n  encoding="utf-8", newline="")`）。
#: 第一版用 `[^)]*` 不跨行，于是**把已经修好的文件误报成不合规** ——
#: 而误报会让人把检查关掉（本项目反复强调：误报比漏报更糟）。
#: 这里改用 `[\s\S]*?` 并且**限定在同一次调用内**（到 `)` 为止的最小匹配）。
OK_PATTERNS = [
    re.compile(r'\.write_text\([\s\S]{0,400}?newline\s*=\s*["\']{2}[\s\S]{0,80}?\)'),
    re.compile(r'open\([\s\S]{0,400}?newline\s*=\s*["\']{2}[\s\S]{0,80}?\)'),
]


def _writes_text(src: str) -> bool:
    return ("write_text(" in src) or bool(re.search(r'open\([^)]*["\']w["\']', src))


def check() -> list[str]:
    probs: list[str] = []
    for rel, why in RETURNS_HASHED.items():
        p = ROOT / rel
        if not p.is_file():
            probs.append(f"{rel} 不存在（清单过期？理由：{why}）")
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        if not _writes_text(src):
            probs.append(f"{rel} 已不写文本文件（清单过期？理由：{why}）")
            continue
        if not any(pat.search(src) for pat in OK_PATTERNS):
            probs.append(
                f"{rel}: 写文本文件但**没有 newline=\"\"** —— "
                f"在 Windows 会写出 CRLF、Linux 写 LF，"
                f"两平台字节不同（{why}）")
    return probs


def self_test() -> int:
    """负向测试：**证明这个检查会失败**，不是恒真。"""
    ok = True
    print("=== newline 卫生自检 ===")

    probs = check()
    cond = not probs
    ok = ok and cond
    print(f"  {'✅' if cond else '❌'} 当前仓库全部合规")
    for x in probs[:3]:
        print(f"      {x}")

    # 负向：一个"写文件但没 newline"的样例必须被识别
    bad = 'def w(p):\n    p.write_text("x", encoding="utf-8")\n'
    good = 'def w(p):\n    p.write_text("x", encoding="utf-8", newline="")\n'
    bad_flagged = not any(pat.search(bad) for pat in OK_PATTERNS)
    good_passes = any(pat.search(good) for pat in OK_PATTERNS)
    for label, c in (("负向：无 newline 会被识别为不合规", bad_flagged),
                     ("正向：有 newline 视为合规", good_passes)):
        ok = ok and c
        print(f"  {'✅' if c else '❌'} {label}")

    # 负向：清单里的文件若真的缺 newline，必须被抓
    fake_rel = "tasks/T3/data/_nonexistent_probe.py"
    RETURNS_HASHED[fake_rel] = "自检用"
    try:
        got = check()
        caught = any(fake_rel in x for x in got)
    finally:
        RETURNS_HASHED.pop(fake_rel, None)
    ok = ok and caught
    print(f"  {'✅' if caught else '❌'} 负向：清单里不存在的文件会被抓")

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="写文本文件是否指定 newline")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    probs = check()
    if probs:
        print("❌ 写文本文件的地方缺少 `newline=\"\"`：")
        for x in probs:
            print(f"  · {x}")
        print()
        print("为什么严重：这些产物**会被哈希或跨机比对**。")
        print("Windows 写 CRLF、Linux 写 LF → 同一份数据字节不同 →")
        print("**同一条 pin 在一台机器报 ✅、另一台报 ❌**。")
        print("而 CI 抓不到（生成物在 clone 里不存在，会 SKIP）。")
        print()
        print("修法：`write_text(..., newline=\"\")` 或 `open(..., newline=\"\")`。")
        return 1

    if not args.quiet:
        print(f"✅ {len(RETURNS_HASHED)} 个会产生哈希产物的脚本都指定了 newline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
