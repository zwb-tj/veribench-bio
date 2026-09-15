---
license: other
license_name: us-government-work-public-domain
license_link: https://www.nist.gov/open/license
pretty_name: VeriBench-Bio T1 — HG002 chr20 变异检出
task_categories:
  - other
tags:
  - bioinformatics
  - genomics
  - variant-calling
  - benchmark
  - giab
  - reproducible
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files: manifest.json
---

# VeriBench-Bio T1 — HG002 chr20 变异检出

这是 **VeriBench-Bio** 的第一个任务数据集：一个**答案已知、体积小、能在普通电脑上 30 分钟内跑完**的变异检出评测集。

造它的原因很简单：现有生信评测集要么重（需要 GPU、需要授权、跑 24–48 小时），要么真值不可靠（作者自己承认"真值不敢保证"）。这个数据集要解决的就是这两点。

---

## 这个任务是什么

**给你一份已经比对好的测序数据，请你找出这个样本哪里有变异。**

答案来自 **NIST 的标准品细胞系**——对错是可判定的，不是我们自己说了算。

## 内容

| 路径 | 说明 |
|---|---|
| `ref/chr20.fa` | 参考序列（UCSC hg38 chr20，公有领域） |
| `aln/HG002.chr20.30x.bam` | HG002 的比对结果，**仅 chr20 目标区域，降采样到 30×** |
| `truth/HG002_GRCh38_v5.0q_smvar.region.vcf.gz` | **真值**：GIAB/NIST v5.0q 小变异 |
| `truth/HG002_GRCh38_v5.0q_smvar.benchmark.region.bed` | 高置信区间（只在有把握的区域评分） |
| `sources.json` | 溯源事实（上游 URL、原始 md5、降采样参数） |
| `manifest.json` | **每个文件的 sha256** |

## 为什么真值可信

真值来自 **GIAB / NIST v5.0q**（`smvar` = 小变异），而非我们自行计算。

- 用 **v5.0q**：v4.2.1 自 2025-11 起已 deprecated
- **不用 HG001/NA12878**：其捐献同意**未明确覆盖商用再分发**
- 用 HG002：NIST 明确其 "consented for commercial redistribution"

## 数据是怎么做出来的（可复现）

源文件是 GIAB 的 `HG002.GRCh38.2x250.bam`，**整文件 121.79 GB**，显然不能整下。所以：

1. **远程按区域取**：`samtools view -b <远程 URL> <区域>` 只传输目标区段
2. **降采样**：`samtools view --subsample <比例> --subsample-seed <seed>`，比例由**实测覆盖度**算出（不是拍脑袋）
3. **真值裁剪**到同一区域

完整脚本见上游仓库的 `tasks/T1/data/prepare_data.sh`，**固定 seed，可重放**。

## 已知限制（写在这里，而不是藏起来）

- **只覆盖 chr20 的一个区段**，不是全基因组
- **预置 BAM，不考"比对"**：这是为了守住 30 分钟 CPU 预算而做的**刻意范围收缩**
- 源 BAM 的比对参考为 `GRCh38_full_plus_hs38d1_analysis_set_minus_alts`（取自 BAM `@PG` 行）；chr20 主 contig 坐标与 GRCh38 chr20 一致
- **`contains_human_data = true`**，但**非受控访问数据**、不涉及 dbGaP

## 怎么用

```bash
# 取数据
hf download <用户名>/biobench-lite-t1-hg002-chr20 --repo-type=dataset --local-dir ./t1-data

# 核对完整性（务必做）
python -c "
import json,hashlib,pathlib
m=json.load(open('t1-data/manifest.json'))
for f in m['files']:
    p=pathlib.Path('t1-data')/f['path']
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    print('OK  ' if h==f['sha256'] else 'FAIL', f['path'])
"
```

评测容器与判分器见上游仓库 `bio-eval/tasks/T1/`。

## 许可依据

- **数据本体**：NIST/GIAB 为**美国政府作品**（公有领域），另附 NIST 免版税全球许可
- **样本同意**：HG002 来自 PGP，NIST 明确说明其 *"consented for commercial redistribution"*
- **参考序列**：UCSC hg38，公有领域
- 本仓库**不是**由 NIST 或 GIAB 发布，也**未获其背书**

## 引用

使用本数据请引用 GIAB/NIST 的 v5.0q 发布，以及本数据集的上游仓库。具体引用格式待补（本项目仍在建设中）。
