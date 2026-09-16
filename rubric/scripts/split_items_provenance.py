#!/usr/bin/env python3
"""把 rubric 题拆成 **公开题面** 与 **私有溯源** 两个文件。

为什么必须拆
-----------
`rubric-item.schema.json` 里带 `provenance`（含 `source_ref` = PMC ID）。
如果原样发布，**"这题出自哪篇论文"就是公开的** —— 模型可以顺着去读原文，
而开放题的上下文与原文高度相关，等于变相给答案。

与 T2 同一个纪律：**公开的是题目，不是题目的来历。**

  items.jsonl        ← 公开：item_id / question / context / criteria / safety_review
  provenance.jsonl   ← 私有：item_id / provenance（含 PMC ID、DOI）
  mapping.jsonl      ← 私有：item_id ↔ 源论文（审计用，绝不公开）

用法：
    python3 split_items_provenance.py --items ../items/items_draft.jsonl --outdir ../items
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PUBLIC_FIELDS = ("item_id", "question", "context", "criteria", "safety_review")
REQUIRED_PROV = ("source_type", "source_ref", "license_spdx", "redistribution_ok", "visibility")


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="拆分 rubric 题面 / 溯源")
    ap.add_argument("--items", required=True, help="含 provenance 的完整题目文件")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args(argv)

    src = Path(args.items)
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    seen: set[str] = set()
    public, prov, mapping = [], [], []

    for r in rows:
        iid = r.get("item_id")
        if not iid:
            problems.append("存在缺 item_id 的条目")
            continue
        if iid in seen:
            problems.append(f"{iid}: item_id 重复")
        seen.add(iid)

        p = r.get("provenance") or {}
        for f in REQUIRED_PROV:
            if f not in p:
                problems.append(f"{iid}: provenance 缺字段 {f}")

        # 公开文件**只保留白名单字段** —— 任何多余字段都可能是泄露源
        extra = set(r) - set(PUBLIC_FIELDS)
        if extra:
            problems.append(f"{iid}: 条目含非公开字段 {sorted(extra)}（会被剥离）")
        public.append({k: r.get(k) for k in PUBLIC_FIELDS if k in r})
        prov.append({"item_id": iid, "provenance": p})
        mapping.append({
            "item_id": iid,
            "source_ref": p.get("source_ref"),
            "source_url": p.get("source_url"),
            "license_spdx": p.get("license_spdx"),
            "license_url": p.get("license_url"),
        })

    def dump(path: Path, data: list[dict]) -> None:
        with path.open("w", encoding="utf-8", newline="") as fh:
            for d in data:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    dump(out / "items.jsonl", public)
    dump(out / "provenance.jsonl", prov)
    dump(out / "mapping.jsonl", mapping)

    print(f"读入 {len(rows)} 条 → 公开题面 {len(public)} / 私有溯源 {len(prov)}")
    print(f"  {out / 'items.jsonl'}        ← 公开（只含 {', '.join(PUBLIC_FIELDS)}）")
    print(f"  {out / 'provenance.jsonl'}   ← 私有（含 PMC ID / DOI）")
    print(f"  {out / 'mapping.jsonl'}      ← 私有（审计映射）")
    if problems:
        print(f"\n发现 {len(problems)} 个问题：")
        for p in problems[:20]:
            print(f"  ⚠️ {p}")
        # 非公开字段只是被剥离，不算失败；重复 ID / 缺溯源字段算失败
        fatal = [p for p in problems if "非公开字段" not in p]
        return 1 if fatal else 0
    print("\n✅ 拆分完成，无问题")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
