#!/usr/bin/env python3
"""取候选文章的正文（用于据此撰写 rubric 题）。

为什么单独一个脚本
----------------
`scripts/pmc_ingest.py` 只抓了 XML 用于**解析许可版本**，正文没有留档。
撰写「审稿式开放题」必须读正文，所以这一步单独做，并且：

1. **记录官方 md5**（PMC 的 s3 路径自带 `?md5=...`）—— 否则取回来的正文无法核实
2. **只处理许可白名单内的条目**（回读 `candidates.jsonl` 的 `license_spdx`）
3. 正文落在 `items/sources/`，**该目录不进公开仓库**（虽然 CC BY 允许再分发，
   但我们没有必要把全文散出去 —— 公开的是题目，不是别人的论文）

用法：
    python3 fetch_source_text.py --candidates ../items/candidates.jsonl \
        --outdir ../items/sources [--max-chars 20000] [--limit 5]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

S3_BASE = "https://pmc-oa-opendata.s3.amazonaws.com"
UA = "VeriBench-Bio/0.2 (open evaluation dataset; PMC OA CC BY sources)"

ALLOWED_SPDX = {"CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "CC-BY-2.0", "PUBLIC-DOMAIN"}


def http_get(url: str, limit: int | None = None, retries: int = 4) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(limit) if limit else r.read()
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:200]
            except Exception:  # noqa: BLE001
                pass
            if exc.code in (403, 404):
                raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
            last = RuntimeError(f"HTTP {exc.code}: {body}")
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET 失败 {url}: {last}")


def find_meta_key(pmcid: str) -> str | None:
    raw = http_get(f"{S3_BASE}/?list-type=2&prefix=metadata/{pmcid}.&max-keys=10")
    keys = re.findall(r"<Key>([^<]+)</Key>", raw.decode("utf-8", "replace"))
    return keys[0] if keys else None


def s3_to_https(uri: str) -> tuple[str, str | None]:
    """s3://pmc-oa-opendata/<path>?md5=xxx  →  (https url, md5)"""
    if not uri.startswith("s3://pmc-oa-opendata/"):
        raise ValueError(f"非预期 s3 路径: {uri}")
    rest = uri[len("s3://pmc-oa-opendata/"):]
    md5 = None
    if "?" in rest:
        rest, q = rest.split("?", 1)
        m = re.search(r"md5=([0-9a-f]{32})", q)
        md5 = m.group(1) if m else None
    return f"{S3_BASE}/{rest}", md5


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="取 PMC OA 候选正文")
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--max-chars", type=int, default=0,
                    help="保留的正文上限；0 = 不截断（默认）。⚠️ 第一版默认 20000，"
                         "结果 24/27 篇被静默截断，导致我据不完整文本判定人类数据、"
                         "判错了 PMC11900006。现在默认全文，且一律记录是否截断。")
    ap.add_argument("--force", action="store_true",
                    help="覆盖已存在的正文（默认跳过）。截断修复后必须用它重取")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.4)
    args = ap.parse_args(argv)

    cpath, outdir = Path(args.candidates), Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in cpath.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    manifest: list[dict] = []
    ok = skipped = failed = 0
    for i, r in enumerate(rows, 1):
        iid = r.get("item_id")
        pmcid = r.get("source_ref")
        spdx = r.get("license_spdx")
        dest = outdir / f"{pmcid}.txt"
        if dest.exists() and dest.stat().st_size > 0 and not args.force:
            skipped += 1
            continue
        if spdx not in ALLOWED_SPDX:
            print(f"  [跳过] {pmcid}: 许可 {spdx} 不在白名单")
            skipped += 1
            continue
        try:
            key = find_meta_key(pmcid)
            if not key:
                print(f"  [失败] {pmcid}: 找不到 metadata key")
                failed += 1
                continue
            meta = json.loads(http_get(f"{S3_BASE}/{key}").decode("utf-8", "replace"))
            turl = meta.get("text_url")
            if not turl:
                print(f"  [失败] {pmcid}: 无 text_url")
                failed += 1
                continue
            url, md5 = s3_to_https(turl)
            full = http_get(url).decode("utf-8", "replace")
            chars_total = len(full)
            text = full[: args.max_chars] if args.max_chars > 0 else full
            truncated = chars_total > len(text)
            dest.write_text(text, encoding="utf-8", newline="")
            if truncated:
                print(f"  ⚠️ {pmcid}: 截断 {chars_total} → {len(text)} 字符")
            manifest.append({
                "item_id": iid,
                "pmcid": pmcid,
                "license_code": r.get("source_license_code"),
                "license_spdx": spdx,
                "license_url": r.get("license_url"),
                "metadata_key": key,
                "text_s3": turl,
                "text_https": url,
                "text_md5_official": md5,
                "chars_total": chars_total,
                "chars_saved": len(text),
                "truncated": truncated,
                "doi": meta.get("doi"),
                "title": meta.get("title"),
                "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  [失败] {pmcid}: {exc}")
            failed += 1
        if i % 10 == 0:
            print(f"  ...{i}/{len(rows)}  成功 {ok} 跳过 {skipped} 失败 {failed}")
        time.sleep(args.sleep)

    mpath = outdir / "manifest.jsonl"
    with mpath.open("w", encoding="utf-8", newline="") as fh:
        for m in manifest:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"\n完成：成功 {ok} / 跳过 {skipped} / 失败 {failed}")
    print(f"正文 → {outdir}/<PMCID>.txt")
    print(f"清单 → {mpath}（含官方 md5，可核实）")
    print("\n⚠️ items/sources/ 不进公开仓库：公开的是题目，不是别人的论文全文。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
