#!/usr/bin/env python3
"""3.10 语法守卫：仓库声明 Python >= 3.10，但**只有 CI 的 3.10 那一格**在真正执行它。

为什么必须自己有一道判据
------------------------
2026-10-13，`c9351f4` 推送后 CI 变红，而**本地 52 步全绿**。根因：

  `rubric/scripts/textio.py` 里写了 `f"{rawj.count(b'\\r\\n')} 个 CRLF"` ——
  **f-string 表达式里含反斜杠**（PEP 701），只在 Python 3.12+ 合法。
  本机是 3.12.0，`run_all_checks.py` 的第 4 步用 `compile()` 编译，
  **用的是当前解释器**，于是它给了一个假绿；CI 的 3.10 那一格当场 SyntaxError，
  连带把 `rubric/run_all_checks.py`（它的第 1 阶段就是编译旗下 45 个文件）
  拖成 exit 1 —— 冒烟测试因此报了"2 个脚本连 --help 都跑不起来"，
  而**真正坏的只有 1 个文件**。

"声明了下限"不等于"有东西在守着下限"。本脚本就是那个守卫，且**不需要装 3.10**。

判据为什么不能是 `ast.parse(feature_version=(3,10))`
----------------------------------------------------
实测（`_probe_310.py`，本机 3.12.0）：`ast.parse(src, feature_version=(3,10))`
对 `f"{b'\\r\\n'}"` **返回 OK** —— 假绿。原因：`feature_version` 只切换
**parser 语法**（所以它能抓 PEP 695 类型参数、`type X = int`、`except*`），
而 PEP 701 改的是 **tokenizer**。

所以本脚本用两个互补的判据：
  1. `tokenize`：在 f-string 替换字段**内部**出现反斜杠 → 只在 3.12+ 合法
  2. `ast.parse(feature_version=(3,10))`：兜住语法级的用例

判据 1 的括号深度**只在 f-string 内部**跟踪，所以普通 dict 字面量里的
`b"\\r\\n"`（例如本文件自己、或 `textio.py` 修好后的写法）不会被误报 ——
误报比漏报更糟。

用法：
    python3 check_py310_compat.py              # 扫全仓
    python3 check_py310_compat.py --self-test  # 先证明它会失败
"""

from __future__ import annotations

import argparse
import ast
import sys
import tokenize
from io import StringIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: 仓库对外声明的 Python 下限（README.md:96 / docs/DATACARD.md:346 /
#: check_env_deps.py 的 "python_min" / CI matrix 全都写 3.10）。
TARGET = (3, 10)

FSTRING_START = getattr(tokenize, "FSTRING_START", None)
FSTRING_END = getattr(tokenize, "FSTRING_END", None)


def scan_fstring_backslashes(src: str) -> list[tuple[int, str]]:
    """f-string 替换字段里的反斜杠（PEP 701，3.12+）。

    括号深度只在 f-string 内部跟踪 —— 这是第一版会误报普通 dict 字面量的原因。
    """
    hits: list[tuple[int, str]] = []
    try:
        toks = list(tokenize.generate_tokens(StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return hits
    in_fstring = False
    depth = 0
    for tok in toks:
        tt, ts = tok.type, tok.string
        if FSTRING_START is not None and tt == FSTRING_START:
            in_fstring, depth = True, 0
            continue
        if FSTRING_END is not None and tt == FSTRING_END:
            in_fstring, depth = False, 0
            continue
        if not in_fstring:
            continue
        if tt == tokenize.OP and ts == "{":
            depth += 1
            continue
        if tt == tokenize.OP and ts == "}":
            depth = max(0, depth - 1)
            continue
        if depth > 0 and "\\" in ts:
            hits.append((tok.start[0], f"f-string 表达式里有反斜杠（PEP 701，3.12+）：{ts[:60]!r}"))
    return hits


def scan_grammar(src: str) -> list[tuple[int, str]]:
    """`feature_version` 能抓到的语法级用例（它抓不到 PEP 701，见模块 docstring）。"""
    try:
        ast.parse(src, feature_version=TARGET)
    except SyntaxError as exc:
        return [(exc.lineno or 0, f"3.10 语法不接受：{exc.msg}")]
    return []


def check_text(src: str) -> list[tuple[int, str]]:
    out = scan_fstring_backslashes(src) + scan_grammar(src)
    return sorted(out)


def source_files() -> list[Path]:
    """扫会被发布的 .py —— 与"克隆下来 CI 会跑到什么"同一集合。"""
    try:
        sys.path.insert(0, str(HERE))
        from publishable_files import publishable  # type: ignore[import-not-found]
    except ImportError:
        return sorted(p for p in ROOT.rglob("*.py")
                      if "__pycache__" not in p.parts and ".git" not in p.parts)
    return [p for p in publishable() if p.suffix == ".py"]


def self_test() -> int:
    ok = True

    def chk(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            ok = False
        print(f"  {'✅' if cond else '❌'} {label}" + (f"  {detail}" if detail else ""))

    print("=== check_py310_compat self-test ===")

    # ⚠️ 本机若 < 3.12，`tokenize` 没有 FSTRING_START，f-string 那条判据**用不了**。
    # 这时**必须明说"本机无法验证"而不是静默全绿、也不是误报失败** ——
    # 在 3.10 上 PEP 701 本来就写不出来（parser 直接拒绝），所以缺这条判据无害。
    can_scan_fstring = FSTRING_START is not None

    # 必须抓：这些在 3.10 上跑不起来。第三项 = 是否依赖 tokenize 判据。
    must_catch = [
        ("CI 上真正炸掉的那一行", 'x = f"{raw.count(b\'\\r\\n\')} 个 CRLF"\n', True),
        ("反斜杠在嵌套调用里", 'y = f"{len(s.split(\'\\n\'))}"\n', True),
        ("PEP 695 类型参数", "def f[T](x: T) -> T: return x\n", False),
        ("PEP 695 type alias", "type X = int\n", False),
        ("except*（3.11）", "try:\n    pass\nexcept* ValueError:\n    pass\n", False),
    ]
    for label, src, needs_tokenize in must_catch:
        if needs_tokenize and not can_scan_fstring:
            print(f"  ⏭ 必须抓：{label} —— 本机 Python {sys.version.split()[0]} "
                  f"无 tokenize.FSTRING_START，**本机无法验证这条判据**（3.10 上 parser 自会拒绝）")
            continue
        hits = check_text(src)
        chk(f"必须抓：{label}", bool(hits), hits[0][1][:52] if hits else "** 没抓到 **")


    # 必须不抓：这些在 3.10 上完全合法（误报比漏报更糟）
    must_not_catch = [
        ("普通 dict 字面量里的反斜杠", 'd = {"a": "\\n"}\n'),
        ("普通字符串里的反斜杠", 's = "a\\nb"\n'),
        ("f-string 里没有反斜杠", 'x = f"{a} 个"\n'),
        ("f-string 外的字节字面量（本仓修好后的写法）", 'raw = p.read_bytes()\nn = raw.count(b"\\r\\n")\n'),
        ("f-string 嵌套引号但无反斜杠", 'x = f"{d[\'k\']}"\n'),
        ("字典推导里的反斜杠", 'y = {k: "\\t" for k in ks}\n'),
        ("三引号字符串里的反斜杠", 'doc = """\n\\n\n"""\n'),
    ]
    for label, src in must_not_catch:
        hits = check_text(src)
        chk(f"必须不抓：{label}", not hits, hits[0][1][:52] if hits else "")

    # 扫描集合必须真的非空，否则"通过"是假的
    files = source_files()
    chk("扫描集合非空（否则通过无意义）", len(files) > 0, f"{len(files)} 个 .py")

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="3.10 语法兼容守卫（本机 3.12 也能查）")
    ap.add_argument("--self-test", action="store_true", help="先证明检查器会失败")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    files = source_files()
    if not files:
        print("❌ 扫描集合为空 —— 一个什么都没查的检查，通过是假的")
        return 1

    bad = 0
    for f in files:
        src = f.read_text(encoding="utf-8", errors="replace")
        for lineno, why in check_text(src):
            print(f"  ❌ {f.relative_to(ROOT).as_posix()}:{lineno}  {why}")
            bad += 1

    print(f"扫了 {len(files)} 个 .py（目标 Python {TARGET[0]}.{TARGET[1]}，"
          f"本机 {sys.version.split()[0]}）")
    if FSTRING_START is None:
        # 本机就是 3.10/3.11：PEP 701 那种写法在本机根本写不出来（parser 直接拒绝），
        # 所以只跑语法级判据就够。**但要说出来**，不要让"通过"看起来比实际更强。
        print(f"ℹ️  本机 Python {sys.version.split()[0]} 无 tokenize.FSTRING_START —— "
              f"本次只验了语法级判据；PEP 701（f-string 内反斜杠）在本机无法构造，"
              f"故无需该判据")
    if bad:
        print(f"❌ {bad} 处只在比 {TARGET[0]}.{TARGET[1]} 更新的解释器上合法")
        print("   （本地跑绿不算数 —— 声明了下限就得有东西守着下限）")
        return 1
    print(f"✅ 全部能在 {TARGET[0]}.{TARGET[1]} 上解析")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
