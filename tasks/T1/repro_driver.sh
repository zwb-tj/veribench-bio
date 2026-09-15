#!/usr/bin/env bash
# 复现驱动（2026-09 重跑）：与历史 driver 的唯一区别是
# **故意不设 REGION / BAM 环境变量** —— 让 run.sh 走它自己的默认值。
#
# 为什么这么改：历史上两个 driver（_runs/driver.sh 与 HF 复现用的那个）
# 都写着 `export REGION=...` 和 `export BAM=...`，把 run.sh 的默认值整个遮住了。
# 结果默认值里的两个真 bug（BAM 少了 .30x、区间写成 10-20 Mb）**从来没被执行过**，
# 也就从来没被发现。这次让默认值真正跑一遍 —— 这才是"新人照 README 跑一遍"的路径。
#
# 另外：SDF 写到 /out（不是 /data），这样 /data 能以只读挂载 ——
# 顺便证明**跑一遍不会改动已发布的数据集**。
set -eo pipefail

echo "===== 0/3 环境自检 ====="
echo "DATA_DIR=${DATA_DIR:-/data}  OUT_DIR=${OUT_DIR:-/out}"
echo "-- 默认值指向的文件是否存在 --"
ls -l "${DATA_DIR}/aln/" "${DATA_DIR}/ref/" 2>&1 | head -20
echo "-- 关键：以下两行必须存在，否则说明默认值是坏的 --"
test -f "${DATA_DIR}/aln/HG002.chr20.30x.bam" && echo "  [ok] aln/HG002.chr20.30x.bam" || { echo "  [失败] 默认 BAM 不存在"; exit 2; }
test -f "${DATA_DIR}/ref/chr20.fa.fai" && echo "  [ok] ref/chr20.fa.fai" || { echo "  [失败] ref .fai 不存在"; exit 2; }
echo

echo "===== 1/3 build reference SDF (rtg format, not timed) -> /out ====="
rm -rf /out/chr20.sdf
rtg format -o /out/chr20.sdf "${DATA_DIR}/ref/chr20.fa" 2>&1 | tail -6
echo

echo "===== 2/3 variant calling (freebayes, TIMED) — run.sh DEFAULTS, no overrides ====="
unset REGION BAM REF SAMPLE THREADS
export DATA_DIR=/data OUT_DIR=/out
bash /work/run.sh
echo

echo "===== 3/3 grading (vcfeval) ====="
python3 /work/grade.py --calls /out/calls.vcf.gz \
  --truth "${DATA_DIR}/truth/HG002_GRCh38_v5.0q_smvar.region.vcf.gz" \
  --bed "${DATA_DIR}/truth/HG002_GRCh38_v5.0q_smvar.benchmark.region.bed" \
  --ref-sdf /out/chr20.sdf \
  --timing /out/timing_call.json --out /out/result.json \
  --image-digest "${IMAGE_DIGEST:-unknown}" \
  --manifest-hash "${MANIFEST_HASH:-unknown}"
echo "REPRO_DONE"
