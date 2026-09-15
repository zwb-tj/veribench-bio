# MODIFICATIONS —— 本镜像对上游组件所做的修改

> 本文件随镜像分发（`/licenses/`）。目的是让拿到镜像的人能**独立核实**我们到底改了什么、为什么改、
> 以及改动的法律依据。**未在此列出的上游文件均未改动。**

---

## 1. 修改 `/opt/rtg-tools/rtg`（RTG Tools 3.12.1 的启动脚本）

**上游原文**（`rtg` 脚本开头即有此检查）：

```bash
elif [[ "$(uname -m)" != "x86_64" ]]; then
    # If you comment this check out you are on your own :-)
    echo "Sorry, you must be running a 64bit operating system."
    exit 1
fi
```

**我们的改动**（`scripts/patch_rtg_launcher.sh`）：

```diff
-elif [[ "$(uname -m)" != "x86_64" ]]; then
+elif [[ "$(uname -m)" == "x86_64_disabled" ]]; then
```

即把该分支条件改为**恒假**。包装脚本的其余逻辑（内存设置、classpath、配置加载、talkback）**原样保留**。

**为什么**：该检查使 `rtg` 在**任何非 x86_64 架构**上立即 `exit 1`（实测 arm64 上 0.1 秒内失败），
导致判分器在 Apple Silicon / arm64 服务器上完全不可用。

**为什么可以去掉**：
1. `RTG.jar` 是**纯 Java**，与 CPU 架构无关；
2. 已确认 `/opt/rtg-tools` 内**不存在任何 ELF 原生二进制**（见 `scripts/check_arch_neutral.sh`）；
3. 上游随包捆的 amd64 专用 JRE（`jre/lib/amd64/*.so`）已由我们删除，改走系统 Java；
4. 该检查写于上游还随包分发 x86_64 JRE 的年代，属保守式"安全带"。

**法律依据**：RTG Tools 以 **BSD 2-Clause** 分发，允许修改与再分发（须保留版权声明）。
我们未删除任何版权声明，并在此声明修改内容。

**验证方式**（不是"看着对"，而是跑出来的）：
- `scripts/patch_rtg_launcher.sh --self-test` —— 自测补丁逻辑，**并检查行为**（补丁后脚本必须能走到主逻辑）
- arm64 镜像内运行判分器自检：完美解法 `1.0`、部分解法 `0.25`，**与 amd64 完全一致**

> ⚠️ **一个值得记下的教训**：本补丁的第一版把条件改成了 `!= ""`，而 `uname -m` 永远不为空
> → 条件恒真 → **在所有架构上都失败**。文本检查（"坏字符串消失了"）完全看不出来，
> 是上面那条**行为自测**抓到的。**验证行为，不要只验证文本。**

---

## 2. 删除 `/opt/rtg-tools/jre/`（上游捆包目录）

**改动**：删除该目录（约 113 MB）。

**为什么**：上游的 `rtg-tools-3.12.1-linux-x64.zip` 内捆了一个 **amd64 专用 JRE**
（`jre/lib/amd64/*.so`），而 `rtg` 启动脚本会**优先**使用它 → 在 arm64 上是 `Exec format error`。
我们改用 Debian `default-jre-headless`（多架构），并在 `/etc/rtg.cfg` 写入 `RTG_JAVA=java`。

**性质**：**删除文件**，未修改任何代码。副作用是正向的（镜像 469 MB → 356 MB）。

---

## 3. 本镜像新增的、非上游内容

以下均为**我们自己的构建期检查**，不是对上游的修改：

| 路径 | 作用 |
|---|---|
| `/opt/veribench-scripts/check_arch_neutral.sh` | 架构中立性门禁（构建期执行，失败即中断） |
| `/opt/veribench-scripts/patch_rtg_launcher.sh` | 上面第 1 项的补丁与自测 |
| `/work/run.sh` | T1 参考流水线（freebayes 检出 + 归一化） |
| `/work/grade.py` | T1 判分器（vcfeval 评分 + JSON 契约） |
| `/work/data/prepare_data.sh` | 数据集生成脚本（远程区域取 + 降采样） |

---

## 未修改的组件（明确声明）

- `RTG.jar` **未修改**
- `samtools` / `bcftools` / `tabix` / `freebayes` **未修改**（Debian 包原样）
- 未对任何组件做静态/动态链接

---

## 已知限制

- 本文件是**事实性修改声明**，不构成法律意见。
- arm64 的功能验证是在 **QEMU 模拟**下完成的；**原生 arm64 硬件上的验证仍未进行**。
