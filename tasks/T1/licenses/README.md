# /licenses —— T1 镜像内的许可声明

本目录随镜像分发。目的：让拿到镜像的人能**独立核实**镜像里有哪些组件、各是什么许可。

## 本镜像包含的组件

| 组件 | 版本来源 | 许可 | 说明 |
|---|---|---|---|
| `samtools` / `bcftools` / `tabix` / `htslib` | Debian bookworm 包（1.16.1-1 / 1.16-1 / 1.16+ds-3 / libhts3 1.16+ds-3） | MIT / Expat | **上游 `LICENSE` 原文已核验**（2026-09，按 `1.16.1`/`1.16` 这两个 tag 逐个读）：<https://github.com/samtools/samtools/blob/1.16.1/LICENSE>、<https://github.com/samtools/bcftools/blob/1.16/LICENSE>、<https://github.com/samtools/htslib/blob/1.16/LICENSE>。注意 `htslib` 的 `cram/` 子目录是 Modified-BSD-3。`bcftools` 本身是 **MIT-or-GPL 双许可** |
| `freebayes` | Debian bookworm 包 | **MIT** | 上游 `LICENSE` 原文已核验（Erik Garrison / Gabor Marth，MIT 全文） |
| RTG Tools（仅用 `vcfeval`） | 上游 release zip | **BSD 2-Clause** | 上游 `LICENSE.txt` 原文已核验 |
| OpenJDK（`default-jre-headless`） | Debian bookworm 包 | GPL-2 **WITH Classpath-exception-2.0** | 例外条款使其不传染；属"假阳性放行" |
| Debian 基础镜像的 userland（`bash`/`coreutils`/`sed` 等） | Debian | GPL-2 / GPL-3+ | **聚合**，非本应用的一部分 |

## 刻意不包含的组件（及原因）

| 组件 | 许可 | 为什么不打包 |
|---|---|---|
| **GATK4** | Apache-2.0（本体） | 官方运行环境会引入**专有 Intel oneMKL**、**GPL 的 R/GSL**、**LGPL 的 `htsjdk-tribble`（不可剥离）**。换 FreeBayes 后这些问题同时消失。 |
| `libgsl` / `gsl-bin` | GPL-3+ | 启用 GSL 会让 `bcftools` 转为 GPL-governed → **构建时许可门禁会直接失败** |
| `r-base` | GPL-2+ | 同上，且本任务不需要 R |
| Intel oneMKL | **专有，源码不可得** | 改用非 MKL 路径；本任务不需 BLAS |

## `bcftools` 的 GSL 问题：一个字面读起来很危险的记录（2026-09 已实证排除）

Debian 自己的 `/usr/share/doc/bcftools/copyright` 写着：

> "License: MIT or GPL-3.0
> Comment: Dual-licensing is in effect for the default compilation mode.
> **When linked with the GPL-licensed GNU Scientific Library (as is done for
> this Debian package), the resulting program must be distributed under the GPL.**"

而 Debian 的 `debian/rules`（bcftools 1.16-1）确实写着
`--with-htslib=system --enable-gsl --with-cblas=gslcblas`。

**照字面读，本镜像里的 `bcftools` 就是 GPL-governed** —— 那"工具链零 copyleft"就是假话。
所以我们**没有采信任何一方的文字**，而是实测。四条独立证据：

1. **行为（决定性）**：上游 `bcftools/Makefile` 说 GSL 依赖只来自 `polysomy` 命令，
   且只有 `make USE_GPL=1` 才编。即 **`USE_GPL` 就是"要不要 GSL"的开关，其可观察表现就是
   `bcftools polysomy` 在不在**。实测：`bcftools polysomy` → `unrecognized command`。
2. **字节级**：`bcftools`/`samtools`/`tabix`/`freebayes` 及 **39 个插件**里都搜不到
   `gsl_*` / `libgsl*` / `libcblas*`。这一条同时排除了**静态链接**（`ldd` 看不见静态链接）。
3. **动态依赖**：上述所有二进制的 `NEEDED` 里都没有 libgsl/libcblas。
4. **文件系统**：镜像内不存在任何 `libgsl*`/`libcblas*` 文件。

**结论**：Debian 的 `--enable-gsl` 并没有把 GSL 编进这个 `bcftools`；
上面那句 copyright 注释对本构建**已过期/是模板文字**。

**这道结论由构建期门禁 `scripts/check_no_gsl.sh` 强制执行**（四道检查全跑，任一失败即中断构建），
并做过负向测试（`scripts/_negtest_no_gsl.sh`）：注入假 `libgsl.so`、让 `bcftools` 会应答
`polysomy`、往二进制里塞 `gsl_*` 字节，三者都能让它失败；复位后重新通过。

> ⚠️ **不要把这道门禁"简化"回 `ldd | grep libgsl`。** 那个版本有三个盲区：
> 静态链接看不见、插件根本没扫、而且完全不验行为。


## 关于"镜像内不得含 GPL"的语义

**按字面不可能满足** —— 每个 Ubuntu/Debian 镜像里的 `bash`、`coreutils`、`sed`、`tar`、`grep`
本身就是 GPL 二进制。

本项目采用的语义（见 `../../SPEC.md` §5.6⑤）：

> 不得含**与本应用构成一个整体（组合作品）**、或**我们依赖其核心功能**的 GPL 组件；
> 纯粹共处同一镜像的 GPL userland 属**聚合**。

## 已知限制

- 本目录的声明**基于上游 LICENSE 原文核验**，但**不是法律意见**。
- 2026-09 更新：`samtools` / `bcftools` / `htslib`（含 `tabix`）的上游 LICENSE 原文
  **已逐个 tag 读过**（见上表链接），因此仓库根的 `NOTICE` 已把它们从 [B] 块
  （"未逐项核验"）移入 [A] 块（"已从原文核验"）。
  `NOTICE` 的 [A]/[B] 划分由 `scripts/verify_notice.py` 强制核对：
  [A] 的每一条都必须给出上游 LICENSE 出处，否则报错。
- **仍未逐项核验**：OpenJDK 与 Debian userland 的许可取自 Debian 包元数据
  （`/usr/share/doc/*/copyright`），未读上游原文 —— 它们仍留在 `NOTICE` 的 [B] 块。
- 未生成完整 SBOM（`THIRD-PARTY-LICENSES.md` 待补；做法见 `../../SPEC.md` §5.6⑧）。
- 本镜像**只在一台 Windows + Docker Desktop（amd64）上实测过**。
  arm64 的功能验证是在 QEMU 模拟下完成的（构建 + 架构中立性检查 + 判分器自检），
  **不等于**原生 arm64 硬件已验证。
