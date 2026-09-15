# VeriBench-Bio 数据合规与可行性调研报告

**调研对象**：VeriBench-Bio —— 计划公开分发、可被第三方复现与引用的生命科学/生信实操评测集
**调研日期**：2026 年 9 月
**调研人**：数据合规与可行性调研员
**方法**：仅采信一手来源（NIST 官方页、NCBI/NLM 政策页、EBI/ENA/BioStudies、wwPDB、Zenodo API、GNU/SPDX、工具官方 LICENSE 文件）。每条结论附 URL；无法读到全文的一律标注「无法核实」并给出人工核实步骤。

> **状态**：本报告已完成。所有许可结论均基于文末所列 URL 在 2026 年 9 月可访问的原文；无法读到全文的条目已在 §12 逐条列出。**本报告不构成法律意见。**

---

## 0. 执行摘要（先看这 9 条）

1. **GIAB 是本题集最干净的人类数据源，但有样本差异**。NIST 明确「All GIAB data is made available with no embargo on publications using the data」，NIST 数据在美国不受版权保护、境外授予免版税全球再分发与改作权。**但** NIST 同时写明 Ashkenazi/Han 双 trio（HG002–HG005）来自 PGP，「more broadly consented, **including for commercial redistribution**」，措辞为「unlike the pilot genome」→ pilot HG001/NA12878（HapMap 来源）**并未**获得同等的商用再分发同意。**→ 变异检出题的主样本从 HG001 换成 HG002。**
2. **HG002 的 v4.2.1 已被 v5.0q 取代**（2025-11 起，v4.2.1 对 HG002 标记 deprecated）。v4.2.1 仍可用，但必须在 DATACARD 写明 deprecated 状态与替代版本。
3. **PMC Open Access Subset 在 2026 年 8 月发生破坏性变更**：OA Web Service 下线（2026-08-25，端点已实测 **404**）、`oa_file_list.csv` 已删（已实测 **404**）、`oa_comm/oa_noncomm/oa_other` 目录已移除。任何基于 `oa_file_list.csv` + license 列的流水线**已失效**。现行唯一合法通道是 **S3 Cloud Service / OAI-PMH / E-utilities / BioC API**。**并且 NCBI 官方推荐的商用检索式对我们的用例是错的**（它含 `cc by-nd` 与 `author manuscript`）。
4. **ClinVar 与 GEO 是两种截然不同的东西**：ClinVar 是 NCBI 自建库，只要求 attribution，可自由再分发、可商用；GEO **根本没有 license 字段**，NCBI 声明「不限制使用与再分发」但同时又声明**无法授予许可**、提交者可能保留权利。GEO 题**只能发脚本 + accession + 自算参考答案**。
5. **✅ 已推翻 4 个流行误解**：**RTG Tools / vcfeval = BSD-2-Clause**（非商用限制属于 RTG Core，且 RTG Core 3.13 起也已 BSD）；**GATK4 ≥4.2 = Apache-2.0**（不是 BSD-3）；**salmon ≥2.0 = BSD-3-Clause**、**STAR ≥2.7.2a = MIT**（GPLv3 只适用于旧版本）。**真正的非商用陷阱是 GATK3（2.0–3.x，Broad 学术非商用专有协议）**。
6. **# 全题集可做到零 GPL 工具依赖。** 每个环节都有宽松许可替代：BWA→**BWA-MEM2 (MIT)**；salmon→**salmon≥2.0 (BSD-3)** 或 **kallisto (BSD-2)**；edgeR/limma→**PyDESeq2 (MIT)**；vcfdist→**hap.py + RTG vcfeval (BSD-2)**。**「只发 Dockerfile 以规避 GPL」因此不必要。**
7. **我们技术栈里唯一真正的合规陷阱是 R 包**：`library(edgeR)`（GPL-2+）在**解释器进程内加载**，FSF 视其为结合作品（不同于 subprocess 调用的安全港）。→ DE 题改用 **PyDESeq2 (MIT)**，或把 R 调用隔离进一个**明确 GPL 兼容**的 shim 脚本。
8. **任务简报的「ENA 比 SRA 更宽松」前提被证伪**：SRA 与 ENA 同受 INSDC 统一政策约束，条款**对称**（「no restrictions or licensing fees … on the redistribution or use of the database by any party」）。真实差异是**运营性/基础设施性**的，且**云端镜像方面 SRA 反而更宽松**（官方明示「Unlimited concurrent downloads from our cloud buckets to your buckets」）。
9. **Cuatro Ciénegas 的许可干净（环境样本、NCBI、论文 CC BY 4.0），但没有权威物种组成真值** → 组成题应替换为 **CAMI2**（CC BY 4.0，有官方 gold standard）。**Micrococcus 直系同源聚类题找不到任何权威公开真值 → 应放弃。** 污染风险最高的是 **ClinVar 变异解读**与**经典 GEO DE 题**。

---

## 1. GIAB / NIST v4.2.1 真值集（HG001/NA12878、HG002）

### 1.1 是否公有领域 / 可否自由再分发

**结论：可以自由再分发。NIST 数据在美国不受版权保护，境外以免版税许可授予再分发与改作权。**

一手条款（NIST 官方页 "Copyright, Fair Use, and Licensing Statements for SRD, Data, Software, and Technical Series Publications"，URL: <https://www.nist.gov/open/license>，页面标注 Updated June 24, 2025）：

> 「Data/works created by NIST employees that are not covered by the Standard Reference Data Act are subject to 17 U.S.C. §105 and **generally are not subject to copyright protection within the United States**. NIST data or other works may be subject to copyright protection in foreign countries.」

> 「To the extent that NIST may hold copyright in countries other than the United States, you are hereby granted the **non-exclusive irrevocable and unconditional right to print, publish, prepare derivative works and distribute** the NIST data, in any medium, or authorize others to do so on your behalf, **on a royalty-free basis throughout the world**.」

> 「You may improve, modify, and create derivative works of the data or any portion of the data, and you may copy and distribute such modifications or works.」

**关键区分（必须写进 DATACARD）**：该页同时规定 **Standard Reference Data (SRD)** 是被商务部代美国政府主张版权的例外类别（15 U.S.C. § 290e），需按 SRD 许可使用。GIAB 的 benchmark VCF/BED 属于 NIST 员工创作的**数据/作品**，不是 SRD 数据产品（NIST 的 SRD 是 Chemistry WebBook、SRD 系列数据库这类）。但**NIST Reference Material 的实物 DNA（RM 8391/8392/8393/8398）**是实物标准物质，购买受 NIST Storefront 条款约束——**我们不购买、不分发实物，只分发数据，故不受影响**。

**再分发要求**：NIST 要求
> 「Modified works should carry a notice stating that you changed the data and should note the date and nature of any such change. Please explicitly acknowledge the National Institute of Standards and Technology as the source of the data」

→ 我们的数据集/镜像里如有 GIAB 派生物（例如 subset 出来的 chr20 VCF/BED），**必须注明「changed from NIST GIAB original, <日期>, <改动内容>」**。

### 1.2 商用可否 —— **这是本题集唯一的真实风险点**

NIST GIAB 主项目页（<https://www.nist.gov/programs-projects/genome-bottle>，Updated May 12, 2026）原文：

> 「GIAB has currently characterized a pilot genome (NA12878/HG001) from the HapMap project, and two son/father/mother trios of Ashkenazi Jewish and Han Chinese ancestry from the Personal Genome Project (**selected because, unlike the pilot genome, they are consented for commercial redistribution**).」

GIAB FAQ 第 11 问（<https://www.nist.gov/programs-projects/faqs-genome-bottle>，Updated May 12, 2026）：

> 「The GIAB Ashkenazi and Chinese trios are from the Personal Genome Project, since they are **more broadly consented, including for commercial redistribution**, development of iPSCs, etc.」

**解读（谨慎但明确）**：
- **数据本身**（NIST 生成的 VCF/BED/BAM）：公有领域 / 免版税，可再分发、可商用。
- **HG002/HG003/HG004/HG005（PGP 来源）**：捐赠者同意范围**明确包含**商用再分发。
- **HG001/NA12878（HapMap 来源）**：NIST 的措辞是「unlike the pilot genome」，即**捐献同意未明确覆盖商用再分发**。样本层面存在同意瑕疵。
- **实务结论**：如果我们把 HG001 的 benchmark VCF 打包进公开仓库并声明「可商用」，我们是在对**样本来源方的同意范围**做超出 NIST 明示的推断。NIST 自己没这么说。
  → **建议：变异检出题主样本用 HG002（RM 8391）。HG001 可用于学术/非商用示例，但不要进入「明确允许商用」的声明范围。**

### 1.3 是否属人类受控数据（dbGaP）？

**结论：GIAB 主数据集不在 dbGaP，是完全公开的。** 依据：
- GIAB 数据经 NCBI 作为 DCC 在**公开 FTP** 与 **公开 S3 bucket `s3://giab`** 分发，无登录、无 DAC 审批（<https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/>；<https://registry.opendata.aws/giab/>）。
- GIAB 项目页原文：「Data and analyses from most short, linked, and long read sequencing methods are **publicly available without publication embargo**」。
- AWS Open Data Registry 对 GIAB 的 License 字段写：「There are no restrictions on the use of this data.」（<https://raw.githubusercontent.com/awslabs/open-data-registry/main/datasets/giab.yaml>）
- GIAB FAQ 第 4 问：「Yes, we encourage all to use these data. **All GIAB data is made available with no embargo on publications using the data.**」

⚠️ **仍需注意**：`s3://giab` 是 2020-11-12 的镜像，**不是最新**。最新版本在 NCBI FTP（release 路径）。不要引用 S3 镜像来声称「最新 v4.2.1」。

**NIST 的 data use 条款原文位置**：<https://www.nist.gov/open/license>（标题 *Copyright, Fair Use, and Licensing Statements for SRD, Data, Software, and Technical Series Publications*），以及项目特定的 <https://www.nist.gov/programs-projects/faqs-genome-bottle>（第 4、11 问）。**没有一份单独的 "GIAB Data Use Agreement" 文件**——NIST 从未对 GIAB 发布数据使用协议，因为不需要。

### 1.4 版本现状（2026-09）

（来源：<https://www.nist.gov/programs-projects/genome-bottle>，Updated May 12, 2026）

| 产品 | 状态 |
|---|---|
| HG002 v5.0q（small variants + SV，GRCh37/GRCh38/T2T-CHM13v2.0） | **当前推荐**，基于 T2T-HG002 v1.1 组装；preprint <https://doi.org/10.1101/2025.09.21.677443> |
| HG002 v1.0 mosaic benchmark（GRCh38 SNV） | 当前可用，<https://doi.org/10.1016/j.xgen.2025.101104> |
| **v4.2.1（全部 7 个样本，GRCh37/GRCh38）** | **仍可用，但对 HG002 已被 v5.0q 取代（deprecated）**；manuscript <https://doi.org/10.1016/j.xgen.2022.100128> |
| HG008-T 胰腺癌 tumor/normal | 2025 新增，broadly consented |

基准文件路径：<https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/>

### 1.5 结论

| 项 | 结论 |
|---|---|
| 许可 | 美国境内无版权（public domain，17 U.S.C. §105）；境外 = NIST 免版税、不可撤销、全球、允许改作与再分发的许可 → SPDX 可标为 `LicenseRef-NIST-Public-Domain`（无标准 SPDX ID） |
| 可再分发 | ✅ 是（需注明改动 + 致谢 NIST） |
| 可商用 | ✅ 数据本身可以；⚠️ **建议仅对 HG002–HG005 做明确商用声明，HG001 不声明** |
| 人类数据限制 | 完全公开，不在 dbGaP，无 DAC；但属人类基因组数据，需在 DATACARD 写明「donor-consented, de-identified, PGP/HapMap 来源」 |
| **结论** | **可用（打包 benchmark VCF + BED）**；主样本改用 HG002 |

---

## 2. GEUVADIS（Lappalainen et al. 2013）

### 2.1 数据落在哪里

- **ArrayExpress/BioStudies**: `E-GEUV-1`，标题「RNA-sequencing of 465 lymphoblastoid cell lines from the 1000 Genomes」，release 2012-11-06。API 实测（2026-09）：<https://www.ebi.ac.uk/biostudies/api/v1/studies/E-GEUV-1>，其中链接字段为 `ERP001942`（Type = ENA）与 `E-GEUV-1`（Type = gxa，即 Expression Atlas）。
- **ENA**: `ERP001942`（raw reads + BAM）。样本为 462 个 LCL，5 个 1000 Genomes 群体（British/Finland/Utah/Yoruba/Tuscan），每个样本有 ERS 号。
- **Expression Atlas**: `E-GEUV-1`，processed expression 数据。
- 论文：Lappalainen T. et al., *Nature* 501:506–511 (2013)，DOI `10.1038/nature12531`。

### 2.2 许可

**结论：BioStudies/ArrayExpress 记录里没有 license 字段（无统一许可标注）；可行路径是走 Expression Atlas，其为 CC BY 4.0。**

- 实测 BioStudies API 返回的 `E-GEUV-1` 记录中**完全没有 license 属性**（只有 Title/ReleaseDate/Organism/Study type/Description/Protocols/Publications/Factors）。这不是「漏读」——BioStudies/ArrayExpress 对 2012 年提交的这批数据不强制/不记录 license。→ **无法从数据源记录本身核实许可。**
- **Expression Atlas 许可页**（<https://www.ebi.ac.uk/gxa/licence.html>，2026 年 9 月可访问）原文：
  > 「We are applying the **Creative Commons Attribution 4.0 International License** for all copyrightable material on our website. This includes the species anatomograms. This means that anyone is free to copy, reuse, display and distribute the images and information on our database, provided you give us credit」
  
  → 通过 Expression Atlas 取得 `E-GEUV-1` 的**处理后表达量数据**适用 **CC BY 4.0**（可再分发、可改作、**可商用**）。
- **ENA `ERP001942` 的 raw reads**：ENA 本身不设许可字段，受 EMBL-EBI Terms of Use 与 INSDC 开放数据原则约束（见 §9）。

### 2.3 商用可否

- Expression Atlas 路径：**可商用**（CC BY 4.0 无 NC 限制）。
- ENA raw reads 路径：见 §9，判断为可商用（ENA 无 NC 条款），但**须自行承担第三方权利风险**（IGSR disclaimer 明文如此，见 §9.3）。

### 2.4 结论与建议

| 项 | 结论 |
|---|---|
| 许可 | ArrayExpress/BioStudies 记录**无许可字段**（无法从记录核实）；Expression Atlas 路径 = **CC BY 4.0** |
| 可再分发 | ✅（走 Expression Atlas 的 processed 数据；需 CC BY 署名） |
| 可商用 | ✅ |
| 人类数据限制 | 样本来自 1000 Genomes Project 的公开 LCL，**开放获取**，非受控（但注意 Coriell LCL 的 MTA 只约束实物细胞，不约束已公开序列数据） |
| **结论** | **可用**，但**优先分发 Expression Atlas 的 processed 定量值 + 下载脚本**，不要把 ENA 的 BAM 打包进仓库（体积 + 权利链不清晰） |

**关于「582 transcripts」**：用户提到的 582 transcripts 基准，其具体来源（是论文附表、还是某个第三方 benchmark 整理）**无法核实**。若要使用，需确认该 582 条转录本清单的出处与许可；如出自论文补充材料，则受该期刊条款约束（*Nature* 2013 年文章的补充材料通常为订阅内容或 CC BY-NC-ND，需逐条确认）。**建议：不要沿用 582 这个数字，改用从 Expression Atlas 完整定量矩阵中自行定义可复现的子集，并在 DATACARD 中给出选择规则与校验和。**

---

## 3. GEO（RNA-seq 差异表达题）

> **调研限制说明**：本报告调研期间，`www.ncbi.nlm.nih.gov/geo/*` 全部页面返回 **reCAPTCHA 拦截**（`Checking your browser`），无法直读。以下 GEO 页面原文取自 **NCBI 自身页面的存档镜像**（Forgejo repo `publicdata/nih-gov`，commit `bd43325b8ac26043be386420dbd6105b3d486ce3`），镜像保留了 NCBI 自己的 "Last modified" 日期（2024-07-16 / 2024-08-21 / 2024-09-05）。NCBI 的非 `/geo/` 路径（SRA 文档、policies）与 GEO **FTP** 主机可正常访问。凡镜像内容均在下方标注 **[存档镜像]** 并给出两个 URL。若镜像与 NCBI 现行页面冲突，以现行页面为准 —— **请用户用浏览器复核一次**（见 §12）。

### 3.1 许可是否统一？—— 更准确的说法是「GEO 根本没有许可字段」

**结论：GEO **没有** per-series 许可，也**没有**统一许可。GEO 不携带任何 license/rights 元数据字段；唯一的权利声明是**存档级**的，而且它是一份「NCBI 无力授权」的免责声明，**不是**许可授予。**

**GEO Disclaimer**（<https://www.ncbi.nlm.nih.gov/geo/info/disclaimer.html>）[存档镜像] <https://git.lsit.ucsb.edu/publicdata/nih-gov/raw/commit/bd43325b8ac26043be386420dbd6105b3d486ce3/www.ncbi.nlm.nih.gov/geo/info/disclaimer.html>，镜像标注 "Last modified: July 16, 2024"：

> **GEO Availability**
> 「The GEO database is designed to provide and encourage access within the scientific community to the most up to date and comprehensive gene expression and hybridization array data. Therefore, **NCBI places no restrictions on the use or distribution of the GEO data**. However, **some submitters may claim patent, copyright, or other intellectual property rights in all or a portion of the data they have submitted. NCBI is not in a position to assess the validity of such claims, and therefore cannot provide comment or unrestricted permission concerning the use, copying, or distribution of the information contained in GEO.**」

> **Copyright Status**
> 「Unless otherwise stated, documents and files on NCBI Web servers may be freely downloaded and reproduced. However, some material on this site, such as abstracts, may be copyright protected under the U.S. and foreign copyright laws. For such material, **the submitting authors or publishers retain all rights for reproduction or redistribution.** Permission to reproduce these documents may be required. All persons reproducing, redistributing, or making commercial use of this information are expected to adhere to the terms and conditions asserted by the copyright holder.」

**NCBI Website and Data Usage Policies**（<https://www.ncbi.nlm.nih.gov/home/about/policies/>，可直读）：

> 「**NCBI itself places no restrictions on the use or distribution of the data contained therein. Nor do we accept data when the submitter has requested restrictions on reuse or redistribution.** However, some submitters of the original data (or the country of origin of such data) may claim patent, copyright, or other intellectual property rights in all or a portion of the data (that has been submitted). NCBI is not in a position to assess the validity of such claims and **since there is no transfer of rights from submitters to NCBI, NCBI has no rights to transfer to a third party. Therefore, NCBI cannot provide comment or unrestricted permission concerning the use, copying, or distribution** of the information contained in the molecular databases.」

**⇒ 回答「统一还是逐条不同」**：存档级条款**不随提交变化**，因为 NCBI 明示**拒绝**带再利用/再分发限制的提交。因此实际只有一套「存档级姿态」。但它**不是许可**，且 NCBI 明说**无法授予许可**。提交者仍可能主张的权利在 NCBI 之上，且在 GEO 元数据中**不可见**。

### 3.2 已核实：GEO 元数据没有 license 字段（四种独立验证）

1. **SOFT 格式文档**（<https://www.ncbi.nlm.nih.gov/geo/info/soft.html>）[存档镜像] —— 文档化了全部 Series 属性（`Series_title`、`Series_summary`、`Series_overall_design`、`Series_pubmed_id`、`Series_web_link`、`Series_contributor`、`Series_variable_[n]`、`Series_sample_id`、`Series_geo_accession` 等）与批量下载附加属性（`_contact_*`、`Series_type` 等）。**对该文档全文扫描 `licen` / `copyright` / `relation` → 0 命中。** 不存在 license、copyright、terms 或访问限制属性；**Series 属性表中也未文档化 `Series_relation`**。
   （注：「GEO discontinued the use of SOFT format for data submissions and updates in early 2024, but continues to make all records available for download in SOFT format.」）
2. **MINiML 文档**（<https://www.ncbi.nlm.nih.gov/geo/info/MINiML.html>）[存档镜像] —— Series 元素仅有 `Title`、`Summary`、`Type`、`Overall-Design`、`Pubmed-ID`、`Web-Link`、`Contributor-Ref`、`Sample-Ref`、`Variable`、`Repeats`。**无 license 元素。**
3. **GEO (GDS) 结构化 API 字段枚举**（`esummary.fcgi?db=gds&id=200345774&version=2.0&retmode=json`）—— 返回字段全集为 `uid, accession, gds, title, summary, gpl, gse, taxon, entrytype, gdstype, ptechtype, valtype, ssinfo, subsetinfo, pdat, suppfile, samples[], relations[], extrelations[], n_samples, seriestitle, platformtitle, platformtaxa, samplestaxa, pubmedids[], projects[], ftplink, geo2r`（v2.0 另有 `bioproject`）。**无 license / copyright / access-control 字段。** 最接近的 `relations[]` 与 `extrelations[]` 在抽样记录中（含一条有 BioProject 的）均为空。
4. **GEO Overview**（<https://www.ncbi.nlm.nih.gov/geo/info/overview.html>）[存档镜像] —— 记录构成（Platform/Sample/Series/DataSet/Profile）中**没有**任何权利或许可组件。

### 3.3 「GEO 数据默认不可再分发」—— 需要精确表述

**若读作「GEO 禁止再分发」则为假；若读作「GEO 不给你授权也不给你担保」则为真。**

**支持「有问题」一侧：**
- disclaimer：「NCBI ... **cannot provide comment or unrestricted permission** concerning the use, copying, or distribution」
- NCBI policy：「there is **no transfer of rights from submitters to NCBI**, NCBI has **no rights to transfer to a third party**」
- 两页都点名风险：「some submitters ... may claim patent, copyright, or other intellectual property rights」；「**the submitting authors or publishers retain all rights for reproduction or redistribution**」
- 元数据**无 license 字段** → 即便提交者想声明条款，下游也无法机读

**反对强读法一侧：**
- disclaimer：「**NCBI places no restrictions on the use or distribution of the GEO data**」
- NCBI policy：「**NCBI itself places no restrictions on the use or distribution of the data contained therein. Nor do we accept data when the submitter has requested restrictions on reuse or redistribution.**」
- GEO FAQ：「The release date is the date on which your data are made public and will be available for **anyone to access, download and re-use**.」；「**Who can use GEO data?** — Anybody can access and download public GEO data. There are no login requirements.」
- NCBI 自己的 GEO 更新论文（Nucleic Acids Res 2024，PMID 37933855，<https://pmc.ncbi.nlm.nih.gov/articles/PMC10767856/>）称 GEO 为「**open-access**」数据，「**free to read, download**」

**⇒ 净结论**：再分发者拿到的是**宽松的存档级声明**，但**没有担保、没有赔偿**。这才是真实且已被文档化的风险 —— **不是默认禁止。**

### 3.4 GEO 承载的人类受控数据：真实机制

**GEO 自身被声明为 unrestricted-access 数据库；受控访问的人类数据被路由到 dbGaP，而不是在 GEO 内部打标记。**

GEO FAQ「Human Subject Guidelines: Can I submit data derived from human subjects?」[存档镜像] 原文：
> 「If your data need controlled access, deposit your data with NCBI's **dbGaP** database.」
> 「**GEO is an unrestricted-access database.** Please read the following guidelines for Human Genomic Data Submitted to Unrestricted-Access Repositories.」
> 「If you do not have consent to make the data fully public in a database like GEO, you can apply to the NIH Office of Science Policy ... **dbGaP has controlled-access mechanisms** and is an appropriate resource for hosting sensitive patient data.」

GEO FAQ「Does GEO store raw data?」：
> 「For high-throughput sequencing, GEO **brokers the complete set of raw data files, e.g., FASTQ, to the SRA database** on your behalf.」

NCBI SRA 提交文档（<https://www.ncbi.nlm.nih.gov/sra/docs/submit/>，可直读）：
> 「Majority of SRA submissions are submitted via SRA Submission Portal Wizard. However, certain types of SRA data must be submitted via **dbGaP or GEO** databases.」
> 「**Do not transmit unconsented human data intended for dbGaP submissions to the public SRA database.**」

NCBI SRA 总览（<https://www.ncbi.nlm.nih.gov/sra/docs/>）：
> 「It is the responsibility of submitting parties to ensure that they have appropriate consent for human sequence data to be distributed publicly without access controls.」

⚠️ **关于「GSE***** is a controlled access series」这个具体措辞 —— 已测试，它不是 GEO 的用法。**
- 检索 `"controlled access series"` 返回 `QuotedPhraseNotFound`（引号短语未命中），引擎退化为 AND 检索（`controlled AND access AND series`，count 118）。对 `"is a controlled access series"` 同样 `QuotedPhraseNotFound`。
- 两词短语**确实**被索引：`"controlled access"` → **Count 1057**，短语检索被接受。
- 但**未能在任何记录的公开展示文本中定位该短语**：GSE345774 与 GSE316688 都命中短语查询（用 `... AND GSE345774[Accession]` 验证 Count=1），然而短语**不在**其 `title`、`summary`、样本标题、`relations`、`extrelations` 或 `esummary`/`efetch` 返回的任何字段中。→ **它存在于一个公开 summary API 不暴露的 GEO 索引字段里。**
- **⇒ 记录级 banner 的确切字符串无法核实**（见 §12）。已确认的是**政策机制**：GEO 声明自己是 unrestricted-access，并把受控访问研究引向 dbGaP。

### 3.5 只发「脚本 + accession + 参考答案」的风险评估

| 分发内容 | 风险 | 依据与说明 |
|---|---|---|
| **(a) 下载脚本**（`prefetch`/`fastq-dump`/`wget`/GEOquery）+ GSE accession | 🟢 **低** | NCBI/ GEO 条款中**没有任何**限制撰写、发布或分发抓取脚本的条文；NCBI 自己的文档反而主动教授程序化访问（E-utilities、"Construct a URL"、SRA Toolkit、GEOquery —— <https://www.ncbi.nlm.nih.gov/geo/info/faq.html#prog>、<https://www.ncbi.nlm.nih.gov/sra/docs/sradownload/>）。<br>**但以下操作义务是有据的**（NCBI policies「Guidelines for Scripting Calls to NCBI Servers」）：≤ **3 请求/秒**；使用 `email` 与 `tool` 参数；批量走 `eutils.ncbi.nlm.nih.gov`；>100 请求的序列安排在**非高峰时段**（周末，或工作日 21:00–05:00 ET）；**必须让服务的用户看到 NCBI 的免责与版权声明**。这些是操作/署名要求，不是许可限制。<br>**不要**设计脚本绕过访问控制，**不要**分发 dbGaP 或其他受控数据的凭据/token。 |
| **(b) accession 号** | 🟢 **低** | GEO FAQ：「Anybody can access and download public GEO data. There are no login requirements.」引用规范是 citation norm，非许可条件。<br>⚠️ 需写进题集的注意点：accession 的**状态会变**——NCBI 文档说明数据可能被 suppress/withdraw，且「public sequence data made available by NCBI may be retrieved and redistributed by other users」。→ **落盘快照是复现性措施；日后重新解析 accession 可能失败。** |
| **(c) 我们自算的派生结果**（DEG 列表等） | 🟢 **最低** | 依据不在法理推测，而在 NCBI 自己的文本：① NCBI 的操作性陈述是关于**使用**的：「NCBI itself places no restrictions on **the use** or distribution of the data contained therein」；GEO FAQ 说已发布数据可供「access[ed], download[ed] and **re-use[d]**」。② NCBI 的 SRA 处理页**明确预期下游再分发与再包装**：「Public sequence data made available by NCBI may be retrieved and **redistributed by other users and presented in other websites, databases, tools, publications, curricula, conference proceedings, or other venues that are not managed by NCBI**.」（<https://www.ncbi.nlm.nih.gov/sra/docs/sequence-data-processing/>）③ **NCBI 自己就把派生结果作为一等数据分发**：GEO2R 产出差异表达表并提供 "Download full table"，NCBI 也生成并分发 RNA-seq count 矩阵。<br>⚠️ **残留的、已被文档化的注意点**：GEO disclaimer 中「submitters may claim patent, copyright, or other intellectual property rights」是 NCBI 点名的**唯一**权利挂钩，而 NCBI 说它「cannot provide comment or unrestricted permission」。DEG 列表是我们的分析产出而非提交数据集的拷贝，因此离那个挂钩更远——但 **NCBI 的文本里没有担保或赔偿**。若题集涉及商业使用，**这句话是要提示法务的**。NCBI 未就派生结果作任何方向性表述。 |
| **原始 FASTQ/BAM/counts 打包** | 🔴 **高** | **不要做。** 无许可依据，且体积巨大 |

**额外提示（GEO/SRA 之外）**：若题集还分发 PMC 文章正文，则明文禁止适用 —— 「**Systematic downloading of batches of articles from the main PMC web site, in any way, is prohibited because of copyright restrictions.**」（<https://pmc.ncbi.nlm.nih.gov/about/copyright/>）。**正文不入库**，或走 PMC 的 OAI-PMH / Cloud / E-utilities 通道。

### 3.6 结论

**可用，但必须以「脚本 + accession + 自算答案」形式。** DATACARD 中必须写明：
- 「本题目不分发任何 GEO 原始数据。使用者须自行从 NCBI GEO 获取 GSE#####，并自行遵守 NCBI 数据使用政策。」
- 「**GEO 不携带任何许可字段**；NCBI 声明不限制使用与再分发，但明示其**无法授予许可**，且提交者可能保留知识产权。我们据 NCBI 政策行事，不主张已获得许可。」
- 「我们已人工确认所用 GSE 不属于受控访问（dbGaP）研究。」（注意：**不要**引用「controlled access series」作为 GEO 的官方标记字符串 —— 见 §3.4）
- 脚本须遵守 §3.5(a) 的速率与署名义务。

---

## 4. ClinVar（变异解读题真值）

### 4.1 是否公有领域 / 再分发与商用限制

**结论：ClinVar 由 NCBI 自建，属美国政府作品，可自由再分发与商用，只要求 attribution（非强制许可条件，是「请求」）。**

一手条款页：<https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/>，原文：

> 「**Disclaimer and data use policy** — The information on this website is not intended for direct diagnostic use or medical decision-making without review by a genetics professional. ... NIH does not independently verify the submitted information.」

> 「**If you distribute or copy data from ClinVar, we ask that you provide attribution to ClinVar as a data source in publications and websites.** You can cite of one the ClinVar publications (e.g. PMID: 29165669).」

注意措辞：是 **"we ask"**（请求），不是 "you must"。且**没有** NC 限制、**没有** ND 限制。

NCBI 通用免责声明：<https://www.ncbi.nlm.nih.gov/About/disclaimer.html>
NLM 网页政策（NLM 自建数据不受版权保护）：<https://www.nlm.nih.gov/web_policies.html>

**下载渠道（全部公开、无登录）**：
- 完整 XML: <https://ftp.ncbi.nlm.nih.gov/pub/clinvar/xml/>（每周更新，每月首个周四归档）
- VCF GRCh37/GRCh38: `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh37/`、`.../vcf_GRCh38/`（每月）
- TSV 摘要: `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/`
- API: E-utilities（esearch/esummary/elink/efetch），示例见上述条款页

### 4.2 结论

| 项 | 结论 |
|---|---|
| 许可 | 美国政府作品 / NLM 自建数据 → 公有领域（美国）；SPDX 建议 `LicenseRef-US-Gov-Public-Domain` 或直接 `CC0-1.0` 声明为便利标签（**严格说 CC0 是 NLM 未明确采用的**，建议写 "US Government work, public domain; attribution requested" ） |
| 可再分发 | ✅ |
| 可商用 | ✅（无 NC 条款） |
| 人类数据限制 | **无受控访问限制**——ClinVar 是公开提交、公开分发的临床变异解读数据库；但**含临床表型信息**，需在 DATACARD 说明「不用于临床决策」 |
| **结论** | **可用（可打包）** |

⚠️ **必须写进题面**：ClinVar 页面明示「not intended for direct diagnostic use or medical decision-making」。题集里不得暗示这是临床可用工具。

---

## 5. PMC Open Access Subset —— ⚠️ 2026 年 8 月发生破坏性变更

### 5.1 变更事实（已亲自核实）

**PMC FTP Service 页**（<https://pmc.ncbi.nlm.nih.gov/tools/ftp/>，页面 Last modified: Thu Aug. 20 2026）原文：

> 「**August 26, 2026: PMC's Article Dataset Distribution Service Changes Are Complete** — Changes to PMC's Article Dataset Distribution Service, first announced in February, are now complete. **All legacy PMC Article Dataset files on the FTP and Cloud Services were removed the week of August 24, 2026.**」
>
> 目前 FTP 上仅保留一项服务：**PMC ID Cross-referencing** — `PMC-ids.csv.gz`，Base FTP URL <https://ftp.ncbi.nlm.nih.gov/pub/pmc>

→ **`oa_file_list.csv`、`oa_file_list.txt`、`oa_comm/`、`oa_noncomm/`、`oa_other/` 等文件已不存在。**

**已直接验证的 404 / 目录快照（2026-09-12）**：
- `https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.csv` → **HTTP 404**
- `https://ftp.ncbi.nlm.nih.gov/pub/pmc/` 当前仅列出 `PMC-ids.csv.gz`、`_PMC-ids.csv.gz`、`readme.txt`
- `https://ftp.ncbi.nlm.nih.gov/pub/pmc/readme.txt`（2026-08-25 更新）：「All legacy files ... are in the process of being removed.」
- `https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC13900` → **HTTP 404**

**PMC OA Web Service 已下线**：<https://pmc.ncbi.nlm.nih.gov/tools/oa-service/>（公告 2026-08-25）：「As part of the PMC Article Dataset Changes announced on February 12, 2026, the PMC OA Web Service is no longer available.」

### 5.2 现在还能用什么（4 条合法路径）

根据 <https://pmc.ncbi.nlm.nih.gov/tools/openftlist/>（OA Subset 现行页面）与 <https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/>：
1. **AWS Cloud Service**（新数据集托管在 AWS）
2. **OAI-PMH**
3. **E-utilities**（Entrez）
4. **BioC API**

OA Subset 页面同时明确警示：
> 「Systematic retrieval (or bulk retrieval) of articles through any other automated process is prohibited.」
> 「Not all articles in PMC are available for text mining.」
> 「**License terms vary.**」

### 5.3 许可类别与可机读字段（变更后的权威口径）

**权威类别表**（<https://pmc.ncbi.nlm.nih.gov/tools/textmining/>，「License Terms」列）原文：
> **Commercial use allowed: CC0, CC BY, CC BY-SA, CC BY-ND**
> **Non-commercial use only: CC BY-NC, CC BY-NC-SA, CC BY-NC-ND**
> **Other: no machine-readable Creative Commons license, no license tagged, or a custom license**

⚠️ 该分类**只针对商用**。`CC BY-ND` 落在「允许商用」桶里，但**禁止改作**——对我们的用途仍然是死路（见 §5.5）。

**现行可机读字段 `license_code`**（<https://pmc-oa-opendata.s3.amazonaws.com/README.txt> §4.2）：每个版本的 JSON 元数据对象暴露
- `is_pmc_openaccess`、`is_manuscript`、`is_historical_ocr`、`is_retracted`
- **`license_code`** — 「a code for the license. This code either corresponds to the Creative Commons license codes ..., or is set to **'TDM'** for author manuscripts where the full text is available for text mining, and where the full text may also be used consistent with the principles of fair use under the copyright law.」

**8 个可查询的许可过滤器**（<https://pmc.ncbi.nlm.nih.gov/about/userguide/>，「By License」）：
`"cc license"[filter]`、`"cc by license"[filter]`、`"cc by-nd license"[filter]`、`"cc by-nc license"[filter]`、`"cc by-nc-nd license"[filter]`、`"cc by-nc-sa license"[filter]`、`"cc by-sa license"[filter]`、`"cc0 license"[filter]`

User Guide 同时警示：「**Please note that not all articles in the Open Access Subset have a CC license.**」NLM **不发布 SPDX 映射**——过滤器对应 CC 许可**名称**，不是 SPDX 标识符。**当前任何 NCBI 页面上都不存在 "NLM LICENSE" / "NO-CC CODE" / "TEXT" 这几个值**（那些是已删除的旧 `oa_file_list.csv` 里的值）。

### 5.4 许可分布——用一方 API 实测（2026-09-12）

**NLM/PMC 从未发布按许可的分项统计**（已核查 openftlist / textmining / pmcaws / userguide 四页，均无）。但可直接用一方 E-utilities 计数 API 测出，检索式为
`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term=<QUERY>&retmode=json&rettype=count`

| 检索式 | 条数 |
|---|---|
| `"open access"[filter]` | **8,219,033** |
| `"cc license"[filter]` | **7,813,394** |
| `"cc by license"[filter]` | **5,250,000** ⚠️ 数字过于整齐，视为近似 |
| `"cc by-nc-nd license"[filter]` | **1,079,607** |
| `"cc by-nc license"[filter]` | **998,714** |
| `"cc by-nc-sa license"[filter]` | **301,897** |
| `"cc0 license"[filter]` | **169,038** |
| `"cc by-nd license"[filter]` | **11,997** |
| `"cc by-sa license"[filter]` | **2,110** |
| `"author manuscript"[filter]` | **1,083,887** |

内部一致性检验：7 个 CC 子过滤器之和 = 7,813,363，vs `"cc license"[filter]` = 7,813,394（Δ 31，≈0.0004%）→ 说明这些过滤器**确实划分**了整个 CC 集合。

**推导结果**：
- CC 许可占 OA Subset 的 **95.1%**（7,813,394 / 8,219,033）
- **非 CC / 自定义许可残留 ≈ 405,639 条（4.9%）** → 必须排除（无任何机读再利用许可）
- **NC 类合计 = 2,380,218（29.0%）**（BY-NC + BY-NC-ND + BY-NC-SA）→ 全部排除
- ✅ **「可再分发 + 可改作 + 可商用」= CC0 + CC BY + CC BY-SA = 5,421,148 条**（已用合成检索式直接查询确认，非仅算术推导）：
  `("cc0 license"[filter] OR "cc by license"[filter] OR "cc by-sa license"[filter])` → **5,421,148**

### 5.4b 程序化筛选：什么还能用

| 机制 | 状态 | 许可语义 |
|---|---|---|
| OA Web Service `oa.fcgi` | ❌ **已死（404）** | 旧的 per-article `license` + `oa_package` FTP 链接 |
| FTP `oa_file_list.csv` / `.txt` | ❌ **已死（404）** | 旧的 `license` 列 |
| FTP `oa_comm/` `oa_noncomm/` `oa_other/` | ❌ **已移除** | 旧的分目录：`oa_comm`=允许商用，`oa_noncomm`=仅 NC，`oa_other`=其他/无 CC |
| PMC ID Converter | ⚠️ **存活但不含 license** | 已核实字段仅 `PMID/PMCID/ArticleInstanceId/DOI/Version/MID/IsCurrent/IsLive/ReleaseDate/ErrorMessage`；**无 license 字段、无 license 参数** → **不能用于许可过滤** |
| **OAI-PMH** | ✅ 可用 | base `https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`，`set=pmc-open`，`metadataPrefix=oai_dc`，解析 **`<dc:rights>`**；限速 3 rps |
| **S3 Cloud Service JSON** | ✅ 可用（推荐） | bucket `arn:aws:s3:::pmc-oa-opendata`（us-east-1，匿名、`--no-sign-request`），base `https://pmc-oa-opendata.s3.amazonaws.com/`；读 `metadata/PMC<id>.<ver>.json` → `license_code`；日更 S3 Inventory 在 `inventory-reports/pmc-oa-opendata/metadata/`（**完整，无 10k 上限**；ESearch 有 10,000 上限） |
| **E-utilities** | ✅ 可用 | 取代旧的目录级划分。NCBI 明示：「The updated PMC Cloud Service does not separate articles by license category at the directory level.」 |

⚠️ **NCBI 官方推荐的商用检索式对我们的用途是错的**。NCBI 在 <https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/> 推荐：
`((cc0 license[filter] OR cc by license[filter] OR cc by-sa license[filter] OR cc by-nd license[filter]) OR author manuscript[sb]) NOT pmc embargo[filter]`
——它**包含 `cc by-nd`**（禁止改作），也**包含 author manuscript**（TDM 许可，不授予再分发权）。**我们要「再分发 + 改作 + 可商用」，应改用**：

```
("cc0 license"[filter] OR "cc by license"[filter] OR "cc by-sa license"[filter])
  AND "open access"[filter]
  NOT "pmc embargo"[filter]
```
→ **5,421,148 条**（2026-09-12 实测）

**推荐流水线**：
1. 取 PMCID：日更 S3 Inventory（完整）或上面的 eSearch 检索式
2. 取文件：`https://pmc-oa-opendata.s3.amazonaws.com/PMC<id>.<ver>/`（XML/TXT/PDF/media；**批量包已不存在**）
3. **逐版本复核**（不要只信检索式）：读 `metadata/PMC<id>.<ver>.json`，要求 `is_pmc_openaccess=true`、`license_code ∈ {CC0, CC BY, CC BY-SA}`（是否接受 CC BY-SA 的 ShareAlike 需单独决策）、`is_retracted=false`、`is_manuscript=false`
4. 记录逐条溯源信息：PMCID、version、`license_code`、许可 URL、来源 URL、抓取日期
5. 我们自己的内容用 CC BY 4.0 或 CC0 发布；第三方摘录单独标记

⚠️ **COVID-19 陷阱**：<https://ftp.ncbi.nlm.nih.gov/pub/pmc/readme.txt> 指出部分 PMC COVID-19 Collection 文章的再利用条款**已过期**：「the terms allowing for reuse of these articles have expired and downstream users should update their datasets accordingly.」移除清单见 <https://pmc.ncbi.nlm.nih.gov/about/covid-19-faq/#removed>。→ **必须在构建时重新核实许可，不能依赖缓存快照。**

⚠️ **NLM 附加再分发义务**（README.txt §3）：再分发者同意「**only distribute data that are licensed for redistribution**」，并须维护最新版本或**明确告知用户其数据可能不是最新**；**不得使用 PubMed Central 字样或 PMC logo**；不得暗示 NLM/NIH/HHS 背书。

### 5.4c 作者稿件（NIHMS / `TDM`）—— 不授予再分发权

- Article Datasets 页把 **Author Manuscript Dataset** 单列：AAM「made available in PMC under a partner funder's policy」
- 默认许可原文：「This file is available for text mining. It may also be used consistent with the principles of fair use under the copyright law.」
- 「AAMs that include a Creative Commons license are also available via the PMC Open Access Subset」
- JSON 标记：`is_manuscript="yes"`；`license_code='TDM'` 或某个 CC code
- 参考 <https://pmc.ncbi.nlm.nih.gov/about/authorms/> 与 <https://pmc.ncbi.nlm.nih.gov/about/public-access-info/>

🚨 **NCBI 两个官方页面自相矛盾，必须标记**：pmcaws FAQ 称 author manuscript「available for commercial reuse regardless of license」，并把它加进商用检索式；但数据集表与 About Author Manuscripts 页把 `TDM` 描述为**仅文本挖掘 + 合理使用**，不授予任何再分发权。→ **不要把 `TDM` 当作再分发许可。** 若使用 AAM，只用其 `license_code` 为 CC0/CC BY/CC BY-SA 的子集。
| 许可 | 可再分发 | 可改作 | 可商用 | 本评测集可用？ |
|---|---|---|---|---|
| **CC0 1.0**（169,038 条） | ✅ | ✅ | ✅ | ✅ **首选** |
| **CC BY 4.0**（≈5,250,000 条） | ✅ | ✅ | ✅ | ✅ 可用（需署名） |
| **CC BY-SA**（2,110 条） | ✅ | ✅ | ✅ | ⚠️ 可用，但改作须 **ShareAlike** 传染 |
| **CC BY-ND**（11,997 条） | ✅ | ❌ | ✅ | ❌ **不可**（禁改作） |
| CC BY-NC（998,714 条） | ✅ | ✅ | ❌ | ❌ **不可** |
| CC BY-NC-SA（301,897 条） | ✅ | ✅ | ❌ | ❌ **不可** |
| CC BY-NC-ND（1,079,607 条） | ✅ | ❌ | ❌ | ❌ **不可** |
| 非 CC / 自定义（≈405,639 条） | 未知 | 未知 | 未知 | ❌ 默认排除 |
| Author manuscript `TDM`（1,083,887 条） | ❌ | ❌ | ❌ | ❌ **不可**（见 §5.4c） |

> 注意：**旧的 `oa_comm` 目录只保证「可商用」，并不保证「可改作」——因为它包含 CC BY-ND。** 这正是旧流水线容易出错的地方。

### 5.5 ND 与 NC 对我们的实际影响

依据 CC BY-NC-ND 4.0 法律文本 <https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.en>：

- **ND（NoDerivatives）**：
  - §1(1)：「**Adapted Material** means material ... derived from or based upon the Licensed Material and in which the Licensed Material is **translated, altered, arranged, transformed, or otherwise modified**...」
  - §2(a)(1)：授权是「(i) reproduce and Share the Licensed Material, in whole or in part, for NonCommercial purposes only; and (ii) **produce and reproduce, but not Share, Adapted Material**...」
  - §3(a)(1)：「**For the avoidance of doubt, You do not have permission under this Public License to Share Adapted Material.**」
  - §2(a)(4)：「simply making modifications authorized by this Section 2(a)(4) **never produces Adapted Material**」→ **纯格式转换不构成改作**（deed 脚注亦称「Merely changing the format never creates a derivative.」）
  - **落到我们的用例**：
    | 行为 | 是否违反 ND |
    |---|---|
    | 分发改写/派生版本 | ❌ **违反** |
    | 翻译 | ❌ **违反**（"translated" 被 §1(1) 明确点名） |
    | 加注释 / 结构化标注 | ❌ **违反**（构成 Adapted Material） |
    | **逐字摘录** | ✅ **不违反**——§2(a)(1)(i) 授权「in whole or in part」的复制；未修改的摘录是 reproduction 而非 Adapted Material。CC BY-ND 下**即使商用也允许**（须署名）；CC BY-NC-ND 下仅限 NonCommercial |
  - ⇒ **「由论文派生出的题目 + 参考答案」= Adapted Material → ND 论文不可用于公开 QA 对。** 逐字摘录可作题干，但一旦改写/翻译/注释，ND 即封杀分发。
  - 但**事实本身不受版权保护**：从文章提取「用了 GRCh38、N=100、工具是 STAR」这类事实出题通说可行。**边界模糊，建议一律排除 ND 以确保安全。**
- **NC（NonCommercial）**：
  - §1(8)：「**NonCommercial** means not primarily intended for or directed towards commercial advantage or monetary compensation.」
  - CC 官方解释页 <https://wiki.creativecommons.org/wiki/NonCommercial_interpretation> 直接回答了「公司能不能用」：
    - 「**NonCommercial turns on the use, not the identity of the reuser.**」
    - 「**no class of reuser is per se permitted or excluded**」
    - 脚注 4：「any interpretation of NonCommercial that assumes **all uses by for-profit entities are automatically commercial conflicts with the plain language of the definition**」
  - ⇒ **(a)** 一家公司**仅用于自身非商业研究**地使用 NC 题集，**并不自动违反** NC。**(b)** 但**我们**若把 NC 材料以「允许商用」的方式重新发布，就**违反** NC——因为那是「Sharing ... directed towards commercial advantage」，且 §2(a)(5)(B) 禁止附加下游限制。
  - ⇒ 我们要「公开分发、可被第三方（含企业）引用」，**NC 材料一律排除**。
  - 参考：<https://creativecommons.org/faq/>（NC/ND 条目 anchor 已确认存在，正文因页面超长未被 fetcher 取回，见 §12）；<https://creativecommons.org/licenses/by-nc-nd/4.0/>
- **实操结论**：PMC 题**只允许 CC0 / CC BY / （可选）CC BY-SA 三个桶**。

### 5.6 关于 BioProBench 的教训

用户提到 BioProBench 是 CC BY-NC-ND 4.0、523,784 条中仅 350,565 条可发布。**本报告未独立核实该论文的具体数字与许可**（无法核实，见 §12）。但该案例的结构性教训是成立的、且与本报告结论一致：
1. **聚合型数据集的总许可 = 最严子集的许可**。上游逐条不同时，整包只能按最严处理，或必须做子集切分并逐条记录许可来源。
2. **必须在第 1 天就做许可分桶（license bucketing），并让每一条样本携带 `source_license` 字段**，否则后期无法切分。
3. **ND 与 NC 是两种不同的封锁机制**：ND 封「改作」（题目改写），NC 封「商用」（企业用户）。BioProBench 同时踩了两个。

### 5.7 结论

| 项 | 结论 |
|---|---|
| 许可 | **无统一许可**，逐条不同（CC0 / CC BY / CC BY-SA / CC BY-ND / CC BY-NC / CC BY-NC-SA / CC BY-NC-ND / 非 CC 自定义 / TDM） |
| 可再分发 | 仅 CC0、CC BY（及可选的 CC BY-SA）✅；其余 ❌ |
| 可商用 | 同上 |
| 人类数据限制 | 文章级；不涉及 dbGaP 受控数据，但正文可能含可识别个案信息，需逐条注意 |
| **结论** | **仅脚本 / 或仅使用 CC0+CC BY（±CC BY-SA）子集**；且**必须放弃 FTP 流水线**，改为 **S3 Cloud Service（读 `metadata/PMC<id>.<ver>.json` 的 `license_code`）** 或 OAI-PMH `<dc:rights>` + 逐条复核 |

---

## 6. Cuatro Ciénegas 宏基因组数据集

### 6.1 结论（修正后的判断）

**许可层面：干净可用 ✅ —— 环境样本、无人类数据、NCBI 无再分发限制、关联论文为 CC BY。**
**真值层面：不存在 ✅ 的物种组成真值 ❌ —— 这是本题的真正障碍，不是许可。**

⇒ **建议：不要用 Cuatro Ciénegas 出「物种组成准确度」题**（天然群落没有已知真值）；若要保留宏基因组题型，**改用 CAMI2 模拟数据集**（有官方 gold standard，见 §8.3）。Cuatro Ciénegas 最多只能出「流程复现 / MAG 组装流程」题，且必须在 DATACARD 中说明「无组成真值」。

### 6.2 候选数据集与已验证的 Data Availability 原文

**首选 A1（最干净：现代 MAG 级、CC BY 4.0、DA 明确、accession 已验证）**
- Rodríguez-Cruz UE, Castelán-Sánchez HG, Madrigal-Trejo D, Eguiarte LE, Souza V. *Uncovering novel bacterial and archaeal diversity: genomic insights from metagenome-assembled genomes in Cuatro Ciénegas, Coahuila.* **Front Microbiol 2024;15:1369263**，DOI [10.3389/fmicb.2024.1369263](https://doi.org/10.3389/fmicb.2024.1369263) · PMC11169877 · PMID 38873164
- **文章许可 = CC BY 4.0**（JATS `<license xlink:href="http://creativecommons.org/licenses/by/4.0/">`；「This is an open-access article distributed under the terms of the Creative Commons Attribution License (CC BY).」）
- **Data Availability 原文（逐字）**：「The data presented in the study are deposited in the NCBI repository, in the bioproject number **PRJNA847603**.」
  （来源：<https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2024.1369263/xml/nlm>，`sec-type="data-availability"`）
- **PRJNA847603 已验证**（<https://www.ncbi.nlm.nih.gov/bioproject/PRJNA847603>）：「Cuatro Cienegas Basin, Archaean Domes」；Data Type: Genome sequencing；**Scope: Environment**；Organism: *hypersaline lake metagenome*（TaxID 904678）；Submitter: Instituto de Ecología (UNAM)；注册 2022-06-09；22 个 SRA experiments、1057 BioSamples、5952 protein sequences

**次选 A2（独立采样点、16S、CC BY 4.0、DA 指明两个库）**
- García-Ulloa M II 等，*Recent Differentiation of Aquatic Bacterial Communities in a Hydrological System in the Cuatro Ciénegas Basin, After a Natural Perturbation*，**Front Microbiol 2022;13:825167**，DOI [10.3389/fmicb.2022.825167](https://doi.org/10.3389/fmicb.2022.825167) · PMC9097865
- 许可 **CC BY 4.0**（同上 JATS 元素）
- **DA 原文（逐字）**：「The datasets presented in this study can be found in online repositories. The names of the repository/repositories and accession numbers can be found below: **NCBI:PRJNA785576, MG-RAST:mgp94066**.」
- **PRJNA785576 已验证**（<https://www.ncbi.nlm.nih.gov/bioproject/PRJNA785576>）：Raw sequence reads；Scope: Multispecies；UNAM；2021-12-02；9 SRA experiments；301 Mbases
- ⚠️ **MG-RAST `mgp94066` 未核实**（未打开 <https://www.mg-rast.org/> 确认记录与条款）

**A3（许可证对照样本，故意用来演示陷阱）**
- Rodriguez-Cruz UE, Ochoa-Sánchez M, Eguiarte LE, Souza V. *Running against the clock...* **FEMS Microbiol Ecol 2025;101(5):fiaf033**，DOI [10.1093/femsec/fiaf033](https://doi.org/10.1093/femsec/fiaf033) · PMC11995699
- **许可 = CC BY-NC-ND**（Europe PMC core 记录 `"license":"cc by-nc-nd"`，<https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:40205473&format=json&resultType=core>）
- 数据 = **同一个 PRJNA847603** → **同一批数据，换一篇论文就从 CC BY 变成 CC BY-NC-ND。** 这正是「文章许可 ≠ 数据许可」的活教材，务必写进 DATACARD 培训材料。

**A4/A5/A6 = 不建议作为主数据源（作为「常被引用但权利链糟糕」的反例）**
- Peimbert M 等 2012，*Astrobiology* 12(7):648–658，DOI [10.1089/ast.2011.0694](https://doi.org/10.1089/ast.2011.0694) · PMC3426886 —— **无 Data Availability 章节**（2012 年，早于强制要求），只在方法里给 **MG-RAST ID**（`4442466.3`、`GS001a` 等），**无 BioProject/SRA/ENA/JGI accession**；文章许可**无法核实**（<https://pmc.ncbi.nlm.nih.gov/articles/PMC3426886/>）
- Souza V 等 2018，*eLife* 7:e38278，DOI [10.7554/eLife.38278](https://doi.org/10.7554/eLife.38278) —— 许可 **CC BY 4.0**（原文：「This article is distributed under the terms of the Creative Commons Attribution License, which permits unrestricted use and redistribution provided that the original author and source are credited.」），**但其自身原始 reads 的 DA/accession 无法核实**（抓取的 JATS XML 中未找到 `sec-type="data-availability"`，且抓取被截断）→ **不要用它做数据源**
- Desnues C 等 2008，*Nature* 452:340–343，DOI [10.1038/nature06735](https://doi.org/10.1038/nature06735) —— **许可与数据托管地均无法核实**（<https://www.nature.com/articles/nature06735> 返回 HTTP 403 / 跳转 idp.nature.com）；历史上托管于已停运的 CAMERA → **未核实，不得当作事实引用**

### 6.3 其他已验证的 CCB BioProject（供 DATACARD 的 data availability 段落使用）

| BioProject | 描述 | Scope | 提交方 | SRA |
|---|---|---|---|---|
| [PRJNA847603](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA847603) | Cuatro Cienegas Basin, Archaean Domes | Environment | hypersaline lake metagenome · UNAM | 22 |
| [PRJNA785576](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA785576) | Pozas Rojas 群落分化 | Multispecies | UNAM | 9 |
| [PRJNA971342](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA971342) | Archaean Domes 微生物席时间序列 | Environment | microbial mat metagenome · UNAM | 18（3 Gbases） |
| [PRJNA1003106](https://www.ncbi.nlm.nih.gov/bioproject/1003106) | 高盐微生物席 | Multispecies | Inst. Ecología | Genome seq. |
| [PRJNA1225699](https://www.ncbi.nlm.nih.gov/bioproject/1225699) | Blue Pond / Archaean Domes 多样性 | Multispecies | CINVESTAV Irapuato | Raw reads |
| [PRJNA337738](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA337738) | Microbialite layer 1（JGI Gp0051548 / BE671） | Environment | freshwater metagenome · **DOE JGI**，2016-08-04 | **「No public data is linked to this project.」** |

### 6.4 文章许可 vs 数据库条款（关键区分，务必写进 DATACARD）

**结论：数据库自身条款说了算，文章 CC BY 不覆盖第三方 accession 记录。**

1. **Frontiers 的 CC BY 文本只说 "this article"**：「The use, distribution or reproduction in other forums is permitted…」—— **完全没有**说 SRA runs 被重新许可。
2. **NCBI 政策刻意「不授权」**（<https://www.ncbi.nlm.nih.gov/home/about/policies/>）：
   > 「Information that is created by or for the US government on this site is within the public domain.」
   > 「**NCBI itself places no restrictions on the use or distribution of the data contained therein.** Nor do we accept data when the submitter has requested restrictions on reuse or redistribution.」
   > ⚠️「some submitters of the original data (or the country of origin of such data) may claim patent, copyright, or other intellectual property rights ... **NCBI cannot provide comment or unrestricted permission concerning the use, copying, or distribution of the information contained in the molecular databases.**」
3. **EMBL-EBI 同构**（<https://www.ebi.ac.uk/about/terms-of-use/>）：
   > 「**EMBL-EBI itself places no additional restrictions on the use or redistribution of the data available via its Data Resources and Tools** other than those provided by the original data owners, unless otherwise specified in these Terms of Use.」
   并明确提示用户须自行注意第三方权利，**包括「biodiversity-related access and benefit-sharing rights」**。
   ⚠️ 这一条**直接适用于 Cuatro Ciénegas**：采样地在墨西哥 **Rancho Pozas Azules（PRONATURA Noroeste）**，受墨西哥联邦许可约束（A1 的 XML 中引用了 SEMARNAT 许可号 SGPA/DGVS/03121/15）。**这是「生物多样性获取与惠益分享」问题，不是人类数据问题**，但仍是需要尊重的第三方权利。
4. **JGI 是决定性反例**（<https://jgi.doe.gov/data-policy-support/data-policy>）：JGI **不使用开放许可**，而使用禁运/使用限制：
   > 「For sequencing or metabolomics projects: data are subject to a **one-year embargo**.」
   > 「At the end of the embargo period data will be made publicly available ... and **are unrestricted for use**.」
   > 遗留条款（**FY22 之前**受理的提案，覆盖 PRJNA337738/2016）：有 **两年使用限制期**，期间第三方若「wish to include use-restricted data in publications, or who wish to **redistribute data in any way** are required to **contact the proposal PI and receive permission**」。
   → **PRJNA337738 因此不可用**（且当前无公开关联数据）。
5. **BMC/Springer 的正面反例**：当出版方**确实**想扩展数据许可时，会**单独、明确**地写出来。例如 Li et al. 2021（*Micrococcus luteus* 比较基因组学，BMC Genomics 22:124，DOI [10.1186/s12864-021-07432-5](https://doi.org/10.1186/s12864-021-07432-5)，CC BY 4.0）的许可段：
   > 「**The Creative Commons Public Domain Dedication waiver (http://creativecommons.org/publicdomain/zero/1.0/) applies to the data made available in this article, unless otherwise stated in a credit line to the data.**」
   —— 注意它说的是「**本文中提供的数据**」，仍**没有**声称能重新许可第三方 GenBank 记录。
6. **给我们的操作性规则**：
   > **文章 CC BY ⇒ 可复用文章正文/图/补充材料（须署名）。它不会升级 SRA/ENA/IMG/MG-RAST 对象的权利状态；每个库的条款须单独核查。**
   对 CCB 各候选：NCBI 对象 → NCBI 无限制但**不担保权利**；JGI 对象（PRJNA337738/Gp0051548）→ 禁运/使用限制制，且该项目当前无公开数据。

### 6.5 是否人类数据？—— 已确认**不是**（5 个 CCB 项目全部）

从 BioProject 记录本身核实：PRJNA847603（**Scope: Environment**，hypersaline lake metagenome）、PRJNA971342（**Environment**，microbial mat metagenome）、PRJNA337738（**Environment**，freshwater metagenome）、PRJNA785576（Multispecies，微生物生态，无人类宿主元数据）、PRJNA1003106 / PRJNA1225699（环境高盐微生物席/池塘）。

→ **无人类基因组数据、无 dbGaP/EGA 受控访问成分、无 IRB/同意依赖。**

### 6.6 结论表

| 项 | 结论 |
|---|---|
| 许可 | 关联论文 CC BY 4.0（A1/A2）；**数据本身**受 NCBI 政策（无限制但无担保）+ 墨西哥生物多样性许可约束 |
| 可再分发 | ✅ 我们**可以**打包 NCBI 记录；但**不建议**（体积数十~数百 GB）→ 只发脚本+accession |
| 可商用 | ✅ NCBI 无 NC 限制 |
| 人类数据限制 | ❌ 无（环境样本） |
| **真值** | ❌ **无物种组成真值**（天然群落）→ **不能出「组成准确度」题** |
| **结论** | **仅脚本 + accession + 流程复现题**；组成/物种丰度题**替换为 CAMI2**（§8.3） |

---

## 7. Micrococcus 直系同源聚类真值

### 7.1 结论

> # ❌ 应放弃该题。

**不存在任何权威、公开、可许可的 Micrococcus 直系同源聚类真值。** 理由（逐条有据）：

1. **没有这样的真值集被发表。** 检索 *Micrococcus* × {ortholog, orthologous groups, COG, eggNOG, OrthoDB, KEGG Orthology, pangenome, benchmark, truth set}，**未找到任何为该属专门构建的策展型直系同源基准**。唯一规模相近的工作（Li et al. 2021，BMC Genomics，106 个 *Micrococcus* 基因组、174 个重组自由单拷贝核心基因、eggNOG 注释）本身是**聚类工具的输出**，不是真值。
2. **拿 OrthoDB / eggNOG / OMA / COG 当「真值」是循环论证** —— 它们是直系同源推断流水线的**预测**。用它们评分只是衡量「与某条流水线的一致性」，不是正确性。**QfO 官方文档自己就承认这一点**（<https://orthology.benchmarkservice.org/proxy/doc>，原文）：
   > 「**Orthology is a property for which it is very difficult to establish a ground truth dataset. We therefore use surrogate measures to assess the quality of predictions.**」
3. **连 QfO 都对比不了**：QfO 参考蛋白质组 2025_04 共 **81 个物种**（<https://www.ebi.ac.uk/reference_proteomes/>），**不含 Micrococcus**。→ 无法提交预测、无法获得社区可比的分数。
4. **两个最强候选在法律上不可用**：
   - **KEGG**（<https://www.kegg.jp/kegg/legal.html>，Last updated: October 1, 2024）原文：
     > 「**KEGG** is an original database product, copyright Kanehisa Laboratories.」
     > 「Academic users may freely use the KEGG website... Academic users who utilize KEGG for providing services are requested to obtain an academic service provider license」
     > 「**Non-academic users must understand that KEGG is not a public database, nor is it a publicly funded database. Non-academic use of KEGG requires a commercial license.**」
   - **BUSCO 数据集 = CC BY-ND 4.0**（<https://busco.ezlab.org/>）原文：
     > 「The BUSCO software is licensed under the **MIT License**. The BUSCO datasets are licensed under the **Creative Commons Attribution-NoDerivatives 4.0 International License**...」
     → **BY-ND 禁止分发改作版本** → 我们不能随题集发布任何 BUSCO 派生的基准数据。且 BUSCO 本质是**完整性 QC 启发式**，不是真值。
5. **COG 是美国政府公有领域，但不是 Micrococcus 真值集**，其 Micrococcus 覆盖**无法核实**（<https://www.ncbi.nlm.nih.gov/research/cog/>），且 NCBI 明确**不担保**提交者不主张权利。

⇒ 任何我们可能出出来的「Micrococcus 直系同源真值」，只能是 **(a) 编造的、(b) 把单一方法输出标为真值的、(c) 权利受限的** —— 三者对声称「权威」的评测集都是否决项。

### 7.2 若坚持要出直系同源题，可辩护的替代方案（按强度排序）

1. **【最强】换到 QfO 参考蛋白质组中的物种。** 用 QfO 基准服务对参考集的**细菌子集**评测（建议 *Streptomyces coelicolor* 与 *Mycobacterium tuberculosis* —— **同为放线菌门，与 Micrococcus 生物学接近**），使用**官方 surrogate 基准**（物种树不一致度；与参考基因系统发育的一致性，如 SwissTree）。
   - 服务入口：<https://orthology.benchmarkservice.org/>，文档 <https://orthology.benchmarkservice.org/proxy/doc>（「This website is free and open to all users and there is no login requirement.」；「This service is free for all users.」）
   - 代码许可 = **MPL 2.0**（<https://raw.githubusercontent.com/qfo/benchmark-webservice/master/LICENSE>：「licensed under the Mozilla Public License Version 2.0 … open source and **free for commercial and non-commercial use**」）
   - 引用：Altenhoff et al. Nat Methods 2016, DOI [10.1038/nmeth.3830](https://doi.org/10.1038/nmeth.3830)；Nevers et al. NAR 2022, DOI [10.1093/nar/gkac330](https://doi.org/10.1093/nar/gkac330)
   - **优点**：得到的是**社区标准的开放评测协议**，而不是伪造的真值集
2. **或者：用 OrthoDB 构建「参考预测」基准，并诚实标注。**
   - OrthoDB 许可 = **CC BY 4.0**（<https://www.orthodb.org/static/pages/disclaimer.html> 原文：「Unless otherwise stated, the data provided from this website by E Zdobnov lab is licensed under a **Creative Commons Attribution 4.0 (CC-BY-4.0)**.」）
   - OrthoDB **确实覆盖 Micrococcus**（已验证 API：<https://data.orthodb.org/v12/species?clade=1268> 返回 *M. luteus* DE0384 (`1270_0`)、*M. luteus* DE0113 (`1270_1`)、*M. flavus* BCRC 80069 (`384602_0`)、*M. lylae* BCRC 12151 (`1273_0`)、*M. terreus* CGMCC 1.7054 (`574650_0`)、*Micrococcus* sp. CH7 (`1770210_0`)）
   - **必须写明的两条警告**：① OrthoDB 自己声明「The underlying sequences and annotations may be subject to third-party constraints. Users of the data are solely responsible for establishing the nature of and complying with any such intellectual property restrictions.」② 用户指南声明「there is no guaranteed inheritance of gene or OG identifiers between past and next releases」（<https://www.ezlab.org/orthodb_v12_userguide.html>）→ **必须锁 release 版本并落盘校验和**
   - **措辞要求**：只能叫「OrthoDB v12.2 的参考直系同源赋值」，**绝不能叫 ground truth**
3. **或者：换成有真值的任务类别** —— 例如 QfO 托管的策展参考基因系统发育（SwissTree）测试，或 GO/EC 保守性基准（参考注释是独立策展的，不是直系同源工具推断的）。
4. **若务必用 Micrococcus** —— 唯一诚实的框架是**可复现性题**：「用 76 个公开基因组复现 Li et al. 2021 的 174 个单拷贝核心基因 / eggNOG 注释」，引用 CC BY 4.0 论文与 Table S1 的 GenBank accession 列表。明确写「复现已发表流水线」，不是「恢复真值」。

### 7.3 其他资源许可（供交叉参考）

| 资源 | 许可 | 来源 |
|---|---|---|
| **OrthoDB** | **CC BY 4.0** | <https://www.orthodb.org/static/pages/disclaimer.html> |
| **OMA** | **CC BY 4.0**（standalone 软件 MPL 2.0） | <https://omabrowser.org/oma/terms_of_use/> |
| **QfO benchmark service（代码）** | **MPL 2.0** | <https://raw.githubusercontent.com/qfo/benchmark-webservice/master/LICENSE> |
| **COG / NCBI** | 美国政府公有领域 | <https://www.ncbi.nlm.nih.gov/home/about/policies/> |
| **eggNOG 数据库** | **无独立许可声明**（站点无 terms 页）；受 EMBL-EBI ToU 约束；**论文** CC BY | <https://www.ebi.ac.uk/about/terms-of-use/>；论文 DOI [10.1093/nar/gky1085](https://doi.org/10.1093/nar/gky1085) |
| **eggnog-mapper 软件** | **GPLv3** | <https://raw.githubusercontent.com/eggnogdb/eggnog-mapper/master/setup.cfg>（`license = GPLv3`） |
| **KEGG** | **商业许可（非公有）** | <https://www.kegg.jp/kegg/legal.html> |
| **BUSCO 软件 / 数据集** | **MIT / CC BY-ND 4.0** | <https://busco.ezlab.org/> |
| **OMA 是否覆盖 Micrococcus** | **无法核实**（API 404） | <https://omabrowser.org/api/docs/> |

---

## 8. 推荐的替代数据集（许可干净 / CPU 可跑 / 体积小）

以下三项均已亲自核实许可原文。

### 8.1 wwPDB / RCSB PDB —— **CC0 1.0**（最干净）

**条款原文**（<https://www.wwpdb.org/about/usage-policies>，2026-09 可访问）：

> 「Data files contained in the PDB archive are available under the **CC0 1.0 Universal (CC0 1.0) Public Domain Dedication**. Users of PDB data are encouraged to attribute the original authors of the PDB structure data where possible. wwPDB makes no warranties about the work, and disclaims liability for all uses of the work, to the fullest extent permitted by applicable law.」

- **许可**：CC0 1.0（公有领域奉献）→ 再分发 ✅、改作 ✅、商用 ✅、**无需署名**
- **体积**：单条目 mmCIF/PDB 文件几十 KB ~ 几 MB，可整包进仓库
- **CPU 可跑**：✅ 纯解析/几何计算，秒级
- **真值权威性**：**✅ 高**——PDB 条目自带实验方法、分辨率、R-free、验证报告（wwPDB Validation Report），且几何量（键长/键角/二面角、Ramachandran 离群率）可由**确定性重算**得到，天然可作真值
- **可出的题**：mmCIF 解析与坐标提取、配体/链筛选、Ramachandran 统计复现、分辨率/验证指标检索、结构比对预处理
- **污染风险**：低-中。具体条目 ID 与数值可能被记住，但**程序化生成的子集 + 从原始 mmCIF 重算**可有效防污染

### 8.2 Gene Ontology（GO）—— **CC BY 4.0**

**条款原文**（<https://geneontology.org/docs/go-citation-policy/>，2026-09 可访问）：

> 「**License** — Gene Ontology Consortium data and data products are licensed under the **Creative Commons Attribution 4.0 Unported License**.」
> 署名要求（引 CC BY 4.0 §3(a)）：「identification of the creator(s)…; a copyright notice; a notice that refers to this Public License; a notice that refers to the disclaimer of warranties; a URI or hyperlink to the Licensed Material」

并给出可复制的署名模板：
> 「[Gene Ontology](https://geneontology.org) data from the [2024-01-17 release](http://release.geneontology.org/2024-01-17) ([DOI:10.5281/zenodo.10536401](https://doi.org/10.5281/zenodo.10536401)) is made available under the terms of the [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/legalcode).」

- **许可**：CC BY 4.0 → 再分发 ✅、改作 ✅、商用 ✅（须署名 + 注明 release 日期）
- **体积**：`go-basic.obo` 约 30 MB；GAF 注释文件按物种切分可很小
- **CPU 可跑**：✅ 图遍历/富集统计，秒~分钟级
- **真值权威性**：✅ **高**——GO 本体是策展权威本体；术语层级关系（is_a/part_of）是**权威真值**，可用于「给定 GO ID 列表，计算最具体共同祖先 / 富集分析」这类题
- **可出的题**：OBO 解析、DAG 祖先/后代查询、IC 值计算、GO 富集分析复现
- **污染风险**：中——GO 本体已广泛进入训练语料；但**层级查询的答案可由本体文件确定性重算**，且可随机抽样术语，污染影响小

### 8.3 CAMI2 toy datasets —— **CC BY 4.0**（宏基因组题的替代）

**已核实**：CAMI2 toy 派生真值包（BinBencher reference）Zenodo 记录 `10.5281/zenodo.15083711`，其 DataCite 元数据 `"license": {"id": "cc-by-4.0"}`（实测 <https://zenodo.org/api/records/15083711>，2026-09）。CAMI2 原始数据集位于 <https://frl.publisso.de/data/frl:6425518/>，含 `README.md`、`airskinurogenital/`、`gastrooral/`、`per_bodysite/`、`md5sums.tsv`，附 **gold standard assembly / 物种组成真值**。

- **许可**：Zenodo 记录为 **CC BY 4.0**；CAMI2 原始数据（publisso/FRL）**许可字段未能在 2026-09 读出**（目录列表页与 README.md 均因 MIME 类型被 fetcher 拒绝）→ ⚠️ **部分无法核实**，见 §12
- **真值权威性**：✅ **高**——CAMI 是社区公认的宏基因组评测挑战，真值是**模拟生成时构造的**，权威且精确
- **CPU 可跑**：✅（Kraken2/MetaPhlAn 均 CPU 可跑）；⚠️ 体积需注意——toy 数据集仍是数十 GB 量级，建议**只取 `per_bodysite/` 或单个 body site 的子集 + 自带 gold standard**
- **污染风险**：低（模拟数据，非自然样本）
- **相比 Cuatro Ciénegas 的优势**：真值明确、有官方 gold standard、许可明确（CC BY 4.0）、可复现

**备选（未逐一核实，附核实入口）**：
| 数据集 | 预期许可 | 核实入口 |
|---|---|---|
| UniProtKB / Swiss-Prot | CC BY 4.0（**未能读到全文**） | <https://www.uniprot.org/help/license> |
| Ensembl | 「无限制」（需核实） | <https://www.ensembl.org/info/about/legal/disclaimer.html> |
| NCBI RefSeq / NCBI Datasets（如 E. coli K-12） | 美国政府作品 | <https://www.nlm.nih.gov/web_policies.html> |
| Zebrafish/Drosophila 小基因组（Ensembl） | 随 Ensembl | 同上 |

---

## 9. SRA / ENA 序列数据再分发限制（单独说明）

> ⚠️ **本次调研推翻了任务简报中的前提。** 简报假设「ENA 通常较宽松，SRA 较严」。**这个差异作为「许可政策」差异并不存在 —— 两者同受 INSDC 统一政策约束，条款是对称的。** 真正的差异是**运营性**与**基础设施性**的。详见 §9.2。

### 9.1 决定性条款：INSDC（同时约束 SRA、ENA、DDBJ）

**INSDC "Nucleotide Sequence Database Policies"（2002, Science 298:1333）** —— <https://www.insdc.org/nucleotide-sequence-database-policies-2002/>。第 2 条是本报告最直接命中的条款：

> 「2. The INSDC will not attach statements to records that restrict access to the data, limit the use of the information in these records, or prohibit certain types of publications based on these records. Specifically, **no use restrictions or licensing requirements will be included in any sequence data records, and no restrictions or licensing fees will be placed on the redistribution or use of the database by any party.**」

> 「1. The INSDC has a **uniform policy of free and unrestricted access** to all of the data records their databases contain. Scientists worldwide can access these records to plan experiments or publish any analysis or critique. Appropriate credit is given by citing the original submission…」
> 「3. All database records submitted to the INSDC will remain permanently accessible as part of the scientific record…」
> 「4. Submitters are advised that the information displayed on the Web sites maintained by the INSDC is fully disclosed to the public. **It is the responsibility of the submitters to ascertain that they have the right to submit the data.**」

（同五点由 ENA 复述：<https://ena-browser-docs.readthedocs.io/en/latest/about/policies.html>）

**INSDC 现行自述** —— <https://www.insdc.org/about-insdc/>：
> 「INSDC Members exchange data and make exchanged data **freely accessible without restrictive licensing** as part of the scientific record, including all corrections and updates.」
> 「**INSDC does not accept submissions of human or other species' genomic data that require controlled-access.**」
> 「If submitting genomic data with risk of human read contamination, such as from human metagenomic or clinical pathogen studies, you are also responsible for screening and removal of contaminating human sequences…」
> 「If you plan to submit human data to any of INSDC repositories, please assume explicit responsibility for: (1) Adhering to informed consent, (2) Protecting research participants' privacy, and as appropriate, (3) Ensuring that the submission meets all regulations.」
> 成员承诺：「**Provision of free and unrestricted access to INSDC data resources and services to members of the public**」

### 9.1b SRA 侧（NCBI / NLM）

**NLM GenBank and SRA Data Processing** —— <https://www.ncbi.nlm.nih.gov/sra/docs/sequence-data-processing/>，**这是最有利于我们的条款**：
> 「**Public sequence data made available by NCBI may be retrieved and redistributed by other users and presented in other websites, databases, tools, publications, curricula, conference proceedings, or other venues that are not managed by NCBI.** These other resources present a snapshot from the time of retrieval and may not contain the most recent updates or changes to status.」
> 「**Public**: Public data are fully accessible for search and distribution.」
> 「**Withdrawn**: Withdrawn data are data that were previously public, have been removed from the NCBI text-based search and comparative analysis results, and cannot be accessed by the public even by accession number.」
> 「Because public sequence data made available by NCBI may be retrieved and redistributed by other users …, **data that are suppressed or withdrawn may remain available through other sources that are not managed by NCBI.**」
> 「(INSDC members do not exchange sensitive controlled access human sequence data)」

**SRA in the Cloud** —— <https://www.ncbi.nlm.nih.gov/sra/docs/sra-cloud/>：
> 「All publicly-available, unassembled read data and authorized-access human data are available for access and compute through these cloud providers.」
> 「**Unlimited concurrent downloads from our cloud buckets to your buckets**」

**SRA 侧**：NCBI 政策（<https://www.ncbi.nlm.nih.gov/home/about/policies/>）同时给出「不限制使用与再分发」与「**我们不在提交者要求限制再利用或再分发时接收数据**」（"Nor do we accept data when the submitter has requested restrictions on reuse or redistribution."），以及「there is no transfer of rights from submitters to NCBI, NCBI has no rights to transfer to a third party」。

⚠️ **不存在 SRA 专属的 "Data Usage Policies" 页面**：`https://www.ncbi.nlm.nih.gov/sra/docs/sra-data-usage/` 返回 **HTTP 404**。已遍历 SRA 文档树全部条目（Getting Started、Submission Quick Start、Search and Download、SRA in the Cloud、Data Storage Model、RCA、Data Submission Standards、File Format Guide、Metadata Overview、File Upload、FAQ、Submitting to SRA、Troubleshooting、Submitting for dbGaP、Submitting for GEO、Updating SRA data、Request status change、Change Release Date）。**SRA 的「数据使用政策」就是 NCBI 全域政策。**

**SRA 唯一可用的限制手段**：(i) 发布前的**保密窗口**（提交者指定 release date）；(ii) 把受控访问人类数据**路由到 dbGaP**。发布后移除**不能收回已分发的副本**。

### 9.2 ENA 侧（EMBL-EBI）与「ENA 比 SRA 更宽松」的证伪

**ENA 的条款就是 EMBL-EBI Terms of Use。** <https://www.ebi.ac.uk/ena/browser/about> 与 `/terms` 只渲染 JS shell，但 shell 本身指向 <https://www.ebi.ac.uk/about/terms-of-use>（"Last revised: 5th February 2024"）：

> General 1：「EMBL-EBI promotes open science through its mission to provide **freely available** Data Resources and Tools … Where EMBL-EBI presents scientific data generated by others, **EMBL-EBI imposes no additional restriction on the use of the contributed data than those provided by the data owner**, unless otherwise specified in these Terms of Use.」
> General 2：「EMBL-EBI expects attribution … in accordance with good scientific practice.」
> General 4：「All scientific data will be made available by a time and release mechanism consistent with the data type (e.g. human data where access needs to be reviewed by a **Data Access Committee**, pre-publication embargoed for a specific time period).」
> Data 1：「The Data Resources and Tools hosted by EMBL-EBI are generated in part from data contributed by the community **who remain the data owners**.」
> **Data 3：「EMBL-EBI itself places no additional restrictions on the use or redistribution of the data available via its Data Resources and Tools other than those provided by the original data owners, unless otherwise specified in these Terms of Use.」**
> Data 4：「The original data may be subject to rights claimed by third parties… **For the specific case of the EGA database and human data consented for biomedical research, these rights may be formalised in Data Access Agreements.** It is the responsibility of users … to ensure that their exploitation of the data does not infringe any of the rights of such third parties.」
> **DRT 1（镜像的关键约束）：「Users of EMBL-EBI Data Resources and Tools agree not to attempt to use any EMBL-EBI computers, files or networks apart from through the service interfaces provided.」**
> DRT 4：「Any attempt to use EMBL-EBI Data Resources and Tools to a level that prevents, or is likely to prevent, EMBL-EBI providing services to others, will result in the user being blocked.」
> DRT 9：「The Data, Resources and Tools are provided by EMBL-EBI 'AS IS' without warranties of any kind.」

**EMBL-EBI 许可路线图** —— <https://www.ebi.ac.uk/licencing>：
> 「**The majority of EMBL-EBI data resources use the institute's Terms of Use**…」
> 「EMBL-EBI will minimise barriers to reuse of data … by adopting the Creative Commons (CC) license framework across all its data resources in the next 5 years.」
> 「**CC0 is preferred over CC-BY.** CC0 is most in line with the spirit of the EMBL-EBI Terms of Use.」——「It is the best way to encourage remixing and reuse as it makes clear to any user – **academic, commercial or otherwise** – that the data are not owned by anyone and therefore can be used freely.」
> 「of the 41 EMBL-EBI-hosted resources analysed: 68% … primarily Terms of Use-based or CC0 licensing; 22% use CC-BY licensing」
> 「for example, **BioStudies** and BioImage Archive make many datasets available under the Terms of Use, but apply **per-dataset CC0 or CC-BY licensing** where this is the wish of the data owner.」
> ⚠️ **「Between 2021 and 2024, … three resources retired and were consolidated into other databases (**ArrayExpress**, Enzyme Portal, IntEnz).」**
> → **重要**：**ArrayExpress 已退役/合并入 BioStudies**。GEUVADIS 的 `E-GEUV-1` 现在必须通过 **BioStudies** 或 **Expression Atlas** 访问（我们前面用的正是 BioStudies API，可行）。

**ENA release policy** —— <https://ena-docs.readthedocs.io/en/latest/faq/release.html>：
> 「Unfortunately, ENA does not support making only part of a submission available or restricting access to selected users. **ENA's policy is that submissions must be made available in full and be accessible to all users.**」
> 「**Already public** — **ENA's policy is that data released into the public domain should remain public.** … Note that **data which are public for even a short time may already have been mirrored to the other INSDC partners or picked up by downstream services that ENA does not control.**」
> 「Note that suppression and withdrawal remove data from ENA, but **cannot recall copies already distributed to the INSDC partners or downstream services**.」

**ENA / INSDC policies 页** —— <https://ena-browser-docs.readthedocs.io/en/latest/about/policies.html>：
> 「In any case where the data has been distributed as public, **the INSDC partners cannot exercise any control on the resultant use of the data by third parties**, even if it is subsequently removed from the service.」
> ⚠️ **镜像持久性警告（对我方影响重大）**：「…**we have never committed to preserving these submitted files** and will, in due course, cease to sustain their storage.」

**ENA 主动支持 bulk 下载** —— <https://ena-docs.readthedocs.io/en/latest/retrieval/file-download.html>：
> 「**Providing users with the ability to download submitted data for further analysis purposes is a key part of ENA's mission. Files are therefore made available through a public FTP server.**」
> 官方认可通道：ENA File Downloader (CLI)、ENA FTP Downloader (GUI)、Globus、enaBrowserTools、wget、curl、FTP、Aspera。

**⇒ 「ENA 比 SRA 对 bulk 再分发/镜像更宽松」——证伪。** 两者同受 INSDC 统一政策约束，条款对称（INSDC：「no restrictions or licensing fees … on the redistribution or use of the database by any party」；SRA：「may be retrieved and redistributed by other users」；EBI：「no additional restrictions on the use or redistribution」）。

**真正的差异（镜像方案应据此调整）：**

| 维度 | SRA/NCBI | ENA/EMBL-EBI | 谁更有利 |
|---|---|---|---|
| **云端镜像** | 公开数据托管于 AWS/GCP，提供原始提交文件，明示「**Unlimited concurrent downloads from our cloud buckets to your buckets**」 | bulk 通道是 FTP/Aspera/Globus，打在 EBI 服务器上 | **SRA 更宽松**（与简报假设相反） |
| **运营约束** | 脚本礼仪：≤3 请求/秒、>100 请求避开高峰、用 `email`/`tool` 参数 | **更明确**：DRT 1「不得绕过服务接口使用其计算机/文件/网络」；DRT 4 过量使用会被封禁 | SRA 稍宽 |
| **文件持久性** | 无原始文件永久保存承诺 | 明示「**never committed to preserving these submitted files**」 | **SRA 更适合镜像** |
| **未来许可清晰度** | — | EBI 正迁向资源级 CC0（68% ToU/CC0，22% CC-BY），但 **ENA 本身尚未被列为 CC0** | 目前无文本依据说 ENA 更优 |

### 9.3 人类序列数据（这是关键）

**受控访问要求已在 INSDC 层面确认**（最强的一手文本）：
- <https://www.insdc.org/about-insdc/>：「**INSDC does not accept submissions of human or other species' genomic data that require controlled-access.**」
- <https://www.insdc.org/submitting-standards/insdc-status-document/>：Withdrawn 原因之一为「(3) Human sequence data that was not consented for unrestricted-access.」
- EBI ToU Data 4：EGA 与人类生物医学数据「these rights may be formalised in **Data Access Agreements**」

**对本评测集的含义：**
- **需要受控访问的人类数据根本不在 ENA/SRA 里** —— 所以那里没有东西可镜像。它在 **EGA**（EBI）或 **dbGaP**（NCBI），受数据访问协议约束。镜像它是对访问协议的**合同违约**，不是「存档条款」问题。
- 对**确实在** ENA/SRA 中的（已同意无限制发布）人类数据：INSDC 条款不限制再分发，**同时放弃对第三方再利用的一切控制**。→ 我们**没有被许可排除**，但**也没有得到任何保护或同意保证**。
- **撤回不能撤销已发生的分发**：「because the data will have been distributed previously as Public, the INSDC partners cannot exercise any control on the resultant use of the data by third parties.」→ 实践上，镜像可以在 ENA/SRA 撤回后**继续提供未获同意的人类数据**。**这才是人类数据再分发的真实风险：隐私/同意/法律风险，而不是存档条款风险。**
- ⚠️ **dbGaP 侧条款未能核实**：`https://www.ncbi.nlm.nih.gov/gap/policies/` 返回 HTTP 404，未定位到现行 dbGaP 政策/DUA 页面。**「受控访问数据不得再分发」这句话在 dbGaP 的 Data Use Agreement 中未被本轮核实**（见 §12）。

### 9.4 IGSR / 1000 Genomes 的明文警示（已亲自核实）

**IGSR Disclaimer**（<https://www.internationalgenome.org/IGSR_disclaimer/>，Updated 15 January 2026）原文：

> 「In relation to the "Data Services" section of the "Terms of Use for EMBL-EBI Services", users should be aware that **data made available by IGSR comes from many different owners and that consequently restrictions on different pieces of data within IGSR and rights claimed on pieces of data vary.** These variations can occur both between and within subsets of data in IGSR. In addition, restrictions and claimed rights may vary over time.」
> 「Where specific restrictions or claimed rights have been made known to IGSR, that information will be provided by IGSR with the data, however, **IGSR can not guarantee the information being accurate for any purpose. It remains the responsibility of users to ensure that their exploitation of the data does not infringe any of the rights of third parties, including the data owners.**」
> 「Data from the 1000 Genomes Project is now **available without embargo**, following the final publication from the project.」

**含义**：即使是 EBI 的旗舰开放人类数据，EBI 也**明确拒绝**保证权利链完整，并把风险转移给使用者。**这不是「ENA 不允许再分发」，而是「ENA 不给你任何权利保证」。**

### 9.5 结论与规则

- ✅ **可以对公开的 SRA/ENA 数据做镜像与再分发** —— 有 INSDC 与两库各自的明文支持，**无 NC 限制**。
- 🟢 **SRA 与 ENA 条款对称，不存在「ENA 更宽松」的许可差异。** 不要基于这个错误前提做架构决策。
- ⚠️ **镜像时的操作约束**：EBI ToU DRT 1 要求「只通过其提供的服务接口」访问；NCBI 要求 ≤3 请求/秒、避开高峰、带 `email`/`tool`。**不要在文档里宣传「绕过限制的镜像脚本」。**
- ⚠️ **优先用 SRA 的云 bucket 做镜像**（官方明示 unlimited bucket-to-bucket），且 ENA 明确不承诺永久保存原始提交文件。
- 🔴 **人类数据的铁律**：
  - GIAB 是**明确的例外**（NIST/PGP 同意范围覆盖完全公开再分发，见 §1）。
  - 1000 Genomes / GEUVADIS 的 LCL 序列数据是**开放**的（历史遗留 broad consent），但**不要**把「开放」推广到任何其他人类 ENA/SRA 数据。
  - **规则：任何非 GIAB 的人类 ENA/SRA 序列数据，一律不打包，只发 accession + 脚本。受控访问（EGA/dbGaP）数据绝对不镜像，也不嵌入可能重识别的个体级派生数据。**

---

## 10. 技术可行性

### 10.1 30 分钟 CPU-only 单 Docker 镜像可行性

| 题目 | 30 分钟 CPU 可行？ | 可行做法与资源量 |
|---|---|---|
| **变异检出（GIAB）** | ⚠️ **仅在限定区域 + 预比对 BAM 时可行** | 全基因组比对（BWA-MEM 3.1 Gb @30x）绝对不可行（单线程 8–20 h）。**可行方案**：镜像内预置 **chr20 或 chr21 的已比对 BAM（限制在 ~10–20 Mb 区间、下采样至 20–30x）**。则 HaplotypeCaller 单样本该区间约 **2–6 分钟**、峰值 RAM **4–8 GB**；随后 hap.py/vcfeval 比较 < 1 分钟。<br>**推荐切分**：chr20:1–10,000,000（GRCh38），BAM 约 1–2 GB。若必须让考生自己做比对，则把区间缩到 **1–2 Mb** @30x，BWA-MEM 单线程约 3–8 分钟。 |
| **转录本定量（GEUVADIS）** | ✅ 可行 | 单样本 75 bp PE RNA-seq 已比对 BAM（ENA 提供）→ salmon/kallisto 定量。**不要**让考生从头比对。若给 FASTQ 子集（下采样至 5–10 M reads），salmon 索引预建后定量约 **1–3 分钟**。镜像内预建索引（人类 transcriptome 索引约 2–4 GB）。 |
| **差异表达（GEO）** | ✅ 可行 | 直接从 GEO 取 **counts 矩阵**（很多 GSE 提供），DESeq2/edgeR 在 3–10 样本、20k 基因规模下 **< 2 分钟**。**不要**从 FASTQ 开始。 |
| **变异解读（ClinVar）** | ✅ 非常可行 | 纯数据查询/规则推理，秒~分钟级。用 `variant_summary.txt.gz`（约 300 MB）或按基因切分。 |
| **宏基因组物种组成（CAMI2 toy）** | ✅ 可行 | Kraken2/MetaPhlAn 在单个 body-site 子集上 CPU 约 **5–20 分钟**；数据库体积是主要约束（Kraken2 standard DB 约 50 GB → **必须预置在镜像或作为外挂卷**，或改用 MetaPhlAn 的 ~1–3 GB marker 库）。 |
| **PDB 结构题** | ✅ 非常可行 | 纯解析重算，秒级。 |
| **GO 富集/本体题** | ✅ 非常可行 | 秒~分钟级。 |

**通用约束**：
- **镜像体积**：Docker Hub 单层上限与拉取时间会成为实际瓶颈。建议镜像 ≤ 8 GB（压缩后），大数据用「首次运行时下载 + 校验和」模式，把下载量写进题面。
- **RAM**：GATK HaplotypeCaller 建议 ≥ 8 GB；salmon 索引加载 ≤ 4 GB；Kraken2 标准库需 ≥ 32 GB RAM → **CAMI2 题若用 Kraken2 需重新评估**，MetaPhlAn 更省。
- **线程**：假设评测机提供 4 vCPU。上述时间估算按 4 线程给出。

### 10.2 真值权威性

| 题 | 真值是否权威公开（非自算） | 说明 |
|---|---|---|
| 变异检出（GIAB） | ✅ **最强** | NIST/GIAB 官方 benchmark VCF + BED，社区公认；有 GA4GH best practices 与 stratifications |
| 转录本定量（GEUVADIS） | ⚠️ **弱** | GEUVADIS 论文**没有发布**转录本定量的官方真值。任何「正确答案」都是我们自己算的 → **不符合「非自算」要求**。**建议改造**：把题目从「定量准确性」改为「可复现性/流程正确性」（给定输入与参数，输出必须与我们的参考实现一致到某容差），并在 DATACARD 说明真值是「参考实现输出」而非生物学金标准。 |
| 差异表达（GEO） | ⚠️ **弱-中** | GEO 本身**不是** DE 真值库。少数 GSE 有配套的 spike-in 或已知 ground truth，绝大多数没有。**建议改造**：改为「复现论文中报告的 DEG 集合」——但论文结论不是「权威真值」，只是「参考基准」。必须在 DATACARD 中降级表述为 "reference benchmark, not ground truth"。或改用 **Perturb-seq / 已知 spike-in 数据集**。 |
| 变异解读（ClinVar） | ✅ 强（但需筛选） | ClinVar 的 **expert panel / practice guideline** review status（3–4 星，如 ENIGMA、ClinGen）是权威真值。**必须过滤掉 1–2 星的低置信提交**，否则真值不可靠。 |
| 宏基因组（CAMI2） | ✅ 强 | CAMI 官方 gold standard，模拟生成时构造 |
| PDB 结构题 | ✅ 强 | 可从 mmCIF 确定性重算 |
| GO 本体题 | ✅ 强 | 本体文件即权威真值 |
| Micrococcus 直系同源 | ❌ **无** | 见 §7 → 放弃 |

### 10.3 容器工具许可风险（已逐条核实上游 LICENSE 文件）

> **本轮最重要的六个纠正**（全部基于上游 LICENSE 一手核实）：
> ① RTG Tools / vcfeval **不是**非商用许可，而是 **BSD-2-Clause**（自 v3.5/2015-07 起；非商用限制属于 **RTG Core**，且 RTG Core 自 **3.13/2025-05-27** 起也已改为 BSD）。
> ② **GATK4 ≥4.2 是 Apache-2.0**（4.0–4.1.x 为 BSD-3）。**真正的非商用陷阱是 GATK3（2.0–3.x）** —— Broad 专有协议「FOR ACADEMIC NON-COMMERCIAL RESEARCH PURPOSES ONLY」。
> ③ **salmon ≥2.0 是 BSD-3-Clause**（只有 C++ 的 ≤1.12.0 才是 GPLv3）。
> ④ **STAR ≥2.7.2a 是 MIT**（只有 ≤2.7.1a 是 GPLv3）。
> ⑤ **kallisto 的许可文件名是小写 `license.txt`**（这就是 `LICENSE` 404 的原因）。
> ⑥ 任务简报里的 GATK 许可 URL（`.../articles/360036802091-Licensing`）**是错的** —— 该 ID 对应的文章标题是「NonZeroFragmentLengthReadFilter」；帮助中心**不存在**标题为 "Licensing" 的文章。**不要再引用该 URL。**

**🟢 宽松许可（可自由放进公开镜像、可商用）**

| 工具 | 许可（SPDX） | 已核实的一手文件 |
|---|---|---|
| **GATK4 ≥4.2**（含 master） | **Apache-2.0** | <https://raw.githubusercontent.com/broadinstitute/gatk/master/LICENSE.TXT>（「Copyright 2021 Broad Institute, Inc. / Licensed under the Apache License, Version 2.0」） |
| GATK 4.0–4.1.x | BSD-3-Clause | <https://raw.githubusercontent.com/broadinstitute/gatk/4.1.0.0/LICENSE.TXT> |
| **RTG Tools / vcfeval** | **BSD-2-Clause** | <https://raw.githubusercontent.com/RealTimeGenomics/rtg-tools/master/LICENSE.txt>；README：「This software is provided under the Simplified BSD License」 |
| **hap.py** | **BSD-2-Clause（Simplified BSD）** | <https://raw.githubusercontent.com/Illumina/hap.py/master/LICENSE.txt> |
| **samtools** | **MIT/Expat** | <https://raw.githubusercontent.com/samtools/samtools/develop/LICENSE> |
| **htslib** | **MIT/Expat**（`cram/` 子目录为 BSD-3-Clause） | <https://raw.githubusercontent.com/samtools/htslib/develop/LICENSE> |
| **bcftools** | **MIT/Expat 或 GPL 双许可（择一）**；⚠️ 若用 GSL 编译（默认关闭）则为 GPL | <https://raw.githubusercontent.com/samtools/bcftools/develop/LICENSE>（「available to you under a choice of one of two licenses… the MIT/Expat license or the GNU General Public License (GPL)… If compiled with the GNU Scientific Library (which is optional and disabled by default)… the use of this software is governed by the GPL license.」） |
| **salmon ≥2.0** | **BSD-3-Clause** | <https://raw.githubusercontent.com/COMBINE-lab/salmon/master/LICENSE>（「BSD 3-Clause License / Copyright (c) 2026, COMBINE lab」） |
| **STAR ≥2.7.2a** | **MIT** | <https://raw.githubusercontent.com/alexdobin/STAR/master/LICENSE> |
| **kallisto** | **BSD-2-Clause** | <https://raw.githubusercontent.com/pachterlab/kallisto/master/license.txt> |
| **minimap2** | **MIT** | <https://raw.githubusercontent.com/lh3/minimap2/master/LICENSE.txt> |
| **BWA-MEM2** | **MIT** | <https://raw.githubusercontent.com/bwa-mem2/bwa-mem2/master/LICENSE> |
| **FreeBayes** | **MIT** | <https://raw.githubusercontent.com/freebayes/freebayes/master/LICENSE> |
| **Kraken2** | **MIT** | <https://raw.githubusercontent.com/DerrickWood/kraken2/master/LICENSE> |
| **MetaPhlAn** | **MIT** | <https://raw.githubusercontent.com/biobakery/MetaPhlAn/master/license.txt>（4.2.6 与 3.0.14 均为标准 MIT） |
| **HUMAnN** | **MIT（Harvard）** | <https://raw.githubusercontent.com/biobakery/humann/master/LICENSE>（⚠️ 但**捆绑 MetaCyc 派生数据**，见下） |
| **SnpEff** | **MIT** | <https://raw.githubusercontent.com/pcingola/SnpEff/master/LICENSE.md>（根 `LICENSE` 404；存在一个**捐赠请求**，不是许可条款） |
| **Ensembl VEP** | **Apache-2.0** | <https://raw.githubusercontent.com/Ensembl/ensembl-vep/main/LICENSE> |
| **PyDESeq2** | **MIT** | <https://raw.githubusercontent.com/owkin/PyDESeq2/main/LICENSE> |
| **Nextflow** | **Apache-2.0** | <https://raw.githubusercontent.com/nextflow-io/nextflow/master/COPYING>（仅商标声明） |
| **nf-core/tools + pipeline 模板** | **MIT** | <https://raw.githubusercontent.com/nf-core/tools/master/LICENSE> |

**🟡 弱 copyleft**
- **DESeq2 = LGPL (≥3)** → LGPL-3.0-or-later。一手来源：`DESCRIPTION`（<https://raw.githubusercontent.com/mikelove/DESeq2/master/DESCRIPTION>，字段 `License: LGPL (>= 3)`）。LGPL 允许 MIT/Apache 代码**动态链接**使用而不被传染；**前提是 LGPL 库保持可替换、可修改，且我们不修改其源码**。若想彻底避开 copyleft → 用 **PyDESeq2（MIT）**。

**🟠 强 copyleft GPL（可分发，但触发源码提供义务）**

| 工具 | 许可 | 一手/二手来源 |
|---|---|---|
| **edgeR** | **GPL (>=2)** → GPL-2.0-or-later | <https://bioconductor.org/packages/release/bioc/html/edgeR.html>（官方页面 `License: GPL (>=2)`）；bioconda 元数据亦为 `GPL (>=2)` |
| **limma** | **GPL (>=2)** | bioconda 元数据 <https://raw.githubusercontent.com/bioconda/bioconda-recipes/master/recipes/bioconductor-limma/meta.yaml> — **二手来源，建议复核** |
| **vcfdist** | **GPLv3** | <https://raw.githubusercontent.com/TimD1/vcfdist/master/LICENSE>（完整 GPLv3 文本） |
| **BWA** | **GPL-3.0**（包级；`COPYING` = GPLv3 文本） | <https://raw.githubusercontent.com/lh3/bwa/master/COPYING>；man page：「The full BWA package is distributed under GPLv3 as it uses source codes from BWT-SW which is covered by GPL. Sorting, hash table, BWT and IS libraries are distributed under the MIT license.」⚠️ **混合来源**：`bwa.c`/`ksw.c` 带 MIT 头，哪些文件适用哪套条款无法从文件本身判定 |
| **bowtie2** | **GPL-3.0** | <https://raw.githubusercontent.com/BenLangmead/bowtie2/master/LICENSE> |
| **salmon ≤1.12.0**（C++/pufferfish） | **GPL-3.0** | <https://raw.githubusercontent.com/COMBINE-lab/salmon/cpp/LICENSE> |
| **STAR ≤2.7.1a** | **GPL-3.0** | <https://raw.githubusercontent.com/alexdobin/STAR/2.7.1a/LICENSE> |
| **eggnog-mapper** | **GPLv3** | <https://raw.githubusercontent.com/eggnogdb/eggnog-mapper/master/setup.cfg>（`license = GPLv3`） |

**🔴 真正的非商用 / 专有陷阱（必须避开）**

| 工具 | 许可 | 原文与含义 |
|---|---|---|
| **GATK3（2.0–3.x）** | **Broad 专有，"ACADEMIC NON-COMMERCIAL RESEARCH PURPOSES ONLY"** | <https://raw.githubusercontent.com/broadgsa/gatk/master/licensing/protected_license.txt>：<br>「BROAD INSTITUTE SOFTWARE LICENSE AGREEMENT **FOR ACADEMIC NON-COMMERCIAL RESEARCH PURPOSES ONLY**」<br>「2.1 … grants to LICENSEE, **solely for academic non-commercial research purposes**」<br>「2.3 … the PROGRAM, in whole or part, **shall not be used for any commercial purpose**, including without limitation, as the basis of a commercial software or hardware product **or to provide services**.」<br>「2.2 … **shall not sublicense or distribute the PROGRAM**, in whole or in part, **without prior written permission from BROAD**.」<br>另有 §3「**PHONE-HOME FEATURE**」：默认启用的「embedded automatic reporting system」。<br>Broad 官方 2017 博客确认：「Under this mixed model, **GATK was free for academic/non-profit research purposes, while any for-profit use required a paid commercial license**」（<https://raw.githubusercontent.com/broadinstitute/gatk-docs/refs/heads/master/blog-2012-to-2019/2017-05-24-GATK4_is_completely_open_source.md>）<br>→ **绝对不要用 GATK3；用 GATK4 ≥4.2（Apache-2.0）。** |
| **RTG Core < 3.13** | 曾为专有（非商用） | 已解除。RTG 3.5 公告（2015-07-16）：「We are also pleased to make **the source code to RTG Tools available under the Simplified BSD License**, on github. (**Source code for RTG Core remains available for non-commercial use**)」（<https://www.realtimegenomics.com/news/rtg-core-3-5-rtg-tools-3-5-released>）。RTG Core 3.13 发行说明：「**RTG Core is now released under the BSD license, there are no longer separate non-commercial and commercial releases.**」（<https://raw.githubusercontent.com/RealTimeGenomics/rtg-tools/master/installer/ReleaseNotes.txt>）<br>→ 用 RTG Tools ≥3.5（pre-3.5 标签的 `LICENSE.txt` 全部 404，条款未核实）；若用 RTG Core 必须 ≥3.13。 |
| **KEGG** | 商业许可（非公有数据库） | <https://www.kegg.jp/kegg/legal.html>：「**Non-academic users must understand that KEGG is not a public database, nor is it a publicly funded database. Non-academic use of KEGG requires a commercial license.**」 |
| **BUSCO 数据集** | **CC BY-ND 4.0** | <https://busco.ezlab.org/>：「The BUSCO software is licensed under the **MIT License**. The BUSCO datasets are licensed under the **Creative Commons Attribution-NoDerivatives 4.0 International License**…」→ **不得分发派生数据集** |

**🟠 未随代码一起授权的「数据」类陷阱（最容易被 SBOM 漏掉）**

| 项 | 问题 | 来源 |
|---|---|---|
| **ChocoPhlAn 数据库**（MetaPhlAn/HUMAnN 依赖） | **没有 LICENSE 文件** | bioBakery 论坛用户提问：<https://forum.biobakery.org/t/license-for-chocophlan/8951>。**MetaPhlAn 软件是 MIT 并不回答数据库的许可问题。** 若提供商业托管服务必须单独确认 |
| **MetaCyc 派生通路定义**（HUMAnN 捆绑） | 有各自的订阅条款 | 同上（未核实） |
| **VEP 插件/注释数据**（dbNSFP、SpliceAI、LOFTEE 等） | 独立的第三方条款 | 未审计 |
| **SnpEff/SnpSift 捆绑 JAR 内容** | 独立的第三方条款 | 未审计 |
| **GenomicsDB**（GATK4 依赖） | 顶层 MIT，但：「libcsv is licensed under… LGPLv2. So, **if you are re-distributing binaries or object files, they may be subject to LGPLv2 terms**」（libuuid 同）。**GATK4 发布的二进制是否真的链接了它们未核实** | 见 §12 |
| **`gatk-bwamem-jni`**（GATK4 依赖） | BSD-3 wrapper，README 称其「allows Java code to call Heng Li's bwa mem aligner」；上游 **BWA 是 GPLv3**。**GPLv3 代码是否被编入所发布的 native library 未解决** | 见 §12 |

**⚠️ Bioconda / conda 元数据的许可字段不可信 —— 已验证两处错误：**
- Bioconda 的 `gatk`（GATK3 v3.8）声明 `license: BSD` —— **错**（实际是学术非商用协议）
- Bioconda 的 `gatk4`（4.7.0.0）声明 `license: BSD-3-Clause` —— **错**（实际是 Apache-2.0）

**⇒ 永远以**上游 `LICENSE` 文件**为准，不要信 conda recipe 的 license 字段。**

**Bioconda 的再分发闸门是真的**：政策要求「**License allows redistribution and license is indicated in `meta.yaml`**」（<https://bioconda.github.io/contributor/guidelines.html>）。GATK3 的封堵有据可查 —— `gatk-register.sh` 原文（<https://raw.githubusercontent.com/bioconda/bioconda-recipes/master/recipes/gatk/gatk-register.sh>）：
> 「**Due to license restrictions, this recipe cannot distribute and install GATK directly.** To fully install GATK, you must download a licensed copy of GATK from the Broad Institute… `gatk-register /path/to/GenomeAnalysisTK…`」

⚠️ 但当前 `gatk` recipe 的 `meta.yaml` 已带有**指向 Broad 的直连 tarball URL + sha256**，`build.sh` 直接复制 jar —— **看似与其自己的「cannot be redistributed」声明矛盾**。**未核实** anaconda.org / quay.io Biocontainer 上实际发布的内容是 GATK3 二进制还是仅 register 占位脚本。**GATK4 在 Bioconda 上没问题（Apache-2.0）。**

⚠️ **RTG Tools ≠ RTG Core**：**RTG Tools（含 vcfeval）= BSD-2，可自由分发、可商用**；**RTG Core** 是 RTG 的独立商业产品（`rtg-core` 仓库），**不要混入镜像**。
⚠️ **salmon 版本切分**：**≥2.0（Rust 重写）为 BSD-3-Clause**；**≤1.12.0（C++/pufferfish）为 GPLv3**（bioconda 单独打包为 `salmon-cpp`）。**锁版本时务必写 `salmon>=2.0`。**
⚠️ **MetaPhlAn 历史版本**：当前 master 与 3.0.14 均为 MIT；更早的 MetaPhlAn 2.x **未核实**（见 §12）。**HUMAnN 未核实**，单独锁定前不要入库。

**🟡 弱 copyleft（LGPL — 动态链接下可放宽）**
- **DESeq2 = LGPL (≥3)**。一手来源：`DESCRIPTION`（<https://raw.githubusercontent.com/mikelove/DESeq2/master/DESCRIPTION>，字段 `License: LGPL (>= 3)`）。LGPL 允许 MIT/Apache 代码**动态链接**使用而不被传染；只要不修改 DESeq2 源码、不做静态链接，公开镜像可分发。若想彻底避开 copyleft → 用 **PyDESeq2（MIT）**。

**🟠 强 copyleft GPL（可分发，但触发源码提供义务）**
| 工具 | 许可 | 来源 |
|---|---|---|
| **edgeR** | **GPL (≥2)** | bioconda 打包元数据 <https://raw.githubusercontent.com/bioconda/bioconda-recipes/master/recipes/bioconductor-edger/meta.yaml>（`license: GPL (>=2)`）— **二手来源，建议以上游 DESCRIPTION 复核** |
| **limma** | **GPL (≥2)** | bioconda 元数据 <https://raw.githubusercontent.com/bioconda/bioconda-recipes/master/recipes/bioconductor-limma/meta.yaml> — **二手来源，建议复核** |
| **vcfdist** | **GPLv3** | <https://raw.githubusercontent.com/TimD1/vcfdist/master/LICENSE>（完整 GPLv3 文本） |
| **STAR** | GPLv3（**未直接核实**） | 见 §12 |
| **bowtie2** | GPLv3（**未直接核实**） | 见 §12 |
| **BWA** | GPLv3（**未直接核实**） | 见 §12 |

### 10.3b 每个 GPL 环节都有宽松许可替代（可直接替换）

| 环节 | GPL 工具 | ✅ 宽松替代 | 许可（已核实） | 可比性说明 |
|---|---|---|---|---|
| 转录本定量 | salmon ≤1.12.0 (GPLv3) | **salmon ≥2.0**（BSD-3）或 **kallisto**（BSD-2） | BSD-3 / BSD-2 | ⚠️ **kallisto ≠ salmon**：kallisto 是 pseudoalignment + EM；salmon 是 selective alignment + 更丰富的 bias 模型。per-transcript 估计**不可互相替代**。**kallisto 可以完成本题，但必须选定一个工具作为「参考实现」并按该工具自身输出评分，绝不能拿 salmon 的输出当真值去卡 kallisto。** 这正说明 GEUVADIS 题的「真值」只能是「参考实现输出」而非生物学金标准 |
| reads→BAM 比对 | BWA / bowtie2 (GPLv3) | **BWA-MEM2**（MIT）或 **minimap2**（MIT） | MIT / MIT | BWA-MEM2 与 BWA-MEM 算法等价、输出兼容 → **首选，可比性最好**。minimap2 面向长读/剪接，短读全基因组不如 BWA-MEM2 |
| BAM/VCF 加工 | — | **samtools / htslib**（MIT/Expat）、**bcftools**（MIT 或 GPL 双许可，**择 MIT**） | MIT | 完全等价，且 bcftools 可主动选择 MIT 分支 |
| 差异表达 | edgeR / limma（GPL≥2） | **PyDESeq2**（MIT）；**DESeq2**（LGPL≥3）亦可 | MIT / LGPL-3 | PyDESeq2 是 DESeq2 的 Python 重实现，结果**高度接近但不逐位相同**。**同样：选定一个作为参考实现** |
| 变异比较 | vcfdist (GPLv3) | **hap.py + RTG vcfeval**（均 BSD-2） | BSD-2 | ✅ **确认：完全不需要 vcfdist。** hap.py+vcfeval 是 GA4GH 官方推荐组合，许可更干净，也是 GIAB 生态默认工具 |
| 宏基因组物种组成 | — | **MetaPhlAn 4.2.6**（MIT）或 **Kraken2**（MIT） | MIT | 两者方法不同（marker-based vs k-mer LCA），**不可互换真值**；选一作参考实现 |

**⇒ 结论：VeriBench-Bio 的全部题目都可以只用宽松许可（MIT / BSD / Apache-2.0）工具实现，无需任何 GPL 工具、无需任何非商用工具。** 这意味着「只发 Dockerfile 以规避 GPL」的策略其实**没有必要**——可以直接发预构建镜像。

### 10.3c 容器策略的法律边界（回答「只发 Dockerfile 是否规避 GPL」）

依据 **GPLv3 法律文本**（本报告直接抓取的原文，见 <https://raw.githubusercontent.com/TimD1/vcfdist/master/LICENSE> 与 <https://raw.githubusercontent.com/samtools/bcftools/develop/LICENSE>）：

**关键条款原文**
- §0：「To **convey** a work means any kind of propagation that enables other parties to make or receive copies. **Mere interaction with a user through a computer network, with no transfer of a copy, is not conveying.**」
- §2：「You may make, run and propagate covered works that **you do not convey**, without conditions so long as your license otherwise remains in force.」
- §5（聚合 vs 衍生）：「A compilation of a covered work with other separate and independent works, which are not by their nature extensions of the covered work, and which are not combined with it such as to form a larger program, **in or on a volume of a storage or distribution medium, is called an "aggregate"** if the compilation and its resulting copyright are not used to limit the access or legal rights of the compilation's users beyond what the individual works permit. **Inclusion of a covered work in an aggregate does not cause this License to apply to the other parts of the aggregate.**」
- §4（分发源码副本）：「You may convey verbatim copies of the Program's source code ... **provided that** you conspicuously and appropriately publish on each copy an appropriate copyright notice; keep intact all notices stating that this License ... apply to the code; keep intact all notices of the absence of any warranty; and **give all recipients a copy of this License** along with the Program.」
- §6（分发二进制）：「You may convey a covered work in object code form under the terms of sections 4 and 5, **provided that you also convey the machine-readable Corresponding Source** ... in one of these ways: (a) 源码随实物介质；**(b) 附至少 3 年有效的书面要约**；(d) **从指定地点提供目标码并同地提供等价源码访问**（源码可在第三方服务器，但须给出明确指引）；(e) P2P。**(c) 仅限偶尔且非商业**」

**风险判断（逐项）**

| 做法 | 是否构成 GPL 意义上的 convey？ | 风险 |
|---|---|---|
| 仓库里只有 `Dockerfile`，写 `RUN conda install -c bioconda salmon` | ❌ **不构成**。GPL 代码不在我们的分发物里；`docker build` 时是**用户**从 conda/上游下载，transfer 发生在「上游 → 用户」之间（§0 的 convey 定义 + §2「do not convey」） | 🟢 低 |
| 同上，但 base image 是**我们发布的、已含 GPL 二进制的镜像** | ✅ **构成**。从 registry 把镜像传给用户即 convey 目标码 | 🟠 触发 §6 |
| 直接发布预构建镜像（含 GPL 二进制） | ✅ **构成** | 🟠 触发 §6。**实务上完全可走 (d)**：镜像内放 `GPL_SOURCES.md`，给出**精确版本号**的上游源码 URL，并保证长期有效（GitHub tag / Software Heritage 永久标识）。§6(d) 明确允许源码托管在第三方服务器 |
| Dockerfile 里 `COPY` 了我们 patch 过的 GPL 源码 | ✅ **构成**（且含修改） | 🟠 触发 §4+§5：须标注修改日期、附 GPL 全文、**整个被修改作品以 GPL 授权** |
| **我们自建 conda channel / apt 镜像**，内含 GPL 二进制 | ✅ **构成** | 🟠 触发 §6 |
| 用户 `docker run` 本地跑，不联网对外提供服务 | — | 🟢 **AGPL §13 网络条款不触发**（GPLv3 §13 只是允许与 AGPL 合并） |
| 我们的题目驱动代码（MIT/Apache）以**子进程**方式调用 GPL 工具 | — | 🟢 依 **GPLv3 §5 的 aggregate 定义**（「in or on a volume of a storage or distribution medium」），我们的代码与 GPL 工具是各自独立作品、非彼此的 extension → 属聚合，**GPL 不传染到我们的代码**。容器镜像可类比为「存储/分发介质上的一卷」 |

### 🔴 10.3d 我们技术栈里**唯一真正的合规陷阱：R 包**

**子进程调用有安全港，R 进程内加载没有。** FSF FAQ #GPLPlugins 原文：
> 「**A main program that uses simple fork and exec to invoke plug-ins and does not establish intimate communication between them results in the plug-ins being a separate program.**」

但 FSF 对**解释器内加载**的处理不同（#IfInterpreterIsGPL）：
> 「if you choose to use **GPLed Perl modules or Java classes** in your program, you must release the program in a GPL-compatible way」

**⇒ 一个写 `library(edgeR)`（GPL-2.0-or-later）的 R 脚本，很可能构成结合作品，需要以 GPL 兼容许可发布。** 这与「subprocess 调用」不是同一个安全港。DESeq2（LGPL-3.0-or-later）的设计**允许**这种用法，前提是 LGPL 库保持可替换/可修改。

FSF FAQ #MereAggregation 补充：
> 「The GPL permits you to create and distribute an aggregate, even when the licenses of the other software are nonfree or GPL-incompatible. The only condition is that you cannot release the aggregate under a license that prohibits users from exercising rights that each program's individual license would grant them.」

**⇒ 建议（三选一）**：
1. **【最稳】DE 题改用 PyDESeq2（MIT）** —— 纯 Python，彻底避开 R 的 copyleft 问题。
2. **把 edgeR/DESeq2 调用隔离进一个薄的 shim 脚本，并明确把该 shim 以 GPL 兼容许可发布**（例如 `GPL-3.0-or-later`），其余题集代码保持 MIT/Apache。这满足 #IfInterpreterIsGPL 的要求，且不污染主仓。
3. 若必须留在 R 且不愿 GPL 化 → 只用 **DESeq2（LGPL-3.0+）**，并在文档中说明「库保持未修改、可替换」，**不要**使用 edgeR/limma。

⚠️ 注意：R 语言本身是 **GPL-2.0-or-later**，但这不是问题——**R 是解释器，不是被我们链接的库**；问题出在**以 GPL 许可发布的 R 包**。

⚠️ **FSF FAQ 的取用限制**：本环境抓取 `https://www.gnu.org/licenses/gpl-faq.html` 时页面在 Distribution/AGPL 章节前被截断，因此 `#NoDistributionRequirements`、`#UnreleasedModsAGPL`、`#AGPLv3InteractingRemotely`、`#AggregateContainers` 的**正文未能取回**。上面引用的 `#GPLInProprietarySystem`、`#UnchangedJustBinary`、`#InternalDistribution` 出自**单独的 GPLv2 时代页面** <https://www.gnu.org/licenses/old-licenses/gpl-2.0-faq.html>，措辞可能与现行 FAQ 不同。另注：任务简报里提到的锚点 `#DistributeWithGPL` 与 `#UnchangedBinaries` **不存在**，真实锚点是 `#UnchangedJustBinary`。流行说法「容器对 aggregate 分析没有影响」（对应 `#AggregateContainers`）**只见于第三方转载，未核实**。

**AGPL 补充**：我们这 17 个工具**没有一个是 AGPL**，所以网络条款在实践中不适用。一般性地：AGPL-3.0 §13 仅在你**修改了程序**且你的版本**支持远程网络交互**时触发 —— 「if you modify the Program, your modified version must prominently offer all users interacting with it remotely through a computer network (if your version supports such interaction) an opportunity to receive the Corresponding Source of your version」（<https://www.gnu.org/licenses/agpl-3.0.txt>）。所以**本地运行未修改的 AGPL 软件不产生 §13 义务**；分发其二进制仍触发 §4–§6；且 §13 是**源码提供**义务，**不是**商用禁令。

**⇒ 结论与更稳妥的替代方案（按推荐度排序）**

1. **【最稳】干脆不用 GPL 工具** —— 见 §10.3b：VeriBench-Bio 全部题目都有 MIT/BSD/Apache-2.0 实现路径。**推荐直接走这条。**
2. **分层镜像** —— `veribench-bio:base`（宽松许可，公开分发）+ `veribench-bio:extra`（GPL，公开分发但镜像内附 `GPL_SOURCES.md`，按 §6(d) 给精确版本上游源码 URL）。即使 §6 义务适用也已履行。
3. **只发 Dockerfile/recipe** —— 对 GPL 确实规避了 convey（§0/§2），**但不是零风险**：① 把构建**可复现性**责任推给用户（conda solver 随时间漂移 → 违反 VeriBench-Bio「可复现」的核心承诺）；② 无网络评测环境不可用。**因此不要把「只发 Dockerfile」当作 GPL 规避手段，而应作为「数据不下仓库」的手段。**
4. **用户自备工具（BYO-toolchain）** —— 题面要求用户自行安装并接受许可。可行，但同样牺牲可复现性。
5. **不要做**：自建含 GPL 二进制的 conda/apt 源；在 Dockerfile 里 vendored GPL 源码却不附许可与修改声明。

> **合规提示**：以上是基于 GPLv3 原文的风险判断，**非法律意见**。正式对外发布前建议让机构法务过一遍 §6 的源码提供方式。

### 10.4 污染（LLM 记忆）风险

| 题 | 污染风险 | 依据与缓解 |
|---|---|---|
| **ClinVar 变异解读** | 🔴 **极高** | ClinVar 的 variant→clinical significance 映射是公开网页、被大量论文复述，几乎必然在训练语料中。模型可**直接背诵**某个 VCV 的分类。**缓解**：① 用**时间切分**——只使用训练截止日之后发布的 ClinVar 记录（ClinVar 有 `LastUpdated`/release 版本，可做到），并把 release 日期写进题面；② 用**程序化生成**的合成变异（在已知致病基因上做 in-silico 突变）配 ClinVar 规则判读，而非查询已知条目；③ 要求模型输出**判读依据（ACMG 规则编号）**而非仅分类，增加「必须推理」的约束。 |
| **经典 GEO 数据集 DE** | 🔴 **高** | 教科书级 GSE（如 airway、pasilla、zebrafish 等）的 DE 结果被无数教程复述，模型可能记住 DEG 名单。**缓解**：① 选**冷门 GSE**（引用数低、发布晚）；② **时间切分**——只用训练截止后的 GSE；③ 改造为「给定 counts + 参数，复现流水线」的可执行题，而非「列出 DEG」的记忆题；④ 在题面提供打乱样本标签/子抽基因的版本，破坏记忆匹配。 |
| **GEUVADIS 定量** | 🟡 **中** | 定量数值不太可能被逐值记住，但「用 salmon 跑 E-GEUV-1」这个组合是标准教程。**缓解**：随机子抽样本、改变 read 子集、要求输出校验和。 |
| **GIAB 变异检出** | 🟢 **低-中** | 模型**可能**记住 HG002 的 benchmark 统计量（如 SNV 数 ~3.3M），但**无法**在 30 分钟内「背诵」出一个满足 hap.py 一致性要求的 chr20 VCF。**任务本身强制执行**。缓解：随机选区间。 |
| **CAMI2 物种组成** | 🟢 **低** | 模拟数据，真值不在语料里。 |
| **PDB / GO** | 🟢 **低** | 答案可由文件确定性重算；随机抽条目即可。 |

**通用反污染设计（建议写进方法论）**：
1. **每道题带 `contamination_risk` 与 `mitigation` 字段**，随题集一起公开。
2. **时间切分**要有据可查：记录数据源 release 版本 + 日期 + 训练截止日期的假设。
3. **可执行题优于问答式题**：凡是「运行工具产生输出并被程序判分」的题，记忆只能帮你写命令，不能帮你通过判分。
4. **程序化生成 + 随机种子**：种子与生成脚本公开，但每次评测用新种子。

---

## 11. 工具链许可速查总表

> 📌 **完整版与逐条一手来源见 §10.3 / §10.3b / §10.3d。** 下表仅为速查；**以 §10.3 为准**。

| 工具 | 许可（SPDX） | 容器分发 | 备注 |
|---|---|---|---|
| **GATK4 ≥4.2** | **Apache-2.0** | 🟢 | 商用无限制 |
| GATK 4.0–4.1.x | BSD-3-Clause | 🟢 | |
| **GATK3（2.0–3.x）** | **专有，学术非商用** | 🔴 **禁用** | 且禁止再分发、含 phone-home |
| samtools / htslib | MIT/Expat | 🟢 | htslib 的 `cram/` 为 BSD-3 |
| bcftools | **MIT/Expat 或 GPLv3 双许可（择一）** | 🟢/🟡 | ⚠️ 用 GSL 编译则为 GPLv3 |
| hap.py | **BSD-2（Simplified BSD）** | 🟢 | 依赖 RTG Tools |
| **RTG Tools / vcfeval** | **BSD-2-Clause** | 🟢 | 无商用限制；**RTG Core 是另一产品，且需 ≥3.13** |
| vcfdist | GPLv3 | 🟡 需附源码 | **不需要用**（用 hap.py+vcfeval 即可） |
| salmon ≥2.0 | **BSD-3-Clause** | 🟢 | ✅ 替代 salmon ≤1.12.0（GPLv3） |
| salmon ≤1.12.0 | GPL-3.0 | 🟡 需附源码 | |
| kallisto | BSD-2-Clause | 🟢 | |
| STAR ≥2.7.2a | **MIT** | 🟢 | ✅ 替代 STAR ≤2.7.1a（GPL-3.0） |
| STAR ≤2.7.1a | GPL-3.0 | 🟡 需附源码 | |
| bowtie2 | GPL-3.0 | 🟡 需附源码 | 替代：**BWA-MEM2 (MIT)** |
| BWA | GPL-3.0 | 🟡 需附源码 | 替代：**BWA-MEM2 (MIT)** |
| BWA-MEM2 | MIT | 🟢 | ✅ |
| minimap2 | MIT | 🟢 | ✅ |
| **DESeq2** | **LGPL (≥3)** | 🟡 | 可替换即可；替代：**PyDESeq2 (MIT)** |
| **edgeR** | **GPL (≥2)** | 🟠 | ⚠️ **R 进程内加载 = 潜在结合作品（见 §10.3d）** |
| limma | GPL (≥2) | 🟠 | 同上（**二手来源**） |
| **PyDESeq2** | **MIT** | 🟢 | ✅ R 问题的解法 |
| Kraken2 | MIT | 🟢 | 数据库体积是问题 |
| **MetaPhlAn** | **MIT** | 🟢 | ⚠️ 但 **ChocoPhlAn 数据库无 LICENSE** |
| HUMAnN | MIT（Harvard） | 🟢 | ⚠️ 但捆绑 **MetaCyc 派生数据** |
| freebayes | MIT | 🟢 | |
| SnpEff | MIT | 🟢 | 根 `LICENSE` 404，用 `LICENSE.md` |
| Ensembl VEP | Apache-2.0 | 🟢 | ⚠️ 插件数据另有条款 |
| Nextflow | Apache-2.0 | 🟢 | 仅商标声明 |
| nf-core/tools | MIT | 🟢 | |
| eggnog-mapper | GPLv3 | 🟡 需附源码 | |

**⇒ 结论：把 GATK3、BWA、bowtie2、旧版 STAR、旧版 salmon、edgeR/limma、vcfdist 全部排除后，VeriBench-Bio 仍可用纯宽松许可（MIT/BSD/Apache-2.0）工具链完成全部题目，并可安全发布预构建镜像。**

---

## 12. 无法核实项清单 + 用户自行核实步骤

| # | 无法核实的项 | 原因 | 用户自行核实步骤 |
|---|---|---|---|
| 1 | **PMC OA Subset 的官方 per-license 统计** | **NLM/PMC 从未发布**按许可的分项计数（已核查 openftlist / textmining / pmcaws / userguide 四页，均无）。§5.4 的表是**我们自己用一方 E-utilities 计数 API 在 2026-09-12 实测**的结果，**不是** NLM 出版物 | 复现：`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term="cc0 license"[filter]&retmode=json&rettype=count`，逐个替换检索式；记录日期 |
| 2 | ~~旧 `oa_file_list.csv` 的 license 列取值枚举~~ | **文件已删除**（`oa_file_list.csv` → HTTP 404）。`archive.org`/Wayback 在本会话 DNS 不可达（`EAI_AGAIN`），无法取历史副本；**当前任何 NCBI 页面都不再记录这些值** | 若能访问 Wayback：`https://web.archive.org/web/2024/https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.csv` |
| 3 | ~~`oa.fcgi` 是否 404~~ | **已直接验证**：`https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC13900` → **HTTP 404** | 已解决 |
| 3b | **`oa_comm/` / `oa_noncomm/` / `oa_other/` 的原始目录结构** | 目录已移除、`oa_file_list.csv` 已删、archive.org 不可达。`oa_comm`=可商用 / `oa_noncomm`=仅 NC / `oa_other`=其他，**只由 NCBI 散文描述与旧 README 佐证，无一手目录清单** | <https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/>（NCBI 自述） |
| 3c | **`license_code` 字段的实际取值字符串拼写**（如 `"CC BY"` vs `"cc-by"`） | `https://pmc-oa-opendata.s3.amazonaws.com/metadata/PMC10009416.1.json` 返回 `binary/octet-stream`，fetcher 拒绝。**字段规范**已从 README.txt §4.2 确认（CC codes 或 `TDM`），但未观测到真实填充值 | `curl -s --no-sign-request https://pmc-oa-opendata.s3.amazonaws.com/metadata/PMC10009416.1.json` |
| 3d | **CC FAQ 中 NC/ND 条目的正文** | <https://creativecommons.org/faq/> 超长，仅取回目录与约前 60%（截断于 "For Licensors"），"For Licensees" 与 AI 章节未返回。**anchor 已确认存在** | 替代权威来源已采用：CC BY-NC-ND 4.0 **法律文本** 与 CC 官方 NC 解释页 <https://wiki.creativecommons.org/wiki/NonCommercial_interpretation> |
| 4 | **BioProBench 论文的 523,784 / 350,565 两个数字与 CC BY-NC-ND 4.0 声明** | 未在 arXiv/期刊正文中定位并核实 | 在 arXiv 与期刊页搜 "BioProBench"，读正文的 License 与 Dataset 章节 |
| 5 | **CAMI2 原始数据集（<https://frl.publisso.de/data/frl:6425518/>）的 license 字段** | 该站返回的 MIME 类型被 fetcher 拒绝（目录页可读，`README.md` 报 `application/x-genesis-rom`） | 浏览器打开该 URL 与 `README.md`；或查 DataCite/DOI 元数据。**注意：其派生真值包（Zenodo 10.5281/zenodo.15083711）的 CC BY 4.0 已由 DataCite 元数据实测确认** |
| 6 | **UniProtKB 的许可全文** | <https://www.uniprot.org/help/license> 为 JS 渲染，返回 fallback 页面；FTP 上的 `README`/`LICENSE` 返回不可处理的 MIME 类型；web.archive.org 在本环境 DNS 解析失败（`EAI_AGAIN`） | 浏览器打开 <https://www.uniprot.org/help/license>；或查 <https://ftp.uniprot.org/pub/databases/uniprot/> 下的 README；或查 UniProt NAR 论文的 "Data availability" |
| 7 | **Ensembl 的许可全文** | 本轮未取 | <https://www.ensembl.org/info/about/legal/disclaimer.html> |
| 8 | ~~RTG Tools 非商用条款~~ | **已核实并推翻该假设** | RTG Tools = **BSD-2-Clause**（<https://raw.githubusercontent.com/RealTimeGenomics/rtg-tools/master/LICENSE.txt>）。⚠️ 遗留：**RTG Core**（独立商业产品）条款未核实 → <https://github.com/RealTimeGenomics/rtg-core> |
| 9 | ~~GATK 商业许可条款~~ | **已解决** | GATK4 ≥4.2 = **Apache-2.0**（<https://raw.githubusercontent.com/broadinstitute/gatk/master/LICENSE.TXT>）；GATK3 = 学术非商用专有（<https://raw.githubusercontent.com/broadgsa/gatk/master/licensing/protected_license.txt>）。⚠️ 简报给出的 URL `.../articles/360036802091-Licensing` **是错的**（该 ID 对应「NonZeroFragmentLengthReadFilter」） |
| 10 | ~~MetaPhlAn 版本许可差异~~ | **已解决** | master（4.2.6）与 `3.0.14` 均为 **MIT**：<https://raw.githubusercontent.com/biobakery/MetaPhlAn/master/license.txt>、`.../3.0.14/license.txt`。⚠️ **MetaPhlAn 2.x 未核实**；⚠️ **ChocoPhlAn 数据库无 LICENSE 文件**（<https://forum.biobakery.org/t/license-for-chocophlan/8951>）；**HUMAnN 捆绑的 MetaCyc 派生数据**未核实 |
| 11 | **GEUVADIS「582 transcripts」基准的出处与许可** | **未定位到任何来源** | 检索 GEUVADIS + "582 transcripts"；若出自 *Nature* 2013 补充材料，查该补充材料的版权声明。**建议弃用该数字** |
| 12 | ~~Cuatro Ciénegas 论文与许可~~ | **已解决**（但真值缺失） | A1 Front Microbiol 2024 DOI [10.3389/fmicb.2024.1369263](https://doi.org/10.3389/fmicb.2024.1369263) CC BY 4.0 + `PRJNA847603`；A2 DOI [10.3389/fmicb.2022.825167](https://doi.org/10.3389/fmicb.2022.825167) CC BY 4.0 + `PRJNA785576`。⚠️ 遗留：**MG-RAST `mgp94066` 的条款**（<https://www.mg-rast.org/>）、**Astrobiology 2012 两篇的许可**（<https://pmc.ncbi.nlm.nih.gov/articles/PMC3426886/>）、**Desnues 2008 Nature 的许可**（403）、**PNAS 2006 的许可**（403） |
| 13 | ~~ENA vs SRA 条款~~ | **已解决并证伪原假设** | INSDC 统一政策 <https://www.insdc.org/nucleotide-sequence-database-policies-2002/>；EBI ToU <https://www.ebi.ac.uk/about/terms-of-use>；NCBI 政策 <https://www.ncbi.nlm.nih.gov/home/about/policies/> |
| 14 | **dbGaP 侧受控访问条款**（「受控数据不得再分发」的 DUA 原文） | `https://www.ncbi.nlm.nih.gov/gap/policies/` 返回 **HTTP 404**，未定位到现行 dbGaP 政策/DUA 页 | 浏览 <https://www.ncbi.nlm.nih.gov/gap/> 的 Policies/Documents 章节，以及 <https://sharing.nih.gov/genomic-data-sharing-policy>，确认 DUA 中的再分发禁令原文 |
| 15 | **EGA 侧受控访问条款** | 本环境 DNS 无法解析 `ega-archive.org`（`EAI_AGAIN`） | 从正常网络打开 <https://ega-archive.org/about/> 与 <https://ega-archive.org/submission/>，记录 EGA 关于受控访问、Data Access Agreement 及其与 ENA/INSDC 关系的原文 |
| 16 | **GEO 政策页面是否有 2024→2026 的措辞漂移** | GEO 数据库是当前的（E-utilities 可见 2026-09 记录），但 `/geo/*` 政策页被 reCAPTCHA 拦截，只能读到标注 2024-07/2024-08/2024-09 的存档镜像 | 用浏览器打开 <https://www.ncbi.nlm.nih.gov/geo/info/disclaimer.html> 与 `/faq.html`，逐字比对「GEO Availability」段与 2024 镜像 |
| 17 | **GEO 记录级受控访问 banner 的确切字符串** | `<https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE345774>` 被 reCAPTCHA 拦截。已知 `"controlled access series"` 在 GEO 索引中 `QuotedPhraseNotFound`，而 `"controlled access"` 命中 1057 条但不在任何公开 API 字段中 | 浏览器打开一个 dbGaP 关联的 GSE（从 dbGaP study 页的 GEO 链接进入），登录态为登出，记录 banner/字段原文；并检查 GSE 页面是否有「License」行 |
| 18 | **`license_code` 字段的实际取值字符串拼写**（`"CC BY"` vs `"cc-by"`） | S3 元数据 JSON 返回 `binary/octet-stream`，fetcher 拒绝解码 | `curl -s --no-sign-request https://pmc-oa-opendata.s3.amazonaws.com/metadata/PMC10009416.1.json` |
| 19 | **旧 `oa_file_list.csv` 的 license 列取值枚举** | 文件已删（404），`archive.org` DNS 不可达 | 若能访问 Wayback：`https://web.archive.org/web/2024/https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.csv` |
| 20 | **GEO SOFT 文件是否真的零 rights 字段**（经验性验证） | 无 shell 可用，无法下载并解压 `<https://ftp.ncbi.nlm.nih.gov/geo/series/GSE1nnn/GSE1000/soft/GSE1000_family.soft.gz>`。当前结论基于 NCBI 的 SOFT/MINiML 文档 + E-utilities 字段枚举 | `curl -s <url> \| gunzip \| grep -iE 'licen\|copyright\|restrict\|redistribut'`，并列出不同的 `!Series_` 键 |
| 21 | **GenomicsDB（GATK4 依赖）是否真在发布的二进制中链接了 LGPLv2 的 libcsv/libuuid** | GATK4 未发布 NOTICE/BOM（`master/NOTICE` 与 `4.2.0.0/NOTICE` 均 404） | 检查 GATK4 官方 Docker 镜像内的 `ldd`/许可证目录 |
| 22 | **`gatk-bwamem-jni`（GATK4 依赖）是否把 GPLv3 的 BWA 编入所发布的 native library** | BSD-3 wrapper 调用上游 GPLv3 BWA；边界未解决 | 检查 GATK4 官方镜像中该 JNI 库的符号与来源 |
| 23 | **Bioconda `gatk` 发布物实际内容**（GATK3 二进制 vs 仅 register 占位脚本） | 当前 recipe 的 `meta.yaml` 带 Broad 直连 tarball + sha256，看似与其自己的「cannot be redistributed」声明矛盾 | 在 anaconda.org / quay.io Biocontainer 上实际拉取并 `find` 内容 |
| 24 | **ChocoPhlAn / MetaCyc / VEP 插件数据 / SnpEff 捆绑 JAR 的第三方条款** | 均未审计；**软件 MIT 不回答数据许可问题** | 分别查 ChocoPhlAn 下载页、MetaCyc 订阅条款、各插件数据源声明 |
| 25 | **bcftools 是否在目标镜像中以 GSL 编译**（若是则为 GPLv3 而非 MIT） | 取决于构建/conda 变体，未核实 | 检查镜像内 bcftools 的链接情况与 build 参数 |
| 26 | **RTG Tools 3.5 之前的条款** | 标签 3.1–3.4.1 的 `LICENSE.txt` 全部 404 | 从 RTG 官网历史发行包或 Wayback 取 |

---

## 13. 本地环境限制说明（诚实记录，影响可核实范围）

1. **`pwsh` 工具在本会话中持续失败**，报错 `SetNamedSecurityInfoW failed (Win32 5): grantWrite(<工作目录>)`（原文里的路径已脱敏为 `<工作目录>`；对此工作目录的任何命令，含指定 `workdir` 的重试，均一致失败）。**后果**：
   - 无法用 `curl`/`wget` 兜底抓取那些被 fetcher 拒绝 MIME 类型的页面（UniProt LICENSE、CAMI2 README、PMC S3 元数据 JSON、eggNOG 统计文件）。
   - 无法实际执行 §附录 A 中的可复现命令；它们**未经执行**，仅作为人工步骤提供。
   - 无法下载并解压 GEO SOFT 文件做经验性 grep（§12 第 20 项）。
   - 不影响 `read`/`write`/`edit`/`grep`/`glob` 等文件工具（本报告已成功写入）。
2. **`web.archive.org` / `archive.org` 在本环境 DNS 解析失败**（`getaddrinfo EAI_AGAIN`）→ 无法用存档页绕过 JS 渲染或取回已删除文件的历史副本。
3. **`ega-archive.org` 在本环境 DNS 解析失败**（`EAI_AGAIN`）→ EGA 侧的受控访问条款未能一手核实（§12 第 15 项）。
4. **`www.ncbi.nlm.nih.gov/geo/*` 全部路径返回 reCAPTCHA 拦截**（`Checking your browser`）→ GEO 政策页只能读**存档镜像**（Forgejo `publicdata/nih-gov`，commit `bd43325b8ac26043be386420dbd6105b3d486ce3`），镜像保留 NCBI 自己的 "Last modified" 日期（2024-07/08/09）。NCBI 的非 `/geo/` 路径与 GEO **FTP** 主机可正常访问。**这构成一个真实的残留风险：无法确认 2024 镜像的措辞在 2026-09 仍与现行页面一致**（§12 第 16 项）。
5. **GitHub REST API 被限流**（`API rate limit exceeded for 160.20.62.29`）→ 无法用 `api.github.com` 批量取 `license.spdx_id`；改用逐个 `raw.githubusercontent.com` LICENSE 文件核实。**按简报要求，未对限流做重试循环。**
6. **部分服务器返回 fetcher 无法解码的 MIME 类型**：`application/x-genesis-rom`（publisso CAMI2 README）、`unknown`（UniProt FTP README）、`binary/octet-stream`（PMC S3 元数据 JSON）。这些页面的内容由 fetcher 拒绝，非 404。
7. **`https://www.gnu.org/licenses/gpl-faq.html` 在 Distribution/AGPL 章节前被截断** → `#NoDistributionRequirements`、`#UnreleasedModsAGPL`、`#AGPLv3InteractingRemotely`、`#AggregateContainers` 的正文未取回。§10.3c/§10.3d 中引用的 GPLv2 时代 FAQ 内容来自 <https://www.gnu.org/licenses/old-licenses/gpl-2.0-faq.html>。
8. **`https://www.nature.com/...`、`https://www.pnas.org/...` 返回 HTTP 403 / 跳转 idp.nature.com** → Desnues 2008 Nature 与 PNAS 2006 的许可未核实。
9. **`https://www.ncbi.nlm.nih.gov/gap/policies/` 返回 HTTP 404** → 未定位到现行 dbGaP 政策/DUA 页。
10. **`https://www.ncbi.nlm.nih.gov/sra/docs/sra-data-usage/` 返回 HTTP 404** → **不存在** SRA 专属的数据使用政策页；适用 NCBI 全域政策。
11. **`https://bioconductor.org` 间歇性超时** → edgeR 的官方页面 `License: GPL (>=2)` 已成功读取；DESeq2 从其自己的 `DESCRIPTION` 核实。

**⇒ 这些限制不改变任何已给出的许可结论（所有结论都基于成功读取的一手原文），但确实缩小了覆盖范围。§12 逐条列出了受影响的项目与人工核实步骤。**

---

## 14. 全部一手来源 URL 清单

**NIST / GIAB**
- <https://www.nist.gov/open/license> — NIST 数据/软件/技术出版物版权与许可声明（GIAB 作为 NIST 数据的授权基础）
- <https://www.nist.gov/programs-projects/genome-bottle> — GIAB 项目主页（含「consented for commercial redistribution」原文、v5.0q/v4.2.1 版本状态）
- <https://www.nist.gov/programs-projects/faqs-genome-bottle> — GIAB FAQ（第 4 问：no embargo；第 11 问：PGP 商用再分发同意）
- <https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/> — GIAB benchmark 数据发布目录
- <https://registry.opendata.aws/giab/> / <https://raw.githubusercontent.com/awslabs/open-data-registry/main/datasets/giab.yaml> — AWS Open Data 对 GIAB 的 License 字段
- <https://github.com/genome-in-a-bottle/about_GIAB> — GIAB 样本与 RM 编号说明
- <https://doi.org/10.1016/j.xgen.2022.100128> — v4.2.1 论文
- <https://doi.org/10.1101/2025.09.21.677443> — HG002 v5.0q 相关 preprint

**EBI / GEUVADIS**
- <https://www.ebi.ac.uk/biostudies/api/v1/studies/E-GEUV-1> — E-GEUV-1 元数据（实测无 license 字段）
- <https://www.ebi.ac.uk/gxa/licence.html> — Expression Atlas 许可 = CC BY 4.0
- <https://www.internationalgenome.org/IGSR_disclaimer/> — IGSR 免责声明（权利逐条不同、不保证、1000G 无 embargo）
- <https://doi.org/10.1038/nature12531> — Lappalainen et al. 2013

**NCBI / ClinVar / GEO / PMC / SRA**
- <https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/> — ClinVar 使用与再分发条款
- <https://www.ncbi.nlm.nih.gov/About/disclaimer.html> — NCBI 免责声明
- <https://www.nlm.nih.gov/web_policies.html> — NLM 网页政策（NLM 自建数据不受版权保护）
- <https://www.ncbi.nlm.nih.gov/geo/info/disclaimer.html> — GEO 免责声明
- <https://pmc.ncbi.nlm.nih.gov/tools/ftp/> — PMC FTP 服务（2026-08-26 变更公告）
- <https://pmc.ncbi.nlm.nih.gov/tools/oa-service/> — PMC OA Web Service 下线公告（2026-08-25）
- <https://pmc.ncbi.nlm.nih.gov/tools/openftlist/> — PMC OA Subset 现行说明（4 条合法路径、license terms vary）
- <https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/> — PMC 数据集 AWS 访问文档
- <https://ncbiinsights.ncbi.nlm.nih.gov/2026/02/12/pmc-article-dataset-distribution-services/> — PMC 数据集分发变更原始公告
- <https://ftp.ncbi.nlm.nih.gov/pub/pmc/PMC-ids.csv.gz> — 仅存的 FTP 服务
- <https://www.ebi.ac.uk/about/terms-of-use> — EMBL-EBI 服务条款
- <https://www.insdc.org/> — INSDC

**替代数据集**
- <https://www.wwpdb.org/about/usage-policies> — PDB = CC0 1.0
- <https://geneontology.org/docs/go-citation-policy/> — GO = CC BY 4.0
- <https://zenodo.org/api/records/15083711> — CAMI2 toy 派生真值 = CC BY 4.0
- <https://frl.publisso.de/data/frl:6425518/> — CAMI2 原始数据集
- <https://creativecommons.org/licenses/by-nc-nd/4.0/> — CC BY-NC-ND 4.0 全文
- <https://creativecommons.org/faq/> — CC FAQ（NC 与 ND 的实务解释）

**GNU / 许可**
- <https://www.gnu.org/licenses/gpl-faq.html> — GPL FAQ（`#GPLPlugins`、`#IfInterpreterIsGPL`、`#MereAggregation`；⚠️ Distribution/AGPL 章节本环境未取回）
- <https://www.gnu.org/licenses/old-licenses/gpl-2.0-faq.html> — GPLv2 时代 FAQ（`#InternalDistribution`、`#GPLInProprietarySystem`、`#UnchangedJustBinary`）
- <https://www.gnu.org/licenses/gpl-3.0.html>、<https://www.gnu.org/licenses/agpl-3.0.html>、<https://www.gnu.org/licenses/agpl-3.0.txt>

**工具许可（一手 LICENSE 文件）**
- <https://raw.githubusercontent.com/broadinstitute/gatk/master/LICENSE.TXT> — GATK4 = Apache-2.0
- <https://raw.githubusercontent.com/broadinstitute/gatk/4.1.0.0/LICENSE.TXT> — GATK 4.0–4.1.x = BSD-3
- <https://raw.githubusercontent.com/broadgsa/gatk/master/licensing/protected_license.txt> — **GATK3 = 学术非商用专有**
- <https://raw.githubusercontent.com/broadinstitute/gatk-docs/refs/heads/master/blog-2012-to-2019/2017-05-24-GATK4_is_completely_open_source.md> — Broad 关于 GATK3「mixed model」的官方说明
- <https://gatk.broadinstitute.org/api/v2/help_center/en-us/articles/360036802091.json> — 证明简报所给「Licensing」URL 是错的
- <https://raw.githubusercontent.com/RealTimeGenomics/rtg-tools/master/LICENSE.txt> — RTG Tools = BSD-2
- <https://raw.githubusercontent.com/RealTimeGenomics/rtg-tools/master/installer/ReleaseNotes.txt> — RTG Core 3.13 改 BSD
- <https://www.realtimegenomics.com/news/rtg-core-3-5-rtg-tools-3-5-released> — RTG Tools 3.5 改 BSD
- <https://raw.githubusercontent.com/Illumina/hap.py/master/LICENSE.txt>
- <https://raw.githubusercontent.com/samtools/samtools/develop/LICENSE>
- <https://raw.githubusercontent.com/samtools/bcftools/develop/LICENSE> — 双许可 MIT/GPL
- <https://raw.githubusercontent.com/samtools/htslib/develop/LICENSE>
- <https://raw.githubusercontent.com/COMBINE-lab/salmon/master/LICENSE> — salmon ≥2.0 = BSD-3
- <https://raw.githubusercontent.com/COMBINE-lab/salmon/cpp/LICENSE> — salmon ≤1.12.0 = GPL-3.0
- <https://raw.githubusercontent.com/alexdobin/STAR/master/LICENSE> — STAR ≥2.7.2a = MIT
- <https://raw.githubusercontent.com/alexdobin/STAR/2.7.1a/LICENSE> — STAR ≤2.7.1a = GPL-3.0
- <https://raw.githubusercontent.com/pachterlab/kallisto/master/license.txt>
- <https://raw.githubusercontent.com/lh3/minimap2/master/LICENSE.txt>
- <https://raw.githubusercontent.com/bwa-mem2/bwa-mem2/master/LICENSE>
- <https://raw.githubusercontent.com/lh3/bwa/master/COPYING> — BWA = GPLv3
- <https://raw.githubusercontent.com/BenLangmead/bowtie2/master/LICENSE> — GPL-3.0
- <https://raw.githubusercontent.com/TimD1/vcfdist/master/LICENSE> — GPLv3
- <https://raw.githubusercontent.com/mikelove/DESeq2/master/DESCRIPTION> — LGPL (≥3)
- <https://bioconductor.org/packages/release/bioc/html/edgeR.html> — GPL (≥2)
- <https://raw.githubusercontent.com/owkin/PyDESeq2/main/LICENSE> — MIT
- <https://raw.githubusercontent.com/biobakery/MetaPhlAn/master/license.txt> — MIT
- <https://raw.githubusercontent.com/biobakery/humann/master/LICENSE> — MIT（Harvard）
- <https://raw.githubusercontent.com/DerrickWood/kraken2/master/LICENSE>
- <https://raw.githubusercontent.com/freebayes/freebayes/master/LICENSE>
- <https://raw.githubusercontent.com/pcingola/SnpEff/master/LICENSE.md>
- <https://raw.githubusercontent.com/Ensembl/ensembl-vep/main/LICENSE>
- <https://raw.githubusercontent.com/nextflow-io/nextflow/master/COPYING>
- <https://raw.githubusercontent.com/nf-core/tools/master/LICENSE>
- <https://raw.githubusercontent.com/eggnogdb/eggnog-mapper/master/setup.cfg> — GPLv3
- <https://raw.githubusercontent.com/bioconda/bioconda-recipes/master/recipes/gatk/gatk-register.sh> — **GATK3 不可再分发的原文**
- <https://bioconda.github.io/contributor/guidelines.html> — Bioconda 再分发闸门
- <https://forum.biobakery.org/t/license-for-chocophlan/8951> — ChocoPhlAn 无 LICENSE

**GEO / SRA / INSDC / PMC 政策页（含存档镜像）**
- <https://www.ncbi.nlm.nih.gov/geo/info/disclaimer.html> — GEO 免责声明（本环境被 reCAPTCHA 拦截）
- <https://git.lsit.ucsb.edu/publicdata/nih-gov/raw/commit/bd43325b8ac26043be386420dbd6105b3d486ce3/www.ncbi.nlm.nih.gov/geo/info/disclaimer.html> — **[存档镜像]** GEO 免责声明
- <https://git.lsit.ucsb.edu/publicdata/nih-gov/raw/commit/bd43325b8ac26043be386420dbd6105b3d486ce3/www.ncbi.nlm.nih.gov/geo/info/faq.html> — **[存档镜像]** GEO FAQ
- <https://git.lsit.ucsb.edu/publicdata/nih-gov/raw/commit/bd43325b8ac26043be386420dbd6105b3d486ce3/www.ncbi.nlm.nih.gov/geo/info/soft.html> — **[存档镜像]** GEO SOFT 字段文档
- <https://git.lsit.ucsb.edu/publicdata/nih-gov/raw/commit/bd43325b8ac26043be386420dbd6105b3d486ce3/www.ncbi.nlm.nih.gov/geo/info/MINiML.html> — **[存档镜像]** MINiML 元素文档
- <https://www.ncbi.nlm.nih.gov/home/about/policies/> — NCBI 网页与数据使用政策（含脚本调用规范）
- <https://www.ncbi.nlm.nih.gov/sra/docs/>、<https://www.ncbi.nlm.nih.gov/sra/docs/submit/>
- <https://www.ncbi.nlm.nih.gov/sra/docs/sequence-data-processing/> — **「may be retrieved and redistributed by other users」原文**
- <https://www.ncbi.nlm.nih.gov/sra/docs/sra-cloud/> — 「Unlimited concurrent downloads from our cloud buckets to your buckets」
- <https://www.insdc.org/nucleotide-sequence-database-policies-2002/> — **INSDC 统一政策（最关键的条款）**
- <https://www.insdc.org/about-insdc/>、<https://www.insdc.org/submitting-standards/insdc-status-document/>
- <https://www.ebi.ac.uk/about/terms-of-use> — EMBL-EBI ToU（Data 3、DRT 1/4）
- <https://www.ebi.ac.uk/licencing> — EMBL-EBI 许可路线图（CC0 优先；ArrayExpress 已退役）
- <https://ena-docs.readthedocs.io/en/latest/faq/release.html>、<https://ena-browser-docs.readthedocs.io/en/latest/about/policies.html>
- <https://ena-docs.readthedocs.io/en/latest/retrieval/file-download.html>
- <https://pmc-oa-opendata.s3.amazonaws.com/README.txt> — PMC 云数据集 README（`license_code` 规范 + NLM 再分发义务）
- <https://pmc.ncbi.nlm.nih.gov/tools/textmining/> — 许可类别表（Commercial allowed / Non-commercial only / Other）
- <https://pmc.ncbi.nlm.nih.gov/about/userguide/> — 8 个 `[filter]` 许可检索式
- <https://pmc.ncbi.nlm.nih.gov/tools/oai/> — OAI-PMH（`set=pmc-open`）
- <https://pmc.ncbi.nlm.nih.gov/about/authorms/>、<https://pmc.ncbi.nlm.nih.gov/about/public-access-info/>
- <https://pmc.ncbi.nlm.nih.gov/about/copyright/> — PMC 批量下载禁令
- <https://ftp.ncbi.nlm.nih.gov/pub/pmc/readme.txt> — COVID-19 Collection 条款过期警告
- <https://pmc.ncbi.nlm.nih.gov/about/covid-19-faq/#removed> — 移除清单

**其他资源许可**
- <https://www.orthodb.org/static/pages/disclaimer.html> — OrthoDB = CC BY 4.0
- <https://omabrowser.org/oma/terms_of_use/> — OMA = CC BY 4.0（软件 MPL-2.0）
- <https://raw.githubusercontent.com/qfo/benchmark-webservice/master/LICENSE> — QfO 代码 = MPL-2.0
- <https://orthology.benchmarkservice.org/proxy/doc> — QfO 自述「难以建立 ground truth」
- <https://www.ebi.ac.uk/reference_proteomes/> — QfO 参考蛋白质组 2025_04 = 81 物种（不含 Micrococcus）
- <https://www.kegg.jp/kegg/legal.html> — KEGG 商业许可
- <https://busco.ezlab.org/> — BUSCO 数据集 = CC BY-ND 4.0
- <https://www.ncbi.nlm.nih.gov/research/cog/> — COG
- <https://jgi.doe.gov/data-policy-support/data-policy> — JGI 禁运/使用限制（与 CC BY 论文并存的反例）
- <https://doi.org/10.1186/s12864-021-07432-5> — Li et al. 2021（Micrococcus；含 Springer 的 CC0 data waiver 反例）
- <https://doi.org/10.3389/fmicb.2024.1369263>、<https://doi.org/10.3389/fmicb.2022.825167> — Cuatro Ciénegas 候选 A1 / A2
- <https://www.ncbi.nlm.nih.gov/bioproject/PRJNA847603>、<https://www.ncbi.nlm.nih.gov/bioproject/PRJNA785576> — CCB accessions
- <https://doi.org/10.7554/eLife.38278>、<https://doi.org/10.1089/ast.2011.0694>、<https://doi.org/10.1038/nature06735> — CCB 反例
- <https://www.mg-rast.org/> — MG-RAST（条款未核实）
- <https://www.wwpdb.org/about/usage-policies> — PDB = CC0 1.0
- <https://geneontology.org/docs/go-citation-policy/> — GO = CC BY 4.0
- <https://zenodo.org/api/records/15083711> — CAMI2 toy 真值 = CC BY 4.0
- <https://frl.publisso.de/data/frl:6425518/> — CAMI2 原始数据集（许可未核实）
- <https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.en> — CC BY-NC-ND 4.0 法律文本（ND 与 NC 的逐条分析依据）
- <https://wiki.creativecommons.org/wiki/NonCommercial_interpretation> — CC 官方 NC 解释（「turns on the use, not the identity of the reuser」）
- <https://creativecommons.org/faq/> — CC FAQ（⚠️ 本环境只取回约前 60%）

---

## 15. 建议保留 / 建议替换的题目清单

### 15.1 ✅ 建议保留（许可干净 + 真值权威 + 30 分钟 CPU 可行）

| # | 题目 | 数据源 | 建议许可标记 | 关键前置条件 |
|---|---|---|---|---|
| T1 | **变异检出（chr20/21 小区间）** | GIAB **HG002** v5.0q（GRCh38）为主，v4.2.1 为备 | `LicenseRef-NIST-Public-Domain`（+ 改动声明） | ① 主样本用 HG002；② 镜像内预置已比对 BAM；③ 区间 ≤10–20 Mb；④ comparison 用 hap.py + RTG vcfeval（BSD-2） |

> **⚠️ 本表是拍板前的调研记录，不是最终取值。** 表中「≤10–20 Mb」是当时在比较的**候选区间上限**；
> T1 **最终实现只用了 chr20:10–12 Mb（约 2 Mb）**。以 `tasks/T1/_data/manifest.json` 的
> `generation.params.region` 为唯一事实来源，并由 `scripts/verify_t1_region.py` 强制核对。
> （2026-09 修：这个候选值曾被误当成事实抄进 7 处文档，错了整整 5 倍。）
| T2 | **变异解读（ACMG 规则判读）** | ClinVar | `LicenseRef-US-Gov-Public-Domain` | ① **只用 3–4 星（expert panel / practice guideline）记录**；② 必须做**时间切分**防污染；③ 题面与 DATACARD 必须写「不用于临床决策」 |
| T3 | **结构解析 / 几何重算** | RCSB PDB | **CC0-1.0** | 用 mmCIF 原文确定性重算，随机抽条目 |
| T4 | **本体查询 / GO 富集** | Gene Ontology | **CC BY 4.0** | 署名模板照抄 GO 官方给的那段；记 release 日期 + Zenodo DOI |
| T5 | **宏基因组物种组成 / 分箱** | **CAMI2 toy**（替代 Cuatro Ciénegas） | **CC BY 4.0**（Zenodo 记录已核实） | ⚠️ CAMI2 原始数据（publisso）许可字段未核实 → **优先用 Zenodo 真值包 + 论文 CC BY**；Kraken2 库体积需换 MetaPhlAn 或预置外挂卷 |
| T6 | **蛋白/直系同源（重构版）** | **QfO 参考蛋白质组**（*S. coelicolor* / *M. tuberculosis*） | 代码 **MPL-2.0**；服务免费开放 | ✅ **必须换掉 Micrococcus**；用官方 surrogate 基准，不假装有真值 |

### 15.2 ⚠️ 建议改造后保留（许可可用，但真值不权威 → 必须降级表述）

| # | 题目 | 问题 | 改造方案 |
|---|---|---|---|
| T7 | **转录本定量** | GEUVADIS **没有发布官方定量真值**；且 kallisto ≠ salmon，数值不可互换 | ① 明确定义「**参考实现输出 = 真值**」，并在 DATACARD 降级表述；② **锁定唯一参考工具与版本**（建议 salmon ≥2.0，BSD-3）；③ 用容差而非精确匹配；④ 数据走 **Expression Atlas（CC BY 4.0）**，不打包 ENA BAM |
| T8 | **差异表达** | GEO 不是 DE 真值库，绝大多数 GSE 无 ground truth | ① 改为「**复现指定参数下的流水线**」而非「列出 DEG」；② DATACARD 写 "reference benchmark, not ground truth"；③ **改用 PyDESeq2（MIT）作参考实现**避开 R 的 GPL 陷阱；④ 必须做时间切分/冷门 GSE 选择防污染 |

### 15.3 ❌ 建议放弃 / 必须替换

| # | 题目 | 理由 | 替换为 |
|---|---|---|---|
| T9 | **Micrococcus 直系同源聚类** | **不存在权威公开真值**；拿 OrthoDB/eggNOG/OMA/COG 当真是循环论证；Micrococcus 不在 QfO 参考集中；KEGG 需商业许可、BUSCO 数据集为 CC BY-ND | **QfO 参考蛋白质组题（T6）**，或改成对 **Li et al. 2021 已发表流水线的可复现题**（明确写「复现」而非「求真值」） |
| T10 | **Cuatro Ciénegas 物种组成/丰度** | 天然群落**无组成真值**（许可本身没问题） | **CAMI2 toy（T5）**。若必须保留 CCB：只能出「MAG 组装流程复现」题，且 DATACARD 写明「无组成真值」，用 `PRJNA847603` + 论文 CC BY 4.0，**不打包数据** |

### 15.4 替代数据集速查（许可 / CPU / 体积）

| 数据集 | 许可 | 体积 | CPU 可行 | 用途 | 来源 |
|---|---|---|---|---|---|
| **RCSB PDB** | **CC0-1.0** | 单条目 KB–MB | ✅ 秒级 | 结构解析、几何重算 | <https://www.wwpdb.org/about/usage-policies> |
| **Gene Ontology** | **CC BY 4.0** | obo ~30 MB | ✅ 秒级 | 本体/DAG/富集 | <https://geneontology.org/docs/go-citation-policy/> |
| **CAMI2 toy**（Zenodo 真值包） | **CC BY 4.0** | 5–50 MB/包（真值）；原始 reads 数十 GB | ✅ 分钟级 | 物种组成、分箱 | <https://zenodo.org/api/records/15083711> |
| OrthoDB v12 | **CC BY 4.0** | 按物种查询 | ✅ | 直系同源**参考预测**（非真值） | <https://www.orthodb.org/static/pages/disclaimer.html> |
| OMA | **CC BY 4.0**（软件 MPL-2.0） | 按查询 | ✅ | 同上 | <https://omabrowser.org/oma/terms_of_use/> |
| QfO benchmark | 代码 **MPL-2.0**，服务免费 | 按 release | ✅ | 直系同源**官方 surrogate 评测协议** | <https://orthology.benchmarkservice.org/> |
| UniProtKB | CC BY 4.0（**未核实全文**） | 按需 | ✅ | 蛋白注释 | <https://www.uniprot.org/help/license> |
| Ensembl | 「无限制」（**未核实**） | 按需 | ✅ | 参考基因组 | <https://www.ensembl.org/info/about/legal/disclaimer.html> |

**⇒ 3 个最干净的替代（全部已一手核实）**：**RCSB PDB（CC0）**、**Gene Ontology（CC BY 4.0）**、**CAMI2 toy（CC BY 4.0）**。

---

## 16. 必须写进 DATACARD 的合规声明

以下 6 条建议逐字采用（可合并为 DATACARD 的「Licensing & Compliance」章节）：

**① 总体许可与再分发声明**
> 「VeriBench-Bio 自身的内容（题目、参考实现、判分脚本、文档）以 **CC BY 4.0** 发布；代码以 **MIT** 发布。第三方数据的许可**逐项不同**，见下表。我们**不主张**对任何第三方数据拥有或授予超出其原始许可的权利。」

**② 每条样本必须携带许可元数据（这是防「第 6 天翻车」的核心机制）**
> 「每一项派生自第三方来源的题目/答案，其 DATACARD 条目必须包含：`source_name`、`source_url`、`source_accession`、`source_license`（SPDX 或 `LicenseRef-*`）、`license_url`、`retrieval_date`、`source_version_or_release`、`redistributable`（bool）、`modifications`（我们对原始数据做了什么改动）。**缺任一字段的条目不得进入公开发布分支。**」

**③ GIAB / NIST 数据的专属声明**
> 「本数据集包含源自 NIST Genome in a Bottle 的派生数据。NIST 数据在美国不受版权保护（17 U.S.C. §105）；在境外，NIST 授予免版税、不可撤销、全球范围的分发与改作许可。我们已按 NIST 要求注明改动。**主样本为 HG002（NIST RM 8391），其捐献者同意范围明确包含商用再分发；HG001/NA12878 的同意范围未被 NIST 声明覆盖商用再分发，故未被用于任何声明可商用的题目。** 引用的 benchmark 版本：`<v5.0q | v4.2.1>`（v4.2.1 对 HG002 已被 NIST 标记 deprecated）。GIAB 数据完全公开，不在 dbGaP 受控访问范围内。」

**④ GEO / SRA / ENA 数据的专属声明**
> 「本数据集**不分发**任何 GEO / SRA / ENA 原始测序数据。相关题目仅提供 (a) 下载脚本、(b) accession 号、(c) 我们自算的派生结果。使用者须自行从 NCBI/EBI 官方渠道获取数据并遵守其政策。**GEO 不携带任何许可字段**；NCBI 声明不对 GEO 数据的使用与再分发施加限制，但同时明示其**无法授予许可**，且提交者可能保留知识产权——我们是依据 NCBI 公开政策行事，并未获得明示许可。下载脚本遵守 NCBI 的调用规范（≤3 请求/秒、使用 `email`/`tool` 参数、批量请求避开高峰时段）。**本数据集不包含任何受控访问（dbGaP/EGA）数据。**」

**⑤ PMC 内容的专属声明（如适用）**
> 「如本数据集包含 PMC 文章文本或摘录，仅限 `license_code ∈ {CC0, CC BY, CC BY-SA}` 的条目，且逐条记录 PMCID、版本、`license_code` 与抓取日期。**不含任何 CC BY-NC / CC BY-NC-SA / CC BY-NC-ND / CC BY-ND / 非 CC / `TDM` 条目。** 未使用 PubMed Central 字样或 PMC logo。用户须注意 NLM 的要求：所分发数据须为**当前版本**，或明确告知可能不是最新。」

**⑥ 工具链与容器声明**
> 「容器内所有工具均为 **MIT / BSD / Apache-2.0** 许可，**不含任何 GPL/AGPL 二进制、不含任何非商用许可工具**。完整清单与各自许可文本见 `/licenses/` 与 `SBOM.json`。相关工具许可**以其上游 `LICENSE` 文件为准**，不以 conda/Bioconda recipe 的 `license` 字段为准（已发现 bioconda 对 GATK 与 GATK4 的许可标注均有误）。」

**⑦（可选但强烈建议）污染与时间切分声明**
> 「每条样本记录 `contamination_risk`（low/medium/high）与 `mitigation`。涉及 ClinVar 与 GEO 的题目使用**时间切分**（仅采用数据源 release 日期晚于 `<训练截止日期假设>` 的记录）或**程序化生成/随机抽样**。随机种子与生成脚本随题集公开。」

---

## 17. PMC 可用池的精确规模（CC0 + CC BY，排除 SA / ND / NC / TDM）

> 本节回答一个比「合法」更严的白名单要求：**排除 `-SA-`（传染性）后，可用池 = CC0 + CC BY**。

### 17.1 实测数据（一方 E-utilities 计数 API，2026-09-12）

检索式：`("cc0 license"[filter] OR "cc by license"[filter]) AND "open access"[filter] NOT "pmc embargo"[filter]`
URL：<https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&retmode=json&rettype=count&term=(%22cc0+license%22%5Bfilter%5D+OR+%22cc+by+license%22%5Bfilter%5D)+AND+%22open+access%22%5Bfilter%5D+NOT+%22pmc+embargo%22%5Bfilter%5D>

**→ 结果：5,418,532 条**

| 桶 | 条数 | 占 OA Subset（8,219,033） |
|---|---|---|
| **CC0 + CC BY（我们的白名单）** | **5,418,532** | **65.9%** |
| CC BY-SA（被排除：ShareAlike） | 2,110 | 0.03% |
| CC BY-ND（被排除：禁改作） | 11,997 | 0.15% |
| CC BY-NC / NC-SA / NC-ND（被排除：禁商用） | 2,380,218 | 29.0% |
| 非 CC / 自定义（被排除：无许可） | ≈405,639 | 4.9% |
| Author manuscript `TDM`（被排除：不授予再分发权） | 1,083,887 | — |
| （参考）含 SA 的宽松池 | 5,421,148 | 66.0% |

→ **去掉 CC BY-SA 只损失 2,516 条（0.03%），代价可忽略。白名单池 = 5,418,532 条，占 OA Subset 的 65.9%。**

### 17.2 正确的检索式与必须剔除的项

**NCBI 官方推荐式（对我们的用例是错的）** —— <https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/>：
```
((cc0 license[filter] OR cc by license[filter] OR cc by-sa license[filter] OR cc by-nd license[filter]) OR author manuscript[sb]) NOT pmc embargo[filter]
```
**必须剔除的两项**：
1. 🔴 **`cc by-nd license[filter]`** —— 允许商用但**禁止改作**（ND）。我们的题目是对原文的**改作**，因此 ND 材料不能用于公开的题目/答案。
2. 🔴 **`author manuscript[sb]`** —— 作者稿件的默认 `license_code` 是 **`TDM`**，只授权文本挖掘 + 合理使用，**不授予任何再分发权**。⚠️ 且 NCBI 两个官方页面**自相矛盾**：pmcaws FAQ 称 author manuscript「available for commercial reuse regardless of license」，而数据集表与 About Author Manuscripts 页把 `TDM` 描述为仅文本挖掘 + 合理使用。

**✅ 应使用的检索式**：
```
("cc0 license"[filter] OR "cc by license"[filter])
  AND "open access"[filter]
  NOT "pmc embargo"[filter]
```
（若愿意接受 ShareAlike，可加 `OR "cc by-sa license"[filter]`，只多 2,110 条。**不建议**——SA 的传染性会与题集自己的 CC BY 4.0 冲突。）

### 17.3 逐条复核（不要只信检索式）

对每条候选取回后，**必须**读 `metadata/PMC<id>.<ver>.json` 并要求：
- `is_pmc_openaccess == true`
- **`license_code ∈ {"CC0", "CC BY"}`**（**不要**接受 `CC BY-SA`、`CC BY-ND`、任何含 `NC` 的值、`TDM`）
- `is_retracted == false`
- `is_manuscript == false`
- ⚠️ **`license_code` 确切字符串拼写未观测到**（S3 元数据文件返回 `binary/octet-stream`，fetcher 无法解码）→ **构建时先人工抽查一条**，确认是 `"CC BY"` 还是 `"cc-by"`，再写死匹配逻辑。

### 17.4 四条合法通道 × 是否支持按许可过滤

| 通道 | 支持按许可过滤？ | 字段 | 允许我们公开分发派生题？ |
|---|---|---|---|
| **S3 Cloud Service**（推荐） | ✅ **支持** | `metadata/PMC<id>.<ver>.json` → **`license_code`**；日更 S3 Inventory 无 10k 上限 | ✅ 是（CC0/CC BY 条目） |
| **OAI-PMH** | ✅ **支持** | base `https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`，`set=pmc-open`，`metadataPrefix=oai_dc` → 解析 **`<dc:rights>`**；限速 3 rps | ✅ 是 |
| **E-utilities** | ✅ **支持**（8 个 `[filter]` 值） | 检索式过滤；⚠️ ESearch **有 10,000 结果上限** | ✅ 是 |
| **BioC API** | ⚠️ 提供全文，`license` 需从记录内读取 | — | ✅ 是（仅限 CC0/CC BY 条目） |

**共同约束**（<https://pmc.ncbi.nlm.nih.gov/tools/openftlist/> 原文）：
> 「The PMC Cloud Service, PMC OAI-PMH Service, E-Utilities and BioC API are the only services that may be used for automated retrieval of PMC content. **Systematic retrieval (or bulk retrieval) of articles through any other automated process is prohibited.**」
> 「**License terms vary.** Please refer to the license statement in each article for specific terms of use.」
> 「Users of this dataset are directly and solely responsible for compliance with copyright restrictions.」

**NLM 附加再分发义务**（<https://pmc-oa-opendata.s3.amazonaws.com/README.txt> §3）：再分发者同意「**only distribute data that are licensed for redistribution**」，并须维护最新版本或**明确告知用户数据可能不是最新**；**不得使用 PubMed Central 字样或 PMC logo**；不得暗示 NLM/NIH/HHS 背书。

⚠️ **COVID-19 陷阱**（<https://ftp.ncbi.nlm.nih.gov/pub/pmc/readme.txt>）：部分 PMC COVID-19 Collection 文章的再利用条款**已过期** —— 「the terms allowing for reuse of these articles have expired and downstream users should update their datasets accordingly.」移除清单：<https://pmc.ncbi.nlm.nih.gov/about/covid-19-faq/#removed>。**→ 必须在构建时重新核实许可，不能依赖缓存快照。**

---

## 18. 附录：本次调研中推翻/修正的流行误解（速查）

| 流行说法 | 核实结果 | 依据 |
|---|---|---|
| 「RTG Tools / vcfeval 是非商用许可，不能进公开镜像」 | ❌ **错**。BSD-2-Clause，可自由分发、可商用 | <https://raw.githubusercontent.com/RealTimeGenomics/rtg-tools/master/LICENSE.txt> |
| 「GATK4 商用需要商业许可」 | ❌ **错**（这是 GATK3 时代的事实）。GATK4 ≥4.2 = **Apache-2.0** | <https://raw.githubusercontent.com/broadinstitute/gatk/master/LICENSE.TXT> |
| 「GATK 是 BSD-3-Clause」 | ❌ 不准确。仅 4.0–4.1.x 是 BSD-3；≥4.2 是 Apache-2.0 | 同上 + <https://raw.githubusercontent.com/broadinstitute/gatk/4.1.0.0/LICENSE.TXT> |
| 「GATK 的许可说明在 `.../articles/360036802091-Licensing`」 | ❌ **该 URL 是错的**，对应文章标题为「NonZeroFragmentLengthReadFilter」；帮助中心无 Licensing 标题的文章 | <https://gatk.broadinstitute.org/api/v2/help_center/en-us/articles/360036802091.json> |
| 「salmon / STAR / bowtie2 / BWA 都是 GPLv3 传染项」 | ⚠️ **半错**。salmon ≥2.0 = BSD-3；STAR ≥2.7.2a = MIT。**只有 bowtie2 与 BWA 始终是 GPLv3** | 见 §11 |
| 「ENA 比 SRA 对 bulk 再分发更宽松」 | ❌ **证伪**。同受 INSDC 统一政策，条款对称；云端镜像方面 SRA 反而更宽松 | <https://www.insdc.org/nucleotide-sequence-database-policies-2002/> |
| 「GEO 数据默认不可再分发」 | ⚠️ **需精确表述**。NCBI 明示「不限制使用与再分发」，但同时明示**无法授予许可**、提交者可能保留权利。不是禁止，是**无担保** | 见 §3 |
| 「GEO 会标注 "GSE***** is a controlled access series"」 | ❌ **未找到该措辞**。`"controlled access series"` 短语在 GEO 索引中 `QuotedPhraseNotFound`。正确机制是 **GEO 声明自己是 unrestricted-access，并把受控研究引向 dbGaP** | 见 §3.4 |
| 「PMC OA Subset 可以用 `oa_file_list.csv` + license 列筛」 | ❌ **已失效**（2026-08 移除，实测 404） | 见 §5 |
| 「NCBI 推荐的 PMC 商用检索式可以直接用」 | ❌ **对我们的用例是错的**（含 `cc by-nd` 与 `author manuscript`） | 见 §17.2 |
| 「Cuatro Ciénegas 数据许可有问题」 | ❌ **许可没问题**（环境样本、NCBI、论文 CC BY 4.0）。**问题是没有权威组成真值** | 见 §6 |
| 「Micrococcus 有权威直系同源真值」 | ❌ **不存在**。→ **应放弃该题** | 见 §7 |
| 「`#DistributeWithGPL` / `#UnchangedBinaries` 是 GPL FAQ 的锚点」 | ❌ 不存在。真实锚点是 `#UnchangedJustBinary` | 见 §10.3d |

---

*报告完成时间：2026 年 9 月。所有 URL 于该月访问。*
*本报告的所有许可结论均附一手来源 URL；凡无法读到全文的条目已在 §12 逐条列出「无法核实」原因与人工核实步骤。**本报告不构成法律意见。***

---

## 附录 A：核实这些结论的可复现命令（供人工复核）

> ⚠️ 本机 `pwsh` 在本会话中不可用（`SetNamedSecurityInfoW failed (Win32 5)`），以下命令**未经本会话实际执行**，仅作为人工复核步骤提供。所有许可结论是通过 `web_fetch` 直接读取上述 URL 原文得出的。

```bash
# 1) PMC 白名单池规模（复现 §17.1 的 5,418,532）
curl -s 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&retmode=json&rettype=count&term=("cc0 license"[filter] OR "cc by license"[filter]) AND "open access"[filter] NOT "pmc embargo"[filter]'

# 2) 确认 PMC 旧文件确已 404
curl -sI https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.csv | head -1
curl -sI 'https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC13900' | head -1

# 3) 列出 PMC FTP 现存内容
curl -s https://ftp.ncbi.nlm.nih.gov/pub/pmc/ | grep -oE 'href="[^"]+"'

# 4) 抽查一条 PMC S3 元数据，确认 license_code 的确切拼写（§17.3 的待办）
curl -s --no-sign-request https://pmc-oa-opendata.s3.amazonaws.com/metadata/PMC10009416.1.json

# 5) 核实工具许可（§11）—— 抽样
for u in \
  https://raw.githubusercontent.com/broadinstitute/gatk/master/LICENSE.TXT \
  https://raw.githubusercontent.com/RealTimeGenomics/rtg-tools/master/LICENSE.txt \
  https://raw.githubusercontent.com/COMBINE-lab/salmon/master/LICENSE \
  https://raw.githubusercontent.com/alexdobin/STAR/master/LICENSE \
  https://raw.githubusercontent.com/samtools/bcftools/develop/LICENSE ; do
  echo "== $u"; curl -s "$u" | head -5
done

# 6) 核实 GEO SOFT 记录确无 rights 字段（§3.2 的待办）
curl -s https://ftp.ncbi.nlm.nih.gov/geo/series/GSE1nnn/GSE1000/soft/GSE1000_family.soft.gz \
  | gunzip | grep -iE 'licen|copyright|restrict|redistribut' ; echo "exit=$?"

# 7) 复核 GEO 受控访问措辞（§3.4 的待办）
curl -s 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gds&term=%22controlled+access+series%22&retmode=json'
