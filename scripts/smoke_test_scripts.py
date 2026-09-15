#!/usr/bin/env python3
"""把仓库里**每一个** .py 都点一遍：能不能起来？有没有自检？

为什么要做这个
--------------
上一轮发现 `make_annotation_sheets.py` **根本不接受作答输入**，生成的标注表
没有可评的对象。它能坏那么久，是因为**没有任何东西在跑它**。

但那只靠人眼撞见。真正该问的是：**还有多少个脚本处在同样状态？**
——写了、文档引用了、但从来没被任何东西执行过。

本脚本对每个脚本跑 `--help`（无副作用的冒烟测试），并检查它有没有 `--self-test`：

  · 起不来（ImportError / 坏 argparse / 顶层就崩）→ ❌ **硬伤，必须修**
  · 能起来但没有自检 → ⚠️ 没有被验证过行为的入口（不一定是错，但要知道）
  · 能起来且有自检 → ✅ 最好的一类

`--help` 是刻意选的：它对**所有** argparse 脚本都安全、不写文件、不连网。
比起"假装导入一下"，它真的会走完参数解析那一段，能抓到改参数时漏改的引用。

用法：
    python3 smoke_test_scripts.py
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent          # bio-eval/

SKIP_PARTS = {"__pycache__", "_artifacts", "_cache", "_data", "_work",
              "_work_backup", "judge_out", "judge_out_run1", "judge_out_run2",
              "manip_out_run1", "manip_out_run2", "judge_outputs", "sources",
              "sources_trunc20000", "_fixtures", "alternate"}


def scripts() -> list[Path]:
    out = []
    for f in ROOT.rglob("*.py"):
        if any(p in SKIP_PARTS for p in f.parts):
            continue
        out.append(f)
    return sorted(out)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="全仓脚本冒烟测试")
    ap.add_argument("--show-ok", action="store_true", help="连通过的也逐行列出来")
    args = ap.parse_args(argv)

    files = scripts()
    print(f"冒烟测试 {len(files)} 个脚本（跑 --help，无副作用）\n")

    crashed: list[tuple[str, str]] = []
    platform_only: list[str] = []
    no_self: list[str] = []
    has_self: list[str] = []
    rows: list[tuple[str, str, str]] = []

    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        src = f.read_text(encoding="utf-8", errors="replace")
        self_test = bool(re.search(r'add_argument\(\s*["\']--self-test', src))
        try:
            p = subprocess.run([sys.executable, str(f), "--help"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=30, cwd=str(f.parent))
            out = ((p.stdout or "") + (p.stderr or "")).strip()
        except subprocess.TimeoutExpired:
            crashed.append((rel, "超时 >30s —— `--help` 不该卡住，可能有顶层副作用"))
            rows.append((rel, "❌ 超时", "?"))
            continue

        if p.returncode != 0:
            lines = [l for l in out.splitlines() if l.strip()]
            why = lines[-1][:110] if lines else f"退出码 {p.returncode}"
            # ⚠️ 平台专属模块（resource/pwd/fcntl/grp/termios 是 Unix-only）
            #    在 Windows 上必然 ImportError。这类脚本**本来就是给容器跑的**，
            #    不是硬伤，但必须**明说"本机无法验证"**，不能默默算通过。
            if "ModuleNotFoundError" in out and any(
                    m in out for m in ("resource", "pwd", "fcntl", "grp", "termios")):
                rows.append((rel, "⚠️ 平台专属（Unix-only）", "有" if self_test else "无"))
                platform_only.append(rel)
                continue
            crashed.append((rel, why))
            rows.append((rel, f"❌ 退出码 {p.returncode}", "有" if self_test else "无"))
        else:
            if self_test:
                has_self.append(rel)
            else:
                no_self.append(rel)
            rows.append((rel, "✅", "有" if self_test else "无"))

    if args.show_ok or crashed:
        w = max(len(r[0]) for r in rows)
        print(f"{'脚本'.ljust(w)}  状态        自检")
        print("-" * (w + 20))
        for rel, st, stt in rows:
            if args.show_ok or st.startswith("❌"):
                print(f"{rel.ljust(w)}  {st:<11}{stt}")

    print()
    print("=" * 70)
    print(f"能起来 {len(files) - len(crashed) - len(platform_only)}/{len(files)}"
          + (f"（另有 {len(platform_only)} 个平台专属，本机无法验证）" if platform_only else ""))
    for r in platform_only:
        print(f"   ⚠️ {r} —— Unix-only，需在容器里验证")
    print(f"  其中有 --self-test：{len(has_self)}")
    print(f"  能起来但无自检：    {len(no_self)}")
    if crashed:
        print(f"\n❌ **{len(crashed)} 个脚本连 --help 都跑不起来**：")
        for rel, why in crashed:
            print(f"   {rel}")
            print(f"      └ {why}")
        print("\n   这些是硬伤：文档可能引用它们，而它们一执行就崩。")
        return 1

    print("\n✅ 全部脚本都能起来")
    if no_self:
        print(f"\n⚠️ 以下 {len(no_self)} 个没有 --self-test —— 它们的行为没有被自动验证过。")
        print("   不一定是错，但要注意：上一轮那个坏掉的标注表生成器就属于这一类。")
        for r in no_self[:20]:
            print(f"   · {r}")
        if len(no_self) > 20:
            print(f"   … 另有 {len(no_self) - 20} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
