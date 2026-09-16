#!/usr/bin/env python3
"""合并 v1.1 批次并逐项校验「只改了该改的」。

校验为什么必须这么严格
----------------------
前后对照的可信度取决于一件事：**除了 criteria 的锚点，别的什么都没变**。
如果 question 被顺手改了一个字、或 provenance 少了一个字段，
那么区分度的变化就不再能归因到"改写标准"了。

所以这里做**逐字段深比较**，而不是"看起来对"：
  · item_id / question / context / provenance / safety_review —— 必须逐字节相同
  · criterion_id 序列 —— 必须完全相同
  · anchors —— 必须齐 0/1/2
  · revision_note —— 改过的必须有、没改的必须没有（防止"声称改了其实没改"）
并交叉核对：改动清单 vs 实测缺陷清单 vs 噪声清单，报告**没动的缺陷**与**动了噪声**。

用法：
    python3 merge_v1.1.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

FROZEN = ["item_id", "question", "context", "provenance", "safety_review"]


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    v10 = {r["item_id"]: r for r in load(ROOT / "items" / "items.jsonl")}
    batches = sorted((ROOT / "items" / "v1.1").glob("batch_*.jsonl"))
    if len(batches) != 4:
        print(f"❌ 期望 4 个批次文件，实到 {len(batches)} 个：{[b.name for b in batches]}")
        return 1

    rows: list[dict] = []
    problems: list[str] = []
    for b in batches:
        for r in load(b):
            rows.append(r)
    rows.sort(key=lambda r: r["item_id"])

    if len(rows) != 24:
        print(f"❌ 合并后 {len(rows)} 题，期望 24")
        return 1
    ids = [r["item_id"] for r in rows]
    if ids != [f"R-{i:04d}" for i in range(1, 25)]:
        print(f"❌ item_id 不连续：{ids}")
        return 1

    changed: list[str] = []
    unchanged: list[str] = []
    for r in rows:
        o = v10[r["item_id"]]
        for f in FROZEN:
            if r.get(f) != o.get(f):
                problems.append(f"{r['item_id']}: 冻结字段 {f} 被改动")
        if r.get("rubric_version") != "1.1":
            problems.append(f"{r['item_id']}: 缺 rubric_version=1.1")

        oc = {c["criterion_id"]: c for c in o["criteria"]}
        nc = {c["criterion_id"]: c for c in r["criteria"]}
        if list(nc) != list(oc):
            problems.append(f"{r['item_id']}: criterion_id 序列变了 {list(oc)} → {list(nc)}")
            continue
        for cid, c in nc.items():
            for k in ("0", "1", "2"):
                if k not in (c.get("anchors") or {}):
                    problems.append(f"{r['item_id']}/{cid}: 缺 {k} 分锚点")
            note = c.get("revision_note")
            # 判定"是否改过"：标准正文或任一锚点文本变化
            really = (c.get("text") != oc[cid].get("text") or
                      (c.get("anchors") or {}) != (oc[cid].get("anchors") or {}))
            if really and not note:
                problems.append(f"{r['item_id']}/{cid}: 内容改了但没有 revision_note")
            if not really and note:
                problems.append(f"{r['item_id']}/{cid}: 内容没改却写了 revision_note")
            (changed if really else unchanged).append(f"{r['item_id']}/{cid}")

    # 交叉核对
    retest = json.loads((ROOT / "fixtures" / "answers" / "retest.json").read_text(encoding="utf-8"))
    defects = {f"{d['item_id']}/{d['criterion_id']}"
               for d in retest["criteria_detail"] if d["reproduced"]}
    noise = {f"{d['item_id']}/{d['criterion_id']}"
             for d in retest["criteria_detail"] if not d["reproduced"]}
    ch, un = set(changed), set(unchanged)

    print(f"合并 {len(rows)} 题 / {len(ch) + len(un)} 条标准")
    print(f"  改动 {len(ch)} 条 · 未改 {len(un)} 条")
    print()
    print(f"确认缺陷 {len(defects)} 条 → 其中已改 {len(defects & ch)}，**未改 {len(defects - ch)}**")
    if defects - ch:
        print(f"    ❌ 未改的缺陷：{sorted(defects - ch)}")
    print(f"噪声条目 {len(noise)} 条 → 其中被改 {len(noise & ch)}（{'结构性修复，可接受' if noise & ch else '无'}）")
    if noise & ch:
        print(f"    动过的噪声条目：{sorted(noise & ch)}")
    print()
    print(f"改动清单：{len(ch)} 条")
    for c in sorted(ch):
        print(f"   {c}")
    print()
    print(f"未改动的标准：{len(un)} 条")
    print("   " + "、".join(sorted(un)))

    if problems:
        print(f"\n❌ {len(problems)} 个问题：")
        for p in problems:
            print(f"   {p}")
        return 1

    out = ROOT / "items" / "items_v1.1.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="")
    print(f"\n✅ 校验通过 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
