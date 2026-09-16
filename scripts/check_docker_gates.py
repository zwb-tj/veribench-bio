#!/usr/bin/env python3
"""检查：Dockerfile 里声明的**门禁阶段是否真的会被构建**。

为什么需要这个检查 —— 本轮最严重的一类缺陷
------------------------------------------
实测（2026-09）：**Docker 不构建未被引用的中间阶段。**
一个 `FROM ... AS gate` 后面写了再多 `RUN` 检查，只要最终阶段
**没有引用它**（如 `COPY --from=gate ...`），Docker 就会**整个跳过该阶段** ——
所有检查静默不执行，而**构建照样成功**。

证据：往 `truth.jsonl` 注入一个错误值后，构建仍然 `exit 0`。
加上 `COPY --from=gate` 之后，同一个注入立刻让构建 `exit 1`。

而我在 README / DATACARD / 验证报告里都写着"构建期执行门禁" ——
**那些断言当时是假的**（T3 与 T4 都中招；T2 因为恰好引用了 gate 而幸免）。

判据（刻意不问"有没有写检查"，而是问"会不会被执行"）
--------------------------------------------------
对每个 `tasks/*/Dockerfile`：
  ① 若声明了 `AS gate`（或任何非最后的命名阶段）→ 必须有人 `--from=<该名>` 引用它
  ② 只声明不引用 → **失败**（那是装饰性门禁）
另外检查最终阶段是否有 `FROM <named-stage>`（另一种合法引用方式）。

用法
----
    python3 check_docker_gates.py
    python3 check_docker_gates.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def stages(dockerfile: str) -> list[tuple[int, str | None]]:
    """返回 [(行号, 阶段名或 None)]，按出现顺序。`AS name` 才有名字。"""
    out: list[tuple[int, str | None]] = []
    for i, line in enumerate(dockerfile.splitlines(), 1):
        m = re.match(r"\s*FROM\s+\S+(?:\s+AS\s+(\w+))?\s*$", line, re.I)
        if m:
            out.append((i, m.group(1)))
    return out


def audit() -> list[str]:
    probs: list[str] = []
    for p in sorted(ROOT.glob("tasks/*/Dockerfile")):
        text = p.read_text(encoding="utf-8", errors="replace")
        st = stages(text)
        if len(st) < 2:
            continue                                  # 单阶段，无此问题
        named = [(ln, n) for ln, n in st[:-1] if n]   # 除最后一个外的命名阶段
        if not named:
            continue
        rel = p.relative_to(ROOT).as_posix()
        for ln, name in named:
            # 被 --from=<name> 引用？
            if re.search(rf"--from={re.escape(name)}\b", text, re.I):
                continue
            # 或被 `FROM <name>` 继承？
            if re.search(rf"^\s*FROM\s+{re.escape(name)}\b", text, re.I | re.M):
                continue
            probs.append(
                f"{rel}:{ln} 阶段 `{name}` **声明了但没被任何人引用** —— "
                f"Docker 不会构建它，里面的门禁全部不会执行（而构建照样成功）")
    return probs


def self_test() -> int:
    """负向测试：**证明这个检查会失败**。"""
    ok = True
    print("=== Docker 门禁可达性自检 ===")

    def fake(text: str) -> list[tuple[int, str | None]]:
        return stages(text)

    # ① 声明未引用 → 必须被判为问题
    bad = (
        "FROM python:3.12-slim AS gate\n"
        "RUN echo check && exit 1\n"
        "\n"
        "FROM python:3.12-slim\n"
        "RUN echo final\n"
    )
    st = fake(bad)
    named = [(ln, n) for ln, n in st[:-1] if n]
    caught = bool(named) and not re.search(r"--from=gate", bad, re.I)
    ok = ok and caught
    print(f"  {'✅' if caught else '❌'} 负向：声明 `AS gate` 但不引用 → 会被抓")

    # ② 有 --from → 不算问题
    good = (
        "FROM python:3.12-slim AS gate\n"
        "RUN echo check\n"
        "\n"
        "FROM python:3.12-slim\n"
        "COPY --from=gate /x /y\n"
    )
    clean = bool(re.search(r"--from=gate", good, re.I))
    ok = ok and clean
    print(f"  {'✅' if clean else '❌'} 正向：`COPY --from=gate` → 视为可执行")

    # ③ FROM <named> 继承也算引用
    inherit = (
        "FROM python:3.12-slim AS base\n"
        "RUN echo a\n"
        "\n"
        "FROM base\n"
        "RUN echo b\n"
    )
    ok3 = bool(re.search(r"^\s*FROM\s+base\b", inherit, re.I | re.M))
    ok = ok and ok3
    print(f"  {'✅' if ok3 else '❌'} 正向：`FROM base` 继承 → 视为可执行")

    # ④ 真实仓库当前状态
    probs = audit()
    cond = not probs
    ok = ok and cond
    print(f"  {'✅' if cond else '❌'} 当前仓库所有 gate 阶段都可执行")
    for x in probs[:3]:
        print(f"      {x}")

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="Dockerfile 门禁阶段是否会被构建")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    probs = audit()
    if probs:
        print("❌ 有门禁阶段不会被构建（= 那些检查从不执行）：")
        for x in probs:
            print(f"  · {x}")
        print()
        print("为什么严重：**没有任何东西会报警** —— 构建成功、镜像正常、")
        print("CI 也绿，只有「门禁」这件事是假的。")
        print("实测：往 truth.jsonl 注入错误值后构建仍 exit 0；")
        print("加上 `COPY --from=<stage>` 之后立刻 exit 1。")
        print()
        print("修法：让最终阶段引用它，例如")
        print("  在 gate 末尾写一个标记文件，然后最终阶段")
        print("  `COPY --from=gate /gate/.gate-passed /work/`")
        return 1

    if not args.quiet:
        n = len(list(ROOT.glob("tasks/*/Dockerfile")))
        print(f"✅ {n} 个 Dockerfile 的门禁阶段都可达（会被真正构建）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
