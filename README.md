# VeriBench-Bio

[![checks](https://github.com/zwb-tj/veribench-bio/actions/workflows/checks.yml/badge.svg)](https://github.com/zwb-tj/veribench-bio/actions/workflows/checks.yml)

> 一个**许可干净、可公开分发、30 分钟内 CPU-only 跑完**的生命科学 / 生信实操评测集，
> 外加一套 **"LLM 裁判到底可不可信"** 的元评测（双标注 + Cohen's κ + 公开失效案例）。

**设计文档见 [`SPEC.md`](SPEC.md)。** 想知道**哪些能信、哪些不能**，直接看
[`docs/DATACARD.md`](docs/DATACARD.md) 的 §4（已知限制）与 §5（已验证事实）——
那两节就是本项目的全部立场。

> **那个徽章不是装饰。** 它跑的就是你自己 clone 下来能跑的那套检查
> （CI 里**不装任何第三方包、不用 Docker**，所以它检验的正是"第三方能不能复现"）。
> 想自己看一遍：`python run_all_checks.py`（零第三方依赖）。

---

## 现在到底做完了什么（**照实说**）

**两个 HF 数据集仓库当前都是 Private，尚未发布。**

| 支柱 | 状态 | 证据 |
|---|---|---|
| **T1** 变异检出 | ✅ **已完成并实测** | HF `zwb-tj/biobench-lite-t1-hg002-chr20`（100.4 MB / 7 文件）；重新下载后**逐字节 sha256 比对通过**；真实数据跑 **39–55 秒**（五次独立端到端运行，预算 1800 秒）；得分 **0.84655**（五跑完全一致，变异数均 12,254）；amd64 实跑通过 |
| **T2** 变异解读 | ⚠️ **本地完成并实测，但尚未发布** | **4,726 条**（3,545 真实 + 1,181 金丝雀 = 25%）；泄漏检查 **0 泄漏**（覆盖 40,170 个字符串字段）；容器端到端 oracle **1.0**；准备公开 3,789 条，**轮换池 937 条永不发布**。**HF 仓库已建但存储 0 B —— 尚未上传**（`hf repo list` 实测） |
| **rubric** 审稿式开放题（第三支柱） | ⚠️ **结构完成，验证未完成** | **24 题 / 101 条标准**（`rubric/items/items_v1.2.jsonl`）；0 泄漏、155 个数字 0 个查不到、27 篇人类数据裁决 27/27 一致；**但人类天花板尚未取得** |
| **台账** | ✅ 30 条 | `ledger/items.jsonl`，审计器 R0–R12 判 **0 致命** |
| **T3–T8** | ❌ **未动工** | SPEC §4.2 有设计，无实现 |
| **榜单** | ❌ **未做** | v1 四件套之一 |

**一句话总结**：两个任务做得比较扎实，第三支柱的方法跑通了但**缺真人标注**，
其余任务和榜单还没开始。

## 为什么存在这个项目

不是第 27 个生物选择题集。竞品尽调（`../research/DECISION.md`）显示：

- 通用生物 MCQ、文献抽取、图表 QA、协议 QA、通路推理、单细胞、变异解读、虚拟细胞**全部已被占**（`BixBench` 143★、`LAB-Bench` 129★、`LABBench2`、`SciKnowEval`…）
- `BixBench` 需 **HF 授权 + Docker + 24–48 小时** → **"30 分钟 CPU-only"是硬缺口**
- `bioagent-bench` 作者**自承真值不敢保证** → 真值权威性是可攻击点
- `jang1563/BioEval` 组件齐备却 **0★ 且作者明确拒绝发榜** → **"公开自助榜"是真空**
- `LAB-Bench` 是 **CC-BY-SA（传染）**、`BioEval` 数据是 **CC-BY-NC（禁商用）**、bioRxiv 大量 **ND（禁改写）**
  → **许可洁净度本身就是护城河，不是杂务**

一句话：**大厂都在卷能力覆盖（更多题、更大语料、更高分），几乎没人在卷可信性。**

## 三条不可协商的原则

1. **每一道题都可溯源。** 没有台账条目的题目不得进集。宁少勿假。
   （由 `scripts/verify_datacard.py` 强制：台账为空直接判失败）
2. **真值必须来自权威公开资源，绝不自算。** 自算真值 = 自证自评，是 bioagent-bench 的死因。
   （T7/T8 若加入，只能进独立的"可复现性"分区，**绝不与准确率榜混排**）
3. **许可先于内容。** 白名单只有 `CC0-1.0` / `CC-BY-4.0` / `CC-BY-3.0` / 公有领域；
   `-NC-`（禁商用）、`-ND-`（禁衍生）、`-SA-`（传染）**一律不可用**。
   ⚠️ `-ND-` 的关键：**把论文改写成题目本身就是衍生作品**，所以 ND 内容在这个项目里等于不可用。
   ⚠️ **arXiv 默认许可不是开放许可**，仅元数据是 CC0 —— 不许当安全区。

## 快速开始

```bash
# 项目级检查（现在 24 步）：台账 + 许可门禁 + 卡片一致性 + LICENSE 正文比对
#   + schema 校验 + 环境依赖 + 全仓 JSON 解析 + 每个任务的镜像 pin 核对 …
python run_all_checks.py

# 第三支柱（rubric）内部检查：10 个环节
python rubric/run_all_checks.py

# 清室检验：只复制"会被发布的那部分"到临时目录，在那里重跑（慢，但抓真问题）
python run_all_checks.py --clean-room

# 许可红线审计（独立可用）
python scripts/audit_licenses.py ledger/items.jsonl
python scripts/audit_licenses.py --self-test      # 16 个用例，验证审计器本身能正确打红

# 镜像 pin 是否还由当前源码算得出来（T1/T2 一起验，不允许只做一半）
python scripts/record_image_digest.py --check-all
python scripts/record_image_digest.py --self-test # 证明"源码一变它就失败"

# 发布前：`.gitignore` 是否与唯一真源一致 + 密钥/本机路径扫描
python scripts/generate_gitignore.py --check      # 过期即失败（安全属性）
python scripts/scan_secrets.py                    # 凭据一旦推上去无法收回

# T1 实跑（需先取数据 + 构建镜像）
bash tasks/T1/data/prepare_data.sh
docker build -t veribench-bio/t1:dev tasks/T1
bash tasks/T1/run.sh
```

**每个检查器都该有一个能证明它会失败的用例。** 现有
`audit_licenses` / `verify_readme` / `verify_t1_region` / `check_t1_scripts_agree` /
`verify_notice` / `verify_json_files` / `record_image_digest` 都带 `--self-test`，
跑 `python scripts/smoke_test_scripts.py` 能看到哪些有、哪些还没有。

**环境要求**：Python ≥ 3.10；**Python 第三方依赖为零**（全部只用标准库，
见 `scripts/check_env_deps.py`；`jsonschema` 装了则多做一步 schema 校验，
没装会**明说本次未校验**而不是静默跳过）。Docker 只在 T1/T2 的**工具链**里需要。

## 目录结构（**与真实文件一致**，由 `scripts/verify_readme.py` 强制）

```
bio-eval/
├── SPEC.md                    # 设计文档（范围、题目、契约、风险、纠错记录）
├── README.md                  # 本文件
├── LICENSE / NOTICE           # 代码 Apache-2.0；第三方组件逐项（分"已核验/未逐项核验"）
├── run_all_checks.py          # 项目级检查（7 环节）
├── docs/
│   ├── DATACARD.md            # 数据卡：许可、台账机制、已知限制、已验证事实
│   ├── SAFETY.md              # 生物安全红线与执行现状
│   ├── PLAIN_LANGUAGE.md      # 给湿实验背景的人的通俗说明
│   ├── HF_UPLOAD.md           # T1 上传流程
│   ├── HF_UPLOAD_T2.md        # T2 上传流程（⚠️ 发布集不对称，务必先读第 0 步）
│   └── GITHUB_PUBLISH.md      # 推到 GitHub 的流程（⚠️ 历史不可撤销，先读第 0 步）
├── schema/
│   └── ledger.schema.json     # 台账契约（17 必填字段）
├── ledger/items.jsonl         # 题级 provenance ledger（唯一真源）
├── scripts/                   # 审计器 / 台账构建 / 各类校验
├── tasks/
│   ├── T1/                    # 变异检出：Dockerfile / run.sh / grade.py / licenses / baseline
│   └── T2/                    # 变异解读：同上 + 三层防污染
└── rubric/                    # 第三支柱
    ├── README.md
    ├── run_all_checks.py      # 10 环节
    ├── items/items_v1.2.jsonl # 24 题 / 101 条标准（**正式版**）
    ├── schema/ judge/ ledger/ review/ annotation/ docs/ scripts/ fixtures/
    └── ...
```

⚠️ `rubric/items/items_v1.1.jsonl` **已废弃，不要使用**（理由见 `SPEC.md` §13.3l）。

## v1 完成的定义（四件套）—— **现在的真实进度是 2/4**

- [x] **SAFETY + DATACARD + license 文档** —— 已完成（`docs/SAFETY.md`、`docs/DATACARD.md`、
      `LICENSE` 正文与 apache.org 官方源逐行比对通过、`NOTICE` 分"已核验/未逐项核验"两块）
- [x] **可复现 manifest** —— T1 的 `_runs/result.json` 记录了
      **每个文件的 sha256**（7/7 逐字节可复算）、**镜像 digest**
      （`sha256:c33862bb…`）、**manifest 自身的哈希**（= sha256(manifest.json)，可复算）、
      工具链与精确版本、以及运行时长的分解。
      ⚠️ 此前这里写着"**镜像 digest 尚未 pin**"—— **那是错的**，digest 一直记在
      `result.json` 里。由 `scripts/verify_t1_claims.py` 检出并更正
      （这是它第一次运行时抓到的唯一一条不符）。
- [ ] **κ 报告** —— judge prompt 是公开的（`rubric/judge/judge_prompt_v1.md`）、
      失效案例有（合成夹具上的 33 例）；**但真实人类双标注尚未取得，
      所以没有可发布的 κ**。现有数字只算"流程校准"，**不得当结果引用**
- [ ] **真实榜单** —— **未完成**。提交校验器已就绪
      （`leaderboard/verify_submission.py`，**含负向测试**：会拒绝"分数对不上 / 数据哈希不符 /
      缺镜像 digest / 超预算"四类提交），但 `leaderboard/results.jsonl` **是 0 字节** ——
      数据集仓库还是 Private，**没有任何人能提交**。
      **就绪 ≠ 完成，所以这一项不勾。**

## 生物安全红线（硬性）

**不做**：增强传播力 / 致病性 / 免疫逃逸、毒素合成、select agents、基因驱动、生殖系编辑。
**只做**：拒答正确性、风险识别、以及"模型是否会在被拒绝的边界上含糊其辞"。
高危题抽象化去参数；敏感子集 gated release + canary string；
需 ≥1 名生物安全背景审阅者签字（**目前尚无人签字**，见 `docs/SAFETY.md` §5）。

## 状态

**v0.2 — 两个任务已完成并实测，第三支柱方法已验证但缺真人标注，未发布。**

发布前必须完成的事项见 `docs/DATACARD.md` §7。**其中两项必须由人完成**：
法务确认许可边界、以及**真实人类双标注**（第三支柱的硬阻塞）。

## 许可

- **代码**：Apache-2.0（`LICENSE`）
- **数据**：**不设统一数据许可** —— 逐条按来源标注，见 `ledger/items.jsonl` 与 `docs/DATACARD.md` §1
- **第三方组件**：见 `NOTICE`（分 **[A] 已核验上游 LICENSE 原文** 与
  **[B] 仅有包元数据**两块；划分由 `scripts/verify_notice.py` 强制，
  [A] 的每条都必须给出上游出处，否则检查失败）
- ⚠️ **`bcftools` 的 GSL 陷阱**：Debian 元数据声称该包因链接 GSL 而受 GPL 管辖，
  经四条实证排除（决定性证据：`bcftools polysomy` 不存在 → 未启用 `USE_GPL`）。
  构建期由 `tasks/T1/scripts/check_no_gsl.sh` 四道检查强制执行，含负向测试。
  详见 `docs/DATACARD.md` §5.2。

## 这个仓库里刻意保留的东西

`SPEC.md` §3.1（静默失败清单）、§13.3（**连续三轮结论被自己的实测推翻**的记录）、
`docs/DATACARD.md` §5.1 / §5.2（pin 了个对不上的镜像；"零 copyleft"差点是假话）。

**一份只展示结论、不展示纠错过程的基准，无法让第三方判断它有多可信。**
所以那些"我错了"的记录不删。

⚠️ 本轮的教训尤其值得留在明面上：发现的偏差**方向全是"往大了说"**
（覆盖区间夸大 5 倍、pin 的镜像比当前的大、耗时报得比实测慢）。
对一个卖点就是"可验证"的项目，**高估**的伤害远大于低估 —— 因为它恰好伪装成好消息。
