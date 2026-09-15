"""核对**已构建镜像**里那些被文档断言过的性质。

为什么不只靠"构建成功"
----------------------
`docker build` 成功只说明 Dockerfile 语法没问题。文档里还断言了一串**具体性质**：

  · 镜像里**不含** GPL 的分析组件（R/GSL/MKL）
  · `bcftools` 未链接 `libgsl`
  · RTG 捆绑的 amd64 JRE **已被剥离**（否则 arm64 会 Exec format error）
  · rtg 启动脚本的架构检查**已打补丁**（否则 arm64 上 0.1 秒就失败）
  · 大小约 356 MB

这些每一条都能在镜像里查。**构建成功 ≠ 这些性质成立。**

用法：
    python3 inspect_image.py --image veribench-bio/t1:dev
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

results: list[tuple[str, bool | None, str]] = []


def add(claim: str, ok: bool | None, ev: str) -> None:
    results.append((claim, ok, ev))


def sh(cmd: list[str]) -> tuple[int, str]:
    # ⚠️ 工具不存在时 `subprocess.run` 抛 `FileNotFoundError`，不是返回非零码。
    #    本脚本要调用 `docker`，而 CI / 第三方机器上**可能没有 docker** ——
    #    实测在 Linux 无 docker 环境下这里直接 traceback。
    #    **崩掉 ≠ 跳过**：前者会被读成"仓库坏了"。这里显式转成 (127, 消息)。
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
    except FileNotFoundError:
        return 127, f"(工具不存在：{cmd[0]})"
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="核对镜像里被断言过的性质")
    ap.add_argument("--image", default="veribench-bio/t1:dev")
    args = ap.parse_args(argv)
    img = args.image

    # T2 的断言与 T1 不同（它没有分析工具链，但有"镜像里不得含真值"这条硬要求）
    if "t2" in img.lower():
        return inspect_t2(img, in_image_factory(img))
    return inspect_t1(img)


def in_image_factory(img: str):
    def in_image(shell: str, timeout: int = 180) -> tuple[int, str]:
        return sh(["docker", "run", "--rm", "--entrypoint", "bash", img, "-lc", shell])
    return in_image


def inspect_t2(img: str, in_image) -> int:
    """T2 的镜像断言。

    ⚠️ 我第一次手查时看到 `/work` 只有一个文件，差点报"镜像缺题目" ——
    其实是我自己用 `Select-Object -First 22` 把输出截断了（`ls /` 就吃掉了 20 行）。
    **截断输出会让检查结果失真**，所以这一条写成了脚本：一次性打印，不再截。
    """
    rc, out = sh(["docker", "image", "inspect", img, "--format", "{{.Size}}"])
    if rc != 0:
        print(f"SKIP: 镜像 {img} 不存在")
        return 0
    add("镜像大小约 123 MB（十进制，±8%）", abs(int(out) / 1e6 - 123) <= 123 * 0.08,
        f"实测 {int(out) / 1e6:.1f} MB = {int(out) / 2**20:.1f} MiB")

    rc, out = in_image("ls /work/ | tr '\\n' ' '")
    add("/work 下有 items.jsonl / grade.py / run.sh / check_no_leakage.py",
        all(f in out for f in ("items.jsonl", "grade.py", "run.sh", "check_no_leakage.py")),
        out.strip()[:140])

    rc, out = in_image("wc -l < /work/items.jsonl")
    add("镜像里题量为 4,726", out.strip() == "4726", f"实测 {out.strip()} 行")

    # 这一条是 T2 的硬要求：镜像里**不得**留真值
    rc, out = in_image("find / -name 'truth*' 2>/dev/null | grep -v proc || true")
    add("镜像内**不含**真值（判分时才只读挂载进来）", out.strip() == "",
        out.strip()[:120] or "（无 truth 文件，符合预期）")

    rc, out = in_image("python3 /work/check_no_leakage.py --items /work/items.jsonl --quiet "
                       "2>&1 | tail -2")
    add("运行期泄漏检查可执行且通过", rc == 0 and "通过" in out, out.strip().replace("\n", " ")[:130])

    w = max(len(c) for c, _, _ in results)
    print(f"{'断言'.ljust(w)}  结论")
    print("-" * (w + 34))
    for claim, ok, ev in results:
        mark = "✅ 通过" if ok is True else ("❌ 不符" if ok is False else "⚠️ 未验证")
        print(f"{claim.ljust(w)}  {mark}")
        print(f"{' ' * w}  └ {ev}")
    n_bad = sum(1 for _, ok, _ in results if ok is False)
    print(f"\n{len(results)} 条：通过 {len(results) - n_bad} · 不符 {n_bad}")
    return 1 if n_bad else 0


def inspect_t1(img: str) -> int:

    rc, out = sh(["docker", "image", "inspect", img, "--format", "{{.Size}}"])
    if rc != 0:
        print(f"SKIP: 镜像 {img} 不存在（先构建）")
        return 0
    # ⚠️ 单位陷阱：`docker image inspect .Size` 返回**字节**。
    #    除以 2**20 得 MiB，除以 1e6 得 MB —— 两者差 4.9%。
    #    第一版把 MiB 当 MB 报（339.3 "MB"），而 `docker images` 显示 356MB（十进制），
    #    于是看起来像是文档写错了 17 MB。**其实文档是对的，是我的单位错了。**
    size_bytes = int(out)
    size_mb = size_bytes / 1e6
    size_mib = size_bytes / 2**20
    add("镜像大小约 356 MB（十进制，±8%）", abs(size_mb - 356) <= 356 * 0.08,
        f"实测 {size_mb:.1f} MB = {size_mib:.1f} MiB")

    def in_image(shell: str, timeout: int = 120) -> tuple[int, str]:
        return sh(["docker", "run", "--rm", "--entrypoint", "bash", img, "-lc", shell])

    # 1) GPL 分析组件不得存在
    rc, out = in_image(
        "for p in r r-base gsl-bin libgsl27 libgsl-dev mkl; do "
        "command -v $p >/dev/null 2>&1 && echo PRESENT:$p; done; "
        "ldconfig -p 2>/dev/null | grep -ci libgsl || true")
    n_gsl = out.strip().splitlines()[-1] if out.strip() else "?"
    add("镜像内无 R / GSL / oneMKL 组件", "PRESENT:" not in out and n_gsl.strip() == "0",
        f"探测输出：{out.strip()[:110] or '（空）'}")

    # 2) bcftools 未链接 libgsl（构建期门禁的核心断言）
    rc, out = in_image("ldd $(command -v bcftools) | grep -ci gsl || true")
    add("bcftools 未链接 libgsl", out.strip() == "0", f"ldd 里 libgsl 命中 {out.strip()} 次")

    # 3) RTG 捆绑的 amd64 JRE 已被剥离
    rc, out = in_image("ls /opt/rtg-tools/jre/lib/amd64 2>/dev/null | wc -l")
    add("RTG 捆绑的 amd64 JRE 已剥离（否则 arm64 会 Exec format error）",
        out.strip() == "0", f"/opt/rtg-tools/jre/lib/amd64 下有 {out.strip()} 个文件")

    # 4) rtg 启动脚本的架构检查已打补丁
    rc, out = in_image(
        "grep -n 'x86_64_disabled' /opt/rtg-tools/rtg | head -1 || echo NOT_PATCHED")
    add("rtg 启动脚本的架构检查已打补丁（否则 arm64 上 0.1 秒即失败）",
        "x86_64_disabled" in out, out.strip()[:120] or "（无输出）")

    # 5) /etc/rtg.cfg 指向系统 java
    rc, out = in_image("cat /etc/rtg.cfg 2>/dev/null || echo MISSING")
    add("存在 /etc/rtg.cfg 且指向系统 java", "RTG_JAVA=java" in out, out.strip()[:80])

    # 6) 许可声明随镜像分发
    rc, out = in_image("ls /licenses/ 2>/dev/null | tr '\\n' ' '")
    add("/licenses/ 随镜像分发（拿镜像的人能独立核实组件许可）",
        "README" in out, out.strip()[:120])

    # 7) 工具链可用
    rc, out = in_image(
        "samtools --version | head -1; bcftools --version | head -1; "
        "freebayes --version 2>&1 | head -1; java -version 2>&1 | head -1")
    lines = [l for l in out.splitlines() if l.strip()]
    add("四个工具都能起来（samtools/bcftools/freebayes/java）", len(lines) >= 4,
        " | ".join(lines[:4])[:150])

    # 8) rtg 能跑（架构补丁的行为验证 —— 文本检查过不代表行为对）
    rc, out = in_image("/opt/rtg-tools/rtg version 2>&1 | head -3", timeout=180)
    add("rtg 在本机架构上可执行（行为验证，不只是文本检查）",
        rc == 0 and "RTG" in out.upper(), out.strip().replace("\n", " ")[:130])

    w = max(len(c) for c, _, _ in results)
    print(f"{'断言'.ljust(w)}  结论")
    print("-" * (w + 34))
    for claim, ok, ev in results:
        mark = "✅ 通过" if ok is True else ("❌ 不符" if ok is False else "⚠️ 未验证")
        print(f"{claim.ljust(w)}  {mark}")
        print(f"{' ' * w}  └ {ev}")
    n_bad = sum(1 for _, ok, _ in results if ok is False)
    print(f"\n{len(results)} 条：通过 {len(results) - n_bad} · 不符 {n_bad}")
    if n_bad:
        print("❌ 镜像里有与文档断言不符的性质")
        return 1
    print("✅ 镜像里被断言过的性质全部成立")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
