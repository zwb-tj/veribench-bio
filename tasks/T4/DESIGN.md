# T4 设计：本体与功能注释任务（GO 确定性图查询）

> **这份文档的每一条事实都经过实测**（2026-09，本机）。凡未验证的一律标注。
> 沿用 T3 的顺序：**许可先于内容**，且真值**必须由原文确定性重算**。

---

## 一、这道题问什么

**给定 GO 本体原文（`go-basic.obo`），确定性地回答一组关于术语与层级的问题。**

作答者提交一个 JSON，逐项回答指定 GO 术语的图结构性质。

**为什么这样出题**：GO 本体是**策展权威本体** ——
它本身就是真值，不需要我们"判断"任何生物学结论。
所有答案都能由 OBO 原文**机械重算**，任何人都能独立复算并推翻我们。
这正是本项目原则 ② 要求的形态。

---

## 二、已核实的事实（实测，非推测）

### 2.1 许可：**CC BY 4.0**（**必须署名** —— 与 T3 的 CC0 不同！）

**来源**：<https://geneontology.org/docs/go-citation-policy/>（HTTP 200，24,216 B）

**原文摘录**：

> 「According to the terms of GO's **CC BY 4.0** license, those using our data
> publicly or redistributing it must provide: "identification of the creator(s)
> of the Licensed Material …"」

**并且许可**写在数据文件内部**（这是最强的一手证据）：

```
$ curl -s http://current.geneontology.org/ontology/go-basic.obo | grep terms:license
property_value: terms:license http://creativecommons.org/licenses/by/4.0/
```

| 问题 | 结论 |
|---|---|
| 能否再分发？ | ✅ 可以 |
| 能否进 Docker 镜像 / git？ | ✅ 可以 |
| **是否必须署名？** | **⚠️ 必须**（CC BY 4.0 §3(a)） |
| 是否可商用？ | ✅ 可以 |

**→ 与 T3 的关键差异**：T3 是 CC0（无需署名），**T4 必须署名**。
本项目 `NOTICE` 有 `[A]` 块专门记录"已核验的第三方组件及许可" ——
T4 的 GO 必须进那个块，并带 release 日期与 URL。

### 2.2 数据入口：可用、无需凭据、**版本明确**

```
http://current.geneontology.org/ontology/go-basic.obo
```

实测：HTTP 200，**32,227,785 B**（32 MB），
`data-version: releases/2026-07-26`。

**⚠️ 版本可复现性**：`current.geneontology.org` 是**滚动别名** ——
它指向的发布版会变。所以必须：
- 记录**取回时的** `data-version` 与该文件的 `sha256`
- 题面里写明版本；`items.jsonl` 记录文件哈希
- 这样"我们用的是哪一版"是可验证的（与 T3 记录 mmCIF 的 sha256 同理）

### 2.3 本体结构（实测）

| 项 | 实测值 |
|---|---|
| 文件里的 `[Term]` 块数 | **48,340** |
| **非 obsolete 的 term** | **38,092** ← 这才是可用题池 |
| 文件体积 | **32 MB** |
| 必存字段 | `id` / `name` / `namespace` / `def` —— **3000/3000** |
| `is_a`（层级） | **2,505/3000**（不是所有 term 都有父节点） |
| `relationship` | 1,052/3000；类型有 `part_of` / `regulates` / `negatively_regulates` / `positively_regulates` |
| **`is_obsolete: true`** | **494/3000**（⚠️ 必须排除） |
| 根节点 | **3 个**：`GO:0003674` molecular_function、`GO:0005575` cellular_component、`GO:0008150` biological_process |

> ⚠️ **48,340 与 38,092 的差别就是 obsolete 项**（约 10,248 个）。
> 第一版设计我写了"48,340 个 term"，那是**块数**不是**可用数** ——
> 这个区别必须写清楚，否则题池规模会被高估 27%。
> 已用**两种独立实现**（分块 vs 锚点扫描）交叉验证：两者都得 **38,092**，且
> `name`/`namespace` 零差异。

**`[Term]` 块样例**（真实，未删改）：

```
id: GO:0000022
name: mitotic spindle elongation
namespace: biological_process
alt_id: GO:1905121
def: "The cell cycle process in which the distance is lengthened between poles
     of the mitotic spindle. …" [GOC:mtg_cell_cycle, GOC:vw, PMID:19686686]
synonym: "spindle elongation during mitosis" EXACT []
is_a: GO:0051231 ! spindle elongation
is_a: GO:1903047 ! mitotic cell cycle process
relationship: part_of GO:0000070 ! mitotic sister chromatid segregation
```

**obsolete 样例**（题目必须排除）：

```
id: GO:0000002
name: obsolete mitochondrial genome maintenance
is_obsolete: true
```

---

## 三、判分器计算什么（四个量，全部确定）

作答格式：**一个 JSON**，按题面给出的 GO ID 回答：

```json
{"GO:0000022": {"name": "mitotic spindle elongation",
                "namespace": "biological_process",
                "direct_parent_count": 2,
                "depth_to_root": 6}}
```

| # | 量 | 定义 | 为什么确定 |
|---|---|---|---|
| 1 | `name` | 该 term 的 `name` 字段 | 原文直读 |
| 2 | `namespace` | 该 term 的 `namespace` | 原文直读 |
| 3 | `direct_parent_count` | `is_a:` 行的条数（**只数 is_a，不数 relationship**） | 纯计数 |
| 4 | `depth_to_root` | 沿 `is_a` 向上到**任一**根的最短距离（根 = 无 `is_a` 的 3 个节点） | 确定性 BFS |

**为什么选这些量**：
- 1–2 是原文直读，无歧义
- 3 是纯计数
- 4 是**图上最短路径** —— 完全确定，且有唯一答案（多个根时取最小值）

**⚠️ 必须排除的量**（引入外部定义，不是"从原文重算"）：
- 「最具体共同祖先」的**语义**判断（需要生物学家裁决）
- 富集分析的 p 值（需要统计假设）
- 任何依赖注释文件（GAF）的量 —— 那是**别人的策展结论**，不是本体结构

---

## 四、确定性判据（与 T3 同样的要求）

**定义**：同一份 `go-basic.obo`，任意机器、任意次运行，四个量**逐位相同**。

**满足确定性的理由**：
- 1–3 是字符串直读与整数计数，与浮点无关
- 4 是 BFS（整数），**不涉及浮点** —— 比 T3 的距离计算更简单

**实现要求**：
1. **只解析 `[Term]` 块**，按 OBO 1.2 规范（`[Term]` 到下一个 `[` 或 EOF）
2. `is_obsolete: true` 的 term **必须排除**，且若题面问到它们要**报错而非静默跳过**
3. BFS 的父节点遍历顺序**必须排序**（`is_a` 的 GO ID 升序），
   否则"最短距离"虽唯一、但**中间过程**可能随字典序变化 —— 排序消除该不确定性
4. 不得用递归（48,340 个节点可能超栈深），用显式队列

---

## 五、接口契约（与 T1/T2/T3 一致，不得另创）

```
tasks/T4/
  Dockerfile          # 构建期执行门禁
  run.sh              # 入口，默认 /out
  grade.py            # 判分器，含 --self-test
  README.md           # 如实写明限制与**署名要求**
  data/
    obo_parse.py      # OBO 1.2 最小解析器（零第三方依赖）
    fetch_go.py       # 取数（记录 data-version 与 sha256）
    go-basic.obo      # 本体原文（32 MB，CC BY 4.0，**可发布**）
    items.jsonl       # 题面（生成物）
    truth.jsonl       # 真值（生成物，**不进镜像**）
  schema/
```

`run.sh` / `grade.py` 的参数与 T2/T3 逐名一致：
`--items` / `--truth` / `--answers` / `--out` / `--self-test`。

接入：
- `scripts/record_image_digest.py` 的 `TASKS` 增加 `T4`
- `scripts/not_published.json` 登记 `truth.jsonl` 等生成物
- `run_all_checks.py` 调用 T4 自检

---

## 六、非目标

- ❌ 不做富集分析（需统计假设）
- ❌ 不解析 GAF 注释文件（那是别人的策展结论）
- ❌ 不判断"两个 term 哪个更具体"（需要语义裁决）
- ❌ 不引入第三方依赖（不用 pronto/obonet/biopython）
- ❌ 不改 T1/T2/T3

---

## 七、预算与体积

| 项 | 值 | 依据 |
|---|---|---|
| 运行时间 | **秒级** | 解析 32 MB 文本 + BFS；实测取数约 10 秒 |
| 本体文件 | **32 MB** | 实测 |
| 题池 | 建议 **20–40 个 term** | 与 T3 同为小规模、可复核 |

**⚠️ 32 MB 进仓库要考虑**：仓库当前 69.4 MB。加 32 MB 会到 ~101 MB。
**可选方案**：
1. 直接进仓库（最简单，且 CC BY 4.0 允许）——**推荐**，因为"可复现"要求原文在手
2. 进镜像但不进 git（则别人要自己下载，而下载是滚动的 → 版本漂移）
→ **选 1**：文件本身带 `data-version`，加 sha256 记录即可锁版本。

---

## 八、验收（实现者逐条做到；验证者逐条独立验）

1. `tasks/T4/` 结构与 `run.sh`/`grade.py` 契约与 T1/T2/T3 一致
2. 容器内 CPU-only 端到端跑通；oracle 作答得 **1.0**
3. 真值**全部由 OBO 原文确定性重算**；**无手工填写的数值真值**
4. `grade.py --self-test` 存在，且**被破坏时会失败**
5. **`is_obsolete` 的 term 被显式排除**，且问到它们时**报错不静默**
6. Dockerfile 构建期门禁；镜像内**不含 `truth.jsonl`**
7. 取数脚本记录 `data-version` 与 `sha256`
8. 接入 `record_image_digest.py` / `not_published.json` / `run_all_checks.py`
9. **`NOTICE` 的 [A] 块补上 GO（CC BY 4.0，含 release 日期与 URL）** ——
   这是 T4 与 T3 的**最大差异**，不署名就是许可违规

---

## 九、仍不确定（照实说）

- ⚠️ **污染风险未定量**：GO ID 与名称是公开常识，很可能在训练集中。
  → 与 T3 同样处理：T4 **不得**用来声称"模型懂生物学"，
  只能主张**能否按规范确定性地做图查询**与**过程是否可复现**。
  必须写进 `DATACARD.md`。
- ⚠️ `current.geneontology.org` 是滚动别名 → 将来取到的版本会不同。
  已用 sha256 + data-version 缓解，但**必须写明**"我们用的是 2026-07-26 那一版"。
- ⚠️ 未验证 arm64；未在第三方机器上复现。
