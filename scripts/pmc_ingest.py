#!/usr/bin/env python3
"""PMC OA 题源采集器 —— 只收 CC0 / CC BY，其余一律不收。

为什么需要这个脚本
------------------
NCBI 已于 2026-08 移除 PMC OA 的分发层（`oa_file_list.csv` 与 `oa.fcgi` 均实测 404），
合法批量通道只剩 AWS Cloud Service / OAI-PMH / E-utilities / BioC API。
本脚本走 S3 匿名通道：`https://pmc-oa-opendata.s3.amazonaws.com/`。

实测发现的两个陷阱（决定了本脚本的写法）
--------------------------------------
1. 元数据里的 `license_code` **只有粗粒度取值**：实测为 `"CC BY"` / `"CC BY-NC-ND"` / `null`，
   **且不带版本号** → 不能直接当 SPDX 用，必须再从正文 XML 里解析精确版本。
2. `null` 在**老记录里很常见** → 一律按"来源未声明"处理，不收。

fail-closed 原则（本脚本最重要的设计）
------------------------------------
- 解析不出精确版本 → 写 `license_spdx="unknown"` + `redistribution_ok=False`，
  让审计器（R1/R5/R7）拦住它。**绝不"看起来像 CC BY 就当 CC BY"。**
- 一律排除 `is_manuscript=True`（作者稿件走 TDM 许可，**不授予再分发权**）。
- 一律排除 `is_retracted=True`。
- `contains_human_data` 无法程序化判定 → **保守取 True** 并在 `notes` 标注待人工复核
  （宁可多标，不可漏标；人工复核后可改）。

用法
----
    # 抽样统计某前缀下的许可码分布（不落盘，只用于摸底）
    python scripts/pmc_ingest.py --tally --prefix metadata/PMC119 --max-keys 60

    # 按 PMC ID 采集
    python scripts/pmc_ingest.py --harvest --pmc-ids PMC11900000,PMC11900001

    # 按前缀批量采集（自动跳过 metadata 阶段就被排除的条目，省带宽）
    python scripts/pmc_ingest.py --harvest --from-listing --prefix metadata/PMC119 --max-keys 60

输出：`ledger/staging/pmc_harvest.jsonl`（**暂存区，不是公开发布集**；
需经人工复核把 `review_status` 改为 reviewed 后，才可提升进 `ledger/items.jsonl`）。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

S3_BASE = "https://pmc-oa-opendata.s3.amazonaws.com"
USER_AGENT = "VeriBench-Bio/0.1 (research benchmark; PMC OA via AWS Open Data)"

#: 只接受这两个"许可码原文"，精确匹配 —— 不用前缀匹配，
#: 否则 "CC BY-NC-ND" / "CC BY-SA" 会被误收。
ACCEPTED_CODES = {"CC BY", "CC0"}

#: 许可码 → SPDX 需要的版本映射（版本必须从正文 XML 解析，不能猜）
SPDX_BY_VERSION = {
    "4.0": "CC-BY-4.0",
    "3.0": "CC-BY-3.0",
    "2.5": "CC-BY-2.5",
    "2.0": "CC-BY-2.0",
    "1.0": "CC-BY-1.0",
}

#: 与本项目白名单一致（audit_licenses.py 的 WHITELIST 子集）
REDISTRIBUTABLE_SPDX = {"CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "CC-BY-2.0"}

#: 正文 XML 只读前若干字节即可（许可声明在前置部分），避免下载整篇
MAX_XML_BYTES = 600_000

CC_URL_RE = re.compile(
    r"https?://creativecommons\.org/(licenses|publicdomain)/([a-z\-]+)/(\d+\.\d+)/?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def http_get(url: str, limit: int | None = None, retries: int = 3) -> bytes:
    """带重试的 GET。S3 是公开桶，无需签名。"""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read(limit) if limit else resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 403):
                raise
            last = exc
        except Exception as exc:  # noqa: BLE001 - 网络层异常统一重试
            last = exc
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET 失败: {url}: {last}")


def s3_https(s3_uri: str) -> str:
    """把元数据里的 s3:// 路径转成同域 HTTPS（保留 md5 查询串）。"""
    prefix = "s3://pmc-oa-opendata/"
    if not s3_uri.startswith(prefix):
        raise ValueError(f"非预期 s3 路径: {s3_uri}")
    return f"{S3_BASE}/{s3_uri[len(prefix):]}"


def list_metadata_keys(prefix: str, max_keys: int) -> list[str]:
    """列举 metadata/ 下的键（自动翻页）。"""
    keys: list[str] = []
    token: str | None = None
    while len(keys) < max_keys:
        want = min(1000, max_keys - len(keys))
        url = f"{S3_BASE}/?list-type=2&prefix={prefix}&max-keys={want}"
        if token:
            url += f"&continuation-token={urllib.parse.quote(token)}"
        raw = http_get(url).decode("utf-8", errors="replace")
        page = re.findall(r"<Key>([^<]+)</Key>", raw)
        keys.extend(page)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", raw)
        token = m.group(1) if m else None
        if not page or not token:
            break
    return keys[:max_keys]


def fetch_metadata_by_key(key: str) -> dict:
    raw = http_get(f"{S3_BASE}/{key}").decode("utf-8", errors="replace")
    return json.loads(raw)


# ---------------------------------------------------------------------------
# 许可解析
# ---------------------------------------------------------------------------


def parse_license_from_xml(xml_text: str) -> tuple[str, str | None]:
    """从正文 XML 解析精确 SPDX 与许可 URL。

    返回 (spdx, url)；解析不出时返回 ("unknown", None) —— **不猜**。
    """
    for m in CC_URL_RE.finditer(xml_text):
        kind, slug, version = m.group(1).lower(), m.group(2).lower(), m.group(3)
        url = m.group(0)
        if kind == "publicdomain" and slug == "zero":
            return "CC0-1.0", url
        if kind == "licenses" and slug == "by":
            spdx = SPDX_BY_VERSION.get(version)
            if spdx:
                return spdx, url
            # 版本不在映射内 → 不猜，交人工
            return "unknown", url
        # 其它（by-nc / by-nd / by-sa / mark ...）→ 明确不可用
        return f"CC-{slug.upper()}-{version}", url
    return "unknown", None


# ---------------------------------------------------------------------------
# 采集
# ---------------------------------------------------------------------------


def evaluate(meta: dict, retrieval_date: str) -> tuple[dict | None, str]:
    """元数据阶段判定。返回 (候选条目 或 None, 排除原因)。"""
    pmcid = str(meta.get("pmcid") or "?")
    code = meta.get("license_code")

    if meta.get("is_retracted"):
        return None, "retracted"
    if meta.get("is_manuscript"):
        # 作者稿件走 TDM 许可，不授予再分发权 —— 必须排除
        return None, "author-manuscript(TDM，不授予再分发)"
    if code is None:
        return None, "license_code=null（来源未声明）"
    if str(code).strip() not in ACCEPTED_CODES:
        return None, f"license_code={code!r}（非 CC0/CC BY）"
    if not meta.get("is_pmc_openaccess"):
        return None, "非 open access 标记"

    item = {
        "item_id": pmcid,  # 暂存用；进入正式集时再分配稳定 ID
        "task": "R",
        # rubric 题的真值来自双标注+仲裁，不是单一权威来源
        "truth_type": "consensus",
        "truth_note": "rubric 由双标注 + 分歧仲裁产生（尚未执行），故非单一权威来源",
        "source_type": "derived_from_paper",
        "source_platform": "pmc-oa",
        "source_ref": pmcid,
        "source_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/",
        "source_license_code": str(code),
        "license_url": "",  # 由 XML 阶段填
        "retrieval_date": retrieval_date,
        "license_spdx": "unknown",  # 由 XML 阶段填；填不出就保持 unknown（fail-closed）
        "redistribution_ok": False,
        "commercial_ok": False,
        "contains_human_data": True,  # 保守取值，见模块 docstring
        "contains_restricted_data": False,  # PMC OA 子集本身非受控访问
        "visibility": "internal",  # XML 阶段许可确认后才升为 public
        "derivation": "rewritten",
        "derivation_note": "由论文方法/结果改写为审稿式开放题（待撰写）",
        "review_status": "pending",
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "notes": (
            f"citation={meta.get('citation')!r}; doi={meta.get('doi')!r}; "
            "contains_human_data 未人工判定，保守取 True"
        ),
    }
    return item, ""


def harvest_one(pmcid: str, retrieval_date: str) -> tuple[dict | None, str]:
    """按 PMC ID 走完整流程：元数据 → 判定 → 正文 XML → 许可版本。"""
    key = None
    # 元数据键需要版本号；先列举该 id 的键
    listing = http_get(f"{S3_BASE}/?list-type=2&prefix=metadata/{pmcid}.&max-keys=10")
    keys = re.findall(r"<Key>([^<]+)</Key>", listing.decode("utf-8", errors="replace"))
    key = keys[0] if keys else None
    if not key:
        return None, "metadata key 未找到"

    meta = fetch_metadata_by_key(key)
    item, reason = evaluate(meta, retrieval_date)
    if item is None:
        return None, reason

    xml_uri = meta.get("xml_url")
    if not xml_uri:
        return None, "无 xml_url"
    xml_text = http_get(s3_https(xml_uri), limit=MAX_XML_BYTES).decode(
        "utf-8", errors="replace"
    )
    spdx, url = parse_license_from_xml(xml_text)
    item["license_spdx"] = spdx
    item["license_url"] = url or ""
    ok = spdx in REDISTRIBUTABLE_SPDX
    item["redistribution_ok"] = ok
    item["commercial_ok"] = ok
    item["visibility"] = "public" if ok else "internal"
    if not ok:
        item["notes"] += f" | XML 解析许可={spdx}（{url}）→ 不可再分发，保持 internal"
    return item, ""


# ---------------------------------------------------------------------------
# 模式
# ---------------------------------------------------------------------------


def mode_tally(prefix: str, max_keys: int, retrieval_date: str) -> int:
    keys = list_metadata_keys(prefix, max_keys)
    print(f"列举 {prefix}* → {len(keys)} 个键")
    if not keys:
        return 1
    tally: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for i, key in enumerate(keys, 1):
        try:
            meta = fetch_metadata_by_key(key)
        except Exception as exc:  # noqa: BLE001
            tally[f"<fetch-error: {exc}>"] = tally.get(f"<fetch-error: {exc}>", 0) + 1
            continue
        code = meta.get("license_code")
        label = "<null>" if code is None else str(code)
        tally[label] = tally.get(label, 0) + 1
        _, reason = evaluate(meta, retrieval_date)
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        if i % 25 == 0:
            print(f"  ...已取 {i}/{len(keys)}")
    print("\n=== license_code 分布 ===")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {v:>5}  {k}")
    print("\n=== 元数据阶段排除原因 ===")
    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {v:>5}  {k}")
    return 0


def mode_harvest(pmcids: list[str], out_path: Path, retrieval_date: str) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[dict] = []
    stats: dict[str, int] = {}
    for i, pmcid in enumerate(pmcids, 1):
        try:
            item, reason = harvest_one(pmcid, retrieval_date)
        except Exception as exc:  # noqa: BLE001
            item, reason = None, f"error: {exc}"
        if item is None:
            stats[reason] = stats.get(reason, 0) + 1
        else:
            kept.append(item)
            stats["<收取>"] = stats.get("<收取>", 0) + 1
        if i % 10 == 0:
            print(f"  ...已处理 {i}/{len(pmcids)}")
        time.sleep(0.2)  # 对上游客气一点

    with out_path.open("w", encoding="utf-8") as fh:
        for item in kept:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n写入 {out_path}：{len(kept)} 条")
    print("=== 处理结果 ===")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"  {v:>5}  {k}")
    print(
        "\n注意：输出在 staging 区，review_status=pending。"
        "\n需人工复核（含 contains_human_data）后才可提升进 ledger/items.jsonl。"
        f"\n复核命令示例：python scripts/audit_licenses.py {out_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="PMC OA 题源采集器（只收 CC0 / CC BY）")
    ap.add_argument("--tally", action="store_true", help="只统计许可码分布，不落盘")
    ap.add_argument("--harvest", action="store_true", help="采集并写 staging JSONL")
    ap.add_argument("--pmc-ids", help="逗号分隔的 PMC ID")
    ap.add_argument("--from-listing", action="store_true", help="从前缀列举结果采集")
    ap.add_argument("--prefix", default="metadata/", help="S3 键前缀")
    ap.add_argument("--max-keys", type=int, default=50, help="最多处理多少条")
    ap.add_argument(
        "--out",
        default="ledger/staging/pmc_harvest.jsonl",
        help="staging 输出路径",
    )
    ap.add_argument("--retrieval-date", default=_dt.date.today().isoformat())
    args = ap.parse_args(argv)

    if not args.tally and not args.harvest:
        ap.error("需要 --tally 或 --harvest")

    if args.tally:
        return mode_tally(args.prefix, args.max_keys, args.retrieval_date)

    if args.pmc_ids:
        ids = [x.strip() for x in args.pmc_ids.split(",") if x.strip()]
    elif args.from_listing:
        keys = list_metadata_keys(args.prefix, args.max_keys)
        ids = sorted({re.sub(r"\.\d+\.json$", "", k.split("/")[-1]) for k in keys})
        print(f"从前缀取得 {len(ids)} 个 PMC ID")
    else:
        ap.error("--harvest 需要 --pmc-ids 或 --from-listing")

    return mode_harvest(ids, Path(args.out), args.retrieval_date)


if __name__ == "__main__":
    raise SystemExit(main())
