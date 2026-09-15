#!/usr/bin/env bash
# T3 运行入口 —— 契约与 T1/T2 一致（见 tasks/T3/DESIGN.md §5.2）
#
# 用法（与 T2 相同）：
#   docker run --rm \
#     -v "$PWD/tasks/T3/data/truth.jsonl:/data/truth.jsonl:ro" \
#     -v "$PWD/tasks/T3/_runs:/out" \
#     veribench-bio/t3:dev
#
#   挂载点：
#     /data/items.jsonl   题面（镜像内已有，可挂载覆盖）
#     /data/truth.jsonl   真值（**只读挂载**；镜像里不含真值）
#     /out/answers.jsonl  被测系统的作答
#     /out/result.json    判分结果
set -euo pipefail

OUT_DIR="${OUT_DIR:-/out}"
DATA_DIR="${DATA_DIR:-/data}"
ITEMS="${ITEMS:-/work/items.jsonl}"
TRUTH="${TRUTH:-$DATA_DIR/truth.jsonl}"
ANSWERS="${ANSWERS:-$OUT_DIR/answers.jsonl}"

mkdir -p "$OUT_DIR"

echo "T3 run.sh"
echo "  ITEMS   = $ITEMS"
echo "  TRUTH   = $TRUTH"
echo "  ANSWERS = $ANSWERS"
echo "  OUT_DIR = $OUT_DIR"

# 1) 再查一次题面（防止挂载进来的 items.jsonl 被替换）
python3 /work/mmcif_parse.py --self-test >/dev/null
echo "  mmcif_parse 自检通过"

# 2) 判分
python3 /work/grade.py \
  --items "$ITEMS" \
  --truth "$TRUTH" \
  --answers "$ANSWERS" \
  --out "$OUT_DIR/result.json"

echo "完成：$OUT_DIR/result.json"
