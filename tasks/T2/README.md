# T2 · 变异解读（Variant Interpretation）

> 状态：**设计已定稿，题池已测算（3,545 条），实现未开始**
> 上游依据：`../../SPEC.md` §4.2；调研见 `../../research/T2_CLINVAR_DESIGN.md` 与 `../../research/T2_POOL_SIZE.md`

---

## 这道题在考什么（用湿实验的话）

**给你一份变异的证据材料，请你按 ACMG 规则判断它是致病还是良性。**

但关键在于**我们不会告诉你这是哪个变异**——只给证据，不给身份。

---

## 为什么这样做：污染是"结构上"解决的，不是打补丁

ClinVar 是公开数据库，大模型很可能**已经把大量「变异 → 标签」背下来了**。如果题面给出变异名/HGVS/rsID，测到的就是**记忆**而不是**推理**。

**方案 B（已采用）：变异身份脱敏**

题面**绝不出现**：HGVS、rsID、基因组坐标、ClinVar ID、变异名、蛋白改变描述。
**只给一个结构化证据包**，让模型按 ACMG 规则推理。

> **记忆的对象是「变异 → 标签」这一对。题面里根本没有变异，就没有可背的东西。**
> 这是**结构性**解决，而不是"打个补丁希望它没用"。

**第二道保险**：时间切分——只用 `CLINSIG_LAST_CHANGED` 落在近年的条目（训练语料里不可能有）。

**第三道：内嵌金丝雀（占 20–30%）**
同一张证据卡，**只改一个字段**（例如把功能实验结果从"无影响"改成"破坏功能"），就要求**分类方向必须翻转**。
若模型两次都答"致病"，说明它在顺着题面语境猜，不是推理。
→ **这是可自动判分的污染探测器**，也是整卷最巧的一个设计。

---

## 题池（已实测测算，非估算）

**数据快照：ClinVar `tab_delimited/` 2026-09-06 14:42 GMT**

| 步骤 | 条件 | 条目数 | 基因数 |
|---|---|---|---|
| S0 | ClinVar **3★** 总数 | 22,428 | — |
| S1 | ∧ `CLINSIG_LAST_CHANGED` ∈ 2024–2026 | **3,825** | 207 |
| S2 | ∧ 基因 ∈ ClinGen **VCEP** CSpec 范围 | 3,659 | 114 |
| S3 | ∧ 基因-疾病有效性 = **Definitive/Strong** | 3,654 | 113 |
| S4 | ∧ CSpec status = Released/Approved | 3,654 | 113 |
| S5 | ∧ 在 **ClinGen EREPO** 有公开 ACMG 判据码 → **set-F1 可用** | **3,545** | 112 |

**结论：v1 题池 3,545 条**（仅 P/LP 则 1,931），是立项门槛（≥100）的 **35 倍**。

**瓶颈全在 S1**；S2–S4 合计只剔除 4.7% → **结论对 VCEP 基因清单的完整性不敏感**（3,825 是硬上界）。

题目清单已导出：`research/raw/funnel_S5_setF1_ready.csv`（正好 3,545 行）。

---

## 真值与评分

| 项 | 来源 | 权威性 |
|---|---|---|
| 分类真值 | ClinVar **3★（reviewed by expert panel）**，可由 `SCVsForAggregateGermlineClassification` 逐题追溯到 SCV accession | authoritative |
| 判据真值（set-F1 用） | **ClinGen EREPO** 的 `Applied Evidence Codes (Met)/(Not Met)` | authoritative |

**我们只装配证据，绝不生成标签。**

评分量（四项，缺一不可）：

1. **5 类精确匹配准确率**：Pathogenic / Likely pathogenic / VUS / Likely benign / Benign
2. **秩距离部分分**：答 P 而真值 LP 应得部分分，答 P 而真值 B 应重罚
3. **判据 set-F1**：要求模型列出 PVS1/PM2/PS3…，与专家小组公开判据比对
   → **这是"真推理 vs 猜"的判别器**：蒙对标签的模型列不对判据
4. **方向性错误惩罚**：把致病判成良性（或反之）比把 VUS 判错更严重

---

## 许可（决定了证据包里能放什么）

| 来源 | 许可 | 能否用 |
|---|---|---|
| ClinVar | SPDX **`NCBI-PD`**（美国政府作品）但有第三方权利保留声明 | ✅ 台账记 `yes_with_caveat` |
| ClinGen（含 EREPO、CSpec、gene-disease validity） | **CC0 1.0** | ✅ 白名单内 |
| **gnomAD 主数据**（等位基因频率） | **CC0 1.0** ✅ 已核实原文 | ✅ 可用 |
| **gnomAD 中的 SpliceAI 注释** | **CC BY-NC 4.0** | ❌ **含该列的文件必须整体排除或剥离该列** |
| **dbNSFP**（REVEL / CADD / PolyPhen-2 / AlphaMissense…） | **CC BY-NC-ND 4.0 + 商用付费（$5k–10k/年）** | ❌ **同时踩 -NC- 和 -ND-，绝对排除** |
| GeneReviews / OMIM | 第三方版权 | ❌ 排除 |

**⚠️ 由此产生的硬约束**：
1. **所有主流 in-silico 预测分数在 v1 里一个都不能发**（它们都在 dbNSFP 里）——这是 v1 证据包的最大缺口
2. gnomAD 的**等位基因频率可用**（PM2/BA1/BS1 这几条最常用的 ACMG 判据有了依据）
3. **不要引用 MIT** 来描述 gnomAD：其 repo 的 MIT/BSD-3 只覆盖**软件**，AWS Registry 的 "License: MIT" 是二手且混淆代码与数据

---

## 工程教训（都必须写进方法学文档）

这几条是实测踩出来的，**每一条都会让结果悄悄错掉**：

| 教训 | 后果 |
|---|---|
| **`"reviewed by expert panel"[Review Status]` 必须加引号** | 不加引号**静默返回 0**（不报错）——会让你以为"没有 3★ 数据" |
| **`2024:2026[CLINSIG_LAST_CHANGED]` 区间语法不可用** | NCBI **静默降级**为 `2026[...]`，只返回 976（真值 3,825）——必须逐年 OR |
| **逐年计数不可相加** | `CLINSIG_LAST_CHANGED` 是多值字段，一条记录可命中多个年份 → naive 相加 4,325，**UID 并集只有 3,825**（重叠 231/169/119） |
| **禁用 `MDAT` 做时间切分** | NCBI 批量刷新注释导致 2026[MDAT] = 20,663（占 3★ 的 92%），**会把大量旧数据误判为新数据**，防污染形同虚设 |
| **VCEP 不产出 gene-disease validity，GCEP 才产出** | validity 文件里 "Variant Curation Expert Panel" 出现 **0 次**；S3 必须用 GCEP 结果 |
| **ClinVar 不提供结构化 ACMG 证据** | XSD 里定义了词汇，但真实记录中这些字段**出现次数 = 0** → 证据必须从外部公有领域来源自己装配 |
| **上游路径会死**：`pub/clinvar/txt/` 已于 2026-09 变 404，现行 `tab_delimited/` | 这是**第二次**上游路径死亡（前一次是 PMC 的 `oa_file_list.csv`）→ 要加"路径存活"CI 门禁 |

---

## v1 明确砍掉的范围

- ❌ **4★（practice guideline）**：2024–2026 区间内 **= 0 条**，整池放弃
- ❌ 所有 **in-silico 预测分数**（dbNSFP 许可）
- ❌ OMIM / GeneReviews（版权）
- ❌ 体细胞 / 致癌性（oncogenicity）子池
- ❌ CNV
- ❌ 从 `submission_summary.txt` 的 `Description` 做 NLP 抽取
  （⚠️ 该自由文本**常直接写出结论词**，用作题面必须做**结论词剥离**）
- ❌ 共分离 / 功能实验证据（v1 装配不了）

## 备选：T2b（1★ 冲突池）

1★ 冲突池：全部 165,613；**2024–2026 并集 = 70,238**；∧ VCEP 基因范围 ≈ **15,029**。
**但冲突池没有专家判据 → set-F1 不成立**，只能做"分类一致性"题型。
→ **v1 优先 T2**，T2b 仅作扩容备选。

---

## 未闭合项（不得假装已完成）

- [ ] VCEP 策展基因清单的完整性（CSpec 只含已注册者；对结论影响有界，见 S1 瓶颈）
- [ ] 逐「基因-疾病对」→ 具体 CSpec 文档的精确映射（需用 MONDO 术语配对）
- [ ] **gnomAD 哪些下载文件嵌入了 SpliceAI 列**（必须逐文件核实并剥离）
- [ ] gnomAD Nature 论文的 data-availability 声明（三条路均失败：Europe PMC 404 / PMC reCAPTCHA / nature.com 付费墙）
- [ ] 2026 年窗口的精确上界：查询按自然年分桶，`"2026"` 覆盖到 2026-09-06 而非 09-30
- [ ] oncogenicity 子池未单独统计（原始数据在 `research/raw/step1_records.json`，可复算）
## 实现状态（2026-09-12）

**✅ 数据管道已跑通**（`data/build_t2.py`，可重放）：

| 环节 | 实测 |
|---|---|
| 候选（ClinVar 3★ + 时间切分 + VCEP + Definitive/Strong + EREPO 有判据） | 3,545 |
| EREPO join（按 ClinVar Variation ID） | **3545 / 3545，零丢失** |
| ClinGen 基因-疾病有效性 | 3,024 个基因 |
| **频率**（gnomAD v4 API，CC0） | **有频率 2,320 / 查无 1,214 / 出错 7** |
| 频率缺口 | **unknown 仅 7 条（0.2%）**，此前用 ClinVar AF_* 时是 2,316 条（65%） |
| 最终题面 | **4,726 条**（3,545 真实 + 1,181 金丝雀 = 25%） |
| 真值分布 | LP 1187 / P 1023 / VUS 785 / LB 700 / B 441（五类齐全） |

**✅ 判分器已自检通过**（`grade.py --self-test`，11/11）：
四个独立分量——分类部分分（有序尺度 + 跨 VUS 反向惩罚）、判据 set-F1、
方向性错误率、金丝雀一致性。**金丝雀不计入主分**（合成题没有专家真值，给它打分 = 自己造真值）。

**✅ 泄露检查器已通过**（`data/check_no_leakage.py`）：
扫描 4,726 条 / 40,170 个字符串字段，**零泄漏**。

**✅ 镜像已构建**（`veribench-bio/t2:dev`，123 MB）：
**泄露门禁在构建期跑两次**（stage 1 带真值逐题交叉核对、stage 2 复核最终镜像）；
**且最终镜像内不含 `truth.jsonl`**——只有题目，没有答案。

**✅ 端到端已跑通**（容器内，oracle 作答 → 全项 1.0）：
见 `baseline/README.md`（含**天花板/地板标定**）

### 这一轮踩到并修掉的坑（都会静默出错）

| 坑 | 后果 | 怎么发现的 |
|---|---|---|
| `item_id` 直接用 ClinVar VariationID | **题号本身就是答案的反查入口** | 泄露检查器当场抓到 |
| 判据码未规范化（ClinGen 写 `PP1_Moderate`） | 真值里带修饰的码永远匹配不上 → oracle 的 F1 只有 0.67 | oracle 基线 |
| 频率金丝雀锚在真值已是 Benign 的题上 | 方向翻转预期不成立 → oracle 金丝雀一致只有 0.94 | oracle 基线 |
| ClinVar CSV 带 BOM | `DictReader` 键名含 BOM + 引号 → KeyError | 显式报错 |
| urllib 下载 184 MB 抛 MemoryError | 换 curl（可续传） | 显式报错 |
| ClinGen validity 解析出 **0 个基因** | 键找错了（实际在 `rows`，基因键是 `symbol`），**不报错** | 强制打印解析数量 |
| gnomAD `joint`/`populations` 没有 `af` 字段 | HTTP 400；**但响应体被我丢掉**，只剩 "Bad Request" | 保留响应体后一眼看到 |
| gnomAD "查无此变异"是 **GraphQL 错误**而非 `null` | 被当成查询失败 → 会让大量题失去 PM2 证据 | 读响应体 |
| gnomAD 0.35s 间隔触发 **429 限流** | 全部失败 | 读响应体 |
| 换源时把 `debian-security` 也映射到 `ftp.debian.org` | 该路径 404 → 构建挂死 | 完整日志（**我先修对过，后来"简化"把修复回退了**） |

## 未闭合项（不得假装已完成）

- [ ] **没有真实模型作答过 T2**（当前只有合成基线；oracle/all_vus/all_pathogenic）
- [ ] 数据集**尚未上传 HuggingFace**（T1 已上传并校验；T2 待上传）
      → 手册：`../../docs/HF_UPLOAD_T2.md`。
      **上传前必须先跑预检**（`scripts/verify_upload_preflight.py --dir tasks/T2/data/public`）——
      发布集有个致命的不对称：`tasks/T2/data/public/`（3,789 条，要传）
      vs `tasks/T2/data/`（4,726 条，
      **含轮换池 937 条答案**），两个路径只差一段。传错不可撤销
- [ ] 36 条真值的判据 token 无法规范化（构建日志已计数），这些 token 被丢弃
- [ ] `criteria_not_met` 目前只入库未参与评分（可用于惩罚"错误声称成立"）
- [ ] 未做外部复现（D9）
- [x] ~~实现尚未开始~~ → 已实现并端到端跑通
