#!/usr/bin/env python3
"""把 staging（无序 item_id）装配成最终 items_draft.jsonl。

staging 每行是一个 item 对象，必须含 `_src`（PMC id）用于 provenance 填充；
`item_id` 由本脚本按文件顺序赋 R-0001、R-0002……保证连续且与 PMC 无关。
provenance 的许可字段一律从 candidates.jsonl 复制，禁止手写。

contains_human_data 例外：candidates.jsonl 对 27 篇一律填 True（其自身 notes 注明
"未人工判定，保守取 True"），已被项目级裁决文件 items/human_data_basis.json 认定为上游错误。
本项目另有 schema/rubric-item.schema.json，要求 contains_human_data 必须与 human_data_basis
自洽。因此：若存在 human_data_basis.json，则 contains_human_data / human_data_basis 取裁决值，
其余许可字段仍严格照抄 candidates.jsonl。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ITEMS_DIR = HERE.parent / "items"
CANDIDATES = ITEMS_DIR / "candidates.jsonl"
HUMAN_ADJ = ITEMS_DIR / "human_data_basis.json"

# 注意：contains_human_data 不在其中 —— 它由裁决文件（若有）决定，见模块 docstring
LICENSE_FIELDS = [
    "source_license_code", "license_spdx", "license_url", "retrieval_date",
    "redistribution_ok", "commercial_ok",
    "contains_restricted_data", "visibility",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", default=str(ITEMS_DIR / "_staging.jsonl"))
    ap.add_argument("--out", default=str(ITEMS_DIR / "items_draft.jsonl"))
    args = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    cands = {c["item_id"]: c for c in
             (json.loads(l) for l in CANDIDATES.read_text(encoding="utf-8").splitlines() if l.strip())}
    adj = {}
    if HUMAN_ADJ.exists():
        adj = json.loads(HUMAN_ADJ.read_text(encoding="utf-8")).get("adjudication", {})
        print(f"human_data 裁决文件：{HUMAN_ADJ.name}（{len(adj)} 篇）")
    else:
        print("⚠️ 未找到 human_data_basis.json —— contains_human_data 退回 candidates.jsonl 的保守值")
    staged = [json.loads(l) for l in Path(args.staging).read_text(encoding="utf-8").splitlines() if l.strip()]

    out_lines = []
    for n, it in enumerate(staged, 1):
        src = it.pop("_src")
        c = cands[src]
        it["item_id"] = f"R-{n:04d}"
        prov = {
            "source_type": "derived_from_paper",
            "source_ref": src,
            "source_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{src}/",
            "derivation_note": "据原文情景改写为去标识化审稿题；未复制原文句子",
        }
        for f in LICENSE_FIELDS:
            prov[f] = c[f]
        # contains_human_data / human_data_basis：优先裁决文件，其次 candidates.jsonl
        if src in adj:
            prov["contains_human_data"] = adj[src]["value"]
            prov["human_data_basis"] = adj[src]["basis"]
        else:
            prov["contains_human_data"] = c.get("contains_human_data")
            if c.get("human_data_basis"):
                prov["human_data_basis"] = c["human_data_basis"]
        it["provenance"] = prov
        it.setdefault("context", "")
        it.setdefault("safety_review", "not-applicable")
        # 字段顺序固定，便于人读
        ordered = {k: it[k] for k in
                   ("item_id", "question", "context", "criteria", "provenance", "safety_review")}
        out_lines.append(json.dumps(ordered, ensure_ascii=False))

    Path(args.out).write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"已写出 {len(out_lines)} 题 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
