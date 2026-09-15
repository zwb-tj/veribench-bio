#!/usr/bin/env python3
"""核对 `LICENSE` 里的 Apache-2.0 正文是否与**官方源逐行一致**。

为什么要专门查这个
------------------
一份**手抄错的**法律文本比没有更糟：它看起来权威，但条款可能被改动或漏掉。
本项目写 LICENSE 时是从 https://www.apache.org/licenses/LICENSE-2.0.txt 取的，
**不是凭记忆敲的** —— 但"我当时是从哪拿的"不是证据，**比对结果才是**。

所以这个脚本把仓库里的正文抓回来跟官方源逐行比。用法：

    python3 verify_license_text.py            # 需要联网
    python3 verify_license_text.py --offline  # 只查结构（行数、首尾、关键条款）

离线时**明确报"未验证"**，不假装通过 —— 这正是本项目对待所有不可核实项的做法。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CANON_URL = "https://www.apache.org/licenses/LICENSE-2.0.txt"
MARKER = "END OF TERMS AND CONDITIONS"

# 正文里必须出现的几个关键短语（离线抽查用；不是为了替代全文比对）
KEY_PHRASES = [
    "Apache License",
    "Version 2.0, January 2004",
    "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
    "Grant of Patent License",
    "Redistribution.",
    "Disclaimer of Warranty",
    "Limitation of Liability",
    "END OF TERMS AND CONDITIONS",
]


def norm(s: str) -> list[str]:
    return [l.rstrip() for l in s.strip().splitlines()]


def offline_check(text: str) -> int:
    body = text[: text.index(MARKER) + len(MARKER)] if MARKER in text else text
    missing = [p for p in KEY_PHRASES if p not in body]
    n = len(norm(body))
    digest = hashlib.sha256(norm(body)[0].encode()).hexdigest()[:12]
    print(f"离线结构检查：Apache-2.0 正文 {n} 行（官方源为 176 行）")
    print(f"  首行指纹 {digest}")
    if missing:
        print(f"  ❌ 缺关键短语：{missing}")
        return 1
    if n != 176:
        print(f"  ❌ 行数不是 176（官方源为 176）—— 正文可能被改动或截断")
        return 1
    print("  ✅ 关键短语齐全、行数符合")
    print("  ⚠️ **未做逐行比对（本次离线）** —— 这只是弱检查，不等于与官方一致。")
    return 0


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="核对 LICENSE 正文")
    ap.add_argument("--offline", action="store_true", help="跳过联网逐行比对")
    args = ap.parse_args()

    lic = ROOT / "LICENSE"
    if not lic.is_file():
        print("❌ 找不到 LICENSE")
        return 1
    text = lic.read_text(encoding="utf-8")
    if MARKER not in text:
        print(f"❌ LICENSE 里找不到 {MARKER!r} —— 正文不完整")
        return 1

    if args.offline:
        return offline_check(text)

    try:
        req = urllib.request.Request(CANON_URL, headers={"User-Agent": "veribench-bio/verify"})
        canon = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 无法访问官方源（{type(exc).__name__}: {exc}）—— 退回离线检查")
        return offline_check(text)

    a = norm(canon)
    ai = next((i for i, l in enumerate(a) if MARKER in l), None)
    if ai is None:
        print("❌ 官方源里找不到结束标记，无法比对")
        return 1
    a = a[: ai + 1]
    b = norm(text[: text.index(MARKER) + len(MARKER)])

    print(f"官方源 {len(a)} 行　本仓库 {len(b)} 行")
    if a == b:
        print("✅ **逐行完全一致** —— 正文与 apache.org 官方源相同")
        return 0
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            print(f"❌ 第 {i + 1} 行不同：")
            print(f"   官方  : {a[i]!r}")
            print(f"   本仓库: {b[i]!r}")
            return 1
    print(f"❌ 行数不同：官方 {len(a)} vs 本仓库 {len(b)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
