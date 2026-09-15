# GATK4 许可边界审计报告
## 场景：对外发布内含 GATK4 的公开评测镜像（预置 BAM + 单样本 HaplotypeCaller）

| 项 | 值 |
|---|---|
| 审计时间 | 2026 年 9 月 |
| 被审对象 | GATK4，最新发布版 **4.7.0.0**（Maven Central `lastUpdated=20260818040147`） |
| 分发政策约束 | 镜像内**不得含 GPL 或非商用组件** |
| 用法假设 | 预置已比对 BAM → 单样本 `HaplotypeCaller` → VCF → hap.py/vcfeval。**不做 reads→BAM 比对，不做多样本联合分型** |
| 证据标准 | 全部结论基于**一手文件 + 对官方发布二进制的实测**。凡未核实者一律标注"无法核实 + 核实方法" |

---

## 0. 执行摘要

### 0.1 三个疑点的结论（含两处重要**修正**）

| 疑点 | 原假设 | **实测结论** | 严重度 |
|---|---|---|---|
| **A** GenomicsDB 链入 LGPLv2 的 libcsv/libuuid | 两者都链入，可能是动态链接 | **libcsv 完全没被链入**（官方发布构建里被显式排除）✓。**libuuid 确实被静态链接** ✓，**但"libuuid 是 LGPLv2"这个前提很可能是错的** —— 被链接的 `gen_uuid.c` 源文件头是 **BSD-3-Clause**，Ubuntu/conda-forge 的 libuuid 也都是 BSD-3-Clause。**⇒ 疑点 A 的 copyleft 部分基本不成立**（只剩 BSD-3 的署名义务）。真正确证的 LGPL 项是 GenomicsDB 的传递依赖 `gnu.getopt:java-getopt:1.0.13` = **LGPL-2.0** | **低**（原判断过高） |
| **B** `gatk-bwamem-jni` 把 GPLv3 的 BWA 编进二进制 | GPLv3 被静态编译进去 | **修正：不成立。** BWA 确实被静态编译进 `libbwa.Linux.so`（已实测确认），但被 pin 的那个 commit（`cb950614`，2017-08-04）**整棵树里唯一的许可文件是 Apache-2.0**，没有 `COPYING`，没有任何 GPL 头，且编译进 `libbwa.a` 的目标文件全部是 Apache-2.0/MIT 文件。**真正的问题是：该构件只声明 BSD-3-Clause，却内含 Apache-2.0/MIT 的 BWA 代码而完全没有相应许可证文本与归属声明** | 低（是署名/NOTICE 问题，不是 GPL 传染问题） |
| **C** 其它 GPL/AGPL/非商用项 | 未知 | **未发现任何 GPL / AGPL / CDDL / SSPL / 非商用项。** 但发现 **两项真实在用的 LGPL-2.1 组件**：`htsjdk:5.0.0` 的 **`tribble` 核心**（其 POM 只写 MIT，属虚假声明）与 `jgrapht-core/io:1.1.0`（可择 EPL-1.0 规避）。另有多项署名缺失 | **高**（这是本审计最该行动的一条） |

### 0.1b 本审计的**最高严重度**发现：不在 GATK 的 jar 里，而在 conda 环境与 base 镜像里

审计过程中发现一个**比 A/B/C 都严重、且与 GATK 的 Java 依赖无关**的问题 —— 官方镜像的 conda 环境里有**专有非开源组件**和**真正的 GPL 组件**：

| 组件 | 许可性质 | 证据 |
|---|---|---|
| **Intel oneMKL**（经 `blas=1.0=mkl` 与 `pytorch=2.1.0=*mkl*100` 引入） | **专有 / 非 OSI**：`license: LicenseRef-IntelSimplifiedSoftwareOct2022`，`license_family: Proprietary`，**二进制-only、源码不可得** | GATK 官方环境模板 https://raw.githubusercontent.com/broadinstitute/gatk/master/scripts/gatkcondaenv.yml.template ：`- conda-forge:blas=1.0=mkl` 与 `- conda-forge::pytorch=2.1.0=*mkl*100`；conda-forge 打包配方 https://raw.githubusercontent.com/conda-forge/intel_repack-feedstock/main/recipe/meta.yaml 对 `mkl` / `mkl-include` / `onemkl-sycl-*` / `dal` / `impi_rt` / `mkl-static` 全部标注 `license_family: Proprietary`。ISSL 原文（conda-forge `onemkl-license`）：`Intel Simplified Software License (Version October 2022) ... provided in binary form only ... No reverse engineering, decompilation, or disassembly ... Redistributions must reproduce the above copyright notice and these terms of use` |
| **GSL**（`r-base` 的硬运行依赖） | **GPL-3.0-or-later** | conda-forge `r-base 4.3.1` 的运行依赖 `gsl >=2.7,<2.8.0a0` |
| **R 4.3.1**（`r-base=4.3.1`） | **GPL-2.0-or-later** | 同上模板；`r-source/src/main/version.c`：`GNU General Public License versions 2 or 3.` |
| `r-gplots` GPL-2.0-only、`r-catools` GPL-3.0-only、`r-gtools` GPL-2.0-only、`r-mass`/`r-mgcv` GPL-2+、`r-getopt`/`r-optparse`/`r-backports` GPL-2+ | GPL 系 | 同上模板 + conda-forge feedstock 元数据 |
| `gcc_impl_linux-64` / `gxx_impl_linux-64` / `gfortran_impl_linux-64`（GPL-3 编译器二进制，**运行时例外不覆盖编译器本身**） | GPL-3.0-or-later | `r-base` 的运行依赖 |
| `liblzma5`（xz-utils） | **LGPL-2.1+**（部分文件）+ PD | Ubuntu jammy copyright：`License: PD` … `License: LGPL-2.1+`。**这才是镜像里真正在用的 LGPL 共享库**（动态链接 → 义务易满足） |
| `bedtools 2.30.0` | **镜像内实为 MIT**；Ubuntu 元数据仍写 GPL-2（陈旧，`Source:` 还指向 v2.25.0） | 上游 tag v2.30.0 LICENSE = MIT；v2.25.0 = GPL-2 |
| `bcftools 1.13-1` | **走 MIT 分支**；Ubuntu copyright 的 GPL 警告未成立 | jammy `Depends` = `libc6, libhts3, zlib1g`（无 `libgsl27`），且 ELF 中无 libgsl 引用 |
| `samtools` / `htslib` / `tabix` / `pysam` | MIT/Expat（`cram/` 为 BSD-3） | 上游 LICENSE |

> **⚠ 最重要的一条现实检查：`bash` / `coreutils` / `sed` / `tar` / `grep` / `gzip` / `make` / `wget` / `git` / `dpkg` 都是 GPL-2/GPL-3+ 二进制，它们存在于**每一个** Ubuntu 镜像里。**
>
> **⇒ 因此"镜像内不得含 GPL"如果按字面理解，是**不可能满足**的 —— 任何可用的 Linux 镜像都含 GPL userland。**
>
> **⇒ 该政策必须被理解为："不得含**与我们分发/链接的应用构成组合作品、或我们必须依赖其功能**的 GPL 组件"，而非"镜像里不得出现任何 GPL 文件"。** 在上述理解下：
> - GPL userland（bash 等）→ **聚合，无义务**，可放行；
> - `libgcc`/`libstdc++`/`libgomp`（GPL-3 **WITH GCC Runtime Library Exception**）→ **故意设计为允许非 GPL 程序使用，属假阳性**，可放行；
> - OpenJDK（GPL-2 **WITH Classpath-exception-2.0**）→ 同理，可放行；
> - **真正需要处理的是**：**Intel MKL（专有）**、**GSL（GPL-3，无例外）**、**R 及其 GPL 包**、**htsjdk tribble / jgrapht（LGPL-2.1，且在你们的执行路径上）**。
>
> **建议：把这条政策的确切含义与法务确认一次。** 这是本审计认为最优先的动作 —— 它决定了后面所有取舍。

**⇒ 这第四条风险线无法靠"剥离 jar 里的 .so"消除。** 好消息：如果你们**自己写 Dockerfile**（而不是直接用 `broadinstitute/gatk`），这部分完全可控 —— 去掉 R 相关依赖、把 BLAS 从 `mkl` 换成 `openblas`/`blis`，GPL 与专有组件同时消失，镜像体积也会大幅下降。

---

### 0.2 对"我们当前用法"的明确回答

**分两层，必须分开看，否则会得出错误结论。**

**第 1 层 · 运行时：A 和 B 都不会被加载 —— 不需要担心。**
已用官方 `gatk-4.7.0.0.jar` 的字节码可达性分析证明（§2.6、§3.4）：从 `HaplotypeCaller` 出发的 763 类传递闭包里，`utils/bwa/` **完全不可达**（0 个 BWA 类），`org.genomicsdb.*` 的 JNI 类也**不可达**。两个 native 库都只在 GenomicsDB 导入/联合分型、或 BWA/PathSeq/SV 路径上才被 `dlopen`。

**第 2 层 · 分发合规：默认镜像不合格，必须处理。**
GPL/LGPL 义务附着在**向他人分发副本**这一行为上，与代码路径是否执行无关。用户 pull 下镜像即获得其中每一个字节，包括 `libbwa.Linux.so`（744 135 B）与静态链接了 LGPLv2 libuuid 的 `libtiledbgenomicsdb.so`（25 391 160 B）。

**第 3 层 · 但真正的重点不是 A/B。**
A/B 的好处是**可以直接删掉**（我们不用它们），义务即归零。而 **`htsjdk` 的 `tribble`（LGPL-2.1）与 `jgrapht`（LGPL-2.1，可择 EPL-1.0）是我们现有路径上真正会执行、且无法轻易剥离的组件**。这才是需要你们做决策的地方 —— 详见 §5。

> **政策语义提醒**：你们的政策原文是"不得含 **GPL** 或非商用组件"。**LGPL ≠ GPL**。按字面理解，LGPL 是允许的，只需履行通告义务。但若你们法务的本意是"不得含任何 copyleft"，那 GATK4 对这条流水线基本不可用（tribble 与 jgrapht 无法剥离），必须换 caller。**这个歧义必须先去澄清，它决定后面所有方案。**

---

## 1. 方法与环境（可复现）

一手文件全部经 `raw.githubusercontent.com` / `repo1.maven.org` 直读。二进制结论来自实际下载官方发布物并用自写 ELF 解析器、Java 常量池解析器、`pom.properties` 枚举器分析。

**下载并实测的官方产物**（位于 `bio-eval/research/_artifacts/`）：

| 文件 | 字节 | SHA-256（前 32） | 来源 |
|---|---|---|---|
| `gatk-4.7.0.0.zip` | 699 681 649 | `D093D2693B1626361A413CA59D6D4A0B` | GitHub release |
| `gatk-package-4.7.0.0-local.jar` | 426 730 186 | `882E180707E0E6887885853FC486FA54` | 从上述 zip 解出（**即 Dockerfile 里 `gatk.jar` 指向的文件**） |
| `gatk-4.7.0.0.pom` | 80 439 | `DADFB901F7D3DB00D6265574244E7AF1` | Maven Central |
| `gatk-bwamem-jni-1.0.4.jar` | 398 914 | `B06D98C51879653470B4FD748CEB99DD` | Maven Central |
| `genomicsdb-1.5.5.jar` | 20 471 875 | `25B415E3DD3A5999E7681960ED688274` | Maven Central |
| `libbwa.Linux.so` | 744 135 | `91454971318DC1B7890926964EE7CF12` | 从 jar 提取 |
| `libtiledbgenomicsdb.so` | 25 391 160 | `71FB2ED71BF3959BAF91E7DFA51C1ADE` | 从 jar 提取 |
| `bwa-commit-LICENSE.txt`（pin 的 commit） | 9 618 | `4198EC61EB959B19103485867DF4161A` | raw.githubusercontent.com |
| `bwa-master-COPYING` | 35 147 | `8CEB4B9EE5ADEDDE47B31E975C1D90C7` | raw.githubusercontent.com |
| `LGPL-2.1.txt` | 26 419 | `20E50FE7AAE3E56378EBF0417D9DE904` | gnu.org |
| `htsjdk-5.0.0-sources.jar` | 1 668 361 | — | Maven Central |

**分析脚本**（留在 `_artifacts/`，可直接重跑）：

```bash
python elfcheck.py libtiledbgenomicsdb.so uuid      # ELF .dynsym/.symtab + DT_NEEDED
python classrefs.py gatk-4.7.0.0.jar org/genomicsdb # 谁引用了某包
python closure.py  gatk-4.7.0.0.jar \
  org/broadinstitute/hellbender/tools/walkers/haplotypecaller/HaplotypeCaller "utils/bwa/,genomicsdb"
python srcheaders.py _work/htsjdk-5.0.0-sources.jar  # 逐文件许可头
python bwaheaders.py _work/bwa-master                # BWA 逐文件许可头
python tracepkg.py gatk-package-4.7.0.0-local.jar "gnu/getopt"
```

---

## 2. 疑点 A：GenomicsDB 是否链入 LGPLv2 的 libcsv / libuuid？

### 2.1 上游自认：两条 LGPL 声明

**出处**：https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/LICENSE （GenomicsDB 本体是 MIT，但自己追加了两段）

libuuid 段：
> ```
> -libuuid-----------------------------------------------------------------------------------------
>
> We use libuuid (https://sourceforge.net/projects/libuuid/) which is licensed under the GNU Library
> or Lesser General Public License version 2.0 (LGPLv2). So, if you are re-distributing binaries or
> object files, they may be subject to LGPLv2 terms. Please ensure that any binaries/object files you
> distribute are compliant with LGPLv2.
> ```

libcsv 段（**关键：它自己给出了关闭方法**）：
> ```
> We use libcsv (https://sourceforge.net/projects/libcsv/) to parse CSV files. libcsv
> is licensed under the GNU Library or Lesser General Public License version 2.0 (LGPLv2).
> ...
> You can disable libcsv usage by not setting the USE_LIBCSV and LIBCSV_DIR flags
> during compilation. However, your binaries/executables will not be able to import CSV
> files into GenomicsDB.
> ```

### 2.2 构建系统：libcsv 被关掉，libuuid 被迫用**静态库**

**出处**：https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/CMakeLists.txt

```cmake
#libcsv
if(NOT BUILD_DISTRIBUTABLE_LIBRARY AND NOT BUILD_BINDINGS)
    if(USE_LIBCSV)
        find_package(libcsv REQUIRED)
    else()
        find_package(libcsv)
    endif()
endif()
```

libuuid 则**无条件 REQUIRED** 并进入最终链接列表：

```cmake
find_package(libuuid REQUIRED)
...
set(GENOMICSDB_EXTERNAL_DEPENDENCIES_LIBRARIES ${GENOMICSDB_EXTERNAL_DEPENDENCIES_LIBRARIES}
  ${OPENSSL_LIBRARIES} ${ZLIB_LIBRARIES} ${LIBUUID_LIBRARY} ${CMAKE_DL_LIBS})
```

**决定性一手证据** —— `Findlibuuid.cmake` 在可分发构建下**优先挑静态库 `libuuid.a`**：

**出处**：https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/cmake/Modules/Findlibuuid.cmake

```cmake
  if(BUILD_DISTRIBUTABLE_LIBRARY)
    find_library(LIBUUID_LIBRARY NAMES libuuid.a uuid HINTS "${LIBUUID_DIR}/lib64" "${LIBUUID_DIR}/lib" "${LIBUUID_DIR}")
  else()
    find_library(LIBUUID_LIBRARY NAMES uuid HINTS "${LIBUUID_DIR}/lib64" "${LIBUUID_DIR}/lib" "${LIBUUID_DIR}")
  endif()
```

### 2.3 官方 Maven 构件确实以 `BUILD_DISTRIBUTABLE_LIBRARY=true` 构建

**出处**：https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/Dockerfile.release
```
FROM ghcr.io/genomicsdb/genomicsdb:centos_6_prereqs_java_17
...
RUN useradd -r -U -m genomicsdb &&\
    ./scripts/install_genomicsdb.sh genomicsdb /usr/local true java
```
第三个位置参数即 `BUILD_DISTRIBUTABLE_LIBRARY`。**出处**：`scripts/install_genomicsdb.sh`
```bash
BUILD_DISTRIBUTABLE_LIBRARY=${3:-false}
ENABLE_BINDINGS=${4:-none}
...
$CMAKE .. -DBUILD_DISTRIBUTABLE_LIBRARY=$BUILD_DISTRIBUTABLE_LIBRARY -DBUILD_JAVA=$BUILD_JAVA ...
```
发布流程：https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/.github/workflows/release_jar.yml （`docker cp genomicsdb:/build/GenomicsDB/build/src/main/libtiledbgenomicsdb.so .`）
README 自述：> `GenomicsDB jars with native libraries and only zlib dependencies are regularly published on Maven Central` —— "only zlib dependencies" 正是静态链接 libuuid/OpenSSL 后的可见结果。

GATK 侧（**出处**：https://raw.githubusercontent.com/broadinstitute/gatk/master/build.gradle）：
```groovy
final genomicsdbVersion = System.getProperty('genomicsdb.version','1.5.5')
...
implementation 'org.genomicsdb:genomicsdb:' + genomicsdbVersion
```

### 2.4 【实测】官方二进制：libuuid **静态链接**，libcsv **不存在**

从 Maven Central 下载 GATK 4.7.0.0 实际使用的 `org.genomicsdb:genomicsdb:1.5.5`，提取 `libtiledbgenomicsdb.so`（25 391 160 B）解析 ELF：

**（a）`DT_NEEDED`（运行时依赖的共享库）**：
```
['libjvm.so', 'libpthread.so.0', 'libdl.so.2', 'libz.so.1', 'librt.so.1',
 'libm.so.6', 'libc.so.6', 'ld-linux-x86-64.so.2']
```
→ **没有 `libuuid.so`，也没有 `libcsv.so`。**

**（b）`uuid_*` 符号全部"在本对象内定义"而非"未定义导入"**：
```
.dynsym: 13 matching symbols for "uuid"
   __uuid_generate_random   bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   __uuid_generate_time     bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   uuid_generate            bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   uuid_generate_random     bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   uuid_generate_time       bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   uuid_generate_time_safe  bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   uuid_pack                bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   uuid_unpack              bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   uuid_unparse             bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   uuid_unparse_lower       bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
   uuid_unparse_upper       bind=GLOBAL type=FUNC DEFINED in this object (shndx=12)
```
`.symtab` 里还有**源文件符号**（只有把 libuuid 的 C 源文件编进来才会有）：
```
   gen_uuid.c                  bind=LOCAL type=FILE DEFINED in this object (shndx=65521)
   uuid_generate_time_generic  bind=LOCAL type=FUNC DEFINED in this object
   uuid_unparse_x              bind=LOCAL type=FUNC DEFINED in this object
   get_uuid_via_daemon         bind=LOCAL type=FUNC DEFINED in this object
```
（另有 `/var/lib/libuuid/clock.txt`，是 e2fsprogs/util-linux `gen_uuid.c` 的钟文件路径。）

> **⇒ libuuid 被静态链接进了 `libtiledbgenomicsdb.so`。** 这正是"library functions copied into the executable"的情形，**不满足** LGPL-2.1 §6 的 (b) 项豁免。

**（c）libcsv 没有被链接。** 只有 GenomicsDB **自己的** C++ 回调（mangled、LOCAL），libcsv 的公开 API 一个都没有：
```
.dynsym: 0 matching symbols for "csv_parse"
.symtab: 1 matching symbols for "csv_parse"
   _Z18csv_parse_callbackPvmS_   bind=LOCAL type=FUNC DEFINED in this object
```
且二进制里内嵌一条说明它是在**没有** libcsv 情况下编译的字符串：
```
Cannot import CSV files without libcsv - recompile GenomicsDB with USE_LIBCSV and/or LIBCSV_DIR set
```
**⇒ 与 §2.2/2.3 的构建配置完全吻合。**

### 2.5 静态 vs 动态：义务差异（权威条文）

**出处**：LGPL-2.1 §6，https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt
> ```
>   You must give prominent notice with each copy of the work that the
> Library is used in it and that the Library and its use are covered by
> this License.  You must supply a copy of this License. ...
> Also, you must do one of these things:
>
>     a) Accompany the work with the complete corresponding
>     machine-readable source code for the Library including whatever
>     changes were used in the work ... and, if the work is an executable linked
>     with the Library, with the complete machine-readable "work that
>     uses the Library", as object code and/or source code, so that the
>     user can modify the Library and then relink to produce a modified
>     executable containing the modified Library. ...
>
>     b) Use a suitable shared library mechanism for linking with the
>     Library.  A suitable mechanism is one that (1) uses at run time a
>     copy of the library already present on the user's computer system,
>     rather than copying library functions into the executable, and (2)
>     will operate properly with a modified version of the library ...
>
>     c) Accompany the work with a written offer, valid for at
>     least three years, to give the same user the materials
>     specified in Subsection 6a, above, ...
> ```

| | 动态链接 libuuid | **静态链接 libuuid（本案例）** |
|---|---|---|
| (b) 项豁免 | 成立 | **不成立** |
| 必须做的 | 通告 + 附许可证副本 + 允许替换 `.so` | **(a) 附 libuuid 完整对应源码 + 可重链接目标码**，或 **(c) 三年有效书面要约**，或 (d)/(e) |

> 注：GenomicsDB 写的是 "LGPLv2"，而 libuuid（e2fsprogs/util-linux 血统）通常标注 **LGPL-2.1**。本报告按更严格的 LGPL-2.1 §6 处理。

### 2.5b ✅ **存疑澄清（结论已翻转）：libuuid 实际是 BSD-3-Clause，不是 LGPL**

§2.1–2.5 的推导（"libuuid 是 LGPLv2 → 静态链接 → 触发 LGPL-2.1 §6 义务"）**建立在一个错误的前提上**。经进一步取证，**`libuuid` 很可能是 BSD-3-Clause，LGPL 之说源自 GenomicsDB 自己过时/错误的 LICENSE 描述。** 证据链如下。

**（a）决定性证据：被静态链接进 `.so` 的那个源文件，其头部就是 BSD-3 系许可。**

§2.4(b) 我在 `libtiledbgenomicsdb.so` 的 `.symtab` 里找到了 **FILE 符号 `gen_uuid.c`** —— 说明这个源文件确实被编译进来了。直接读 e2fsprogs 的该文件（**出处**：https://raw.githubusercontent.com/tytso/e2fsprogs/master/lib/uuid/gen_uuid.c ）：

```c
/*
 * gen_uuid.c --- generate a DCE-compatible uuid
 *
 * Copyright (C) 1996, 1997, 1998, 1999 Theodore Ts'o.
 *
 * %Begin-Header%
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, and the entire permission notice in its entirety,
 *    including the disclaimer of warranties.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. The name of the author may not be used to endorse or promote
 *    products derived from this software without specific prior
 *    written permission.
 * ...
 * %End-Header%
 */
```
—— 这是标准的 **BSD-3-Clause**（三条款 BSD）文本，**不是 LGPL**。注意版权年份包含 **2007**，与"libuuid 曾在早年使用 LGPL-2、其后被重新许可为 BSD-3 系"的历史一致（这解释了 GenomicsDB 描述为何过时）。

**（b）发行版元数据同样指向 BSD-3-Clause。**
- Ubuntu 22.04 `libuuid1` 的 `/usr/share/doc/libuuid1/copyright`（从 jammy 实际 .deb 提取）在 `Files: libuuid/*` 段标注 `License: BSD-3-clause`（Copyright: 1996-2007 Theodore Ts'o）；该 copyright 中的 LGPL 条目覆盖 util-linux 的**其它**部分。
- conda-forge 的 `libuuid` 元数据同样标注 **BSD-3-Clause**。

**（c）util-linux 项目级说明并未支持 LGPL 之说。** https://raw.githubusercontent.com/util-linux/util-linux/master/README.licensing （我独立复核）逐字：
> ```
> The project util-linux doesn't use the same license for all of the code.
> There is code under:
>    * LGPL-2.1-or-later  - GNU Lesser General Public License 2.1 or any later version
>    ...
>    * BSD-3-Clause       - BSD 3-Clause "New" or "Revised" License
>    ...
> Please, check the source code for more details. A license is usually at the start
> of each source file.
> ```
即 util-linux **同时包含 LGPL-2.1-or-later 与 BSD-3-Clause**，并明确要求**逐文件看头** —— 不能凭项目名断言。

**（d）GenomicsDB 的 LICENSE 描述很可能是错的。** 它写 "libuuid ... licensed under ... LGPLv2" 并指向 `https://sourceforge.net/projects/libuuid/`。但（a）表明实际编入的源码文件头是 BSD-3 系。

**⇒ 修正后的结论（对疑点 A）**
1. **libuuid 部分：很可能不产生 copyleft 义务**（BSD-3-Clause）。原假设"libuuid = LGPLv2 + 静态链接 = LGPL §6 义务"**不成立**。BSD-3-Clause 只要求**保留版权声明与免责声明**（这是署名义务，成本极低）。
2. **但这不改变推荐动作**：因为我们的用法**根本不需要这个 `.so`**（§2.6 已证不被加载），按 §7.2 剥离即可 —— 剥离后连 BSD-3 的署名义务都不用继承。
3. **方法论教训（本审计最重要的经验）**：**依赖作者自己的 NOTICE/LICENSE 也可能写错，且可能两个方向都错** —— `genomicsdb` 把 BSD-3 说成 LGPL（**高估** copyleft），而 `htsjdk` 把 LGPL-2.1 说成 MIT（**低估** copyleft，见 §4.3）。**必须落到被链接的具体源文件头部或二进制取证**，不能只看 POM/NOTICE。
4. **仍属未完全闭合**：我未能确认 GenomicsDB 的 CentOS 6 构建容器里装的究竟是哪个 libuuid 包（见 §8）。但两个主流实现（e2fsprogs 与 util-linux）的 `libuuid` 都是 BSD-3 系，故判为"很可能无 copyleft 义务"。

---

## 2.5c ✅ 附带确认：`gnu.getopt:java-getopt` = **LGPL-2.0**（这一条是真的）

用 `tracepkg.py` 在 `gatk.jar` 里追踪 `gnu/getopt` 的引用者，定位到 4 个类，其中 1 个在 `org/genomicsdb`：
```
=== classes whose bytecode mentions 'gnu/getopt': 4 ===
       3  owner-package: gnu/getopt
       1  owner-package: org/genomicsdb
```
继续追到源文件：`org/genomicsdb/model/CommandLineImportConfig.java` 引用了 `gnu.getopt`。而 `genomicsdb-1.5.5.jar` 与 `-sources.jar` **自身都不含** `gnu/getopt`（实测 0 条目）→ 说明它来自 GenomicsDB 的 **Maven 传递依赖**。查 `genomicsdb-1.5.5.pom` 确认：
```xml
      <groupId>gnu.getopt</groupId>
      <artifactId>java-getopt</artifactId>
      <version>${gnu.getopt.version}</version>
```
且该 POM 内 `<gnu.getopt.version>1.0.13</gnu.getopt.version>`。

**⇒ jar 内 `gnu/getopt/COPYING.LIB`（25 283 B）逐字开头：**
```
		  GNU LIBRARY GENERAL PUBLIC LICENSE
		       Version 2, June 1991

 Copyright (C) 1991 Free Software Foundation, Inc.
```
即 **`gnu.getopt:java-getopt:1.0.13` 是 LGPL-2.0**（**这一条经许可文件原文确证，与 libuuid 不同，是真的 LGPL**）。注意：**它自己的 POM 没有 `<licenses>` 块**（实测）—— 这也是它未出现在 §4.2 `pom.properties` 清单里的原因（老式 Ant 构建，jar 内有 `Makefile`、`buildx.xml`）。

**好消息**：jar 内已随附**完整源码** `gnu/getopt/Getopt.java`(48 490 B) 与 `LongOpt.java`(5 745 B)，LGPL 的"对应源码"要求实际已满足；只需补通告与许可证文本。

---

### 2.6 【明确回答】我们的用法下 GenomicsDB 会被加载吗？—— **不会**

**（a）全 jar（2 569 类）只有 3 个类引用 `org/genomicsdb`：**
```
scanned 2569 classes in gatk-4.7.0.0.jar
--- constant "org/genomicsdb/reader/GenomicsDBFeatureReader" referenced by 1 class(es):
      org/broadinstitute/hellbender/engine/FeatureDataSource.class
--- constant "Lorg/genomicsdb/model/GenomicsDBExportConfiguration$ExportConfiguration;" referenced by 2:
      org/broadinstitute/hellbender/engine/FeatureDataSource.class
      org/broadinstitute/hellbender/tools/genomicsdb/GATKGenomicsDBUtils.class
```
即 `GenomicsDBImport` / `GATKGenomicsDBUtils` / `FeatureDataSource`。**`HaplotypeCaller` 自己完全不引用 `org/genomicsdb`。**

**（b）从 `HaplotypeCaller` 出发的 763 类闭包：**
```
### transitive closure from .../walkers/haplotypecaller/HaplotypeCaller: 763 classes (of 2569)
  target 'utils/bwa/': NOT reachable
  target 'genomicsdb': REACHABLE -> ['.../tools/genomicsdb/GATKGenomicsDBUtils',
                                     '.../tools/genomicsdb/GenomicsDBArgumentCollection',
                                     '.../tools/genomicsdb/GenomicsDBConstants',
                                     '.../tools/genomicsdb/GenomicsDBOptions']
```
可达的**只是 GATK 自己 `tools/genomicsdb/` 下的配置包装类**（不加载 native 库）；**`org.genomicsdb.*` 的 JNI 类一个都不可达。**

**（c）native 库由谁加载？** 在 `genomicsdb-1.5.5.jar` 中，真正 `System.load` 的 `GenomicsDBLibLoader` 只被 4 个类引用：
```
--- constant "org/genomicsdb/GenomicsDBLibLoader" referenced by 5 class(es):
      org/genomicsdb/GenomicsDBLibLoader.class
      org/genomicsdb/GenomicsDBUtilsJni.class
      org/genomicsdb/importer/GenomicsDBImporter.class
      org/genomicsdb/reader/GenomicsDBQuery.class
      org/genomicsdb/reader/GenomicsDBQueryStream.class
```

**（d）唯一的"意外"入口及其精确触发条件。** `FeatureDataSource`（`--dbsnp`/`--known-sites` 会用到）里确实有一条 GenomicsDB 分支。一手源码（https://raw.githubusercontent.com/broadinstitute/gatk/4.7.0.0/src/main/java/org/broadinstitute/hellbender/engine/FeatureDataSource.java ）：
```java
private static <T extends Feature> FeatureReader<T> getFeatureReader(final FeatureInput<T> featureInput, ...) {
    if (IOUtils.isGenomicsDBPath(featureInput.getFeaturePath())) {
        Utils.nonNull(genomicsDBOptions);
        ...
        return (FeatureReader<T>)getGenomicsDBFeatureReader(featureInput, referenceAsFile, genomicsDBOptions);
    } else {
        final FeatureCodec<T, ?> codec = getCodecForFeatureInput(...);
        ...
        return getTribbleFeatureReader(featureInput, codec, cloudWrapper, cloudIndexWrapper);
    }
}
```
**只有特征输入路径本身是 GenomicsDB workspace 时才走这条分支。** 普通 `.vcf`/`.vcf.gz` 走 `getTribbleFeatureReader(...)`，永不触碰 native 库。

> **⇒ 预置 BAM + 单样本 HaplotypeCaller → VCF 的用法下，`libtiledbgenomicsdb.so` 永远不会被 dlopen，libuuid 代码永远不执行。**
> **但这不改变分发义务**（§2.4 已确认该 `.so` 就在我们分发的 `gatk.jar` 里）。

### 2.7 换成"多样本 / 联合分型"会额外引入什么

会**真的加载** `libtiledbgenomicsdb.so`：

| 触发场景 | 入口 | 依据 |
|---|---|---|
| 联合分型 `GenotypeGVCFs` / `GnarlyGenotyper` | 这两个类直接引用 `GenomicsDBArgumentCollection` | §2.6 分析输出 |
| `GenomicsDBImport` / `GenomicsDBImportSpark` | `GenomicsDBImporter` → `GenomicsDBLibLoader` | 同上 |
| `CreateSomaticPanelOfNormals`、`SelectVariants`（sample-name-map） | 引用 `GenomicsDBArgumentCollection` | 同上 |
| 把 GenomicsDB workspace 当 `--dbsnp`/`--known-sites` | `FeatureDataSource` 的 `isGenomicsDBPath` 分支 | 同上 |

**额外义务**：运行层面不新增许可类型（LGPL 不是 AGPL，不因网络服务而升级），但 §6 的"prominent notice"要求会从纸面变成实际需要落地到镜像文档/启动提示。
**规避方式**：`GenotypeGVCFs` 可逐个传 `-V g.vcf` 而不走 GenomicsDB 后端；但 `.so` 仍在 jar 里，仍须按 §7.2 剥离。

---

## 3. 疑点 B：`gatk-bwamem-jni` 是否把 GPLv3 的 BWA 编进了二进制？

> **结论：BWA 确实被静态编译进去了，但"GPLv3"这个前提不成立。** 下面是完整事实链。

### 3.1 仓库自称 BSD-3-Clause，但构建时 `git clone` BWA 并静态编译

**出处**：https://raw.githubusercontent.com/broadinstitute/gatk-bwamem-jni/master/LICENSE
```
BSD 3-Clause License

Copyright (c) 2017, Broad Institute
All rights reserved.
```
`build.gradle` 的 POM 也声明 `name 'BSD 3-Clause'`（且其 license url 指向 `.../LICENSE.TXT`，而仓库里的文件实际叫 `LICENSE` —— 坏链）。README 直说：`JNI code for bwa mem. / It allows Java code to call Heng Li's bwa mem aligner.`

**决定性证据**：https://raw.githubusercontent.com/broadinstitute/gatk-bwamem-jni/master/src/main/c/Makefile
```make
BWA_MEM_COMMIT=cb950614ce7217788780b9a8d445c64cd4d8f62e
...
libbwa.$(LIB_EXT): $(JNI_BASE_NAME).o init.o jnibwa.o bwa/libbwa.a
	$(CC) -ggdb -dynamiclib -shared -o $@ $^ -lm -lz -lpthread

bwa:
	git clone https://github.com/lh3/bwa && cd bwa && git checkout $(BWA_MEM_COMMIT) && echo '#define BWA_COMMIT "'$(BWA_MEM_COMMIT)'"' > bwa_commit.h
	sed -i.bak -e's/\(LOBJS=.*\)/\1 bwtindex.o rle.o rope.o bwt.o is.o/g' bwa/Makefile

bwa/libbwa.a: bwa
	$(MAKE) CFLAGS="$(CFLAGS)" -C bwa libbwa.a
```
`build.gradle` 把它塞进 jar：
```groovy
processResources { dependsOn buildBwaLib; from cpath; include "$libname*" }
```
> 整个 `gatk-bwamem-jni` 仓库文件树里**只有 `LICENSE`（BSD-3）一个许可文件，没有 NOTICE，没有 BWA 的许可证副本，也没有任何 BWA 归属声明。**

### 3.2 【关键修正】被 pin 的 commit 里**没有任何 GPL 代码**

我把该 commit 的完整源码树（`codeload` tarball）下载后**逐文件扫描许可头**。

**（a）该 commit 的完整文件树（75 项）里唯一的许可文件是：**
```
   LICENSE.txt  [blob]  sha=efaa7b948f9019bf7a5aa90223b1f85b128c1c8c
```
9 618 字节，内容 = **Apache License 2.0**（本地副本 `_artifacts/bwa-commit-LICENSE.txt`，SHA-256 `4198EC61…`）：
```
Apache License

Version 2.0, January 2004
```
**该树里没有 `COPYING`。**

**（b）同 commit 的 README.md：**
> `BWA is released under [Apache 2.0][1]. The latest source code is [freely available at github][2].`
> `[1]: http://en.wikipedia.org/wiki/GNU_General_Public_License`

—— 文字写 Apache-2.0，方括号链接 `[1]` 却指向 GPL 维基页（上游自身的瑕疵）。

**（c）逐文件许可头扫描（55 个源文件）：**
```
--- MIT header: 13 ---
    bntseq.c   Copyright (c) 2008 Genome Research Ltd (GRL).
    bntseq.h   bwt.c   bwt.h   bwtindex.c   utils.c   utils.h   (GRL)
    is.c       Copyright (c) 2008 Yuta Mori All Rights Reserved.
    khash.h / kseq.h / ksort.h / kvec.h / ksw.c   (Attractive Chaos)

--- GPL header: 0 ---
--- NO license header: 42 ---
    bwa.c bwa.h bwamem.c bwamem.h bwamem_pair.c bwamem_extra.c fastmap.c main.c
    rle.c rle.h rope.c rope.h kstring.c kopen.c kbtree.h kthread.c malloc_wrap.c ...
```
（`bwt_gen.c` —— master 上唯一带 GPL 头的文件 —— **不在该树里**：这个 commit 的标题就是 "removed bwt_gen.c"。）

MIT 头原文（`bntseq.c`、`bwt.c` 等，逐字）：
```
/* The MIT License

   Copyright (c) 2008 Genome Research Ltd (GRL).

   Permission is hereby granted, free of charge, to any person obtaining
   a copy of this software and associated documentation files (the
   "Software"), to deal in the Software without restriction, ...
```

**（d）最要紧的：到底哪些目标文件被编译进 `libbwa.a`？**
该 commit 的 `Makefile`：
```make
LOBJS= utils.o kthread.o kstring.o ksw.o bwt.o bntseq.o bwa.o bwamem.o bwamem_pair.o bwamem_extra.o malloc_wrap.o
libbwa.a:$(LOBJS)
		$(AR) -csru $@ $(LOBJS)
```
加上 `gatk-bwamem-jni` 的 sed 补丁追加 `bwtindex.o rle.o rope.o bwt.o is.o`，最终进入 `libbwa.so` 的是：
**utils, kthread, kstring, ksw, bwt, bntseq, bwa, bwamem, bwamem_pair, bwamem_extra, malloc_wrap, bwtindex, rle, rope, is**

对应许可：6 个带 MIT 头（utils/ksw/bwt/bntseq/bwtindex/is），9 个无头（kthread/kstring/bwa/bwamem/bwamem_pair/bwamem_extra/malloc_wrap/rle/rope）→ 无头文件由**该 commit 唯一的许可文件**（Apache-2.0）治理。**没有任何一个 GPL 文件被编入。**

### 3.3 上游确实换过许可文件（这条要写进风险登记）

| 时间 / 引用 | `LICENSE.txt`（Apache-2.0, 9 618 B） | `COPYING`（GPLv3, 35 147 B） | README |
|---|---|---|---|
| 2011-01-14 首个导入 commit `007c3eb75d` | — | **存在** | — |
| **`cb950614`（2017-08-04，被 pin）** | **存在（唯一）** | **不存在** | "released under [Apache 2.0][1]"，`[1]`→ GPL 页 |
| tag `v0.7.17`（2017-10）/ `v0.7.18` / `v0.7.19` | 不存在 | **存在** | — |
| `master`（2026） | 404 | **存在** | `BWA is released under [GPLv3][1]` |

- `compare/cb950614...v0.7.17` 返回 `status=diverged`（谱系已分叉），解释了"同期出现两种许可文件"。
- `lh3/bwa` 的 commit 记录里，2020-07-01 有 `added MIT license to some non-GPL source files`、2020-07-02 有 `added the MIT license header to main.c`。
- **今天（master）bwa-mem 核心已是逐文件 MIT**（我独立复核，21 个文件带 MIT 头）：`bwa.c / bwamem.c / bwamem_pair.c / bwamem_extra.c / bntseq.c / bwt.c / bwtindex.c / fastmap.c / ksw.c / utils.c / main.c` + `khash.h / kseq.h / ksort.h / kvec.h`；`COPYING`=GPLv3 治理的是无头的遗留文件（`bwtaln.c / bwape.c / bwase.c / bwtsw2_*` 等）与整体分发；master 上唯一带 GPL 头的文件是 `bwt_gen.c`。

**⇒ 判断**：被编译进 `libbwa.Linux.so` 的代码，在该快照下**受 Apache-2.0（仓库唯一许可文件）治理，另有 13 个文件自带 MIT 头**；**"GPLv3 BWA 被编进去"不成立**。作者对 bwa-mem 核心的宽松意图也在 2020 年的 MIT 头补加上得到印证。

**但仍有两个真实问题**：
1. **上游许可声明不一致**（2017 树内 Apache-2.0 vs 前后 GPLv3 vs README 链接指 GPL）。这是**上游缺陷**，不是我们能修的；写进风险登记即可。
2. **构件的许可声明是错的**（见 §3.5）—— 这才是我们要处理的。

### 3.4 【实测】BWA 二进制确实在官方发布物里

**（a）Maven 构件** `org.broadinstitute:gatk-bwamem-jni:1.0.4` 解包后：
```
      215452  libbwa.Darwin.dylib
      744135  libbwa.Linux.so
      15390  org/broadinstitute/hellbender/utils/bwa/BwaMemAligner.class
      15101  org/broadinstitute/hellbender/utils/bwa/BwaMemIndex.class
```

**（b）`libbwa.Linux.so` 里确认是 BWA 本体**（扫描字符串，60 个 BWA 相关符号/字符串）：
```
bwa_idx_build  bwa_idx_load  bwa_idx_load_bwt  bwa_idx_load_from_disk  bwa_idx2mem
bwa_mem2idx    bwa_idx_destroy  bwa_idx_infer_prefix  bwa_gen_cigar  bwa_gen_cigar2
bwa_fill_scmat bwa_verbose  bwa_print_sam_hdr  bwa_set_rg  bwa_rg_id
bwa_insert_header  bwa_fa2pac  bwa_pac2bwt  bwa_bwtupdate  bwa_bwt2sa  bwa_index
??bwamem.c     bwamem_pair.c   bwamem_extra.c
[bwa_index] Pack FASTA...
```

**（c）官方 `gatk.jar` 里就有它。** 从官方 release zip 解出 `gatk-package-4.7.0.0-local.jar`（= Dockerfile 里 `gatk.jar` 指向的文件），原生库清单包含：
```
      215452  libbwa.Darwin.dylib
      744135  libbwa.Linux.so
      173424  libfml.Linux.so
    25391160  libtiledbgenomicsdb.so
    37454912  libtiledbgenomicsdb.dylib
      812712  com/intel/gkl/native/libgkl_compression.so
```
`libbwa.Linux.so` 744 135 B 与 Maven 构件一致（`libtiledbgenomicsdb.so` 25 391 160 B 亦与 genomicsdb jar 一致），**说明 §2.4 的 ELF 结论可直接套用到 Docker 镜像内的二进制。**

Docker 链路（**出处**：https://raw.githubusercontent.com/broadinstitute/gatk/master/Dockerfile）：
```
RUN ... /gatk/gradlew clean collectBundleIntoDir shadowTestClassJar shadowTestJar -Drelease=$RELEASE && ...
COPY --from=gradleBuild /gatk/unzippedJar .
RUN ln -s $( find /gatk -name "gatk*local.jar" ) gatk.jar && ...
```
配合 `build.gradle`：
```groovy
shadowJar { configurations = [project.configurations.runtimeClasspath]; archiveClassifier = 'local'; ... }
```
`runtimeClasspath` 含 `gatk-bwamem-jni:1.0.4`，故 `libbwa.*` 被打进 `gatk-package-<v>-local.jar`。

### 3.5 真正的问题：署名与许可证文本缺失

对 jar 内所有 `notice|licen|copying` 文本文件做关键词扫描：
```
   org/broadinstitute/hellbender/utils/alignment/MUMmer-4.0.0rc1_LICENSE.md  ->  Artistic
   gnu/getopt/COPYING.LIB  ->  GPL
   META-INF/license/LICENSE.aix-netbsd.txt  ->  non-commercial
   META-INF/license/LICENSE.boringssl.txt  ->  non-commercial
   META-INF/NOTICE.markdown  ->  GPL
```
**`bwa` / `BWA` / `libuuid` / `uuid` / `libcsv` 一个都没命中。**

**⇒ 即：官方 `gatk.jar` 内含约 744 KB 受 Apache-2.0（+ 13 个 MIT 文件）治理的 BWA 代码，却没有 Apache-2.0 文本、没有 MIT 文本、没有对 Heng Li / GRL / Broad / 能源部-DFCI 的任何归属声明。** 这是 Apache-2.0 §4 与 MIT"须保留版权与许可声明"条款的实际违反而非 GPL 问题；由我们分发时，义务转移到我们头上。

### 3.6 【明确回答】我们的用法下 BWA 会被加载吗？—— **不会**

```
### transitive closure from .../walkers/haplotypecaller/HaplotypeCaller: 763 classes
  target 'utils/bwa/': NOT reachable
```
全 jar 仅 6 个类引用 `BwaMemIndex`：
```
      org/broadinstitute/hellbender/tools/BwaMemIndexImageCreator.class
      org/broadinstitute/hellbender/tools/spark/bwa/BwaSparkEngine$ReadAligner.class
      org/broadinstitute/hellbender/tools/spark/pathseq/PSBwaAligner.class
      org/broadinstitute/hellbender/tools/spark/sv/utils/SingleSequenceReferenceAligner.class
      org/broadinstitute/hellbender/tools/walkers/realignmentfilter/RealignmentEngine.class
      org/broadinstitute/hellbender/utils/bwa/BwaMemIndexCache.class
```
其中唯一像 walkers 的 `RealignmentEngine`，其**唯一引用者**是：
```
### direct referencers of tools/walkers/realignmentfilter/RealignmentEngine
    org/broadinstitute/hellbender/tools/walkers/realignmentfilter/FilterAlignmentArtifacts
```
即独立的 `FilterAlignmentArtifacts` 后处理工具，**与 `HaplotypeCaller` 无关**。

> **⇒ 我们的用法下 `libbwa.Linux.so` 永不加载，BWASpark / PathSeq / SV / FilterAlignmentArtifacts 都不会被调用。** 且如 §3.2 所证，它也不是 GPL 代码 —— 所以它对"无 GPL"政策的威胁远小于原假设。**它剩下的唯一义务是署名/NOTICE。**

### 3.7 若换成"需要重新比对"会额外引入什么

| 场景 | 入口类 | 后果 |
|---|---|---|
| `BwaSpark` | `BwaSparkEngine` → `BwaMemIndexCache` → `BwaMemIndex` | 加载并**执行** `libbwa` |
| `PathSeqBwaSpark` / `PathSeqFilterSpark` | `PSBwaAligner` / `PSBwaFilter` | 同上 |
| SV `FindBreakpointEvidenceSpark` | `FermiLiteAssemblyHandler` → `SingleSequenceReferenceAligner` | 同上，同时加载 `libfml.Linux.so`（fermi-lite，MIT） |
| `BwaMemIndexImageCreator` / `FilterAlignmentArtifacts` | 直接构造索引 / `RealignmentEngine` | 同上 |

**额外义务**：因为是**静态链接**，Apache-2.0 §4 / MIT 的署名义务会实际落到"我们分发的二进制"上（需附 Apache-2.0 全文 + MIT 全文 + BWA 版权归属）。**若你们仍按 GPLv3 认定（保守派法务可能这么读），则必须提供 BWA 完整对应源码。** 两种情形下的最省事解法都是 §7.2 的剥离。

---

## 4. 疑点 C：`LICENSE.TXT` / `build.gradle` 声明的依赖许可清单

### 4.1 前提证实：确实没有 NOTICE / BOM

**（a）`LICENSE.TXT` 只有概括性声明**（**出处**：https://raw.githubusercontent.com/broadinstitute/gatk/master/LICENSE.TXT）：
```
   Copyright 2021 Broad Institute, Inc.

   Licensed under the Apache License, Version 2.0 (the "License");
   ...
   All files in the Genome Analysis Toolkit (GATK) (https://github.com/broadinstitute/gatk) 
   are implicitly licensed under the Apache License, Version 2.0, unless otherwise explicitly stated.
```

**（b）仓库根目录在 tag `4.7.0.0` 的完整文件清单**（GitHub contents API 实测）：
```
  .dockerignore  .dockstore.yml  .gitattributes  .gitignore  AUTHORS
  CODE_OF_CONDUCT.md  Dockerfile  LICENSE.TXT  README.md  build.gradle
  build_docker.sh  build_docker_remote.sh  codecov.yml  gatk  gradle.properties
  gradlew  settings.gradle  testsettings.gradle
```
—— **没有 `NOTICE`**，只有 `LICENSE.TXT` 和 `AUTHORS`。

**（c）发布的 POM 只声明一个许可**（`gatk-4.7.0.0.pom` 实测）：
```xml
  <licenses>
    <license>
      <name>Apache 2.0</name>
      <url>https://github.com/broadinstitute/gatk/blob/master/LICENSE.TXT</url>
      <distribution>repo</distribution>
    </license>
  </licenses>
```
POM 里共 75 个非 test 依赖块、59 个不同 groupId，**没有任何依赖的许可清单**。

> **⇒ 你们的前提成立：GATK4 从未发布 NOTICE/BOM，必须自己查依赖。**

### 4.2 一份"事实上的 SBOM"，但**不完整**（重要方法论警告）

`shadowJar` 保留了各依赖的 `META-INF/maven/<group>/<artifact>/pom.properties`，实测 **308 项**。但**它不是完整清单**，实测缺项包括：

```
missing  org.freemarker:freemarker        missing  com.github.broadinstitute:picard
missing  org.broadinstitute:barclay       missing  com.github.samtools:htsjdk
missing  it.unimi.dsi:fastutil            missing  com.intel.gkl:gkl
missing  org.broadinstitute:gatk-bwamem-jni        missing  org.broadinstitute:gatk-fermilite-jni
missing  org.broadinstitute:http-nio      missing  org.objenesis:objenesis
missing  org.broadinstitute:hdf5-java-bindings     missing  org.broadinstitute:gatk-native-bindings
missing  gnu.getopt:java-getopt
```
而这些库**确实被打包了**（按类路径条目数实测）：
```
   picard      匹配 902 个条目        htsjdk      匹配 1272 个条目
   barclay     匹配 111 个条目        fastutil    匹配 10762 个条目
   freemarker  匹配 1224 个条目       objenesis   匹配 52 个条目
   gkl         匹配 12 个条目（com/intel/gkl/native/*.so）
```
原因是多数的：Gradle 构建的构件（Picard/Barclay/htsjdk/gatk-*-jni/gkl）不带 `pom.properties`；老式 Ant 构建的构件（如 `gnu.getopt:java-getopt`，jar 里有 `Makefile`/`buildx.xml`）也没有。

> **⇒ 生成的第三方清单必须以「`pom.properties` 308 项 ∪ 你自己的依赖解析输出」为准。** 单靠 pom.properties 会漏掉 htsjdk（**LGPL-2.1！**）、gkl、hdf5-native 等关键项。

### 4.3 **本审计最重要的发现：两项 LGPL-2.1 组件在我们的路径上真的会被执行**

#### （1）`htsjdk:5.0.0` 内含 **22 个 LGPL-2.1 文件**（其 POM 只写 MIT）

**出处**：https://repo1.maven.org/maven2/com/github/samtools/htsjdk/5.0.0/htsjdk-5.0.0-sources.jar （我下载后逐文件扫描，801 个 `.java`）

```
  --- LGPL: 22 ---
      htsjdk/tribble/AbstractFeatureReader.java
      htsjdk/tribble/AsciiFeatureCodec.java
      htsjdk/tribble/CloseableTribbleIterator.java
      htsjdk/tribble/FeatureCodec.java
      htsjdk/tribble/FeatureReader.java
      htsjdk/tribble/index/AbstractIndex.java
      htsjdk/tribble/index/interval/Interval.java
      htsjdk/tribble/index/interval/IntervalIndexCreator.java
      htsjdk/tribble/index/interval/IntervalTree.java
      htsjdk/tribble/index/interval/IntervalTreeIndex.java
      htsjdk/tribble/index/linear/LinearIndex.java
      htsjdk/tribble/readers/AsciiLineReader.java
      htsjdk/tribble/readers/PositionalBufferedStream.java
      htsjdk/tribble/util/HTTPHelper.java
      htsjdk/tribble/util/URLHelper.java
      htsjdk/samtools/seekablestream/SeekableFTPStream.java
      htsjdk/samtools/seekablestream/SeekableFTPStreamHelper.java
      htsjdk/samtools/seekablestream/SeekableFileStream.java
      htsjdk/samtools/util/ftp/FTPClient.java
      htsjdk/samtools/util/ftp/FTPReply.java
      htsjdk/samtools/util/ftp/FTPStream.java
      htsjdk/samtools/util/ftp/FTPUtils.java

  --- Apache-2.0: 75 (CRAM)   --- MIT: 383   --- GPL: 0
```
`htsjdk/tribble/FeatureCodec.java` 逐字开头：
```java
/*
 * Copyright (c) 2007-2010 by The Broad Institute, Inc. and the Massachusetts Institute of Technology.
 * All Rights Reserved.
 *
 * This software is licensed under the terms of the GNU Lesser General Public License (LGPL), Version 2.1 which
 * is available at http://www.opensource.org/licenses/lgpl-2.1.php.
 * ...
 */
package htsjdk.tribble;
```
htsjdk 官方 README（tag 5.0.0）自认：
> "the majority of the code is covered under the MIT license with the following notable exceptions:
> * Much of the CRAM code is under the Apache License, Version 2
> * Core `tribble` code (underlying VCF reading/writing amongst other things) is under LGPL"

**为什么这条对我们特别重要**：GATK 的 `FeatureDataSource` 直接 `import htsjdk.tribble.*` 并使用 `AbstractFeatureReader` / `FeatureCodec` / `CloseableTribbleIterator`（见 §2.6(d) 的一手源码），而 **`FeatureDataSource` 在 `HaplotypeCaller` 的 763 类闭包内**。也就是说 —— **与 A/B 不同，`tribble` 的 LGPL-2.1 代码是在我们真实路径上会被加载执行的**（任何 feature 输入如 `--dbsnp` / `--known-sites` 必然走到 `getTribbleFeatureReader`）。而且因为 htsjdk 的 POM 只写 MIT，**下游的 notice 文件几乎必然漏掉它**。

> **好消息**：LGPL-2.1 是**弱 copyleft**。分发**未修改**的 jar + 附 LGPL-2.1 全文 + 保留版权声明 + 提供对应源码（或指向 upstream 的书面说明）即可；不触及你们自己的代码，无需开源你们的代码。对 jar 形式的 Java 库，"可重链接"天然满足。

#### （2）`jgrapht-core:1.1.0` / `jgrapht-io:1.1.0`：**LGPL-2.1 或 EPL-1.0，由被许可方择一**

**出处**：`jgrapht-core-1.1.0-sources.jar` 的 `org/jgrapht/Graph.java` 逐字：
```
 * This program and the accompanying materials are dual-licensed under
 * either
 *
 * (a) the terms of the GNU Lesser General Public License version 2.1
 * as published by the Free Software Foundation, or (at your option) any
 * later version.
 *
 * or (per the licensee's choosing)
 *
 * (b) the terms of the Eclipse Public License v1.0 as published by
 * the Eclipse Foundation.
```
POM 同样列出两条：`<name>GNU Lesser General Public License Version 2.1, February 1999</name>` + `<name>Eclipse Public License (EPL) 1.0</name>`。

**⇒ 关键**：措辞是 **"or (per the licensee's choosing)"** —— **我们可以显式选择 EPL-1.0**，从而**完全避开 LGPL-2.1 §6 的重链接义务**。EPL-1.0 仍是文件级弱 copyleft，但只需：附 EPL-1.0 全文、保留声明、不把 JGraphT 的文件改成别的许可。因为我们分发的是**未修改**的 jgrapht，合规成本很低。

**这两项都是 `build.gradle` 的直接依赖**：
```groovy
implementation 'org.jgrapht:jgrapht-core:1.1.0'
implementation 'org.jgrapht:jgrapht-io:1.1.0'
```
且 `HaplotypeCaller` 的 read-threading 图算法（`haplotypecaller/graphs/`）**真的在用 jgrapht**，无法轻易剥离。

### 4.4 其余非宽松项：全部可回避或仅需署名

| 构件 | 许可 | 镜像分发结论 |
|---|---|---|
| `gnu.getopt:java-getopt:1.0.13`（`org.genomicsdb:genomicsdb` 的**传递依赖**，其 POM 声明 `gnu.getopt:java-getopt:${gnu.getopt.version}` = 1.0.13；**其自身 POM 没有 `<licenses>` 块**） | **LGPL-2.0**（jar 内 `gnu/getopt/COPYING.LIB` 逐字：`GNU LIBRARY GENERAL PUBLIC LICENSE / Version 2, June 1991`） | 需通告 + 许可证文本。**好消息**：jar 内已随附完整源码 `gnu/getopt/Getopt.java`(48 KB) 与 `LongOpt.java`，LGPL 的对应源码要求实际已满足。由 `org/genomicsdb/model/CommandLineImportConfig.java` 引用（实测 `tracepkg` 定位） |
| `com.sun.jersey:{core,client,servlet}:1.19`、`{server}:1.19.4`、`contribs:jersey-guice:1.19.4` | **CDDL-1.1 OR GPL-2.0-CE**（双许可） | 择 CDDL-1.1 即可，**永不需要接受 GPL 分支**。⚠ 这 5 个 jar **完全不带许可证文件**，文本需我们补 |
| `javax.ws.rs:jsr311-api:1.1.1` | **CDDL-1.0（单一，非双）** | 仅需通告。jar 不带许可文件 |
| `jakarta.ws.rs:jakarta.ws.rs-api:2.1.6` | **EPL-2.0 OR GPL-2.0-CE** | 择 EPL-2.0。这个 jar 自带 `META-INF/LICENSE.md` + `NOTICE.md` |
| `org.javassist:javassist:3.29.2-GA` | MPL-1.1 / LGPL-2.1 / **Apache-2.0**（三许可） | **显式选 Apache-2.0，义务消失**。jar 不带许可文件 |
| `io.netty:netty-tcnative-boringssl-static:2.0.70.Final` | Apache-2.0 包装 + 内嵌 BoringSSL（ISC + OpenSSL + SSLeay） | 仅**署名义务**。需在文档中复制 OpenSSL/SSLeay 的致谢句。⚠ 许可文件只在 `-linux-x86_64` classifier jar 里，shadow 易丢 |
| `org.fusesource.leveldbjni:leveldbjni-all:1.8` | BSD-3，但内嵌 hawtjni（EPL-1.0 或 Apache-2.0）、leveldb-api（Apache-2.0）、native LevelDB（BSD-3） | 择 Apache-2.0 后仅需通告 |
| `com.intel.gkl:gkl:0.9.1` | **MIT** + BSD-3（ISA-L、GATK PairHMM）+ Zlib | **不是 Intel 非商用许可**。全部内嵌 `.so` 已扫描，**无 MKL**；只引用宿主 `libgomp.so.1`（GCC 运行时例外） |
| `org.reflections:reflections:0.9.10` | WTFPL **或** New BSD（POM）；upstream master 为 WTFPL-2 + Apache-2.0 | 法律上零限制；WTFPL **非 OSI 认证**，会触发"非 OSI 许可"合规勾选项，属流程问题 |
| `gov.nist.math.jama:1.1.1` | **public domain**（jar 内 `copyright.html`："released to the public domain"） | 无义务 |
| `org.broadinstitute:*`（barclay/gatk-native-bindings/http-nio/gatk-fermilite-jni） | BSD-3（fermilite-jni 另含 MIT fermi-lite） | 仅需通告。⚠ fermilite-jni jar 不带任何许可文本 |
| `org.broadinstitute:hdf5-java-bindings:1.2.0-hdf5_2.11.0` | BSD-3（bindings）+ 内嵌原生 **HDF5 1.8.14**（HDF Group 许可，**明示允许商业用途**）+ zlib 1.2.8 + Univ. of New Mexico 声明 | 仅需通告。⚠ **jar 完全不带许可/通告文件**，须我们补 |
| `com.github.fommil.netlib:netlib-native_ref/solid_*` | BSD-3（Reference LAPACK） | 通告即可。`netlib-native_system-*` 的 BLAS/LAPACK 来自宿主 OS，未打包 |
| CRAM 相关（htsjdk 内 75 文件） | Apache-2.0 | 通告即可 |

### 4.5 澄清：几项常被误传为 GPL/AGPL 的组件，**实测都不是**

我原本的怀疑与业界的常见说法都错了，如实更正以免你们走弯路：

| 组件 | 常见误解 | **实测** | 证据 |
|---|---|---|---|
| `org.jpmml:pmml-model:1.4.8` | AGPL-3.0 | **BSD-3-Clause** | POM `<name>BSD 3-Clause License</name>`；[tag 1.4.8 的 LICENSE.txt](https://raw.githubusercontent.com/jpmml/jpmml-model/1.4.8/LICENSE.txt)："Copyright (c) 2009, University of Tartu ... 3. Neither the name of the copyright holder…"。**AGPL 在姊妹项目 `org.jpmml:pmml-evaluator`（AGPL-3.0，可付费换 BSD-3）—— 请检查你们的清单里有没有 `pmml-evaluator*`** |
| `org.json:json:20231013` | "JSON License"（Good, not Evil） | **Public Domain** | POM `<name>Public Domain</name>`；[上游 LICENSE](https://raw.githubusercontent.com/stleary/JSON-java/20231013/LICENSE) 全文仅一行 `Public Domain.`；对 jar **逐字节扫描 `Good, not Evil` = 0 命中**。（20211205/20220320 仍是旧 JSON License，已换） |
| `gsalib`（GATK 把 CRAN 的 gsalib 打进 jar） | GPL | **MIT** | jar 内 `org/broadinstitute/hellbender/utils/R/gsalib.tar.gz` 解包后 `gsalib/DESCRIPTION`：`License: MIT + file LICENSE`；`gsalib/LICENSE`：`YEAR: 2012 / COPYRIGHT HOLDER: The Broad Institute` |
| `MUMmer 4.0.0rc1`（2.6 MB 二进制打进 jar） | GPL | **Artistic License 2.0** | jar 内 `..._LICENSE.md` 开头 `The Artistic License 2.0 / _Copyright © 2000-2006, The Perl Foundation._`。**但 Artistic-2.0 §5 有源码指引义务**，GATK 已履行 —— 同 jar 内 `..._README.TXT` 写明 "This is an unmodified distribution of MUMmer 4.0.0rc1, compiled from source using the commands: ... Full source code is available here: https://github.com/mummer4/mummer/releases/download/v4.0.0rc1/mummer-4.0.0rc1.tar.gz"。**这条信息必须在我们的 NOTICE 里继承，否则会丢掉一个已履行的义务** |
| `com.github.jsr203hadoop:jsr203hadoop:1.0.3` | vendored GNU getopt | **Apache-2.0，且不含 getopt** | 对 jar 与 sources jar **逐字节扫描 `getopt` = 0 命中**；`gnu/getopt` 的真正来源是 `gnu.getopt:java-getopt:1.0.13`（§4.4） |

### 4.6 `shadowJar` 静默丢弃了大量依赖的 NOTICE/LICENSE

`gatk.jar` 里存活的许可/通告文件只有很少几个（实测）：
```
       172  META-INF/NOTICE            <- 内容其实是 "Spark Project ML Library"
       103  NOTICE                     <- "developed by The Apache Software Foundation"
       192  META-INF/NOTICE-binary     <- "Apache Hadoop Third-party Libs"
      1541  META-INF/NOTICE.txt        896  META-INF/NOTICE.md
      1894  META-INF/NOTICE.markdown   11358  META-INF/LICENSE
     11558  LICENSE                   15217  META-INF/LICENSE.txt
      3047  META-INF/thirdparty-LICENSE（fast_float/bigint 等）
      1731  META-INF/licenses-binary/LICENSE.protobuf.txt
+ META-INF/license/LICENSE.{aix-netbsd,boringssl,mvn-wrapper,tomcat-native}.txt
     25283  gnu/getopt/COPYING.LIB
      8909  org/broadinstitute/hellbender/utils/alignment/MUMmer-4.0.0rc1_LICENSE.md
```
**问题**：308+ 个依赖里有大量各自带 `META-INF/NOTICE`（Spark 全家族、Hadoop 全家族、Netty、Jersey、Guava、Jackson、log4j…），而 `shadowJar` 合并时**同名文件只保留一份** —— 结果 `META-INF/NOTICE` 只剩 Spark ML 那一条，其余依赖的归属声明被静默覆盖丢失。

这同时解释了 §3.5 的扫描结果：**"不是没人写，而是写了也被覆盖掉"**。**⇒ 绝不能把 GATK jar 内的许可文件当完整清单。**

### 4.7 镜像里除 jar 之外的组件 —— **专有组件 Intel oneMKL 与真正的 GPL 组件 R/GSL**

官方 `Dockerfile`：`ARG BASE_DOCKER=broadinstitute/gatk:gatkbase-3.3.1`，随后 `RUN conda env create -vv -n gatk -f /gatk/gatkcondaenv.yml`。README 自述镜像另含 `bedtools 2.30.0`、`samtools 1.13`、`bcftools 1.13`、`tabix 1.13+ds`，以及 Python 3.10.13 与 R 4.3.1。

**（a）官方 conda 环境模板的逐字内容**（**出处**：https://raw.githubusercontent.com/broadinstitute/gatk/master/scripts/gatkcondaenv.yml.template ）：
```yaml
channels:
- conda-forge
- bioconda

dependencies:
- conda-forge::python=3.10.13
- conda-forge:pip=23.3.1
- conda-forge:blas=1.0=mkl            # our official environment uses MKL versions of various packages
- conda-forge::numpy=1.26.2
- conda-forge::pymc=5.10.1
- conda-forge::scipy=1.11.4
- conda-forge::h5py=3.10.0
- conda-forge::pytorch=2.1.0=*mkl*100
- conda-forge::pytorch-lightning=2.4.0
- conda-forge::scikit-learn=1.3.2
- conda-forge::matplotlib=3.8.2
- conda-forge::pandas=2.1.3
- conda-forge::tqdm=4.66.1
- conda-forge::dill=0.3.7
- conda-forge::biopython=1.84

# core R dependencies; these should only be used for plotting and do not take precedence over core python dependencies!
- r-base=4.3.1
- r-data.table=1.14.8
- r-dplyr=1.1.3
- r-getopt=1.20.4
- r-ggplot2=3.4.4
- r-gplots=3.1.3
- r-gsalib=2.2.1
- r-optparse=1.7.3
- r-backports=1.4.1

- bioconda::pysam=0.22.0
- conda-forge::pyvcf=0.6.8
- pip:
  - gatkPythonPackageArchive.zip
```
注意源码里的注释本身就承认了：`# our official environment uses MKL versions of various packages`。

**（b）🔴 最高严重度：Intel oneMKL 是专有、非开源组件。**
`blas=1.0=mkl`（强制 MKL 作为 BLAS 实现）与 `pytorch=2.1.0=*mkl*100`（显式请求 MKL 版 PyTorch 构建）会引入 Intel oneMKL。conda-forge 的打包配方（**出处**：https://raw.githubusercontent.com/conda-forge/intel_repack-feedstock/main/recipe/meta.yaml ，本次实测）对 `mkl` / `mkl-include` / `onemkl-sycl-*` / `dal` / `dal-gpu` / `impi_rt` / `mkl-static` / `mkl-devel` 等**每一个输出**都标注：
```yaml
    about:
      license: LicenseRef-IntelSimplifiedSoftwareOct2022
      license_family: Proprietary
      license_file:
         - mkl/info/licenses/license.txt
         - mkl/info/licenses/tpp.txt
```
配方顶层也写 `about: license: LicenseRef-IntelSimplifiedSoftwareOct2022`。

**⇒ 即"Intel Simplified Software License (ISSL, Oct 2022)"—— 二进制-only、禁止反向工程、再分发须复制版权声明与条款。** 这不是"非商用"（ISSL 允许商业使用），但它是**专有 / 非 OSI 认证**许可，且带来真实的再分发义务。**对"镜像内不得含非开源组件"这类政策，它比 LGPL 更值得警惕，因为它连源代码都拿不到。**

> **须核实的点**：本报告未能直接检视构建好的镜像。请用 `conda list -n gatk | grep -i mkl`（或 `conda list -n gatk`）确认 MKL 实际被解析安装。**但模板的 `blas=1.0=mkl` 与 `*mkl*100` 构建串已近乎确证。**

**（c）镜像内的真实 GPL 组件（R 技术栈）**

| 组件 | 许可 | 说明 |
|---|---|---|
| `r-base=4.3.1` | **GPL-2.0-or-later** | conda-forge 的 r-base |
| `gsl`（`r-base` 的硬运行依赖） | **GPL-3.0-or-later** | — |
| `r-gplots=3.1.3` | GPL-2.0-only | 由 `r-ggplot2`/绘图需求拉入 |
| `r-catools`、`r-gtools` | GPL-3.0-only / GPL-2 | 由 `r-gplots` 拉入 |
| `r-mass`、`r-mgcv` | GPL-2+ | 由 `r-ggplot2` 拉入 |
| `r-getopt=1.20.4`、`r-optparse=1.7.3`、`r-backports=1.4.1` | GPL-2+ | — |
| `r-base` 的运行依赖 `gcc_impl_linux-64`、`gxx_impl_linux-64`、`gfortran_impl_linux-64`、`make`、`sed` | GPL-3 编译器/工具二进制 | — |

> **⇒ R 技术栈是镜像内真正的 GPL 集群**，与 GATK 自身版权无关，但直接违反"镜像内不得含 GPL"。**且它无法靠"剥离 jar 里的 .so"消除** —— 必须自己写 Dockerfile、去掉 R 相关依赖（`r-*` 全部）才能解决。这也顺带去掉 GSL 与绘图相关的 copyleft。

**（d）base 镜像与其它 apt 组件**（由并行审计员从发行版元数据核实）
- `bedtools`：许可随版本变化 —— 上游 tag `v2.25.0` 的 LICENSE 是 **GNU GPL v2**，tag `v2.30.0` 已改为 **MIT**。Ubuntu 22.04 装的是 `bedtools 2.30.0+dfsg-2`（上游 MIT），**但其 debian/copyright 元数据仍写 GPL-2、Source 行仍指向 v2.25.0.tar.gz** —— 属发行版元数据陈旧。**结论：镜像里实际装的是 MIT 版；建议记录并注明依据。**
- `bcftools 1.13-1`：上游为 **MIT/Expat 或 GPL 双许可**，但 Ubuntu 的 copyright 明确警告 "When linked with the GPL-licensed GNU Scientific Library (as is done for this Debian package), the resulting program must be distributed under the GPL." —— **并行审计员用二进制取证推翻了这一点**：jammy 的 bcftools 1.13-1 `Depends` = `libc6, libhts3, zlib1g`（**无 `libgsl27`**），且 ELF 中无任何 libgsl 引用。**⇒ 该镜像内的 bcftools 走 MIT 分支，GPL 分支未被触发。**
- `samtools` / `tabix` / `htslib`：MIT/Expat（`cram/` 为 BSD-3）。**注意**：这与 GATK 内部打包的 htsjdk 是两回事（见 §4.3）。

---

## 5. 【核心结论】"我们当前用法"下是否需要担心？

### 第 1 层 · 运行时会不会被加载 —— **A 和 B 都不会，不需要担心**

| 组件 | 是否加载 | 依据 |
|---|---|---|
| `libtiledbgenomicsdb.so`（含静态 libuuid） | **否** | `HaplotypeCaller` 的 763 类闭包中 `org.genomicsdb.*` 不可达；native 库仅由 `GenomicsDBImporter`/`GenomicsDBFeatureReader`/`GenomicsDBQuery(Stream)` 经 `GenomicsDBLibLoader` 加载；`FeatureDataSource` 仅在 `IOUtils.isGenomicsDBPath(...)` 为真时走那条分支（§2.6） |
| `libbwa.Linux.so`（BWA） | **否** | 同一闭包中 `utils/bwa/` 不可达；全 jar 仅 6 类引用 `BwaMemIndex`，全属 BwaSpark/PathSeq/SV/`FilterAlignmentArtifacts`（§3.6） |
| `libfml.Linux.so`（fermi-lite，SV 用） | **否** | 仅被 SV 路径引用 |

如果验收标准是"运行时不会调用这些代码"，**可以签收。**

### 第 2 层 · 分发合规 —— **必须处理，但 A/B 好解决**

GPL/LGPL 义务附着在**分发副本**上，与执行路径无关。要把 A/B 归零，**最省事的做法就是删掉它们**（§7.2），因为我们确实不用。

### 第 3 层 · 真正的重点：两项**无法剥离、且真的在执行**的 LGPL-2.1

| 组件 | 是否在我们路径上执行 | 严重度 |
|---|---|---|
| **`htsjdk` 的 `tribble`（LGPL-2.1，22 个文件）** | **是**。GATK `FeatureDataSource` 直接使用 `htsjdk.tribble.AbstractFeatureReader`/`FeatureCodec`/`CloseableTribbleIterator`，而它在 `HaplotypeCaller` 闭包内；任何 feature 输入（`--dbsnp`/`--known-sites`）必然执行 `getTribbleFeatureReader` | **高**。且 htsjdk 的 POM 只写 MIT，**下游 notice 几乎必然漏掉它** |
| **`jgrapht-core/io`（LGPL-2.1 或 EPL-1.0，可选 EPL）** | **是**。`HaplotypeCaller` 的 read-threading 图算法在用 | 中。**可显式择 EPL-1.0 规避 LGPL §6** |
| `gnu.getopt:java-getopt`（LGPL-2.0） | 否（`CommandLineImportConfig` 属 GenomicsDB 导入工具链） | 低。且源码已随 jar 分发 |

**⇒ 决策点 1**：你们的政策写的是"不得含 **GPL** 或非商用组件"。**LGPL 不是 GPL。** 按字面理解，GATK4 可用，只需把 LGPL 通告做干净。**但若法务本意是"不得含任何 copyleft"，那么 GATK4 对这条流水线基本不可用** —— tribble 与 jgrapht 无法剥离。**建议先澄清这一点，再决定是否换 caller。**

### 第 4 层 · **官方镜像的 conda 环境里有专有组件和真正的 GPL —— 这是最严重的一层**

| 组件 | 性质 | 能否靠剥离 jar 解决 |
|---|---|---|
| **Intel oneMKL**（`blas=1.0=mkl`、`pytorch=2.1.0=*mkl*100`） | **专有、非开源**（`LicenseRef-IntelSimplifiedSoftwareOct2022`，`license_family: Proprietary`），**源码不可得** | **不能**。只能自己写 Dockerfile 换掉 |
| **GSL**（`r-base` 硬运行依赖） | **GPL-3.0-or-later** | **不能** |
| **R 4.3.1 技术栈**（`r-base` GPL-2+，以及 `r-gplots` GPL-2-only、`r-catools` GPL-3-only、`r-mass`/`r-mgcv`/`r-getopt`/`r-optparse`/`r-backports` GPL-2+，`gcc/gxx/gfortran_impl` GPL-3 编译器） | **真正的 GPL** | **不能**。只能去掉全部 `r-*` 依赖 |
| `liblzma5` | LGPL-2.1+（**动态**链接） | 无需处理，附通告即可 |
| GPL userland（`bash`/`coreutils`/`sed`/`tar`/`grep`/`gzip`/`make`/`wget`/`git`/`dpkg`） | GPL-2/GPL-3+ | **不可能消除**（任何 Ubuntu 镜像都有）→ **必须按"聚合"处理并放行** |
| `libgcc`/`libstdc++`/`libgomp`（GPL-3 **WITH GCC-exception-3.1**）、OpenJDK（GPL-2 **WITH Classpath-exception-2.0**） | 带例外的 copyleft | **假阳性，放行** |
| btcfools 1.13-1 | 已取证为 MIT 分支（无 libgsl 链接） | 无需处理 |
| bedtools 2.30.0 | 镜像内实为 MIT 版 | 无需处理，但建议记录依据 |

**⇒ 决策点 2**：如果你们要严格满足"镜像内不得含 GPL 或非开源组件"，**最关键的动作不是处理 GATK 的 jar，而是自己写一份精简 Dockerfile**：以 `python:3.10-slim`（或同类）为 base、只装 GATK 的 Java 依赖与你们真正用到的 CLI 工具、BLAS 用 `openblas`/`blis` 而非 `mkl`、**不装任何 R 包**。这样第 4 层的问题一次性消失，且镜像体积会大幅下降。

**⇒ 决策点 3（最优先）**：**请先与法务确认"不得含 GPL"的确切含义。** 因为 `bash`/`coreutils` 等 GPL-3 二进制必然存在，"字面零 GPL"不可能达成；政策只能指"不得含与我们应用构成组合作品、或我们依赖其核心功能的 GPL 组件"。**确认这一条之后，第 3 层（tribble/jgrapht）与第 4 层（MKL/R/GSL）的取舍才有意义。**

---

## 5.1 四层汇总：一张表看清"要不要担心"

| 层 | 内容 | 在我们的用法下 | 处理动作 |
|---|---|---|---|
| 1 运行时 | A（GenomicsDB+libuuid）、B（BWA）是否被加载 | **都不加载**（763 类闭包已证） | 无需动作 |
| 2 分发（jar 内原生库） | `libbwa.*`、`libtiledbgenomicsdb.*`、`libfml.*` | 存在于镜像中 → 有分发义务（**但 A 的 copyleft 前提已被推翻，B 也不是 GPL**；主要剩署名义务） | `zip -d` 剥离 + `MODIFICATIONS.md`（仍建议做，成本极低） |
| 3 分发（jar 内 Java LGPL，**且真的在执行**） | `htsjdk` 的 `tribble`（LGPL-2.1，POM 谎称 MIT）、`jgrapht`（LGPL-2.1 或 EPL-1.0）、`gnu.getopt:java-getopt`（LGPL-2.0） | **tribble 与 jgrapht 真的执行**，无法剥离 | 补 LGPL/EPL 文本与通告；jgrapht **显式择 EPL-1.0**；java-getopt 源码已在 jar 内。**若"零 copyleft"则必须换 caller** |
| 4 分发（conda/base 环境） | **Intel MKL（专有，源码不可得）**、**GSL（GPL-3）**、**R 技术栈（GPL）**、`liblzma5`（LGPL-2.1+，动态）、GPL userland（不可避免） | 存在于镜像中 | **自己写 Dockerfile**：去 R、BLAS 换 openblas/blis；GPL userland 按聚合放行 |

---

---

## 6. 若必须"零 copyleft"：替代路径

> 以下许可均由并行审计员读上游 LICENSE 一手核实，我在关键项（bwa-mem2）上做了独立复核。

### 6.1 比对（reads → BAM）

| 方案 | 许可 | 说明 |
|---|---|---|
| **`bwa-mem2`** | **MIT**（[LICENSE](https://raw.githubusercontent.com/bwa-mem2/bwa-mem2/master/LICENSE)：`Copyright (C) 2019 Intel Corporation, Heng Li`） | **可用的最干净路线，但必须 pin 版本 ≥ 2.0**：其 `NEWS.md` Release 2.0pre2（2020-02-04）明确记载 `* Changed the license from GPL to MIT.` —— **2.0 之前的版本是 GPL。用 v2.3 或 v2.2.1。** 已核验：v2.3 全源码搜 `GNU General Public License`/`Affero` = 0 命中；`src/` 不含 `bwtsw2_*`/`bwtaln.c`/`bwape.c`/`bwase.c`/`bwt_gen.c`/`QSufSort.c`/`is.c`/`rope.c`/`rle.c`（即不含 BWA 的 GPL 遗留组件） |
| **`minimap2`** | **MIT**（[LICENSE.txt](https://raw.githubusercontent.com/lh3/minimap2/master/LICENSE.txt)：`Copyright (c) 2018- Dana-Farber Cancer Institute / 2017-2018 Broad Institute, Inc.`） | 干净 |
| `STAR` | MIT（[LICENSE](https://raw.githubusercontent.com/alexdobin/STAR/master/LICENSE)） | 干净；但源码文件无逐文件头，且 `Source/` 下打包了 htslib/samtools，需按所用 tag 复核 |
| `bwa`（原方案） | 分发层面 `COPYING`=GPL-3.0，但 bwa-mem 核心逐文件 MIT | **不建议**。它的 GPL 印象会持续拖累你们的合规材料 |
| `bowtie2` / `HISAT2` / `dragmap` | **GPL-3.0** | **避免**（dragmap 的许可文件是 `/COPYRIGHT`，`/LICENSE` 404） |

### 6.2 变异检出（caller）

| 方案 | 许可 | 说明 |
|---|---|---|
| **`DeepVariant`** | **BSD-3-Clause**（[LICENSE](https://raw.githubusercontent.com/google/deepvariant/master/LICENSE)） | 干净。⚠ 注意它是**替换整个 HaplotypeCaller**，评测语义会变；且 Google 的预构建镜像里打包了大量第三方组件，若用其镜像需另行盘点，建议自己 build |
| **`FreeBayes`** | **MIT**（[LICENSE](https://raw.githubusercontent.com/freebayes/freebayes/master/LICENSE)：`Copyright (c) 2010 Erik Garrison, Gabor Marth`） | 干净。其 `contrib/SeqLib/LICENSE` = Apache-2.0。**功能上最接近单样本 germline calling 的替代** |
| **`bcftools` + `htslib`** | **MIT/Expat（可选 GPL 分支）** | htslib [LICENSE](https://raw.githubusercontent.com/samtools/htslib/develop/LICENSE)："Files ... outwith the cram/ subdirectory are distributed according to ... MIT/Expat"（`cram/` 为 BSD-3）。⚠ **bcftools 的 GSL 陷阱**：其 LICENSE 说 `If compiled with the GNU Scientific Library ... the use of this software is governed by the GPL license.` GSL 默认关闭 —— **构建时绝不要启用** |
| `Strelka2` | **GPL-3.0** | **避免** |
| `VarScan` | **专有 / 非商用**（仓库**没有** LICENSE 文件）：`VarScan 2 is free for non-commercial use by academic, government, and non-profit/not-for-profit institutions. A commercial version ... licensed through the Office of Technology Management at Washington University School of Medicine.` | **避免** —— 正是你们政策明确禁止的"非商用" |
| `Sentieon` | **商业专有**（EULA 禁止复制/再分发） | **无法放进可再分发的公开镜像** |
| `LoFreq` | 仓库自称 MIT，**但存在未决缺口** | `src/cdflib90.README` 只有描述、**无许可条款**；其 LICENSE 引用的 `src/samtools-1.1.LICENSE`/`htslib-1.1.LICENSE` 均 404。**若要用，必须 pin 精确版本并重读该 tag 的 LICENSE** |

### 6.3 你们已在用的评测工具

**`hap.py`（Illumina）与 `vcfeval`（RTG）的许可未在本次范围内核实** —— 但它们同样在镜像里、同样受同一政策约束。**建议列入下一轮审计。**

---

## 7. 镜像里应该放什么声明

### 7.1 生成准确清单的正确做法

**不要把 `pom.properties` 当完整清单**（§4.2 已证它会漏掉 htsjdk 这种 LGPL 项）。正确做法是：

```bash
# 1) 取 GATK shadow jar 内的 pom.properties（308 项，覆盖 Maven 构建的依赖）
# 2) 与你们自己的依赖解析输出取并集（覆盖 Gradle/Ant 构建的依赖）
#    Gradle: ./gradlew dependencies --configuration runtimeClasspath
# 3) 对每一项反查 Maven Central 的 <licenses> 块并生成表
#    https://repo1.maven.org/maven2/<g>/<a>/<v>/<a>-<v>.pom
# 4) 对"自述与实质不符"的项做二进制/源码实测
```
第 4 步不可省 —— 本审计已抓到**三处自述与实质不符**：
- `com.github.samtools:htsjdk:5.0.0` POM 只写 MIT，**实际含 22 个 LGPL-2.1 文件**
- `org.broadinstitute:gatk-bwamem-jni:1.0.4` POM 只写 BSD-3，**实际内含 Apache-2.0+MIT 的 BWA 代码**
- `org.genomicsdb:genomicsdb:1.5.5` POM 写 MIT，**实际静态链接 LGPLv2 libuuid，并传递依赖 LGPL-2.0 的 java-getopt**

把这些结果固化为 `THIRD-PARTY-LICENSES.md` 随镜像发布。

### 7.2 建议的镜像结构与剥离操作

**（A）推荐：发布精简版**

```bash
# 从镜像里的 gatk.jar 删除不需要的原生二进制（不改动任何 .class）
zip -d /gatk/gatk.jar 'libbwa.*' 'libtiledbgenomicsdb.*' 'libfml.*'
```
- 删除后：BWA（Apache-2.0/MIT 代码 + 缺失署名）与 libuuid（LGPLv2 静态链接）**都不再被分发**，相应义务彻底消失；
- **必须记录修改**：Apache-2.0 §4(b) 要求 "must cause any modified files to carry prominent notices stating that you changed the files"。请在 `/licenses/MODIFICATIONS.md` 中写明删除了 `libbwa.Linux.so`、`libbwa.Darwin.dylib`、`libfml.Linux.so`、`libfml.Darwin.dylib`、`libtiledbgenomicsdb.so`、`libtiledbgenomicsdb.dylib`；
- **必须文档化能力损失**：`BwaSpark`、`PathSeqBwaSpark`、`BwaMemIndexImageCreator`、`FilterAlignmentArtifacts`、SV 流程中依赖 BWA/fermi-lite 的部分，以及所有 GenomicsDB 相关工具（`GenomicsDBImport`、`GenotypeGVCFs`/`GnarlyGenotyper` 的 GenomicsDB 后端）将不可用（预期 `UnsatisfiedLinkError`）。**对 T1 无影响**；
- **建议冒烟测试**：构建后跑一次小样本 `HaplotypeCaller`，确认剥离未破坏目标路径；再跑 `gatk --list` 确认无类加载错误；
- **注意**：此方案**并不能**解决 §5 第 3 层的 `htsjdk/tribble` 与 `jgrapht`（它们是纯 Java 类，在 jar 里且在用）。

**（B）若你们不想改 jar**：必须完整承担义务 —— 在 `/licenses/` 提供 libuuid 的完整对应源码或三年书面要约（**因为是静态链接，(b) 项豁免不成立**），以及 BWA 的 Apache-2.0 全文 + MIT 全文 + 版权归属（保守派法务若按 GPLv3 认定，还需提供 BWA 完整对应源码）。

**（C）LGPL 项的最小合规动作**（无论 A/B 与否都要做）：
1. **`htsjdk:5.0.0` 的 tribble**：附 LGPL-2.1 全文 + 版权声明 + 指向 htsjdk 对应源码（未修改的 jar 天然满足"可重链接"）；
2. **`jgrapht`**：**在文档中显式声明选择 EPL-1.0**（这正是上游 "or (per the licensee's choosing)" 授权的用法），并附 EPL-1.0 全文；这样就不必再履行 LGPL §6；
3. **`gnu.getopt:java-getopt:1.0.13`**：附 LGPL-2.0 全文（jar 内已有 `gnu/getopt/COPYING.LIB` 与完整源码，可直接引用）；
4. **CDDL/EPL 组（jersey/jsr311/jakarta.ws.rs）**：附 CDDL-1.1 / CDDL-1.0 / EPL-2.0 文本（这些 jar 基本不带许可证文件，须自补）；
5. **`javassist`**：显式声明选择 Apache-2.0；
6. **BoringSSL/OpenSSL/SSLeay 致谢句**必须复制进文档。

### 7.3 `/licenses/` 最小清单

```
/licenses/
├── README.md                    # 本镜像的许可边界 + 已知能力损失说明
├── MODIFICATIONS.md             # Apache-2.0 §4(b)：对被修改的 GATK jar 的说明（方案 A）
├── GATK-LICENSE.TXT             # GATK4 的 Apache-2.0 全文（从上游 LICENSE.TXT 原样复制）
├── THIRD-PARTY-LICENSES.md      # §7.1 生成的逐项表：名称/版本/许可/出处 URL
├── NOTICE                       # 见下
└── texts/
    ├── LGPL-2.1.txt             # htsjdk tribble（+ 若保留 tiledb 则为 libuuid）
    ├── LGPL-2.0.txt             # gnu.getopt:java-getopt
    ├── EPL-1.0.txt              # jgrapht（显式择此）  EPL-2.0.txt（jakarta.ws.rs）
    ├── CDDL-1.1.txt  CDDL-1.0.txt   # jersey / jsr311-api
    ├── Apache-2.0.txt  MIT.txt  BSD-3-Clause.txt  BSD-2-Clause.txt
    ├── Artistic-2.0.txt         # MUMmer
    ├── boringssl-OpenSSL-SSLeay.txt + 致谢句
    └── HDF5-COPYING.txt         # hdf5-java-bindings 内嵌原生 HDF5 1.8.14
```

`NOTICE` 最小内容（按本报告发现的**必须**继承项）：

```
本镜像包含以下第三方组件。完整清单与许可证原文见 THIRD-PARTY-LICENSES.md 与 texts/。

1. Genome Analysis Toolkit (GATK) 4.7.0.0
   Copyright Broad Institute, Inc. — Apache License 2.0
   来源: https://github.com/broadinstitute/gatk/blob/master/LICENSE.TXT
   修改声明: 见 MODIFICATIONS.md

2. htsjdk 5.0.0 — MIT，但 htsjdk/tribble/**、htsjdk/samtools/seekablestream/**、
   htsjdk/samtools/util/ftp/** 共 22 个文件为 GNU LGPL v2.1
   Copyright (c) 2007-2010 The Broad Institute, Inc. and the Massachusetts Institute of Technology
   许可证原文: texts/LGPL-2.1.txt        源码: https://github.com/samtools/htsjdk

3. JGraphT 1.1.0 (jgrapht-core, jgrapht-io) — 本项目显式选择 Eclipse Public License v1.0
   （上游为 LGPL-2.1 或 EPL-1.0 双重许可，由被许可方择一）
   Copyright (C) 2003-2017 Barak Naveh and Contributors
   许可证原文: texts/EPL-1.0.txt          源码: https://github.com/jgrapht/jgrapht

4. gnu.getopt:java-getopt 1.0.13 — GNU Library General Public License v2 (LGPL-2.0)
   本镜像已随附其完整源码 gnu/getopt/Getopt.java 与 gnu/getopt/LongOpt.java

5. MUMmer 4.0.0rc1 — The Artistic License 2.0  (Copyright (c) 2000-2006, The Perl Foundation)
   本镜像包含 MUMmer 4.0.0rc1 的未修改编译发行版（仅部分二进制）。
   完整源码获取方式: https://github.com/mummer4/mummer/releases/download/v4.0.0rc1/mummer-4.0.0rc1.tar.gz
   [Artistic-2.0 §5 要求提供源码获取指引，此条不可省略]

6. gsalib 2.1 — MIT (Copyright 2012, The Broad Institute)

7. BWA（经 gatk-bwamem-jni 1.0.4 静态编入 libbwa.Linux.so）
   Copyright (c) 2008 Genome Research Ltd (GRL); (c) 2008 Yuta Mori;
   (c) 2008-2011 Attractive Chaos; 部分文件 Copyright (c) 2018- Dana-Farber Cancer Institute
   [上游该快照的唯一许可文件为 Apache License 2.0，另有 13 个文件为 MIT]
   [若按 §7.2 方案 A 剥离 libbwa.*，本条可移除]

8. GenomicsDB 1.5.5 — MIT License
   Copyright (c) 2016-2018 Intel Corporation; (c) 2018-2020 Omics Data Automation, Inc.
   [其自带 libtiledbgenomicsdb.so 静态链接了 LGPLv2 的 libuuid；
    若按方案 A 剥离则本条可移除，否则须附 libuuid 源码或三年书面要约]

9. 其他 Apache-2.0 / MIT / BSD 组件（Spark, Hadoop, Netty+tcnative-boingssl,
   Jersey(java 1.x, CDDL-1.1), jsr311-api(CDDL-1.0), jakarta.ws.rs(EPL-2.0),
   javassist(本项目择 Apache-2.0), HDF5 1.8.14, LevelDB, protobuf, GKL …）
   见 THIRD-PARTY-LICENSES.md

10. ⚠ Intel oneAPI Math Kernel Library (oneMKL) — Intel Simplified Software License
    (Version October 2022)，专有许可、非 OSI 认证。本镜像经 conda-forge
    `blas=1.0=mkl` 与 `pytorch=2.1.0=*mkl*100` 引入。
    按 ISSL 要求，再分发须复制 Intel 的版权声明与使用条款原文
    （conda 包内路径: $CONDA_PREFIX/lib/../info/licenses/license.txt）。
    [若不使用 mkl（改用 openblas/blis），本条可移除]

11. R 4.3.1 (GPL-2.0-or-later) 及 conda 环境中的 R 包
    (r-gplots GPL-2.0-only, r-catools GPL-3.0-only, r-gtools GPL-2.0-only,
     r-mass/r-mgcv/r-getopt/r-optparse/r-backports GPL-2.0-or-later)
    与 GSL 2.7 (GPL-3.0-or-later)
    [若镜像不含 R，本条可移除；这是最推荐的简化路径]

12. liblzma5 (xz-utils) — public domain + GNU LGPL v2.1（部分文件），动态链接
13. 其余 Ubuntu/GCC/OpenJDK 组件说明：
    - bash/coreutils/sed/tar/grep/gzip/make/wget/git/dpkg 等为 GPL-2/GPL-3+ 独立程序（聚合）
    - libgcc-s1/libstdc++6/libgomp1 为 GPL-3 WITH GCC Runtime Library Exception
    - OpenJDK 17 为 GPL-2 WITH Classpath-exception-2.0
    以上均为独立程序或带明确链接例外，不构成对我方代码的 copyleft 义务。
```

**若采用 §7.2 方案 A（剥离原生库）并自建精简 Dockerfile（去 R、换 BLAS），上述第 7、8、10、11 条可全部移除，NOTICE 会大幅精简。**

**另外三件必须同步的事**：
1. **`AUTHORS`** 文件（tag 4.7.0.0 根目录确实存在）应随镜像提供或引用；
2. **启动可见声明**：LGPL-2.1 §6 要求 "prominent notice with each copy of the work that the Library is used in it"。建议在镜像 README 顶部体现；
3. **修改声明**：只要对 jar 做了任何改动（含方案 A 的 `zip -d`），Apache-2.0 §4(b) 就要求 "prominent notices stating that you changed the files" —— `MODIFICATIONS.md` 是最低成本的合规方式。

---

## 8. 未核实项与你们可自行核实的步骤

| # | 未核实项 | 原因 | 自行核实步骤 |
|---|---|---|---|
| 0 | **libuuid 的最终定论**：GenomicsDB 的 CentOS 6 构建容器里装的究竟是哪个 libuuid 包（e2fsprogs 还是 util-linux），从而确定被静态链接进 `libtiledbgenomicsdb.so` 的那份代码的确切许可 | 无法访问 `ghcr.io/genomicsdb/genomicsdb:centos_6_prereqs_java_17` 镜像；二进制中无判别性字符串（见 §2.5b） | `docker run --rm ghcr.io/genomicsdb/genomicsdb:centos_6_prereqs_java_17 sh -c 'rpm -qf /usr/lib*/libuuid.a 2>/dev/null \|\| dpkg -S libuuid.a; find / -name "libuuid.a" 2>/dev/null'`；再读该包自带的 LICENSE。**注意：本报告已判定 libuuid 很可能为 BSD-3-Clause，但未 100% 闭合；不过因我们建议剥离该 `.so`，此项不影响最终动作。** |
| 1 | Docker base 镜像（`broadinstitute/gatk:gatkbase-3.3.1`）内 apt 包清单、**Intel MKL 是否真的被解析安装**、conda 环境的确切传递闭包、R 4.3.1 的 GPL 处理 | 本机 Docker daemon 未运行（`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`），无法检视构建好的镜像文件系统；只能静态分析 Dockerfile 与包元数据 | `docker run --rm broadinstitute/gatk:4.7.0.0 sh -c 'conda list -n gatk \| grep -iE "mkl\|^gsl\|r-base"; dpkg -l \| grep -iE "liblzma\|libuuid"; ls -l /lib/x86_64-linux-gnu/libuuid.so.1'` |
| 1b | base 镜像内的 apt 版本（Dockerfile 先跑 `apt full-upgrade -y`，会拉到 -updates/-security；本报告引的是 jammy GA 版本） | 同上 | `docker run --rm broadinstitute/gatk:4.7.0.0 dpkg -l bedtools samtools bcftools tabix openjdk-17-jdk liblzma5 libuuid1` |
| 2 | `hap.py` / `vcfeval` 的许可 | 超出本次范围 | 分别读 Illumina/hap.py 与 RealTimeGenomics/rtg-tools 的 LICENSE |
| 3 | `org.reflections:reflections:0.9.10` 中 WTFPL 与 New BSD 各覆盖哪些文件 | jar 与 sources jar 内均无许可文件；源码无许可头；upstream LICENSE 路径在 master 全 404；GitHub API 命中 403（按要求未反复重试） | 浏览 https://github.com/ronmamo/reflections 与 https://repo1.maven.org/maven2/org/reflections/reflections/0.9.10/reflections-0.9.10.pom |
| 4 | `librocksdbjni-*.so`（jar 内含 11 个平台二进制，约 130 MB）的确切许可 | jar 内只有二进制；`META-INF/NOTICE.markdown` 命中 "GPL" 需进一步定位 | 查 `org.rocksdb:rocksdbjni` 的 Maven POM `<licenses>`；RocksDB 常见为 Apache-2.0 / GPL-2.0 双许可 |
| 5 | `org.jpmml:pmml-evaluator*` 是否在你们镜像里 | 它是 **AGPL-3.0**（可付费换 BSD-3）；本次实测的 `pmml-model:1.4.8` 是 BSD-3，**未发现 evaluator** | `unzip -l gatk-package-*.jar \| grep -i pmml-evaluator`，或检查你们的依赖树 |
| 6 | `META-INF/license/*.txt`（BoringSSL 等）是否在 GATK shadow jar 中保留 | 我在 jar 列表中确实看到了 `META-INF/license/LICENSE.boringssl.txt`（12 486 B）等，**已保留**；但未逐一核对每一条致谢句 | `unzip -l gatk-package-4.7.0.0-local.jar \| grep -i "META-INF/license"` |
| 7 | **未做运行时动态验证**（`strace` 确认 A/B 不被 `dlopen`） | 本机 Docker daemon 未运行（`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`） | 在可用 Docker 的环境执行：<br>`docker run --rm -v $PWD:/w broadinstitute/gatk:4.7.0.0 bash -lc 'strace -f -e trace=openat gatk HaplotypeCaller -I /w/in.bam -R /w/ref.fa -O /w/out.vcf 2>&1 \| grep -Ei "libbwa\|libtiledbgenomicsdb"'`<br>**预期无输出。** 本报告的"不加载"结论由字节码可达性分析得出，**未做运行时验证** |
| 8 | `bwa-mem2` 早期版本（<2.0）的 GPL 期间代码是否仍残留在 v2.3 中 | 已核验 v2.3 全源码搜 GPL 关键词 = 0 命中、且不含 `bwtsw2_*` 等 GPL 遗留组件，但未做逐行 diff | 若用于生产，建议做一次 v2.3 源码与 `cb950614` 的逐文件 diff，并确认 MIT 头覆盖全部派生文件 |

---

## 附录 A：一手出处 URL 汇总

| 主题 | URL |
|---|---|
| GATK4 LICENSE.TXT（Apache-2.0） | https://raw.githubusercontent.com/broadinstitute/gatk/master/LICENSE.TXT |
| GATK4 build.gradle（依赖声明） | https://raw.githubusercontent.com/broadinstitute/gatk/master/build.gradle |
| GATK4 README（许可与镜像内容自述） | https://raw.githubusercontent.com/broadinstitute/gatk/master/README.md |
| GATK4 Dockerfile（镜像构建链路） | https://raw.githubusercontent.com/broadinstitute/gatk/master/Dockerfile |
| GATK4 `FeatureDataSource.java`（GenomicsDB 分支 + htsjdk.tribble 使用） | https://raw.githubusercontent.com/broadinstitute/gatk/4.7.0.0/src/main/java/org/broadinstitute/hellbender/engine/FeatureDataSource.java |
| GATK4 官方发布物（用于实测） | https://github.com/broadinstitute/gatk/releases/download/4.7.0.0/gatk-4.7.0.0.zip |
| GATK4 Maven 构件与版本 | https://repo1.maven.org/maven2/org/broadinstitute/gatk/ |
| GenomicsDB LICENSE（libcsv/libuuid 声明） | https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/LICENSE |
| GenomicsDB CMakeLists.txt | https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/CMakeLists.txt |
| GenomicsDB `Findlibuuid.cmake`（静态库优先） | https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/cmake/Modules/Findlibuuid.cmake |
| GenomicsDB `Findlibcsv.cmake` | https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/cmake/Modules/Findlibcsv.cmake |
| GenomicsDB `install_genomicsdb.sh` | https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/scripts/install_genomicsdb.sh |
| GenomicsDB `Dockerfile.release` | https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/Dockerfile.release |
| GenomicsDB `release_jar.yml` | https://raw.githubusercontent.com/GenomicsDB/GenomicsDB/master/.github/workflows/release_jar.yml |
| GenomicsDB 1.5.5 POM（含 `gnu.getopt:java-getopt` 传递依赖） | https://repo1.maven.org/maven2/org/genomicsdb/genomicsdb/1.5.5/genomicsdb-1.5.5.pom |
| `gnu.getopt:java-getopt:1.0.13`（无 `<licenses>` 块） | https://repo1.maven.org/maven2/gnu/getopt/java-getopt/1.0.13/java-getopt-1.0.13.pom |
| `gatk-bwamem-jni` LICENSE（BSD-3） | https://raw.githubusercontent.com/broadinstitute/gatk-bwamem-jni/master/LICENSE |
| `gatk-bwamem-jni` `src/main/c/Makefile`（BWA 静态编译） | https://raw.githubusercontent.com/broadinstitute/gatk-bwamem-jni/master/src/main/c/Makefile |
| `gatk-bwamem-jni` build.gradle | https://raw.githubusercontent.com/broadinstitute/gatk-bwamem-jni/master/build.gradle |
| **BWA @ 被 pin 的 commit：唯一许可文件 = Apache-2.0** | https://raw.githubusercontent.com/lh3/bwa/cb950614ce7217788780b9a8d445c64cd4d8f62e/LICENSE.txt |
| **BWA @ 被 pin 的 commit：README** | https://raw.githubusercontent.com/lh3/bwa/cb950614ce7217788780b9a8d445c64cd4d8f62e/README.md |
| BWA @ 被 pin 的 commit：Makefile（LOBJS） | https://raw.githubusercontent.com/lh3/bwa/cb950614ce7217788780b9a8d445c64cd4d8f62e/Makefile |
| BWA master：COPYING = GPLv3 | https://raw.githubusercontent.com/lh3/bwa/master/COPYING |
| BWA master：README（"released under GPLv3"） | https://raw.githubusercontent.com/lh3/bwa/master/README.md |
| **htsjdk 5.0.0 sources jar（22 个 LGPL-2.1 文件）** | https://repo1.maven.org/maven2/com/github/samtools/htsjdk/5.0.0/htsjdk-5.0.0-sources.jar |
| **JGraphT 1.1.0 sources jar（双许可择一措辞）** | https://repo1.maven.org/maven2/org/jgrapht/jgrapht-core/1.1.0/jgrapht-core-1.1.0-sources.jar |
| JGraphT 1.1.0 POM | https://repo1.maven.org/maven2/org/jgrapht/jgrapht-core/1.1.0/jgrapht-core-1.1.0.pom |
| LGPL-2.1 全文（§6 静态链接义务） | https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt |
| jpmml-model 1.4.8 LICENSE（BSD-3，证伪 AGPL 猜测） | https://raw.githubusercontent.com/jpmml/jpmml-model/1.4.8/LICENSE.txt |
| org.json LICENSE（Public Domain，证伪 JSON License 猜测） | https://raw.githubusercontent.com/stleary/JSON-java/20231013/LICENSE |
| bwa-mem2 LICENSE（MIT）；NEWS.md 记录 2020 年由 GPL 改为 MIT | https://raw.githubusercontent.com/bwa-mem2/bwa-mem2/master/LICENSE |
| minimap2 LICENSE（MIT） | https://raw.githubusercontent.com/lh3/minimap2/master/LICENSE.txt |
| FreeBayes LICENSE（MIT） | https://raw.githubusercontent.com/freebayes/freebayes/master/LICENSE |
| DeepVariant LICENSE（BSD-3） | https://raw.githubusercontent.com/google/deepvariant/master/LICENSE |
| bcftools LICENSE（MIT/Expat 或 GPL，含 GSL 陷阱） | https://raw.githubusercontent.com/samtools/bcftools/develop/LICENSE |
| htslib LICENSE（MIT/Expat） | https://raw.githubusercontent.com/samtools/htslib/develop/LICENSE |
| VarScan 非商用声明（无 LICENSE 文件） | https://raw.githubusercontent.com/dkoboldt/varscan/master/VarScan.v2.4.6.description.txt |

## 附录 B：给决策者的五句话

1. **运行时无忧**：单样本 HaplotypeCaller + 预置 BAM 的路径上，GenomicsDB（含 libuuid）与 BWA 都不会被加载 —— 已用 763 类可达闭包证明。
2. **疑点 A 与 B 的原假设都被推翻了（两个方向）**：
   - A：libcsv 根本没被链入；libuuid 确实被**静态链接**，**但它不是 LGPL 而是 BSD-3-Clause**（被链接的 `gen_uuid.c` 源文件头就是 BSD-3）—— GenomicsDB 自己的 LICENSE 把它写成了 LGPLv2，属**高估**。
   - B：BWA 确实被静态编译进 `libbwa.Linux.so`，但被 pin 的那个 commit（`cb950614`）**整棵树里唯一的许可文件是 Apache-2.0**，编译进 `libbwa.a` 的目标文件无一是 GPL —— **"GPLv3 BWA"不成立**；真问题是构件只声明 BSD-3 却内含 Apache-2.0/MIT 代码而**完全没有署名**。
   - **代价最低的动作仍是** `zip -d /gatk/gatk.jar 'libbwa.*' 'libtiledbgenomicsdb.*' 'libfml.*'` + 一份 `MODIFICATIONS.md`（我们本来也不用它们）。
3. **真正的硬骨头在 jar 里、且真的在执行**：`htsjdk` 的 `tribble`（**LGPL-2.1，22 个文件，其 POM 谎称 MIT** —— 属**低估**）和 `jgrapht`（LGPL-2.1 **或** EPL-1.0，**可显式择 EPL-1.0 规避**）。这两个在 `HaplotypeCaller` 路径上会执行且无法剥离。
4. **最严重的一层不在 GATK 里**：官方镜像的 conda 环境含 **Intel oneMKL（`license_family: Proprietary`，二进制-only、源码不可得）**、**GSL（GPL-3）** 与 **R 技术栈（GPL-2/3）**。这一层只能靠**自己写 Dockerfile**（去 R、BLAS 换 `openblas`/`blis`）解决。
5. **第一个要澄清的不是技术问题，而是政策语义**：`bash`/`coreutils` 等 GPL-3 二进制存在于**每个** Ubuntu 镜像里，所以"镜像内不得含 GPL"按字面**不可能满足**，只能理解为"不得含与我们应用构成组合作品、或我们需要依赖其核心功能的 GPL 组件"。**确认这一点之后**：若 LGPL 可接受 → 用 GATK，把 LGPL/EPL 通告做干净；若"零 copyleft" → 这条流水线必须换 caller（**DeepVariant / BSD-3** 或 **FreeBayes / MIT**）。
