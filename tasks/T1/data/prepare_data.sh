#!/usr/bin/env bash
# T1 数据准备 —— 从 GIAB 官方源取 chr20 区域，降采样到目标覆盖度
#
# 为什么不能直接下整个 BAM：GIAB 的 HG002.GRCh38.2x250.bam 是 **121.79 GB**。
# 所以走"远程按区域取 + 降采样"：只取需要的那一段，压到可托管的体积。
#
# 实测事实（2026-09）：
#   - samtools 可经 HTTPS 直接读该远程 BAM 并按区域取（htslib + libcurl）
#   - 官方 md5：HG002.GRCh38.2x250.bam = 56c30eaa4e2f25ff0ac80ef30e09d78e
#   - 该 BAM 实际覆盖度约 75×（不是 300×），比对参考为
#     GRCh38_full_plus_hs38d1_analysis_set_minus_alts
#   - chr20 主 contig 的坐标与 GRCh38 chr20 一致，故 UCSC chr20 可用
#
# 健壮性设计（踩过的坑）：
#   1) UCSC/NCBI 的 HTTPS 会中途断流（curl 18）→ 全部 curl 带重试
#   2) **一律写临时文件再 mv**：否则中途失败会留下残缺文件，
#      下次运行时被"已存在"检查跳过 → 静默产生坏数据（这比直接报错更危险）
#   3) **不要用 OUT_DIR 当变量名**：镜像里 `OUT_DIR=/out` 是 run.sh 的输出目录，
#      撞名曾把 100+ MB 数据写进**未挂载**的 /out，容器一删就没了，而脚本仍"成功"退出。
#      故本脚本改用 DATA_DIR，并在末尾**断言真的产出了文件**。
#
# 用法（容器内）：
#   DATA_DIR=/data REGION=chr20:10000000-12000000 TARGET_COV=30 bash /work/data/prepare_data.sh
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
REGION="${REGION:-chr20:10000000-12000000}"
CONTIG="${CONTIG:-chr20}"
TARGET_COV="${TARGET_COV:-30}"
SEED="${SEED:-42}"
FORCE="${FORCE:-0}"

CURL_OPTS=(-fsSL --retry 6 --retry-delay 5 --retry-all-errors
           --connect-timeout 30 --max-time 3600 --http1.1)

GIAB="https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab"
BAM_URL="$GIAB/data/AshkenazimTrio/HG002_NA24385_son/NIST_Illumina_2x250bps/novoalign_bams/HG002.GRCh38.2x250.bam"
BAM_MD5="56c30eaa4e2f25ff0ac80ef30e09d78e"
BAM_BYTES="130770531934"
V5Q="$GIAB/release/AshkenazimTrio/HG002_NA24385_son/v5.0q"
TRUTH_VCF_URL="$V5Q/HG002_GRCh38_v5.0q_smvar.vcf.gz"
TRUTH_BED_URL="$V5Q/HG002_GRCh38_v5.0q_smvar.benchmark.bed"
REF_URL="${REF_URL:-https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr20.fa.gz}"

REF_DIR="$DATA_DIR/ref"
ALN_DIR="$DATA_DIR/aln"
TRUTH_DIR="$DATA_DIR/truth"
WORK_DIR="$DATA_DIR/_work"   # 中间产物，不进公开数据集（make_manifest 会跳过）
mkdir -p "$REF_DIR" "$ALN_DIR" "$TRUTH_DIR" "$WORK_DIR"

log() { printf '[prepare %s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }

# 仅当目标文件已存在且非空时跳过（残缺文件不算"已存在"）
skip_if_done() {  # $1=path
  if [ -s "$1" ] && [ "$FORCE" != "1" ]; then
    log "已存在且非空，跳过：$1"
    return 0
  fi
  return 1
}

# 原子下载：写 .part 再 mv
fetch() {  # $1=url $2=dest
  local dest="$1"; local url="$2"
  if skip_if_done "$dest"; then return 0; fi
  log "下载 $(basename "$dest")"
  curl "${CURL_OPTS[@]}" -o "$dest.part" "$url"
  mv -f "$dest.part" "$dest"
}

mean_cov() {  # $1=region $2=bam
  samtools depth -a -r "$1" "$2" 2>/dev/null \
    | awk '{s+=$3; n++} END {if (n>0) printf "%.2f", s/n; else print "0"}'
}

# ---------------------------------------------------------------------------
# 1) 参考基因组（chr20，公有领域）
# ---------------------------------------------------------------------------
if ! skip_if_done "$REF_DIR/$CONTIG.fa"; then
  fetch "$REF_DIR/$CONTIG.fa.gz" "$REF_URL"
  gunzip -f "$REF_DIR/$CONTIG.fa.gz"
  samtools faidx "$REF_DIR/$CONTIG.fa"
  log "参考序列就绪：$(grep -v '^>' "$REF_DIR/$CONTIG.fa" | tr -d '\n' | wc -c) bp"
fi

# ---------------------------------------------------------------------------
# 2) 远程按区域取 BAM
# ---------------------------------------------------------------------------
REGION_BAM="$WORK_DIR/HG002.$CONTIG.region.bam"
if ! skip_if_done "$REGION_BAM"; then
  log "远程取区域 $REGION（源 121.79 GB，只传输该区段）"
  samtools view -b "$BAM_URL" "$REGION" -o "$REGION_BAM.part"
  mv -f "$REGION_BAM.part" "$REGION_BAM"
  samtools index "$REGION_BAM"
  log "区域 BAM 大小：$(du -h "$REGION_BAM" | cut -f1)"
fi
[ -f "$REGION_BAM.bai" ] || samtools index "$REGION_BAM"

# ---------------------------------------------------------------------------
# 3) 估计覆盖度 → 计算降采样比例
# ---------------------------------------------------------------------------
BASE="${REGION#*:}"; BASE="${BASE%%-*}"
PROBE="$CONTIG:$BASE-$((BASE + 100000))"
log "估计覆盖度（探针区 $PROBE）"
OBSERVED="$(mean_cov "$PROBE" "$REGION_BAM")"
log "实测覆盖度 ≈ ${OBSERVED}×，目标 ${TARGET_COV}×"
FRAC="$(awk -v t="$TARGET_COV" -v o="$OBSERVED" 'BEGIN{ if (o<=0) {print "0"; exit} f=t/o; if (f>1) f=1; printf "%.6f", f }')"
log "降采样比例 = ${FRAC}（seed=${SEED}）"

# ---------------------------------------------------------------------------
# 4) 降采样（固定 seed，可复现）
# ---------------------------------------------------------------------------
SAMPLED="$ALN_DIR/HG002.$CONTIG.${TARGET_COV}x.bam"
if ! skip_if_done "$SAMPLED"; then
  log "降采样中"
  samtools view -b --subsample "$FRAC" --subsample-seed "$SEED" \
    "$REGION_BAM" -o "$SAMPLED.part"
  mv -f "$SAMPLED.part" "$SAMPLED"
  samtools index "$SAMPLED"
fi
[ -f "$SAMPLED.bai" ] || samtools index "$SAMPLED"

# ---------------------------------------------------------------------------
# 5) 验证降采样后的覆盖度（三个窗口）
# ---------------------------------------------------------------------------
log "验证降采样后覆盖度（3 个窗口）"
for off in 0 500000 1000000; do
  s=$((BASE + off)); e=$((s + 50000))
  c="$(mean_cov "$CONTIG:$s-$e" "$SAMPLED")"
  log "  $CONTIG:$s-$e → ${c}×"
  awk -v c="$c" -v t="$TARGET_COV" 'BEGIN{ d=(c-t)/t; if (d<0) d=-d; if (d>0.25) exit 1 }' \
    || log "  ⚠️ 警告：该窗口覆盖度偏离目标 >25%，需在 manifest 中标注"
done
samtools flagstat "$SAMPLED" 2>&1 | sed 's/^/  flagstat: /' >&2

# ---------------------------------------------------------------------------
# 6) 真值（v5.0q smvar）：裁剪到目标区域
# ---------------------------------------------------------------------------
TRUTH_VCF="$TRUTH_DIR/HG002_GRCh38_v5.0q_smvar.region.vcf.gz"
TRUTH_BED="$TRUTH_DIR/HG002_GRCh38_v5.0q_smvar.benchmark.region.bed"
if ! skip_if_done "$TRUTH_VCF"; then
  fetch "$TRUTH_DIR/truth.full.vcf.gz" "$TRUTH_VCF_URL"
  fetch "$TRUTH_DIR/truth.full.vcf.gz.tbi" "$TRUTH_VCF_URL.tbi"
  bcftools view -r "$REGION" -Oz -o "$TRUTH_VCF.part" "$TRUTH_DIR/truth.full.vcf.gz"
  mv -f "$TRUTH_VCF.part" "$TRUTH_VCF"
  tabix -f -p vcf "$TRUTH_VCF"
  fetch "$TRUTH_DIR/full.benchmark.bed" "$TRUTH_BED_URL"
  awk -v c="$CONTIG" -v r="$REGION" \
    'BEGIN{split(r,a,":"); split(a[2],b,"-"); s=b[1]; e=b[2]}
     $1==c && $2<e && $3>s { st=($2>s?$2:s); en=($3<e?$3:e); print c"\t"st"\t"en }' \
    "$TRUTH_DIR/full.benchmark.bed" > "$TRUTH_BED.part"
  mv -f "$TRUTH_BED.part" "$TRUTH_BED"
  rm -f "$TRUTH_DIR/truth.full.vcf.gz" "$TRUTH_DIR/truth.full.vcf.gz.tbi" "$TRUTH_DIR/full.benchmark.bed"
  log "真值区域内变异数：$(bcftools view -H "$TRUTH_VCF" | wc -l | tr -d ' ')"
fi

# ---------------------------------------------------------------------------
# 6.5) 断言真的产出了文件
#      踩过的坑：ENV 变量撞名会把数据写进未挂载目录，容器一删就没了，
#      而脚本仍然以 0 退出 —— 这种"假成功"比直接报错危险得多。
# ---------------------------------------------------------------------------
n_files="$(find "$DATA_DIR" -type f ! -name 'sources.json' ! -name 'manifest.json' | wc -l | tr -d ' ')"
log "产出文件数：${n_files}，目录合计 $(du -sh "$DATA_DIR" | cut -f1)"
if [ "$n_files" -eq 0 ]; then
  log "❌ 未产出任何文件 —— 请检查 DATA_DIR（当前 ${DATA_DIR}）是否指向挂载目录"
  exit 4
fi

# ---------------------------------------------------------------------------
# 7) 溯源事实（供 make_manifest.py 合并成 manifest.json）
# ---------------------------------------------------------------------------
cat > "$DATA_DIR/sources.json" <<JSON
{
  "dataset": "biobench-lite-t1-hg002-chr20",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "region": "$REGION",
  "target_coverage": $TARGET_COV,
  "observed_coverage_source": $OBSERVED,
  "subsample_fraction": $FRAC,
  "subsample_seed": $SEED,
  "sources": [
    {
      "role": "aln-source",
      "url": "$BAM_URL",
      "bytes": $BAM_BYTES,
      "md5_official": "$BAM_MD5",
      "note": "GIAB HG002 Illumina 2x250；整文件 121.79 GB，本数据集只取 ${REGION} 区段并降采样到 ${TARGET_COV}x",
      "license": "US Government work / public domain；HG002 明确同意商用再分发（NIST genome-bottle FAQ Q11）"
    },
    {
      "role": "truth-vcf",
      "url": "$TRUTH_VCF_URL",
      "note": "GIAB/NIST v5.0q 小变异真值（smvar），已裁剪到目标区域",
      "license": "US Government work / public domain"
    },
    {
      "role": "truth-bed",
      "url": "$TRUTH_BED_URL",
      "note": "高置信区间（benchmark regions），已裁剪到目标区域",
      "license": "US Government work / public domain"
    },
    {
      "role": "reference",
      "url": "$REF_URL",
      "note": "UCSC hg38 chr20（与 GRCh38 chr20 主 contig 序列一致）",
      "license": "public domain"
    }
  ],
  "provenance_notes": [
    "源 BAM 的比对参考为 GRCh38_full_plus_hs38d1_analysis_set_minus_alts（取自 BAM @PG 行）；chr20 主 contig 坐标与 GRCh38 chr20 一致",
    "降采样用 samtools view --subsample + 固定 seed，可用同一命令复现",
    "真值使用 v5.0q（v4.2.1 自 2025-11 起 deprecated）；不使用 HG001，其捐献同意未明确覆盖商用再分发"
  ]
}
JSON

log "溯源记录已写入 $DATA_DIR/sources.json"
log "完成。下一步：python3 /work/data/make_manifest.py --data $DATA_DIR"
