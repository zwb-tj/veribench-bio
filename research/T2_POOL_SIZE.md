# VeriBench-Bio T2《变异解读》题池规模测算 + gnomAD 数据许可核实

**报告日期**：2026-09-10
**数据快照**：
- ClinVar `tab_delimited/` 快照 = **2026-09-06 14:42 GMT**（`variant_summary.txt.gz` Last-Modified 实测）
- ClinVar E-utilities 查询执行时间 = 2026-09-10
- ClinGen CSpec Registry API / Gene-Disease Validity API 访问时间 = 2026-09-10
- ClinGen FTP `ClinGen_gene_curation_list_GRCh38.tsv` 目录时间戳 = 2026-09-12

---

## 0. 结论摘要（TL;DR）

| 项目 | 结论 |
|---|---|
| **T2 v1 可用题目数** | **3,545 题**（严苛口径，set-F1 判据可公开比对）；若只保留 P/LP 则 **1,931 题** |
| **立项判定** | ✅ **可行**（≥100 门槛的 35 倍） |
| **T2b 备选池（1★ 冲突，2024–2026）** | **70,238** 条；经 VCEP 基因范围过滤后约 **15,029** 条 |
| **gnomAD 许可** | ✅ **可进入白名单（CC0 1.0）**，但必须剥离 SpliceAI 注释列（CC BY-NC 4.0） |
| **⚠️ 上一轮数字需更正** | 「4,325」与「2,810」均为**逐年份相加导致的重复计数**；「1★ 冲突 2025–2026 ≈ 14,622」实为 **2026 单年** |

---

## 1. 对上一轮实测数字的三处更正（本报告最重要的方法学发现）

### 更正 1：`[Review Status]` 必须加引号，否则静默返回 0

``` 
esearch?db=clinvar&term=reviewed by expert panel[Review Status]
  → Count = 0      querytranslation = (reviewed by expert panel[Review Status])

esearch?db=clinvar&term="reviewed by expert panel"[Review Status]
  → Count = 22428  querytranslation = "reviewed by expert panel"[Review Status]
```
**原始返回**：无引号 = 0；加引号 = **22,428**（与上一轮 22,424 一致，差异为快照漂移）。
任何按 review status 做的筛选，若不加引号，会**静默得到 0 而不是报错**。

### 更正 2：`CLINSIG_LAST_CHANGED` 不支持 `2024:2026` 区间语法，会被静默降级

```
term = "reviewed by expert panel"[Review Status] AND 2024:2026[CLINSIG_LAST_CHANGED]
  → Count = 976
  → querytranslation = "reviewed by expert panel"[Review Status] AND 2026[CLINSIG_LAST_CHANGED]
```
NCBI 把 `2024:2026` **静默改写成 `2026`**，等于只查了 2026 一年。另外几种写法同样失败：

| 写法 | Count | querytranslation |
|---|---|---|
| `2024:2026[CLINSIG_LAST_CHANGED]` | 976 | `2026[CLINSIG_LAST_CHANGED]` |
| `2024/01/01:2026/09/30[CLINSIG_LAST_CHANGED]` | 0 | `((2024/01/[All Fields] AND 2026/09/30[CLINSIG_LAST_CHANGED]))` |
| `2024:2026[Last Changed]` | 0 | `(2024 2026[All Fields])` |
| `"2024"[CLINSIG_LAST_CHANGED]` | 67,418 | 正确，按年匹配 |

**可用写法**：`("2024"[CLINSIG_LAST_CHANGED] OR "2025"[CLINSIG_LAST_CHANGED] OR "2026"[CLINSIG_LAST_CHANGED])`。
注意：查询语法提示词里给的 `2024:2026[CLINSIG_LAST_CHANGED]` 示例**实际不可用**。

### 更正 3：逐年份计数**不可相加**——单条 VCV 可命中多个年份桶

`CLINSIG_LAST_CHANGED` 是**多值字段**（每个提交有各自的 last-changed 日期），因此一条 VCV 可同时落在 2024 与 2025 桶里。用 UID 列表实证：

```
3★ 逐年:  2024 = 1515 UID, 2025 = 1834 UID, 2026 = 976 UID
naive_sum        = 4325          <-- 上一轮的数字
overlap 24&25 = 231 ; 24&26 = 169 ; 25&26 = 119
UNION(2024-2026) = 3825          <-- 正确数字
OR 查询返回      = 3825          <-- 与 UNION 逐一比对：union 中 0 条遗漏于 OR 集合
```
实例（同时出现在 2024 与 2025 桶的 UID）：
```
uid=3380944  VCV003380944.4  gene=F8
uid=2925658  VCV002925658.5  gene=CDKL5
uid=2773776  VCV002773776.3  gene=APC
```
**结论**：`2024–2026` 正确的 3★ 数量是 **3,825**，不是 4,325（上一轮多算 500 条）。
同理 `2025–2026` 正确值是 `1834+976-119 = 2,691`，不是 2,810。
**并且**：上一轮「1★ 冲突池 2025–2026 约 14,622」实测为 `conflicting AND 2026[...]` = **14,622**，即那是 **2026 单年**的数字。

---

## 2. 任务 1：T2 v1 题池漏斗（实际数量）

### 2.1 漏斗表

| 步骤 | 筛选条件 | 条目数 | 涉及基因数 | 所用查询 / 文件 URL |
|---|---|---|---|---|
| **S0** | ClinVar 全部 3★ | 22,428 | — | `esearch?db=clinvar&term="reviewed by expert panel"[Review Status]` |
| **S1** | 3★ ∧ `CLINSIG_LAST_CHANGED` ∈ 2024–2026 | **3,825** | 207 | `...AND ("2024"[CLINSIG_LAST_CHANGED] OR "2025"[CLINSIG_LAST_CHANGED] OR "2026"[CLINSIG_LAST_CHANGED])` |
| **S2** | ∧ 基因 ∈ ClinGen VCEP 策展范围 | **3,659** (−4.3%) | 114 | `https://cspec.genome.network/cspec/api/svis`（208 条 CSpec / 65 个 affiliation / 192 个基因） |
| **S3** | ∧ 基因-疾病 validity = Definitive 或 Strong | **3,654** (−0.1%) | 113 | `https://search.clinicalgenome.org/api/validity`（3,672 行；Definitive 2,292 + Strong 84） |
| **S4** | ∧ VCEP 判据规范已公开（CSpec status = Released / Approved For Release） | **3,654** (−0.0%) | 113 | 同上 CSpec API 的 `status` 字段（Released 123 条 / 2 genes Approved） |
| **S5** | ∧ 该变异在 ClinGen EREPO 有公开的 ACMG 判据码（Met / Not Met）→ **set-F1 可用** | **3,545** (−3.0%) | 112 | `https://erepo.clinicalgenome.org/evrepo/api/summary/classifications/download?type=csv`（13,263 行 / 12,539 个 VariationID / 12,257 个带 Met 码） |

**S5 分类构成**：Likely pathogenic 1,044｜Pathogenic 882｜**P/LP 合计 1,931**｜Uncertain significance 790｜Likely benign 611｜Benign 375｜混合/其他 10。

**S1 逐年明细**：2024 = 1,515｜2025 = 1,834｜2026 = 976（并集 3,825）。

### 2.2 判定

> ### ✅ **最终可用题目数 = 3,545（保守口径 P/LP only = 1,931）。T2 v1 立项可行。**

- 相对 `≥100 → 可行` 的门槛，余量 **35 倍**；即使只取 P/LP，余量仍为 **19 倍**。
- **瓶颈完全在第 1 步**：第 2/3/4 步合计只剔除 4.7%（3,825 → 3,654）。
- 因此本结论**对 ClinGen VCEP 基因清单的完整性不敏感**——即使清单规模翻一倍，S1 = 3,825 仍是硬上界，结论不变。

### 2.3 为什么第 2–4 步几乎不筛东西（重要设计含义）

- ClinVar 的 3★ 状态**本身就是专家小组提交的产物**，所以绝大多数 3★ 记录天然落在某个 VCEP 的策展范围内（3,684/3,825 = 96.3%）。
- **VCEP 不产出 gene-disease validity，GCEP 才产出**。实测 ClinGen validity 文件中 `ep` 字段**没有任何一条包含 "Variant Curation Expert Panel"**（0 条）。因此第 3 步必须用 **GCEP** 的 curation 结果，不能用 VCEP。这一条应在方法学文档中写清楚，否则会被审稿人当作逻辑错误。
- 第 4 步在本漏斗中通过 **CSpec Registry 的基因成员关系 + status** 近似实现（只剔掉 5 条）。更严格的做法就是 S5：直接要求变异在 ClinGen EREPO 中有逐条公开的判据码——这是 set-F1 的**唯一可靠真值来源**（字段 `Applied Evidence Codes (Met)` / `(Not Met)`）。建议 v1 的 set-F1 评分以 **S5 = 3,545** 为分母。

---

## 3. 任务 1 附：T2b 备选池（1★ 冲突池）

同一套方法（`"criteria provided, conflicting classifications"[Review Status]`）：

| 口径 | 数量 | 说明 |
|---|---|---|
| 全部 1★ 冲突 | **165,613** | 无时间限制 |
| **2024–2026 并集** | **70,238** | ← T2b 总池 |
| 2025–2026 并集 | 45,582 | 直接 OR 查询返回 |
| 2024 单年 | 27,105 | |
| 2025 单年 | 31,416 | |
| 2026 单年 | 14,622 | ← **上一轮误标为「2025–2026」的数字** |
| ∧ 基因 ∈ VCEP CSpec 范围（per-gene 汇总，含约 0.7% 多基因重复计数） | **≈15,029** | 192 个 CSpec 基因逐个 esearch |
| ∧ CSpec Released + 基因-疾病 Def/Strong | **≈11,263** | 更严口径 |
| 参照：2★「multiple submitters, no conflicts」 | 669,914 | |
| 参照：1★「single submitter」 | 3,305,068 | |

**T2b 结论**：池子充裕（≈15,000 条 VCEP 基因内 1★ 冲突），但**冲突池没有专家小组判据，set-F1 判据比对这一条不成立**；T2b 只能做「分类一致性/冲突消解」题型。建议：**v1 优先做 T2（有 EREPO 判据真值），T2b 仅作扩容/难度分层备选**。
注：T2b 的基因范围过滤是 per-gene esearch 汇总值，未做逐条 esummary，存在约 0.7%（3★ 交叉验证：per-gene 3,684 vs 唯一记录 3,659，差 25）的多基因重复计数，实际唯一记录数应略低。

---

## 4. 任务 2：gnomAD 数据许可核实

### 结论：✅ **可进入「仅 CC0 / CC BY / 公有领域」白名单**（附一处必须处理的例外）

**最强一级证据（原文，逐字）**，来源为 gnomAD 官方仓库中**渲染 `/policies` 页面的那份 markdown 源文件**：

> "The primary data from the gnomAD exomes and genomes are available free of restrictions under the [Creative Commons Zero Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/). This means that you can use it for any purpose without legally having to give attribution."

- 固定提交（pinned SHA）：`https://raw.githubusercontent.com/broadinstitute/gnomad-browser/86cc268b6ef6638a631cf53aae591987c2ac9a2d/browser/about/policies/terms.md`（2026-05-20，与 `main` 字节一致；3,005 bytes）
- **独立的第二路验证（线上部署产物）**：`https://gnomad.broadinstitute.org/js/190-883ccd4d11eceb0362e0.js` —— 站点实际投递的 JS chunk 中含同一句 CC0 原文。
- **映射证明**：`Routes.tsx` 中 `<Redirect from="/terms" to="/policies" />`；`PoliciesPage.tsx` 中 `import termsContent from '../about/policies/terms.md'`。→ 规范 URL 是 **https://gnomad.broadinstitute.org/policies**（`/terms` 现为 302）。
- 同页另有原文："There are absolutely no restrictions or embargoes on the publication of results derived from gnomAD data."

**⚠️ 必须处理的例外（否则不能进白名单）**，同上页面原文：

> "Some annotations may have restrictions on usage. For instance, SpliceAI annotations have been computed by Illumina and are provided with permission under a **CC BY NC 4.0** license for academic and non-commercial use... It is the responsibility of users to abide by all relevant licensing requirements."

→ **任何包含 SpliceAI 注释列的 gnomAD 文件必须整体排除，或剥离该列**后再入库。CC BY-NC 不在白名单内。
（未核实项：具体哪些下载文件/列嵌入了 SpliceAI —— 需逐文件检查 INFO 头。）

**其他记录在案的条款（不阻断 CC0）**：
1. 「All users of gnomAD data agree to not attempt to reidentify participants」——伦理使用条件，非再分发限制。
2. 商标：「不得在工具名中使用 gnomAD / Genome Aggregation Database，不得使用 gnomAD logo」——仅限命名/品牌。
3. **不要引用 MIT**。`gnomad-browser` / `gnomad_methods` / `gnomad_qc` 的 LICENSE 是 MIT / BSD-3-Clause，**只覆盖软件代码**。AWS Registry of Open Data（`https://registry.opendata.aws/broad-gnomad/`）标注的 `License: MIT` 是**二手来源且把代码许可与数据许可混为一谈**，属误导，不可作为数据许可依据。

完整证据表（16 条，逐条带 URL / 原文 / 一手或二手标注）见 `research/raw/GNOMAD_LICENSE_FINDINGS.md`。

---

## 5. 未核实项清单 + 自行核实步骤

| # | 未核实项 | 为什么无法核实 | 自行核实步骤 |
|---|---|---|---|
| 1 | **ClinGen VCEP 策展基因清单的完整性** | CSpec Registry 只收录已注册 CSpec 的 VCEP：实测 208 条 CSpec / 65 个 affiliation / **192 个基因**。而 `https://clinicalgenome.org/affiliation/vcep/` 列出更多 VCEP（部分标 `In Process`），其基因范围未逐一抓取。 | 遍历 `https://clinicalgenome.org/affiliation/vcep/` 中每个 `affiliation/{id}` 页，抓取 gene 列表合并。**影响有界**：S1 = 3,825 是硬上界，清单扩大也改变不了「可行」结论。 |
| 2 | **每个 S4 记录对应的「基因-疾病对」是否真有公开 CSpec** | 我用的是「基因 ∈ 某个 Released CSpec」+「基因有 Def/Strong」，而非逐基因-疾病对映射到具体 CSpec 文档。 | 从 `https://cspec.genome.network/cspec/api/svis` 解析 `ruleSets[].genes[].diseases[].@id`（MONDO 术语）与 ClinGen validity 的 `mondo` 字段做精确配对。 |
| 3 | **gnomAD 哪些下载文件嵌入 SpliceAI（CC BY-NC）列** | 需逐文件解析 VCF INFO 头，未执行。 | 下载 v4 sites VCF/TSV 的 header 行，grep `spliceai`/`SpliceAI`；若存在则剥离该 INFO 列。见 `GNOMAD_LICENSE_FINDINGS.md` §4.2 步骤。 |
| 4 | **gnomAD Nature 论文的 data-availability 声明** | Europe PMC `fullTextXML` 404（`isOpenAccess=N`）、PMC reCAPTCHA、nature.com 付费墙，三条路均失败。无期刊级佐证。 | 有机构权限时读 `https://www.nature.com/articles/s41586-023-06045-0`（v4，PMID 38057664）的 Data availability 段。 |
| 5 | **2026 年时间窗的精确上界** | 查询按自然年分桶，`"2026"` 覆盖到快照日 2026-09-06，而非 2026-09-30。 | 若必须精确到 9/30，需用 `variant_summary.txt.gz`（442 MB，本次按纪律未下载）解析 `LastUpdated` 列做逐日过滤，或等 10 月快照。 |
| 6 | **S2 的基因范围过滤是否等价于「该 VCEP 确实策展了该基因-疾病对」** | 用基因成员关系近似，非逐疾病对。 | 同第 2 项。 |
| 7 | **`clinical_impact_classification` / `oncogenicity_classification` 子池** | 未单独分析（本报告只统计 germline classification）。 | esummary 已含这两个字段，可从 `research/raw/step1_records.json` 直接复算。 |

---

## 6. 复现用原始查询（可直接粘贴）

```powershell
# S0 3★ 总数
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&retmode=json&term=%22reviewed%20by%20expert%20panel%22%5BReview%20Status%5D
#   -> 22428

# S1 3★ ∧ 2024-2026（正确写法：逐年 OR；区间语法 2024:2026 会被降级为 2026）
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&retmode=json&term=
  "reviewed by expert panel"[Review Status] AND ("2024"[CLINSIG_LAST_CHANGED] OR "2025"[CLINSIG_LAST_CHANGED] OR "2026"[CLINSIG_LAST_CHANGED])
#   -> 3825

# T2b 1★ 冲突 ∧ 2024-2026
  "criteria provided, conflicting classifications"[Review Status] AND ("2024"[CLINSIG_LAST_CHANGED] OR "2025"[CLINSIG_LAST_CHANGED] OR "2026"[CLINSIG_LAST_CHANGED])
#   -> 70238

# 4★ 复核（验证上一轮「4★ 2024-2026 = 0」）
  "practice guideline"[Review Status] AND ("2024"[CLINSIG_LAST_CHANGED] OR "2025"[CLINSIG_LAST_CHANGED] OR "2026"[CLINSIG_LAST_CHANGED])
#   -> 0   （4★ 总数 663，全部早于 2024）✅ 上一轮该结论正确
```

**限速**：全程遵守 ≤3 请求/秒（每次请求间 `Start-Sleep -Milliseconds 380~400`），未出现 429/403，无死循环重试。

**ClinVar FTP 路径核实**：`https://ftp.ncbi.nlm.nih.gov/pub/clinvar/txt/` → **HTTP 404** 确认；
`https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/` → **HTTP 200**，为现行路径。目录内含 `variant_summary.txt.gz` (442,645,117 B)、`summary_of_conflicting_interpretations.txt` (1.81 GB) 等。**未下载任何大文件**（全部结论来自 E-utilities 计数 + ClinGen 小型策展文件 + 32 MB EREPO 导出）。

**ClinGen 许可**：`https://www.clinicalgenome.org/docs/terms-of-use/` 原文——
> "All curated content published by ClinGen is available free of restriction under the **CC0 1.0 Universal (CC0 1.0) Public Domain Dedication**."

ClinGen 数据（CSpec Registry、ERE PO、Gene-Disease Validity）✅ 在白名单内。

---

## 7. 产出文件

| 文件 | 内容 |
|---|---|
| `research/T2_POOL_SIZE.md` | 本报告 |
| `research/raw/GNOMAD_LICENSE_FINDINGS.md` | gnomAD 许可完整证据表（16 条，含原文与 URL） |
| `research/raw/gnomad_terms.md.pinned-86cc268.txt` | gnomAD terms 原文（pinned SHA 86cc268） |
| `research/raw/gnomad_terms.md.main.txt` | gnomAD terms 原文（main，字节一致） |
| `research/raw/gnomad_deployed_policies_chunk_excerpt.txt` | 线上 JS chunk 中 CC0 原文摘录 |
| `research/raw/step1_uids.txt` | S1 的 3,825 个 ClinVar VariationID |
| `research/raw/step1_records.json` | S1 全部 3,825 条 esummary 记录 |
| `research/raw/step1_gene_counts.csv` | S1 基因分布 |
| `research/raw/funnel_S5_setF1_ready.csv` | **S5 = 3,545 条可用题目清单** |
| `research/raw/cspec_svis.json` | ClinGen CSpec Registry 全量（208 条） |
| `research/raw/clingen_validity.json` | ClinGen Gene-Disease Validity 全量（3,672 行） |
| `research/raw/erepo_classifications.csv` | ClinGen EREPO 全量导出（13,263 行，含判据码） |
| `research/raw/pergene_counts.csv` | 192 个 CSpec 基因的 3★/1★ 逐年计数（per-gene 交叉验证） |
| `research/raw/verify.ps1`、`analyze2.ps1`、`pergene.ps1` | 复现脚本 |
