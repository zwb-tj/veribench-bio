#!/usr/bin/env python3
"""守住"什么算会被发布"这件事**只有一份实现**。

为什么需要这个检查
------------------
2026-09 审计发现：同一段"遍历仓库、排除刻意不发布的东西"的逻辑被**抄了三份**
（`print_project_stats.py` / `scan_secrets.py` / `verify_no_answer_leak.py`）——
而**每一份的 docstring 都写着**：

    「复用 not_published.json —— **不另写一份过滤逻辑**（本项目的老毛病）」

**写着"不另写一份"，然后各写了一份。** 而且三份已经漂移：
实测分别报出 698 / 697 / 698 个文件。

为什么这不是"代码风格问题"
--------------------------
这段逻辑决定 **哪些内容会被扫查答案泄露、哪些会被扫查凭据**。
它不是工具函数，它是**安全边界**。安全边界抄三份 = 有三个不同的安全边界，
而其中任意一份的 bug（例如漏排除 `.git/`，真实发生过：把 615 个 git 对象
算成发布内容，报 1308 而真实 693）**只影响它自己**，其余两份不会报警。

本检查做两件事
--------------
  A. **结构**：那三个消费方必须真的 `from publishable_files import publishable`，
     不许再出现自己的 `rglob` + `not_published` 过滤循环。
  B. **行为**：三个消费方数出的文件数必须一致
     （`scan_secrets` 允许少 1 —— 它按设计排掉自己，见其 docstring）。

用法
----
    python3 check_publishable_agree.py
    python3 check_publishable_agree.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: 必须委托给共享实现的消费方：(文件, 允许的数量差异)
CONSUMERS = [
    ("scripts/print_project_stats.py", 0),
    ("scripts/verify_no_answer_leak.py", 0),
    #: scan_secrets 排除自己（自检样本里含假凭据），所以允许少 1
    ("scripts/scan_secrets.py", 1),
]

#: 共享实现本身
SHARED = "scripts/publishable_files.py"

#: 出现这个组合就说明又自己抄了一份过滤循环
OWN_LOOP_MARKERS = ("not_published.json", "rglob")


def check_delegation() -> list[str]:
    """A. 结构检查：消费方必须 import 共享实现，且不得再有自己的过滤循环。"""
    probs: list[str] = []
    for rel, _ in CONSUMERS:
        p = ROOT / rel
        if not p.is_file():
            probs.append(f"{rel} 不存在")
            continue
        t = p.read_text(encoding="utf-8")
        if "from publishable_files import" not in t:
            probs.append(f"{rel} 没有委托给 {SHARED}"
                         "（应当 `from publishable_files import publishable`）")
        # 找函数体里是否还有自己的过滤循环
        for m in re.finditer(r"def (_?publishable)\s*\([^)]*\)[^:]*:\s*(?:\"\"\".*?\"\"\")?",
                             t, re.S):
            start = m.end()
            body = t[start:start + 1200]
            has_loop = "rglob" in body
            mentions_manifest = "not_published" in body
            if has_loop and mentions_manifest:
                probs.append(f"{rel}: {m.group(1)}() 里又有自己的 rglob + not_published"
                             " 过滤循环 —— 必须委托给共享实现")
    return probs


def count_published(rel: str) -> int | None:
    """B. 行为检查：数出每个消费方**实际会扫的文件数**。

    ⚠️ **不能靠抓 stdout。** 第一版解析脚本输出里的 "NNN 个" ——
    在全新 clone 里 `verify_no_answer_leak.py` 会因缺轮换池数据而 **SKIP**，
    于是它不打印任何计数，我的检查器就报「数不出文件数（输出格式变了？）」，
    **把一个正常的 SKIP 误报成漂移**。

    那时 CI 会红，而人会怎么办？**把检查关掉。**
    本项目已经吃过"误报会让人把检查关掉，比漏报更糟"的亏
    （见 check_annotation_blinding.py 的同一教训）。

    正确做法：**直接导入那个模块，调它自己的 publishable 函数** ——
    判据是"它们是否真的共用同一实现"，而不是"它们的日志长得像不像"。
    """
    import importlib.util

    p = ROOT / rel
    if not p.is_file():
        return None
    # 让模块能 import 同目录的 publishable_files
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(
            "consumer_" + p.stem, p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, "publishable", None) or getattr(mod, "_publishable", None)
        if fn is None:
            return None
        out = fn()
        return len(out)
    except Exception:  # noqa: BLE001
        # 导入失败（依赖缺失等）→ 交给调用方按"数不出"处理，
        # 但**不**把它当成漂移（那是别的检查该管的事）
        return None


def self_test() -> int:
    ok = True
    print("=== 共享实现一致性自检 ===")

    # ① 共享实现存在且自检通过
    sh = ROOT / SHARED
    cond = sh.is_file()
    ok = ok and cond
    print(f"  {'✅' if cond else '❌'} 共享实现存在（{SHARED}）")

    # ② 当前结构检查应当通过
    probs = check_delegation()
    cond = not probs
    ok = ok and cond
    print(f"  {'✅' if cond else '❌'} 三个消费方都委托了共享实现")
    for x in probs[:3]:
        print(f"      {x}")

    # ③ **负向**：造一个"自己抄一份"的假消费方，必须被抓到
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "fake_consumer.py"
        fake.write_text(
            "import json\n"
            "from pathlib import Path\n"
            "ROOT = Path('.')\n"
            "def publishable():\n"
            "    man = json.loads((ROOT / 'not_published.json').read_text())\n"
            "    out = []\n"
            "    for p in ROOT.rglob('*'):\n"
            "        out.append(p)\n"
            "    return sorted(out)\n",
            encoding="utf-8")
        # 临时把这个假文件塞进 CONSUMERS 检查
        orig = list(CONSUMERS)
        try:
            CONSUMERS.append((str(fake.relative_to(Path(td))), 0))
            # 直接对假文件跑结构检查
            t = fake.read_text(encoding="utf-8")
            caught = ("from publishable_files import" not in t)
            m = re.search(r"def (_?publishable)\s*\([^)]*\)[^:]*:\s*(?:\"\"\".*?\"\"\")?",
                          t, re.S)
            if m:
                body = t[m.end():m.end() + 1200]
                caught = caught or ("rglob" in body and "not_published" in body)
        finally:
            CONSUMERS[:] = orig
        ok = ok and caught
        print(f"  {'✅' if caught else '❌'} 负向：自己抄一份过滤循环会被抓到")

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="守住发布集过滤只有一份实现")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    probs = check_delegation()
    counts: dict[str, int | None] = {}
    for rel, _ in CONSUMERS:
        counts[rel] = count_published(rel)

    if not args.quiet:
        print("各消费方数出的文件数：")
        for rel, _ in CONSUMERS:
            print(f"  {counts[rel]!s:>6}  {rel}")

    # 行为一致性：以共享实现为准，差值不得超过该消费方声明的允许量
    ref_p = subprocess.run([sys.executable, str(ROOT / SHARED), "--json"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT))
    try:
        ref = len(json.loads(ref_p.stdout))
    except (ValueError, TypeError):
        ref = None

    if ref is not None:
        for rel, slack in CONSUMERS:
            c = counts.get(rel)
            if c is None:
                probs.append(f"{rel}: 数不出文件数（输出格式变了？）")
            elif not (0 <= ref - c <= slack):
                probs.append(f"{rel}: {c} 个，共享实现 {ref} 个，"
                             f"差 {ref - c}（允许 ≤ {slack}）—— **已经漂移**")

    if probs:
        print()
        print("❌ 『什么算会被发布』出现了第二份实现 / 已经漂移：")
        for x in probs:
            print(f"  · {x}")
        print()
        print("为什么严重：这段逻辑决定**哪些内容会被查答案泄露、哪些会被查凭据**。")
        print("它是安全边界，不是工具函数 —— 抄三份 = 三个安全边界，")
        print("其中一份的 bug 不会让另外两份报警（真实发生过：漏排除 .git/，")
        print("把 615 个 git 对象算成发布内容，报 1308 而真实 693）。")
        return 1

    print(f"✅ 三个消费方都委托同一实现（{ref} 个文件；scan_secrets 按设计少 1）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
