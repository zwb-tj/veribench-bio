#!/usr/bin/env python3
"""检查每个 Dockerfile 里的 `apt-get install` 是否都被重试包裹。

为什么单独做这个
----------------
2026-09 实测：`docker build --no-cache` 在当前网络下**会失败** ——
`deb.debian.org` 对多个 .deb 持续返回 502，apt 自带的 `Acquire::Retries=3` 没扛住。
于是给 apt 调用加了一层有界外层重试。

**但当时我只修了 T1。** T2 有**两个** apt 块（`gate` 与最终镜像两个阶段），
一个都没加。这正是本项目反复出现的那个模式：**同一样东西写在多处，改一处漏一处。**

（同类前科：schema 的 `required` vs 审计器的 `REQUIRED_FIELDS`；
"刻意不发布"清单同时写在两个工具里。**同一个事实写两遍，迟早会分叉。**）

理想做法是抽成一份共享脚本，但 Docker 的构建上下文是各任务的目录，
共享会牵动 `-f`/上下文路径，改动面比收益大。所以退一步：
**保留内联副本，用这个检查强制它们不许分叉。**

判据（不要求包列表相同，只要求健壮性一致）：
  · 每个 Dockerfile 里 `apt-get install` 的出现次数
    必须等于重试标记 `APT_RETRY_V1` 的出现次数
  · 且每处 `apt-get install` 都要有对应的循环结构

用法：
    python3 check_dockerfile_apt.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                     # bio-eval/
MARKER = "APT_RETRY_V1"


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    dfs = sorted(p for p in ROOT.rglob("Dockerfile")
                 if "__pycache__" not in p.parts)
    print(f"检查 {len(dfs)} 个 Dockerfile\n")

    problems: list[str] = []
    total_installs = 0
    for df in dfs:
        rel = df.relative_to(ROOT).as_posix()
        text = df.read_text(encoding="utf-8")
        n_install = len(re.findall(r"apt-get install", text))
        n_marker = text.count(MARKER)
        n_loop = len(re.findall(r"for i in 1 2 3", text))
        total_installs += n_install

        status = "✅" if (n_install == n_marker == n_loop or n_install == 0) else "❌"
        print(f"  {status} {rel}")
        print(f"      apt-get install × {n_install} · {MARKER} × {n_marker} · 重试循环 × {n_loop}")

        if n_install == 0:
            continue
        if n_marker != n_install:
            problems.append(
                f"{rel}: {n_install} 处 apt-get install，但只有 {n_marker} 处带 {MARKER} "
                f"—— **有 apt 调用没被重试包裹**（上游 502 时会直接构建失败）")
        if n_loop != n_install:
            problems.append(
                f"{rel}: 重试循环 {n_loop} 个，apt 调用 {n_install} 个 —— 数目对不上")

    print()
    if problems:
        print(f"❌ {len(problems)} 个问题：")
        for p in problems:
            print(f"   {p}")
        print()
        print("   上下文：T1 只修了一处、T2 的两处漏了 —— 这个检查就是为了防这种事。")
        return 1
    print(f"✅ 全部 {total_installs} 处 apt-get install 都被有界重试包裹，且标记数一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
