#!/usr/bin/env bash
# 许可门禁：证明镜像里**没有** GSL 被链接进来。
#
# 为什么不能只用 `ldd | grep libgsl`
# ----------------------------------
# 2026-09 复核 Debian 的 bcftools 许可时发现，原来的门禁有三个真实盲区：
#
#   1. **静态链接看不见。** `ldd` 只列**动态**依赖。若 GSL 被静态链进去，
#      二进制里确实含 GSL 代码（→ GPL-governed），但 `ldd` 输出**完全干净**。
#      这道门禁会**假通过**。
#   2. **插件根本没扫。** bcftools 的插件（/usr/lib/*/bcftools/*.so）是运行时
#      动态加载的，不在 `command -v bcftools` 的 `ldd` 里。实测镜像里有 39 个插件。
#   3. **没验行为。** 上游 `bcftools/Makefile` 写得很清楚：
#          # The polysomy command is not compiled by default because it brings
#          # dependency on libgsl. ... can be compiled with `make USE_GPL=1`
#          ifdef USE_GPL
#              OBJS += polysomy.o peakfit.o
#              GSL_LIBS ?= -lgsl -lcblas
#          endif
#      也就是说 **USE_GPL 就是「要不要 GSL」的开关**，而它的**行为表现**是
#      `bcftools polysomy` 这个子命令在不在。**行为比文本可靠**（见 SPEC §3.1）。
#
# 本脚本四道检查，任何一道失败即 `exit 1`（失败必须响亮）：
#   A. 动态依赖：主程序 + 所有插件都不得 NEEDED libgsl/libcblas
#   B. 静态痕迹：主程序 + 所有插件的字节里不得出现 `gsl_*` 符号
#   C. 行为：`bcftools polysomy` **必须不存在**（存在 = USE_GPL 被打开）
#   D. 文件系统：镜像内不得存在任何 libgsl/libcblas 共享库
#
# 用法：bash check_no_gsl.sh
set -uo pipefail

FAIL=0
note() { printf '  %s\n' "$*"; }
fail() { printf '  [失败] %s\n' "$*"; FAIL=1; }
ok()   { printf '  [ok] %s\n' "$*"; }

echo "== 许可门禁 A/4：动态依赖（主程序 + 全部插件）=="
BINS=""
for b in samtools bcftools tabix freebayes; do
  p="$(command -v "$b" 2>/dev/null || true)"
  [ -n "$p" ] && BINS="$BINS $p" || note "[跳过] 未找到 $b"
done
# 插件也要扫 —— 这是原来漏掉的那一类
PLUGINS="$(find /usr/lib -path '*/bcftools/*.so' 2>/dev/null | tr '\n' ' ')"
n_plugins=$(printf '%s' "$PLUGINS" | wc -w | tr -d ' ')
note "扫描 $(printf '%s' "$BINS" | wc -w | tr -d ' ') 个主程序 + ${n_plugins} 个 bcftools 插件"
for p in $BINS $PLUGINS; do
  if ldd "$p" 2>/dev/null | grep -qiE 'libgsl|libcblas'; then
    fail "$p 动态链接了 libgsl/libcblas"
  fi
done
[ "$FAIL" = 0 ] && ok "无任何动态依赖指向 libgsl/libcblas"

echo
echo "== 许可门禁 B/4：静态链接痕迹（字节级扫 gsl_* 符号）=="
# 用 python3 扫原始字节：静态链接会把 gsl_* 符号名留在文件里。
# 镜像里没有 strings/nm/readelf，所以不能依赖它们（**这也是一个教训**：
# 我第一次用 `strings | grep -c gsl_` 得到 0，其实是因为 `strings` 根本没装，
# 那个 0 是"命令失败"，不是"没有 GSL"）。
if ! command -v python3 >/dev/null 2>&1; then
  fail "没有 python3，无法做字节级扫描 —— 不能静默跳过"
else
  python3 - "$BINS" "$PLUGINS" <<'PY'
import re, sys
paths = (sys.argv[1] + " " + sys.argv[2]).split()
GSL = re.compile(rb"\bgsl_[a-z0-9_]{3,}\b")
LIB = re.compile(rb"libgsl[a-zA-Z0-9._+-]*|libcblas[a-zA-Z0-9._+-]*")
bad = []
for p in paths:
    try:
        d = open(p, "rb").read()
    except OSError:
        continue
    syms = {m.group(0) for m in GSL.finditer(d)}
    libs = {m.group(0) for m in LIB.finditer(d)}
    if syms or libs:
        bad.append((p, sorted(x.decode('ascii','replace') for x in (syms|libs))[:6]))
if bad:
    for p, hits in bad:
        print(f"  [失败] {p} 里出现 GSL 痕迹: {hits}")
    sys.exit(1)
print(f"  [ok] {len(paths)} 个二进制里都没有 gsl_* / libgsl 痕迹（含静态链接）")
PY
  [ $? -ne 0 ] && FAIL=1
fi

echo
echo "== 许可门禁 C/4：行为验证 —— bcftools polysomy 必须不存在 =="
# 这是**决定性**的检查：polysomy 是上游唯一需要 GSL 的命令，
# 它存在 ⇔ 编译时开了 USE_GPL。
if command -v bcftools >/dev/null 2>&1; then
  out="$(bcftools polysomy 2>&1 || true)"
  if printf '%s' "$out" | grep -qi 'unrecognized'; then
    ok "bcftools polysomy 不存在 → 未启用 USE_GPL（无 GSL 版 polysomy）"
  else
    fail "bcftools polysomy **存在** → 该构建启用了 USE_GPL，GSL 已被编入（GPL-governed）"
    note "输出：$(printf '%s' "$out" | head -2 | tr '\n' ' ')"
  fi
  # 旁证：自报的许可证行
  if bcftools --version 2>/dev/null | grep -qi 'Expat'; then
    ok "bcftools 自报 License Expat（MIT/Expat）"
  else
    note "[注意] bcftools --version 未自报 Expat 许可，请人工确认"
  fi
else
  fail "找不到 bcftools，无法做行为验证 —— 不能静默跳过"
fi

echo
echo "== 许可门禁 D/4：文件系统里不得存在 GSL 共享库 =="
found="$(find / \( -name 'libgsl*' -o -name 'libcblas*' \) -not -path '/proc/*' 2>/dev/null | head -5)"
if [ -n "$found" ]; then
  fail "镜像内存在 GSL 相关库文件："
  printf '%s\n' "$found" | sed 's/^/      /'
else
  ok "镜像内不存在任何 libgsl*/libcblas* 文件"
fi
# 原来的"禁止包"检查保留
for p in r-base r-base-core gsl-bin libgsl27 libgsl-dev mkl intel-mkl; do
  if dpkg -s "$p" >/dev/null 2>&1; then
    fail "镜像含禁止包：$p"
  fi
done

echo
if [ "$FAIL" != 0 ]; then
  echo "== 许可门禁失败 =="
  echo "   注意：Debian 的 bcftools/copyright 里有一句"
  echo "   \"When linked with the GPL-licensed GNU Scientific Library (as is done"
  echo "    for this Debian package), the resulting program must be distributed"
  echo "    under the GPL.\""
  echo "   本轮已实证这句话对本镜像**不成立**（polysomy 未编入、无符号、无依赖）；"
  echo "   但如果你换了 Debian 版本/bcftools 版本，必须重新跑这道门禁。"
  exit 1
fi
echo "== 许可门禁全部通过（动态 + 静态 + 行为 + 文件系统）=="
