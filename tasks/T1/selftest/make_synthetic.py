#!/usr/bin/env python3
"""为 T1 判分器生成"答案已知"的合成数据（自检用，不依赖 GIAB 真实数据）。

为什么要这个
-----------
判分器本身如果算错了，整张榜就不可信。所以在碰真实数据之前，
先用一份**变异位置和 REF/ALT 都由程序算出来**的迷你基因组验证判分器：
- `calls_perfect.vcf` 与真值完全相同 → 期望 F1 = 1.0
- `calls_partial.vcf` 故意做对 1 个 SNP、做错 1 个 SNP、漏掉 1 个缺失
  → 期望 SNP F1 = 0.5、INDEL F1 = 0、宏平均 = 0.25

注意：REFP/ALT 必须与参考序列严格一致，否则 vcfeval 会拒绝 —— 所以这里全部由程序计算，不手写。
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

CONTIG = "chr20"
LENGTH = 2000
SEED = 42
SAMPLE = "HG002"

# 1-based 位置
SNP1 = 501
SNP2 = 801
DEL_START = 1001
DEL_LEN = 4  # REF 长度；ALT 长度 1 → 删除 3 个碱基


def make_sequence() -> str:
    rng = random.Random(SEED)
    return "".join(rng.choice("ACGT") for _ in range(LENGTH))


def other_base(ref: str, exclude: set[str]) -> str:
    for b in "ACGT":
        if b != ref and b not in exclude:
            return b
    raise ValueError("无法选出不同的碱基")


def vcf_header() -> str:
    return (
        "##fileformat=VCFv4.2\n"
        f"##contig=<ID={CONTIG},length={LENGTH}>\n"
        '##FILTER=<ID=PASS,Description="All filters passed">\n'
        '##INFO=<ID=DP,Number=1,Type=Integer,Description="Total Depth">\n'
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
        f"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{SAMPLE}\n"
    )


def record(pos: int, ref: str, alt: str) -> str:
    return (
        f"{CONTIG}\t{pos}\t.\t{ref}\t{alt}\t60\tPASS\tDP=30\tGT\t0/1\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 T1 判分器自检数据")
    ap.add_argument("--out", default="/tmp/selftest", help="输出目录")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    seq = make_sequence()

    # --- 参考基因组 -------------------------------------------------------
    (out / "ref.fa").write_text(f">{CONTIG}\n{seq}\n", encoding="utf-8")

    # --- 真值 -------------------------------------------------------------
    s1_ref = seq[SNP1 - 1]
    s1_alt = other_base(s1_ref, set())
    s2_ref = seq[SNP2 - 1]
    s2_alt = other_base(s2_ref, set())
    del_ref = seq[DEL_START - 1 : DEL_START - 1 + DEL_LEN]
    del_alt = del_ref[0]

    truth_records = [
        record(SNP1, s1_ref, s1_alt),
        record(SNP2, s2_ref, s2_alt),
        record(DEL_START, del_ref, del_alt),
    ]
    (out / "truth.vcf").write_text(vcf_header() + "".join(truth_records), encoding="utf-8")

    # --- 完美解法：与真值一致 --------------------------------------------
    (out / "calls_perfect.vcf").write_text(
        vcf_header() + "".join(truth_records), encoding="utf-8"
    )

    # --- 部分解法：对 1 个 SNP、错 1 个 SNP、漏掉缺失 -----------------------
    wrong_alt = other_base(s2_ref, {s2_alt})
    partial_records = [
        record(SNP1, s1_ref, s1_alt),          # 正确
        record(SNP2, s2_ref, wrong_alt),       # 错误 ALT → FP + FN
    ]
    (out / "calls_partial.vcf").write_text(
        vcf_header() + "".join(partial_records), encoding="utf-8"
    )

    # --- 高置信区间 BED（0-based half-open，覆盖整条 contig） --------------
    (out / "confident.bed").write_text(f"{CONTIG}\t0\t{LENGTH}\n", encoding="utf-8")

    print(f"已生成到 {out}：")
    for name in ("ref.fa", "truth.vcf", "calls_perfect.vcf", "calls_partial.vcf", "confident.bed"):
        print(f"  {name}")
    print("\n真值变异：")
    print(f"  SNP   {CONTIG}:{SNP1} {s1_ref}>{s1_alt}")
    print(f"  SNP   {CONTIG}:{SNP2} {s2_ref}>{s2_alt}")
    print(f"  DEL   {CONTIG}:{DEL_START} {del_ref}>{del_alt}  (删除 {DEL_LEN - 1} bp)")
    print("\n部分解法的错误 ALT（用于制造 FP+FN）：")
    print(f"  SNP   {CONTIG}:{SNP2} {s2_ref}>{wrong_alt}  ← 与真值 {s2_alt} 不同")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
