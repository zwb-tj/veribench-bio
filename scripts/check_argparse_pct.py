"""全仓扫：argparse 的 help/epilog/description 里的裸 % （会让 --help 崩）。"""

import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(".").resolve()
SKIP = {"__pycache__", "_artifacts", "judge_out", "manip_out", "sources"}
bad = []


def has_bare_pct(s: str) -> bool:
    i = 0
    while i < len(s):
        if s[i] == "%":
            if i + 1 < len(s) and s[i + 1] == "%":
                i += 2
                continue
            # %s %d %f 之类是合法的
            if i + 1 < len(s) and s[i + 1] in "sdrfgiouxXeE":
                i += 2
                continue
            return True
        i += 1
    return False


for f in sorted(ROOT.rglob("*.py")):
    if any(p in f.parts for p in SKIP):
        continue
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"), str(f))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "attr", None) or getattr(fn, "id", None)
        if name not in ("add_argument", "ArgumentParser"):
            continue
        for kw in node.keywords:
            if kw.arg in ("help", "description", "epilog", "usage"):
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    if has_bare_pct(kw.value.value):
                        bad.append((f.relative_to(ROOT).as_posix(), kw.value.lineno, kw.arg,
                                    kw.value.value[:70]))

if bad:
    print(f"❌ {len(bad)} 处 help/description 含裸 `%`（argparse 会做 % 插值 → --help 崩）：")
    for p, ln, k, s in bad:
        print(f"   {p}:{ln}  {k}= {s!r}")
    print("\n   修法：把 `%` 写成 `%%`。")
    sys.exit(1)
print("✅ 全部 argparse 的 help/description 都没有裸 `%`")
