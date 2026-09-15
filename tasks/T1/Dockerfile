# syntax=docker/dockerfile:1
#
# VeriBench-Bio · T1 变异检出容器
# 全链路零 copyleft：MIT / BSD-2 / Apache 等价组件（见 ../../SPEC.md §4.4）
#
# 与官方 GATK 镜像的对比：官方环境会引入专有 Intel oneMKL、GPL 的 R/GSL、
# LGPL 的 htsjdk-tribble（不可剥离）（见 ../../SPEC.md §5.6）。
# 本镜像刻意不打包 GATK4 —— 换 FreeBayes 后这些问题同时消失，镜像也小得多。

FROM debian:bookworm-slim

LABEL org.opencontainers.image.title="veribench-bio-t1-variant-calling"
LABEL org.opencontainers.image.licenses="MIT AND BSD-2-Clause"
LABEL org.opencontainers.image.description="VeriBench-Bio T1 variant calling task (permissive-license toolchain)"

ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8

# ---------------------------------------------------------------------------
# 组件与其许可（逐项在手核验过的会标注）
#   samtools / bcftools / tabix  : MIT
#   freebayes                    : MIT   （已亲手读上游 LICENSE 原文）
#   default-jre-headless         : OpenJDK, GPL-2 WITH Classpath-exception-2.0
#                                  → 按 SPEC §5.6⑤ 属"假阳性放行"
# ---------------------------------------------------------------------------
# 依赖安装
#
#   ⚠️ 一段走弯路的记录，留着比删掉有用：
#   `deb.debian.org` 曾对 arm64 的 pool 路径返回 502 Bad Gateway（CDN 侧临时故障），
#   导致 arm64 构建失败。当时我加了"首个源失败自动切备用源"的逻辑 —— **那是错的**：
#     · 它在给一个**临时**问题写**永久**代码，反而成了新的故障源
#       （首次尝试会在坏镜像上重试很久，拖到构建超时）
#     · 而且它自身引入了 bug，把本来正常的 amd64 构建也弄挂了
#   → 正确做法：**默认路径保持简单**（标准镜像源 + apt 自身重试），
#     把换源做成**可选 build-arg**，交给真正遇到网络问题的人自己决定。
#
#   本项目面向国内用户，`deb.debian.org` 有时确实很慢，此时可以：
#     docker build --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn ...
#
#   ⚠️⚠️ **换源必须分开处理两个归档**（这条踩了两次）：
#     `deb.debian.org` 同时服务 `debian` 与 `debian-security`，
#     但换到 `ftp.debian.org` 后 **`ftp.debian.org/debian-security` 是 404** ——
#     安全归档不在那儿，它在 `security.debian.org`。
#     所以必须把 security 单独映射，**顺序还不能颠倒**（先 security，再一般规则）。
#     踩坑记录：我第一版写对了，后来"简化"成一句 `s|deb.debian.org|$MIRROR|g`
#     把修复回退了 → `ftp.debian.org/debian-security` → `404 Not Found` → 构建挂掉。
#     **"简化"一个已经修对的东西，是有代价的。**
# ---------------------------------------------------------------------------
ARG APT_MIRROR=""
RUN set -eux; \
    if [ -n "$APT_MIRROR" ]; then \
      for f in /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list; do \
        [ -f "$f" ] || continue; \
        sed -i \
          -e "s|deb.debian.org/debian-security|security.debian.org/debian-security|g" \
          -e "s|deb.debian.org/debian|${APT_MIRROR}/debian|g" \
          "$f"; \
      done; \
    fi; \
    # APT_RETRY_V1 —— 有界外层重试（**不是换源**：只重试同一条命令，全失败仍报错）
    # 2026-09 实测：`--no-cache` 全量重建时，apt 自带的 `Acquire::Retries=3`
    # **没能扛住**一波 502（samtools/tabix/libncurses6/unzip 的 .deb 全部 502），
    # 构建以 exit 100 失败。对第三方来说，第一次构建就失败的代价很高，
    # 所以加这一层。**改这里必须同时改 tasks/T2/Dockerfile 的两处** ——
    # scripts/check_dockerfile_apt.py 会强制这个不变量，防止只修一处。
    ok=0; \
    for i in 1 2 3; do \
      apt-get update -o Acquire::Retries=3 && \
      apt-get install -y --no-install-recommends -o Acquire::Retries=3 \
        ca-certificates curl unzip python3 samtools bcftools tabix freebayes default-jre-headless \
      && { ok=1; break; } || { echo "[重试 $i/3] apt 失败，${i}0 秒后再试"; sleep $((i*10)); }; \
    done; \
    [ "$ok" = "1" ] || { echo "[失败] apt 三次都失败 —— 若为 502/超时，可换国内源重试："; \
      echo "         docker build --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn ."; exit 1; }; \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# RTG Tools（BSD 2-Clause —— 已亲手读 LICENSE.txt 原文）
# 只用 vcfeval 评分；刻意不用 hap.py，避免引入 boost 构建链
#
# ⚠️ 上游有**两个**架构陷阱，都实测过，都会毁掉"任何人可复现"：
#   1. `...-linux-x64.zip` 里**捆了一个 amd64 专用 JRE**（jre/lib/amd64/*.so），
#      而 rtg 启动脚本会**优先**用它 → 在 arm64 上是 "Exec format error"。
#      处置：删掉捆包 JRE + `/etc/rtg.cfg` 写 `RTG_JAVA=java`，改走系统 Java
#      （顺带把镜像从 469 MB 瘦到 356 MB）。
#   2. **更致命**：rtg 启动脚本开头**硬编码** `uname -m != x86_64 → exit 1`，
#      在任何非 x86_64 架构上 **0.1 秒内直接失败**（实测）。
#      处置见 scripts/patch_rtg_launcher.sh（含"为什么可以去掉"的论证与合规说明）。
# ---------------------------------------------------------------------------
COPY scripts/ /opt/veribench-scripts/

ARG RTG_VERSION=3.12.1
RUN set -eux; \
    curl -fsSL -o /tmp/rtg.zip \
      "https://github.com/RealTimeGenomics/rtg-tools/releases/download/${RTG_VERSION}/rtg-tools-${RTG_VERSION}-linux-x64.zip"; \
    unzip -q /tmp/rtg.zip -d /opt; \
    mv "/opt/rtg-tools-${RTG_VERSION}" /opt/rtg-tools; \
    rm -f /tmp/rtg.zip; \
    rm -rf /opt/rtg-tools/jre; \
    printf 'RTG_JAVA=java\n' > /etc/rtg.cfg; \
    ln -s /opt/rtg-tools/rtg /usr/local/bin/rtg; \
    printf 'RTG_VERSION=%s\n' "${RTG_VERSION}" > /opt/rtg-tools/BUILD_INFO; \
    bash /opt/veribench-scripts/patch_rtg_launcher.sh /opt/rtg-tools/rtg

# ---------------------------------------------------------------------------
# 🏗️ 架构中立性门禁（构建时执行，失败即中断构建）
#    把"这个镜像能不能在别的 CPU 架构上跑"变成**构建期可验证的事**，
#    而不是等别人在 Apple Silicon 上踩坑。
#    这道门禁已经抓到两个真问题（见上），所以它不是装饰。
# ---------------------------------------------------------------------------
RUN bash /opt/veribench-scripts/check_arch_neutral.sh

# ---------------------------------------------------------------------------
# 🔒 许可门禁（构建时执行，失败即中断构建）
#
# 2026-09 复核 Debian 的 bcftools 许可时发现，原来那段内联检查有**三个真实盲区**，
# 每一条都可能让"零 copyleft"变成假话：
#
#   1. **静态链接看不见。** 原来只用 `ldd | grep libgsl`，而 `ldd` 只列*动态*依赖。
#      若 GSL 被静态链进去，二进制里确实含 GSL 代码（→ GPL-governed），
#      但 `ldd` 输出**完全干净** —— 门禁会**假通过**。
#   2. **插件根本没扫。** bcftools 的插件（/usr/lib/*/bcftools/*.so）是运行时
#      动态加载的，不在主程序的 `ldd` 里。实测本镜像里有 **39 个**插件。
#   3. **没验行为。** 上游 `bcftools/Makefile` 说得很明白：
#          # The polysomy command is not compiled by default because it brings
#          # dependency on libgsl. ... can be compiled with `make USE_GPL=1`
#          ifdef USE_GPL
#              GSL_LIBS ?= -lgsl -lcblas
#          endif
#      **USE_GPL 就是"要不要 GSL"的开关，而它的行为表现是 `bcftools polysomy`
#      在不在。** 行为比文本可靠（SPEC §3.1）。
#
# 为什么值得这么较真：Debian 的 `bcftools/copyright` 里明写着
#   "When linked with the GPL-licensed GNU Scientific Library (as is done for
#    this Debian package), the resulting program must be distributed under the GPL."
# 本轮已用四种实证手段确认这句话**对本镜像不成立**（polysomy 未编入、无 gsl_* 符号、
# 无动态依赖、无 GSL 库文件），但那是**测出来的结论，不是抄来的结论** ——
# 所以它必须留在构建期被反复验证，而不是写进文档当承诺。
#
# 门禁脚本自带四道检查（动态 / 静态 / 行为 / 文件系统），并已做负向测试：
#   见 scripts/_negtest_no_gsl.sh —— 四种注入都能让它失败，复位后重新通过。
# ---------------------------------------------------------------------------
RUN bash /opt/veribench-scripts/check_no_gsl.sh

# 许可声明目录（随镜像分发）
COPY licenses/ /licenses/

WORKDIR /work
COPY grade.py run.sh /work/
COPY data/ /work/data/
RUN chmod +x /work/run.sh /work/data/prepare_data.sh

# 说明：数据不打包进镜像（几百 MB），由 run.sh 通过挂载的 /data 提供，
# 详见 README.md 的"输入"与"未闭合项"。
ENV DATA_DIR=/data
ENV OUT_DIR=/out

ENTRYPOINT ["/bin/bash"]
CMD ["/work/run.sh"]
