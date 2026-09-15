#!/usr/bin/env python3
"""清室检验（clean-room check）：**只给会被公开发布的东西**，流水线还跑不跑得起来？

为什么这是"第三方/CI 复现"的第一步
----------------------------------
D9 要求"第三方 + clean-CI 复现"。第三方我变不出来，但**有一个子问题我自己就能测**：

> 如果我们现在把仓库推公开，别人 clone 下来，**能跑通吗？**

我本地跑得通说明不了这件事 —— 因为本地有大量**不会发布**的东西：
判分产出、PMC 全文、几百 MB 的中间数据、GATK 的拆包产物。
只要有任何一步**偷偷依赖了这些**，第三方就会在第一步失败，而我在本地看不见。

所以本脚本把"会发布的那部分"复制到一个干净临时目录，在那里重跑检查。

排除项与理由（每一项都是"发不发"的决定，不是随手忽略）
------------------------------------------------------
| 排除 | 大小 | 为什么不发布 |
|---|---|---|
| `research/_artifacts/` | ~1.1 GB | 上游 jar 拆包产物，用于许可审计，**结论已写进文档**，原件不必分发 |
| `tasks/T1/_data/` `_work_backup/` | ~171 MB | 运行期数据；由 `prepare_data.sh` 从上游重新取 |
| `tasks/T2/data/_cache/` | ~184 MB | ClinVar 原始 VCF；由取数脚本重新下载 |
| `rubric/items/sources/` | ~1 MB | **别人的论文全文**。公开的是改写后的题目，不是原文 |
| `rubric/fixtures/answers/*_out*/` | 大 | 判分产出，可重跑；且它们是"我们的结果"不是"数据集" |
| `__pycache__` / `*.pyc` | — | 构建产物 |

⚠️ **本脚本只回答"能不能跑起来"，不回答"跑出来的结论对不对"** ——
后者需要真值，是另一件事。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: ⚠️ 刻意不发布的路径**从 `not_published.json` 读，不在这里另写一份**。
#:    本轮踩到的坑：本脚本把 `rubric/items/sources/` 当"不发布"排除掉，
#:    而 `verify_doc_links.py` 不知道，于是把 SPEC / SAFETY 里对它的引用
#:    报成死亡链接 —— 同一个概念有两份定义，两个工具就会互相打架
#:    （清室检验正是因此失败）。所以设成单一真源。
MANIFEST = HERE / "not_published.json"


def _load_not_published() -> tuple[set[str], set[str], set[str]]:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return set(man["dirs"]), set(man["suffixes"]), set(man["names"])


EXCLUDE_DIRS, EXCLUDE_SUFFIX, EXCLUDE_NAMES = _load_not_published()


def ignore(dirpath: str, names: list[str]) -> set[str]:
    skip: set[str] = set()
    rel = Path(dirpath).resolve()
    for n in names:
        p = rel / n
        try:
            rels = p.relative_to(ROOT).as_posix()
        except ValueError:
            rels = n
        if n in EXCLUDE_NAMES or Path(n).suffix in EXCLUDE_SUFFIX:
            skip.add(n)
        elif rels in EXCLUDE_DIRS or any(rels.startswith(d + "/") for d in EXCLUDE_DIRS):
            skip.add(n)
        elif any(rels == d for d in EXCLUDE_DIRS):
            skip.add(n)
    return skip


def tree_size(p: Path) -> tuple[int, int]:
    n = 0
    sz = 0
    for f in p.rglob("*"):
        if f.is_file():
            n += 1
            sz += f.stat().st_size
    return n, sz


def run(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, cwd=str(cwd))
    lines = [l for l in ((p.stdout or "") + (p.stderr or "")).strip().splitlines() if l.strip()]
    return p.returncode == 0, "\n".join(lines[-4:])


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="清室检验")
    ap.add_argument("--keep", action="store_true", help="保留临时目录（排查用）")
    args = ap.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix="veribench-clean-"))
    dest = tmp / "bio-eval"
    print(f"清室目录：{tmp}")
    print(f"从 {ROOT} 复制**会被发布的那部分**…")
    shutil.copytree(ROOT, dest, ignore=ignore)

    n, sz = tree_size(dest)
    print(f"复制后：{n} 个文件 / {sz / 1024 / 1024:.1f} MB")
    n0, sz0 = tree_size(ROOT)
    print(f"原始：  {n0} 个文件 / {sz0 / 1024 / 1024:.1f} MB"
          f"（去掉 {100 - sz / sz0 * 100:.1f}% 的体积）")

    checks: list[tuple[str, bool, str]] = []

    print("\n--- A) 上游没有任何生成物时，项目级检查还能跑吗 ---")
    ok, out = run([sys.executable, "run_all_checks.py"], dest)
    checks.append(("项目级 run_all_checks.py", ok, out))
    print(f"  {'✅' if ok else '❌'} 项目级检查")
    for l in out.splitlines():
        print(f"      {l}")

    print("\n--- B) rubric 支柱呢（判分产出全被拿掉了）---")
    ok, out = run([sys.executable, "run_all_checks.py"], dest / "rubric")
    checks.append(("rubric/run_all_checks.py", ok, out))
    print(f"  {'✅' if ok else '❌'} rubric 检查")
    for l in out.splitlines():
        print(f"      {l}")

    print("\n--- C) 关键脚本能否独立启动（--help 是最低门槛）---")
    key = [
        dest / "scripts" / "audit_licenses.py",
        dest / "scripts" / "build_master_ledger.py",
        dest / "rubric" / "scripts" / "kappa.py",
        dest / "rubric" / "scripts" / "judge_eval.py",
    ]
    for k in key:
        if not k.is_file():
            checks.append((k.name, False, "文件缺失"))
            print(f"  ❌ {k.name}: 复制后不存在")
            continue
        if k.name in ("kappa.py", "judge_eval.py"):
            ok, out = run([sys.executable, str(k), "--self-test"], dest)
        else:
            ok, out = run([sys.executable, str(k), "--help"], dest)
        checks.append((k.name, ok, out))
        print(f"  {'✅' if ok else '❌'} {k.name}")

    print("\n--- D) 明文提到的排除项确实不在清室目录里 ---")
    leftovers = []
    for d in sorted(EXCLUDE_DIRS):
        if (dest / d).exists():
            leftovers.append(d)
    checks.append(("无排除项残留", not leftovers, str(leftovers)))
    print(f"  {'✅' if not leftovers else '❌'} 残留：{leftovers or '无'}")

    n_fail = sum(1 for _, ok, _ in checks if not ok)
    print("\n" + "=" * 68)
    for name, ok, out in checks:
        print(f"  {'✅' if ok else '❌'} {name}")
    print()
    if n_fail:
        print(f"❌ {n_fail} 项失败 —— **第三方 clone 下来会卡住**。这必须在发布前修掉。")
        print(f"   清室目录保留在 {tmp} 以便排查。")
        return 1
    print("✅ 清室检验通过：只给会被发布的文件，两级检查都能跑通。")
    print()
    print("⚠️ 这**不等于**第三方复现已经做过。它只证明：")
    print("   · 没有隐藏依赖未发布的文件（这是最容易漏、也最容易让第三方卡住的一类）")
    print("   它**没有**证明：")
    print("   · 环境依赖齐全（docker / jsonschema / 网络可达上游）")
    print("   · 跑出来的数字对不对（那需要真值与上游数据）")
    if args.keep:
        print(f"\n（--keep）清室目录保留：{tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
        print("\n（临时目录已清理；用 --keep 可保留）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
