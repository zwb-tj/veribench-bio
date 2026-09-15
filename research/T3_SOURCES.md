# T3 数据来源与许可核实

> **方法**：只采信一手来源（wwPDB / RCSB 官方页面、RCSB 下载端点、RCSB Data API）。
> 本仓库既有文档（`DATA_LICENSES.md` §8.1）的结论**不作为证据** ——
> 这次重新去官网取原文，目的是**独立复核**，而不是抄自己的笔记。
> 每条结论附 URL 与实际取回的内容。

核实时间：2026-09（本机）。凡取不到或无法确认的，一律标「无法核实」并给出人工步骤。

---

## 一、许可：**CC0 1.0**（已从一手来源确认）

**来源**：<https://www.wwpdb.org/about/usage-policies>
（HTTP 200，页面 14,815 字符，2026-09 实测可访问）

**原文摘录**（从页面正文提取，未改动）：

> 「Data files contained in the PDB archive are available under the
> **CC0 1.0 Universal (CC0 1.0) Public Domain Dedication**. Users of PDB data
> are encouraged to attribute the original authors of the PDB structure data
> where possible. wwPDB makes no warranties about the work, and disclaims
> liability for all uses of the work, to the fullest extent permitted by
> applicable law.」

**结论**：

| 问题 | 结论 | 依据 |
|---|---|---|
| 能否再分发？ | ✅ 可以 | CC0 是公有领域奉献，不保留权利 |
| 能否进 Docker 镜像？ | ✅ 可以 | 同上，再分发的一种形式 |
| 能否进 git 仓库？ | ✅ 可以 | 同上 |
| 是否必须署名？ | ❌ **不必须** | 原文是 "are encouraged to"（鼓励），不是 "must" |
| 是否可商用？ | ✅ 可以 | CC0 无使用领域限制 |

> ⚠️ **一处必须说清的边界**：上面确认的是 **PDB 归档里的数据文件**（data files）。
> 它**不自动覆盖**：
> - RCSB 网站上的**第三方注释/整合内容**（例如某些 UniProt/Pfam 交叉引用文本）
> - **结构图的图片**（RCSB 生成的渲染图，可能另有条款）
>
> → 因此 T3 **只使用 `files.rcsb.org` 下载的 mmCIF 原文**，不使用任何网页内容或图片。
> 这样许可链条是干净的单一来源。

---

## 二、可获取性：无需 API key（已实测）

**入口**：`https://files.rcsb.org/download/{PDB_ID}.cif`

实测（本机，2026-09）：

| 条目 | HTTP | 字节数 | sha256 前 12 位 | 首行 |
|---|---|---|---|---|
| 1CRN | 200 | 69,506 | `23787562c427` | `data_1CRN` |
| 4HHB | 200 | 772,198 | `2d3ca1bf21dd` | `data_4HHB` |
| 6LU7 | 200 | 326,399 | `1496edb125c5` | `data_6LU7` |

- **无需凭据**：直接 GET，不带任何 token
- **无需注册**：无 API key、无 OAuth
- **格式确定**：正文以 `data_<ID>` 开头，是标准 mmCIF

**批量入口**（未在本轮实测，仅记录）：

- RCSB Data API：`https://data.rcsb.org/rest/v1/core/entry/{ID}` ——
  **已实测可达**（用 4HHB 验证过，返回 JSON，含 entry id 与 structure title）
- 但 T3 **不依赖**该 API：运行时不用网络，取数只在准备阶段

---

## 三、条目体积分布（实测）

从上述实测与扩展抽样（8 条）得到：

| 统计量 | 值 |
|---|---|
| 最小 | 69,506 B（1CRN） |
| 最大 | 772,198 B（4HHB） |
| 中位 | ≈326,399 B |

**原子数分布**（同一抽样，用 `loop_` 语义解析）：

| 条目 | ATOM 行 | HETATM 行 |
|---|---|---|
| 1CRN | 327 | 0 |
| 4HHB | 4,384 | 395 |
| 6LU7 | 2,387 | 113 |
| 1UBQ | 602 | 58 |
| 2LZM | 1,309 | 118 |
| 3AID | 1,912 | — |
| 1ATP | 3,070 | — |
| 5XNL | 98,986 | — |

**对 T3 的含义**：
- 题池若取 20–40 条，预期 **5–15 MB** —— 可整包进仓库（与 `DATA_LICENSES.md` 判断一致）
- 选条目时应**优先小体积**（< 400 KB），把 5XNL 那类 10 万原子的留给"大结构"压力测试

---

## 四、字段存在率（这是一个**设计级**发现）

实测 8 个条目，关键标量字段的存在率：

| 字段 | 存在率 | 含义 |
|---|---|---|
| `_exptl.method` | 8/8 | 一定有，但是自由文本 |
| `_cell.length_a` | 8/8 | 一定有 |
| `_struct.title` | 8/8 | 一定有 |
| `_refine.ls_d_res_high` | 7/8 | **会缺** |
| `_refine.ls_R_factor_R_work` | 4/8 | **经常缺** |
| `_refine.ls_R_factor_R_free` | **1/8** | **几乎总是缺** |

**结论（已写进 `tasks/T3/DESIGN.md` §2.3）**：
> 任何"读某个标量当答案"的题目都会大量出无解。
> T3 的判分量**必须**建立在 `_atom_site` 上 —— 没有坐标就不构成结构，所以它一定在。

⚠️ **样本量限制**：以上是 **8 个条目**的抽样，不是全 PDB 统计。
实现时应扩大到 ≥30 条再确认一次（已在 DESIGN §9 标注为未定量）。

---

## 五、污染风险评估

| 维度 | 评估 | 依据 |
|---|---|---|
| 条目 ID 是否可能被记住？ | **可能** | 1CRN（Crambin）是教科书级条目；4HHB（血红蛋白）极常见 |
| 具体数值是否可能被记住？ | **不确定** | 无法核实 LLM 训练集内容；不猜测 |
| 能否防污染？ | ✅ 部分可以 | 按**程序化规则**抽样（不挑"好看的"）+ 从原文重算，避免依赖记忆 |

**必须写进 `DATACARD.md` 的限制**：
> T3 的题目**不能**用来声称"模型理解蛋白结构"。
> 它测的是**能否按规范确定性地重算**，以及**过程是否可复现**。
> 常见条目的数值可能已在训练集中 —— 这削弱其"能力评测"价值，
> 但**不影响**其"确定性/可复现性"价值。

---

## 六、无法核实 / 需人工确认的项（照实说）

1. ⚠️ **RCSB 网页政策页 404**
   `https://www.rcsb.org/pages/about-us/policies` 返回 **HTTP 404**（2026-09 实测）。
   → 无法从该 URL 确认 RCSB 侧政策。但 **wwPDB 的 CC0 声明已足够**（wwPDB 是
   PDB 归档的联合管理机构，其 usage policy 是权威来源）。
   若需双源确认，人工步骤：访问 <https://www.rcsb.org/> 查找 "Usage Policies" 链接。

2. ⚠️ **RCSB Data API 的许可未单独核实**
   本轮确认了 wwPDB 对 **data files** 的 CC0。Data API 返回的是**同一批数据的
   另一种呈现**，但 API 本身的使用条款未逐字核实。
   → **规避措施**：T3 运行时不用 API；取数只用 `files.rcsb.org`。
   若将来要用 API 批量取数，需先补核实。

3. ⚠️ **`_pdbx_validate_*` 字段的性质**
   这些是 wwPDB 自带的**校验结论**（如 `_pdbx_validate_rmsd_angle`）。
   引用它们 = **引用他人判断**，不是"从坐标重算"。
   → 已在 DESIGN §6 明确排除出 T3 的判分量。

---

## 七、结论（供实现者直接引用）

| 问题 | 答案 |
|---|---|
| 许可 | **CC0 1.0**，可再分发、可进镜像、无需署名 |
| 一口来源 | <https://www.wwpdb.org/about/usage-policies>（原文已摘录于 §1） |
| 下载入口 | `https://files.rcsb.org/download/{ID}.cif`，**无需凭据** |
| 建议题池体积 | 20–40 条 ≈ 5–15 MB，优先 < 400 KB/条 |
| 真值来源 | 仅 `_atom_site`（标量字段会缺，见 §4） |
| 必须写入 DATACARD 的限制 | 污染风险 → 不得声称测"能力"（见 §5） |
