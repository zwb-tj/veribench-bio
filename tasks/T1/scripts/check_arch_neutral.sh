#!/usr/bin/env bash
# 架构中立性检查：这个镜像能不能在非 x86 CPU 上跑。
#
# 为什么需要它（本项目已抓到两个真问题）
# ------------------------------------
# 1. 上游 RTG Tools 的 `...-linux-x64.zip` 里**捆了一个 amd64 专用 JRE**
#    （jre/lib/amd64/*.so），而 rtg 启动脚本会**优先**用它。
# 2. 更致命的是：上游 `rtg` 脚本开头**硬编码** `uname -m != x86_64 → exit 1`，
#    在 arm64 上 0.1 秒内直接失败。
# → 光看图看不出来，必须**实测**。
#
# 判据：
#   A. 镜像里**自行引入**的组件（非 apt）不得含原生二进制（ELF）
#   B. 不得存在 amd64/x86_64 专用路径（在 arm64 上毫无意义）
#   C. 关键命令**真的能运行**（不是"装上了"就算数）
#
# 同一脚本两处复用：
#   - 构建期：由 Dockerfile COPY 进来后直接 RUN（失败即中断构建）
#   - 运行期：docker run --rm -v ".../scripts:/scripts:ro" <image> -lc "bash /scripts/check_arch_neutral.sh"
set -uo pipefail

fail=0

echo "=== 0) 容器架构 ==="
echo "  uname -m : $(uname -m)"
echo "  dpkg arch: $(dpkg --print-architecture 2>/dev/null || echo '(无 dpkg)')"

echo
echo "=== A) 架构专用路径（应为空） ==="
found="$(find /opt /usr/local -maxdepth 6 \( -name '*amd64*' -o -name '*x86_64*' \) 2>/dev/null | head -20)"
if [ -n "$found" ]; then
  echo "$found"
  echo "  ❌ 发现架构专用路径"
  fail=1
else
  echo "  ✅ 无"
fi

echo
echo "=== B) 自行引入的组件里有无原生二进制（ELF，应为空） ==="
n=0
while IFS= read -r f; do
  if head -c4 "$f" 2>/dev/null | grep -q ELF; then
    echo "  ELF: $f"
    n=$((n + 1))
  fi
done < <(find /opt /usr/local -type f 2>/dev/null)
if [ "$n" -eq 0 ]; then
  echo "  ✅ 无 —— 自行引入的组件全是脚本 / Java / 数据"
else
  echo "  ❌ 发现 $n 个原生二进制"
  fail=1
fi

echo
echo "=== C) 关键命令能否真的运行 ==="
for b in samtools bcftools tabix freebayes java python3; do
  p="$(command -v "$b" 2>/dev/null)" || { printf '  %-10s ❌ 缺失\n' "$b"; fail=1; continue; }
  if v="$("$b" --version 2>&1 | head -n1)"; then
    printf '  %-10s ✅ %s\n' "$b" "$v"
  else
    printf '  %-10s ❌ 存在但无法运行：%s\n' "$b" "$p"
    fail=1
  fi
done

# rtg 要单独测：上游包装脚本有架构检查，失败时**必须把错误打出来**
# （曾因为把输出重定向到 /dev/null，把关键错误吞掉了整整一轮）
echo
echo "=== D) rtg 能否运行（上游脚本有架构检查，重点看这里） ==="
if [ -f /opt/rtg-tools/RTG.jar ]; then echo "  ✅ RTG.jar 存在（纯 Java）"; else echo "  ❌ 缺 RTG.jar"; fail=1; fi
if [ -e /opt/rtg-tools/jre ]; then echo "  ❌ 捆包 JRE 仍存在（架构专用！）"; fail=1; else echo "  ✅ 无捆包 JRE"; fi
echo "  rtg 配置: $(cat /etc/rtg.cfg 2>/dev/null || echo '(缺失 —— 应显式指定 RTG_JAVA)')"
if out="$(rtg version 2>&1)"; then
  echo "  ✅ rtg 可运行：$(echo "$out" | head -n1)"
else
  echo "  ❌ rtg 无法运行。完整输出如下："
  echo "$out" | head -n 20 | sed 's/^/      /'
  fail=1
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "✅ 架构中立性检查通过。"
else
  echo "❌ 架构中立性检查未通过（见上）。"
fi
exit "$fail"
