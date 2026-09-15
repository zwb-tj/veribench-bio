#!/usr/bin/env python3
"""环境依赖清单：**从代码里扫出来**，而不是凭记忆写。

为什么不能凭记忆
----------------
清室检验证明了"文件齐不齐"，但它自己写明了不管"环境够不够"。
而"环境依赖"最容易写错 —— 手写一份 `requirements.txt` 十有八九漏东西，
因为**人是照着印象写的，不是照着 import 扫的**。

所以本脚本：
  1. 用 `ast` 扫全部 `.py` 的 import，按 `sys.stdlib_module_names` 分成
     **标准库 / 本仓库内部 / 第三方**
  2. 对第三方逐个 `importlib.util.find_spec` 验证**当前环境里是否真的能导入**
  3. 扫出 Docker 依赖与**网络端点**（第三方复现最容易卡在这两处）
  4. 报告 Python 版本要求

输出是一份可复现的清单，而不是一段描述。

用法：
    python3 check_env_deps.py            # 检查并列清单
    python3 check_env_deps.py --json out.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from importlib.util import find_spec
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# 扫描范围：仓库自己的源码。排除生成物与第三方。
SCAN_DIRS = ["scripts", "rubric/scripts", "rubric/fixtures", "rubric", "tools", "tasks"]
SKIP_PARTS = {"__pycache__", "judge_out", "judge_out_run1", "judge_out_run2",
              "manip_out_run1", "manip_out_run2", "judge_outputs", "_artifacts",
              "_cache", "_data", "_work", "_work_backup", "sources"}

URL_RE = re.compile(r"https?://([a-zA-Z0-9._-]+)")


def iter_py() -> list[Path]:
    out: list[Path] = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for f in base.rglob("*.py"):
            if any(p in SKIP_PARTS for p in f.parts):
                continue
            out.append(f)
    # 顶层脚本
    out += list(ROOT.glob("*.py"))
    return sorted(set(out))


def local_modules() -> set[str]:
    """本仓库里的顶层模块名（用于区分"内部导入"与"第三方"）。"""
    names = set()
    for f in iter_py():
        names.add(f.stem)
    for d in SCAN_DIRS:
        p = ROOT / d
        if p.is_dir():
            names.add(p.name)
            for f in p.glob("*.py"):
                names.add(f.stem)
    return names


def scan_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    except SyntaxError:
        return set()
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:          # 相对导入 → 内部
                continue
            if node.module:
                mods.add(node.module.split(".")[0])
    return mods


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="环境依赖清单")
    ap.add_argument("--json", help="把清单写成 JSON")
    args = ap.parse_args(argv)

    files = iter_py()
    local = local_modules()
    stdlib = set(sys.stdlib_module_names)

    third: dict[str, set[str]] = {}
    stdlib_used: set[str] = set()
    internal: set[str] = set()
    for f in files:
        for m in scan_imports(f):
            if m in stdlib:
                stdlib_used.add(m)
            elif m in local:
                internal.add(m)
            else:
                third.setdefault(m, set()).add(f.relative_to(ROOT).as_posix())

    print(f"扫描 {len(files)} 个 .py")
    print(f"Python 版本：{sys.version.split()[0]}"
          f"（代码里用到的语法：f-string、`X | None` 类型标注 → 需 **>= 3.10**）")
    print()
    print(f"标准库模块 {len(stdlib_used)} 个：{'、'.join(sorted(stdlib_used))}")
    print(f"仓库内部模块 {len(internal)} 个")
    print()

    missing: list[str] = []
    if third:
        print(f"**第三方依赖 {len(third)} 个**：")
        for m in sorted(third):
            spec = find_spec(m)
            ok = spec is not None
            if not ok:
                missing.append(m)
            where = sorted(third[m])
            loc = f"{len(where)} 个文件"
            print(f"  {'✅' if ok else '❌'} {m:<14} {loc}   例：{where[0]}")
    else:
        print("**第三方依赖：无**（只用标准库）")

    # Docker
    dockers = sorted(p for p in ROOT.rglob("Dockerfile") if not any(x in p.parts for x in SKIP_PARTS))
    print()
    print(f"Docker 依赖：{len(dockers)} 个 Dockerfile")
    for d in dockers:
        print(f"  · {d.relative_to(ROOT).as_posix()}")

    # 网络端点：第三方复现最常卡在这里
    hosts: dict[str, set[str]] = {}
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in URL_RE.finditer(txt):
            hosts.setdefault(m.group(1), set()).add(f.relative_to(ROOT).as_posix())
    print()
    print(f"**网络端点 {len(hosts)} 个**（第三方复现必须能访问）：")
    for h in sorted(hosts, key=lambda x: -len(hosts[x])):
        print(f"  · {h:<42} 出现在 {len(hosts[h])} 个文件")

    print()
    print("=" * 70)
    if missing:
        print(f"❌ 当前环境缺 {len(missing)} 个第三方依赖：{missing}")
        print("   装法：pip install " + " ".join(missing))
        return 1
    print("✅ 当前环境满足代码里实际出现的全部第三方依赖")
    print()
    print("⚠️ 两点必须说清：")
    print("  1. 这只覆盖 **import 得到的**依赖。Docker、上游网络可达性、磁盘空间")
    print("     都不是 import，本脚本查不出 —— 它们仍是第三方复现的未知项。")
    print("  2. 有些脚本**只在需要时才 import 第三方**（如 jsonschema 只在 schema 校验那步），")
    print("     所以'本机装过'不等于'别人也必须有' —— 上面的清单才是权威。")

    if args.json:
        op = Path(args.json)
        op.write_text(json.dumps({
            "python_min": "3.10",
            "python_checked": sys.version.split()[0],
            "third_party": {m: sorted(v) for m, v in third.items()},
            "stdlib_used": sorted(stdlib_used),
            "internal": sorted(internal),
            "dockerfiles": [d.relative_to(ROOT).as_posix() for d in dockers],
            "network_hosts": {h: sorted(v) for h, v in hosts.items()},
            "not_covered": ["Docker 可用性", "上游网络可达性", "磁盘空间", "操作系统/架构"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n清单 → {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
