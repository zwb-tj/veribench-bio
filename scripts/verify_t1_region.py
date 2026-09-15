#!/usr/bin/env python3
"""核对「T1 到底覆盖哪一段 chr20」的唯一事实，并确保没有文档跟它矛盾。

为什么单独写一个检查
--------------------
2026-09 发现 T1 的区间被**写错了 7 处**，而且错了整整一个数量级：

    文档说  chr20 10–20 Mb（约 10 Mb）
    事实是  chr20 10–12 Mb（约  2 Mb）

三份**互相独立**的产物都指向 2 Mb（见下），只有文字是错的。
这不是笔误，是**没有唯一事实来源**：区间这个数字在 README、SPEC、DATACARD、
PLAIN_LANGUAGE、T1/README、台账生成器、run.sh 里各写了一遍，谁也没跟数据对过。

为什么原来的检查没抓到
----------------------
`verify_t1_claims.py` 只扫 README + DATACARD 两份文档，而且判据是
`0\\.\\d{3,5}` 这种**小数**正则 —— 区间是个字符串，正则根本不匹配。
所以「有检查」不等于「检查覆盖了」。（给这份脚本做负向测试时确认过这一点。）

唯一事实来源（两个独立记录，必须互相一致）
------------------------------------------
1. `tasks/T1/_data/manifest.json` → `generation.params.region`（数据管线自己写的）
2. 真值 BED 的实际跨度（GIAB 官方 benchmark regions）

两者不一致时**本脚本直接报错**，不允许「取其一」。

被扫描的文件（deliberately 列表，不递归全仓）
--------------------------------------------
README.md, SPEC.md, docs/DATACARD.md, docs/PLAIN_LANGUAGE.md,
tasks/T1/README.md, tasks/T1/run.sh, tasks/T1/data/prepare_data.sh,
ledger/items.jsonl, scripts/build_master_ledger.py

**故意不扫** `research/DATA_LICENSES.md`：那是**拍板之前**的调研记录，
里面 10–20 Mb 是当时在比较的候选方案（最后收缩到 2 Mb）。
扫它只会制造假警报。但调研文档里也加了一句"最终取值见 manifest"，避免读者误读。

用法
----
    python3 verify_t1_region.py
    python3 verify_t1_region.py --self-test    # 负向测试：证明它真的会失败
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
T1 = ROOT / "tasks" / "T1"

SCAN_FILES = [
    "README.md",
    "SPEC.md",
    "docs/DATACARD.md",
    "docs/PLAIN_LANGUAGE.md",
    "tasks/T1/README.md",
    "tasks/T1/run.sh",
    "tasks/T1/data/prepare_data.sh",
    # 2026-09 补：这份里有 `REGION=chr20:10000000-12000000`（复现命令），
    # 值本身是对的，但它此前**不在扫描范围内** —— 也就是说如果哪天被改错，
    # 没人会知道。**"恰好写对了"和"被检查着"是两件事。**
    "tasks/T1/baseline/README.md",
    "ledger/items.jsonl",
    "scripts/build_master_ledger.py",
]

# 区间断言的正则。三类写法都要认：
#   chr20:10000000-12000000      (bp)
#   chr20:10–12 Mb / chr20 10-12 Mb  (Mb，en dash 或 hyphen)
#   （约 2 Mb）                   (长度)
RE_BP = re.compile(r"chr20\s*:\s*(\d{7,9})\s*[–\-]\s*(\d{7,9})")
RE_MB = re.compile(r"chr20\s*:?\s*(\d{1,3})\s*[–\-]\s*(\d{1,3})\s*Mb")
RE_LEN = re.compile(r"约\s*(\d{1,3})\s*Mb")

#: 豁免标记。**必须写在行内、而且是可见的**（不是 HTML 注释），
#: 这样读渲染后文档的人也能看见"这一行的错值是作为历史引用的"。
#:
#: 为什么需要它：`SPEC.md` §3.1 是"我们踩过的坑"清单，它**必须**引用当年写错的
#: 那个值（10–20 Mb）才说得清楚。任何基于文本的核对都会与它相撞。
#: 但豁免**不能是静默的**：run() 会把每一处豁免**逐条打印**，并且**设上限**——
#: 豁免一旦变多就应该有人来解释，而不是让它悄悄长成"这个检查其实没在查"。
EXEMPT_MARKER = "【历史错误】"
MAX_EXEMPT = 5


class SkipCheck(Exception):
    """该检查需要**不随仓库发布**的产物。此时必须 **SKIP 且退出码 0**。

    ⚠️ 不能用 `raise SystemExit("SKIP: ...")` —— 带字符串的 SystemExit 退出码是 **1**，
    会被 run_all_checks 当成"检查失败"。这个 bug 是在**清室检验**里暴露的：
    清室只放会被发布的文件，`_data/manifest.json` 不在其中，于是本脚本"失败"了。
    """


def expected_from_sources() -> tuple[tuple[int, int], list[str]]:
    """从两个独立产物取事实；不一致就抛错。返回 (start, end) 与证据行。"""
    ev: list[str] = []
    man_p = T1 / "_data" / "manifest.json"
    if not man_p.is_file():
        raise SkipCheck(f"缺 {man_p}（数据不随仓库发布，清室检验里正常）")
    man = json.loads(man_p.read_text(encoding="utf-8"))
    region = man["generation"]["params"]["region"]
    m = re.fullmatch(r"chr20:(\d+)-(\d+)", region)
    if not m:
        raise SystemExit(f"❌ manifest 里的 region 格式看不懂：{region!r}")
    man_span = (int(m.group(1)), int(m.group(2)))
    ev.append(f"manifest.json generation.params.region = {region}")

    beds = sorted((T1 / "_data" / "truth").glob("*.bed"))
    if not beds:
        raise SkipCheck("缺 _data/truth/*.bed（同上，不随仓库发布）")
    starts, ends = [], []
    for bed in beds:
        for line in bed.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            f = line.split()
            starts.append(int(f[1]))
            ends.append(int(f[2]))
    bed_span = (min(starts), max(ends))
    ev.append(f"{beds[0].name} 实际跨度 = {bed_span[0]}-{bed_span[1]}（{len(starts)} 个区间）")

    if man_span != bed_span:
        raise SystemExit(
            f"❌ 两个独立记录互相矛盾：manifest={man_span} vs BED={bed_span}\n"
            + "\n".join("   " + e for e in ev)
        )
    return man_span, ev


def scan_text(text: str, expect: tuple[int, int]) -> tuple[list[str], int, list[int]]:
    """扫一段文本，返回 (问题列表, 找到的断言条数, 被豁免的行号)。"""
    problems: list[str] = []
    exempted: list[int] = []
    found = 0
    for ln, line in enumerate(text.splitlines(), 1):
        if "chr20" not in line and "约" not in line:
            continue
        if EXEMPT_MARKER in line:
            exempted.append(ln)
            continue
        for m in RE_BP.finditer(line):
            found += 1
            got = (int(m.group(1)), int(m.group(2)))
            if got != expect:
                problems.append(f"第 {ln} 行 bp 写法 {m.group(0)!r} → {got}，应为 {expect}")
        for m in RE_MB.finditer(line):
            found += 1
            got = (int(m.group(1)) * 1_000_000, int(m.group(2)) * 1_000_000)
            if got != expect:
                problems.append(f"第 {ln} 行 Mb 写法 {m.group(0)!r} → {got}，应为 {expect}")
        for m in RE_LEN.finditer(line):
            found += 1
            got_mb = int(m.group(1))
            want_mb = (expect[1] - expect[0]) // 1_000_000
            if "chr20" in line and got_mb != want_mb:
                problems.append(f"第 {ln} 行长度写法 {m.group(0)!r} → {got_mb} Mb，应为 {want_mb} Mb")
    return problems, found, exempted


def run(expect: tuple[int, int]) -> int:
    total_found = 0
    all_problems: list[str] = []
    all_exempt: list[str] = []
    scanned = 0
    for rel in SCAN_FILES:
        p = ROOT / rel
        if not p.is_file():
            all_problems.append(f"{rel}: 文件不存在（清单里写了但找不到）")
            continue
        scanned += 1
        probs, found, exempted = scan_text(p.read_text(encoding="utf-8"), expect)
        total_found += found
        for ln in exempted:
            all_exempt.append(f"{rel}:{ln}")
        for pr in probs:
            all_problems.append(f"{rel}: {pr}")

    print(f"唯一事实（两个独立记录一致）：chr20 {expect[0]}-{expect[1]}"
          f"（{(expect[1] - expect[0]) / 1e6:g} Mb）")
    print(f"扫描 {scanned}/{len(SCAN_FILES)} 个文件，找到 {total_found} 条区间断言")
    print("故意不扫 research/DATA_LICENSES.md（拍板前的候选方案比较，非事实声明）")

    # 豁免必须**逐条可见**，不能静默。§3.1 的"踩坑清单"必须引用当年的错值才讲得清，
    # 所以豁免本身是合理的；但豁免数变多就说明"这个检查正在被绕过"。
    if all_exempt:
        print(f"豁免 {len(all_exempt)} 行（含标记 {EXEMPT_MARKER}，上限 {MAX_EXEMPT}）："
              + "、".join(all_exempt))

    # ⚠️ 找到 0 条也必须失败：一个什么都没查的检查，通过是假的。
    if total_found == 0:
        print("❌ 一条区间断言都没找到 —— 说明扫描清单或正则坏了，不能算通过")
        return 1
    if len(all_exempt) > MAX_EXEMPT:
        print(f"❌ 豁免行数 {len(all_exempt)} 超过上限 {MAX_EXEMPT} —— "
              "要么有人在拿豁免当万能钥匙，要么该回头改检查本身")
        return 1
    if all_problems:
        print(f"❌ {len(all_problems)} 处与事实矛盾：")
        for pr in all_problems:
            print("   " + pr)
        return 1
    print(f"✅ {total_found} 条区间断言全部与产物一致")
    return 0


def self_test() -> int:
    """负向测试：证明这个检查**真的会失败**。"""
    expect = (10_000_000, 12_000_000)
    cases = [
        ("正确答案", "只考 chr20:10–12 Mb（约 2 Mb）", True),
        ("bp 写法正确", 'REGION="${REGION:-chr20:10000000-12000000}"', True),
        ("回归：原来的 10–20 Mb 错值", "只考 chr20:10–20 Mb（约 10 Mb）", False),
        ("回归：台账里的 10-20Mb", "GRCh38 chr20:10-20Mb, 30x", False),
        ("回归：run.sh 原来的 bp 错值", 'REGION="${REGION:-chr20:10000000-20000000}"', False),
        ("只错长度不改区间", "只考 chr20:10–12 Mb（约 10 Mb）", False),
        ("干净文本（0 条断言）", "T1 是变异检出任务。", None),
    ]
    ok = True
    for name, text, want_pass in cases:
        probs, found, exempted = scan_text(text, expect)
        if want_pass is None:
            passed = (found == 0 and not exempted)
            verdict = "找到 0 条 → run() 会判失败" if passed else "本应找不到"
        else:
            passed = (not probs) == want_pass
            verdict = ("通过" if not probs else f"抓到 {len(probs)} 处") + f"，期望{'通过' if want_pass else '失败'}"
        flag = "✅" if passed else "❌"
        if not passed:
            ok = False
        print(f"  {flag} {name}: {verdict}")

    # 豁免路径也要验：带标记的错值必须被**豁免并且计数**，
    # 既不能静默放过（那样标记就成了万能钥匙），也不能误报（那样文档没法引用历史错误）。
    ex_text = "文档写 chr20 10–20 Mb（约 10 Mb）" + EXEMPT_MARKER
    ex_probs, ex_found, ex_ex = scan_text(ex_text, expect)
    ex_ok = (not ex_probs) and ex_found == 0 and len(ex_ex) == 1
    if not ex_ok:
        ok = False
    print(f"  {'✅' if ex_ok else '❌'} 豁免路径: 带标记的错值被豁免且计为 1 行"
          f"（问题 {len(ex_probs)} · 断言 {ex_found} · 豁免 {len(ex_ex)}）")

    print("负向测试 " + ("全部通过（含 5 个必须失败的用例）" if ok else "**有失败**"))
    return 0 if ok else 1


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="核对 T1 区间事实与文档是否一致")
    ap.add_argument("--self-test", action="store_true", help="跑的负向测试，证明检查会失败")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    try:
        expect, ev = expected_from_sources()
    except SkipCheck as exc:
        print(f"SKIP: {exc}")
        return 0
    for e in ev:
        print("  · " + e)
    return run(expect)


if __name__ == "__main__":
    raise SystemExit(main())
