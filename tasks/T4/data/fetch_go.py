#!/usr/bin/env python3
"""取 GO 本体并生成 T4 的题面与真值。

设计依据：`tasks/T4/DESIGN.md`；许可依据：`research/T4_SOURCES.md`。

**真值不是写出来的，是算出来的。**
每个条目的真值由 `obo_parse.metrics_for()` 从 OBO 原文重算 ——
任何人都可以用同一份原文独立复算并推翻我们（原则 ②）。

⚠️ **选样规则：不加挑选。**
用**固定种子**随机抽样（`random.Random(SEED)`），
不挑"好看的"或不挑"判别力强的" —— 与 `make_pilot.py` 的原则一致。
种子写死，保证可复现。

⚠️ **必须记录版本**：`current.geneontology.org` 是**滚动别名**，
今天取到的是 `releases/2026-07-26`，将来会变。所以题面与真值都记录
`data-version` 与文件 `sha256` —— 否则"我们用的是哪一版"无法验证。

用法：
    python3 fetch_go.py --outdir .              # 取数 + 生成
    python3 fetch_go.py --outdir . --check      # 只核对已有文件
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from obo_parse import (OboError, cross_check_totals, find_roots,  # noqa: E402
                       metrics_for, parse_terms, usable_terms)

#: GO 官方滚动入口（无需凭据；见 research/T4_SOURCES.md §2）
URL = "http://current.geneontology.org/ontology/go-basic.obo"

#: 题池规模。**固定种子 + 随机抽样**（不挑选）
N_ITEMS = 30
SEED = 20260916

#: 只收这些 namespace 的 term（三个根各取一些，避免全是同一分支）
NAMESPACES = ("molecular_function", "biological_process", "cellular_component")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch(url: str = URL, timeout: int = 300) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "veribench-bio-t4"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main(argv: list[str] | None = None) -> int:
    """取数并生成 items/truth。

    ⚠️ 两个产物都用 `newline=\"\"` 写 —— 否则换行符随平台而变，
    而 `items.jsonl` 是 `record_image_digest.py` 的**构建输入**：
    字节变了 `source_sha256` 就变，同一条 pin 在 Windows/Linux 结论相反。
    （T2/T3 都栽过这个坑，见 `scripts/check_newline_hygiene.py`。）
    """
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="取 GO 本体并生成 T4 题面/真值")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--check", action="store_true", help="不下载：核对已有文件")
    ap.add_argument("--n", type=int, default=N_ITEMS)
    args = ap.parse_args(argv)

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    obo_p = out / "go-basic.obo"

    problems: list[str] = []
    if args.check:
        if not obo_p.is_file():
            print(f"❌ 缺 {obo_p}")
            return 1
        raw = obo_p.read_bytes()
    else:
        try:
            raw = fetch()
            obo_p.write_bytes(raw)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            print(f"❌ 取数失败：{type(e).__name__}: {e}")
            return 1

    text = raw.decode("utf-8", "replace")
    m_ver = re.search(r"^data-version:\s*(\S+)", text, re.M)
    data_version = m_ver.group(1) if m_ver else "unknown"
    file_hash = sha256(raw)

    terms = parse_terms(text)
    cross_check_totals(text, terms)          # 内部会在不一致时抛
    usable = usable_terms(terms)
    roots = set(find_roots(terms))

    print(f"OBO: {len(raw):,} B  data-version={data_version}")
    print(f"  term {len(terms):,}（非 obsolete {len(usable):,}）  根 {sorted(roots)}")

    #: 固定种子随机抽样（不加挑选）
    rng = random.Random(SEED)
    by_ns: dict[str, list[str]] = {ns: [] for ns in NAMESPACES}
    for gid, v in usable.items():
        if v["namespace"] in by_ns:
            by_ns[v["namespace"]].append(gid)
    for ns in by_ns:
        by_ns[ns].sort()
        rng.shuffle(by_ns[ns])

    #: 三个 namespace 轮转取，避免全落在同一分支
    picked: list[str] = []
    order = list(NAMESPACES)
    i = 0
    while len(picked) < args.n:
        ns = order[i % len(order)]
        if by_ns[ns]:
            picked.append(by_ns[ns].pop())
        elif all(not by_ns[x] for x in order):
            break
        i += 1
    picked = sorted(picked)

    items: list[dict] = []
    truths: list[dict] = []
    for gid in picked:
        try:
            m = metrics_for(terms, gid, roots)
        except OboError as e:
            # ⚠️ 解析失败**必须响亮**，不能静默跳过
            problems.append(f"{gid}: {e}")
            continue
        items.append({
            "item_id": f"T4-{gid}",
            "go_id": gid,
            "obo_sha256": file_hash,
            "obo_data_version": data_version,
            "question": (
                f"读取 GO 本体（{data_version}），对术语 {gid} 报告："
                "name、namespace、直接父节点个数（`is_a` 行数）、"
                "以及沿 `is_a` 到**任一**根的最短距离（depth_to_root，根本身为 0）。"
                "⚠️ 口径：**排除 `is_obsolete: true` 的术语**（它们既不作为题目，"
                "也不作为到达根的路径）。"
            ),
        })
        truths.append({"item_id": f"T4-{gid}", "go_id": gid, **m})

    (out / "items.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in items),
        encoding="utf-8", newline="")
    (out / "truth.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in truths),
        encoding="utf-8", newline="")

    print(f"生成 {len(items)} 条题 → {out / 'items.jsonl'} / {out / 'truth.jsonl'}")
    if problems:
        print()
        print(f"❌ {len(problems)} 处问题（**不许静默跳过**）：")
        for p in problems:
            print(f"  · {p}")
        return 1
    print("✅ 全部条目解析成功且通过交叉核对")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
