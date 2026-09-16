#!/usr/bin/env bash
# T4 运行入口 —— 契约与 T1/T2/T3 一致（见 tasks/T4/DESIGN.md §5）
#
# 用法：
#   docker run --rm \
#     -v "$PWD/tasks/T4/data/truth.jsonl:/data/truth.jsonl:ro" \
#     -v "$PWD/tasks/T4/_runs:/out" \
#     veribench-bio/t4:dev
set -euo pipefail

OUT_DIR="${OUT_DIR:-/out}"
DATA_DIR="${DATA_DIR:-/data}"
ITEMS="${ITEMS:-/work/items.jsonl}"
TRUTH="${TRUTH:-$DATA_DIR/truth.jsonl}"
ANSWERS="${ANSWERS:-$OUT_DIR/answers.jsonl}"

mkdir -p "$OUT_DIR"

echo "T4 run.sh"
echo "  ITEMS   = $ITEMS"
echo "  TRUTH   = $TRUTH"
echo "  ANSWERS = $ANSWERS"
echo "  OUT_DIR = $OUT_DIR"

# 1) 解析器自检（证明它在坏输入上会失败）
python3 /work/obo_parse.py --self-test >/dev/null
echo "  obo_parse 自检通过"

# 2) 判分
python3 /work/grade.py \
  --items "$ITEMS" \
  --truth "$TRUTH" \
  --answers "$ANSWERS" \
  --out "$OUT_DIR/result.json"

echo "完成：$OUT_DIR/result.json"
