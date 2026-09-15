#!/usr/bin/env python3
"""VeriBench-Bio · T1 判分器

用 GIAB/NIST 权威真值，通过 **RTG `vcfeval`（BSD 2-Clause）** 计算
SNP 与 INDEL 各自的 精确率 / 召回率 / F1。

设计原则（与项目一致）
--------------------
1. **真值权威**：真值来自 GIAB/NIST，不是我们自己算的。
2. **分开计时**：任务耗时读 run.sh 的 `timing_call.json`；评分耗时单独统计，两者都公开。
3. **不静默失败**：某类型跑不起来 → `status` 标 `partial` 并写明原因，**绝不用 0 分糊过去**。
4. **主分口径明确**：`score = mean(F1_snp, F1_indel)`（宏平均）。
   若某一类型在真值里不存在，只对存在的类型取平均，并在 `score_note` 里说明。

用法
----
    python3 grade.py \
        --calls /out/calls.vcf.gz \
        --truth /data/truth/HG002_GRCh38_v5.0q.vcf.gz \
        --bed   /data/truth/HG002_GRCh38_v5.0q_benchmark.bed \
        --ref-sdf /data/ref/chr20.sdf \
        --out   /out/result.json
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

VARIANT_TYPES = ("snps", "indels")


def sh(cmd: list[str], log: list[str]) -> subprocess.CompletedProcess[str]:
    log.append("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout.strip():
        log.append(proc.stdout.strip()[-2000:])
    if proc.returncode != 0:
        if proc.stderr.strip():
            log.append(proc.stderr.strip()[-2000:])
    return proc


def parse_summary(path: Path) -> dict:
    """解析 vcfeval 的 summary.txt，取 Threshold=None 那一行。

    列：Threshold True-pos-baseline True-pos-call False-pos False-neg Precision Sensitivity F-measure
    """
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[0] == "None":
            nums = [float(x) for x in parts[1:8]]
            return {
                "tp_baseline": nums[0],
                "tp_call": nums[1],
                "fp": nums[2],
                "fn": nums[3],
                "precision": nums[4],
                "sensitivity": nums[5],
                "f1": nums[6],
            }
    raise ValueError(f"summary.txt 中找不到 'None' 行：{path}")


def subset_type(src: Path, vtype: str, outdir: Path, log: list[str]) -> Path | None:
    """按变异类型切分并索引。该类无记录则返回 None。"""
    out = outdir / f"{src.stem}.{vtype}.vcf.gz"
    proc = sh(
        ["bcftools", "view", "-v", vtype, "-Oz", "-o", str(out), str(src)],
        log,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"bcftools view -v {vtype} 失败")
    sh(["tabix", "-f", "-p", "vcf", str(out)], log)
    n = sh(["bcftools", "view", "-H", str(out)], log).stdout.strip()
    if not n:
        return None
    return out


def run_vcfeval(
    truth: Path, calls: Path, ref_sdf: Path, bed: Path | None, outdir: Path, log: list[str]
) -> subprocess.CompletedProcess[str]:
    # ⚠️ rtg vcfeval 拒绝写入已存在的目录（"already exists. Please remove it first"），
    #    所以这里必须**先删掉**，让它自己创建，不能预先 mkdir。
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "rtg",
        "vcfeval",
        "--baseline", str(truth),
        "--calls", str(calls),
        "--template", str(ref_sdf),
        "--output", str(outdir),
    ]
    if bed is not None:
        cmd += ["--bed-regions", str(bed)]
    return sh(cmd, log)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="T1 判分器（vcfeval）")
    ap.add_argument("--calls", required=True, help="被测解法产出的 VCF(.gz)")
    ap.add_argument("--truth", required=True, help="GIAB/NIST 真值 VCF(.gz)")
    ap.add_argument("--ref-sdf", required=True, help="参考基因组 SDF 目录（rtg format 产物）")
    ap.add_argument("--bed", help="高置信区间 BED（强烈建议提供）")
    ap.add_argument("--workdir", default="/out/vcfeval", help="vcfeval 工作目录")
    ap.add_argument("--out", help="结果 JSON 输出路径")
    ap.add_argument("--timing", default=None, help="run.sh 产出的 timing_call.json")
    ap.add_argument("--image-digest", default=None)
    ap.add_argument("--manifest-hash", default=None)
    args = ap.parse_args(argv)

    calls = Path(args.calls)
    truth = Path(args.truth)
    ref_sdf = Path(args.ref_sdf)
    bed = Path(args.bed) if args.bed else None
    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)

    for p, label in ((calls, "calls"), (truth, "truth"), (ref_sdf, "ref-sdf")):
        if not p.exists():
            print(f"[错误] {label} 不存在：{p}", file=sys.stderr)
            return 2

    log: list[str] = []
    problems: list[str] = []
    # ⚠️ 测时长一律用单调时钟：容器里挂钟会跳（实测出现过 grade_sec = -11.9）
    t0 = time.monotonic()

    # --- 按类型切分（SNP / INDEL 分开评分） -------------------------------
    truth_by_type: dict[str, Path | None] = {}
    calls_by_type: dict[str, Path | None] = {}
    for vtype in VARIANT_TYPES:
        truth_by_type[vtype] = subset_type(truth, vtype, work, log)
        calls_by_type[vtype] = subset_type(calls, vtype, work, log)

    # --- 逐类型评分 -------------------------------------------------------
    per_type: dict[str, dict | None] = {}
    for vtype in VARIANT_TYPES:
        t, c = truth_by_type[vtype], calls_by_type[vtype]
        if t is None:
            problems.append(f"{vtype}: 真值中无该类型记录，跳过评分")
            per_type[vtype] = None
            continue
        if c is None:
            problems.append(f"{vtype}: 解法未产出该类型变异（真值有，记为 0 分）")
            per_type[vtype] = {
                "tp_baseline": 0.0, "tp_call": 0.0, "fp": 0.0, "fn": 0.0,
                "precision": 0.0, "sensitivity": 0.0, "f1": 0.0,
                "note": "解法未产出该类型变异",
            }
            continue
        outdir = work / f"eval_{vtype}"
        proc = run_vcfeval(t, c, ref_sdf, bed, outdir, log)
        summary = outdir / "summary.txt"
        if proc.returncode != 0 or not summary.exists():
            problems.append(f"{vtype}: vcfeval 执行失败（见 log），未静默计 0 分")
            per_type[vtype] = None
            continue
        try:
            per_type[vtype] = parse_summary(summary)
        except ValueError as exc:
            problems.append(f"{vtype}: {exc}")
            per_type[vtype] = None

    # --- 综合（不套用 bed 的“全量”参考分） --------------------------------
    all_dir = work / "eval_all"
    reg_proc = run_vcfeval(truth, calls, ref_sdf, bed, all_dir, log)
    all_scores = None
    if reg_proc.returncode == 0 and (all_dir / "summary.txt").exists():
        try:
            all_scores = parse_summary(all_dir / "summary.txt")
        except ValueError as exc:
            problems.append(f"all: {exc}")

    f1s = [per_type[v]["f1"] for v in VARIANT_TYPES if per_type[v]]
    score = sum(f1s) / len(f1s) if f1s else None
    score_note = "score = mean(F1_snp, F1_indel)"
    if len(f1s) == 1:
        score_note = "score = 仅存在类型的 F1（另一类型在真值中缺失）"
    if not f1s:
        score_note = "无法计算：所有类型评分均失败"

    grade_sec = round(time.monotonic() - t0, 1)

    # --- 任务耗时（来自 run.sh，评分耗时不计入） --------------------------
    task_sec = None
    timing_path = Path(args.timing) if args.timing else None
    if timing_path and timing_path.exists():
        try:
            task_sec = json.loads(timing_path.read_text(encoding="utf-8")).get("wall_clock_sec")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"无法解析 {timing_path}: {exc}")

    peak_rss_mb = round(
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024.0, 1
    )

    status = "ok"
    if problems and any(per_type[v] is None for v in VARIANT_TYPES):
        status = "partial"
    elif problems:
        status = "ok-with-warnings"
    if score is None:
        status = "failed"

    result = {
        "task_id": "T1",
        "status": status,
        "score": None if score is None else round(score, 6),
        "metric": "macro_f1_snp_indel",
        "score_note": score_note,
        "per_type": per_type,
        "all_variants": all_scores,
        "wall_clock_sec": task_sec,
        "grade_sec": grade_sec,
        "wall_clock_note": "wall_clock_sec 仅计任务本身（run.sh），不含数据准备与评分",
        "peak_rss_mb": peak_rss_mb,
        "cpu_count": os.cpu_count(),
        "image_digest": args.image_digest or "unknown",
        "manifest_hash": args.manifest_hash or "unknown",
        "problems": problems,
        "toolchain": {"caller": "freebayes", "grader": "rtg vcfeval", "splitter": "bcftools"},
        "log_tail": log[-40:],
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"结果写入 {args.out}")
    print(text)
    return 0 if score is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
