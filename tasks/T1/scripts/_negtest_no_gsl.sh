#!/usr/bin/env bash
# 负向测试：证明 check_no_gsl.sh **真的会失败**。
# 一个不能失败的检查比没有更坏。
#
# 手法：装一个 libgsl 库文件，让"文件系统"那道检查必须报错；
# 再造一个假的 bcftools 让"行为"那道检查必须报错。
set -uo pipefail
GATE=/gate/check_no_gsl.sh
echo "############ 用例 1：在干净镜像上跑门禁 —— 必须通过（exit 0）############"
bash "$GATE"
echo "==> 用例 1 退出码 = $?"
echo

echo "############ 用例 2：放入 libgsl.so → D 检查必须失败 ############"
mkdir -p /usr/lib/x86_64-linux-gnu
# 造一个最小的假 GSL 共享库（内容不重要，门禁看的是文件名/依赖/符号）
cp /usr/bin/bcftools /usr/lib/x86_64-linux-gnu/libgsl.so.27 2>/dev/null || \
  echo "fake" > /usr/lib/x86_64-linux-gnu/libgsl.so.27
bash "$GATE" > /tmp/case2.log 2>&1
rc=$?
echo "==> 用例 2 退出码 = $rc （必须非 0）"
grep -E '失败|D/4' /tmp/case2.log | head -5
rm -f /usr/lib/x86_64-linux-gnu/libgsl.so.27
echo

echo "############ 用例 3：伪造一个会响应 polysomy 的 bcftools → C 检查必须失败 ############"
# 模拟"启用了 USE_GPL"的构建：polysomy 不是 unrecognized
mkdir -p /tmp/fakebin
cat > /tmp/fakebin/bcftools <<'EOF'
#!/bin/bash
if [ "${1:-}" = "polysomy" ]; then echo "Usage: bcftools polysomy [options]"; exit 0; fi
if [ "${1:-}" = "--version" ]; then echo "bcftools 1.16"; echo "License GPLv3+: GNU GPL version 3"; exit 0; fi
echo "Usage: bcftools <command>"
EOF
chmod +x /tmp/fakebin/bcftools
PATH="/tmp/fakebin:$PATH" bash "$GATE" > /tmp/case3.log 2>&1
rc=$?
echo "==> 用例 3 退出码 = $rc （必须非 0）"
grep -E 'polysomy|失败' /tmp/case3.log | head -5
echo

echo "############ 用例 4：静态链接痕迹 → B 检查必须失败 ############"
# 造一个含 gsl_ 符号的假二进制，替换掉一个被扫的路径
cp /usr/bin/tabix /tmp/tabix.bak
python3 - <<'PY'
d = open('/usr/bin/tabix','rb').read()
# 追加一段含 gsl_* 符号的字节
d += b"\x00gsl_sf_lnbeta\x00gsl_rng_alloc\x00gsl_vector_alloc\x00"
open('/usr/bin/tabix','wb').write(d)
PY
bash "$GATE" > /tmp/case4.log 2>&1
rc=$?
echo "==> 用例 4 退出码 = $rc （必须非 0）"
grep -E '痕迹|失败' /tmp/case4.log | head -4
cp /tmp/tabix.bak /usr/bin/tabix
chmod +x /usr/bin/tabix

echo
echo "############ 复位后复跑 —— 必须重新通过 ############"
bash "$GATE" > /tmp/case5.log 2>&1
echo "==> 复位后退出码 = $? （必须为 0）"
tail -2 /tmp/case5.log
