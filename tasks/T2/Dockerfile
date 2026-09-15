# syntax=docker/dockerfile:1
#
# VeriBench-Bio · T2 变异解读容器
#
# 与 T1 的根本不同：T2 **不需要任何生信工具**。
# 被测系统拿到的是"去标识化证据包"（纯文本字段），要输出的是分类 + 它认为成立的 ACMG 判据。
# 所以这个镜像只做两件事：**装题目** 与 **判分**。
#
# ⚠️ 两条关键设计：
#   1. **镜像里只放题目，不放答案。** 用多阶段构建：第一阶段（有真值）跑泄露门禁，
#      最终阶段**只复制 items.jsonl**，`truth.jsonl` 永远不进镜像。
#   2. **题面泄漏会让构建失败。** 见下面的泄露门禁 —— 一旦泄漏，T2 就退化成记忆测试，
#      而且是**悄悄**退化。所以把它做成构建期硬门禁，而不是靠人记得检查。

# ---------------------------------------------------------------------------
# 阶段 1：泄露门禁（这一阶段**有**真值，可用于逐题交叉核对）
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS gate
ENV DEBIAN_FRONTEND=noninteractive
# 可选换源（国内访问 deb.debian.org 不稳时用）：
#   docker build --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn ...
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
    # 2026-09 实测：`--no-cache` 全量构建时 deb.debian.org 对多个 .deb 持续返回 502，
    # apt 自带的 Acquire::Retries=3 没扛住，构建以 exit 100 失败。
    ok=0; \
    for i in 1 2 3; do \
      apt-get update -o Acquire::Retries=3 \
      && apt-get install -y --no-install-recommends -o Acquire::Retries=3 python3 \
      && { ok=1; break; } || { echo "[重试 $i/3] apt 失败，${i}0 秒后再试"; sleep $((i*10)); }; \
    done; \
    [ "$ok" = "1" ] || { echo "[失败] apt 三次都失败 —— 若为 502/超时，换源重试："; \
      echo "         docker build --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn ."; exit 1; }; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /gate
COPY data/check_no_leakage.py data/items.jsonl data/truth.jsonl /gate/

# 🚨 硬门禁：题面中不得出现任何变异身份（HGVS/rsID/坐标/氨基酸码）、
#    数据库 accession（SCV/VCV/CA/NM_…）、或结论词（pathogenic/benign/…）。
#    并逐题核对：题面里有没有出现**本题真值里**的 HGVS 或 VariationID。
RUN python3 /gate/check_no_leakage.py --items /gate/items.jsonl --truth /gate/truth.jsonl

# ---------------------------------------------------------------------------
# 阶段 2：最终镜像（**不含真值**）
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim

LABEL org.opencontainers.image.title="veribench-bio-t2-variant-interpretation"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.description="VeriBench-Bio T2: de-identified ACMG variant interpretation task (questions only, no answers)"

ENV DEBIAN_FRONTEND=noninteractive
ENV LC_ALL=C.UTF-8

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
    # APT_RETRY_V1 —— 同上（两个阶段各需一次；改一处必须改全部，
    # 由 scripts/check_dockerfile_apt.py 强制）
    ok=0; \
    for i in 1 2 3; do \
      apt-get update -o Acquire::Retries=3 \
      && apt-get install -y --no-install-recommends -o Acquire::Retries=3 \
           ca-certificates python3 \
      && { ok=1; break; } || { echo "[重试 $i/3] apt 失败，${i}0 秒后再试"; sleep $((i*10)); }; \
    done; \
    [ "$ok" = "1" ] || { echo "[失败] apt 三次都失败 —— 若为 502/超时，换源重试："; \
      echo "         docker build --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn ."; exit 1; }; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY grade.py run.sh /work/
COPY data/check_no_leakage.py /work/
COPY --from=gate /gate/items.jsonl /work/items.jsonl

# 注意：**没有** COPY truth.jsonl —— 镜像里不留答案。
# 判分时把真值以只读方式挂载进来即可（见 run.sh 的 TRUTH 变量）。

# 运行期再查一次泄露：防止有人替换了挂载进来的 items.jsonl
RUN python3 /work/check_no_leakage.py --items /work/items.jsonl --quiet

RUN chmod +x /work/run.sh

ENV DATA_DIR=/data
ENV OUT_DIR=/out
ENTRYPOINT ["/bin/bash"]
CMD ["/work/run.sh"]
