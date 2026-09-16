#!/usr/bin/env python3
"""构建**主台账** `ledger/items.jsonl` —— 截至本轮它是空的，而 T1/T2 早已完成。

问题
----
本项目的第 1 条原则是：

> **每一道题都可溯源。没有 `ledger/items.jsonl` 条目的题目不得进集。宁少勿假。**

而 `ledger/items.jsonl` **是 0 字节**：T1、T2 两个已经上线 HF、跑过实测、
做过字节比对的支柱，**一条台账记录都没有**。（rubric 有自己的一份
`rubric/ledger/rubric_items.jsonl`，但 README 说主台账才是唯一真源。）

这是"原则写了但没执行"。本脚本把它补上，并让审计器来判。

粒度决策（必须说明，因为这里有个真实取舍）
------------------------------------------
原则说"每一道题都可溯源"。T2 有 4,726 道题，但**它们的来源完全相同**
（ClinVar 3★ + ClinGen EREPO + gnomAD），逐题复制 4,726 行**同样的 provenance**
只是噪声，不增加可溯源性。

所以采用：**按来源各一条**，并在 `derivation_note` 里写明该条覆盖哪些题号/题量，
使"任意一题 → 台账条目"的映射仍然确定且可核验。T1 同理（GIAB 真值 + UCSC 参考各一条）。

`contains_human_data` 的判定（逐条写理由，因为这是曾经翻车的地方）
-----------------------------------------------------------------
- **T1 / GIAB HG002**：HG002 是一个**个体**的基因组（去标识、已获公开同意）。
  虽然公开，但它**就是人类个体数据** → `true`，basis `human_subjects_primary`。
- **T2 / ClinVar · ClinGen · gnomAD**：题面只有变异层面的结论与聚合频率，
  **不含任何个体记录** → `false`。basis 用 `human_aggregate_only`
  （这个取值是本轮把 schema 用于真实数据时才补上的，见 ledger.schema.json 的说明）。

用法：
    python3 build_master_ledger.py            # 写入 ledger/items.jsonl
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent              # bio-eval/
RETRIEVED = "2026-09-15"
CREATED = "2026-09-15T00:00:00+00:00"


def base(**kw) -> dict:
    row = {
        "task": "?",
        "truth_type": "authoritative",
        "source_type": "public_dataset",
        "retrieval_date": RETRIEVED,
        "redistribution_ok": True,
        "commercial_ok": True,
        "contains_restricted_data": False,
        "visibility": "public",
        "derivation": "none",
        "review_status": "reviewed",
        "created_at": CREATED,
    }
    row.update(kw)
    return row


# 每条都写明：来源、许可、覆盖范围、依据。
ENTRIES: list[dict] = [
    base(
        item_id="T1-dataset-giab-hg002-chr20",
        task="T1",
        source_platform="giab",
        source_ref="NIST GIAB v5.0q HG002 (RM 8391), GRCh38 chr20:10-12Mb, 30x downsampled",
        source_url="https://www.nist.gov/programs-projects/genome-bottle",
        source_license_code="public-domain (US Government work, NIST)",
        license_url="https://www.nist.gov/open/license",
        license_spdx="PUBLIC-DOMAIN",
        contains_human_data=True,
        human_data_basis="human_subjects_primary",
        derivation_note=(
            "覆盖 T1 全部题目（该任务只有 1 个题面：chr20:10–12 Mb 变异检出）。"
            "数据集含参考序列、HG002 比对结果（30×、仅 chr20 目标区域）、"
            "以及 NIST v5.0q 真值 VCF。"
            "contains_human_data=true 的理由：HG002 是一个**个体**的基因组"
            "（去标识、已获公开同意），虽已公开，但它本身就是人类个体数据。"
            "**HG001 不作可商用声明**，本条只针对 HG002。"
        ),
    ),
    base(
        item_id="T1-ref-ucsc-hg38-chr20",
        task="T1",
        source_platform="ucsc",
        source_ref="UCSC hg38 chr20 reference sequence (chromFa)",
        source_url="https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/",
        source_license_code="public-domain (UCSC genome annotation data are freely available)",
        license_url="https://genome.ucsc.edu/license/",
        license_spdx="PUBLIC-DOMAIN",
        contains_human_data=False,
        human_data_basis="human_aggregate_only",
        derivation_note=(
            "T1 数据集的参考序列组件。参考基因组是**共识序列**，不等于任何个体的基因组"
            "→ 不构成人类个体数据。"
        ),
    ),
    base(
        item_id="T2-source-clinvar",
        task="T2",
        source_platform="clinvar",
        source_ref="ClinVar 3-star 'reviewed by expert panel' records; CLINSIG_LAST_CHANGED <= 2025-12-31",
        source_url="https://www.ncbi.nlm.nih.gov/clinvar/",
        source_license_code="NCBI-PD (US Government work; NLM imposes no restriction)",
        license_url="https://www.ncbi.nlm.nih.gov/home/about/policies/",
        license_spdx="PUBLIC-DOMAIN",
        contains_human_data=False,
        human_data_basis="human_aggregate_only",
        derivation_note=(
            "覆盖 T2 公开集 3,789 条 + 轮换池 937 条（合计 4,726 条中的全部真实条目；"
            "其余 1,181 条为本项目自造的金丝雀对，见 T2-source-canary）。"
            "提供：变异注释、分子后果、3★ 专家小组结论。"
            "contains_human_data=false 的理由：题面只保留**变异层面的结论**，"
            "不含任何个体记录；去标识在构建期强制（审计器 + check_no_leakage.py，"
            "实测 40,110 个字符串字段 0 泄漏）。"
            "⚠️ 时间切分用 **CLINSIG_LAST_CHANGED**，绝不用 MDAT —— "
            "NCBI 批量刷新会让 2026 年的 MDAT 占 3★ 的 92%，旧数据会'长得像新数据'。"
        ),
    ),
    base(
        item_id="T2-source-clingen-erepo",
        task="T2",
        source_platform="clingen",
        source_ref="ClinGen EREPO Applied Evidence Codes; gene-disease validity (Definitive/Strong)",
        source_url="https://clinicalgenome.org/",
        source_license_code="CC0 1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        license_spdx="CC0-1.0",
        contains_human_data=False,
        human_data_basis="human_aggregate_only",
        derivation_note=(
            "覆盖 T2 全部真实条目。提供：专家判据码（作为判据集 set-F1 的真值）、"
            "遗传方式、基因-疾病有效性（Definitive/Strong 为入池条件）。"
            "⚠️ 注意：**VCEP 不产出基因-疾病有效性，那是 GCEP 的产物** —— "
            "两者混用会静默取到空集。"
        ),
    ),
    base(
        item_id="T2-source-gnomad-v4",
        task="T2",
        source_platform="gnomad",
        source_ref="gnomAD v4 joint allele frequencies (ac/an; no 'af' field on joint type)",
        source_url="https://gnomad.broadinstitute.org/",
        source_license_code="CC0 1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        license_spdx="CC0-1.0",
        contains_human_data=False,
        human_data_basis="human_aggregate_only",
        derivation_note=(
            "覆盖 T2 全部真实条目（作为 BA1/BS1/PM2 判据的频率依据）。"
            "实测来源分布：gnomAD v4 命中 2,320 条 / gnomAD-not-found 1,214 条 / "
            "ClinVar 频率回退 4 条 / 未知 7 条。"
            "contains_human_data=false：只有**聚合**等位基因频率，不含个体记录 —— "
            "`human_aggregate_only` 这个取值正是为了安放这类数据才补进 schema 的。"
            "⚠️ **刻意排除**：gnomAD 里的 SpliceAI 注释是 **CC BY-NC 4.0**，"
            "含该列的整份文件一律不用；dbNSFP 系 in-silico 预测器是 CC BY-NC-ND + 商用付费，"
            "全部排除。"
        ),
    ),
    base(
        item_id="T2-source-canary",
        task="T2",
        source_type="synthetic",
        source_platform="self-generated",
        source_ref="本项目程序化生成的 1,181 条金丝雀对（占 25%）",
        source_url="https://github.com/",
        source_license_code="self-generated (CC BY 4.0 by this project)",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        license_spdx="CC-BY-4.0",
        contains_human_data=False,
        human_data_basis="non_human_only",
        derivation="programmatic",
        derivation_note=(
            "覆盖 T2 的 1,181 条金丝雀条目。由真实条目**程序化构造**，"
            "用于检测污染（模型若背下了 ClinVar，会在金丝雀对上暴露出不一致）。"
            "**不是真实临床结论**，不得单独用于准确率解读。"
        ),
    ),
]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="构建主台账")
    ap.add_argument("--out", default=str(ROOT / "ledger" / "items.jsonl"))
    args = ap.parse_args(argv)

    rows = list(ENTRIES)

    # 把 rubric 的 24 条也并进来 —— README 说主台账是唯一真源，
    # 那就不能让它只装一半。
    rl = ROOT / "rubric" / "ledger" / "rubric_items.jsonl"
    if rl.is_file():
        rows += [json.loads(l) for l in rl.read_text(encoding="utf-8").splitlines() if l.strip()]
        print(f"并入 rubric 台账 {len(rows) - len(ENTRIES)} 条")
    else:
        print("⚠️ 找不到 rubric 台账，只写 T1/T2 条目")

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    # ⚠️ `newline=""` —— 台账会被 `audit_licenses` 与 CI 逐字节比较，
    #    不加会让 Windows 写 CRLF、Linux 写 LF，两平台产物不同字节。
    op.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                  encoding="utf-8", newline="")
    print(f"主台账 → {op}（{len(rows)} 条）")
    for r in rows:
        print(f"   {r['item_id']:<38} {r['task']:<3} {r.get('license_spdx')}")

    aud = HERE / "audit_licenses.py"
    p = subprocess.run([sys.executable, str(aud), str(op)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [l for l in (p.stdout or "").strip().splitlines() if l.strip()][-3:]
    print()
    for l in tail:
        print("   " + l)
    if p.returncode != 0:
        for l in (p.stdout or "").strip().splitlines():
            if "[致命]" in l:
                print("   " + l.strip())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
