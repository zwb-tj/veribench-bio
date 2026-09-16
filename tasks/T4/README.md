# T4 —— 本体与功能注释任务（GO 确定性图查询）

> **一句话**：给定 GO 本体原文，确定性地回答一组关于术语与层级的问题。
> 真值全部由 OBO 原文**机械重算** —— 不是谁"判断"出来的。

设计依据见 [`DESIGN.md`](DESIGN.md)；许可与来源见
[`../../research/T4_SOURCES.md`](../../research/T4_SOURCES.md)。

---

## ⚠️ 与 T3 的**关键差异**：本题数据**必须署名**

| | T3（PDB） | **T4（GO）** |
|---|---|---|
| 许可 | CC0-1.0 | **CC BY 4.0** |
| 署名 | 不需要 | **必须** |

署名已履行：`NOTICE` 的 `[A]` 块含可复制的署名声明 + release 日期 + 许可链接，
并由 `scripts/verify_notice.py` 的 `ATTRIBUTION_REQUIRED` 守着
（删掉署名句检查即失败，已做负向测试）。

**删掉那个块就是许可违规。**

---

## 一、这道题考什么

30 个 GO 术语，每题要求报告四个量：

| 量 | 定义 |
|---|---|
| `name` | 该 term 的 `name` 字段 |
| `namespace` | `molecular_function` / `biological_process` / `cellular_component` |
| `direct_parent_count` | `is_a:` 行的条数（**只数 `is_a`**，不含 `relationship`） |
| `depth_to_root` | 沿 `is_a` 向上到**任一**根的最短距离（根 = 3 个无 `is_a` 的节点） |

这些量**只依赖 OBO 原文的字段与图结构** —— 没有阈值、没有统计假设、
没有需要生物学家裁决的语义判断。所以它们是**确定的**。

---

## 二、⚠️ 诚实说明：这题**不能**用来测"能力"

**必读**：

1. **GO 是公开常识性资源。** 术语 ID 与名称很可能已在 LLM 训练集中。
   我们**无法核实**训练集内容，所以不猜测、也不声称。
2. **真值可由原文重算** —— "知道答案"与"会算"在这里几乎等价。

**所以 T4 主张的是**：

> ✅ 它测**能否按规范确定性地做图查询**，以及**过程是否可复现**。
> ❌ 它**不**测"模型懂生物学"。

这一条必须同步写进 `docs/DATACARD.md`。

---

## 三、怎么跑

### 3.1 取数（只需一次；结果不进 git）

```bash
cd tasks/T4/data
python3 fetch_go.py --outdir .       # 下载 32 MB 本体 → items.jsonl + truth.jsonl
python3 fetch_go.py --outdir . --check   # 只核对，不下载
```

⚠️ **`current.geneontology.org` 是滚动别名** —— 将来取到的版本会不同。
所以每题都记录 `obo_data_version` 与 `obo_sha256`：
"我们用的是哪一版"可验证（实测 `releases/2026-07-26`）。

### 3.2 在容器里跑

```bash
docker build -t veribench-bio/t4:dev tasks/T4

# 真值**只读挂载**（镜像里不含答案）
docker run --rm \
  -v "$PWD/tasks/T4/data/truth.jsonl:/data/truth.jsonl:ro" \
  -v "$PWD/out:/out" \
  veribench-bio/t4:dev
# → /out/result.json
```

### 3.3 自检

```bash
python3 tasks/T4/data/obo_parse.py --self-test
python3 tasks/T4/grade.py --self-test
```

---

## 四、实测结果

| 项 | 结果 |
|---|---|
| 题池 | **30 条**（三个 namespace 各 10 条），本体 32 MB |
| 本体规模 | 48,340 个 `[Term]`，其中 **38,092 非 obsolete**；3 个根 |
| 解析耗时 | **2.1 秒**（48,340 个 term） |
| oracle 得分（容器内） | **1.0**，量命中 **120/120**，30/30 题 |
| 端到端耗时 | **1.1 秒**（预算 30 分钟） |
| 镜像 | 157 MB，**不含 `truth.jsonl`**（构建期用文件系统确认） |
| 全部真值可由原文重算 | ✅（构建期门禁 C 逐条验证） |

---

## 五、实现时踩到的两个坑（都留了检查）

### 坑 1：不过滤 `obsolete` 会多出 **10,248 个"假根"**

实测：不过滤时"无 `is_a`"的项有 **10,251 个**，过滤后**真实根只有 3 个**。

后果：`depth_to_root` 全部算错（BFS 会把 obsolete 项当成到达点）。
而这个错误**不会自己喊出来** —— 答案看起来仍是正常整数。

→ 自检先抓到（合成夹具里 obsolete 项也被算成根），
然后在真实文件上量出影响。`find_roots()` 与 `depth_to_root()` 都已排除 obsolete。

### 坑 2：**"构建期门禁"根本不会执行**（这个更严重，T3 也中招）

Docker **不构建未被引用的中间阶段**。一个 `FROM ... AS gate` 后面写再多 `RUN`，
只要最终阶段**没有引用它**，Docker 就整个跳过 —— 所有检查静默不执行，
而**构建照样成功**。

**证据**：往 `truth.jsonl` 注入一个错误值后，构建仍然 `exit 0`。
加上 `COPY --from=gate` 之后，同一个注入立刻让构建 `exit 1`。

→ 修复：gate 阶段末尾写一个标记文件，最终阶段 `COPY --from=gate` 它。
现在 gate 的 8 个步骤真的会执行，且注入错误会让构建失败。
→ 新增 `scripts/check_docker_gates.py` 守着这一类（**T3 也因此被发现并修复**）。

> 这条值得单独记住：**"我写了检查"和"检查会执行"是两件事**。
> 而前者很容易被当成后者 —— 文档里写着"构建期执行门禁"，构建也成功，
> 唯一的问题是那些门禁**从未跑过**。

---

## 六、未完成 / 未验证（照实说）

- ⚠️ **无第三方机器复现**（本机端到端跑过）
- ⚠️ **arm64 未验证**（本机 QEMU 模拟不可用）
- ⚠️ **污染风险未定量**（见 §2，是设计限制而非待办）
- ⚠️ **没有真实模型作答过 T4** —— 目前只有 oracle（合成基线）
- ⚠️ **题池未做人工审阅**（图查询是机械重算，但题目措辞是否清晰未评估）
- ⚠️ **版本锁定依赖 sha256 记录**，而非一个稳定的按版本下载 URL（见 SOURCES §5）
