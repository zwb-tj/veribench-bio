# T4 数据来源与许可核实

> **方法**：只采信一手来源（Gene Ontology 官方政策页、官方下载端点、以及
> **数据文件自身的许可元数据**）。本仓库既有文档的结论**不作为证据**。
> 每条结论附 URL 与实际取回的内容。
>
> ⚠️ **与 T3 的关键差异**：PDB 是 CC0（无需署名），**GO 是 CC BY 4.0（必须署名）**。
> 这个差别很容易被"统一处理"抹掉 —— 而抹掉就是**许可违规**。

核实时间：2026-09（本机）。

---

## 一、许可：**CC BY 4.0**（**署名是条件，不是可选项**）

**来源 1**：<https://geneontology.org/docs/go-citation-policy/>
（HTTP 200，24,216 B）

**原文摘录**：

> 「According to the terms of GO's **CC BY 4.0** license, those using our data
> publicly or redistributing it must provide: "identification of the creator(s)
> of the Licensed Material and any others designated to receive attribution,
> in any reasonable manner requested by the Licensor…"」

**来源 2（更强）**：**许可写在数据文件自身里** ——

```
$ grep terms:license go-basic.obo
property_value: terms:license http://creativecommons.org/licenses/by/4.0/
```

这是最强的一手证据：不依赖网页是否还在，**文件本身**声明了许可。

| 问题 | 结论 |
|---|---|
| 能否再分发？ | ✅ 可以 |
| 能否进 git / Docker 镜像？ | ✅ 可以 |
| **是否必须署名？** | **⚠️ 必须**（CC BY 4.0 §3(a)） |
| 是否可商用？ | ✅ 可以 |

**→ 本项目如何履行署名义务**：登记在 `NOTICE` 的 `[A]` 块，
包含可复制的署名声明、release 日期、许可链接。
**并且有检查守着**：`scripts/verify_notice.py` 的 `ATTRIBUTION_REQUIRED`
会验证署名句存在；删掉它检查即失败（已做负向测试）。

> ⚠️ **这个检查第一版是坏的**：判据用 `CC BY 4\.0 license` 作正则，
> 而 NOTICE 里该串命中 **2 处** —— 一处是**引用的上游政策原文**，
> 一处才是我们自己的署名句。于是删掉我们的署名句后**检查仍然通过**。
> 现在锚定到署名句的主语（`Gene Ontology Consortium data`），
> 只可能出现在我们自己的声明里。

---

## 二、可获取性：无需凭据，但**版本是滚动的**

**入口**：`http://current.geneontology.org/ontology/go-basic.obo`

实测（2026-09）：HTTP 200，**32,227,785 B**，`data-version: releases/2026-07-26`。

- **无需凭据**：直接 GET
- ⚠️ **`current` 是滚动别名** —— 今天取到 2026-07-26，将来会变
- **缓解措施**：`items.jsonl` 每条都记录 `data-version` 与文件 `sha256`
  （实测 `b08d45b268b8cbb1…`），所以"我们用的是哪一版"可验证

---

## 三、本体结构（实测）

| 项 | 实测值 |
|---|---|
| `[Term]` 块数 | 48,340 |
| **非 obsolete** | **38,092** ← 真正的题池 |
| 文件体积 | 32,227,785 B |
| 必存字段 | `id` / `name` / `namespace` / `def` —— **3000/3000** |
| `is_a` | 2,505/3000（不是所有 term 都有父节点） |
| `relationship` | 1,052/3000 |
| **`is_obsolete: true`** | **494/3000** |
| 根节点 | 3 个：`GO:0003674` / `GO:0005575` / `GO:0008150` |

### ⚠️ 一个必须写清的陷阱：不过滤 obsolete 会多出 10,248 个"假根"

实测：**不加 obsolete 过滤**时，"无 `is_a`"的项有 **10,251 个**；
过滤后**真实根只有 3 个**。

后果：`depth_to_root` 全部算错（BFS 会把 obsolete 项当成到达点）。
而这个错误**不会自己喊出来** —— 答案看起来仍像正常整数。

→ 已写进 `tasks/T4/DESIGN.md` §2.3，并由 `obo_parse.py` 的自检钉住。

---

## 四、污染风险评估

| 维度 | 评估 |
|---|---|
| GO ID 与名称是否可能被记住？ | **很可能** —— GO 是公开常识性资源 |
| 数值（depth 等）是否可能被记住？ | **不确定**，无法核实训练集 |
| 能否防污染？ | ✅ 部分：程序化固定种子抽样 + 从原文重算 |

**必须写进 `DATACARD.md` 的限制**：
> T4 **不得**用来声称"模型懂生物学"。它测的是**能否按规范确定性地做图查询**
> 与**过程是否可复现**。GO 术语与层级是公开常识，可能已在训练集中。

---

## 五、无法核实 / 需人工确认（照实说）

1. ⚠️ **`current` 别名背后的具体发布**只能通过文件内的 `data-version` 得知；
   官方没有一个"按版本固定下载"的稳定 URL 被本轮核实。
   → 已用 sha256 记录缓解；若要严格锁版本，需人工确认
   `http://release.geneontology.org/<date>/ontology/go-basic.obo` 是否长期可用。
2. ⚠️ **GAF 注释文件的许可未核实** —— 但 T4 **不使用**注释文件
   （那是别人的策展结论，见 DESIGN §6），所以不影响本题。
3. ⚠️ GO 政策页提到"optionally the Zenodo DOI"用于引用。
   本轮**未**在 `NOTICE` 里写明 DOI（政策页把它列为可选）。
   若将来要求更完整的引用，可补。

---

## 六、结论（供实现者直接引用）

| 问题 | 答案 |
|---|---|
| 许可 | **CC BY 4.0** —— 可再分发，**必须署名** |
| 一口来源 | <https://geneontology.org/docs/go-citation-policy/> + 文件内 `terms:license` |
| 下载入口 | `http://current.geneontology.org/ontology/go-basic.obo`（**滚动别名**） |
| 我们用的版本 | `releases/2026-07-26`，sha256 记录在 `items.jsonl` |
| 题池 | 非 obsolete 的 **38,092** 个 term 中固定种子抽 30 条 |
| **署名义务** | **已在 `NOTICE` `[A]` 块履行，并由 `verify_notice.py` 守着** |
| 必须写入 DATACARD 的限制 | 污染风险 → 不得声称测"能力"（见 §4） |
