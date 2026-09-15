#!/usr/bin/env python3
"""把 rubric 题的 provenance 转换并并入**主台账**（`ledger/items.jsonl`）。

为什么要并入而不是各搞一套
------------------------
如果第二支柱自带一套平行的溯源，就会出现：
  · 主台账的许可门禁（`scripts/audit_licenses.py`，R0–R11）**管不到它**
  · 同一个项目里两套"什么算合规"的标准，早晚会不一致

并入之后，rubric 题与 T1/T2 走**同一道门禁**：许可白名单、身份泄露、真值权威性
（R10/R11）全部一视同仁。

字段补全规则（rubric provenance 缺的 6 个）：
  · `task`           = "R"
  · `truth_type`     = "consensus"（逐题得分靠双标注 + 仲裁确立，不是单一权威来源）
  · `truth_note`     = 必填（审计器 R10：非 authoritative 真值必须说明来源）
  · `derivation`     = "rewritten"（情景是据原文改写的）
  · `review_status`  = 由复核结果决定：accept→reviewed / reject→rejected / 否则 pending
  · `created_at`     = 生成时间

用法：
    python3 to_master_ledger.py --items ../items/items.jsonl \
        [--provenance ../items/provenance.jsonl] [--verdicts ../items/review_verdicts.jsonl] \
        --out ../ledger/rubric_items.jsonl
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path


def load(path: Path | None) -> list[dict]:
    if not path or not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="rubric 题并入主台账")
    ap.add_argument("--items", required=True, help="题面文件（含 provenance，或配合 --provenance）")
    ap.add_argument("--provenance", help="拆分后的 provenance.jsonl（若题面里已剥掉）")
    ap.add_argument("--verdicts", help="人工复核结果 review_verdicts.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--created-at", help="覆盖 created_at（默认当前 UTC）")
    args = ap.parse_args(argv)

    items = load(Path(args.items))
    prov_rows = {p["item_id"]: p.get("provenance", {}) for p in load(Path(args.provenance))} \
        if args.provenance else {}
    verdicts = {v["item_id"]: v for v in load(Path(args.verdicts))} if args.verdicts else {}
    now = args.created_at or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    out_rows: list[dict] = []
    problems: list[str] = []
    stats = {"reviewed": 0, "pending": 0, "rejected": 0}

    for it in items:
        iid = it.get("item_id")
        prov = prov_rows.get(iid) or it.get("provenance") or {}
        if not prov:
            problems.append(f"{iid}: 找不到 provenance")
            continue

        v = verdicts.get(iid) or {}
        verdict = (v.get("verdict") or "").lower()
        if verdict == "accept":
            review_status = "reviewed"
        elif verdict == "reject":
            review_status = "rejected"
        else:
            review_status = "pending"
        stats[review_status] += 1

        row = dict(prov)                     # 12 个原有字段照抄，不改写
        row.update({
            "item_id": iid,
            "task": "R",
            "truth_type": "consensus",
            "truth_note": (
                "rubric 逐题得分靠双标注 + 分歧仲裁确立的共识，不是单一权威来源"
                + (f"；复核备注：{v.get('comment')}" if v.get("comment") else "")
            ),
            "derivation": "rewritten",
            "review_status": review_status,
            "created_at": now,
        })
        # 复核判定为 reject 的，不放进可公开台账
        if review_status == "rejected":
            row["visibility"] = "internal"
        out_rows.append(row)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"转换 {len(items)} 题 → 台账 {len(out_rows)} 条")
    print(f"  review_status：reviewed {stats['reviewed']} · pending {stats['pending']} · rejected {stats['rejected']}")
    print(f"  → {out}")
    if problems:
        print(f"\n❌ {len(problems)} 个问题：")
        for p in problems[:15]:
            print(f"   {p}")
        return 1
    print("\n下一步：用主台账的许可门禁验一遍")
    print(f"  python ../scripts/audit_licenses.py {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
