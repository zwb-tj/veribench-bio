#!/usr/bin/env bash
# T1 判分器自检（容器内运行，不依赖 GIAB 真实数据）
#
# 目的：在碰真实数据之前，先证明判分器算得对。
# 一个没被测过的判分器是负债 —— 它会静默地把错的分发出去。
#
# 用法（在宿主机）：
#   docker run --rm -v "<repo>/bio-eval/tasks/T1/selftest:/selftest:ro" \
#     veribench-bio/t1:dev -lc "bash /selftest/run_selftest.sh"
set -euo pipefail

SELFTEST_DIR="${SELFTEST_DIR:-/selftest}"
WORK="${WORK:-/tmp/selftest}"
rm -rf "$WORK"
mkdir -p "$WORK"

echo "== 1/6 生成合成数据（参考序列 + 真值 + 两个解法） =="
python3 "$SELFTEST_DIR/make_synthetic.py" --out "$WORK"

cd "$WORK"

echo
echo "== 2/6 建参考 SDF（rtg format，BSD-2） =="
rtg format -o ref.sdf ref.fa

echo
echo "== 3/6 压缩 + 索引三个 VCF（bgzip/tabix，MIT） =="
for f in truth calls_perfect calls_partial; do
  bcftools view -Oz -o "$f.vcf.gz" "$f.vcf"
  tabix -f -p vcf "$f.vcf.gz"
  echo "  ok $f.vcf.gz"
done

echo
echo "== 4/6 判分：完美解法（期望 score = 1.0） =="
python3 /work/grade.py \
  --calls calls_perfect.vcf.gz --truth truth.vcf.gz \
  --ref-sdf ref.sdf --bed confident.bed \
  --out perfect.json --workdir wk_perfect > /dev/null
python3 -c "import json;d=json.load(open('perfect.json'));print('  score=',d['score'],' status=',d['status'],' snp_f1=',d['per_type']['snps']['f1'],' indel_f1=',d['per_type']['indels']['f1'])"

echo
echo "== 5/6 判分：部分解法（期望 score = 0.25） =="
python3 /work/grade.py \
  --calls calls_partial.vcf.gz --truth truth.vcf.gz \
  --ref-sdf ref.sdf --bed confident.bed \
  --out partial.json --workdir wk_partial > /dev/null
python3 -c "import json;d=json.load(open('partial.json'));print('  score=',d['score'],' status=',d['status'],' snp_f1=',d['per_type']['snps']['f1'],' indel_f1=',d['per_type']['indels']['f1']);print('  problems=',d['problems'])"

echo
echo "== 6/6 断言 =="
python3 "$SELFTEST_DIR/assert_results.py" perfect.json partial.json
