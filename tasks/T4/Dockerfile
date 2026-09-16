# T4 —— 本体与功能注释任务（GO 确定性图查询）
#
# 设计依据：tasks/T4/DESIGN.md
# 许可：**CC BY 4.0（必须署名）** —— 见 research/T4_SOURCES.md
#       ⚠️ 与 T3（CC0，无需署名）不同！署名要求记录在 NOTICE 的 [A] 块。
#
# 三条硬约束（与 T3 相同）：
#   ① **镜像里不含 truth.jsonl** —— 判分时只读挂载
#   ② **构建期执行门禁** —— 数据不自洽就让构建失败
#   ③ 零第三方 Python 依赖（只用标准库）
FROM python:3.12-slim-bookworm

ENV PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

WORKDIR /work

# ==============================================================================
# 门禁阶段：只用来回答"这批数据自洽吗"。产物随后丢弃。
# ==============================================================================
FROM python:3.12-slim-bookworm AS gate

ENV PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1
WORKDIR /gate

COPY data/obo_parse.py data/fetch_go.py data/items.jsonl data/truth.jsonl /gate/
COPY data/go-basic.obo /gate/
COPY grade.py /gate/

# 门禁 A：解析器自检（**证明它在坏输入上会失败**）
RUN python3 /gate/obo_parse.py --self-test

# 门禁 B：判分器自检
RUN python3 /gate/grade.py --self-test

# 门禁 C：题面/真值/OBO 三方一致 + **真值可由原文重算**
RUN python3 - <<'PY'
import hashlib, json, pathlib, sys
sys.path.insert(0, "/gate")
from obo_parse import (cross_check_totals, find_roots, metrics_for,
                       parse_terms, usable_terms)

g = pathlib.Path("/gate")
raw = (g / "go-basic.obo").read_bytes()
text = raw.decode("utf-8", "replace")
items = [json.loads(l) for l in (g / "items.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
truth = [json.loads(l) for l in (g / "truth.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
probs = []

if not items:
    probs.append("items.jsonl 是空的")
if {i["item_id"] for i in items} != {t["item_id"] for t in truth}:
    probs.append("题面与真值的 id 集合不一致")

# ① OBO 文件的 sha256 必须与题面记录一致（防"文件被换过"）
h = hashlib.sha256(raw).hexdigest()
for i in items:
    if i["obo_sha256"] != h:
        probs.append(f"{i['item_id']}: obo_sha256 与文件不符")
        break

# ② 真值必须能由原文重算（T4 的核心声明）
terms = parse_terms(text)
cross_check_totals(text, terms)
usable = usable_terms(terms)
roots = set(find_roots(terms))
for t in truth:
    try:
        m = metrics_for(terms, t["go_id"], roots)
    except Exception as e:                       # noqa: BLE001
        probs.append(f"{t['item_id']}: 重算失败 {e}")
        continue
    for k in ("name", "namespace", "direct_parent_count", "depth_to_root"):
        if m[k] != t[k]:
            probs.append(f"{t['item_id']}.{k}: 重算 {m[k]!r} != 记录 {t[k]!r}")

# ③ **题池不得含 obsolete 项**（T4 正确性的关键）
obs = [t["item_id"] for t in truth
       if t["go_id"] in terms and terms[t["go_id"]]["is_obsolete"]]
if obs:
    probs.append(f"题池含 obsolete 项：{obs[:5]}")

if probs:
    print("❌ 门禁失败：")
    for p in probs[:20]:
        print("  ·", p)
    sys.exit(1)
print(f"✅ 门禁通过：{len(items)} 条题；真值全部可由 OBO 原文重算；无 obsolete 项")

# ⚠️ **写一个标记文件**：最终阶段会 COPY 它，从而**强制 Docker 构建本阶段**。
#    没有这个文件（或被引用），Docker 会跳过整个 gate 阶段，
#    所有 RUN 都静默不执行 —— 而构建仍然成功，门禁形同虚设。
pathlib.Path("/gate/.gate-passed").write_text(
    f"门禁通过：{len(items)} 条题，OBO {h[:12]}\n", encoding="utf-8", newline="")
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

COPY data/obo_parse.py data/fetch_go.py /work/
COPY grade.py run.sh /work/
COPY data/items.jsonl /work/items.jsonl
COPY data/go-basic.obo /work/go-basic.obo

# ⚠️ **这一行是门禁真正生效的关键。**
#    实测（2026-09）：Docker **不构建未被引用的中间阶段** ——
#    gate 里的 RUN 全都不会执行，而构建照样成功。
#    证据：往 truth.jsonl 注入一个错误值后，构建仍然 exit 0。
#    所以最终阶段必须**依赖** gate（哪怕只是 copy 一个标记文件），
#    否则"构建期门禁"只是装饰。
COPY --from=gate /gate/.gate-passed /work/.gate-passed

# ⚠️ **没有** COPY truth.jsonl —— 镜像里不留答案。
# 判分时把真值以只读方式挂载进来（见 run.sh 的 TRUTH 变量）。

RUN chmod +x /work/run.sh

# 构建期最后一道：确认镜像里没有真值（**用文件系统判断，不靠人记得**）
RUN set -eux; \
    if find / -name 'truth.jsonl' -not -path '/proc/*' | grep -q .; then \
        echo "❌ 镜像里出现了 truth.jsonl —— 答案泄漏"; exit 1; \
    fi; \
    echo "✅ 已确认镜像内不含 truth.jsonl"

CMD ["/work/run.sh"]
