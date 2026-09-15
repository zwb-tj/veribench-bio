# T1 · 变异检出（Variant Calling）

> 状态：**任务定义与容器已写好，尚未在真实数据上计时验证**（本机 Docker daemon 未运行）。
> 上游依据：`../../SPEC.md` §4.2 / §4.4

---

## 这道题在考什么（用湿实验的话）

**给你一份已经比对好的测序数据，请你找出这个样本哪里有变异。**

就像一份已经做好的样本，让你跑一遍变异检出流程。**答案来自 NIST 的标准品**——所以对错是可判定的，不是我们自己说了算。

## 输入（题目给的东西）

| 文件 | 说明 |
|---|---|
| 参考基因组 | GRCh38 **chr20** 的 FASTA + `.fai` |
| 比对结果 | HG002 的 BAM + `.bai`，**只保留 chr20 10–12 Mb**（即"比对"这一步已经替你做完了） |
| 高置信区间 BED | GIAB 的 benchmark BED —— 只在**有把握的区域**里比，避免拿参考基因组的模糊区扣分 |

## 输出（要交的东西）

一个 VCF：`calls.vcf.gz` + `calls.vcf.gz.tbi`，样本名必须是 **`HG002`**。

## 怎么判分

用 **GIAB / NIST v5.0q 的真值 VCF** 与你的 VCF 比对，由 **RTG `vcfeval`（BSD-2-Clause）** 计算
**SNP 与 INDEL 各自的 精确率 / 召回率 / F1**。

- 真值类型：**authoritative**（权威公开真值 —— 这是本任务与 T7/T8 的根本区别）
- 判分器：`grade.py`（见同目录）

---

## 三个必须写清的设计约束

### ① 为什么预置 BAM、只考检出？
为守住 **30 分钟 CPU-only** 预算。把"比对"这一步预先做掉，只考变异检出。
**这是刻意的范围收缩，不是能力缺失** —— DATACARD 里必须写明，不能让人误以为它测全流程。

### ② 计时口径（必须诚实标注"计什么、不计什么"）

`wall_clock_sec` **计**：
- 从参考基因组 + BAM 就绪开始，到 `calls.vcf.gz` 产出（含归一化与索引）
- 评分（`vcfeval` 运行）**单独计时**，不计入任务耗时

`wall_clock_sec` **不计**（属环境准备，非任务能力）：
- 数据下载
- 参考基因组 SDF 格式转换（`rtg format`，一次性）

**理由**：如果把环境准备算进去，这个数字反映的就是网速而不是能力；但把评分算进去又会惩罚"产出更大 VCF"的解法。所以分开报，**两项都公开**。

### ③ 样本名必须对齐
`vcfeval` 按**样本名**匹配 baseline 与 query。若解法输出的样本名不是 `HG002`，
判分器会先用 `bcftools reheader` 对齐（**这一步会记入日志**，因为它可能掩盖问题）。

---

## 真值与数据来源（许可已核验，文件名已实测确认）

| 资源 | 确切来源 | 本数据集采用 | 许可 |
|---|---|---|---|
| 真值 VCF | `v5.0q/HG002_GRCh38_v5.0q_smvar.vcf.gz` | 裁剪到目标区域 | 美国政府作品 / 公有领域 |
| 高置信区间 | `v5.0q/HG002_GRCh38_v5.0q_smvar.benchmark.bed` | 裁剪到目标区域 | 同上 |
| 比对结果 | `NIST_Illumina_2x250bps/novoalign_bams/HG002.GRCh38.2x250.bam` | 取区域后降采样到 30× | 美国政府作品；**HG002 明确同意商用再分发** |
| 参考序列 | UCSC `hg38/chromosomes/chr20.fa.gz` | 原样 | 公有领域 |

**实测事实（2026-09，不是推测）**：
- 源 BAM 整文件 **121.79 GB**；覆盖度实测约 **70.6×**（不是 300×）；官方 md5 `56c30eaa4e2f25ff0ac80ef30e09d78e`
- 目标区域 **chr20:10,000,000–12,000,000**（2 Mb），区域 BAM **76 MB**
- 降采样比例 **0.425110**（seed=42）→ 三个窗口校验：**29.53× / 29.11× / 29.52×**（目标 30×，偏差 <3%）
- 真值在该区域内共 **3,352 个变异**（F1 的统计量足够）
- 参考序列 chr20 长度 **64,444,167 bp**（与 GRCh38 chr20 一致 ✓）
- `samtools flagstat`：237,739 reads，99.19% mapped，98.32% properly paired
- **`samtools` 可经 HTTPS 直接按区域读该远程 BAM**（无需下载 121 GB）

⚠️ **不用 HG001 / NA12878** —— 其捐献同意**未明确覆盖商用再分发**（见 SPEC §5.4）。
⚠️ **v4.2.1 自 2025-11 起 deprecated**，本任务用 **v5.0q**。

---

## 容器内容与许可

全链路**零 copyleft**（见 SPEC §4.4）：

| 组件 | 许可 |
|---|---|
| `samtools` / `bcftools` / `tabix` / `htslib` | MIT |
| `freebayes` | **MIT**（已亲手读 LICENSE 原文） |
| RTG `vcfeval` | **BSD 2-Clause**（已亲手读 LICENSE.txt 原文） |
| `default-jre-headless`（OpenJDK） | GPL-2 **WITH Classpath-exception-2.0** → 按 SPEC §5.6⑤ 属**假阳性放行** |

**镜像内含一条许可门禁**（构建时执行）：若 `samtools`/`bcftools`/`freebayes` 的动态依赖里出现
`libgsl`，构建**直接失败** —— 因为启用 GSL 会使 `bcftools` 转为 GPL-governed。

> 说明：**v1 镜像不含 GATK4**。它是 Apache-2.0，但官方运行环境会引入专有 Intel oneMKL、
> GPL 的 R/GSL、LGPL 的 `htsjdk-tribble`（不可剥离）（见 SPEC §5.6）。换 FreeBayes 后这些问题同时消失。

---

## 已完成并实测验证

- [x] **镜像已构建成功**：`veribench-bio/t1:dev`，**356 MB**（samtools 1.16.1 / bcftools 1.16 / freebayes 1.3.6 / OpenJDK 17 / RTG 3.12.1）
      —— ⚠️ 2026-09 更正：此处原写"469 MB"，那是**剥离 rtg 捆绑 JRE 之前**的旧尺寸；
      剥离后是 356 MB（见 `Dockerfile` 第 99 行与 `docs/DATACARD.md` §5.1）
- [x] **许可门禁在构建时真实执行并通过**；并**实测确认 `samtools`/`bcftools`/`tabix`/`freebayes` 都未链接 `libgsl`**
      （这条此前被我标为"待核实"，现已闭合——本项目里 `bcftools` 不会因 GSL 转为 GPL-governed）
- [x] **判分器自检通过**（合成数据，无需 GIAB）：
      - 完美解法 → `score = 1.0`（SNP F1 = 1.0，INDEL F1 = 1.0），`status = ok`
      - 部分解法（1 对 1 错 1 漏）→ `score = 0.25`（SNP F1 = 0.5，INDEL F1 = 0），且**正确记录"解法未产出该类型变异"**

      **复现命令**（⚠️ 2026-09 更正：这**不是** `grade.py --self-test` ——
      T1 的 `grade.py` 根本没有那个 flag，文档此前写错了）：

      ```bash
      docker run --rm \
        -v "$PWD/selftest:/selftest:ro" \
        veribench-bio/t1:dev -lc "bash /selftest/run_selftest.sh"
      ```

      自检脚本在 `selftest/run_selftest.sh`，用 `make_synthetic.py` 造 2 kb 合成参考，
      再跑 `assert_results.py` 断言 FP/FN 计数与 problem 记录。**已实跑确认 1.0 / 0.25。**
- [x] 自检过程中发现并修掉判分器自身两个 bug：
      ① `rtg vcfeval` 拒绝写入已存在目录 → 必须先删；
      ② 测时长误用挂钟 `time.time()`（容器时钟跳变导致出现 `grade_sec = -11.9`）→ 改用单调时钟 `time.monotonic()`
- [x] **数据准备脚本已跑通**：从 121.79 GB 的远程 BAM 按区域取到 76 MB，降采样到 30×（实测 29.1–29.5×）
- [x] **修掉一个"假成功"bug**：Dockerfile 的 `ENV OUT_DIR=/out` 与数据脚本的 `OUT_DIR` 撞名，
      导致 100+ MB 数据写进**未挂载**的 `/out`、容器删除后全部丢失，而脚本仍以 0 退出。
      现改用 `DATA_DIR`，并在脚本末尾**断言真的产出了文件**（否则 exit 4）。
      这个 bug 是被 `make_manifest.py` 报出的"文件数：0"暴露的。
- [x] **✅ 真实数据端到端跑通**（2026-09-12，16 CPU）—— **这是 D2 的出口标准**：

  | 项 | 实测 |
  |---|---|
  | **变异检出（freebayes）** | **55 秒**（门禁 1,800 秒，**只用 3%**） |
  | 评分（vcfeval） | 11.4 秒 |
  | **主分 `score` = mean(F1_snp, F1_indel)** | **0.84655**（`status = ok`，无 problem） |
  | SNP | F1 **0.9087**（P 0.8768 / R 0.9429；TP 2512 / FP 353 / FN 152） |
  | INDEL | F1 **0.7844**（P 0.8569 / R 0.7232；TP 431 / FP 75 / FN 165） |
  | 峰值内存 | 1,100.8 MB |
  | 产出变异 | 12,254 条（真值 3,352 条） |

  完整输出、复现命令与"怎么读这个数字"见 **`baseline/README.md`**；原始产物在 `baseline/`。

  ⚠️ **这不是"题目的上限"，是"参考基线"**：默认参数、未调优（没调过滤阈值、没加 `--dbsnp`、没做 BQSR），
  且输入是降采样到 30× 的数据。用途是**环境自检**与**弱基线对照**，不是成绩。

- [x] **发现 30 分钟预算有 32 倍余量** → 将来若需要更大统计量，可把区域从 2 Mb 扩到 10 Mb
      （真值变异数从 3,352 增到约 1.6 万）仍在预算内。v1 保持 100 MB 小体积，
      以兑现"任何人都能用笔记本复现"的承诺。

- [x] **发现并修掉一个会毁掉"任何人可复现"的架构陷阱**（D9 前置排查）：

  **症状**：镜像里 RTG Tools 来自上游的 `rtg-tools-3.12.1-**linux-x64**.zip`，
  而这个包里**捆了一个 amd64 专用 JRE**（`jre/lib/amd64/*.so`），
  且 `rtg` 启动脚本会**优先**用它：
  ```bash
  if [[ -x "$THIS_DIR/jre/bin/java" ]]; then
      RTG_JAVA="$THIS_DIR/jre/bin/java"   # ← 在 arm64 上就是 Exec format error
  ```
  → 在 Apple Silicon / arm64 服务器上**判分器会直接跑不起来**。

  **修法**：删掉捆包 JRE（`rm -rf /opt/rtg-tools/jre`），并在 `/etc/rtg.cfg` 写 `RTG_JAVA=java`
  强制走 Debian 的 `default-jre-headless`（多架构）。
  **副作用还是正向的**：镜像 **469 MB → 356 MB**。

  **并且加了一道构建期门禁**（架构中立性检查）：断言 `jre` 目录不存在、
  `/opt` 与 `/usr/local` 下无 `amd64`/`x86_64` 专用路径、且 `rtg version` 真的能跑。
  **把"能不能在别的 CPU 架构上跑"变成构建期可验证的事，而不是等别人踩坑。**

- [x] **⚠️ 而上面那个 JRE 只是第一个陷阱。第二个更致命，是门禁抓出来的**：

  上游 `rtg` 启动脚本**开头第一段**就硬编码了架构检查：
  ```bash
  elif [[ "$(uname -m)" != "x86_64" ]]; then
      echo "Sorry, you must be running a 64bit operating system."
      exit 1
  fi
  ```
  → **在任何非 x86_64 架构上，`rtg` 会 0.1 秒内直接 exit 1。**

  **关键线索是"0.1 秒"**：模拟下 JVM 启动要好几秒，0.1 秒失败**不可能是 Java 的问题**，
  只可能是 shell 包装脚本自己退出——顺着这条线索才挖到那一行。

  **修法**：`scripts/patch_rtg_launcher.sh` 把该条件改为**恒假**，保留包装脚本其余逻辑；
  补丁脚本带 `--self-test`（**含行为检查**），并已记入 `licenses/MODIFICATIONS.md`。
  （RTG Tools 为 BSD-2-Clause，允许修改，但必须声明。）

  > 补丁第一版把条件写成 `!= ""`，而 `uname -m` 永远不为空 → **恒真 → 全架构都失败**。
  > 文本检查完全看不出来，是**行为自测**抓到的。**验证行为，不要只验证文本。**

- [x] **✅ arm64 已实测通过**（本机 QEMU 模拟，`docker buildx --platform linux/arm64`）：

  | 检查 | amd64 | arm64（模拟） |
  |---|---|---|
  | 构建 | ✅ | ✅ |
  | 架构中立性检查 | ✅ | ✅ |
  | `rtg version` | ✅ `RTG Tools 3.12.1` | ✅ `RTG Tools 3.12.1` |
  | samtools / bcftools / tabix / freebayes / java / python3 全部可运行 | ✅ | ✅ |
  | **判分器自检** | **1.0 / 0.25** | **1.0 / 0.25** |

  ⚠️ **但这不等于"已在 Apple Silicon 上验证过"**：QEMU 模拟**不代表原生 arm64**——性能会差很多倍，
  且模拟层可能掩盖真实硬件上的差异。原生 arm64 验证仍是 **D9 未闭合项**。

  > ⚠️⚠️ **2026-09 追加的实质警告（这条比上面那段更重要）**
  >
  > 上表那次 arm64 验证用的是**当时的**镜像，而那个镜像里的 `run.sh`
  > **带着两个错误默认值**（`BAM` 少了 `.30x`、`REGION` 写成 10–20 Mb，见本文件"输入"一节）。
  > 本机 `veribench-bio/t1:arm64` 实测仍然带着这两个值：
  >
  > ```
  > REGION="${REGION:-chr20:10000000-20000000}"  # 【历史错误】改前
  > BAM="${BAM:-${DATA_DIR}/aln/HG002.chr20.bam}" # 【历史错误】改前
  > ```
  >
  > 而且**本轮无法重建/重跑 arm64 来修**：本机的 arm64 模拟已经不工作
  > （`docker run --platform linux/arm64 ... → exec format error`）。
  >
  > 所以现状是：**"arm64 验证通过"只对"修 `run.sh` 之前的那版镜像"成立。**
  > 它在当时是真实的（那时默认值本来就没被用到 —— 因为 driver 都覆盖了它们），
  > 但**不能**据此说"当前镜像在 arm64 上验证过"。
  > 结论：**arm64 需要在一台能跑 arm64 的机器上，用当前 `Dockerfile` 重新构建 + 重跑。**
  > 这正是 D9"外部复现"要解决的事，此处不假装已完成。

- [x] 验证：删掉捆包 JRE 后 `rtg` 走系统 Java 正常（`Product: RTG Tools 3.12.1`），
      且**判分器自检仍然 1.0 / 0.25 通过**（删错了判分器就废了，所以必须回归测一遍）

## 未闭合项（不得假装已完成）

- [x] ~~arm64 镜像构建验证~~ → **已在 QEMU 模拟下全部通过**（构建 + 架构中立性检查 + 判分器自检 1.0/0.25，与 amd64 一致）
- [ ] ⚠️ **arm64 需要重做**：那次验证用的是**修 `run.sh` 之前**的镜像，
      而本机 `veribench-bio/t1:arm64` 里仍带着两个错误默认值；本轮 arm64 模拟已不可用
      （`exec format error`），因此**无法在本机修正**。需在能跑 arm64 的机器上
      用当前 `Dockerfile` 重建 + 重跑。详见上文"追加的实质警告"
- [ ] **原生 arm64 硬件验证仍未做**（QEMU 模拟 ≠ 真机；性能与极端路径可能不同）——属 D9 外部复现的一部分
- [x] ~~数据集尚未上传 HuggingFace~~ → **已上传并逐字节校验通过**：
      仓库 `zwb-tj/biobench-lite-t1-hg002-chr20`（**当前 Private**），7/7 文件与 manifest 完全一致；
      数据卡 `data/HF_DATASET_CARD.md`，上传手册 `../../docs/HF_UPLOAD.md`
- [x] ~~完全无复现验证~~ → **已从 HF 副本重跑并逐字段比对**：`score` 与全部 TP/FP/FN、P/R/F1 **逐位相同**
      （见 `baseline/README.md` 的复现记录）。2026-09 又独立重跑 4 次（含"不覆盖默认值"与
      "用当前 Dockerfile 重建的镜像"两条路径），**5 次得分均为 0.84655、变异数均为 12,254**
- [ ] **外部复现仍缺三块**（D9 剩余）：
      ① **不同机器 / 不同 OS / 不同 CPU 架构**（arm64 需按上一条重做）；
      ② **真正第三方独立复核**（目前是我们自己跑的）；
      ③ **无缓存的干净环境**（如 CI runner）
- [x] ~~`samtools` / `bcftools` 的 **Debian 包**上游 LICENSE 原文**待补核验**~~ →
      **2026-09 已核验**：按镜像内实际版本读上游 `LICENSE` 原文
      （samtools 1.16.1 / bcftools 1.16 / htslib 1.16），链接写在 `NOTICE` [A] 块，
      由 `scripts/verify_notice.py` 强制。[A] 块里**没有** Debian 打包产物的 LICENSE 原文，
      但已把"Debian 打包是否引入 copyleft"这一实质问题用四道门禁实测排除（见 `DATACARD` §5.2）。
- [ ] 参考基因组 SDF（约数百 MB）由使用者本地构建、**本数据集不托管**；构建耗时未单独记录。
- [x] ~~真实数据上的计时未验证~~ → **已完成：55 秒**
- [x] ~~`freebayes` 在真实 BAM 上的行为未测试~~ → 已完成
- [x] ~~数据托管位置未定~~ → **HuggingFace Datasets**；数据卡与上传手册已写好
- [x] ~~高置信区间 BED 文件名待确认~~ → 已实测确认：`HG002_GRCh38_v5.0q_smvar.benchmark.bed`
