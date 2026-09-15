#!/usr/bin/env python3
"""写文件后立刻自查：中文串里混了 ASCII 双引号吗？

为什么单独做这个
----------------
本项目我**已经犯了七次**同一个错：在中文句子里用 ASCII `"` 包一个词，
而整个字符串又用 `"` 包起来 —— 直接 SyntaxError。

`run_all_checks.py` 的编译检查能抓到它，**但只有在我记得跑的时候**。
所以把这个检查单独摘出来，一行就能跑：

    python3 scripts/lint_zh.py

**第一版用正则做，报了 665 处，全是假阳性** —— 它把 Python 自己的字符串
定界符也当成了"中文里的引号"（因为 `print("裁决自洽:")` 里那个 `"` 后面
紧跟的确实是中文）。教训：**正则看不出"这个引号是定界符还是内容"，
但词法分析器看得出**。所以改用 `tokenize` 只在 **STRING token 的内容里**找。

退出码非零表示有问题。
"""

from __future__ import annotations

import io
import sys
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CJK = r"\u3000-\u303f\u4e00-\u9fff\uff00-\uffef"


def check(path: Path) -> list[str]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    issues: list[str] = []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
        return [f"  ❌ 词法分析失败: {exc}"]

    for tok in toks:
        if tok.type != tokenize.STRING:
            continue
        content = tok.string
        # 去掉定界符与可能的 f/r/b 前缀，只看**字符串内容**
        body = content
        for pre in ("f", "r", "b", "u", "F", "R", "B", "U", "rb", "br", "fr", "rf"):
            if body.lower().startswith(pre):
                body = body[len(pre):]
                break
        if len(body) >= 2 and body[0] in "\"'" and body[-1] == body[0]:
            # ⚠️ 必须区分三引号（文档字符串）与单引号。第一版只剥 1 个字符，
            # 结果每个 `"""docstring"""` 的开头都被当成"中文前的 ASCII 引号"，
            # 报了 50 处假阳性。剥 3 个才对。
            triple = body[:3] in ('"""', "'''") and body[-3:] == body[:3]
            q = 3 if triple else 1
            body = body[q:-q]
        else:
            triple = False
        # 内容里还有 ASCII 双引号，且它旁边是中文 → 就是那个 bug
        import re
        for m in re.finditer(rf'"(?=[{CJK}])|(?<=[{CJK}])"', body):
            snippet = body[max(0, m.start() - 25):m.end() + 25].replace("\n", "⏎")
            # 三引号（文档字符串）里的这种写法**能编译**，所以是隐患不是错误；
            # 单/双引号字符串里则是真错（那种文件根本编译不过）。
            kind = "⚠️ 隐患（在三引号内，可编译）" if triple else "❌ 错误（短字符串内，会编译失败）"
            issues.append(f"  {kind}：第 {tok.start[0]} 行 …{snippet}…")
            break
    return issues


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    args = sys.argv[1:]
    targets = [Path(a) for a in args] or sorted(
        set(list((ROOT / "scripts").glob("*.py")) + list((ROOT / "fixtures").glob("*.py"))
            + list(ROOT.glob("*.py"))))
    total = 0
    fatal = 0
    for p in targets:
        issues = check(p)
        if issues:
            print(f"{p.name}:")
            for i in issues:
                print(i)
                total += 1
                if i.lstrip().startswith("❌"):
                    fatal += 1
    if fatal:
        print(f"\n❌ {total} 处，其中 {fatal} 处会直接编译失败。")
        return 1
    if total:
        print(f"\n⚠️ {total} 处隐患：都在三引号文档字符串内，**当前可编译**，")
        print("   但一旦该字符串被改成单引号就会炸。建议统一换成「」/『』。")
        return 0
    print(f"✅ {len(targets)} 个文件：字符串内容里没有混用 ASCII 双引号")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
