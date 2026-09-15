#!/usr/bin/env python3
"""核对 `NOTICE` 的 [A]/[B] 分块是否**名副其实**。

为什么需要它
------------
`NOTICE` 把第三方组件分成两块：

  [A] VERIFIED        —— 上游 LICENSE 原文「读过了」，许可从原文确认
  [B] NOT VERIFIED    —— 许可取自发行版包元数据，「没亲手打开上游 LICENSE」

这个划分本身就是**诚实性的表达**：它承认"我验到什么程度"。
所以它必须可核对 —— 否则 [A] 会随着时间变成一句自我表扬：
有人把组件从 [B] 挪到 [A]，却没真去读上游原文。

三类检查：
  1. **结构**：两个块都存在，[A] 非空。
  2. **证据**：凡列在 [A] 的组件，条目里必须给出**上游 LICENSE 的 URL**
     （"读过了"至少要能指出去哪读的）。这条正是本次修复的由来：
     samtools/bcftools/htslib 原先在 [B]，2026-09 真的读了三个 tag 的
     LICENSE 原文后才移到 [A]，并附上 URL。
  3. **不许两头都列**：同一个组件不能同时出现在 [A] 和 [B]。
  4. **覆盖**：Dockerfile 里装的分析工具，必须在 NOTICE 里被提到过：
     samtools / bcftools / tabix / freebayes / default-jre-headless。
     漏掉一个就等于"装了但没声明"。

用法
----
    python3 verify_notice.py
    python3 verify_notice.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NOTICE = ROOT / "NOTICE"
DOCKERFILE = ROOT / "tasks" / "T1" / "Dockerfile"

#: Dockerfile 装了、因而必须在 NOTICE 里出现的组件（名字 → NOTICE 里的匹配式）
REQUIRED_COMPONENTS = {
    "samtools": r"samtools",
    "bcftools": r"bcftools",
    "tabix/htslib": r"tabix|htslib",
    "freebayes": r"freebayes",
    "openjdk": r"OpenJDK",
}

#: [A] 块里的条目必须带一个上游 LICENSE 链接（"读过了"要有出处）
RE_UPSTREAM_URL = re.compile(r"https?://\S+", re.I)


def split_blocks(text: str) -> tuple[str, str, list[str]]:
    """返回 (A 段, B 段, 问题)。

    ⚠️ [B] 段必须**止于** `DELIBERATELY NOT INCLUDED` 表头 —— 那之后是
    "我们刻意不打包的东西"（GATK4 / libgsl / dbNSFP…），它们**不在镜像里**，
    不是"未逐项核验的组件"。第一版一路切到文件尾，把它们算了进来。
    """
    problems: list[str] = []
    m_a = re.search(r"^\[A\][^\n]*\n=+\n", text, re.M)
    m_b = re.search(r"^\[B\][^\n]*\n=+\n", text, re.M)
    if not m_a:
        return "", "", ["找不到 [A] 块的表头（`[A] ...` 后跟一行 `===`）"]
    if not m_b:
        return "", "", ["找不到 [B] 块的表头"]
    if m_b.start() <= m_a.end():
        return "", "", ["[B] 块出现在 [A] 之前，无法切分"]
    end = len(text)
    m_end = re.search(r"^DELIBERATELY NOT INCLUDED\s*$", text[m_b.end():], re.M)
    if m_end:
        end = m_b.end() + m_end.start()
    return text[m_a.end():m_b.start()], text[m_b.end():end], problems


def entries(block: str) -> list[str]:
    """把一段按「顶格非空行」切成条目（条目内部的缩进行属于上一条）。

    ⚠️ 必须先滤掉 `====` 分隔线与块尾的说明文字 —— 它们顶格、但不是组件条目。
    （第一版没滤，于是分隔线被当成一个"组件"，还因为 [A]/[B] 里各有一条
      而被报成"同一组件两头都列"。这是 --self-test 抓出来的。）
    """
    out: list[list[str]] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"=+", stripped):        # 分隔线
            continue
        # 块尾的说明段落（以 "Run this" / "If a claim" 之类开头）不算组件条目
        if stripped.startswith(("Run this", "If a claim", "=====")):
            continue
        if line[0] not in " \t":                 # 顶格 = 新条目
            out.append([line])
        elif out:                                # 缩进 = 上一条的续行
            out[-1].append(line)
    return ["\n".join(e) for e in out]


def check(text: str, dockerfile: str) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    notes: list[str] = []

    a_block, b_block, sp = split_blocks(text)
    if sp:
        return sp, notes
    a_entries, b_entries = entries(a_block), entries(b_block)
    notes.append(f"[A] {len(a_entries)} 条 · [B] {len(b_entries)} 条")

    if not a_entries:
        problems.append("[A] 块是空的 —— 那这个分块就没有意义了")

    # 2) [A] 的每一条都要有上游 URL
    for e in a_entries:
        first = e.splitlines()[0].strip()
        if not RE_UPSTREAM_URL.search(e):
            problems.append(
                f"[A] 里的『{first[:50]}』没有给出上游 LICENSE 的 URL —— "
                "[A] 的含义是「读过上游原文」，至少要能指出读的是哪一份"
            )

    # 3) 不许两头都列
    def key(entry: str) -> str:
        return entry.splitlines()[0].strip().lower()

    a_keys = {key(e) for e in a_entries}
    b_keys = {key(e) for e in b_entries}
    both = a_keys & b_keys
    if both:
        problems.append(f"同一组件同时出现在 [A] 与 [B]：{sorted(both)}")

    # 4) Dockerfile 装的组件必须在 NOTICE 里被提到
    text_low = text.lower()
    for name, pat in REQUIRED_COMPONENTS.items():
        rx = pat.lower()
        if not re.search(rx, text_low):
            problems.append(f"Dockerfile 装了 {name}，但 NOTICE 里完全没提到（装了却不声明）")
        else:
            notes.append(f"{name}: 已声明")

    # 反向：NOTICE 声称 [B] 的组件，不该同时被说成 [A]（上面 both 已覆盖）
    # 额外一条：Dockerfile 的 apt 列表真的装了这些吗（防止 REQUIRE 清单过期）
    m = re.search(r"apt-get install[^\\\n]*((?:\\\n[^\n]*)+)", dockerfile)
    if m:
        apt_blob = m.group(1)
        for name, pat in REQUIRED_COMPONENTS.items():
            if name == "openjdk":
                pat_apt = "default-jre-headless"
            elif name == "tabix/htslib":
                pat_apt = "tabix"
            else:
                pat_apt = name
            if pat_apt not in apt_blob:
                problems.append(
                    f"REQUIRED_COMPONENTS 里的 {name} 已不在 Dockerfile 的 apt 列表里 —— "
                    "本检查的清单过期了，要么更新清单，要么这是真漏装"
                )
    return problems, notes


def self_test() -> int:
    """负向测试：证明这个检查真的会失败。"""
    real = NOTICE.read_text(encoding="utf-8")
    df = DOCKERFILE.read_text(encoding="utf-8")

    # 用例：把 samtools 条目从 [A] 里删掉 URL，应报错
    broke_url = real.replace(
        "    https://github.com/samtools/samtools/blob/1.16.1/LICENSE\n"
        "    https://github.com/samtools/bcftools/blob/1.16/LICENSE\n"
        "    https://github.com/samtools/htslib/blob/1.16/LICENSE\n", "")
    # 用例：把 freebayes 整条从 NOTICE 里去掉，覆盖检查应报错
    # ⚠️ 不能用 "freebayes"→"xfreebayes"：那样 `re.search("freebayes", ...)`
    #    仍然能匹配到子串，用例根本不会触发 —— 第一版就是这么写的，
    #    结果"必须失败的用例"通过了，是 --self-test 自己把这个假用例抓出来的。
    broke_cov = re.sub(r"[Ff]ree[Bb]ayes", "SOMETHINGELSE", real)
    # 用例：把 [B] 表头删掉，结构检查应报错
    no_b = real.replace("[B] NOT INDIVIDUALLY VERIFIED", "[C] SOMETHING ELSE")

    cases = [
        ("当前真实的 NOTICE", real, df, True),
        ("回归：[A] 条目缺上游 URL", broke_url, df, False),
        ("回归：漏声明一个已装组件（freebayes）", broke_cov, df, False),
        ("回归：Dockerfile 少装了一个（清单过期）",
         real, df.replace("samtools bcftools tabix", "bcftools tabix"), False),
        ("回归：[B] 表头缺失", no_b, df, False),
    ]
    ok = True
    for name, t, d, want_ok in cases:
        probs, _ = check(t, d)
        passed = (not probs) == want_ok
        if not passed:
            ok = False
        detail = "通过" if not probs else f"抓到 {len(probs)} 处"
        print(f"  {'✅' if passed else '❌'} {name}: {detail}，期望{'通过' if want_ok else '失败'}")
        if probs and not want_ok:
            for p in probs[:3]:
                print(f"       └ {p[:105]}")

    print("负向测试 " + (f"全部通过（含 {sum(1 for _,_,_,w in cases if not w)} 个必须失败的用例）"
                         if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="核对 NOTICE 的 [A]/[B] 分块是否名副其实")
    ap.add_argument("--self-test", action="store_true", help="跑的负向测试，证明检查会失败")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    if not NOTICE.is_file():
        print("SKIP: 没有 NOTICE")
        return 0
    problems, notes = check(NOTICE.read_text(encoding="utf-8"),
                            DOCKERFILE.read_text(encoding="utf-8") if DOCKERFILE.is_file() else "")
    for n in notes:
        print("  · " + n)
    if problems:
        print(f"❌ {len(problems)} 处问题：")
        for p in problems:
            print("   " + p)
        return 1
    print("✅ NOTICE 的 [A]/[B] 分块名副其实：")
    print("   [A] 每条都有上游 LICENSE 出处 · 无组件两头都列 · 已装组件全部声明")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
