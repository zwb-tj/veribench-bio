# T3 —— 蛋白结构任务（mmCIF 确定性重算）
#
# 设计依据：tasks/T3/DESIGN.md
# 许可与数据来源：research/T3_SOURCES.md（RCSB PDB，CC0-1.0）
#
# 三条硬约束：
#   ① **镜像里不含 truth.jsonl** —— 判分时只读挂载（与 T2 同做法）
#   ② **构建期执行门禁** —— 数据不自洽就让构建失败，而不是等运行完才发现
#   ③ 零第三方 Python 依赖（只用标准库）
FROM python:3.12-slim-bookworm

ENV PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

WORKDIR /work

# ==============================================================================
# 门禁阶段（gate）：只用来回答"这批数据自洽吗"。
# 这一阶段的产物随后被丢弃 —— 真正进镜像的只有 items.jsonl 与 mmcif/。
# ==============================================================================
FROM python:3.12-slim-bookworm AS gate

ENV PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1

WORKDIR /gate

# 一次性把校验需要的东西全放进来（顺序不重要，避免分阶段时的路径依赖）
COPY data/mmcif_parse.py data/fetch_mmcif.py data/items.jsonl data/truth.jsonl /gate/
COPY data/mmcif /gate/mmcif
COPY grade.py /gate/

# 门禁 A：解析器自检（**证明它在坏输入上会失败**，不是恒真）
RUN python3 /gate/mmcif_parse.py --self-test

# 门禁 B：判分器自检
RUN python3 /gate/grade.py --self-test

# 门禁 C：**数据自洽** —— 独立于判分逻辑的结构校验
RUN python3 - <<'PY'
import hashlib, json, pathlib, sys

g = pathlib.Path("/gate")
items = [json.loads(l) for l in (g / "items.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
truth = [json.loads(l) for l in (g / "truth.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
probs = []

if not items:
    probs.append("items.jsonl 是空的")
if {i["item_id"] for i in items} != {t["item_id"] for t in truth}:
    probs.append("题面与真值的 id 集合不一致")

for i in items:
    cand = g / "mmcif" / pathlib.Path(i["mmcif_file"]).name
    if not cand.is_file():
        probs.append(f"{i['item_id']}: 缺 mmCIF 文件")
        continue
    if hashlib.sha256(cand.read_bytes()).hexdigest() != i["mmcif_sha256"]:
        probs.append(f"{i['item_id']}: mmCIF 的 sha256 与题面记录不符")

for t in truth:
    if sum(t["element_histogram"].values()) != t["atom_count"]:
        probs.append(f"{t['item_id']}: 元素直方图之和 != atom_count")
    if not (1.0 <= t["ca_distance"] <= 5.0):
        probs.append(f"{t['item_id']}: CA 距离 {t['ca_distance']} 不在 1.0–5.0 Å")
    for k in ("atom_count", "hetatm_count", "chain_count"):
        if not isinstance(t[k], int) or isinstance(t[k], bool):
            probs.append(f"{t['item_id']}.{k} 不是整数")

if probs:
    print("❌ 门禁失败：")
    for p in probs[:20]:
        print("  ·", p)
    sys.exit(1)
print(f"✅ 门禁通过：{len(items)} 条题，题面 / 真值 / mmCIF 三方一致")
PY

# 门禁 D：**真值必须能由原文重算出来**（这是 T3 的核心声明）
#   做法：把 mmCIF 重新解析一遍，与 truth.jsonl 逐字段比对。
#   如果两者不同，说明真值不是从原文来的（或原文被换过）——构建必须失败。
RUN python3 - <<'PY'
import json, pathlib, sys
sys.path.insert(0, "/gate")
from mmcif_parse import metrics_from_cif

g = pathlib.Path("/gate")
truth = {json.loads(l)["item_id"]: json.loads(l)
         for l in (g / "truth.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
items = [json.loads(l) for l in (g / "items.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

probs = []
for it in items:
    iid = it["item_id"]
    text = (g / "mmcif" / f"{it['pdb_id']}.cif").read_text(encoding="utf-8", errors="replace")
    rec = metrics_from_cif(text)          # 内部含交叉核对
    t = truth[iid]
    for k in ("atom_count", "hetatm_count", "chain_count", "element_histogram", "ca_distance"):
        if rec[k] != t[k]:
            probs.append(f"{iid}.{k}: 重算 {rec[k]!r} != 记录 {t[k]!r}")
if probs:
    print("❌ 真值与 mmCIF 重算结果不符：")
    for p in probs[:20]:
        print("  ·", p)
    sys.exit(1)
print(f"✅ 门禁通过：{len(items)} 条真值全部可由 mmCIF 原文重算得到")

# ⚠️ **写一个标记文件**：最终阶段会 COPY 它，从而**强制 Docker 构建本阶段**。
#    实测（2026-09）：Docker **不构建未被引用的中间阶段** ——
#    没有这一行（也没有最终阶段的 COPY --from=gate）时，
#    整个 gate 阶段的 RUN **全都不会执行**，而构建照样成功。
#    证据：往 truth.jsonl 注入一个错误值后，构建仍然 exit 0。
#    也就是说：在加上这一行之前，本文件里那些"构建期门禁"从未真正跑过 ——
#    而 README / DATACARD / 验证报告都声称它们跑了。
pathlib.Path("/gate/.gate-passed").write_text(
    f"门禁通过：{len(items)} 条题\n", encoding="utf-8", newline="")
PY

# ==============================================================================
# 正式镜像：零第三方依赖
# ==============================================================================
FROM python:3.12-slim-bookworm

ENV PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

WORKDIR /work

COPY data/mmcif_parse.py data/fetch_mmcif.py /work/
COPY grade.py run.sh /work/
COPY data/items.jsonl /work/items.jsonl
COPY data/mmcif /work/data/mmcif

# ⚠️ **这一行是门禁真正生效的关键** —— 最终阶段必须**依赖** gate 阶段，
#    否则 Docker 会跳过整个 gate，里面的 RUN 一个都不执行（见 gate 里的说明）。
COPY --from=gate /gate/.gate-passed /work/.gate-passed

# ⚠️ **没有** COPY truth.jsonl —— 镜像里不留答案。
# 判分时把真值以只读方式挂载进来（见 run.sh 的 TRUTH 变量）。

RUN chmod +x /work/run.sh

# 构建期最后一道：确认镜像里确实没有真值（**用文件系统判断，不靠人记得**）
RUN set -eux; \
    if find / -name 'truth.jsonl' -not -path '/proc/*' | grep -q .; then \
        echo "❌ 镜像里出现了 truth.jsonl —— 答案泄漏"; exit 1; \
    fi; \
    echo "✅ 已确认镜像内不含 truth.jsonl"

CMD ["/work/run.sh"]
