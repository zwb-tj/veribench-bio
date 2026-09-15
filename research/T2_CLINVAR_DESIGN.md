# T2「变异解读」数据调研与设计方案

**项目**：VeriBench-Bio
**作者**：数据调研（T2 预研）
**调研日期**：2026-09-12
**方法纪律**：所有列名、取值、计数、许可原文均来自一手来源（NCBI FTP 文件头、官方 README / 文档页、XSD、E-utilities）。取数方式为 HTTP Range 部分下载 + 流式 gzip 解压，**未下载任何完整大文件**（最大单次拉取 800 KB）。
**结论一句话**：T2 可以成立，但**只有把"变异身份"从题面里删掉、只给结构化证据包**才能成立；"只给变异名让模型分类"测的是记忆，不可作为主任务。4 星（实践指南）池因**近期无更新**必须放弃，主任务锁定 **3 星专家小组**。

---

## 0. 关键路径变更警告（2026 年实测）

| 提示词中给出的路径 | 2026-09-12 实测 |
|---|---|
| `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/txt/` | **HTTP 404（已不存在）** |
| `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/` | **HTTP 200（现行路径）** |
| `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/` | HTTP 200（未变） |

> `txt/` 目录已改名为 `tab_delimited/`。任何写死 `txt/` 的脚本在 2026 年已经全线失效 —— 这本身就是一条应该进 CI 的"路径存活检查"。

---

## 1. ClinVar 数据文件与真实列名（实测）

### 1.1 `tab_delimited/` 目录清单（读自 `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/`，Last Modified 2026-09-06）

| 文件 | 字节数 | 说明 |
|---|---|---|
| `variant_summary.txt.gz` | 442,645,117 | 每变异每组装一行（GRCh37 + GRCh38 各一行） |
| `submission_summary.txt.gz` | 387,668,111 | 每条当前提交一行，**含自由文本理由** |
| `summary_of_conflicting_interpretations.txt` | 1,810,068,714 | 1.8 GB 未压缩，成对冲突 |
| `hgvs4variation.txt.gz` | 522,573,033 | HGVS 表达式 |
| `variation_allele.txt.gz` | 24,156,102 | VariationID ↔ AlleleID |
| `allele_gene.txt.gz` | 91,765,510 | 等位基因 ↔ 基因关系 |
| `gene_specific_summary.txt` | 3,495,858 | 每基因统计（小，可直接下载） |
| `cross_references.txt` | 111,555,392 | 外部库 ID |
| `var_citations.txt` | 229,879,548 | PMID 关联 |
| `organization_summary.txt` | 930,420 | 提交机构 |
| `archive/` | — | **月度快照，实测存在 42 个 `variant_summary_YYYY-MM.txt.gz`** |
| `README` | 47,147 | 列定义权威文档（Last updated January 13, 2026） |

### 1.2 `variant_summary.txt.gz` 真实表头

**取数方法**：`curl -r 0-400000` 取 gz 前 400 KB → Python `zlib.decompressobj(16+zlib.MAX_WBITS)` 部分解压 → 读第 1 行。

**实测 43 列**（注意：官方 README 只文档化到第 40 列，**最后 3 列是新增未文档化的**）：

```
#AlleleID  Type  Name  GeneID  GeneSymbol  HGNC_ID  ClinicalSignificance  ClinSigSimple
LastEvaluated  RS# (dbSNP)  nsv/esv (dbVar)  RCVaccession  PhenotypeIDS  PhenotypeList
Origin  OriginSimple  Assembly  ChromosomeAccession  Chromosome  Start  Stop
ReferenceAllele  AlternateAllele  Cytogenetic  ReviewStatus  NumberSubmitters  Guidelines
TestedInGTR  OtherIDs  SubmitterCategories  VariationID  PositionVCF  ReferenceAlleleVCF
AlternateAlleleVCF  SomaticClinicalImpact  SomaticClinicalImpactLastEvaluated
ReviewStatusClinicalImpact  Oncogenicity  OncogenicityLastEvaluated  ReviewStatusOncogenicity
SCVsForAggregateGermlineClassification  SCVsForAggregateSomaticClinicalImpact
SCVsForAggregateOncogenicityClassification
```

**实测第一条数据行（截取关键列，来自真实文件）：**

| 列 | 实测值 |
|---|---|
| `Assembly` / `Chromosome` | `GRCh37` / `7`，同一 AlleleID 紧接着一行 `GRCh38` |
| `ClinicalSignificance` | `Pathogenic/Likely pathogenic`（**用 `/` 连接，非分号**） |
| `ClinSigSimple` | `1` |
| `LastEvaluated` | `Dec 17, 2024`（格式 `MMM DD, YYYY`） |
| `ReviewStatus` | `criteria provided, multiple submitters, no conflicts` |
| `NumberSubmitters` | `4` |
| `Guidelines` | `-` |
| `SCVsForAggregateGermlineClassification` | `SCV001451119\|SCV005622007\|SCV005909190` |

**要点**：
- **没有整数"星级"列**。星级必须由 `ReviewStatus` 字符串映射得到（见 §2）。
- 空值统一为 `-` 或 `na`。
- `Guidelines` 列**只是基因层面的偶发变异报告标记**（`ACMG2013` / `ACMG2016`，README 明确写 "if ACMG, not specific to the AlleleID but to the Gene"），**不是变异级 ACMG 判据**。
- **`variant_summary.txt` 没有任何"首次提交/首次公开"日期**。只有 `LastEvaluated`（README："the latest 'date last evaluated' on submissions with a germline classification"）。
- ✅ 意外收获：`SCVsForAggregateGermlineClassification` 列可直接拿到**产生该聚合分类的 SCV accession 列表** —— 这让 provenance ledger 可以逐题登记"这条真值来自哪个 SCV"，审计链条完整。

### 1.3 `submission_summary.txt.gz` 真实表头

**取数方法**：`curl -r 0-800000` → 部分解压 → 扫描首个"以 `#` 开头且含 tab"的行。

该文件**前 18 行是 `##` 注释前言**，真正的表头在**第 19 行**：

```
#VariationID  ClinicalSignificance  DateLastEvaluated  Description  SubmittedPhenotypeInfo
ReportedPhenotypeInfo  ReviewStatus  CollectionMethod  OriginCounts  Submitter  SCV
SubmittedGeneSymbol  ExplanationOfInterpretation  SomaticClinicalImpact  Oncogenicity
ContributesToAggregateClassification
```

**实测 16 列**（README 只文档化 15 列，实际多了 `ContributesToAggregateClassification`）。

**回答提示词的重点问题：**

| 问题 | 实测答案 |
|---|---|
| 有没有自由文本的 Comment？ | ✅ **有**，列名是 `Description`。README 原文："an optional free text description comment describing the rationale for the classification" |
| 有没有 AssertionMethod 列？ | ❌ **没有**。`submission_summary.txt` 无此列。`AssertionMethod` 只存在于 **XML** 的 `<Attribute Type="AssertionMethod">` |
| 证据描述列？ | 只有 `Description` 一列自由文本；**无结构化证据列** |
| 有没有 ACMG 判据字段（PVS1/PM2 之类）？ | ❌ **完全没有**。全 ClinVar 无结构化 ACMG 判据码字段 |

**实测 `Description` 真实内容（证明它确实是理由文本）：**
```
This variant is expected to result in the loss of a functional protein. This variant has not been
reported in large, multi-ethnic general populations. (http://gnomad.broadinstitute.org) This variant
has been identified in at least one individual with clinical features associated with this gene.
This variant appears to segregate with disease associated with this gene in at ...
```
以及：`... This variant was classified as Likely pathogenic based on ACMG criteri[a] ...`

> ⚠️ **重要**：`Description` 里经常直接写出结论词（"classified as Likely pathogenic"）。**若用作题面证据，必须做结论词剥离**，否则等于把答案一起给出。这是一条必须进构建期门禁的规则。

`DateLastEvaluated` 实测格式：`Jun 25, 2024`，缺失为 `-`。

### 1.4 VCF 真实字段

**取数方法**：`curl -r 0-300000` 取 `vcf_GRCh38/clinvar.vcf.gz` 前 300 KB → 部分解压 → 读全部 `##` 元信息行。

`##fileDate=2026-09-05`，`##reference=GRCh38`，固定列 `#CHROM POS ID REF ALT QUAL FILTER INFO`。

**实测 INFO 标签（39 个）**：
```
AF_ESP AF_EXAC AF_TGP ALLELEID CLNDN CLNDNINCL CLNDISDB CLNDISDBINCL CLNHGVS CLNREVSTAT
CLNSIG CLNSIGCONF CLNSIGINCL CLNSIGSCV CLNVC CLNVCSO CLNVI DBVARID GENEINFO MC
ONCDN ONCDNINCL ONCDISDB ONCDISDBINCL ONC ONCINCL ONCREVSTAT ONCSCV ONCCONF ORIGIN
RS SCIDN SCIDNINCL SCIDISDB SCIDISDBINCL SCIREVSTAT SCI SCIINCL SCISCV
```

**关键结论**：
- ✅ `CLNREVSTAT` = 聚合**胚系**分类的 review status；`ONCREVSTAT`（致癌性）、`SCIREVSTAT`（体细胞临床影响）各管一类。
- ✅ `CLNSIG` = 聚合胚系分类；`CLNSIGCONF` = 冲突分类；`MC` = 分子后果（SO ID|名称）—— **`MC` 是唯一可直接用作题面证据且无污染的字段**。
- ❌ **VCF 完全没有日期字段**。`README_VCF.txt`（`https://ftp.ncbi.nlm.nih.gov/pub/clinvar/README_VCF.txt`，Last updated January 30, 2024）列出的 39 个标签中无一个日期。**时间切分不能靠 VCF 做。**

---

## 2. 星级（review status）的确切表示方式

**来源**：`https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/`（Last updated: 2024-04-18T13:38:49Z）

官方原文明确："Review status is reported only in text format in ClinVar's products available by FTP." —— **FTP 产品里只有文字，没有星号**；星号仅用于网页展示。

### 2.1 聚合记录（VCV / RCV）胚系分类与致癌性

| 星 | ReviewStatus 字符串 |
|---|---|
| 4 | `practice guideline` |
| 3 | `reviewed by expert panel` |
| 2 | `criteria provided, multiple submitters, no conflicts` |
| 1 | `criteria provided, conflicting classifications` |
| 1 | `criteria provided, single submitter` |
| 0 | `no assertion criteria provided` |
| 0 | `no classification provided` |
| 0 | `no classification for the individual variant` |

**识别方法（直接回答提示词问题）**：
- 专家小组评审 → `ReviewStatus == "reviewed by expert panel"`（3★）
- 实践指南 → `ReviewStatus == "practice guideline"`（4★）
- 注意 **1★ 和 0★ 都对应多个字符串**，所以"数星"必须做多对一映射，不能假设 1★ 唯一。

### 2.2 体细胞临床影响（细微差别，别抄错）

| 星 | ReviewStatus 字符串 |
|---|---|
| 2 | `criteria provided, multiple submitters` ← **没有 `, no conflicts` 后缀**，因为体细胞分类不计算共识 |
| 1 | `criteria provided, single submitter` |

### 2.3 取值字符串的实测校验（E-utilities）

**方法**：`esearch.fcgi?db=clinvar&rettype=count&term="<字符串>"[Review status]`

| 字符串 | 计数 | 是否在用 |
|---|---|---|
| `criteria provided, multiple submitters, no conflicts` | 669,914 | ✅ 在用 |
| `criteria provided, single submitter` | 3,305,068 | ✅ 在用 |
| `criteria provided, conflicting classifications` | 165,613 | ✅ 在用 |
| `no assertion criteria provided` | 147,477 | ✅ 在用 |
| `no classification provided` | 250,269 | ✅ 在用 |
| `conflicting interpretations of pathogenicity` | **0** | ❌ **旧字符串，已废弃** |

> ⚠️ 很多老教程/老代码还在写 `conflicting interpretations of pathogenicity`。2026 年它已经**查不到任何记录**。白名单式枚举必须从官方文档页同步，不能凭记忆。

---

## 3. 规模：各星级约多少条

**方法 A（官方统计页，权威）**：`https://www.ncbi.nlm.nih.gov/clinvar/docs/statistics/`
页面标题 "Current total (Sep 05, 2026)"，实测原文：

| 类别 | 数量 |
|---|---|
| Unique variation records with **practice guidelines (4 stars)** | **663** |
| Unique variation records from **expert panels (3 stars)** | **22,424** |
| Unique variation records with assertion criteria, **multiple submitters, and no conflicts (2 stars)** | **669,912** |
| Unique variation records with assertion criteria (1 star) | 3,301,656 |
| Unique variation records with assertion criteria **and a conflict** (1 star) | 165,611 |
| Unique variation records with conflicting classifications | 166,041 |
| Unique variation records（总数） | 4,559,528 |
| Unique variation records with germline classifications | 4,307,623 |

**方法 B（E-utilities 交叉验证，同日 2026-09-12）**：

| 查询 | 计数 | 与官方统计差异 |
|---|---|---|
| `"reviewed by expert panel"[Review status]` | 22,428 | +4（0.018%） |
| `"practice guideline"[Review status]` | 663 | 0 |

**方法 C（已下载文件的换算，仅备查）**：`variant_summary.txt.gz` 442,645,117 字节 ÷ 4.5 字节解压比 ≈ 2.0 GB 解压后；每变异 2 行（37+38 组装）× 约 4.56 M 变异 ≈ 9.1 M 行，平均约 215 字节/行。**不推荐用这个方法**，官方统计页已经给了准确答案。

**数量级结论**：
- **4★ 实践指南：仅 663 条**（0.015%）
- **3★ 专家小组：约 2.24 万条**（0.5%）
- **2★ 多提交者无冲突：约 67 万条**（15%）
- 3★+4★ 合计约 2.31 万条，占全部已分类变异的 **0.54%**

**复核命令（用户可自行验证，不需要下大文件）**：
```bash
curl -s 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&rettype=count&term=%22reviewed+by+expert+panel%22%5BReview+status%5D'
```

---

## 4. 日期字段与时间切分

### 4.1 各文件的日期字段实测

| 文件 | 日期字段 | 是否含"首次提交时间" |
|---|---|---|
| `variant_summary.txt` | `LastEvaluated`, `SomaticClinicalImpactLastEvaluated`, `OncogenicityLastEvaluated` | ❌ **无** |
| `submission_summary.txt` | `DateLastEvaluated` | ❌ **无** |
| VCF | **无任何日期字段** | ❌ 无 |
| VCV XML | `DateCreated`, `DateLastUpdated`, `MostRecentSubmission`, `DateLastEvaluated`, `SubmissionDate`, `DateChanged`, `DateDeleted`, `ReleaseDate` | ✅ **有 `DateCreated`** |

**XML 一手证据**：
**取数方法**：`curl` 下载 `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/xsd_public/ClinVar_VCV.xsd`（159,754 字节）后本地 grep。
- `DateCreated`：类型 `xs:date`；XSD 注释片段含 *"DateCreated is the date when the record first became public in ..."*
- `DateLastUpdated`：XSD 注释原文 —— *"The date the record was last updated in the public database. The update may be a change to one of the submitted records (SCVs) or annotation added to the aggregate record by NCBI staff. This date is independent of a version change; annotated added by NCBI may change without representing a change in the version."*
- `SubmissionDate`：XSD 注释原文 —— *"SubmissionDate is when ClinVar received the submission."*
- `MostRecentSubmission`：XSD 注释片段 —— *"This date is of the most recent submitted record (SCV) for the VCV; it may reflect a new submitted record or an update to a submitted record."*

**真实记录验证**（样本 `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/xml/sample_xml/VCV_XML_VCV000091629.xml`，193,155 字节）：
```xml
<VariationArchive VariationID="91629" VariationName="NM_007294.4(BRCA1):c.4357+2T>G"
  VariationType="single nucleotide variant" Accession="VCV000091629" Version="19"
  RecordType="classified" NumberOfSubmissions="6" NumberOfSubmitters="6"
  DateLastUpdated="2026-02-15" DateCreated="2014-04-01" MostRecentSubmission="2026-02-15">
```
✅ `DateCreated` 确实被填充。**注意格式是 ISO `YYYY-MM-DD`**，与 tab_delimited 的 `MMM DD, YYYY` 不同 —— 解析器要分别处理。

> ⚠️ 实测发现：E-utilities `efetch.fcgi?db=clinvar&id=<VariationID>&rettype=vcv&retmode=xml` 对测试的 ID **返回空结果**（`<ClinVarResult-Set><set/></ClinVarResult-Set>`，110 字节）。**XML 数据请走 FTP 月度大文件，不要指望 efetch。**（此项列为未核实项）

### 4.2 ⭐ 最重要的发现：Entrez 的可检索日期字段

**取数方法**：`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?db=clinvar`。实测字段清单中包含 4 个日期字段：

| 字段码 | FullName | 官方 Description（原文） |
|---|---|---|
| `CDAT` | Creation Date | "The date on which this record first appeared" |
| `MDAT` | Modification Date | "The last date on which the record was updated" |
| `IMOD` | Last interpreted | "The latest date for each interpretation of a variant" |
| **`CLINSIG_LAST_CHANGED`** | **Date of last change to clinical significance** | — |

**`CLINSIG_LAST_CHANGED` 是去污染的关键字段**：它追踪的是**分类本身的最后变更日期**，而不是记录创建/更新日期。一个 2026 年才被专家小组改判的变异，其分类不可能出现在 2024 年之前的训练语料里。

**实测计数（2026-09-12）**，查询模式 `"reviewed by expert panel"[Review status] AND <范围>[CLINSIG_LAST_CHANGED]`：

| 时间范围 | 3★ 计数 |
|---|---|
| 2026 | 976 |
| 2025 | 1,834 |
| 2024 | 1,515 |
| 2023 | 1,440 |
| 2020:2022 | 1,874 |
| 2010:2019 | 1,008 |
| **2025:2026 合计** | **2,810** |
| **2024:2026 合计** | **4,325** |

**该字段确实按年份正确分桶**（各年数量互不相同、量级合理），不是假索引。✅

**其他可用池**：

| 查询 | 计数 |
|---|---|
| `"criteria provided, multiple submitters, no conflicts"[Review status] AND 2025:2026[CLINSIG_LAST_CHANGED]` | 15,358 |
| `"criteria provided, conflicting classifications"[Review status] AND 2025:2026[CLINSIG_LAST_CHANGED]` | 14,622 |
| `"reviewed by expert panel"[Review status] AND 2025:2026[CDAT]`（按**记录创建**） | 686 |
| `"reviewed by expert panel"[Review status] AND 2026[CDAT]` | 185 |
| `"criteria provided, multiple submitters, no conflicts"[Review status] AND 2026[CDAT]` | 2,876 |

**⛔ 致命约束：4★ 实践指南不能用于时间切分。**
`"practice guideline"[Review status] AND 2024:2026[CLINSIG_LAST_CHANGED]` = **0**。全部 663 条 4★ 记录都是老的、无近期更新。**4★ 池整体曝光在训练语料中，必须放弃。主任务只能锁 3★。**

**⚠️ 不要用 `MDAT` 做去污染。**
`"reviewed by expert panel"[Review status] AND 2026[MDAT]` = **20,663**（占 3★ 总数的 92%）。原因是 NCBI 会做批量注释更新，`MDAT` 会被整体刷新。**用 `MDAT` 切分会把旧数据全部误判成"新数据"，是陷阱。** 必须用 `CLINSIG_LAST_CHANGED`。

### 4.3 不依赖 Entrez 的兜底方案：归档快照差分

`tab_delimited/archive/` 下实测存在 **42 个** `variant_summary_YYYY-MM.txt.gz` 月度快照（`submission_summary_2025-01` … `2025-12` 等也已确认存在）；`vcf_GRCh38/archive_2.0/` 下有 **2017–2026 共 10 个年度目录**。

**方法**：取当前快照 + 一个 cutoff 之前的基线快照，按 `VariationID`/`AlleleID` join，找出 `ClinicalSignificance` 发生变化（或被基线中不存在的新 `VariationID`）的记录。这给出一个**完全可复现、可写进 ledger、不依赖 Entrez 索引行为**的时间切分集合。

**代价**：单文件 442 MB（variant_summary）或 185 MB（VCF）。**构建期下载 2 个文件约 0.6–0.9 GB，可接受**（评测期不需要）。建议用 VCF 哈希 + 流式过滤只保留需要的列。

### 4.4 时间切分的诚实局限（必须写进报告，不能藏）

`CLINSIG_LAST_CHANGED ≥ cutoff` 保证的是 **label 新鲜**，**不保证 variant 身份新鲜**。一个 2016 年作为 VUS 进入 ClinVar、2026 年才被 VCEP 改判的变异，其 `基因 + HGVS` 已经在公开网上挂了十年，模型完全可能"记得"它是个 VUS。

**这正是下节设计 B 的核心动机**：既然身份无法可靠去污染，就**把身份从题面删掉**。

---

## 5. 许可

### 5.1 ClinVar / NCBI

**来源 1：NCBI 政策页** `https://www.ncbi.nlm.nih.gov/home/about/policies/`

> **Molecular Data Usage 原文**：
> "NCBI itself places no restrictions on the use or distribution of the data contained therein. Nor do we accept data when the submitter has requested restrictions on reuse or redistribution."
>
> "However, some submitters of the original data (or the country of origin of such data) may claim patent, copyright, or other intellectual property rights in all or a portion of the data (that has been submitted). NCBI is not in a position to assess the validity of such claims and since there is no transfer of rights from submitters to NCBI, NCBI has no rights to transfer to a third party. Therefore, NCBI cannot provide comment or unrestricted permission concerning the use, copying, or distribution of the information contained in the molecular databases."

> **Copyright Status of Webpages 原文**：
> "Information that is created by or for the US government on this site is within the public domain."

**来源 2：SPDX 官方许可条目** `https://spdx.org/licenses/NCBI-PD.html`
SPDX 标识符 **`NCBI-PD`**（"NCBI Public Domain Notice"），原文：

> "With the exception of certain third-party files summarized below, this software/database is a 'United States Government Work' under the terms of the United States Copyright Act. ... This software/database is freely available to the public for use. The NLM and the U.S. Government have not placed any restriction on its use or reproduction."
>
> "Please cite the author in any work or product based on this material."

**结论（许可台账应登记的内容）**：
- **SPDX 标签：`NCBI-PD`**（公有领域）。**落在白名单内**（无 -NC- / -ND- / -SA-，允许商用与再分发）。
- **必须同时登记的保留意见**：ClinVar 聚合了第三方提交，NCBI 明确声明"无法评估也无法转让第三方权利"。因此 ledger 的 `redistributable` 字段应写 `yes_with_caveat`，并附上 NCBI 原文链接，而不是无保留的 `yes`。
- **必做动作**：登记 `取数日期` + 官方 `.md5` 校验文件内容（目录下每个大文件都有 `.md5`，实测存在）。

### 5.2 白名单核验：T2 候选附加数据集（这是本报告最有价值的发现之一）

| 数据集 | 许可结论 | SPDX / 依据 | 是否进白名单 |
|---|---|---|---|
| **ClinVar** | 公有领域 | `NCBI-PD`（含第三方权利保留意见） | ✅ **是** |
| **ClinGen 策展内容**（gene-disease validity / dosage sensitivity / clinical actionability） | **CC0 1.0** | 官方原文（`https://www.clinicalgenome.org/docs/terms-of-use/`）："All curated content published by ClinGen is available free of restriction under the **CC0 1.0 Universal (CC0 1.0) Public Domain Dedication**." | ✅ **是（干净）** |
| **dbNSFP**（in-silico 预测合集） | **CC BY-NC-ND 4.0**（学术分支）+ 商用需付费授权（$5,000–$10,000/年） | `https://www.dbnsfp.org/license` 原文："The dbNSFP academic branch is distributed free of charge for academic and non-commercial use under **CC BY-NC-ND 4.0**"；"Obtaining the academic branch data from any source does not grant commercial use rights" | ❌ **否 —— 同时踩 -NC- 和 -ND- 两条红线，绝对排除** |
| **gnomAD**（频率 / 约束） | **未能核实** | `https://gnomad.broadinstitute.org/policies` 与 `/terms` 均为 JS 渲染，curl 原始 HTML 仅 142/… 字节，**无任何许可文本可读**。AWS Open Data registry 元数据（`awslabs/open-data-registry/datasets/broad-gnomad.yaml`）写作 License: "MIT (gnomad_methods) + terms of use"，描述含 "released for the benefit of the wider scientific community without restriction on use"，但**这是二手来源** | ⚠️ **待核实，核实前不得进入可交付数据** |
| **MedGen**（NCBI） | 公有领域 | `NCBI-PD` | ✅ 是 |
| **OMIM** | 未核实，且已知受限 | 本次未核验 | ⚠️ **默认排除**，改用 MedGen / ClinGen |
| **GeneReviews**（NCBI Bookshelf） | **不是公有领域** | NCBI 政策页明确把 Bookshelf 列为"incorporated material ... protected by U.S. and foreign copyright laws" | ❌ **排除正文引用** |
| **Sequence Ontology (SO)** | CC BY 4.0 | 未在本次核验（已知宽松） | ⚠️ 待核实，预期 ✅ |

### 5.3 许可结论对设计的影响（重要）

**所有主流 in-silico 致病性预测分数（dbNSFP 收录的 REVEL / CADD / PolyPhen-2 / SIFT / AlphaMissense ... ）在 dbNSFP 语境下是 -NC-ND，而单独分发也普遍是"仅限学术非商用"。**

→ **T2 v1 必须一个 in-silico 预测分数都不发。** 这不是妥协，而是把白名单纪律变成设计约束。证据包只用：ClinVar 自身的字段（公有领域）+ ClinGen 基因-疾病有效性（CC0）+ SO 分子后果（待核实）+ （核实后）gnomAD 频率。

---

## 6. 结构化 ACMG 证据：一个重要负面结论

**动机**：如果 ClinVar 本身携带结构化的 ACMG 证据字段（等位基因频率、共分离、功能实验…），方案 B 的证据包就能直接取用，无需外部数据。

**实测方法**：下载 `ClinVar_VCV.xsd` → 提取 `<xs:enumeration value="..."/>` 全部取值 → 再在真实完整记录 `VCV000091629`（193 KB）上统计实际出现的 `Attribute Type`。

**XSD 里确实存在一套"长得非常像 ACMG 判据"的证据词汇表**，实测包含：
```
AlleleFrequency   Population   reference population
CosegregatingFamilies   NumFamiliesWithVariant   SegregationObserved   InformativeMeioses
ModeOfInheritance   Penetrance   Severity   AgeOfOnset   FamilyHistory
Experimental   in vitro   in vivo   MethodResult   MethodAppropriate   ControlsAppropriate
IndependentObservations   SubjectsWithVariant   NumberMosaic
VariantAlleles   VariantChromosomes   GenotypeAndMOIConsistent
AssertionMethod   ExplanationOfClassification   Computational
```
历史取值枚举还包含 `reclassified` / `previous` / `current` / `no classifications from unflagged records`。

**但真实记录里这些字段几乎没有被填充。** 对 `VCV000091629`（BRCA1 `c.4357+2T>G`，6 条提交，193 KB 完整 XML）统计到的 `Attribute Type` **全部取值**只有：

| Attribute Type | 出现次数 |
|---|---|
| `HGVS` | 多条 |
| `AssertionMethod` | 3（`Ambry Variant Classification Scheme 2023` / `GeneDx Variant Classification (06012015)` / `Invitae Variant Classification Sherloc (09022015)` / `ACMG Guidelines, 2015`） |
| `keyword` | 2（`Neoplasm`, `Hereditary cancer syndrome`） |
| `GARD id` | 3 |
| `public definition` | 2 |
| `disease mechanism` | 2（`loss of function`） |

→ **`AlleleFrequency`、`CosegregatingFamilies`、`Experimental`、`ModeOfInheritance` 等 ACMG 型证据字段出现次数 = 0。**
→ 同时 `ClassificationHistory` / `DescriptionHistory` 元素在该记录中**出现次数 = 0**（regex `matches: 0`）。

**结论（必须让团队知道）**：
1. **不能假设 ClinVar 提供结构化 ACMG 判据。** 真实证据主要存在于 XML 的 `Comment` / tab_delimited 的 `Description` **自由文本**里，需要 NLP 抽取，且抽取本身引入我们自己的判断（违反"禁止自算真值"的精神）。
2. **`AssertionMethod` 的熵很低**：多数提交只写"ACMG Guidelines, 2015"或厂家内部方案名，对逐题判据无信息量。
3. **`ClassificationHistory` 的填充率未知**（在 1 条记录中为 0）—— 列为未核实项。

**由此得出方案 B 的正确形态**：证据包由我们在构建期从**公有领域来源"装配"**（而非从 ClinVar 抽取），而**标签**仍然取 ClinVar 3★。**我们计算证据，绝不计算标签** —— 这条边界必须写进构建脚本的注释和 CI 门禁。

---

## 7. 候选任务设计对比

### 方案 A：只给变异名 → 让模型分类

| 维度 | 评估 |
|---|---|
| **真值来源** | ✅ 权威（限定 `ReviewStatus == "reviewed by expert panel"` 时，是 VCEP 的正式判定，非自算） |
| **污染风险** | 🔴 **极高**。ClinVar 是全网被抓取最狠的生物医学资源之一；`基因 + HGVS` / `rsID` 是可被逐字记忆的键。ClinVar 网页本身对这类字符串排名极高。 |
| **时间切分能否解决** | ⚠️ **只能部分解决**。`CLINSIG_LAST_CHANGED` 2026 年有 976 条 3★，但**变异身份是旧的**（可能是挂了十年的 VUS），模型可能记得"旧答案"。若改用 `CDAT`（2025:2026 = 686 条）则身份也新，但池子薄，且这些是没人写过的新变异 —— 更糟的是，模型靠"无义突变 + 单倍剂量不足基因 ⇒ 致病"这类**基因级先验**也能答对，那是**推理**不是记忆，导致得分**无法解释**：我们分不清高分来自记忆还是推理。 |
| **额外数据需求** | 无（只要 ClinVar） |
| **30 min CPU-only** | ✅ 完全可行（零计算） |
| **可自动判分** | ✅ 5 类精确匹配准确率。但**基线不可解释**（类别不均衡 + 基因级先验基线很高） |
| **结论** | ❌ **不可作为主任务**。✅ **保留为"记忆探针 / 对照组"**：零成本，用来给 B 提供一个"纯记忆能做到多少"的下界参照，并作为污染告警信号（若 A 的分数显著高于 B，说明题目被记忆污染）。 |

### 方案 B（推荐）：结构化证据包 + 变异身份脱敏 → 按 ACMG 规则推理

| 维度 | 评估 |
|---|---|
| **真值来源** | ✅ **权威且可审计**。标签 = ClinVar 聚合胚系分类，且 `ReviewStatus == "reviewed by expert panel"`（3★）。`variant_summary.txt` 的 `SCVsForAggregateGermlineClassification` 列可直接记录**产生该判定的一条或多条 SCV accession**，逐题可追溯。完全不碰"自算真值"红线 —— 我们只装配证据，不生成标签。 |
| **污染风险** | 🟢 **低**。记忆的对象是 `(变异 → 标签)` 这一对；题面**从不出现** HGVS / rsID / 坐标 / ClinVar ID / 变异名 / 外显子位置。模型看到的是"某单倍剂量不足基因上的无义变异，gnomAD popmax AF = 0，LOEUF = 0.2，ClinGen 基因-疾病有效性 = Definitive…"。**残留风险**：证据模式本身可能唯一识别某些明星变异（如"BRCA1 + 无义 + 频率 0"）。缓解：① 优先选同基因内有 ≥5 道可测题的基因，使证据卡不唯一；② 做**消融实验**——把证据卡的字段设盲，看分数是否塌陷；③ 强制跑方案 D 的翻转金丝雀。 |
| **时间切分能否解决** | ✅ **能，且是双保险**。① 标签侧：`CLINSIG_LAST_CHANGED ≥ cutoff`（实测 2025:2026 = 2,810 条 / 2026 = 976 条 3★）；② 来源侧：VCEP 的判据文档与专家小组提交本身也晚于 cutoff。由于身份已脱敏，即便 `CLINSIG_LAST_CHANGED` 的"身份不新"局限存在，也不再是致命问题 —— 这正是 B 相对 A 的结构性优势。 |
| **额外数据需求** | ClinVar（✅ 公有领域）；**ClinGen 基因-疾病有效性**（✅ CC0）；SO 分子后果（⚠️ 待核实）；gnomAD 频率/约束（⚠️ **许可未核实 → v1 可先不带**）；MedGen 遗传方式（✅ `NCBI-PD`）。**明确剔除**：dbNSFP（-NC-ND）、OMIM（受限）、GeneReviews 正文（版权）。 |
| **30 min CPU-only** | ✅ **完全可行**。证据包在**构建期**预计算并作为小体积 JSON/TSV 随题分发；评测期是**纯读题 + 推理**，无需比对、无需注释、无需网。若 v1 砍掉 gnomAD，则构建期也不需要大文件，整条流水线都轻。 |
| **可自动判分（明确评分量）** | ① **主指标**：5 类 ACMG 精确匹配准确率（`Benign` / `Likely benign` / `Uncertain significance` / `Likely pathogenic` / `Pathogenic`）。② **序数部分分**：按 P(4)–B(0) 的**秩距离**给部分分（LP vs P 是真实的连续梯度，一刀切不合理）。③ **判据归因分**：要求模型显式列出所用 ACMG 判据码（PVS1 / PM2 / PS3 / PP3 / BS1 / BA1 …），与从 VCEP 公开判据文档中恢复出的判据集合算 **set-F1** —— **这是"真推理 vs 猜"的判别器**：猜对结论但判据乱写会被扣分。④ **方向性错误惩罚**：把 P 判成 B（反之亦然）的代价高于弃答，鼓励校准与弃答。全部为确定性精确匹配，可自动判分。 |
| **结论** | ✅ **推荐作为 T2 主任务。** |

### 方案 C：判断两条已有提交之间的分歧 / 预测专家小组会怎么改判

| 维度 | 评估 |
|---|---|
| **真值来源** | ✅ 权威（VCEP 3★ 最终判定）。 |
| **污染风险** | 🟡 **中**。被改判的变异恰恰是论文和"reclassification list"里反复出现的对象。但**"两条提交的对照"本身不是一个被记忆的单元**，且 1★ 冲突池大（实测 2025:2026 `CLINSIG_LAST_CHANGED` = **14,622** 条）。 |
| **时间切分能否解决** | ✅ 能（`CLINSIG_LAST_CHANGED`）。但需注意：改判常由知名联盟（ENIGMA、InSiGHT、ClinGen VCEP）发起，相关论文的**摘要**可能已进入语料 —— 应把"论文发表时间"也纳入 cutoff 判断。 |
| **额外数据需求** | 最少，仅 ClinVar（`submission_summary.txt` 的 `Description` 自由文本 + `summary_of_conflicting_interpretations.txt`）。**但必须做结论词剥离**（`Description` 常直接写 "classified as Likely pathogenic"）。 |
| **30 min CPU-only** | ✅ 完全可行。 |
| **可自动判分** | ✅ 精确匹配（预测 VCEP 最终类）+ 二选一/全否（模型更认同哪条提交）准确率。 |
| **结论** | ✅ **强候选，建议作为 T2b 在 B 之后发布。** |

### 方案 D：配对反事实"翻转金丝雀"（建议嵌入 B 作为强制子集）

**做法**：同一张证据卡呈现两次，其中**恰好一个字段被定向改动**（例：`popmax AF` 由 `0.0001` 改为 `0.03`，或 `ClinGen 基因-疾病有效性` 由 `Definitive` 改为 `No evidence`），要求模型重新分类。

| 维度 | 评估 |
|---|---|
| **真值来源** | ✅ 两个方向都有权威真值来源可用（原卡用真实 3★ 标签；翻转卡不声明"真值"而是断言"**方向必须改变**"，这是逻辑一致性命题，不依赖新真值）。**注意：翻转后的分类不得伪造成 ClinVar 里的另一条记录** —— 只考"方向是否一致翻转"，不考一个不存在的标签。 |
| **污染风险** | 🟢 **极低，且它是一个污染探测器**。记忆型/基因级模式匹配型的模型会**忽略字段变化**给出同一答案；真推理的模型会翻转。 |
| **时间切分** | 不需要（逻辑命题，与训练语料无关）。 |
| **额外数据需求** | 无（复用 B 的证据包）。 |
| **30 min CPU-only** | ✅ 极小开销。 |
| **可自动判分** | ✅ **配对翻转一致率**（paired-flip accuracy）—— 一个干净的 0–1 指标。 |
| **结论** | ✅ **作为 B 的强制内嵌守卫子集**（建议占 B 的 20–30%），不单独成任务。这是把"污染检查"从人工评审变成**题目自带、可自动判分**的机制。 |

### 对比总表

| 方案 | 真值权威性 | 污染风险 | 额外数据需求 | 30min 可行 | 评分量 |
|---|---|---|---|---|---|
| **A** 只给变异名 | ✅ 3★ 权威（但 4★ 不可用） | 🔴 极高；时间切分只部分有效；基线不可解释 | 无 | ✅（零计算） | 5 类准确率（基线不可解释） |
| **B** 证据包 + 身份脱敏 | ✅ 3★，SCV accession 可逐题追溯 | 🟢 低；时间切分双保险 | ClinVar ✅ + ClinGen ✅ + SO ⚠️ + gnomAD ⚠️（v1 可砍） | ✅ 纯推理，构建期预计算 | 5 类准确率 + 秩距离部分分 + **判据 set-F1** + 方向性惩罚 |
| **C** 分歧/改判预测 | ✅ 3★ | 🟡 中；时间切分有效 | 仅 ClinVar（需结论词剥离） | ✅ | 精确匹配 + 二选一准确率 |
| **D** 配对翻转金丝雀 | ✅ 逻辑命题（不依赖新真值） | 🟢 极低（且是探测器） | 复用 B | ✅ | 配对翻转一致率 |

---

## 8. 推荐方案与最小可行 v1 范围

### 推荐：**方案 B，内嵌方案 D 作为强制守卫子集；方案 A 作为已发布的对照组；方案 C 作为 T2b 后续任务。**

**理由（按重要性排序）**：
1. **它是唯一在结构上解决污染问题的方案** —— 因为记忆的对象是"变异 → 标签"这一对，而 B 的题面里根本没有"变异"。时间切分对 A 只是打补丁（因为身份旧），对 B 是锦上添花。
2. **它满足"绝对禁止自算真值"** —— 标签 100% 来自 ClinVar 3★ 专家小组，且 `variant_summary.txt` 提供 `SCVsForAggregateGermlineClassification`，可以逐题登记产生标签的 SCV accession。我们装配的是**证据**，不是**答案**。
3. **它的许可最干净** —— 主数据 `NCBI-PD` + ClinGen `CC0`，不引入任何一个 -NC-/-ND- 数据集。相比之下，任何依赖 dbNSFP 的方案直接出局。
4. **它不需要大文件、不需要比对、不需要网** —— 评测期纯推理，30 分钟 CPU-only 绰绰有余；这是 T1 已经验证过的模式（预置输入 + 单一明确动作）。
5. **它可自动判分且有多层信号** —— 精确匹配 + 秩距离 + 判据 set-F1，后者专门区分"推理"与"猜"。

### 最小可行 v1 范围

**先做（v1 shippable）**：
- ✅ 仅 **3★ `reviewed by expert panel`**（4★ 因 `CLINSIG_LAST_CHANGED` 近期为 0，**整池放弃**）
- ✅ 仅**胚系**分类（`ClinicalSignificance`，不碰体细胞 `SCI` / 致癌性 `ONC`）
- ✅ 仅 **SNV + 短 indel**（不碰 CNV；`summary_of_conflicting_interpretations.txt` 有 1.8 GB 且结构复杂，暂不引入）
- ✅ 仅**同时具备 ClinGen VCEP 且基因-疾病有效性为 Definitive/Strong** 的基因（ClinGen CC0，许可干净）
- ✅ 仅**遗传方式明确**（AD / AR / XL，来自 MedGen，`NCBI-PD`）
- ✅ 证据卡字段只保留：基因符号（保留，因为机制知识是合法领域知识）、遗传方式、分子后果（SO）、变异类型（无义/移码/剪接/错义）、ClinGen 基因-疾病有效性、gnomAD popmax AF + 纯合子数 + 基因约束（**仅在 gnomAD 许可核实通过后**）
- ✅ 每个题面**强制做身份脱敏**，并配 CI 正则门禁
- ✅ 内嵌 20–30% 的**方案 D 翻转金丝雀**
- ✅ 每题的 provenance ledger 记录：`ReviewStatus` 字符串、`SCVsForAggregateGermlineClassification`、`LastEvaluated`、`CLINSIG_LAST_CHANGED`、来源 URL、SPDX、取数日期、官方 `.md5`

**先砍（明确移出 v1）**：
- ❌ 4★ 实践指南（时间切分后为 0，无法去污染）
- ❌ 所有 in-silico 预测分数（dbNSFP 为 CC BY-NC-ND + 商用付费 → 触碰白名单红线；单库分发同样普遍非商用）
- ❌ OMIM（许可未核实且已知受限）、GeneReviews 正文（明确有版权）
- ❌ 体细胞分类 / 致癌性分类（术语体系不同，需另一套真值验证）
- ❌ CNV / 结构变异
- ❌ 从 `Description` 自由文本做 NLP 证据抽取（引入我们自己的判断，逼近"自算真值"红线）
- ❌ 共分离 / 功能实验证据（ClinVar 结构化字段实测填充率为 0，只能从文献抽，违反许可与"不自算"原则）
- ❌ 依赖 `efetch` 取 VCV XML（实测返回空）

### 建议的 CI / 构建期自动门禁（针对 T2）

| # | 门禁 | 失败条件 |
|---|---|---|
| G1 | 真值星级 | 任一条目的 `ReviewStatus` ∉ {`reviewed by expert panel`, `practice guideline`} → FAIL |
| G2 | 时间切分 | 任一条目的 `CLINSIG_LAST_CHANGED` < cutoff → FAIL |
| G3 | **身份脱敏** | 题面文本正则命中 `c\.\d`、`p\.[A-Z][a-z]{2}\d+`、`rs\d+`、`NC_0`、`chr\d+:\d+`、`ClinVar ID`、`VariationID` → FAIL |
| G4 | 许可白名单 | provenance 中任一 SPDX 含 `-NC-` / `-ND-` / `-SA-`，或字面含 `NonCommercial` / `NoDerivatives` → FAIL |
| G5 | 结论词剥离 | `Description`（若使用）命中 `pathogenic` / `benign` / `likely` / `uncertain` → FAIL |
| G6 | 真值可追溯 | 条目没有对应的 `SCVsForAggregateGermlineClassification` → FAIL |
| G7 | 路径存活 | `tab_delimited/`、`vcf_GRCh38/` 任一路径返回非 200 → FAIL（2026 年 `txt/` 已整体 404，此门禁有真实先例） |
| G8 | 污染金丝雀 | 方案 D 子集的翻转一致率低于阈值 → 告警（提示题目可能被记忆污染） |

---

## 9. 未核实项清单（及用户自行核实步骤）

| # | 未核实项 | 原因 | 核实步骤 |
|---|---|---|---|
| 1 | **gnomAD 的许可条款** | `https://gnomad.broadinstitute.org/policies` 与 `/terms` 均为 JS 渲染，curl 原始 HTML 无许可文本；仅拿到二手描述 | ① 浏览器打开 policies 页抄录原文；② 或读 gnomAD v4 下载包的 README / 授权文件；③ 或邮件 `gnomad@broadinstitute.org`。**核实前 gnomAD 数据不得进入可交付数据** |
| 2 | **ClinVar 结构化 ACMG 证据属性（`AlleleFrequency`/`CosegregatingFamilies`/`Experimental` 等）的真实填充率** | 实测仅在 1 条完整记录（`VCV000091629`）中为 **0**，样本量 n=1 | 下载一期 `ClinVarVCVRelease` 月度 XML，统计 `Attribute Type="CosegregatingFamilies"` 等的出现次数；或随机抽 200 条 VCV 记录逐条统计 |
| 3 | **`ClassificationHistory` / `DescriptionHistory` 的填充率** | 实测在 `VCV000091629` 中出现次数为 0 | 同 #2；另可在 ClinVar 网页版变异页查看是否有 "Reclassification" 区块 |
| 4 | **XSD 中 `DateCreated` 的完整官方注释句** | 本地 grep 只取到片段 `"DateCreated is the date when the record first became public in ..."`，被多行截断 | 直接读 `ClinVar_VCV.xsd` 中 `name="DateCreated"` 附近的 `<xs:documentation>` 完整段落 |
| 5 | **时间切分池 ∩ ClinGen VCEP 基因 ∩ Definitive 有效性 的实际交集大小** | 需要跨库 join，本次未执行 | 跑构建脚本：`CLINSIG_LAST_CHANGED ≥ 2024` 的 3★ 变异（实测 4,325 条）⋈ ClinGen gene-validity 表，统计剩余条目数。**这决定 v1 是 100+ 题还是只有 ~30 题**，是 v1 能否立项的关键数字 |
| 6 | **Sequence Ontology (SO) 的许可** | 本次未核验 | 查 `https://github.com/The-Sequence-Ontology/SO-Ontologies` 的 LICENSE（预期 CC BY 4.0，符合白名单） |
| 7 | **OMIM 的数据许可** | 本次未核验；NCBI 政策页已提示 OMIM 属第三方版权资源 | 查 `https://omim.org/help/copyright`。**默认按排除处理，改用 MedGen** |
| 8 | **VCV XML 的程序化访问路径** | `efetch.fcgi?db=clinvar&rettype=vcv&retmode=xml` 对测试 ID 返回空（110 字节空记录集） | 确认是否需要改用 `rettype=vcv` + VCV accession，或只能走 FTP 月度大文件 |
| 9 | **`CLINSIG_LAST_CHANGED` 在 Entrez 索引中是否为"每变异单值"** | 已确认按年份正确分桶（各年数量互异），未确认多条件/多病种记录是否会有多个值 | 用 `esearch` 取少量 ID，逐一 `esummary` 对照网页版"Last change to clinical significance"字段 |
| 10 | **ClinVar FTP 路径的长期稳定性** | `txt/` 已在 2026 年前整体 404 更名为 `tab_delimited/` | 已建议 G7 门禁；另在 ledger 中固化取数日期与官方 `.md5` |

---

## 附录 A：本次全部一手来源 URL

| 用途 | URL | 取数日期 |
|---|---|---|
| 目录结构（发现 `txt/` 已 404） | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/` | 2026-09-12 |
| tab_delimited 目录清单 | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/` | 2026-09-12 |
| 列定义权威 README | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/README` | 2026-09-12 |
| `variant_summary.txt.gz` 真实表头 | HTTP Range 0–400000，部分解压 | 2026-09-12 |
| `submission_summary.txt.gz` 真实表头 | HTTP Range 0–800000，部分解压 | 2026-09-12 |
| VCF 目录清单 | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/` | 2026-09-12 |
| VCF INFO 字段 | `clinvar.vcf.gz` HTTP Range 0–300000，部分解压 | 2026-09-12 |
| VCF README | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/README_VCF.txt` | 2026-09-12 |
| 星级 ↔ 措辞映射 | `https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/` | 2026-09-12 |
| 官方规模统计 | `https://www.ncbi.nlm.nih.gov/clinvar/docs/statistics/` | 2026-09-12 |
| 分类术语体系 | `https://www.ncbi.nlm.nih.gov/clinvar/docs/clinsig/` | 2026-09-12 |
| XSD 日期属性 | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/xsd_public/ClinVar_VCV.xsd` | 2026-09-12 |
| XML 真实记录样本 | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/xml/sample_xml/VCV_XML_VCV000091629.xml` | 2026-09-12 |
| XML README | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/xml/_README` | 2026-09-12 |
| Entrez 可检索字段 | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?db=clinvar` | 2026-09-12 |
| 计数校验 | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&rettype=count&term=...` | 2026-09-12 |
| NCBI 使用政策（公有领域 + 第三方权利保留） | `https://www.ncbi.nlm.nih.gov/home/about/policies/` | 2026-09-12 |
| SPDX `NCBI-PD` 全文 | `https://spdx.org/licenses/NCBI-PD.html` | 2026-09-12 |
| ClinGen 条款（CC0 1.0） | `https://www.clinicalgenome.org/docs/terms-of-use/` | 2026-09-12 |
| dbNSFP 许可（CC BY-NC-ND 4.0） | `https://www.dbnsfp.org/license` | 2026-09-12 |
| gnomAD（**未能核实**） | `https://gnomad.broadinstitute.org/policies`、`/terms`、`/about` | 2026-09-12 |

## 附录 B：复核用的最小命令集

```bash
# 1) 官方 3★ / 4★ 规模（不下任何大文件）
curl -s 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&rettype=count&term=%22reviewed+by+expert+panel%22%5BReview+status%5D'

# 2) 时间切分池：2025–2026 年被改判的 3★ 变异
curl -s 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&rettype=count&term=%22reviewed+by+expert+panel%22%5BReview+status%5D+AND+2025%3A2026%5BCLINSIG_LAST_CHANGED%5D'

# 3) 取 variant_summary 真实表头（只拉 400 KB，不下载 442 MB）
curl -s -r 0-400000 'https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz' -o vs.gz
python -c "import zlib;d=zlib.decompressobj(16+zlib.MAX_WBITS);print(d.decompress(open('vs.gz','rb').read()).decode('utf-8','replace').split(chr(10))[0])"

# 4) 取 VCF 全部 INFO 字段定义（只拉 300 KB）
curl -s -r 0-300000 'https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz' -o cv.gz
python -c "import zlib;d=zlib.decompressobj(16+zlib.MAX_WBITS);t=d.decompress(open('cv.gz','rb').read()).decode('utf-8','replace');[print(l) for l in t.split(chr(10)) if l.startswith('##')]"
```
