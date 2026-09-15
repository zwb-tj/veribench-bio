---
license: other
license_name: us-government-work-public-domain-plus-cc0
license_link: https://www.ncbi.nlm.nih.gov/home/about/policies/
pretty_name: VeriBench-Bio T2 — ACMG 变异解读（去标识化证据包）
task_categories:
  - text-classification
  - question-answering
tags:
  - bioinformatics
  - genomics
  - clinical-genetics
  - acmg
  - benchmark
  - contamination-resistant
size_categories:
  - 1K<n<10K
---

# VeriBench-Bio T2 — ACMG 变异解读（去标识化证据包）

这是 **VeriBench-Bio** 的第二个任务数据集：给一个变异的**证据材料**，让模型按 **ACMG 规则**判断致病性。

**但题面里不会告诉你这是哪个变异。**

---

## 为什么这样设计：污染是"结构上"解决的

ClinVar 是公开数据库，大模型很可能已经把大量「变异 → 标签」背下来了。
如果题面给出变异名/HGVS/rsID，测到的就是**记忆**而不是**推理**。

**所以题面里绝不出现**：HGVS、rsID、基因组坐标、ClinVar/ClinGen accession、变异名、氨基酸改变。
**只给一个结构化证据包。**

> **记忆的对象是「变异 → 标签」这一对。题面里根本没有变异，就没有可背的东西。**

**三层防污染**：
1. **身份脱敏**（结构性）—— 见上
2. **时间切分** —— 只用 `CLINSIG_LAST_CHANGED` 落在 2024–2026 的条目（训练语料里不可能有）
3. **金丝雀配对**（占 25%）—— 见下

## 数据

| 文件 | 条数 | 说明 |
|---|---|---|
| `items.jsonl` | 3,789 | **题面**（2,836 真实题 + 953 金丝雀） |
| `truth.jsonl` | 3,789 | **真值**（分类 + 专家小组的 ACMG 判据码） |
| `audit.jsonl` | 3,789 | 溯源审计（含 HGVS / VariationID，**仅用于核实真值，勿当题面**） |

**本仓库是全量 4,726 的 `public` 子集（80%）。** 另有 20% 作为**永不公开的轮换集**，
用于将来检测"是否有人在公开集上过拟合"。

### 题面字段（`items.jsonl`）

```
item_id                     T2-00001          ← 不可反查（**不是** ClinVar ID）
gene / disease                                 ← 必要上下文，不是变异身份
mode_of_inheritance                            ← 来源：ClinGen
gene_disease_validity                          ← 来源：ClinGen（Definitive/Strong 为入池条件）
consequence_category                           ← 粗粒度（missense/nonsense/frameless…），**不给氨基酸改变**
population_frequency_band                      ← **分档**，不给精确值
population_popmax_band
canary / canary_of / canary_changed_field      ← 金丝雀标记
```

**频率为什么分档？** 分档边界刻意对齐 ACMG 阈值（PM2 罕见 / BS1 ≥1% / BA1 ≥5%）——
既保留推理所需信息，又降低"靠精确频率反查变异身份"的风险。

### 真值字段（`truth.jsonl`）

```
assertion                  专家小组结论原文
assertion_normalized       归一化到 5 类
criteria_met               **专家小组判定成立的 ACMG 判据码**（set-F1 的评分依据）
criteria_not_met
expert_panel               出具结论的小组（真值权威性的依据）
clinvar_variation_id / hgvs  逐题追溯用，**不出现在题面**
canary_expected            金丝雀配对题的预期方向
```

## 金丝雀（占 25%，**不计入主分**）

| 类型 | 做法 | 预期 |
|---|---|---|
| **频率翻转** | 只把频率档改成 `>=0.05`（BA1 区间） | 方向必须更偏良性 —— **这是 ACMG 规则推导的预期，不是我们编的真值** |
| **自洽性重复** | 证据完全复制，只换 ID | 答案必须**不变** —— 同题两答不一致，说明答案里含随机噪声 |

⚠️ **金丝雀只做诊断，不进主分的分母**：它是合成题，**没有专家小组真值**。
给它打准确率分就等于我们自己造真值。

## 评分（四个独立分量）

```
score = 0.6 × classification_credit + 0.4 × criteria_f1     ← 权重是声明式约定
```

| 分量 | 说明 |
|---|---|
| `classification_credit` | 有序尺度（B < LB < VUS < LP < P）上的部分分；**跨越 VUS 判到反方向额外乘 0.5** |
| `exact_accuracy` | 精确命中率 |
| `criteria_f1` | 判据集合 micro-F1 —— **"真推理 vs 蒙对标签"的判别器** |
| `directional_error_rate` | 把致病判成良性（或反之）的比例 |
| `canary_consistency` | 诊断量，**不计入主分** |

## 评分尺度标定（**发布前必读**）

| 基线 | 主分 | 分类部分分 | 精确命中 | 判据F1 |
|---|---|---|---|---|
| **oracle**（照抄真值） | **1.0000** | 1.0000 | 1.0000 | 1.0000 |
| all_vus（永远答中间档） | 0.4236 | 0.7060 | 0.1851 | 0.0000 |
| all_pathogenic | 0.3496 | 0.5826 | 0.2571 | 0.0000 |

⚠️ **有序尺度的部分分会奖励"答中间那一档"**：`all_vus` 的分类部分分有 **0.7060**，
精确命中却只有 **0.1851**。
→ **所以别只看主分。** 必须同时看 `exact_accuracy` 与 `criteria_f1`（退化基线是 **0**）。

## 许可与来源

| 来源 | 许可 | 用途 |
|---|---|---|
| ClinVar | **NCBI-PD**（美国政府作品，NLM 未施加使用限制） | 变异注释、分子后果、3★ 结论 |
| ClinGen（EREPO / CSpec / gene-disease validity） | **CC0 1.0** | 专家判据码、遗传方式、基因-疾病有效性 |
| gnomAD v4 | **CC0 1.0** | 等位基因频率 |
| ClinVar VCF 的 `AF_EXAC`/`AF_ESP`/`AF_TGP` | NCBI-PD | 极少数条目的频率回退来源 |

⚠️ **刻意排除的数据**：
- **dbNSFP 系 in-silico 预测分数**（REVEL / CADD / PolyPhen-2 / AlphaMissense…）—— **CC BY-NC-ND 4.0 + 商用付费**
- **gnomAD 中的 SpliceAI 注释** —— **CC BY NC 4.0**（含该列的文件整体排除）
- OMIM / GeneReviews —— 第三方版权

**本仓库不是由 NCBI、ClinGen 或 gnomAD 发布，也未获其背书。**

## 已知限制（写在这里，而不是藏起来）

- **频率来源比 gnomAD v4 旧**的条目有 4 条（回退到 ClinVar 的 AF_EXAC）
- **7 条**（0.2%）频率仍为 `unknown`（API 多次失败）
- **270 条**（7.6%）的基因-疾病有效性为 `unknown`（ClinGen 未收录该基因）
- **36 条**真值的判据 token 无法规范化，这些 token 被丢弃
- **只覆盖 VCEP/GCEP 已策展的 112 个基因**，不是全基因组
- **v1 不含任何 in-silico 预测证据**（许可原因，见上）—— 这是最大的证据缺口
- **尚未有真实模型作答过**；上表是合成基线

## 怎么用

> ### ⚠️ 状态：本数据集**尚未上传**（2026-09 实测）
>
> HF 仓库 `zwb-tj/biobench-lite-t2-acmg-variant-interpretation` **已创建，但存储为 0 B** ——
> 一个文件都没传（`hf repo list --format json` 实测 `storage = "0 B"`）。
> 所以下面那条 `hf download` **现在下下来是空的**。
>
> 待上传的是 `tasks/T2/data/public/` 里的 3,789 条（`items.jsonl` + `truth.jsonl` + `audit.jsonl`）。
> **`tasks/T2/data/{items,truth,audit}.jsonl`（全量 4,726 条）不得上传** ——
> 它们含轮换池 937 条的题面与答案，而轮换池的设计目标就是「**永不公开**」
> （见 `split_public_rotation.py` 与 `docs/DATACARD.md` §7.3）。
> 这条约束由 `scripts/verify_t2_rotation_isolation.py` 检查。

```bash
# 取数据（**上传完成后**才有内容）
hf download zwb-tj/biobench-lite-t2-acmg-variant-interpretation --repo-type=dataset --local-dir ./t2

# 判分（题面与真值都在数据里；判分器见上游仓库 tasks/T2/grade.py）
python3 grade.py --items t2/items.jsonl --truth t2/truth.jsonl \
                 --answers t2/answers.jsonl --out result.json
```

**作答格式**（每行一个 JSON）：
```json
{"item_id": "T2-00001", "classification": "Likely pathogenic", "criteria_met": ["PVS1","PM2"]}
```

## 引用

使用本数据请引用 ClinVar、ClinGen 与 gnomAD 的原始发布，以及本数据集的上游仓库。
具体引用格式待补（本项目仍在建设中）。
