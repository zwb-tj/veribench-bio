#!/usr/bin/env python3
"""用 gnomAD v4 API 富集等位基因频率（可续跑、可断点重来）。

为什么要这一步
-------------
ClinVar VCF 自带的 `AF_EXAC`/`AF_ESP`/`AF_TGP` 只覆盖那些**老数据集里出现过**的变异。
实测 3,545 条里 **65% 拿不到频率** —— 而罕见/新发变异（恰恰是致病性变异的主体）
本来就不在 ExAC/ESP/1000G 里。

关键在于**区分两种"没有频率"**：
  · 在 gnomAD 里**查无此变异** → 这是**真的缺席**，正是 ACMG **PM2** 的证据（有意义！）
  · gnomAD 有记录但频率为 0 → 同样是罕见证据
  · API 查询失败 → 这才是 **unknown**（不可用作证据）
把前两者错标成 unknown，会让一半以上的题失去最重要的证据类型。

许可
----
gnomAD 主数据是 **CC0 1.0**（已核实原文）。
⚠️ 我们**只请求等位基因频率**。绝不请求 in-silico 预测字段：
   SpliceAI = CC BY NC 4.0；dbNSFP 系（REVEL/CADD/PolyPhen/AlphaMissense）= CC BY-NC-ND + 商用付费。

用法：
    python3 enrich_gnomad.py --variants _cache/variants.jsonl --out _cache/gnomad_af.json [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://gnomad.broadinstitute.org/api"
UA = "VeriBench-Bio/0.2 (open evaluation dataset; allele-frequency only, no predictors)"

QUERY = """
query V($id: String!) {
  variant(variantId: $id, dataset: gnomad_r4) {
    variant_id
    exome { ac an }
    genome { ac an }
    joint { ac an populations { id ac an } }
  }
}
"""
# ⚠️ 踩过的坑：gnomAD 的 `joint`（VariantDetailsJointSequencingTypeData）与
#    `joint.populations`（VariantPopulation）**没有 `af` 字段，只有 `ac`/`an`**。
#    请求 `af` 会被 GraphQL 校验拒绝，而 gnomAD 把校验错误**包在 HTTP 400 里**返回。
#    → 必须自己算 af = ac/an；并且**错误处理必须保留响应体**，否则只剩
#      "400 Bad Request" 这种毫无信息量的报错（这次就因此多绕了好几轮）。

SLEEP = 0.8    # 实测 0.35s（≈3 次/秒）会触发 429 限流；放到 ~1.2 次/秒
RETRIES = 5    # 429 会走更长的退避


def gql(variant_id: str) -> dict:
    payload = {"query": QUERY, "variables": {"id": variant_id}}
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(
                ENDPOINT,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "User-Agent": UA},
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as exc:
            # ⚠️ 必须读响应体：gnomAD 把 GraphQL 校验/schema 错误包在 400 里，
            #    只记状态码会得到"Bad Request"这种查不出问题的信息。
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:400]
            except Exception:  # noqa: BLE001
                pass
            if exc.code == 429:
                # 限流要**长退避**，短重试只会继续撞墙（实测 0.35s 间隔即触发）
                wait = 10 * (attempt + 1)
                time.sleep(wait)
                last = RuntimeError(f"HTTP 429 限流（已退避 {wait}s）: {body[:120]}")
                continue
            last = RuntimeError(f"HTTP {exc.code}: {body}")
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{variant_id}: {last}")


def _af(ac, an) -> float | None:
    """gnomAD 的 joint/population 只有 ac/an，没有 af → 自己算。"""
    try:
        if ac is None or an in (None, 0):
            return None
        return float(ac) / float(an)
    except (TypeError, ValueError):
        return None


def extract(data: dict) -> dict:
    errs = data.get("errors") or []
    if errs:
        msg = " ".join(str((e or {}).get("message", "")) for e in errs).lower()
        # ⚠️ 关键语义：gnomAD 对"库里没有这个变异"返回的是 **GraphQL 错误
        #    `Variant not found`**（HTTP 200 + errors 数组），**不是 `variant: null`**。
        #    而"gnomAD 里查无此变异"**正是 ACMG PM2 的证据**（罕见性），
        #    绝不能当成"查询失败"而标 unknown —— 那会让大量题目失去最关键的一类证据。
        if "not found" in msg or "not_found" in msg:
            return {"found": False, "note": "gnomAD: Variant not found"}
        raise RuntimeError(f"GraphQL errors: {str(errs)[:300]}")

    v = (data.get("data") or {}).get("variant")
    if v is None:
        return {"found": False, "note": "gnomAD: variant 为 null"}

    ex, ge, jo = (v.get("exome") or {}), (v.get("genome") or {}), (v.get("joint") or {})
    af_ex, af_ge, af_jo = _af(ex.get("ac"), ex.get("an")), _af(ge.get("ac"), ge.get("an")), _af(jo.get("ac"), jo.get("an"))
    pops = []
    for p in (jo.get("populations") or []):
        a = _af((p or {}).get("ac"), (p or {}).get("an"))
        if a is not None:
            pops.append(a)
    vals = [x for x in (af_ex, af_ge, af_jo) if x is not None]
    return {
        "found": True,
        "af_exome": af_ex,
        "af_genome": af_ge,
        "af_joint": af_jo,
        "af_max": max(vals) if vals else None,
        "popmax": max(pops) if pops else None,
        "n_populations": len(pops),
    }


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="gnomAD v4 频率富集（可续跑）")
    ap.add_argument("--variants", required=True, help="variants.jsonl（含 variant_id）")
    ap.add_argument("--out", required=True, help="输出缓存 JSON")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条（调试用）")
    args = ap.parse_args(argv)

    vpath, opath = Path(args.variants), Path(args.out)
    if not vpath.is_file():
        print(f"[错误] 找不到 {vpath}", file=sys.stderr)
        return 2

    ids: list[str] = []
    for line in vpath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            ids.append(json.loads(line)["variant_id"])
    if args.limit:
        ids = ids[: args.limit]

    cache: dict[str, dict] = {}
    if opath.is_file():
        try:
            cache = json.loads(opath.read_text(encoding="utf-8"))
            print(f"已加载缓存：{len(cache)} 条（续跑）")
        except json.JSONDecodeError:
            print("⚠️ 缓存文件损坏，忽略并重建")

    # ⚠️ 只跳过**已成功判定**的条目（found 为 True/False）。
    #    出错条目（found 为 None）必须重试 —— 否则一次网络抖动会被永久缓存成"unknown"。
    todo = [v for v in ids if cache.get(v, {}).get("found") not in (True, False)]
    print(f"待查询 {len(todo)} / {len(ids)} 条（已有成功缓存 {len(ids) - len(todo)} 条）")
    if not todo:
        print("无待查条目。")
        return 0

    ok = notfound = err = 0
    t0 = time.monotonic()
    for i, vid in enumerate(todo, 1):
        try:
            cache[vid] = extract(gql(vid))
            if cache[vid]["found"]:
                ok += 1
            else:
                notfound += 1
        except Exception as exc:  # noqa: BLE001
            cache[vid] = {"found": None, "error": str(exc)[:200]}
            err += 1
        if i % 25 == 0 or i == len(todo):
            el = time.monotonic() - t0
            rate = i / el if el > 0 else 0
            eta = (len(todo) - i) / rate if rate > 0 else 0
            print(f"  {i}/{len(todo)}  有频率 {ok} / 查无 {notfound} / 出错 {err}  "
                  f"({rate:.1f}/s, 剩余约 {eta/60:.1f} 分钟)")
            opath.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        time.sleep(SLEEP)

    opath.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"\n完成：有频率 {ok} / 查无此变异 {notfound} / 出错 {err}")
    print(f"缓存写入 {opath}（共 {len(cache)} 条）")
    if err:
        print("⚠️ 有出错条目 —— 重跑本脚本会自动补查（缓存续跑）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
