#!/usr/bin/env python3
"""检查**已跟踪的文本文件是否被写成了 CRLF**（而 HEAD 里是 LF）。

为什么需要这个检查 —— 这是本轮最难发现的一类缺陷
------------------------------------------------
`.gitattributes` 要求所有文本文件 `eol=lf`，HEAD 里也确实是 LF。
但**工作区**可能被某段代码写成 CRLF，而：

  · `core.autocrlf=true` 会在比较前把 CRLF 归一化成 LF
  · 于是 **`git status` 说 clean —— git 看不见这个污染**

实测（2026-09）：全仓有 **45 个已跟踪文件**被污染成 CRLF 而 git 报 clean。
更糟的是我修好之后，重新 pin T3 又把它变回 CRLF —— **污染源是
`record_image_digest.py` 自己的写入点**（已修）。

为什么要紧：`record_image_digest.py` 在**工作区字节**上算 `source_sha256`。
污染的工作区算出的 pin 与**干净检出（Linux / CI）不一致**，
于是**同一条 pin 在一台机器报 ✅、另一台报 ❌** ——
而这正是"可复现"这个核心主张的失败模式。

判据（**刻意不用 git status**）
------------------------------
逐个已跟踪文本文件比较：
  · 工作区字节里有没有 CRLF
  · `git show HEAD:<file>` 里有没有 CRLF
若前者有、后者无 → 污染。

用法
----
    python3 check_worktree_lf.py
    python3 check_worktree_lf.py --self-test
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: 视为"文本"的扩展名（二进制不参与）
TEXT_EXT = {".py", ".sh", ".md", ".json", ".jsonl", ".yml", ".yaml", ".txt",
            ".csv", ".toml", ".cfg", ".tsv", ".html", ".ps1"}
#: 明确不是文本的
BIN_EXT = {".gz", ".bam", ".bai", ".tbi", ".png", ".jpg", ".jpeg", ".webp",
           ".gif", ".zip", ".so", ".jar", ".cif"}


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True).stdout


def tracked_files() -> list[str]:
    return [x.decode("utf-8", "replace")
            for x in _git("ls-files", "-z").split(b"\x00") if x]


def audit() -> list[tuple[str, int]]:
    """返回 [(相对路径, CRLF 数)] —— 工作区有 CRLF 而 HEAD 无的。"""
    out: list[tuple[str, int]] = []
    for rel in tracked_files():
        p = ROOT / rel
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in BIN_EXT:
            continue
        if ext not in TEXT_EXT and p.name not in ("Dockerfile", "LICENSE", "NOTICE",
                                                  ".gitignore", ".gitattributes"):
            continue
        wt = p.read_bytes()
        n = wt.count(b"\r\n")
        if n == 0:
            continue
        head = _git("show", f"HEAD:{rel}")
        if head.count(b"\r\n") == 0 and head:
            out.append((rel, n))
    return out


def self_test() -> int:
    """负向测试：**证明这个检查会失败**。"""
    ok = True
    print("=== 工作区 LF 卫生自检 ===")

    probs = audit()
    cond = not probs
    ok = ok and cond
    print(f"  {'✅' if cond else '❌'} 当前工作区无污染（{len(probs)} 个）")
    for rel, n in probs[:3]:
        print(f"      CRLF={n}  {rel}")

    # 负向：造一个"工作区 CRLF 但 HEAD LF"的场景必须被识别。
    # 用临时文件模拟判据核心（不碰真实仓库）：
    def is_polluted(wt: bytes, head: bytes) -> bool:
        return wt.count(b"\r\n") > 0 and head.count(b"\r\n") == 0

    a = is_polluted(b"x\r\n", b"x\n")        # 污染
    b = is_polluted(b"x\n", b"x\n")          # 干净
    c = is_polluted(b"x\r\n", b"x\r\n")      # HEAD 本来就有 → 不算污染
    for label, cond2 in (("负向：工作区 CRLF + HEAD LF → 判为污染", a),
                         ("正向：两侧都 LF → 不报", not b),
                         ("正向：HEAD 本来 CRLF → 不报（不是本次引入的）", not c)):
        ok = ok and cond2
        print(f"  {'✅' if cond2 else '❌'} {label}")

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="工作区是否被写成 CRLF")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    probs = audit()
    if probs:
        print(f"❌ {len(probs)} 个已跟踪文本文件在工作区是 CRLF，而 HEAD 是 LF：")
        for rel, n in sorted(probs, key=lambda x: -x[1])[:20]:
            print(f"  CRLF={n:>6}  {rel}")
        print()
        print("⚠️ **`git status` 看不见这个污染** —— `core.autocrlf=true`")
        print("   会在比较前把 CRLF 归一化成 LF，于是它报 clean。")
        print()
        print("为什么要紧：`record_image_digest.py` 在**工作区字节**上算")
        print("   `source_sha256`。污染的工作区算出的 pin 与干净检出（CI/Linux）")
        print("   不一致 → **同一条 pin 一台机器报 ✅、另一台报 ❌**。")
        print()
        print("修法（`git checkout -- .` 不够，因为 git 认为没变）：")
        print("   rm <file> && git checkout -- <file>   ← 先删再检出")
        return 1

    if not args.quiet:
        n = len(tracked_files())
        print(f"✅ 已跟踪文本文件全为 LF（检查了 {n} 个跟踪文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
