#!/usr/bin/env python3
"""按裁决文件纠正 candidates.jsonl 与各批次题目的 contains_human_data。

这次纠正的记录
--------------
错误：`candidates.jsonl` 把 27 篇**全部**标成 contains_human_data=true，
      包括蜜蜂转录组（PMC11900027）、大鼠心梗模型（PMC11900020）、
      叙述性综述（PMC11900017/28）。24 道题的 provenance 又照抄了它。

为什么长期没被发现：
  1. 该字段是**裸布尔**，没有任何可核对的痕迹；
  2. 审计器只声明它必填、从未使用它（无牙齿）；
  3. `precheck_items.py` 强制"与 candidates 一致"，把一个未核实的事实
     当成已验证的许可字段来锁，还把它写进"禁止编造"分支——于是纠正
     一个错误事实反而被拦下。

修法（三处一起动，缺一不可）：
  · 本脚本把裁决值写进 candidates + items，并加 human_data_basis 字段
  · 审计器新增 R12：必须有依据，且依据与布尔自洽
  · precheck 区分「许可判定字段」（强锁）与「事实判定字段」（核对裁决文件）

用法：
    python3 apply_human_data_fix.py --adjudication ../items/human_data_basis.json \
        --candidates ../items/candidates.jsonl \
        --items ../items/batch_1.jsonl ../items/batch_2.jsonl ... [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TRUE_BASES = {"human_subjects_primary", "human_biospecimen"}


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def dump(rows: list[dict], p: Path) -> None:
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="纠正 contains_human_data")
    ap.add_argument("--adjudication", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--items", nargs="*", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    adj = json.loads(Path(args.adjudication).read_text(encoding="utf-8"))["adjudication"]
    print(f"裁决文件：{len(adj)} 篇")
    for ref, a in adj.items():
        expect = a["basis"] in TRUE_BASES
        if expect != a["value"]:
            print(f"❌ {ref}: basis={a['basis']} 与 value={a['value']} 自相矛盾")
            return 1

    # --- candidates.jsonl ---
    cpath = Path(args.candidates)
    rows = load(cpath)
    n_fix = 0
    for r in rows:
        ref = r.get("pmcid") or r.get("source_ref")
        a = adj.get(ref)
        if not a:
            print(f"⚠️ candidates 中的 {ref} 不在裁决文件里，跳过")
            continue
        if r.get("contains_human_data") != a["value"]:
            n_fix += 1
        r["contains_human_data"] = a["value"]
        r["human_data_basis"] = a["basis"]
    print(f"\ncandidates.jsonl：{len(rows)} 条，纠正 {n_fix} 条 contains_human_data")
    if not args.dry_run:
        dump(rows, cpath)

    # --- 批次题目 ---
    total_fix = 0
    for ip in args.items:
        p = Path(ip)
        items = load(p)
        n = 0
        for it in items:
            prov = it.setdefault("provenance", {})
            ref = prov.get("source_ref")
            a = adj.get(ref)
            if not a:
                print(f"⚠️ {p.name}/{it.get('item_id')}: source_ref={ref} 不在裁决文件里")
                continue
            if prov.get("contains_human_data") != a["value"]:
                n += 1
            prov["contains_human_data"] = a["value"]
            prov["human_data_basis"] = a["basis"]
        total_fix += n
        print(f"{p.name}：{len(items)} 题，纠正 {n} 题")
        if not args.dry_run:
            dump(items, p)

    print(f"\n合计纠正：candidates {n_fix} 条 + 题目 {total_fix} 题")
    if args.dry_run:
        print("（--dry-run，未写盘）")
    else:
        print("已写盘。下一步：")
        print("  python ../scripts/audit_licenses.py --self-test")
        print("  python scripts/precheck_items.py --items <合并后的文件>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
