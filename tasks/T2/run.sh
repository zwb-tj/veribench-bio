#!/usr/bin/env bash
# VeriBench-Bio · T2 流水线：校验 → 判分
#
# T2 与 T1 不同：**不需要任何生信工具**。被测系统拿到的是去标识化证据包（纯文本），
# 输出的是「分类 + 它认为成立的 ACMG 判据」。所以这里只做两件事：
#   1. 再查一次题面有没有泄漏（防止挂载进来的 items.jsonl 被替换）
#   2. 判分
#
# 挂载约定：
#   /data/items.jsonl   题面（可来自镜像，也可挂载覆盖）
#   /data/truth.jsonl   真值（**只读挂载**；镜像里不含真值，见 Dockerfile）
#   /out/answers.jsonl  被测系统的作答
#   /out/result.json    判分结果
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
OUT_DIR="${OUT_DIR:-/out}"
# 题面来自镜像（可用挂载覆盖）；真值**只读挂载**进来（镜像里不含真值，见 Dockerfile）
ITEMS="${ITEMS:-/work/items.jsonl}"
TRUTH="${TRUTH:-$DATA_DIR/truth.jsonl}"
ANSWERS="${ANSWERS:-$OUT_DIR/answers.jsonl}"

log() { printf '[run.sh %s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }

mkdir -p "$OUT_DIR"

# --- 前置检查：缺文件立刻报错，别跑到一半才发现 ---------------------------
missing=0
for f in "$ITEMS" "$TRUTH" "$ANSWERS"; do
  if [ ! -f "$f" ]; then log "缺少：$f"; missing=1; fi
done
if [ "$missing" -eq 1 ]; then
  log "需要：items.jsonl（题面，镜像内已有）、truth.jsonl（真值，只读挂载）、answers.jsonl（作答）"
  exit 2
fi

# --- 1) 泄露复检 ------------------------------------------------------------
# 题面泄漏会让 T2 退化成记忆测试，而且是**悄悄**退化。构建期已查过一次，
# 但挂载进来的文件可能被替换，所以运行期再查一次（很便宜）。
log "泄露复检"
if ! python3 /work/check_no_leakage.py --items "$ITEMS" --truth "$TRUTH" --quiet; then
  log "❌ 题面泄露检查未通过 —— 拒绝判分"
  exit 3
fi

# --- 2) 判分 ---------------------------------------------------------------
log "判分中"
T0=$(date +%s)
set +e
python3 /work/grade.py \
  --items "$ITEMS" \
  --truth "$TRUTH" \
  --answers "$ANSWERS" \
  --out "$OUT_DIR/result.json"
rc=$?
set -e
T1=$(date +%s)

if [ "$rc" -ne 0 ]; then
  log "❌ 判分失败（退出码 $rc）"
  exit "$rc"
fi

log "判分完成，耗时 $((T1 - T0)) 秒 → $OUT_DIR/result.json"
