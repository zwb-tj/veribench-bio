#!/usr/bin/env python3
"""T2 数据管道 —— 装配**去标识化证据包**（题面）+ **真值**。

设计要点
--------
1. **题面绝不含变异身份**：不给 HGVS、rsID、坐标、ClinVar/ClinGen accession、变异名、氨基酸改变。
   记忆的对象是「变异 → 标签」；题面里没有变异，就没有可背的东西。这是**结构性**防污染。
2. **真值 100% 来自权威公开来源**：ClinVar 3★（reviewed by expert panel）的结论
   + ClinGen EREPO 的公开 ACMG 判据码。**我们只装配证据，绝不生成标签。**
3. **频率分档而非给精确值**：分档边界对齐 ACMG 阈值（PM2 罕见 / BS1 ≥1% / BA1 ≥5%），
   既保留推理所需信息，又降低"靠精确频率反查变异身份"的风险。
4. **频率来源 = ClinVar VCF 的 `AF_EXAC`/`AF_ESP`/`AF_TGP`**（NCBI-PD 公有领域）。
   刻意**不走 gnomAD API**：一次下载即可、无限速、可离线复现。
   ⚠️ 已知限制：ExAC/ESP/1000G 比 gnomAD v4 旧，写进 DATACARD。
   （gnomAD v4 的 API 实测可用且为 CC0，列为 v2 升级路径。）
5. ⚠️ **绝不请求或存储任何 in-silico 预测**：SpliceAI = CC BY-NC 4.0；
   dbNSFP 系（REVEL/CADD/PolyPhen/AlphaMissense）= CC BY-NC-ND + 商用付费。全部排除。

用法：
    python3 build_t2.py --raw ../../../research/raw --out . [--download-vcf]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
import re
import subprocess
import sys
from pathlib import Path

VCF_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
UA = "VeriBench-Bio/0.2 (open evaluation dataset; ClinVar public domain subset)"

# ---------------------------------------------------------------------------
# 分子后果：ClinVar 的 MC 是 Sequence Ontology 术语，映射到我们的粗粒度枚举
# （映射表必须显式，且写进 DATACARD）
# ---------------------------------------------------------------------------
SO_TO_CATEGORY = {
    "SO:0001587": "nonsense",              # stop_gained
    "SO:0001589": "frameshift",            # frameshift_variant
    "SO:0001574": "splice_acceptor",       # splice_acceptor_variant
    "SO:0001575": "splice_donor",          # splice_donor_variant
    "SO:0001630": "splice_region",         # splice_region_variant
    "SO:0002012": "start_lost",            # start_lost
    "SO:0001578": "stop_lost",             # stop_lost
    "SO:0001822": "inframe_deletion",      # inframe_deletion
    "SO:0001821": "inframe_insertion",     # inframe_insertion
    "SO:0001583": "missense",              # missense_variant
    "SO:0001819": "synonymous",            # synonymous_variant
    "SO:0001627": "intronic",              # intron_variant
    "SO:0001623": "utr",                   # 5_prime_UTR_variant
    "SO:0001624": "utr",                   # 3_prime_UTR_variant
    "SO:0001743": "copy_number_loss",
    "SO:0001742": "copy_number_gain",
}
#: 严重度排序（多后果时取最严重的；splice_region 不覆盖 splice_donor/acceptor）
SEVERITY = [
    "frameshift", "nonsense", "splice_acceptor", "splice_donor", "start_lost",
    "stop_lost", "copy_number_loss", "copy_number_gain", "inframe_deletion",
    "inframe_insertion", "missense", "splice_region", "synonymous", "utr",
    "intronic", "other",
]

#: 频率分档边界 —— 对齐 ACMG：PM2（罕见）、BS1（≥1%）、BA1（≥5%）
BANDS = [
    ("absent", None, 0.0),                 # 实际上=0 或缺失
    ("<0.00001", 0.0, 0.00001),
    ("0.00001-0.0001", 0.00001, 0.0001),
    ("0.0001-0.001", 0.0001, 0.001),
    ("0.001-0.01", 0.001, 0.01),
    ("0.01-0.05", 0.01, 0.05),
    (">=0.05", 0.05, None),
]

#: ClinGen 基因-疾病有效性 → 我们的枚举
VALIDITY_MAP = {
    "definitive": "Definitive",
    "strong": "Strong",
    "moderate": "Moderate",
    "limited": "Limited",
    "disputed": "Disputed",
    "refuted": "Refuted",
    "no known disease relationship": "No Known Disease Relationship",
    "no known disease relationship ": "No Known Disease Relationship",
}


def band(af: float | None) -> str:
    if af is None:
        return "unknown"
    if af <= 0:
        return "absent"
    for name, lo, hi in BANDS:
        if lo is not None and af <= lo:
            continue
        if hi is not None and af > hi:
            continue
        return name
    return ">=0.05"


def category_from_mc(mc_field: str) -> str:
    cats: set[str] = set()
    for chunk in (mc_field or "").split(","):
        term = chunk.split("|")[0].strip()
        cat = SO_TO_CATEGORY.get(term)
        if cat:
            cats.add(cat)
    if not cats:
        return "other"
    for sev in SEVERITY:
        if sev in cats:
            return sev
    return "other"


def parse_info(info: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for kv in info.split(";"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k] = v
        else:
            out[kv] = ""
    return out


def fnum(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 载入
# ---------------------------------------------------------------------------


def clean_keys(row: dict) -> dict:
    """清洗 CSV 字段名：去 BOM、去首尾空白、去可能残留的引号。

    踩过的坑：NCBI/ClinGen 导出的 CSV 带 UTF-8 BOM，`csv.DictReader` 会把
    表头第一列读成 `'\\ufeff"uid"'`（BOM + 引号都留在名字里），于是 `r["uid"]` KeyError。
    在**读取处统一清洗**比"记得加 encoding=utf-8-sig"更可靠（下一个人不必知道这件事）。
    """
    out: dict = {}
    for k, v in row.items():
        if k is None:
            continue
        kk = str(k).lstrip("\ufeff").strip().strip('"').strip()
        out[kk] = v
    return out


def load_funnel(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            r = clean_keys(r)
            rows.append(
                {
                    "uid": int(r["uid"]),
                    "accession": r["accession"],
                    "gene": r["gene"],
                    "clinvar_cls": r["cls"],   # ⚠️ 答案，只用于交叉核对，不进题面
                    "title": r["title"],       # ⚠️ 变异身份，只用于审计，不进题面
                }
            )
    return rows


def load_erepo(path: Path) -> dict[int, dict]:
    idx: dict[int, dict] = {}
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            r = clean_keys(r)
            raw = (r.get("ClinVar Variation Id") or "").strip()
            if not raw.isdigit():
                continue
            idx[int(raw)] = r
    return idx


def load_validity(path: Path) -> tuple[dict[str, dict], str]:
    """ClinGen 基因-疾病有效性。实测结构（不要凭猜）：

        {"total": 3672, "totalNotFiltered": 3672, "rows": [
            {"symbol": "AARS1", "hgnc_id": "HGNC:20",
             "ep": "Charcot-Marie-Tooth Disease Gene Curation Expert Panel",
             "disease_name": "...", "mondo": "MONDO:0013212", "moi": "AD",
             "classification": "Definitive", ...}, ...]}

    ⚠️ 踩过的坑：第一版按 `data`/`results` 找记录、按 `gene` 取基因名 → 解析出 **0 个基因**
    却**不报错**（静默空结果）。这类"看起来成功、其实是空"的失败在本项目里反复出现，
    所以现在**必须在报告里打印解析到的数量**，让空结果一眼可见。
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []

    rank = {"Definitive": 0, "Strong": 1, "Moderate": 2, "Limited": 3,
            "Disputed": 4, "Refuted": 5, "No Known Disease Relationship": 6}
    out: dict[str, dict] = {}
    for rec in rows:
        if not isinstance(rec, dict):
            continue
        gene = rec.get("symbol") or rec.get("gene") or rec.get("geneSymbol")
        cls_raw = rec.get("classification") or rec.get("validity")
        if not gene or not cls_raw:
            continue
        norm = VALIDITY_MAP.get(str(cls_raw).strip().lower(), "unknown")
        if norm == "unknown":
            continue
        cur = out.get(str(gene))
        if cur is None or rank.get(norm, 9) < rank.get(cur["validity"], 9):
            out[str(gene)] = {
                "validity": norm,
                "moi": (rec.get("moi") or "").strip(),
                "disease": (rec.get("disease_name") or "").strip(),
                "mondo": (rec.get("mondo") or "").strip(),
                "ep": (rec.get("ep") or "").strip(),
            }
    shape = f"顶层键={sorted(data.keys()) if isinstance(data, dict) else type(data).__name__}，rows={len(rows)}"
    return out, shape


def load_clinvar_vcf(path: Path, uids: set[int]) -> dict[int, dict]:
    """流式扫描 ClinVar VCF，只保留我们关心的 VariationID。"""
    found: dict[int, dict] = {}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 8:
                continue
            vid = f[2]
            if not vid.isdigit() or int(vid) not in uids:
                continue
            info = parse_info(f[7])
            # 取三个频率源里最大的作为 popmax 近似（没有真正的 popmax 时）
            afs = [fnum(info.get(k)) for k in ("AF_EXAC", "AF_ESP", "AF_TGP")]
            afs = [a for a in afs if a is not None]
            found[int(vid)] = {
                "chrom": f[0],
                "pos": int(f[1]),
                "ref": f[3],
                "alt": f[4].split(",")[0],
                "af_exac": fnum(info.get("AF_EXAC")),
                "af_esp": fnum(info.get("AF_ESP")),
                "af_tgp": fnum(info.get("AF_TGP")),
                "af_max": max(afs) if afs else None,
                "mc": category_from_mc(info.get("MC", "")),
                "clnhgvs": info.get("CLNHGVS", ""),
            }
    return found


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="T2 数据管道")
    ap.add_argument("--raw", default="../../../research/raw")
    ap.add_argument("--out", default=".")
    ap.add_argument("--download-vcf", action="store_true", help="若缓存中无 VCF 则下载")
    ap.add_argument("--canary-frac", type=float, default=0.25, help="金丝雀占比")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    raw = Path(args.raw).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "_cache"
    cache.mkdir(exist_ok=True)

    print(f"raw  = {raw}")
    print(f"out  = {out}")

    funnel = load_funnel(raw / "funnel_S5_setF1_ready.csv")
    print(f"\n[1] 漏斗候选：{len(funnel)} 条")

    erepo = load_erepo(raw / "erepo_classifications.csv")
    print(f"[2] EREPO 索引：{len(erepo)} 条（按 ClinVar Variation Id）")

    validity, shape = load_validity(raw / "clingen_validity.json")
    print(f"[3] ClinGen 有效性：{len(validity)} 个基因；结构 = {shape}")

    vcf = cache / "clinvar_GRCh38.vcf.gz"
    if not vcf.exists() or vcf.stat().st_size < 100_000_000:
        if not args.download_vcf:
            print(f"\n❌ 缺少 {vcf}；加 --download-vcf 下载（约 184.5 MB）")
            return 2
        print(f"\n[4] 下载 ClinVar VCF（约 184.5 MB）→ {vcf}")
        # ⚠️ 不用 urllib：实测在 184 MB 响应上抛 MemoryError。
        #    改用 curl（系统自带，支持断点续传与重试），并校验最终大小。
        cmd = ["curl", "-fL", "--retry", "5", "--retry-delay", "3",
               "-C", "-", "-o", str(vcf), VCF_URL]
        print("    $ " + " ".join(cmd))
        proc = subprocess.run(cmd)
        if proc.returncode != 0:
            print(f"❌ curl 退出码 {proc.returncode}")
            return 3
        size = vcf.stat().st_size
        print(f"    下载完成：{size:,} bytes ({size / 1e6:.1f} MB)")
        if size < 100_000_000:
            print("❌ 文件明显偏小，疑似下载不完整（期望约 184.5 MB）")
            return 3
    else:
        print(f"[4] 使用缓存 VCF：{vcf.stat().st_size:,} bytes")
    print(f"[4] 读取 ClinVar VCF（只看目标 VariationID）…")
    uids = {f["uid"] for f in funnel}
    cv = load_clinvar_vcf(vcf, uids)
    print(f"    VCF 中命中 {len(cv)} / {len(uids)} 条")

    # 导出 variant_id 列表，供 enrich_gnomad.py 富集频率（gnomAD 能明确区分
    # "真缺席" 与 "查不到"，而 ClinVar 的 AF_* 不能）
    vlist = cache / "variants.jsonl"
    # ⚠️ `newline=""`：见 write_jsonl 的说明 —— 不加会让产物随平台变字节
    with vlist.open("w", encoding="utf-8", newline="") as fh:
        for uid, v in sorted(cv.items()):
            fh.write(json.dumps({
                "uid": uid,
                "variant_id": f"{v['chrom']}-{v['pos']}-{v['ref']}-{v['alt']}",
                "af_exac": v["af_exac"], "af_esp": v["af_esp"], "af_tgp": v["af_tgp"],
                "af_max_clinvar": v["af_max"], "mc": v["mc"],
            }, ensure_ascii=False) + "\n")
    print(f"    变体 ID 列表 → {vlist}（{len(cv)} 条）")

    g_cache = cache / "gnomad_af.json"
    gnomad: dict[str, dict] = {}
    if g_cache.is_file():
        try:
            gnomad = json.loads(g_cache.read_text(encoding="utf-8"))
            nf = sum(1 for x in gnomad.values() if x.get("found") is True)
            nn = sum(1 for x in gnomad.values() if x.get("found") is False)
            ne = sum(1 for x in gnomad.values() if x.get("found") not in (True, False))
            print(f"[4b] gnomAD 频率缓存：{len(gnomad)} 条（有频率 {nf} / 查无 {nn} / 出错 {ne}）")
        except json.JSONDecodeError:
            print("⚠️ gnomAD 缓存损坏，忽略")
    else:
        print("[4b] 无 gnomAD 缓存 —— 将回退到 ClinVar 的 AF_EXAC/AF_ESP/AF_TGP（覆盖率低）")

    # --- join + 过滤 ---------------------------------------------------------
    items: list[dict] = []
    truth: list[dict] = []
    audit: list[dict] = []
    stats = {"funnel": len(funnel), "no_erepo": 0, "retracted": 0, "no_vcf": 0,
             "no_assertion": 0, "kept": 0, "af_unknown": 0, "validity_unknown": 0}

    for f in funnel:
        e = erepo.get(f["uid"])
        if e is None:
            stats["no_erepo"] += 1
            continue
        if str(e.get("Retracted") or "").strip().lower() in {"true", "yes", "1"}:
            stats["retracted"] += 1
            continue
        assertion = (e.get("Assertion") or "").strip()
        if not assertion:
            stats["no_assertion"] += 1
            continue
        v = cv.get(f["uid"])
        if v is None:
            stats["no_vcf"] += 1
            # 没有坐标/频率也仍然可以做（频率标 unknown），但先如实统计
        iid = f"T2-{f['uid']:05d}"

        # --- 频率分档：优先 gnomAD（能区分"真缺席"与"查不到"） ---------------
        vid_str = f"{v['chrom']}-{v['pos']}-{v['ref']}-{v['alt']}" if v else None
        g = gnomad.get(vid_str) if vid_str else None
        if g and g.get("found") is True:
            afv = g.get("af_max")
            band_val = band(afv if afv is not None else 0.0)
            popmax_val = band(g["popmax"]) if g.get("popmax") is not None else band_val
            freq_src = "gnomad_v4"
        elif g and g.get("found") is False:
            # ⚠️ gnomAD 明确回答"没有这个变异" → 这是**真缺席**，正是 PM2 的证据，
            #    绝不能标成 unknown（否则一半以上的题会失去最重要的证据类型）
            band_val = "absent"
            popmax_val = "absent"
            freq_src = "gnomad_v4_absent"
        else:
            afv = v["af_max"] if v else None
            band_val = band(afv) if v else "unknown"
            popmax_val = band_val
            freq_src = "clinvar_af_exac" if afv is not None else "unknown"
        if band_val == "unknown":
            stats["af_unknown"] += 1
        stats[f"freq_src_{freq_src}"] = stats.get(f"freq_src_{freq_src}", 0) + 1
        stats[f"band_{band_val}"] = stats.get(f"band_{band_val}", 0) + 1

        # 基因-疾病有效性：EREPO 只有变异级的疾病，遗传方式/有效性以 ClinGen 为准
        vinfo = validity.get(f["gene"]) or {}
        validity_cls = vinfo.get("validity", "unknown")
        if validity_cls == "unknown":
            stats["validity_unknown"] += 1

        e_moi = (e.get("Mode of Inheritance") or "").strip()
        moi = map_moi(e_moi) if e_moi else map_moi(vinfo.get("moi", ""))
        disease = (e.get("Disease") or "").strip() or vinfo.get("disease", "")

        items.append(
            {
                "item_id": iid,
                "gene": f["gene"],
                "disease": disease,
                "mode_of_inheritance": moi,
                "gene_disease_validity": validity_cls,
                "consequence_category": (v["mc"] if v else "other"),
                "population_frequency_band": band_val,
                "population_popmax_band": popmax_val,
                "canary": False,
            }
        )
        cmet, cmet_bad = parse_criteria(e.get("Applied Evidence Codes (Met)"))
        cnot, _ = parse_criteria(e.get("Applied Evidence Codes (Not Met)"))
        if cmet_bad:
            stats["criteria_unparsable"] = stats.get("criteria_unparsable", 0) + 1
        truth.append(
            {
                "item_id": iid,
                "assertion": assertion,
                "assertion_normalized": normalize_assertion(assertion),
                "criteria_met": cmet,
                "criteria_not_met": cnot,
                "expert_panel": (e.get("Expert Panel") or "").strip(),
                "clinvar_variation_id": f["uid"],
                "hgvs": f["title"],
                "disease_mondo_id": (e.get("Mondo Id") or "").strip(),
                "source_url": (e.get("Evidence Repo Link") or "").strip(),
                "approval_date": (e.get("Approval Date") or "").strip(),
            }
        )
        # 审计字段单独放 audit.jsonl —— 不让它们污染 truth.jsonl 的 schema
        audit.append(
            {
                "item_id": iid,
                "clinvar_variation_id": f["uid"],
                "hgvs": f["title"],
                "clinvar_cls_cross_check": f["clinvar_cls"],
                "af_exac": v["af_exac"] if v else None,
                "af_esp": v["af_esp"] if v else None,
                "af_tgp": v["af_tgp"] if v else None,
                "gnomad_af_max": (g or {}).get("af_max") if (g and g.get("found")) else None,
                "gnomad_popmax": (g or {}).get("popmax") if (g and g.get("found")) else None,
                "freq_source": freq_src,
                "criteria_met_raw": (e.get("Applied Evidence Codes (Met)") or "").strip(),
                "criteria_not_met_raw": (e.get("Applied Evidence Codes (Not Met)") or "").strip(),
                "is_canary": False,
            }
        )
        stats["kept"] += 1

    print(f"\n[5] join + 过滤：")
    for k, v_ in stats.items():
        print(f"    {k:20} {v_}")

    # --- 重新分配**不可反查**的题号 ---------------------------------------
    # ⚠️ 踩过的坑（泄露检查器当场抓到）：最初用 `T2-{VariationID}` 当 item_id，
    #    结果**题号本身就是 ClinVar ID** —— 任何人拿题号去 ClinVar 一查就知道答案。
    #    题号必须**不含任何可反查信息**。
    #    做法：固定种子打乱后顺序编号；uid → 题号 的映射只留在 truth/audit 里。
    print(f"\n[5b] 打乱并重新编号（题号不得可反查）")
    rng0 = random.Random(args.seed + 1)
    order = list(range(len(items)))
    rng0.shuffle(order)
    items = [items[i] for i in order]
    truth = [truth[i] for i in order]
    audit = [audit[i] for i in order]
    for n, (it, tr, au) in enumerate(zip(items, truth, audit), 1):
        new_id = f"T2-{n:05d}"
        it["item_id"] = new_id
        tr["item_id"] = new_id
        au["item_id"] = new_id
    print(f"     题号范围 T2-00001 .. T2-{len(items):05d}（与 ClinVar ID 无关）")

    print(f"\n[6] 生成金丝雀（目标占比 {args.canary_frac:.0%}）")
    rng = random.Random(args.seed)
    items, truth, audit = add_canaries(items, truth, audit, args.canary_frac, rng)

    write_jsonl(out / "items.jsonl", items)
    write_jsonl(out / "truth.jsonl", truth)
    write_jsonl(out / "audit.jsonl", audit)
    print(f"\n[7] 已写出：items={len(items)}  truth={len(truth)}  audit={len(audit)}")

    norm_report = report_normalization(truth)
    print("\n[8] assertion 归一化映射：")
    for k, v_ in sorted(norm_report.items(), key=lambda kv: -kv[1]):
        print(f"    {v_:6}  {k!r}")
    return 0


def map_moi(raw: str) -> str:
    """把遗传方式代码/长写统一成可读形式。映射表必须显式（写进 DATACARD）。"""
    s = (raw or "").strip()
    if not s:
        return "unknown"
    key = s.lower()
    table = {
        "ad": "Autosomal dominant",
        "autosomal dominant": "Autosomal dominant",
        "ar": "Autosomal recessive",
        "autosomal recessive": "Autosomal recessive",
        "xl": "X-linked",
        "xld": "X-linked dominant",
        "xlr": "X-linked recessive",
        "x-linked": "X-linked",
        "x-linked dominant": "X-linked dominant",
        "x-linked recessive": "X-linked recessive",
        "mt": "Mitochondrial",
        "mitochondrial": "Mitochondrial",
        "sd": "Semidominant",
        "semidominant": "Semidominant",
        "unknown": "unknown",
    }
    return table.get(key, s)


def normalize_assertion(raw: str) -> str:
    s = raw.strip().lower()
    if s.startswith("pathogenic"):
        return "Pathogenic"
    if s.startswith("likely pathogenic"):
        return "Likely pathogenic"
    if s.startswith("likely benign"):
        return "Likely benign"
    if s.startswith("benign"):
        return "Benign"
    if "uncertain" in s or s.startswith("vus"):
        return "Uncertain significance"
    return "Uncertain significance"


_BASE_RE = re.compile(r"^(PVS1|PS[1-4]|PM[1-6]|PP[1-5]|BA1|BS[1-4]|BP[1-7])")


def parse_criteria(raw: str | None) -> tuple[list[str], list[str]]:
    """把 EREPO 的判据字段切成**规范 ACMG 基础码**；返回 (规范码, 未识别 token)。

    ClinGen 会写 `PP1_Moderate`、`PM2_Supporting` 这类**带强度修饰**的码，
    所以要把修饰去掉取基础码。

    ⚠️ **本函数必须与 `../grade.py` 的 `canonicalize_criteria` 保持一致。**
       一旦漂移，oracle 基线（照抄真值）的判据 F1 就会掉到 1.0 以下 ——
       这就是我们的自动一致性检查，不需要额外写测试。
    """
    if not raw:
        return [], []
    ok: list[str] = []
    bad: list[str] = []
    for tok in raw.replace(",", " ").replace(";", " ").split():
        t = tok.strip().upper().split("(")[0].strip().replace(" ", "")
        if not t:
            continue
        m = _BASE_RE.match(t.split("_")[0])
        if m:
            if m.group(1) not in ok:
                ok.append(m.group(1))
        else:
            bad.append(tok.strip())
    return ok, bad


def report_normalization(truth: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in truth:
        counts[t["assertion"]] = counts.get(t["assertion"], 0) + 1
    return counts


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """写 JSONL。⚠️ **必须 `newline=""`** —— 否则换行符随平台而变。

    实测（2026-09）：不加 `newline=""` 时，Python 在 Windows 上把 `\\n`
    翻译成 `\\r\\n`、在 Linux 上不翻译，于是**同一份数据在两平台产出不同字节**。
    而 `items.jsonl` 是 `record_image_digest.py` 的**构建输入** ——
    它的字节变了，`source_sha256` 就变了，**同一条 pin 记录在 Windows 报 ✅、
    在 Linux 报 ❌**（实测：CRLF 版 `400fe720…` vs LF 版 `be5da56d…`）。

    更麻烦的是 **CI 抓不到**：生成物在 clone 里不存在，`--check-all` 会 SKIP。
    只有真正按 README 跑一遍取数+构建的人才会撞上。

    `newline=""` 让 `\\n` 原样写入，两个平台得到**逐字节相同**的文件。
    """
    with path.open("w", encoding="utf-8", newline="") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def add_canaries(
    items: list[dict],
    truth: list[dict],
    audit: list[dict],
    frac: float,
    rng: random.Random,
) -> tuple[list[dict], list[dict], list[dict]]:
    """两类金丝雀，**都是规则可辩护的**：

    A) 频率翻转（BA1）：证据其余部分不变，只把频率分档改成 `>=0.05`。
       依据 ACMG 规则 BA1 单独成立即判 Benign → 预期方向 `flip_more_benign`。
       **这是规则推导的预期，不是我们编的真值。**
    B) 重复题（阴性对照）：证据完全复制，只换 item_id → 预期 `unchanged`。
       测的是**模型自洽性/确定性**：同题两答不一致，说明答案里含随机噪声。
    """
    n_total = len(items)
    n_can = int(n_total * frac / (1 - frac))
    n_freq = n_can // 2
    n_dup = n_can - n_freq

    truth_by_id = {t["item_id"]: t for t in truth}
    audit_by_id = {a["item_id"]: a for a in audit}

    idx = list(range(n_total))
    rng.shuffle(idx)

    # ⚠️ 频率金丝雀只能锚在「真值还不是 Benign」且「当前频率还没到 BA1」的题上：
    #    如果母题本来就是 Benign，把频率改成 ≥5% 之后答案仍是 Benign，
    #    "方向翻转"的预期根本不成立。
    #    实测指纹：oracle（照抄真值）的金丝雀一致率因此只有 0.9438 而不是 1.0。
    eligible_freq = [
        i for i in idx
        if truth_by_id[items[i]["item_id"]]["assertion_normalized"] != "Benign"
        and items[i]["population_frequency_band"] != ">=0.05"
    ]
    freq_picks = eligible_freq[:n_freq]
    chosen = set(freq_picks)
    dup_picks = [i for i in idx if i not in chosen][:n_dup]
    picked = [(i, "freq") for i in freq_picks] + [(i, "dup") for i in dup_picks]
    print(f"     频率金丝雀 {len(freq_picks)} 对（可锚定 {len(eligible_freq)} 条）"
          f" · 自洽性重复题 {len(dup_picks)} 对")

    new_items: list[dict] = []
    new_truth: list[dict] = []
    new_audit: list[dict] = []

    for i, kind in picked:
        base_i, base_t = items[i], truth_by_id[items[i]["item_id"]]
        base_a = audit_by_id.get(base_i["item_id"])
        if kind == "freq":
            cid = f"{base_i['item_id']}B"
            ci = dict(base_i)
            ci.update({
                "item_id": cid,
                "population_frequency_band": ">=0.05",
                "population_popmax_band": ">=0.05",
                "canary": True,
                "canary_of": base_i["item_id"],
                "canary_changed_field": "population_frequency_band",
            })
            ct = dict(base_t)
            ct.update({
                "item_id": cid,
                "canary_pair": base_i["item_id"],
                "canary_expected": "flip_more_benign",
                "assertion": f"[规则推导] BA1 成立（popmax ≥5%）→ Benign（原题：{base_t['assertion']}）",
                "assertion_normalized": "Benign",
                "criteria_met": ["BA1"],
            })
        else:
            cid = f"{base_i['item_id']}D"
            ci = dict(base_i)
            ci.update({
                "item_id": cid,
                "canary": True,
                "canary_of": base_i["item_id"],
                "canary_changed_field": "none（重复题，测自洽性）",
            })
            ct = dict(base_t)
            ct.update({
                "item_id": cid,
                "canary_pair": base_i["item_id"],
                "canary_expected": "unchanged",
            })
        new_items.append(ci)
        new_truth.append(ct)
        if base_a:
            ca = dict(base_a)
            ca.update({"item_id": cid, "is_canary": True, "canary_of": base_i["item_id"]})
            new_audit.append(ca)

    return items + new_items, truth + new_truth, audit + new_audit


if __name__ == "__main__":
    raise SystemExit(main())
