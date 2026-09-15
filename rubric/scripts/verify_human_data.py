"""核对 `human_data_basis.json`（裁决）↔ candidates ↔ 题目 三方一致。

⚠️ 路径一律相对**本文件所在位置**解析，不用 cwd。
    原版是 `open("items/human_data_basis.json")` —— 只有当你**恰好在 `rubric/` 下**
    执行时才对；换任何别的目录就 FileNotFoundError。
    这一点由 `scripts/smoke_test_scripts.py` 的冒烟测试抓到（`--help` 直接崩）。
"""

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                  # rubric/
ITEMS = ROOT / "items"

T = {"human_subjects_primary", "human_biospecimen"}
adj = json.loads((ITEMS / "human_data_basis.json").read_text(encoding="utf-8"))["adjudication"]

bad = [k for k, v in adj.items() if (v["basis"] in T) != v["value"]]
print("裁决自洽:", "OK" if not bad else bad)

c = [json.loads(l) for l in (ITEMS / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
     if l.strip()]
print("candidates 键:", sorted(c[0].keys())[:6])
mis = []
for r in c:
    ref = r.get("source_ref") or r.get("pmcid")
    a = adj.get(ref)
    if a is None:
        mis.append(ref + ":不在裁决")
    elif r["contains_human_data"] != a["value"] or r.get("human_data_basis") != a["basis"]:
        mis.append(ref)
print("candidates 与裁决不符:", mis or "无")

items = [json.loads(l) for l in (ITEMS / "items.jsonl").read_text(encoding="utf-8").splitlines()
         if l.strip()]
mis2 = []
for i in items:
    ref = i["provenance"]["source_ref"]
    a = adj[ref]
    if i["provenance"]["contains_human_data"] != a["value"] or i["provenance"].get("human_data_basis") != a["basis"]:
        mis2.append(i["item_id"])
print("题目与裁决不符:", mis2 or "无")
print("题数:", len(items),
      "| true:", sum(1 for i in items if i["provenance"]["contains_human_data"]),
      "| false:", sum(1 for i in items if not i["provenance"]["contains_human_data"]))
print("唯一来源数:", len({i["provenance"]["source_ref"] for i in items}))

led_p = ROOT / "ledger" / "rubric_items.jsonl"
led = [json.loads(l) for l in led_p.read_text(encoding="utf-8").splitlines() if l.strip()]
print("台账条目:", len(led), "| 带 human_data_basis:", sum(1 for r in led if r.get("human_data_basis")))
