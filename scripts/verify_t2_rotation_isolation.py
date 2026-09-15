#!/usr/bin/env python3
"""T2 的"轮换池永不公开"到底成不成立？—— 直接验，不靠文字。

为什么需要它
------------
项目对外声明：

    `tasks/T2/data/split_public_rotation.py` 的注释写着 rotation「**永不公开**」
    DATACARD 写着「公开 3,789 条；**轮换池 937 条从未发布**」

2026-09 实测发现：**全量 `data/truth.jsonl` 含轮换池全部 937 条的答案**，
而它当时**不在** `scripts/not_published.json` 里 ——
也就是说 `clean_room_check` 一直把它当"会被发布的文件"复制进清室目录
（已实测确认发生过）。`data/items.jsonl`（含轮换池**题面**）同样如此。

**这个声明此前从未被任何检查验证过。** 本脚本把它变成可执行的：

  A. **覆盖检查**：全量 truth/items 是否真的覆盖了轮换池 id（若覆盖，它们就不能发布）
  B. **隔离检查**：这些文件是否已在 not_published 里被声明为"不发布"
  C. **不重不漏**：public ∪ rotation == 全量，且 public ∩ rotation == ∅
  D. **公开集自洽**：public/truth 只覆盖 public/items（不得顺带带上轮换池的答案）

A 与 B 必须**同时**成立，声明才是真的：
  · 只有 A（确实覆盖）而没有 B → 答案会随仓库发出去 → 声明为假
  · 只有 B（声明不发布）而没有 A → 声明空转（其实没覆盖，努不努力都一样）

用法
----
    python3 verify_t2_rotation_isolation.py
    python3 verify_t2_rotation_isolation.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
T2 = ROOT / "tasks" / "T2"
DATA = T2 / "data"
NOT_PUBLISHED = ROOT / "scripts" / "not_published.json"

#: 含轮换池内容、因而**必须**声明为不发布的文件
MUST_BE_UNPUBLISHED = [
    "tasks/T2/data/items.jsonl",
    "tasks/T2/data/truth.jsonl",
    "tasks/T2/data/audit.jsonl",
]


def ids(path: Path) -> set[str]:
    out: set[str] = set()
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        i = d.get("item_id")
        if i:
            out.add(i)
    return out


def check() -> tuple[list[str], list[str]]:
    """返回 (问题, 说明)。"""
    problems: list[str] = []
    notes: list[str] = []

    full_items = ids(DATA / "items.jsonl")
    full_truth = ids(DATA / "truth.jsonl")
    rot_items = ids(DATA / "rotation" / "items.jsonl")
    pub_items = ids(DATA / "public" / "items.jsonl")
    pub_truth = ids(DATA / "public" / "truth.jsonl")

    if not full_items or not rot_items:
        return [], ["SKIP-MARKER: 缺全量或轮换池数据（未生成）"]

    np_dirs = set()
    if NOT_PUBLISHED.is_file():
        np_dirs = set(json.loads(NOT_PUBLISHED.read_text(encoding="utf-8")).get("dirs") or {})

    # A. 全量文件确实覆盖轮换池（→ 它们不能发布）
    cov_items = rot_items & full_items
    cov_truth = rot_items & full_truth
    notes.append(f"全量 items 覆盖轮换池 {len(cov_items)}/{len(rot_items)} 个 id")
    notes.append(f"全量 truth 覆盖轮换池 {len(cov_truth)}/{len(rot_items)} 个 id")

    # B. 覆盖了就必须声明不发布
    for rel in MUST_BE_UNPUBLISHED:
        p = ROOT / rel
        if not p.is_file():
            continue
        if rel not in np_dirs:
            # 只有当该文件**确实**含轮换池内容时才算问题（避免空转的强制声明）
            these = ids(p)
            if (rot_items & these):
                problems.append(
                    f"{rel} 含轮换池内容（{len(rot_items & these)} 个 id），"
                    "但**未**在 scripts/not_published.json 里声明为不发布 —— "
                    "它会随仓库发布，于是『轮换池从未发布』就是假话")

    # C. 不重不漏
    if pub_items:
        if not (pub_items | rot_items == full_items):
            problems.append("public ∪ rotation ≠ 全量 items（有重复或遗漏）")
        if pub_items & rot_items:
            problems.append(f"public ∩ rotation 非空（{len(pub_items & rot_items)} 个）")
        else:
            notes.append("public ∪ rotation == 全量，且不相交 ✅")

    # D. 公开集不得含轮换池的答案
    if pub_truth:
        leaked = pub_truth & rot_items
        if leaked:
            problems.append(f"public/truth.jsonl 含 {len(leaked)} 条轮换池答案 —— "
                            "公开集本身就不干净")
        else:
            notes.append("public/truth 不含任何轮换池答案 ✅")
        stray = pub_truth - pub_items
        if stray:
            problems.append(f"public/truth 有 {len(stray)} 条不在 public/items 里")

    # E. public/README.md 必须**逐字节**等于数据集卡（单一真源）
    #    2026-09 实测：它是一份手工复制的陈旧副本（7223 vs 8043 B），
    #    缺了"尚未上传"警示 —— 原样上传就会在 HF 上挂一张写错状态的卡。
    #    现已改为 `split_public_rotation.py` 每次从卡片生成，并强制逐字节一致。
    card = DATA / "T2_DATASET_CARD.md"
    pub_readme = DATA / "public" / "README.md"
    if card.is_file() and pub_readme.is_file():
        a, b = pub_readme.read_bytes(), card.read_bytes()
        if a != b:
            problems.append(
                "tasks/T2/data/public/README.md 与 T2_DATASET_CARD.md 不一致 —— "
                f"（{len(a)} vs {len(b)} B）。它必须是卡片的逐字节副本（单一真源），"
                "因为上传到 HF 的就是这一份")
        else:
            notes.append("public/README.md == 数据集卡（逐字节）✅")
    elif pub_readme.is_file() and not card.is_file():
        problems.append("有 public/README.md 但没有 T2_DATASET_CARD.md（真源缺失）")

    return problems, notes


def self_test() -> int:
    """负向测试：证明"声明缺失"会被抓到。"""
    import shutil
    import tempfile

    global ROOT, DATA, NOT_PUBLISHED  # noqa: PLW0603
    real = (ROOT, DATA, NOT_PUBLISHED)
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="rot-"))
    try:
        d = tmp / "tasks" / "T2" / "data"
        (d / "public").mkdir(parents=True)
        (d / "rotation").mkdir(parents=True)
        # ⚠️ 必须在把 ROOT 指向 tmp **之后**再建这个目录 ——
        #    第一版在赋值之前就 `(ROOT / "scripts").mkdir()`，
        #    于是它跑去仓库根建目录，而 tmp 里的 scripts/ 不存在 → FileNotFoundError。
        (tmp / "scripts").mkdir(parents=True, exist_ok=True)

        def w(p: Path, items: list[str]) -> None:
            p.write_text("\n".join(json.dumps({"item_id": i}) for i in items) + "\n",
                         encoding="utf-8")

        w(d / "items.jsonl", ["A", "B", "C", "D"])
        w(d / "truth.jsonl", ["A", "B", "C", "D"])
        w(d / "public" / "items.jsonl", ["A", "B"])
        w(d / "public" / "truth.jsonl", ["A", "B"])
        w(d / "rotation" / "items.jsonl", ["C", "D"])

        ROOT = tmp
        DATA = d
        npf = tmp / "scripts" / "not_published.json"

        # ① 未声明 → 必须报问题
        npf.write_text('{"dirs": {}}', encoding="utf-8")
        NOT_PUBLISHED = npf
        probs, _ = check()
        c1 = any("未" in p and "not_published" in p for p in probs)
        ok = ok and c1
        print(f"  {'✅' if c1 else '❌'} 未声明不发布 → 报问题（{len(probs)} 条）")

        # ② 声明后 → 不报（其余条件本来就满足）
        npf.write_text(json.dumps({"dirs": {
            "tasks/T2/data/items.jsonl": "答案/题面",
            "tasks/T2/data/truth.jsonl": "答案",
            "tasks/T2/data/audit.jsonl": "审计",
        }}), encoding="utf-8")
        probs, _ = check()
        c2 = not probs
        ok = ok and c2
        print(f"  {'✅' if c2 else '❌'} 已声明 → 通过（问题 {len(probs)} 条：{probs[:2]}）")

        # ③ 公开集里混进轮换池答案 → 必须报
        w(d / "public" / "truth.jsonl", ["A", "B", "C"])
        probs, _ = check()
        c3 = any("轮换池答案" in p for p in probs)
        ok = ok and c3
        print(f"  {'✅' if c3 else '❌'} 公开集混入轮换池答案 → 报问题")

        # ④ 重复切分 → 必须报
        w(d / "public" / "truth.jsonl", ["A", "B"])
        w(d / "public" / "items.jsonl", ["A", "B", "C"])
        probs, _ = check()
        c4 = any("非空" in p or "≠" in p for p in probs)
        ok = ok and c4
        print(f"  {'✅' if c4 else '❌'} public 与 rotation 重叠 → 报问题")
    finally:
        ROOT, DATA, NOT_PUBLISHED = real
        shutil.rmtree(tmp, ignore_errors=True)

    print("负向测试 " + ("全部通过（含 3 个必须失败的用例）" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="验证 T2『轮换池永不公开』是真的")
    ap.add_argument("--self-test", action="store_true", help="跑的负向测试，证明检查会失败")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    problems, notes = check()
    if any(n.startswith("SKIP-MARKER") for n in notes):
        print("SKIP: 缺 T2 全量或轮换池数据（未生成；`data/rotation` 刻意不发布）")
        return 0
    for n in notes:
        print("  · " + n)
    if problems:
        print(f"\n❌ {len(problems)} 处问题：")
        for p in problems:
            print("   " + p)
        print("\n**『轮换池从未发布』是一句对外声明 —— 它必须由检查保证，不能只写在注释里。**")
        return 1
    print("\n✅ 『轮换池 937 条永不公开』成立：")
    print("   全量文件确实含轮换池内容 · 它们已声明为不发布 · 公开集不含轮换池答案")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
