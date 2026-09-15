#!/usr/bin/env python3
"""从 `not_published.json` **生成** `.gitignore` —— 不手工维护第二份清单。

为什么必须生成
--------------
本项目有一条**不可撤销**的红线：T2 的轮换池 937 条「**永不公开**」。
而 `git add .` 会抓走工作区里的一切，包括：

    tasks/T2/data/truth.jsonl     4,726 条答案（**含全部 937 条轮换池答案**）
    tasks/T2/data/items.jsonl     4,726 条题面（含轮换池题面）
    tasks/T2/data/rotation/…      轮换池本体

一旦 `git push` 上去，**这句对外声明就永久变成假话** —— 公开过的数据
收不回来，而且它对"是否有人在公开集上过拟合"的检测能力也一并作废。

所以 `.gitignore` 的正确性 = 一个**安全属性**，不是一个方便设置。

为什么是"生成"而不是"手写"
--------------------------
`scripts/not_published.json` 已经是"什么不该对外"的**唯一真源**
（`clean_room_check` 与 `verify_doc_links` 都读它）。
若 `.gitignore` 另写一份，就会出现两份真源 —— 而本项目在这件事上
已经栽过至少三次（`_runs_repro3`、`tasks/T2/_runs`、T2 全量 items/truth/audit）。
**所以这里生成，并让 `--check` 检验它没有过期。**

用法
----
    python3 generate_gitignore.py            # 写入 .gitignore
    python3 generate_gitignore.py --check    # 核对 .gitignore 是否仍然一致
    python3 generate_gitignore.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = HERE / "not_published.json"
GITIGNORE = ROOT / ".gitignore"

HEADER = """\
# ==============================================================================
# ⚠️ 本文件由 scripts/generate_gitignore.py **自动生成**，不要手改。
#
# 唯一真源是 scripts/not_published.json（"什么不该对外"）
# —— `clean_room_check` 与 `verify_doc_links` 也读那一份。
#
# 为什么这件事是**安全属性**而不是方便设置：
#   T2 有一个不可撤销的红线 —— 轮换池 937 条「永不公开」。
#   而 `git add .` 会抓走 `tasks/T2/data/truth.jsonl`
#   （4,726 条答案，**含全部 937 条轮换池答案**）。
#   一旦 push 上去，那句话就永久变成假话。
#
# 改完 not_published.json 后请重新生成：
#     python3 scripts/generate_gitignore.py
# 核对是否过期：
#     python3 scripts/generate_gitignore.py --check
# ==============================================================================

# --- 由 not_published.json 的 dirs 生成（每条都附上了理由）-------------------
"""

FOOTER = """
# --- 由 not_published.json 的 suffixes / names 生成 -------------------------
"""

#: 与 not_published 无关、但属于"本机/编辑器产物"的常规忽略项。
#: **刻意与上面分开写**，这样一眼能看出哪些是安全项、哪些只是噪声项。
EDITOR_NOISE = """\

# --- 本机 / 编辑器噪声（与发布策略无关，纯粹避免误提交）--------------------
.venv/
venv/
env/
__pycache__/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.ipynb_checkpoints/
.vscode/
.idea/
*.swp
*~
.DS_Store
Thumbs.db

# --- 仓库自身的 git 元数据 ---------------------------------------------------
.git/
"""


def build() -> str:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dirs: dict[str, str] = man.get("dirs") or {}
    suffixes: list[str] = man.get("suffixes") or []
    names: list[str] = man.get("names") or []

    parts = [HEADER]
    for d in sorted(dirs):
        # ⚠️ **尾斜杠只加在真目录上。** `not_published.json` 的 `dirs` 里
        #    既有目录（`tasks/T2/data/rotation`）也有**单个文件**
        #    （`tasks/T2/data/truth.jsonl`）。
        #    第一版给所有条目都加了尾斜杠，于是生成了
        #        /tasks/T2/data/truth.jsonl/
        #    而 gitignore 里"带尾斜杠"表示**只能是目录** —— 对文件永不匹配。
        #    后果：**最危险的那个文件（4,726 条答案）根本没被忽略**，
        #    实测 `git add -A` 把它staged 了。
        #    这个 bug 是靠**真跑一遍 git** 发现的，不是靠读代码。
        is_dir = not Path(d).suffix        # 有扩展名 → 当文件处理
        if is_dir:
            parts.append(f"\n# {dirs[d]}\n/{d}/\n")
        else:
            # 文件：列出路径本身，**不加尾斜杠**；同时用 `!` 之外的形式确保
            # 即使父目录将来被"反向"放开也不会漏。
            parts.append(f"\n# {dirs[d]}\n/{d}\n")

    parts.append(FOOTER)
    for s in sorted(suffixes):
        parts.append(f"*{s}\n")
    for n in sorted(names):
        parts.append(f"{n}/\n")

    parts.append(EDITOR_NOISE)
    return "".join(parts)


def check() -> int:
    """核对 .gitignore 是否与 not_published.json 一致（即没有过期）。"""
    want = build()
    if not GITIGNORE.is_file():
        print("❌ 缺 .gitignore —— 生成它：python3 scripts/generate_gitignore.py")
        return 1
    got = GITIGNORE.read_text(encoding="utf-8")
    if got == want:
        n = want.count("\n/")  # 目录条目数（粗略）
        print(f"✅ .gitignore 与 not_published.json 一致（{len(want.splitlines())} 行）")
        return 0
    print("❌ .gitignore 已过期 —— 它和唯一真源不一致")
    import difflib
    d = list(difflib.unified_diff(got.splitlines(), want.splitlines(),
                                  ".gitignore（现状）", "应当生成的内容",
                                  lineterm="", n=1))
    for line in d[:40]:
        print("   " + line)
    print("\n   修复：python3 scripts/generate_gitignore.py")
    print("   ⚠️ 这**不是**格式问题：不一致意味着某些「不发布」的路径"
          "可能正暴露在 `git add .` 之下。")
    return 1


def self_test() -> int:
    """负向测试：**用真 git 验证**关键路径确实被忽略。

    ⚠️ 为什么不能只做字符串匹配
    ---------------------------
    第一版自检的判据是 "`/` + 路径 + `/` in 文本" —— 对**所有**条目都拼尾斜杠。
    而生成器当时也给**文件**条目拼了尾斜杠，于是
    **实现与自检犯同一个错、自检照样通过**。
    实测 `git add -A` 把 `tasks/T2/data/truth.jsonl`（4,726 条答案，含全部
    937 条轮换池答案）**staged 了** —— 最危险的文件根本没被忽略。

    → 教训：**验证"关于 X 的性质"时，不要用"与实现共享同一个假设"的判据。**
      这里直接调 `git check-ignore`，让 git 自己回答。
    """
    import shutil
    import subprocess
    import tempfile

    #: 这些路径**必须**被忽略（每条都对应一次真实踩坑）
    MUST_IGNORE = [
        "tasks/T2/data/truth.jsonl",       # 含轮换池答案 —— 最致命
        "tasks/T2/data/items.jsonl",
        "tasks/T2/data/audit.jsonl",
        "tasks/T2/data/rotation/truth.jsonl",
        "tasks/T2/data/public/truth.jsonl",
        "tasks/T2/data/_cache/x.vcf",
        "tasks/T1/_data/manifest.json",
        "tasks/T1/_runs/result.json",
        "tasks/T1/_runs_repro3/result.json",
        "rubric/items/sources/any.txt",
    ]
    #: 这些**不能**被忽略（是产品的一部分）
    MUST_KEEP = [
        "README.md", "SPEC.md", "LICENSE", "NOTICE",
        "tasks/T2/grade.py", "tasks/T2/data/check_no_leakage.py",
        "tasks/T2/data/T2_DATASET_CARD.md",
        "scripts/not_published.json",
    ]

    if shutil.which("git") is None:
        print("SKIP: 本机没有 git，无法做真实验证（**不算通过**）")
        return 0

    text = build()
    tmp = Path(tempfile.mkdtemp(prefix="gitignore-selftest-"))
    ok = True
    try:
        (tmp / ".gitignore").write_text(text, encoding="utf-8", newline="")
        subprocess.run(["git", "init", "-q"], cwd=tmp, capture_output=True)

        def ignored(rel: str) -> bool:
            r = subprocess.run(["git", "check-ignore", "-q", "--no-index", rel],
                               cwd=tmp, capture_output=True)
            return r.returncode == 0

        for rel in MUST_IGNORE:
            hit = ignored(rel)
            ok = ok and hit
            print(f"  {'✅' if hit else '❌'} 忽略 {rel}")
        for rel in MUST_KEEP:
            hit = ignored(rel)
            ok = ok and not hit
            print(f"  {'✅' if not hit else '❌'} 不忽略 {rel}（应被提交）")

        if ignored("definitely/not/here.txt"):
            ok = False
            print("  ❌ 判据无效：不存在的路径被判为已忽略")
        else:
            print("  ✅ 判据有效（不存在的路径不会被误判为已忽略）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("负向测试 " + ("全部通过（用真 git 验证）" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="从 not_published.json 生成 .gitignore")
    ap.add_argument("--check", action="store_true", help="核对是否与真源一致")
    ap.add_argument("--self-test", action="store_true", help="负向测试")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.check:
        return check()

    text = build()
    GITIGNORE.write_text(text, encoding="utf-8", newline="")
    n = len([l for l in text.splitlines() if l.startswith("/")])
    print(f"已写入 {GITIGNORE}")
    print(f"   {len(text.splitlines())} 行，其中 {n} 条目录级忽略（来自 not_published.json）")
    print("   ⚠️ 这是**安全属性**：它保证 `git add .` 不会抓走 T2 的 4,726 条答案")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
