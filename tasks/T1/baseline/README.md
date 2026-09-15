# T1 参考基线结果（Reference Baseline）

> **这不是榜单成绩，是"参考基线"。**
> 它的用途是：让任何人在跑自己的解法之前，先有一个可复现的对照点——
> 如果连参考实现都跑不出这个量级，那大概是环境或数据出了问题，而不是解法不行。

---

## 运行环境（可复现的关键参数）

| 项 | 值 |
|---|---|
| 日期 | 2026-09-12 |
| 镜像 digest | `sha256:c33862bb7ba588e42f98a52bd8b6a3be0df3a120fc081a9acfcd7e90e6f04e1e` |
| 数据集 manifest 哈希 | `fa025875cb2b593810119d04f08588a6467609314279c5a68752a653f804200f` |
| 主机 | Docker Desktop / Windows，**16 CPU**，容器可用内存约 7.9 GB |
| 区域 | `chr20:10,000,000–12,000,000`（2 Mb） |
| 输入覆盖度 | **30×**（从源 BAM 实测 70.57× 降采样，比例 0.425110，seed=42） |
| 参考 | UCSC hg38 chr20（64,444,167 bp） |
| 真值 | GIAB/NIST **v5.0q smvar**，裁剪到该区域后共 **3,352** 个变异 |

## 结果

| 指标 | SNP | INDEL | 合计 |
|---|---|---|---|
| TP | 2,512 | 431 | 3,086 |
| FP | 353 | 75 | 473 |
| FN | 152 | 165 | 168 |
| **精确率** | 0.8768 | 0.8569 | 0.8649 |
| **召回率** | 0.9429 | 0.7232 | 0.9484 |
| **F1** | **0.9087** | **0.7844** | **0.9047** |

**主分 `score` = mean(F1_snp, F1_indel) = 0.84655**（`status = ok`，无 problem）

## 资源消耗

| 项 | 值 |
|---|---|
| **变异检出（freebayes）** | **55 秒**（门禁 1,800 秒，**用了 3%）** |
| 评分（vcfeval） | 11.4 秒 |
| 峰值内存 | 1,100.8 MB |
| 检出变异数 | 12,254 |

---

## 怎么读这个数字（重要）

**它是一次"默认参数、未调优"的运行。** 具体说：

- `freebayes` 用默认参数，**没有调过滤阈值、没有加 `--dbsnp`、没有做 BQSR**
- 输入是**从 70.6× 降采样到 30×** 的数据，不是原始深度
- 只在 **2 Mb** 区域内评测，不是全基因组

**所以：**
- ❌ 不要把它当"这道题的上限"——真实工位上的调优结果会明显更好（尤其 INDEL 召回率 0.7232 偏低，通常靠调参和加已知位点能改善）
- ✅ 可以把它当"**环境自检标准**"：如果你的运行产出的是 0.3 或 0，先查环境，别急着改算法
- ✅ 也可以把它当"**弱基线**"：任何声称"AI 自动化变异检出"的方案，**至少要好过这个普通工具链的默认结果**，才有讨论价值

## 一个值得注意的余量

**门禁是 30 分钟，实际只用了 55 秒——余量 32 倍。**

这意味着如果将来需要更充分的统计量，可以把区域从 2 Mb 扩到 10 Mb 甚至更大（变异数从 3,352 增到约 1.6 万），仍然在预算内。**这是在 D3 之后可以考虑的扩展方向**，但 v1 先保持小体积（数据集 100 MB）以兑现"任何人用笔记本就能复现"的承诺。

---

## 复现命令

```bash
# 1) 取数据（或按 tasks/T1/data/prepare_data.sh 自己生成）
hf download <用户名>/biobench-lite-t1-hg002-chr20 --repo-type=dataset --local-dir ./t1-data

# 2) 建参考 SDF（一次性，不计入任务耗时）
rtg format -o ./work/chr20.sdf ./t1-data/ref/chr20.fa

# 3) 变异检出（这一步是"被评测的任务"，会计时）
docker run --rm \
  -v "$PWD/t1-data:/data" -v "$PWD/out:/out" \
  veribench-bio/t1:dev -lc '
    export DATA_DIR=/data OUT_DIR=/out REGION=chr20:10000000-12000000
    export REF=/data/ref/chr20.fa BAM=/data/aln/HG002.chr20.30x.bam
    bash /work/run.sh'

# 4) 评分
docker run --rm \
  -v "$PWD/t1-data:/data" -v "$PWD/out:/out" -v "$PWD/work:/work-sdf" \
  veribench-bio/t1:dev -lc '
    python3 /work/grade.py \
      --calls /out/calls.vcf.gz \
      --truth /data/truth/HG002_GRCh38_v5.0q_smvar.region.vcf.gz \
      --bed   /data/truth/HG002_GRCh38_v5.0q_smvar.benchmark.region.bed \
      --ref-sdf /work-sdf/chr20.sdf \
      --timing /out/timing_call.json --out /out/result.json'
```

## 本目录文件

| 文件 | 说明 |
|---|---|
| `freebayes_result.json` | 判分器完整输出（含逐类型指标、耗时、镜像与 manifest 哈希、执行日志尾部） |
| `timing_call.json` | `run.sh` 产出的任务计时（**只有它计入 `wall_clock_sec`**） |
| `full_run.log` | 容器内完整日志（含 SDF 构建、检出、评分全过程） |

## 诚实声明

- 这份基线**由本项目的参考流水线产出**，不是官方成绩
- `peak_rss_mb` 取自 `getrusage(RUSAGE_CHILDREN).ru_maxrss`，是子进程峰值的近似
- 运行日志中包含 3,352 个真值变异与 12,254 个检出的明细，**可被独立复核**

---

## 复现记录

### 第 1 次：从 HuggingFace 下载副本重跑（2026-09-12）

**做法**：把数据以**只读**方式挂载，且**只用从 HF 下载回来的那一份**（不碰本机原始数据），
在干净容器里重跑整条流水线。

**结果**（`../tools/compare_results.py` 逐字段比对，退出码 0）：

| 字段 | 基线（本机数据） | 复现（HF 副本） | 一致 |
|---|---|---|---|
| `status` | ok | ok | ✅ |
| **`score`** | **0.84655** | **0.84655** | ✅ |
| `snps.tp/fp/fn` | 2512 / 353 / 152 | 2512 / 353 / 152 | ✅ |
| `snps.precision/sensitivity/f1` | 0.8768 / 0.9429 / 0.9087 | 同 | ✅ |
| `indels.tp/fp/fn` | 431 / 75 / 165 | 431 / 75 / 165 | ✅ |
| `indels.precision/sensitivity/f1` | 0.8569 / 0.7232 / 0.7844 | 同 | ✅ |
| `wall_clock_sec` | 55 | 46 | ～ 允许波动 |
| `peak_rss_mb` | 1100.8 | 745.5 | ～ 允许波动 |

另外，HF 副本的 **7 个文件与 manifest 逐字节一致**（`../tools/verify_manifest.py`，退出码 0）。

**这证明了什么**：
- 数据集从 HF 取下来**没有损坏**（字节级）
- **本机原始数据 → 降采样 → 上传 → 下载 → 重跑** 这条链路没有引入偏差
- 同一输入在**同一台机器**上得到**逐位相同的评分**（说明流水线是确定性的，不是每次都随机）

**这还没证明什么**（重要，别过度解读）：
- ❌ **还没有在不同机器 / 不同操作系统 / 不同 Docker 版本上验证过**。
  本机是 Windows + Docker Desktop；换到 Linux 宿主机、或 Apple Silicon（arm64）上是否一致，
  **尚未验证**。arm64 尤其值得担心：镜像里 RTG 是 `linux-x64` 版，Java 部分可跨平台，
  但若有 x86 专用二进制就会出问题。
- ❌ 没有第三方**独立**复核（目前是我们自己跑的）
- ❌ 未在"没有本机缓存"的完全干净环境（如 CI runner）里跑过

→ 这三条是 **D9（外部复现）** 的剩余内容。

## 2026-09 追加：五次独立重跑（含"走默认值"与"重建镜像"两条新路径）

上表只覆盖了前两次。2026-09 又跑了三次，**刻意换了三条不同的路径**，
因为前两次都有同一个盲区：**driver 都 `export` 覆盖了 `run.sh` 的默认值**，
于是默认值里的两个 bug（`BAM` 少了 `.30x`、`REGION` 写成 10–20 Mb）**从来没被执行过**。

复现用的 driver 是 `../repro_driver.sh`（**刻意不设 `REGION`/`BAM`**，
并把 `$DATA_DIR` 以**只读**挂载，顺便证明跑任务不改动已发布的数据集）：

```bash
docker run --rm \
  -v "<HF 下载下来的数据>:/data:ro" \
  -v "$PWD/_runs_reproN:/out" \
  -v "$PWD/repro_driver.sh:/work/_driver.sh:ro" \
  -e IMAGE_DIGEST=<镜像 ID> -e MANIFEST_HASH=<manifest 哈希> \
  <镜像> /work/_driver.sh
```

| # | 路径 | score | 变异数 | 耗时 | 峰值内存 | 镜像 |
|---|---|---|---|---|---|---|
| A | 首次（本机数据） | 0.84655 | 12,254 | 55s | 1100.8 MB | `c33862bb…` |
| B | HF 重新下载的数据 | 0.84655 | 12,254 | 46s | 745.5 MB | `c33862bb…` |
| C | **不覆盖默认值**（走 `run.sh` 自带默认值） | 0.84655 | 12,254 | 41s | 616.0 MB | `c33862bb…` |
| D | 由当前 `Dockerfile` 重建的镜像 | 0.84655 | 12,254 | 39s | 508.1 MB | `1f5c665b…` |
| E | 重建镜像 + 四道 GSL 门禁 | 0.84655 | 12,254 | 43s | 491.0 MB | `e75867d5…` |

**结论**：**五次得分与变异数逐位相同**，只有耗时与内存波动（39–55s / 491–1101 MB）。
"得分可复现"这一条因此从"2 次"加强到"5 次，且覆盖三种不同镜像/配置路径"。

**顺带查清的两件事**（都不在最初计划里，是重跑才暴露的）：

1. **C 与 D 的差异是有意义的**：C 证明**默认路径真的能跑**（改之前不能 —— 会 `exit 2`）；
   D/E 证明**当前 `Dockerfile` 构建出的镜像**也被实跑验证过（此前 pin 的 digest
   其实是剥离 JRE 之前的旧镜像，见 `../../../docs/DATACARD.md` §5.1）。
2. **arm64 那一列需要作废重做**：上表判分器自检数字来自**修 `run.sh` 之前**的镜像，
   本机 `t1:arm64` 至今带着错误默认值，而本轮 arm64 模拟已不可用。
   详见 `../README.md` 的"追加的实质警告"。

### 复跑方法（任何人都能做）

```bash
cd bio-eval/tasks/T1
docker build --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn -t veribench-bio/t1:dev .
python scripts/record_image_digest.py --check      # 构建输入有没有变
python ../../scripts/verify_t1_claims.py           # 文档数字与产物是否一致
```

⚠️ 重建镜像后，`verify_t1_claims.py` 会**故意报错**，直到你
在该镜像上重跑一遍并用 `record_image_digest.py --image-id …` 重新记录 ——
这是设计如此：digest 不是一个孤立字符串，它绑定着"这批构建输入"。
