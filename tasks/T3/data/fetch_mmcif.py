#!/usr/bin/env python3
"""取 RCSB PDB 的 mmCIF 并生成 T3 的题面与真值。

设计依据：`tasks/T3/DESIGN.md`；许可与入口依据：`research/T3_SOURCES.md`。

**真值不是写出来的，是算出来的。**
每个条目的真值由 `mmcif_parse.metrics_from_cif()` 从 mmCIF 原文重算 ——
任何人都可以用同一份原文独立复算并推翻我们。这是本项目的原则 ②。

选条目规则（**不加挑选**，与 `make_pilot.py` 的原则一致）：
    取一个**预先固定**的 PDB ID 列表，按 ID 排序后处理。
不按"哪几条好看"来选 —— 为结果好看而选样正是本项目一直避免的事。
列表固定写死在 `PDB_IDS` 里，保证可复现（不用随机、不用"最新"）。

用法：
    python3 fetch_mmcif.py --outdir .            # 取数 + 生成 items/truth
    python3 fetch_mmcif.py --outdir . --check    # 只核对已有文件是否与原文一致
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from mmcif_parse import MmcifError, metrics_from_cif  # noqa: E402

#: RCSB 官方单条下载入口（无需 API key；见 research/T3_SOURCES.md §2）
URL = "https://files.rcsb.org/download/{pid}.cif"

#: **固定**的题池。选样规则：优先小体积（< 400 KB），
#: 覆盖不同链数/配体情况，但**不按判别力挑选**。
#: 顺序即 ID 升序，保证可复现。
PDB_IDS = [
    "1CRN",   # 单链，无配体（教科书级小条目）
    "1UBQ",   # 单链，泛素
    "1L2Y",   # 极小的设计肽（Trp-cage）
    "2GB1",   # 免疫球蛋白结合域
    "1VII",   # 绒毛蛋白片段
    "2LZM",   # 溶菌酶，单链 + 水
    "1LMB",   # lambda 阻遏蛋白
    "1FNA",   # 纤连蛋白域
    "5CYT",   # 细胞色素 c
    "1BPI",   # 胰蛋白酶抑制剂
    "1CTF",   # C 端片段
    "1PGB",   # 蛋白 G B 域
    "1SHG",   # SH3 域
    "1IGD",   # 蛋白 G
    "1TEN",   # 肌腱蛋白域
    "1HZ6",   # 设计蛋白
    "2CI2",   # 糜蛋白酶抑制剂 2
    "1STP",   # 链霉亲和素 + 配体
    "3AID",   # 多链
    "1ATP",   # 多链 + 配体
]


def fetch(pid: str, timeout: int = 90) -> str:
    req = urllib.request.Request(URL.format(pid=pid),
                                 headers={"User-Agent": "veribench-bio-t3"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="取 mmCIF 并生成 T3 题面/真值")
    ap.add_argument("--outdir", default=".", help="输出目录（默认本目录）")
    ap.add_argument("--check", action="store_true",
                    help="不下载：核对已有 mmcif 与 truth 是否一致")
    ap.add_argument("--ids", nargs="*", help="覆盖默认题池（调试用）")
    args = ap.parse_args(argv)

    out = Path(args.outdir)
    cif_dir = out / "mmcif"
    cif_dir.mkdir(parents=True, exist_ok=True)
    ids = args.ids or PDB_IDS

    items: list[dict] = []
    truths: list[dict] = []
    problems: list[str] = []

    for pid in ids:
        cf = cif_dir / f"{pid}.cif"
        try:
            if args.check:
                if not cf.is_file():
                    problems.append(f"{pid}: 缺 {cf.name}")
                    continue
                raw = cf.read_bytes()
                text = raw.decode("utf-8", "replace")
            else:
                text = fetch(pid)
                raw = text.encode("utf-8")
                cf.write_bytes(raw)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            problems.append(f"{pid}: 取数失败 {type(e).__name__}: {e}")
            continue

        try:
            m = metrics_from_cif(text)   # 内部含交叉核对
        except MmcifError as e:
            # ⚠️ 解析失败**必须响亮** —— 不能跳过当"这道题不存在"
            problems.append(f"{pid}: 解析失败 —— {e}")
            continue

        if m["ca_distance"] is None:
            problems.append(f"{pid}: 没有可用的 CA 对（第一条链 CA < 2 个）—— 该量无解")
            continue

        items.append({
            "item_id": f"T3-{pid}",
            "pdb_id": pid,
            "mmcif_file": f"mmcif/{pid}.cif",
            "mmcif_sha256": sha256(raw),
            "mmcif_bytes": len(raw),
            "question": (
                f"读取 {pid} 的 mmCIF 原文，报告："
                "ATOM 行数、HETATM 行数、链数（label_asym_id 去重）、"
                "ATOM 行的元素直方图、以及第一条链上前两个 CA 原子间的欧氏距离（Å，3 位小数）。"
            ),
        })
        truths.append({"item_id": f"T3-{pid}", "pdb_id": pid, **m})

    (out / "items.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in items), encoding="utf-8")
    (out / "truth.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in truths), encoding="utf-8")

    total = sum(i["mmcif_bytes"] for i in items)
    print(f"{'核对' if args.check else '取数'}完成：{len(items)} 条题"
          f"（mmCIF {total / 1e6:.1f} MB）")
    print(f"  题面 → {out / 'items.jsonl'}")
    print(f"  真值 → {out / 'truth.jsonl'}")
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
