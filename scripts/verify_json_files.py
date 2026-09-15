#!/usr/bin/env python3
"""全仓 JSON / JSONL 能不能解析？—— 一条"最低限度"的检查。

为什么需要它
------------
2026-09，我在给 `scripts/not_published.json` 加一条说明时，在 JSON 字符串里
用了 **ASCII 双引号**（`证明"枚举式登记"这个做法…`），把文件写坏了。
这是**同一个错误在本项目里的第 9 次**（前 8 次都在 Python 中文串里）。

当时的发现过程纯属运气：下一个脚本刚好要读这个文件才炸。
**没有任何检查在守着"JSON 文件本身是不是合法 JSON"。**

而这类错误极其恶劣：
  · 它不会在编辑时被发现（JSON 没有 lint 步骤）
  · 它会让**所有**读该文件的工具在**运行时**崩掉
  · 而 `not_published.json` 是 `clean_room_check` 与 `verify_doc_links` 的共享真源 ——
    它坏了，等于"什么算不该发布"这个判断同时失效

因此加这一条。它很笨（就是挨个 `json.loads`），但**笨检查守住的正是最贵的错误**。

范围
----
扫仓库里所有 `*.json` 与 `*.jsonl`。跳过：
  · `.git` / `__pycache__` / 运行期数据目录（`_data` / `_cache` / `_work` / `_artifacts`）
  · 上游原文目录（`rubric/items/sources` —— 那是别人的论文，不是我们的 JSON）
  · 已知的夹具（`_fixtures` 里故意放坏数据的用例由各自的负向测试覆盖）

对 `*.jsonl`：**逐行**解析，并在报错时给出**行号**。行号很关键 ——
T2 的 items.jsonl 有 4,726 行，只说"解析失败"等于没说。

用法
----
    python3 verify_json_files.py
    python3 verify_json_files.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: 不扫的目录片段（运行期产物 / 上游原文 / 缓存）
SKIP_PARTS = {
    ".git", "__pycache__", "node_modules", "_artifacts", "_scratch", "_cache",
    "_work", "_work_backup", "_data", "sources", "sources_trunc20000",
    "alternate", "judge_out", "judge_out_run1", "judge_out_run2",
    "manip_out_run1", "manip_out_run2", "judge_outputs", "_fixtures",
    "rotation", "public", "baseline", "baseline_public",
}

#: 体积上限：超过就不解析（避免把 200 MB 的上游数据读进来）。
#: 明确记录跳过，不静默略过。
MAX_BYTES = 12 * 1024 * 1024


def candidates() -> tuple[list[Path], list[tuple[Path, int]]]:
    files: list[Path] = []
    skipped_big: list[tuple[Path, int]] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in (".json", ".jsonl"):
            continue
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > MAX_BYTES:
            skipped_big.append((p, size))
            continue
        files.append(p)
    return sorted(files), skipped_big


def check_file(p: Path) -> list[str]:
    """返回问题列表（空 = 该文件没问题）。"""
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{p.relative_to(ROOT).as_posix()}: 读不出来（{type(exc).__name__}）"]

    rel = p.relative_to(ROOT).as_posix()
    problems: list[str] = []
    if p.suffix == ".json":
        try:
            json.loads(text)
        except ValueError as exc:
            # 给出**行列**，方便直接定位
            line = getattr(exc, "lineno", None)
            col = getattr(exc, "colno", None)
            loc = f"（第 {line} 行第 {col} 列）" if line else ""
            problems.append(f"{rel}{loc}: {exc}")
        return problems

    # .jsonl —— 逐行，报行号
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except ValueError as exc:
            problems.append(f"{rel} 第 {i} 行: {exc}")
            if len(problems) >= 5:      # 单个文件最多报 5 条，避免刷屏
                problems.append(f"{rel}: （还有更多，已截断）")
                break
    return problems


def self_test() -> int:
    """负向测试：证明坏 JSON 会被抓到，且**报出正确行号**。"""
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="jsoncheck-"))
    global ROOT  # noqa: PLW0603
    real_root = ROOT
    cases = [
        ("合法 .json", "a.json", '{"k": "v"}', 0),
        ("我犯过的那种错：串里用 ASCII 双引号",
         "b.json", '{"k": "证明"枚举"不可靠"}', 1),
        ("缺逗号", "c.json", '{"a": 1 "b": 2}', 1),
        ("合法 .jsonl", "d.jsonl", '{"a":1}\n{"a":2}\n', 0),
        ("jsonl 第 3 行坏掉", "e.jsonl", '{"a":1}\n{"a":2}\nNOT JSON\n', 1),
    ]
    ok = True
    for name, fname, content, want in cases:
        p = tmp / fname
        p.write_text(content, encoding="utf-8")
        ROOT = tmp                                   # 让 relative_to 能算
        probs = check_file(p)
        got = len(probs)
        passed = (got > 0) == (want > 0)
        if not passed:
            ok = False
        print(f"  {'✅' if passed else '❌'} {name}: 报 {got} 条，期望{'有' if want else '无'}"
              + (f"  → {probs[0][:78]}" if probs else ""))
    # 行号必须准
    p = tmp / "f.jsonl"
    p.write_text('{"a":1}\n\n{"a":2}\nBROKEN\n', encoding="utf-8")
    ROOT = tmp
    probs = check_file(p)
    line_ok = bool(probs) and "第 4 行" in probs[0]
    if not line_ok:
        ok = False
    print(f"  {'✅' if line_ok else '❌'} 行号准确: {probs[0][:70] if probs else '（无输出）'}")
    ROOT = real_root
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="全仓 JSON / JSONL 解析检查")
    ap.add_argument("--self-test", action="store_true", help="跑的负向测试，证明检查会失败")
    ap.add_argument("--show-ok", action="store_true", help="连通过的文件也列出来")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    files, skipped_big = candidates()
    all_problems: list[str] = []
    for p in files:
        probs = check_file(p)
        all_problems.extend(probs)
        if args.show_ok:
            print(f"  {'✅' if not probs else '❌'} {p.relative_to(ROOT).as_posix()}")

    print(f"扫描 {len(files)} 个 JSON/JSONL 文件")
    if skipped_big:
        print(f"跳过 {len(skipped_big)} 个超过 {MAX_BYTES // 1024 // 1024} MB 的文件"
              "（**明说跳过，不静默略过**）：")
        for p, sz in skipped_big[:5]:
            print(f"   · {p.relative_to(ROOT).as_posix()}（{sz / 1e6:.1f} MB）")

    # ⚠️ 一个文件都没扫到也必须失败：那说明扫描逻辑坏了，通过是假的。
    if not files:
        print("❌ 一个文件都没扫到 —— 扫描清单或过滤条件坏了，不能算通过")
        return 1
    if all_problems:
        print(f"\n❌ {len(all_problems)} 处 JSON 解析失败：")
        for pr in all_problems[:25]:
            print("   " + pr)
        if len(all_problems) > 25:
            print(f"   …（共 {len(all_problems)} 条，已截断）")
        print("\n**JSON 文件坏掉会让读它的工具在运行时崩 —— 而崩的时机往往是别人 clone 之后。**")
        return 1
    print("✅ 全部可解析")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
