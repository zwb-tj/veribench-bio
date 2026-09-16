#!/usr/bin/env python3
"""检查**标注表有没有泄露答案档位** —— 即"盲评到底盲没盲"。

背景（2026-09 实测发现的真实缺陷）
--------------------------------
试点标注表把三份回答标成 `BLIND-weak` / `BLIND-medium` / `BLIND-strong`，
而 `README_FOR_ANNOTATOR.md` 写着：

> 这只是三个不同的回答，**编号本身不告诉你哪份好**。

**这句话与事实不符。** `weak` / `medium` / `strong` 本身就是质量标签，
"编号"明明白白告诉了标注者哪份"应该"得高分。

更要命的是它还**与 rubric 的核心规则直接冲突**。同一份说明书里写着：

> **不要被长度影响。** 写得长不等于写得好；堆术语但没说清，属于没做到。

而实测这三档的**长度严格递增**（175 / 207 / 360 字符）。

为什么这会毁掉试点
------------------
试点要测的是"**人能不能一致地读这套标准**"，那个一致性（κ）是后面
判断"AI 裁判准不准"的**分母（人类天花板）**。但如果我们把档位写在标签里：
  · 标注者会不自觉地对齐标签 → κ **假性偏高**
  · 于是人类天花板虚高 → judge 的"相对上限"被压低 → **结论反了**
  · 而这一切不会有任何东西报警：数据看起来完全正常

正确的做法（判官侧一直是对的）
------------------------------
`fixtures/answers/judge_blind/_mapping.json` 用的是**随机 12 位十六进制**
（如 `7512fd311247`）+ 一份独立映射表（blind_id → item_id, level）。
**裁判看到的就是随机 id。人类这边应该用同一套。**

用法
----
    python3 check_annotation_blinding.py                    # 查试点 + 全套
    python3 check_annotation_blinding.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: 档位词 —— 出现在 answer_id 里就是泄露
LEVEL_WORDS = ("weak", "medium", "strong", "good", "bad", "poor", "best", "worst")

#: 合法的盲 id：12 位十六进制（与 judge_blind/_mapping.json 同构）
BLIND_RE = re.compile(r"^[0-9a-f]{12}$")


def find_answer_id_files() -> list[Path]:
    """找出**发给标注者的**文件 —— 只认 `ann_*.jsonl`。

    为什么不用"含 answer_id 就算"：`answers_flat.jsonl` 这类作答源文件
    带的是 `model` 字段（必须记档位），不是给标注者的，查了就是误报。
    **判据要比事实更精确** —— 宁可窄，也不要制造噪音。
    """
    out: list[Path] = []
    for p in ROOT.glob("annotation/**/ann_*.jsonl"):
        if p.is_file():
            out.append(p)
    return sorted(set(out))


def _rel(p: Path) -> str:
    """相对路径；**在仓库外时退回绝对路径**。

    ⚠️ `Path.relative_to` 对仓库外的路径会抛 ValueError ——
    自检用的临时目录正好在仓库外，于是自检直接崩了。
    （这个坑本项目在 `verify_upload_preflight.py` 里已经踩过一次。）
    """
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def audit(path: Path) -> list[str]:
    """返回该文件的泄露问题列表（空 = 没问题）。

    ⚠️ **只查 `answer_id`，不查 `model`。** 两者角色不同：

      · `model`（在 `answers_flat.jsonl` 这类**作答源文件**里）**必须**记录档位
        （`BLIND-weak`）—— 那是流水线自己的元数据，用来事后把 id 对回档位。
        它**不给标注者看**，所以不是泄露。
      · `answer_id`（在 `ann_*.jsonl` 这类**发给标注者的文件**里）必须是随机盲 id。
        它一旦含 `weak`/`strong`，标注者就知道哪份"应该"得高分。

    第一版把两者一起查，于是对源文件**误报** ——
    而误报会让人干脆把检查关掉，比漏报更糟。**判据要比事实更精确。**
    """
    probs: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return [f"读不了：{e}"]
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        aid = r.get("answer_id")
        if aid is None:
            continue
        s = str(aid)
        hit = [w for w in LEVEL_WORDS if w in s.lower()]
        if hit:
            probs.append(f"{_rel(path)}:{i} answer_id={s!r} 含档位词 {hit}")
    # 只报每种 id 一次，避免同一问题刷屏
    seen: set[str] = set()
    dedup: list[str] = []
    for p in probs:
        key = p.split("answer_id=")[-1].split(" 含档位词")[0]
        if key in seen:
            continue
        seen.add(key)
        dedup.append(p)
    return dedup


def self_test() -> int:
    """负向测试：**已知泄露必须被抓到，干净的不许误报。**"""
    import tempfile

    cases = [
        # (answer_id, 期望被抓)
        ("BLIND-weak", True),
        ("BLIND-medium", True),
        ("BLIND-strong", True),
        ("weak", True),
        ("7512fd311247", False),   # 判官侧一直在用的正确形式
        ("67cd84bf747d", False),
        ("BLIND-a1b2c3d4e5f6", False),  # 有前缀但无档位词 —— 可接受
    ]
    print("=== 标注盲评自检 ===")
    ok = True
    for aid, should_flag in cases:
        flagged = any(w in aid.lower() for w in LEVEL_WORDS)
        good = flagged == should_flag
        ok = ok and good
        print(f"  {'✅' if good else '❌'} {aid!r}: "
              f"{'被抓' if flagged else '放行'}（期望{'被抓' if should_flag else '放行'}）")

    # 端到端：在临时目录里造一个泄露文件与一个干净文件
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        leak = t / "leak.jsonl"
        leak.write_text(json.dumps({"item_id": "R-1", "answer_id": "BLIND-strong",
                                    "criterion_id": "c1", "score": None}) + "\n",
                        encoding="utf-8", newline="")
        clean = t / "clean.jsonl"
        clean.write_text(json.dumps({"item_id": "R-1", "answer_id": "7512fd311247",
                                     "criterion_id": "c1", "score": None}) + "\n",
                         encoding="utf-8", newline="")
        got_leak = bool(audit(leak))
        got_clean = bool(audit(clean))
        for label, cond in (("泄露文件被抓到", got_leak), ("干净文件不误报", not got_clean)):
            ok = ok and cond
            print(f"  {'✅' if cond else '❌'} {label}")

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="标注盲评泄漏检查")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    files = find_answer_id_files()
    if not args.quiet:
        print(f"扫描 {len(files)} 个含 answer_id/model 的文件")

    all_probs: dict[str, list[str]] = {}
    for p in files:
        probs = audit(p)
        if probs:
            all_probs[str(p.relative_to(ROOT))] = probs

    if all_probs:
        print()
        print("❌ **标注表泄露了答案档位** —— 这会让 κ 假性偏高：")
        for f, probs in all_probs.items():
            print(f"  {f}")
            for x in probs[:4]:
                print(f"    · {x.split(':', 1)[-1].strip()}")
        print()
        print("  正确做法：用**随机盲 id** + 一份独立映射表。")
        print("  判官侧已经是这么做的（`fixtures/answers/judge_blind/_mapping.json`），")
        print("  人类标注表应当**复用同一套 id**。")
        print()
        print("  ⚠️ 为什么严重：试点测的是「人能不能一致地读标准」，")
        print("     那个 κ 是判断「AI 裁判准不准」的**分母**。")
        print("     标签泄露 → κ 假性偏高 → 分母虚高 → **结论会反过来**，")
        print("     而且数据看起来完全正常，没有任何东西会报警。")
        return 1

    print(f"✅ {len(files)} 个文件均未泄露答案档位")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
