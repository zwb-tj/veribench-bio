#!/usr/bin/env bash
# VeriBench-Bio · T1 参考流水线
#
# 输入（挂载在 $DATA_DIR）：参考基因组 + 预置 BAM（已比对，chr20 10–12 Mb）
# 输出（写到 $OUT_DIR）：calls.vcf.gz + .tbi，以及计时信息
#
# 本脚本只做"变异检出 + 归一化"（= 被评测的任务本身）；
# 评分由 grade.py 单独执行并单独计时。详见 README.md 的计时口径。
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
OUT_DIR="${OUT_DIR:-/out}"
REGION="${REGION:-chr20:10000000-12000000}"
SAMPLE="${SAMPLE:-HG002}"
REF="${REF:-${DATA_DIR}/ref/chr20.fa}"
BAM="${BAM:-${DATA_DIR}/aln/HG002.chr20.30x.bam}"
THREADS="${THREADS:-2}"

mkdir -p "$OUT_DIR"

log() { printf '[run.sh %s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }

# ---------------------------------------------------------------------------
# 前置检查：缺文件要立刻报错，不能跑到一半才发现
# ---------------------------------------------------------------------------
for f in "$REF" "${REF}.fai" "$BAM" "${BAM}.bai"; do
  if [ ! -f "$f" ]; then
    log "缺少输入文件：$f"
    log "请按 README.md 的『输入』准备数据，或先跑 selftest（无需真实数据）"
    exit 2
  fi
done

# ---------------------------------------------------------------------------
# 计时：只计"任务本身"，不计数据准备与 SDF 转换
# ---------------------------------------------------------------------------
T0=$(date +%s)

log "开始变异检出：freebayes（MIT）区域=${REGION} 样本=${SAMPLE}"
freebayes \
  --fasta-reference "$REF" \
  --region "$REGION" \
  --ploidy 2 \
  --use-mapping-quality \
  "$BAM" > "${OUT_DIR}/calls.raw.vcf"

log "归一化 + 压缩索引：bcftools（MIT）"
# -m -both 同时拆分多等位并左对齐；vcfeval 需要 bgzip + tabix
bcftools norm --fasta-ref "$REF" -m -both "${OUT_DIR}/calls.raw.vcf" \
  | bcftools view -Oz -o "${OUT_DIR}/calls.unsorted.vcf.gz"
bcftools sort -Oz -o "${OUT_DIR}/calls.sorted.vcf.gz" "${OUT_DIR}/calls.unsorted.vcf.gz"

# 样本名对齐：vcfeval 按样本名匹配 baseline 与 query（见 README 的约束③）
actual_sample="$(bcftools query -l "${OUT_DIR}/calls.sorted.vcf.gz" | head -n1 || true)"
if [ -z "$actual_sample" ]; then
  # 无样本的 VCF 会被 vcfeval 拒绝 —— 这里显式补上样本名而不是静默通过
  log "警告：输出 VCF 无样本列，补入样本名 ${SAMPLE}（此步骤会记入日志）"
  printf '%s\n' "$SAMPLE" > "${OUT_DIR}/.sample_name"
  bcftools reheader -s "${OUT_DIR}/.sample_name" \
    -o "${OUT_DIR}/calls.vcf.gz" "${OUT_DIR}/calls.sorted.vcf.gz"
elif [ "$actual_sample" != "$SAMPLE" ]; then
  log "警告：输出样本名为 ${actual_sample}，重命名为 ${SAMPLE}（此步骤会记入日志）"
  printf '%s\n' "$SAMPLE" > "${OUT_DIR}/.sample_name"
  bcftools reheader -s "${OUT_DIR}/.sample_name" \
    -o "${OUT_DIR}/calls.vcf.gz" "${OUT_DIR}/calls.sorted.vcf.gz"
else
  cp "${OUT_DIR}/calls.sorted.vcf.gz" "${OUT_DIR}/calls.vcf.gz"
fi
tabix -f -p vcf "${OUT_DIR}/calls.vcf.gz"

T1=$(date +%s)
WALL=$((T1 - T0))

n_var="$(bcftools view -H "${OUT_DIR}/calls.vcf.gz" | wc -l | tr -d ' ')"
log "完成：${n_var} 个变异，任务耗时 ${WALL}s"

# 计时结果落盘（供 grade.py 读取；评分耗时单独统计）
printf '{"task_id":"T1","stage":"call","wall_clock_sec":%s,"region":"%s","variants":%s,"tool":"freebayes"}\n' \
  "$WALL" "$REGION" "$n_var" > "${OUT_DIR}/timing_call.json"

# 30 分钟门禁：超时视为设计失败，不放宽预算
LIMIT="${WALL_CLOCK_LIMIT:-1800}"
if [ "$WALL" -gt "$LIMIT" ]; then
  log "❌ 任务耗时 ${WALL}s 超过门禁 ${LIMIT}s —— 按设计原则应视为失败（不放宽预算）"
  exit 3
fi

log "完成。下一步：python3 grade.py --calls ${OUT_DIR}/calls.vcf.gz ..."
