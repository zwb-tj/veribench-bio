# DATACARD · VeriBench-Bio

> **本文件的规则**：每一句话都必须指向一个**可复核的证据**（HF 上的字节比对、
> 台账字段、CI 输出、或明确标为"未验证"）。凡是没验证的，一律写明"未验证"。
>
> 这份卡片的作用不是宣传，是**让第三方能在接手前就知道哪些能信、哪些不能**。

- 版本：v1（2026-09）
- 状态：**未发布**。两个 HF 数据集仓库当前均为 **Private**。
- 总许可：见 §1

---

## 1. 许可（逐层，不设统一许可）

| 层 | 许可 | 依据 |
|---|---|---|
| **代码** | Apache-2.0（`LICENSE` 已落地，正文与 apache.org 官方源**逐行一致**，由 `scripts/verify_license_text.py` 核对） | 见 `LICENSE` |
| **第三方组件** | 逐项列在 `NOTICE`，并**区分"已核验上游 LICENSE"与"仅有包元数据"** | `NOTICE`、`tasks/T1/licenses/README.md` |
| **T1 数据集内容** | 公有领域（GIAB / NIST 美国政府作品） | `tasks/T1/data/HF_DATASET_CARD.md` |
| **T2 数据集内容** | 逐条标注，来源为 ClinVar（公有领域） | `ledger/items.jsonl` 的 `license_spdx` |
| **rubric 题面** | CC BY 4.0（改写自 PMC OA 的 CC BY 论文） | `rubric/ledger/rubric_items.jsonl` |
| **容器内第三方组件** | 仅 MIT / BSD / Apache-2.0，**零 GPL** | SPEC §5.5、`tasks/T1/licenses/` |

**白名单**（`scripts/audit_licenses.py` 强制执行）：`CC0-1.0` / `CC-BY-4.0` /
`CC-BY-3.0` / `PUBLIC-DOMAIN`。

**明确排除**：
- `-NC-`（禁商用）、`-SA-`（传染）
- `-ND-`（禁衍生）—— **把一篇论文改写成一道题，本身就是衍生作品**，所以 ND 在此一律不可用
- 例：`dbNSFP` = CC BY-NC-ND + 付费商用 → **全部 in-silico 预测器被排除**；
  gnomAD 主数据是 CC0，但**其中的 SpliceAI 是 CC BY-NC 4.0**

⚠️ **两个已知的许可边界问题，尚未由法务确认**（SPEC §13.5）：
1. `"镜像内不得含 GPL"` 的字面要求**不可能满足** —— `bash`/`coreutils` 本身就是 GPL。
   实际执行的是"不含 GPL 的**分析组件**"，但这个语义需要法务确认。
   （**实测补充见 §5.2**：Debian 元数据一度声称 `bcftools` 因 GSL 而受 GPL 管辖，
   经四条实证排除 —— 但"不含 GPL 的分析组件"这个**语义**本身仍需法务拍板。）
2. `bwa-mem2` 声称 MIT，但它继承了 GPLv3 时代的代码；**核实前不得写"可商用"**。
   （v1 不需要 BWA，此项仅为将来预留。）

---

## 2. 逐条溯源（防"第 6 天翻车"的核心机制）

每一道题在 `ledger/items.jsonl` 里都能映射到条目，**17 个必填字段**（schema 强制）：

```
item_id  task  truth_type  source_type  source_ref  source_license_code
license_url  retrieval_date  license_spdx  redistribution_ok  commercial_ok
contains_human_data  human_data_basis  contains_restricted_data  visibility
derivation  review_status  created_at
```

**台账粒度（这里有个真实取舍，必须说明）**：T2 有 4,726 道题，但**来源完全相同**
（ClinVar 3★ + ClinGen EREPO + gnomAD）。逐题复制 4,726 行同样的 provenance 只是噪声，
不增加可溯源性。所以按**来源各一条**，并在 `derivation_note` 里写明该条覆盖哪些题目，
使"任意一题 → 台账条目"的映射**仍然确定且可核验**。

当前台账 **30 条**：T1 × 2（GIAB 真值 / UCSC 参考）、T2 × 4（ClinVar / ClinGen / gnomAD /
自造金丝雀）、rubric × 24（逐题）。

> ⚠️ **这一节曾经是假的。** 截至 2026-09 本轮之前，`ledger/items.jsonl` 是 **0 字节** ——
> T1、T2 这两个**已经上线 HF、跑过实测、做过字节比对**的支柱，**一条台账记录都没有**。
> README 第 1 条原则写着"没有台账条目的题目不得进集"，但没有任何东西在强制执行它。
> 现在由 `scripts/verify_datacard.py` 强制检查（空台账直接判失败）。

**审计器 `scripts/audit_licenses.py` 执行 R0–R12 + W1**，`--self-test` 16/16 通过。
其中三条最值得单独说：

- **R10**：非权威真值必须写明 `truth_note`（说明来源、为何不权威、锁定了哪个参考实现）
- **R11**：`truth_type=none` 的条目**不得公开**（无真值即不可计分）
- **R12**：`contains_human_data` 必须配 `human_data_basis` 依据枚举。**裸布尔不可审计** ——
  本项目就曾把 27 篇来源（含**蜜蜂**转录组、**大鼠**心梗模型、叙述性综述）一律标成
  `true` 而长期无人发现（SPEC §3.1）

**`human_data_basis` 的枚举在本轮补过一个值**：把它用于真实数据（gnomAD v4 频率）时才发现，
"**来自人类但已完全聚合、不含个体记录**"（聚合等位基因频率）在前四个取值里**没有安放处** ——
原枚举只有"个体数据/生物样本/二次文献转述/纯非人"。硬塞进任何一个都会误标，
所以补了 `human_aggregate_only`。**schema 的缺陷是在拿真实数据用它的时候才暴露的。**

---

## 3. 各任务的真值来源与污染风险

| 任务 | 真值类型 | 真值来源 | 污染风险 | 缓解 |
|---|---|---|---|---|
| **T1** 变异检出 | authoritative | GIAB / NIST v5.0q（HG002） | **低** | — |
| **T2** 变异解读 | authoritative | ClinVar **3★ reviewed by expert panel**（判据集取 ClinGen EREPO） | **极高** | 三层：结构去标识 + 时间切分 + 25% 金丝雀 |
| **rubric** 审稿式开放题 | consensus | 双标注 + 仲裁确立的共识 | 中 | **尚未取得**真实双标注（§6） |

**T2 的三层防污染（具体做法）**：
1. **结构去标识**：题面里不出现 HGVS / rsID / 坐标 / ClinVar ID / 氨基酸改变
2. **时间切分**：用 `CLINSIG_LAST_CHANGED`，**绝不用 `MDAT`**
   （NCBI 批量刷新会让 2026 年的 `MDAT` 占 3★ 的 92%，旧数据长得像新数据）
3. **金丝雀对**（25%）：配对条目用于检测污染

---

## 4. 已知限制（**这一节最重要**）

### 4.1 真值层面
- **T7/T8 若将来加入，必须单独分区。** 它们没有官方真值，只有"某个锁定版本的参考实现输出"，
  `truth_type=reference-implementation`，对外只能描述为**可复现性**，**不得与准确率榜混排**。
  参照实现必须唯一锁定 —— `kallisto ≠ salmon`，两者输出数值不可互换。
- **T1 是刻意的范围收缩**：只考 chr20:10–12 Mb（约 2 Mb）且**预置已比对好的 BAM**，
  不考比对。这是为了守住"全集 CPU <30 分钟"，不是能力缺失。

### 4.2 评测层面
- **rubric 支柱缺少人类天花板。** 核心方法论主张是"**人类之间的一致率是裁判可靠性的上限**"，
  而这条链需要**两位真人**独立标注。当前只有合成数据上的校准值，
  **不得当作结果发布**（SPEC §13.2）。
- **裁判自一致性 ≠ 效度。** 实测裁判重测 κ = 0.9636（v1.1），
  **高于**合成 fixture 上的人类天花板 κ = 0.8415。
  同一个模型当然比自己与别人之间更一致 —— 它报告的是**自身确定性**，不是判得对。
  （⚠️ 可比性缺陷：0.9636 来自真实 24 题，0.8415 来自合成夹具，跨数据集比较只能当提示。）
- **cross-criterion 重复计分未解决**：裁判定性指出多条标准共用同一句回答
  （如 R-0007 c1/c4、R-0011 c1/c4）。**仍在**（`rubric/README.md`）。
- **锚点可判性检查只覆盖数字型要件。** 文字型要件
  （如"未按泪液流率归一化"）抓不到，仍需人工复核。

### 4.3 上游来源的已知不可核实项
| 项 | 状态 |
|---|---|
| dbGaP DUA 页面 | **404** |
| EGA 条款 | **DNS 不可达** |
| GEO 政策页 | 只能读 **2024 年存档镜像**（reCAPTCHA 拦截） |
| PMC `oa_file_list.csv` / `oa.fcgi` | **404**（2026-08；仅 AWS Cloud Service / OAI-PMH / E-utilities / BioC API 合法） |
| ClinVar `pub/clinvar/txt/` | **404**，现路径为 `tab_delimited/` |

---

## 5. 已验证的事实（**带证据**）

> 与 §4 对照阅读。§4 是"我不知道的"，这里是"我验过的"。

### T1
| 项 | 值 | 证据 |
|---|---|---|
| HF 数据集 | `zwb-tj/biobench-lite-t1-hg002-chr20`，100.4 MB / 7 文件 | 重新下载后 **逐字节 sha256 比对通过** |
| 真实数据运行 | **39–55 秒**（五次独立端到端运行：55 / 46 / 41 / 39 / 43；取最慢的 55 秒对照 1800 秒预算） | 实跑 ×5 |
| 得分 | **0.84655**（SNP F1 0.9087 / INDEL F1 0.7844） | 实跑 |
| 调用量 | 12,254 变异 vs 真值 3,352 | 实跑 |
| 架构 | amd64 实跑通过；arm64 在 QEMU 下通过架构检查与 grader 自检 | 实跑（⚠️ arm64 用的是**另一个镜像**，见 §5.1） |
| 峰值内存 | 491–1101 MB（五次运行；与并发负载有关） | 实跑 ×5 |
| 复现性 | 五次运行**得分与变异数完全一致**（0.84655 / 12,254），仅耗时与内存有波动 | 实跑 ×5 |
| **默认路径可用** | 有一跑**刻意不覆盖** `REGION`/`BAM`，走 `run.sh` 自带默认值 → 正常跑通。此前每个 driver 都覆盖了默认值，所以**默认路径从没被执行过**（这正是两个 bug 藏身之处） | 实跑 ×1 |
| **不污染已发布数据** | `/data` 以**只读**（`:ro`）挂载即可跑通（参考 SDF 写到 `/out`）→ 跑任务不会改动数据集 | 实跑 ×1 |
| 评分器自检 | **1.0 / 0.25 两档均符合预期**（实跑确认） | `tasks/T1/selftest/run_selftest.sh`（容器内，用合成数据，不需要 GIAB）⚠️ **不是** `grade.py --self-test` —— T1 的 `grade.py` 没有这个 flag（2026-09 更正） |
| **自检已被自动跑** | 上一条的 1.0/0.25 现在由 `run_all_checks.py` **第 6g 步**每次执行 | 2026-09 补：此前它**只写在文档里**，没有任何自动检查在跑 |

### T2
| 项 | 值 | 证据 |
|---|---|---|
| 题量 | **4,726 条**（3,545 真实 + 1,181 金丝雀 = 25%） | 构建日志 |
| 泄漏检查 | **0 泄漏**，覆盖 40,170 个字符串字段 | 构建期门禁 |
| 容器端到端 | oracle 得分 **1.0** | 实跑 |
| 基线 | oracle 1.0000 / all_vus 0.4245 / all_pathogenic 0.3478 | 实跑 |
| HF 数据集 | **尚未上传**（HF 仓库 `zwb-tj/biobench-lite-t2-acmg-variant-interpretation` 已创建但**存储为 0 B**）。待上传的是 `tasks/T2/data/public/` 的 3,789 条；**轮换池 937 条永不发布** | 2026-09 用 `hf repo list` 实测：storage = 0 B |
| 镜像 | 123 MB，**构建期即执行泄漏门禁** | 构建日志 |
| **镜像 pin** | `sha256:f1bcfdea1ae5…`，绑定 `Dockerfile`/`run.sh`/`grade.py`/`items.jsonl`/`check_no_leakage.py` 5 个构建输入 | `tasks/T2/IMAGE_DIGEST.json`（2026-09 补：此前 T2 **连 pin 都没有**） |
| **镜像内容与源码逐字节一致** | `/work` 下 4 个文件与仓库源码 sha256 全等；**镜像内不含 `truth.jsonl`** | `docker cp` 取出比对（`verify_t2_claims.py` 自动跑） |
| **重数过的条数** | 4,726 = 公开 3,789 + 轮换 937（不重不漏）；金丝雀 1,181 | 2026-09 独立重数（非读文档） |

### 容器（T1）
| 项 | 值 |
|---|---|
| 镜像大小 | 356 MB（剥离 rtg 捆绑的 amd64 JRE 后，原 469 MB） |
| 当前源码对应的镜像 | `sha256:e75867d58f60…`（356 MB，由当前 `Dockerfile` 构建，实跑复现 0.84655 / 12,254；含四道检查的 GSL 门禁，见 §5.2） |
| 许可 | FreeBayes MIT / RTG Tools BSD-2 / samtools·bcftools·tabix·htslib MIT-Expat（**已读上游原文**，逐条在 `NOTICE` [A] 块列出 URL）/ OpenJDK GPL-2+Classpath（聚合） |
| GATK4 | **v1 不含**（许可负担，SPEC §5.6） |
| 实测许可陷阱 | 官方 GATK4 镜像里 `htsjdk-tribble` 是 LGPL-2.1（POM 谎称 MIT）、
`jgrapht` 是 LGPL-2.1/EPL-1.0 双许可 |
| **bcftools 的 GSL 陷阱（已实证排除）** | Debian 的 `bcftools/copyright` 写着「GSL … as is done for this Debian package」且 `debian/rules` 确有 `--enable-gsl`，字面读=GPL-governed。**实测：`bcftools polysomy` 不存在（上游仅 `USE_GPL=1` 才编）、无 `gsl_*` 符号、无动态依赖、无 GSL 库文件** → 本构建未启用 GSL。见 §5.2 |

#### 5.1 镜像 digest 曾经"pin 了个对不上的东西"（2026-09 修正）

这是本项目**最值得记下的一次自查**，因为它暴露的不是数字错，而是**检查本身的错**。

**事实**：

| | 值 |
|---|---|
| 三次早期实跑（`result.json`）记录的 digest | `sha256:c33862bb7ba588e4…` → 实测该镜像 **469 MB，里面仍有 `jre/lib/amd64/*.so`** |
| 当前 `Dockerfile` 构建出的镜像 | **356 MB**，因为第 99 行写着 `rm -rf /opt/rtg-tools/jre` |

也就是说：**被 pin 的那个 digest，不是当前 Dockerfile 能构建出来的镜像。**
Dockerfile 是在那次实跑**之后**才改进的（剥 JRE 瘦身 469→356 MB），
而 `result.json` 里的 digest **从来没有跟着更新**。

**为什么原来的检查没抓到**：它只问"`result.json` 里有没有 digest"——有，于是报 ✅。
**只验证存在性的检查，无法发现"对不对"。** 这与 §4 里其它教训是同一类。

**另一个连带问题**：那个旧镜像里捆着 **amd64 专用 JRE**，而它正是
Dockerfile 注释里写的、会在 arm64 上造成 `Exec format error` 的东西。
所以"amd64 + arm64 均通过"这句话，**两个架构用的其实是不同的镜像**。

**处置**：

1. 用当前 `Dockerfile` 重新构建 → `sha256:1f5c665b…`（356 MB，含修好的 `run.sh` 默认值）。
2. 在该镜像上**重新实跑**：得分 **0.84655**、变异 **12,254**，与前三次完全一致。
3. 新增 `IMAGE_DIGEST.json`：把**构建输入的源码哈希**（`Dockerfile`/`run.sh`/`grade.py`/
   `inspect_image.py`/`scripts/*.sh`/`licenses/*`，共 8 个文件）与镜像 digest 绑在一起。
   今后任何构建输入被改动，`scripts/verify_t1_claims.py` 会报
   **"记录的 digest 已与源码脱节，必须重建并重新实跑"** —— 而不是继续报 ✅。
4. 已做负向测试：改动 `run.sh` 一个字节 → 检查立刻失败；还原 → 通过。

#### 5.2 "零 copyleft"差点是假话：bcftools 的 GSL 陷阱（2026-09 实证排除）

这是本轮第二个"看起来更漂亮、实际更危险"的发现，而且**两边说法互相矛盾**：

| 来源 | 说法 |
|---|---|
| Debian `/usr/share/doc/bcftools/copyright` | "When linked with the GPL-licensed GNU Scientific Library (**as is done for this Debian package**), the resulting program **must be distributed under the GPL**." |
| Debian `debian/rules`（bcftools 1.16-1） | `dh_auto_configure -- --with-htslib=system **--enable-gsl** --with-cblas=gslcblas` |

**照字面读，本镜像里的 `bcftools` 是 GPL-governed**，那"工具链零 copyleft"就是假话。

**没有采信任何一方的文字，改为实测。** 决定性证据来自上游 `bcftools/Makefile`：

```
# The polysomy command is not compiled by default because it brings dependency
# on libgsl. The command can be compiled with `make USE_GPL=1`.
ifdef USE_GPL
    OBJS += polysomy.o peakfit.o
    GSL_LIBS ?= -lgsl -lcblas
endif
```

即 **`USE_GPL` 就是"要不要 GSL"的开关，它的可观察表现就是 `bcftools polysomy` 在不在。**
四条独立检查（都可在镜像内复现）：

| # | 检查 | 结果 |
|---|---|---|
| 1 | **行为（决定性）**：`bcftools polysomy` | `unrecognized command` → **未启用 GSL** |
| 2 | **字节级**：主程序 + **39 个插件**搜 `gsl_*`/`libgsl*`/`libcblas*` | 0 命中 → 同时排除**静态链接** |
| 3 | **动态依赖**：所有 `NEEDED` 项 | 无 libgsl/libcblas |
| 4 | **文件系统**：全盘找 `libgsl*`/`libcblas*` | 不存在 |

**结论**：Debian 的 `--enable-gsl` 并未把 GSL 编进这个 `bcftools`；那句 copyright 注释
对本构建**已过期**。"零 copyleft"成立 —— **但这是测出来的，不是抄来的。**

**同时修掉了门禁本身的三个盲区。** 原来的门禁只有 `ldd | grep libgsl`：

| 盲区 | 后果 |
|---|---|
| 静态链接看不见（`ldd` 只列动态依赖） | GSL 静态编入时，门禁**假通过**，而程序真的受 GPL 管辖 |
| **39 个插件根本没扫** | 插件是运行时动态加载的，不在主程序 `ldd` 里 |
| 完全不验行为 | 文本/依赖都可能与真实编译配置脱节 |

新门禁 `tasks/T1/scripts/check_no_gsl.sh` 跑完这四道检查，任一失败即中断构建；
并做了**负向测试**（`tasks/T1/scripts/_negtest_no_gsl.sh`）：注入假 `libgsl.so`、
让 `bcftools` 会应答 `polysomy`、往二进制里塞 `gsl_*` 字节 —— **三种注入都能让它失败**，
复位后重新通过。<br>
⚠️ **不要把门禁简化回 `ldd \| grep libgsl`**（Dockerfile 里已写明原因）。

**顺带纠正一个我自己的观察错误**：中途我用 `strings | grep -c gsl_` 得到 `0`，
差点当成"没有 GSL"。实际上 `strings`/`nm`/`readelf` **在这个镜像里根本没装** ——
那个 `0` 是"命令失败"，不是"扫描结果干净"。改用 Python 直接解析 ELF 字节才拿到真结果。
**工具缺失会被误读成阴性结果**，这是所有"扫描类"检查的通用陷阱。

### rubric
| 项 | 值 |
|---|---|
| 题量 | 24 题 / 101 条标准（`items/items_v1.2.jsonl`） |
| 校准（**非结果**） | 合成夹具上：人类天花板 κ(二次加权) 0.8415、裁判 vs 金标准 0.7091、相对天花板 0.8427 |
| 结构检查 | 0 泄漏（1.47M 字符全文比对）· 155 个数字 0 个查不到 · 27 篇人类数据裁决 27/27 一致 |
| 裁判重测 | v1.0 κ=0.9494 → v1.1 κ=0.9636 |

---

## 6. 复现方式

```bash
# 许可与安全门禁（16 个自检用例）
python bio-eval/scripts/audit_licenses.py --self-test
python bio-eval/scripts/audit_licenses.py bio-eval/ledger/items.jsonl

# T1：构建镜像 + 实跑 + 评分
bash bio-eval/tasks/T1/data/prepare_data.sh     # 需先下载 GIAB 数据
docker build -t veribench-bio/t1:dev bio-eval/tasks/T1
bash bio-eval/tasks/T1/run.sh

# rubric：一键 10 个环节
python bio-eval/rubric/run_all_checks.py

# 项目级：台账 + 许可门禁 + 卡片一致性 + LICENSE 正文比对
python bio-eval/run_all_checks.py

# 清室检验：只复制**会被发布的那部分**到临时目录，在那里重跑两级检查
# （慢；但它第一次跑就抓到 3 个"本地看不见、第三方必卡"的问题，见 §5）
python bio-eval/run_all_checks.py --clean-room
```

**第三方复现的现状**：
- **本轮实测：默认构建路径在当前网络下会失败。**
  `docker build --no-cache` 在 apt 安装阶段以 exit 100 失败 ——
  `deb.debian.org` 对 `samtools` / `tabix` / `libncurses6` / `unzip` 的 .deb
  持续返回 **502 Bad Gateway**。apt 自带的 `Acquire::Retries=3` 没扛住，
  于是在 Dockerfile 里加了一层**有界外层重试**（3 次、递增间隔）；
  实测三轮共约 320 秒后**仍然失败** → 说明这不是瞬时抖动。
- **文档记载的备用路径实测可用**：
  ```
  docker build --no-cache --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn -t veribench-bio/t1:mirror .
  ```
  构建成功，产物 **355.8 MB**（文档写 356 MB），
  且 `tasks/T1/inspect_image.py` 核对的 **9 项被断言属性全部成立**
  （无 R/GSL/MKL、`bcftools` 未链 `libgsl`、RTG 捆绑 JRE 已剥离、rtg 启动脚本已打补丁、
  `/licenses/` 随镜像分发、四个工具可运行、**rtg 能实际执行**）。
- **因此「第三方能构建」这一条现在依赖备用路径。** 这是诚实的现状：
  默认路径本身没写错，是上游 CDN 的问题；但**不能因此说"照着 README 就能构建"**。

> ⚠️ 这条也说明：**"构建成功"与"构建出来的东西满足文档断言"是两回事** ——
> 前者只说明 Dockerfile 语法没错。所以补了 `tasks/T1/inspect_image.py`，
> 把"镜像里有哪些性质被文档断言过"逐条到镜像里查，**包含行为验证**
> （真的跑一次 `rtg version`），而不只是文本检查。

- **清室检验已做**（`scripts/clean_room_check.py`）：只把**会被发布的那部分**复制到临时目录，
  在那里重跑两级检查。跑通了 —— 但**它第一次跑时失败了 3 项**，
  见下方"这一轮抓到什么"。
- **环境依赖清单已生成**（`scripts/check_env_deps.py`，**从 `ast` 扫 import 得出来，不是凭记忆写的**）：
  - **Python 第三方依赖：零**。全部 63 个 `.py` 只用标准库。
    → 分析流水线**只需一个 python3**，这是复现风险最小的一类结构。
  - `jsonschema` 是**可选**依赖，只用于 `validate_schemas.py`；没装时该步输出 `SKIP` 并**明说"本次未校验"**。
  - 需 **Python ≥ 3.10**（用了 `X | None` 类型标注语法）。
  - Docker：2 个 Dockerfile（T1 / T2），只在这两个任务的**工具链**里需要。
  - 网络端点 11 个：`gnomad.broadinstitute.org`、`www.ncbi.nlm.nih.gov`、
    `ftp.ncbi.nlm.nih.gov`、`pmc-oa-opendata.s3.amazonaws.com`、`www.nist.gov`、
    `hgdownload.soe.ucsc.edu`、`genome.ucsc.edu`、`clinicalgenome.org`、`github.com`、
    `creativecommons.org`、`www.apache.org`。
- **尚未由第三方独立复现过**，也**未做过真正的 clean-CI**（本机清室 ≠ 另一台机器）。

### 这一轮清室 + schema 检验抓到什么（保留记录）

**① 清室检验第一次跑，3 项失败** —— 全是同一类问题：**脚本假设"只有本地才有"的输入存在**。

| 失败 | 根因 | 修法 |
|---|---|---|
| `classify_human_data.py` 报"一篇都没找到" | `items/sources/`（论文全文）**刻意不发布**，本地有、第三方没有 | 目录不存在时输出 `SKIP:` 并退出 0，**明确说"没跑"而不是"跑错了"** |
| `precheck_items.py` `FileNotFoundError` | 依赖 `sources/manifest.jsonl`，同样不发布 | 改为**明说"标题比对与 n-gram 检查本次未执行"**，不静默跳过 |
| `scale_reliability.py` **ZeroDivisionError 崩掉** | `judge_blind/_mapping.json` 会发布（小），但 `judge_out*/` 不发布 → 配对数 n=0 → `exact / n` 除零 | 加 n=0 守卫，输出 `SKIP:` |

**这三条都不是"本地跑得通"能发现的** —— 它们只在"拿走不发布的东西"之后才暴露。

**顺带定了一条约定**：`run_all_checks.py` 现在把 `SKIP:` 与通过**分开显示**（⏭ vs ✅）。
"没跑"既不能算通过（会掩盖问题），也不该算失败（会让第三方卡在假故障上）。

**② 加 schema 校验时，它立刻发现 `schema/ledger.schema.json` 本身是非法 JSON。**

我在 JSON 串里混了 ASCII 双引号（和我在 Python 里犯过七次的是同一类错）。
**而审计器照样通过 —— 因为它根本不读 schema。** 也就是说：

> 本轮之前，**schema 与数据可以各自漂移而没有任何东西会发现**。
> 101 条标准、30 条台账"合不合 schema"，只靠我在命令行里手动跑过几次。

现在这一步进了自动检查，并且额外比对**"必填字段的两个真源"**
（schema 的 `required` 与审计器的 `REQUIRED_FIELDS`）是否一致 —— 目前 17 : 17 一致。

---

## 7. 发布前必须完成

- [x] ~~落地 `LICENSE`（Apache-2.0 全文）+ `NOTICE`（第三方组件逐项）~~ →
      **已完成**。LICENSE 正文取自 apache.org 官方源并**逐行比对通过**
      （不凭记忆敲法律文本）；NOTICE 分两块：**[A] 已核验上游 LICENSE** 与
      **[B] 仅有包元数据、未逐项核验**，并单列"刻意排除的组件及原因"
- [ ] 法务确认 §1 的三个边界问题
- [ ] 取得**真实人类双标注**并算出天花板（rubric 支柱的硬阻塞）
- [x] ~~补齐 `docs/SAFETY.md`~~ → **已完成**
- [x] ~~清室检验~~ → **已完成并跑通**（`scripts/clean_room_check.py`，本轮首次跑出 3 个真问题，见 §5）
- [x] ~~环境依赖清单~~ → **已完成**（`scripts/check_env_deps.py`，从 import 扫出来的；
      **Python 第三方依赖为零**，Python ≥ 3.10，11 个网络端点已列明）
- [ ] **真正的 clean-CI**（在另一台机器/容器里从零 clone 并跑）
- [ ] 第三方**实机**验证 11 个网络端点的可达性（本机可达不等于别人可达）
- [ ] HF 仓库由 Private 改为 Public（**当前命令**：
      `hf repos settings <repo> --repo-type dataset --private false`）

**一条诚实说明（2026-09 更新）**：`NOTICE` 里原先把 `samtools` / `bcftools` / `htslib`
的 MIT 标注放在 **[B] 块**（"仅有包元数据，未核验上游原文"），并明说"不能假装已经核过"。

**现在这一项已经真的去核了**：按镜像里实际的版本（samtools 1.16.1-1、bcftools 1.16-1、
htslib 1.16+ds-3）逐个 tag 读了上游 `LICENSE` 原文，三条链接写进 `NOTICE` 的 [A] 块。
同时发现 `htslib` 的 `cram/` 子目录是 Modified-BSD-3（不止 MIT），已补上。

**仍未逐项核验的**（继续留在 [B] 块，不混进 [A]）：OpenJDK 与 Debian userland。
`NOTICE` 的 [A]/[B] 划分现在由 `scripts/verify_notice.py` 强制核对 ——
[A] 的每一条都必须给出上游 LICENSE 出处，否则检查失败（已做负向测试）。

#### 7.1 T2 的"生命线"检查器本身有两个漏检（2026-09）

T2 的防污染是**结构性**的：题面里没有变异身份，模型就没有可背的东西。
所以 `check_no_leakage.py` 是 T2 的生命线 —— 它报"0 泄漏"，这个任务才成立。

本轮对这条生命线做了**变异测试**（把已知阳性逐个注入，看它会不会报错）。
结果发现**它自己有两个漏检，而 docstring 明写着会查这两类**：

| # | 坏 pattern | 后果 | 怎么发现的 |
|---|---|---|---|
| ① | `RefSeq/转录本 accession`：`\b(N[MCGRX]\|X[MR]\|ENST\|LRG_)\d{4,}` | **匹配不到任何标准 RefSeq accession** —— 真实写法 `NM_000277.3` 中间有**下划线**，而 pattern 要求数字紧跟 `NM`。实测 **7/11 种形态永远漏检**，包括 `NC_/NG_/NR_/XM_/XR_/LRG_`，以及**真值 HGVS 里真实存在**的 `NM_001754.5`（出现 376 次）等 | 注入 `NM_000277.3` → 检查器**退出码 0** |
| ② | `变异 ID 形态`：`\b\d{1,2}-\d{5,}-\d+-[ACGT]+\b` | 只认**四段**形态 `12-102852862-1-G`；实测该形态在本项目数据里**从未出现过（0 处）**，而真正危险、且**完全漏检**的是**三段**的 `12-102852862-G-T`（染色体-位置-参考-替代），它直接泄露身份 | 自检里钉的阳性样本没匹配到 |

**两个都必须强调同一件事**：checker 的 **docstring 写着会查**，代码**实际查不到** ——
**自述覆盖 ≠ 实际覆盖**。这正是本项目 §3.1 反复记的那一类。

**处置**：

1. 修 ①：下划线用 `_?` 兼容两种写法 → `\b(N[MCGRX]_?\d{4,}|X[MR]_?\d{4,}|ENST_?\d{4,}|LRG_?\d+)`
   修完后 **11/11 种形态全部命中**。
2. 修 ②：第 3 段允许"数字或碱基"（两种形态的第 3 token 不同）→
   `\b\d{1,2}-\d{5,}-(?:\d+\|[ACGT]{1,10})-[ACGT]{1,10}\b`
3. **误报验证**：新 pattern 对**全部 4,726 条题面的所有字符串字段**扫描，
   误报 **0 处**（重点确认没误伤 `population_frequency_band` 的 `0.0001-0.001` 这类值）。
4. **新增 `--self-test`**：8 类 pattern 各钉已知阳性（共 32 个），
   任何一条匹配不到即**失败**。已接入 `run_all_checks.py`。
5. 因为 `check_no_leakage.py` 是 T2 的**构建输入**，改它触发了镜像 pin 检查
   （"pin 已与源码脱节"）—— 于是**重建镜像 + 重跑 oracle**：
   三个基线（1.0 / 0.424485 / 0.347792）与重建前**完全一致**，随后重新 pin。
   **这正是那条 pin 检查存在的意义**：它逼着"改了检查器"必须重新验证一遍。

**修完后重跑真实数据**：4,726 条 / 40,170 个字符串字段，仍然 **0 泄漏** ——
也就是说这两个漏检**目前没有造成实际泄露**，但它们本来会**让未来的泄露静默通过**。

---

#### 7.2 两个"没有消费者"就烂掉的东西（2026-09）

这一轮抓到的问题有个共同点：**它们都在"没人看"的地方腐烂。**

**① T2 的两个 schema 从来没有任何代码引用**

`tasks/T2/schema/t2-item.schema.json` 与 `t2-truth.schema.json` 各自带着一个
**非法的 ASCII 双引号**（写在中文说明串里），**JSON 根本无法解析** ——
它们就这样坏了很久。原因很简单：**全仓没有任何代码 `import` 或读取它们**，
所以没有任何工具会在读的时候炸。

> **"有文件"不等于"有约束"。** 一个不被消费的 schema，既不会报警，
> 也不再约束任何数据 —— 它只是两坨看起来像规范的字节。

处置：新增 `scripts/verify_json_files.py`（全仓 JSON/JSONL 解析检查，报精确行列）
当场扫出；随后把两个 schema 接上真实数据 ——
`validate_schemas.py` 现在会拿它们校验 **4,726 条题面 + 4,726 条真值**（全部通过）。

**② `scripts/not_published.json` 被我自己写坏**

我在给一条说明加文字时，在 JSON 字符串里用了 ASCII 双引号（中文串内）。
**这是同一个错误在本项目的第 9 次**（前 8 次都在 Python 中文串里）。
发现纯属运气：下一个要读它的脚本刚好炸了。

而它的后果比"一个文件坏了"严重得多：它是 `clean_room_check` 与
`verify_doc_links` 的**共享真源** —— 它一坏，"什么算不该发布"这个判断
就同时对两个工具失效。

处置同上：`verify_json_files.py` 已进常规检查，这类错误此后 100% 被抓。
自检里专门放了"我犯过的那种错"作为用例。

**③ 顺带：T2 连镜像 pin 都没有**

T1 修好"digest 绑定构建源码"之后，T2 漏着。这属于同一个缺陷类。
处置：把 `record_image_digest.py` 从 `tasks/T1/scripts/` 提到仓库级并参数化
`--task T1|T2`，一条检查管两个任务（而不是复制第二份）。

> **本轮的通用教训**：修完一处，必须立刻问 **"同一个缺陷类还有谁？"**
> 本轮连续三次撞上同一个模式（digest 只做 T1、`_runs` 只登记 T1、schema 没人管），
> 说明**"逐个修"这个做法本身不够** —— 要把检查提成"管所有任务"的形式。

#### 7.3 T2 的答案差点跟着仓库发出去（2026-09，**未实际泄露**）

这是本轮最需要留档的一条，因为它差点让一句**对外声明变成假话**。

**声明**（两处都写着）：

> `tasks/T2/data/split_public_rotation.py`：rotation 20% ——「**永不公开**」，
> 用于将来检测"是否有人在公开集上过拟合"
> `docs/DATACARD.md`：「公开 3,789 条；**轮换池 937 条从未发布**」

**实测事实**：

| 文件 | 内容 | 当时是否在 `not_published.json` 里 |
|---|---|---|
| `tasks/T2/data/items.jsonl` | 全量题面 4,726 条（**含轮换池 937 条题面**） | ❌ 不在 |
| `tasks/T2/data/truth.jsonl` | 全量答案 4,726 条（**含轮换池 937 条答案**） | ❌ 不在 |
| `tasks/T2/data/audit.jsonl` | 全量审计记录（含逐题证据） | ❌ 不在 |

后果：`clean_room_check` 一直把这三个文件当作**"会被发布的文件"**复制进清室目录。
实测确认发生过（在三个历史清室目录里都找到了 `truth.jsonl`）。

> ⚠️ **必须说清楚**：这三个文件**当时并没有真的对外发布** ——
> T2 尚未上传 HuggingFace（`tasks/T2/README.md` 的未闭合项里还挂着这一条），
> 仓库也不是 git repo。所以这是**潜在泄露，不是已发生的泄露**。
> **但"未被发现"和"没有问题"是两件事**：一旦按原样打包发布，声明立刻变成假话。

**为什么会发生**：`not_published.json` 是**枚举式**的 —— 谁写清单谁记得加。
T2 的切分脚本产出 `public/` 与 `rotation/` 两个目录，作者记得把 `rotation/` 排除了，
但**忘了全量文件同样含轮换池内容**（全量 = public + rotation）。
这与 T1 的 `_runs_repro3`、T2 的 `_runs` 是**同一个漏法**（见 §7.2）。

**处置**：

1. 把 `data/{items,truth,audit}.jsonl` 三个文件登记进 `not_published.json`（并写明理由）。
2. **新增 `scripts/verify_t2_rotation_isolation.py`** —— 把这句话变成可执行的检查：
   · 全量文件是否**确实**覆盖轮换池 id（覆盖了 → 它们就不能发布）
   · 覆盖了却**没**声明不发布 → **失败**
   · `public ∪ rotation == 全量` 且不相交
   · `public/truth` 不得含任何轮换池答案
   · `public/README.md` 必须**逐字节**等于数据集卡
   A 与 B 必须**同时**成立声明才为真：只有 A 没 B = 真的会泄露；
   只有 B 没 A = 声明空转。已做负向测试（3 个必须失败的用例）。
3. 由此连带修了两处**只在清室检验里才现形**的缺陷（详见 §4.3 的说明）：
   · `verify_doc_links.py` 的白名单只做前缀匹配，文档里写目录本身
     （`tasks/T2/_runs`，不带尾斜杠）会被误报死链；
   · `record_image_digest.py` 把 T2 的 `tasks/T2/data/items.jsonl` 当构建输入，
     而它现在**刻意不发布** → 清室/新 clone 里必然缺席。
     **"缺席"与"源码漂移"必须分开报**（新增 `Unavailable` 态，缺席时 SKIP 而非报错）——
     否则假警报会训练人忽略真警报。
4. **数据集卡不再手工复制**：`tasks/T2/data/public/README.md` 原是一份
   **手工复制的陈旧副本**（7,223 B vs 卡片 8,043 B），缺了"尚未上传"警示 ——
   原样上传就会在 HF 上挂一张写错状态的卡。现改为
   `split_public_rotation.py` **每次从卡片重新生成**（并强制 `newline=""`，
   否则 Windows 上 `\r\n` 会让副本与真源逐字节不同、哈希对不上）。

---

## 8. 引用与致谢

真值来自：GIAB/NIST（HG002）、ClinVar / ClinGen（EREPO）、PMC OA（CC BY 论文）。
工具：FreeBayes、RTG Tools、hap.py、samtools/bcftools/htslib。

**免责**：本基准用于评测方法学能力，**不用于任何临床决策**。
T2 条目描述的是 ClinVar 已归档的历史解读，不代表当前临床意见。
