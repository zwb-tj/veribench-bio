#!/usr/bin/env python3
"""**什么算"会被发布出去"** —— 唯一实现。

为什么这个文件必须存在
----------------------
2026-09 审计发现：同一段"遍历仓库、排除刻意不发布的东西"的逻辑，
**被抄了三份**（`print_project_stats.py` / `scan_secrets.py` /
`verify_no_answer_leak.py`），而每一份的 docstring 都写着
「复用 not_published.json —— **不另写一份过滤逻辑**（本项目的老毛病）」。

**写着"不另写一份"，然后各写了一份。**

代价已经发生过两次：
  · `print_project_stats.py` 第一版漏排除 `.git/`，把 615 个 git 对象算成
    发布内容，报出 1308 文件（真实 693）—— **而那个错数字看起来完全正常**
  · 实测三份现在报 **698 / 697 / 698** 个文件（1 个差异来自 `SELF_SKIP`，属合法，
    但**没有任何东西在保证它们继续一致**）

这段逻辑决定了**哪些内容会被扫查泄露、哪些会被扫查凭据** ——
它不是"工具函数"，它是**安全边界**。安全边界抄三份，等于没有边界。

⚠️ 正确性比"少几行"更重要，所以这里**只做一件事**：
遍历 → 按 `not_published.json` 过滤 → 返回绝对路径。
排序用 POSIX 相对路径（跨平台稳定，见 `record_image_digest.py` 的同一教训）。

用法
----
    from publishable_files import publishable
    for p in publishable(): ...

    python3 publishable_files.py            # 打印数量与抽样
    python3 publishable_files.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = HERE / "not_published.json"


def load_manifest() -> tuple[set[str], set[str], set[str]]:
    """读 `not_published.json`，返回 (目录, 后缀, 名字)。"""
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return (set(man.get("dirs") or {}),
            set(man.get("suffixes") or []),
            set(man.get("names") or []))


def publishable(*, extra_skip: set[str] | None = None) -> list[Path]:
    """返回**会被发布**的文件（绝对路径，已排序）。

    :param extra_skip: 调用方额外想排掉的**仓库相对 POSIX 路径**集合。
        例如 `scan_secrets.py` 要把自己排掉（它内嵌了用于自检的假凭据样本）。
        **这是唯一允许的差异点** —— 用参数表达，而不是再抄一遍函数体。
    """
    dirs, suffixes, names = load_manifest()
    skip = extra_skip or set()
    out: list[Path] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        # ⚠️ `.git/` 必须在 `not_published.json` 之外单独排除：
        #    它是**版本控制元数据**，不是"该不该发布"的决策对象。
        if ".git" in p.parts or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in skip:
            continue
        if any(part in names for part in p.parts):
            continue
        if p.suffix in suffixes:
            continue
        if any(rel == d or rel.startswith(d + "/") for d in dirs):
            continue
        out.append(p)
    return sorted(out, key=lambda p: p.relative_to(ROOT).as_posix())


def self_test() -> int:
    """负向测试：**证明这段过滤真的会排东西，而不是恰好返回全部。**

    判据必须独立于实现：这里不看函数体，只看**输出**是否满足可观察性质。
    """
    ok = True
    files = publishable()
    rels = [p.relative_to(ROOT).as_posix() for p in files]

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            ok = False
        print(f"  {'✅' if cond else '❌'} {label}" + (f"  {detail}" if detail else ""))

    print("=== publishable_files 自检 ===")
    check("返回非空", len(files) > 0, f"{len(files)} 个文件")
    check("绝对不返回 .git/ 下的东西",
          not any(r.startswith(".git/") or "/.git/" in r for r in rels))
    check("绝对不返回 __pycache__",
          not any("__pycache__" in r for r in rels))
    # not_published.json 里的第一条目录必须真的被排除
    dirs, _, _ = load_manifest()
    if dirs:
        d = sorted(dirs)[0]
        check(f"声明的目录被排除（{d}）", not any(r == d or r.startswith(d + "/") for r in rels))
    # 一个**确定会在仓库里**的已发布文件必须出现
    check("README.md 在发布集里", "README.md" in rels)
    # extra_skip 必须真的生效
    if rels:
        one = rels[0]
        check(f"extra_skip 生效（{one}）",
              one not in [p.relative_to(ROOT).as_posix()
                          for p in publishable(extra_skip={one})])
    check("排序是 POSIX 路径序", rels == sorted(rels))

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="列出会被发布的文件")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    files = publishable()
    if args.json:
        print(json.dumps([p.relative_to(ROOT).as_posix() for p in files],
                         ensure_ascii=False, indent=2))
        return 0
    print(f"会被发布的文件：{len(files)} 个")
    for p in files[:10]:
        print(f"  {p.relative_to(ROOT).as_posix()}")
    if len(files) > 10:
        print(f"  … 另有 {len(files) - 10} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
