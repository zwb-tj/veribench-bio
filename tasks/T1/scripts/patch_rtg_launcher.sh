#!/usr/bin/env bash
# 去掉上游 rtg 启动脚本里硬编码的 x86_64 检查。
#
# ── 上游原文（rtg-tools 3.12.1 的 rtg 脚本开头）────────────────────────
#     elif [[ "$(uname -m)" != "x86_64" ]]; then
#         # If you comment this check out you are on your own :-)
#         echo "Sorry, you must be running a 64bit operating system."
#         exit 1
#     fi
#
# ── 为什么必须处理 ────────────────────────────────────────────────────
# 实测：在 arm64 上 rtg **0.1 秒内直接 exit 1**，判分器完全不可用。
# 这会让"任何人都能用笔记本复现"的承诺在 Apple Silicon 上当场失效。
#
# ── 为什么可以去掉这个检查 ────────────────────────────────────────────
# 1. RTG.jar 是**纯 Java**，与 CPU 架构无关
# 2. 已确认 /opt/rtg-tools 内**不存在任何 ELF 原生二进制**（见 check_arch_neutral.sh）
# 3. 已删掉上游捆的 amd64 JRE（jre/lib/amd64/*.so），改用系统 Java
# 4. 该检查写于上游还随包分发 x86_64 JRE 的年代，属保守式"安全带"
#
# ── 合规 ──────────────────────────────────────────────────────────────
# 这是对上游代码的**修改**。RTG Tools 为 BSD-2-Clause，允许修改与再分发，
# 但必须在 MODIFICATIONS / NOTICE 中声明（我们已声明）。
#
# 用法：
#   patch_rtg_launcher.sh [/opt/rtg-tools/rtg]     # 打补丁
#   patch_rtg_launcher.sh --self-test             # 自测补丁逻辑（不需要真实文件）
set -euo pipefail

PATCH_MARK='!= "x86_64"'
UPSTREAM_SNIPPET='#!/bin/bash
# Pre-flight safety-belts
if [[ "$(uname -s)" != "Linux" ]] && [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Sorry, only Linux and MacOS are supported."
    exit 1
elif [[ "$(uname -m)" != "x86_64" ]]; then
    echo "Sorry, you must be running a 64bit operating system."
    exit 1
fi
echo "reached-main-body"'

apply_patch() {
  local f="$1"
  [ -f "$f" ] || { echo "❌ 找不到 $f"; return 1; }

  if ! grep -q "$PATCH_MARK" "$f"; then
    echo "❌ 目标文件里找不到上游的 x86_64 检查（上游脚本可能已变更）"
    echo "--- 文件中与 uname 相关的行 ---"
    grep -n 'uname' "$f" | head -10 | sed 's/^/    /'
    return 1
  fi

  # 把该分支条件改成**恒假**：`uname -m == "x86_64_disabled"` 永远不成立。
  # 保留包装脚本其余逻辑（内存设置、classpath、配置加载、talkback）。
  #
  # ⚠️ 这里踩过一个严重的坑：最初改成 `!= ""`，而 `uname -m` **永远不为空**，
  #    于是条件恒真 → 在**所有**架构上都 exit 1（把"只在非 x86_64 失败"
  #    改成"永远失败"）。文本检查看不出来，是行为自测抓到的。
  #    → 教训：**验证行为，不要只验证文本。**
  # 模式里不含 $，避免被 Dockerfile 的环境变量替换吞掉。
  sed -i 's/!= "x86_64" \]\]; then/== "x86_64_disabled" ]]; then/' "$f"

  # 验证：检查**坏模式是否已消失**（比"匹配新文本"稳，不依赖精确的引号/括号形态）。
  # 这里踩过坑：曾用 grep 'uname -m" != ""' 做断言，漏了 uname -m 后面的 `)`，
  # 导致断言永远失败、构建被 fail-closed 拦下 —— 拦下是对的，但断言本身错了。
  if grep -q "$PATCH_MARK" "$f"; then
    echo "❌ 补丁未生效：硬编码的 x86_64 检查仍然存在"
    grep -n -B2 -A3 'uname -m' "$f" | head -20 | sed 's/^/    /'
    return 1
  fi

  if ! bash -n "$f"; then
    echo "❌ 补丁后脚本语法检查失败（bash -n）"
    return 1
  fi

  echo "✅ 补丁生效：x86_64 检查已移除，且 bash -n 通过"
  return 0
}

self_test() {
  local tmp rc=0
  tmp="$(mktemp)"
  printf '%s\n' "$UPSTREAM_SNIPPET" > "$tmp"
  chmod +x "$tmp"

  echo "--- 补丁前：应含 $PATCH_MARK ---"
  if grep -q "$PATCH_MARK" "$tmp"; then echo "  ✅ 确认存在"; else echo "  ❌ 测试样本构造有误"; rc=1; fi

  echo "--- 打补丁 ---"
  if ! apply_patch "$tmp"; then rc=1; fi

  echo "--- 补丁后：应不含 $PATCH_MARK ---"
  if grep -q "$PATCH_MARK" "$tmp"; then echo "  ❌ 仍存在"; rc=1; else echo "  ✅ 已移除"; fi

  echo "--- 补丁后：脚本应能走到主逻辑 ---"
  local out
  out="$(bash "$tmp" 2>&1 || true)"
  if printf '%s' "$out" | grep -q 'reached-main-body'; then
    echo "  ✅ 输出: $out"
  else
    echo "  ❌ 未能到达主逻辑，输出: $out"
    rc=1
  fi

  rm -f "$tmp"
  if [ "$rc" -eq 0 ]; then
    echo "✅ 补丁脚本自测通过"
  else
    echo "❌ 补丁脚本自测未通过"
  fi
  return "$rc"
}

if [ "${1:-}" = "--self-test" ]; then
  self_test
  exit $?
fi

apply_patch "${1:-/opt/rtg-tools/rtg}"
