#!/usr/bin/env python3
"""守住"位置式引用"这一类：**"上表最后 N 条"写的时候是对的，之后静默腐烂**。

## 为什么需要它

`SPEC.md` §3.1 的两段推论标题原文是「关于**上表最后四条**的推论」与
「关于**上表最后五条**的推论」。跨 6 个已提交版本实测（`0237494` 表 34 行、
`cf0bcd4` 40、`e3919ea` 41、`0e8eab3` 46、`deeba83` 49、`41f3398` 52）：
**两个标题在每一个版本里都存在，而表尾早就不在那儿了。**

按语义对号入座后确认归属是连续的：「最后四条」= 第 9–12 行、「最后五条」的
前四条 = 第 13–17 行 —— 也就是说它们是在表还只有 12 行 / 17 行时写的，
随后又追加了 17 行（第 18–34 行）而**标题从未跟着更新**。

这就是本项目反复踩的那一类：**看起来对、实际不对、不报错**。
它比"忘了更新"更坏，因为引用它的读者不会察觉自己读错了条目。

## 判据（刻意很窄）

只抓**紧邻**"上表/下表"的位置式引用：`上表最后四条`、`下表最后 5 行`……
**不抓**正文里的"最后一行是…""故意丢掉最后一行"——那些"最后"指的是
某个输出的末行，与"表的第几行到第几行"无关。

**误报比漏报更糟**：一个会误报的检查很快就被关掉了，那就什么也守不住。
所以宁可窄，宁可让 `--self-test` 的"必须不抓"用例多过"必须抓"的用例。

`SPEC.md` §3.1 那条**必须**引用当年的错标题才说得清经过，所以它带
`EXEMPT_MARKER` 豁免。豁免**不能静默**：逐条打印，并且**设上限** ——
豁免一旦变多，说明这个检查正在被绕过，而不是文档需要引用历史。

## 与 `verify_t1_region.py` 的区别（同为"扫文档"的检查器，但失败条件相反）

`verify_t1_region.py` 是**一致性**检查：必须**找到**断言并与唯一事实比对，
所以"找到 0 条"本身就要失败。
本脚本是**禁止性**检查：**找到 0 条才是成功**（"文档里不存在位置式引用"），
因此"扫描确实发生了"由**扫描文件数 > 0** 与 `--self-test` 里的阳性夹具保证。

    python3 check_positional_refs.py
    python3 check_positional_refs.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

sys.path.insert(0, str(HERE))
from publishable_files import publishable  # noqa: E402

#: 判据：**紧邻**的表引用 + "最后" + 数量 + 量词（条/行）。
#:
#: `上表|下表` 之后允许一个"的"，但不允许插入别的词 —— 一旦允许拉长，
#: 正文里"上表列出了每个样本，最后一行是表头"这类句子就会被误报。
RE_POSITIONAL = re.compile(
    r"(上表|下表|上面的表|下面的表)\s*的?\s*最后\s*"
    r"([一二三四五六七八九十两0-9]+)\s*([条行])"
)

#: 与 `verify_t1_region.py` 共用同一个可见标记（**一处定义，避免两份真源**）。
#: 它必须写在行内而且是渲染后可见的 —— 读文档的人也要能看见"这处是历史引用"。
from verify_t1_region import EXEMPT_MARKER  # noqa: E402

#: 豁免上限。豁免本身合理（§3.1 必须引用当年的错标题），但**变多就是警报**。
MAX_EXEMPT = 3


def scan_text(text: str) -> tuple[list[str], list[str]]:
    """扫一段文本，返回 (未豁免的问题行, 被豁免的行号串)。

    豁免行**不计入问题**，但会被单独列出并计入上限。
    """
    problems: list[str] = []
    exempted: list[str] = []
    for ln, line in enumerate(text.splitlines(), 1):
        hits = RE_POSITIONAL.findall(line)
        if not hits:
            continue
        if EXEMPT_MARKER in line:
            exempted.append(f"{ln}({len(hits)})")
            continue
        for table, num, unit in hits:
            problems.append(
                f"第 {ln} 行 {table}最后{num}{unit} → "
                "位置式引用：表的行数一变它就会指错，改成内容锚定"
            )
    return problems, exempted


def run() -> int:
    files = [p for p in publishable() if p.suffix == ".md"]
    all_problems: list[str] = []
    all_exempt: list[str] = []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        probs, exempted = scan_text(p.read_text(encoding="utf-8", errors="replace"))
        all_problems += [f"{rel}: {pr}" for pr in probs]
        all_exempt += [f"{rel}:{e}" for e in exempted]

    print(f"扫描 {len(files)} 个会被发布的 .md 文件，找「上表/下表 + 最后 N 条」")
    print("判据是窄的：正文里的「最后一行」「最后一条」（不带表引用）**不抓**")

    if all_exempt:
        print(f"豁免 {len(all_exempt)} 行（含标记 {EXEMPT_MARKER}，上限 {MAX_EXEMPT}）："
              + "、".join(all_exempt))

    if not files:
        print("❌ 一个 .md 都没扫到 —— 说明发布集或路径算错了，不能算通过")
        return 1
    if len(all_exempt) > MAX_EXEMPT:
        print(f"❌ 豁免行数 {len(all_exempt)} 超过上限 {MAX_EXEMPT} —— "
              "要么有人在拿豁免当万能钥匙，要么该回头改检查本身")
        return 1
    if all_problems:
        print(f"❌ {len(all_problems)} 处位置式引用：")
        for pr in all_problems:
            print("   " + pr)
        return 1
    print("✅ 未发现任何「上表/下表 + 最后 N 条」式引用")
    return 0


def self_test() -> int:
    """负向测试：既证明**真的会抓**，也证明**不会乱抓**。"""
    must_catch = [
        ("原样：上表最后四条", "→ **关于上表最后四条的推论（比结论本身更重要）**："),
        ("原样：上表最后五条", "→ **关于上表最后五条的推论（2026-09 补）**："),
        ("数字写法", "见下表最后 5 条。"),
        ("量词是行", "上表最后两行是新增的。"),
        ("中间有「的」", "关于下表的最后三条推论："),
    ]
    must_not_catch = [
        # SPEC.md §3.1 里带豁免标记的历史引用（由豁免路径单独验，这里验"没标记就抓"）。
        ("不带表引用：最后一行是", '每个都标注"不含轮换池 id ✅"，最后一行是'),
        ("不带表引用：预期最后一行", "预期最后一行：`✅ 逐字节一致`。"),
        ("代码注释里的最后一行", "    cross_check_totals(good, atoms[:-1])   # 故意丢掉最后一行"),
        ("单数、且无表引用", "正文里最后一条不抓。"),
        # 关键的反向用例：**有"最后"、有表、但中间隔了别的词** —— 不能误报。
        ("表与最后之间隔了词", "上表列出了每个样本，最后一行是表头。"),
        ("既无表也无最后", "这一段没有任何位置式引用。"),
    ]
    ok = True
    for name, text in must_catch:
        probs, exempted = scan_text(text)
        caught = bool(probs) and not exempted
        ok = ok and caught
        print(f"  {'✅' if caught else '❌'} 必须抓：{name}"
              + ("" if caught else f"  → 漏了（problems={probs}）"))
    for name, text in must_not_catch:
        probs, exempted = scan_text(text)
        clean = not probs and not exempted
        ok = ok and clean
        print(f"  {'✅' if clean else '❌'} 必须不抓：{name}"
              + ("" if clean else f"  → 误报 {probs}"))

    # 豁免路径：带标记的错值必须被豁免并计数 —— 既不能静默放过（标记会变成万能钥匙），
    # 也不能误报（那样 §3.1 就没法引用历史了）。
    ex_text = "标题原文是「关于上表最后四条的推论」" + EXEMPT_MARKER
    ex_probs, ex_ex = scan_text(ex_text)
    ex_ok = (not ex_probs) and len(ex_ex) == 1
    ok = ok and ex_ok
    print(f"  {'✅' if ex_ok else '❌'} 豁免路径：带标记必须豁免且计数（1 行）"
          + ("" if ex_ok else f"  → problems={ex_probs} exempted={ex_ex}"))

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="扫描「上表最后 N 条」式位置引用")
    ap.add_argument("--self-test", action="store_true", help="负向测试")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
