#!/usr/bin/env python3
"""二分找出 gnomAD GraphQL 查询里哪一部分导致 HTTP 400。

已知：内联 `variant(variantId: "...", dataset: gnomad_r4) { variant_id exome { ac an af } }` → 200。
脚本里那条（变量 + genome + joint + populations）→ 400。
逐个字段加上去，定位是哪一步炸的。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

ENDPOINT = "https://gnomad.broadinstitute.org/api"
UA = "VeriBench-Bio/0.2 (open evaluation dataset; allele-frequency only)"
VID = "13-20189481-A-G"

CASES: list[tuple[str, str, dict]] = [
    ("1  内联 · 仅 exome{ac an af}",
     'query { variant(variantId: "%s", dataset: gnomad_r4) { variant_id exome { ac an af } } }' % VID, {}),
    ("2  内联 · + genome{af}",
     'query { variant(variantId: "%s", dataset: gnomad_r4) { variant_id exome { af } genome { af } } }' % VID, {}),
    ("3  内联 · + joint{af}",
     'query { variant(variantId: "%s", dataset: gnomad_r4) { variant_id joint { af } } }' % VID, {}),
    ("4  内联 · + joint{populations{id af}}",
     'query { variant(variantId: "%s", dataset: gnomad_r4) { variant_id joint { populations { id af } } } }' % VID, {}),
    ("5  变量 $id: String!",
     "query V($id: String!) { variant(variantId: $id, dataset: gnomad_r4) { variant_id exome { af } } }",
     {"id": VID}),
    ("6  变量 $id: String! + dataset 也作变量",
     "query V($id: String!, $ds: DatasetId!) { variant(variantId: $id, dataset: $ds) { variant_id exome { af } } }",
     {"id": VID, "ds": "gnomad_r4"}),
    ("7  脚本里那条（原样）",
     "query V($id: String!) { variant(variantId: $id, dataset: gnomad_r4) "
     "{ variant_id exome { af } genome { af } joint { af populations { id af } } } }",
     {"id": VID}),
]


def post(query: str, variables: dict) -> tuple[int, str]:
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, r.read().decode("utf-8")[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"


for label, q, v in CASES:
    code, body = post(q, v)
    print(f"[{code}] {label}")
    print(f"    {body[:250]}")
