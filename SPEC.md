# VeriBench-Bio · 设计方案 v0.1（SPEC）

> 状态：草案，待 `research/DATA_LICENSES.md` 核实后冻结 §4/§5 的数据源条款
> 上游依据：`../research/DECISION.md`（8 想法竞品尽调）、`../research/github-02-bio-eval.md`

---

## 1. 一句话定位

**一个许可干净、可公开分发、30 分钟内 CPU-only 跑完的生命科学/生信实操评测集，外加一套"LLM 裁判到底可不可信"的元评测。**

不是第 27 个生物选择题集。卖点是**可信性与可复现性**，不是题量。

## 2. 为什么要窄化到这个格子（竞品尽调结论）

| 事实 | 来源 | 对我们的含义 |
|---|---|---|
| 通用生物 MCQ / 文献抽取 / 图表 QA / 协议 QA / 通路推理 / 单细胞 / 变异解读 / 虚拟细胞**全部已被占** | `BixBench` 143★、`LAB-Bench` 129★（2400+ MCQ）、`LABBench2`、`SciKnowEval`、`BioMaze`、`CellBench`… | ❌ 不要再做选择题集 |
| `BixBench` 需 **HF 授权 + Docker + 24–48h** | BixBench README | ✅ **"30 分钟 CPU-only"是硬缺口**，且大厂不会修（对他们无发表价值） |
| `bioagent-bench` 作者自承**真值不敢保证** | 其 README | ✅ 真值权威性是可攻击点 |
| `jang1563/BioEval` 组件齐备、带 rubric 字段，**0★ 且作者明确拒绝发榜** | 仓库 | ✅ **"公开自助榜"是真空**；也警告我们：没人把可信榜单跑通 |
| `LAB-Bench`/`LABBench2` = **CC-BY-SA（传染）**；`BioEval` 数据 = **CC-BY-NC（禁商用）**；bioRxiv 大量 **ND（禁改写）** | 各仓库 license | ⚠️ **许可洁净度是护城河，不是杂务** |
| GitHub 已有描述与 bio-eval 逐字相同但 size=0 的空壳仓库 | 尽调 | ⚠️ idea 不稀缺，**执行与可信度才稀缺** |

## 3. 设计原则（不可协商）

1. **每一道题都可溯源。** 没有 `ledger` 条目的题目不得进集。宁少勿假。
2. **真值必须来自权威公开资源，绝不自算。** 自算真值等于自证自评，是 bioagent-bench 的死因。
   ⚠️ **推论（必须执行）**：若某题**不存在**权威真值，则该题只能以 `truth_type=reference-implementation` 标注，**进入独立的"可复现性"分区，绝不与准确率榜混排**——绝不自算真值冒充真值。（T7/T8 即按此处理，见 §4.2。）
3. **许可先于内容。** 第一天就切分"可公开分发"与"仅本地"两库，避免第 6 天发现数据集不能开源。
4. **可被第三方复现。** 一条命令跑完全集；`manifest` 带内容哈希；评测环境 pin 到镜像 digest。
5. **诚实标注不确定。** 无法核实的项写 `unknown`，不用"看起来像"的东西糊过去。
6. **能力与裁判分离。** 题目打分器 ≠ LLM judge 的研究对象；裁判可靠性单独评测（§6）。
7. **失败必须响亮，成功必须可计数。** 每一步取数/解析都要**打印"实际拿到了多少条"**；
   每一个上游错误都要**带上响应体**，不能只留状态码。理由见下 —— 本项目反复出现的失败
   不是"报错"，而是**静默错误**。

### 3.1 本项目实际踩过的"静默失败"清单（这是原则 7 的由来）

**它们全都是"看起来对、实际不对"，而且全都不报错：**

| 现象 | 真实情况 | 是谁发现的 |
|---|---|---|
| `hf upload` 打印 `[OK] Uploaded`，进度行却写 `0/0 uploaded` | 其实成功；但**反过来也可能**——只有重新下载逐字节比对才能确定 | 重新下载 + sha256 比对 |
| `[Review Status]` 不加引号 | GraphQL/E-utilities **静默返回 0**，不报错 | 与加引号的查询对照 |
| 用 `MDAT` 做时间切分 | NCBI 批量刷新导致 **2026[MDAT] 占 3★ 的 92%**，旧数据长得像新数据 | 与 `CLINSIG_LAST_CHANGED` 对照 |
| 逐年计数相加 | `CLINSIG_LAST_CHANGED` 是多值字段，naive 相加 **4,325**，UID 并集只有 **3,825** | 用 UID 并集复核 |
| ClinGen validity 解析出 **0 个基因** | 我的解析器找错了键（实际在 `rows`，基因键是 `symbol`），**不报错** | 强制在日志里打印解析数量 |
| gnomAD 返回 `HTTP 400` | 只记状态码 → 毫无信息；**读响应体才看到** `Cannot query field "af" on type ...` | 改为保留响应体 |
| 上游 `rtg` 脚本在 arm64 上 0.1 秒失败 | 文本检查全过，**行为是反的**（条件恒真） | 行为自测 |
| 上游 README 说 Apache-2.0 | 拆开 jar 发现里面捆的是别的东西 | 逐文件核验 |
| **27 篇来源的 `contains_human_data` 全被填成 `true`** | 含**蜜蜂**转录组、大鼠心梗模型、叙述性综述——**过半是错的**（15/27） | 子agent 复核 + 用标题/类型字段重判 |
| **校验脚本把上面这个错误冻结住** | `precheck_items.py` 强制"与 candidates 一致"，把未核实的事实当已验证的许可字段来锁；有人改成正确值时报**"禁止编造"**，纠正路径被堵死 | 出题子agent 报告"改 false 会被拦" |
| **我自己把"他人数据"当成"本文数据"** | PMC11900006 正文片段里的患者队列是引言**引用作者既往工作 [5]**，本文自身用的是商品化人视网膜内皮细胞。我据此误判为 `human_subjects_primary` | 出题子agent 指出；用完整标题复核 27 条才发现 |
| 源文 `.txt` **24/27 篇被截断在 20,000 字符** | 我是在不完整文本上做判定的。片段里出现患者数据 ≠ 本文采集了患者数据 | 统计文件长度时发现 |
| 文档写 T1 覆盖面 **chr20 10–20 Mb（约 10 Mb）** 【历史错误】 | 真值是 **10–12 Mb（约 2 Mb）**：**夸大了 5 倍**，而且错在 README / SPEC / DATACARD / PLAIN_LANGUAGE / T1 README / 台账生成器 / run.sh **共 7 处** | 用 manifest 的 `region` + 真值 BED 实测跨度复核 |
| `run.sh` 的两个默认值（BAM 文件名少 `.30x`、区间 10–20 Mb）**都是错的** | 因为**历史上每个 driver 都 `export REGION/BAM` 把默认值覆盖掉了** —— 默认值从来没被执行过，所以错不错没人知道。新人照 README 直接跑会立刻 `exit 2` | 重跑时**故意不覆盖**默认值 |
| `result.json` 里 pin 的镜像 digest | 是**剥离 rtg 捆绑 JRE 之前**的旧镜像（469 MB，含 `jre/lib/amd64`），与当前 `Dockerfile`（356 MB）**不是同一个镜像** | 起容器看里面还有没有 `jre/lib/amd64` |
| "镜像 digest 已记录" 这条检查报 ✅ | 它只问**有没有** digest，不问**对不对** —— 存在性检查给的是假保证 | 换成源码哈希绑定后立刻暴露 |
| 文档写运行时长 **55 秒**（单值） | 四次独立实跑是 **55 / 46 / 41 / 39** —— 单点数字是把**运行噪声当成了结果** | 重跑四次并对比 |
| Debian 的 bcftools 声明 **"GSL … as is done for this Debian package"**，且 `debian/rules` 确有 `--enable-gsl` | **照字面读，"零 copyleft"就是假话**。实测才知该构建并未启用 GSL（`polysomy` 未编入、无 `gsl_*` 符号、无动态依赖、无库文件）—— **发行版元数据与发行版自己的说明互相矛盾时，两者都不可信，只能实测** | 四条独立实证 + 读上游 `Makefile` 找到 `USE_GPL` 开关 |
| 许可门禁原来只有 `ldd \| grep libgsl` | **三个盲区**：静态链接看不见（`ldd` 只列动态依赖）、**39 个插件根本没扫**、完全不验行为。前两条都能让"零 copyleft"变成假话而门禁照过 | 对照上游 Makefile 重写门禁 + 四种注入的负向测试 |
| 我用 `strings \| grep -c gsl_` 得到 **0**，差点当成"没有 GSL" | `strings`/`nm`/`readelf` **在镜像里根本没装** —— 那个 0 是"命令失败"，不是"扫描结果干净"。**工具缺失会被误读成阴性结果** | 改用 Python 直接扫 ELF 字节 |
| "arm64 已验证通过"（T1 README 曾勾选） | 那次验证用的是**修 `run.sh` 之前**的镜像；本机 `t1:arm64` 至今带着两个错误默认值，且本轮 arm64 模拟已坏（`exec format error`），**无法在本机修正**。"通过"只对旧镜像成立，不能用来描述当前镜像 | 把 arm64 镜像 `docker create` + `docker cp` 出 `run.sh` 看默认值（不执行也能查） |
| **T2 连镜像 pin 都没有** | T1 修好"digest 绑定源码"之后，T2 漏着 —— 一个任务修了、另一个没修，是最典型的"给自己开特例"。而 T2 的 `items.jsonl` 也是构建输入（COPY 进镜像），更需要这个绑定 | 把 `record_image_digest.py` 从 `tasks/T1/scripts/` 提到仓库级并参数化 `--task T1\|T2`，一条检查管两个任务 |
| **T2 的两个 schema 烂了很久没人知道** | `tasks/T2/schema/t2-*.schema.json` **没有任何代码引用它们** → 各自带一个非法的 ASCII 双引号（中文串内），JSON 根本解析不了。**不被消费的 schema 不会报警，但它同时也不再是约束** | 新增 `verify_json_files.py`（全仓 JSON 解析检查）当场扫出；随后把它们接上真实数据（4,726 条 × 2 全部合 schema） |
| `not_published.json` 被我自己写坏 | 在 JSON 字符串里用了 **ASCII 双引号**（中文串内）—— **同一个错误在本项目的第 9 次**。发现纯属运气：下一个脚本刚好要读它。而它是 `clean_room_check` 与 `verify_doc_links` 的**共享真源**，坏了等于"什么算不该发布"同时失效 | 新增 `verify_json_files.py`，此后这类错误 100% 被抓（含精确行列号） |
| `tasks/T2/_runs` 从未登记为"不发布" | 与 T1 的 `_runs_repro3` **一模一样的漏法**。说明"枚举式登记"这个做法本身不可靠 | 把守卫从 `T1.glob("_runs*")` 扩成 `tasks/*/_runs*` —— 不允许只查一个任务 |
| **T2 的答案差点随仓库发出去** | 全量 `tasks/T2/data/{items,truth,audit}.jsonl` **含轮换池 937 条的题面与答案**，而 `split_public_rotation.py` 明写轮换池「**永不公开**」。这三个文件当时**不在** `not_published.json` 里 → 清室检验一直把它们当"会发布的文件"复制（已实测确认）。**这句对外声明此前从未被任何检查验证过** | 实测 id 交集（轮换池 937/937 全在全量 truth 里）+ 三个历史清室目录里都找到了 `truth.jsonl` |
| 文档说 T2「已上传 HF 并逐字节比对」 | `hf repo list` 实测 T2 仓库 **storage = 0 B** —— 仓库建了，**一个文件都没传**。而 `tasks/T2/README.md` 的未闭合项里一直挂着"尚未上传"，**两处自相矛盾**且无人发现 | 用 `hf repo list --format json` 读 storage 字段（**不需要下载内容**即可核对） |
| `tasks/T2/README.md` 写泄漏检查覆盖 **40,110** 个字段 | 实测是 **40,170**。根 README 与 DATACARD 都写对了，**只有这第三份文档是旧值** —— 因为检查器只扫那两份 | 把检查从"逐两份文档"扩成"**全文档数值矛盾扫描**"（同类问题在 T1 区间上也犯过：只扫 2 份文档） |
| T2 的"生命线"泄露检查器**自己漏检两整类** | `RefSeq/转录本 accession` 的 pattern 匹配不到任何标准写法（`NM_000277.3` 有下划线），**7/11 种形态永远漏检**；`变异 ID 形态` 只认四段式（数据里 0 处），完全漏掉三段式 `12-102852862-G-T`。**docstring 却明写会查这两类** | 变异测试：把已知阳性逐个注入 → 检查器返回 **0**（"干净"）。加了 `--self-test` 后**当场又抓出第二条** |
| 文档写「判分器自检 1.0/0.25」，并给出命令 `grade.py --self-test` | **该 flag 在 T1 的 `grade.py` 里根本不存在**（`argparse` 里没有）。真正的自检是 `tasks/T1/selftest/run_selftest.sh`（容器内 + 合成数据）。数字本身是真的（实跑确认 1.0/0.25），**但文档指的命令跑不起来** | 在容器里执行文档给的命令 → `error: the following arguments are required` |
| 两个判分器的自检**都没有被任何自动检查跑过** | T1（1.0/0.25）与 T2（11/11）都只写在文档里，靠人记得手跑 —— **等于"文档里的结论没有被守着"** | 清点"哪些 `--self-test` 没进套件"时发现；现已加 `run_all_checks.py` 第 6g 步每次都跑 |
| rubric 的 κ 数字来自**重跑会变的产物**（潜在风险） | `verify_rubric_claims.py` 只比对"文档 vs 产物"，**无法发现产物本身不可复现**；若两次重跑不同，文档数字就只是"某次运行的快照" | 实测：11 个产物重跑两次**逐字节相同**（确定性成立）。新增 `verify_rubric_determinism.py` 固定该性质，并做负向测试（注入随机字段 → 立刻报"不可复现"） |
| **"要上传什么"这一步此前完全没人守** | 现有检查验的是"仓库里的状态对不对"，**它不管人敲的那条 `hf upload` 命令**。而 T2 的发布集有个致命不对称：`tasks/T2/data/public/`（3,789 条）与 `tasks/T2/data/`（4,726 条，**含轮换池 937 条答案**）**只差一个路径段** —— 手滑一次就把"永不公开"变成假话，且**不可撤销** | 给"上传集"本身建了检查 `verify_upload_preflight.py`：逐文件列清单（行数/大小/sha256）、白名单、**逐文件禁止出现轮换池 id**、三文件 id 集合自洽、卡片逐字节一致。已做负向测试（指向 `tasks/T2/data/` → 拦下 6 处并点名 937 条） |
| 我在上传手册里写了段 `python -c @"..."@` 的内联比对 | 本项目在 Windows/PowerShell 上被内联脚本的引号坑过多次（本轮又一次）。**给别人照抄的命令，必须在我这里先跑通过** | 把比对逻辑写进脚本（`--compare-with`），并加负向测试（改一个字节 → 必须报不一致） |

→ **推论**：任何"检查通过"的结论，都必须说明**检查的是文本还是行为、样本量是多少**。
   "没报错"不等于"是对的"。

→ **关于上表最后四条的推论（比结论本身更重要）**：
  1. **裸布尔不可审计。** 一个只有 true/false 的字段没有留下任何可核对的痕迹，
     所以它错了不会有任何东西报警。**必须带上"依据"（本研究用 `human_data_basis` 枚举），
     并且依据要与布尔值自洽** —— 这就是审计器新增 R12 的原因。
  2. **"一致性校验"只能传递已经验证过的事实。** 把一个未核实的字段纳入强制一致，
     等于给它盖了个"已验证"的章：错误反而被固化，而且**纠正它会触发报错**。
     现在 precheck 把字段分成两类：**许可判定字段**（一个来源一份结论，强锁）与
     **事实判定字段**（核对**裁决文件**，而不是核对上一版数据）。
  3. **判定要看完整证据。** 截断文本 + 正则数词频，会稳定地把"引言引用的他人工作"
     算成"本文数据"。本轮的补救是用文件头部**完整的标题与 Subjects 类型**复核全部 27 条。
  4. 这三条都不是新工具能解决的，**只能靠"不同的人用不同的方法再看一遍"** ——
     本例中正是出题子agent 独立复核才发现的。

→ **关于上表最后五条的推论（2026-09 补，同样比结论本身重要）**：
  1. **默认值是"从没被执行过的代码"。** 所有 driver 都覆盖 `REGION`/`BAM`，
     于是 `run.sh` 的默认值错了两处也无人知晓。**修完必须用默认值再跑一遍** ——
     否则只是"改了一行字"，并没有证明它现在能跑。
  2. **只问"有没有"的检查给的是假保证。** 凡是 pin（版本 / 哈希 / 摘要）类断言，
     都必须绑定到**能复算的源码哈希**：`IMAGE_DIGEST.json` + `record_image_digest.py`
     就是这么来的。**"有记录"不等于"对得上"。**
  3. **单个测量值不是事实，是样本。** 耗时 / 内存这类量必须报**区间 + 重复次数**；
     报单点等于把噪声写成结论。
  4. **往大了夸的错最危险。** 本轮两个偏差（区间夸大 5 倍、pin 了个更大的旧镜像）
     方向都是**高估**。对一个卖点就是"可验证"的项目，高估的伤害远大于低估。
  5. **"检查覆盖了"要单独验证。** `verify_t1_claims.py` 一直存在也一直通过，
     但它只扫 2 份文档、判据是小数正则 —— **区间是个字符串，压根匹配不到**。
     文档数 ≠ 覆盖数。新增 `verify_t1_region.py` 时，负向测试专门验了这一点。
  6. **发行版元数据不是事实，它只是一份说法。** Debian 的包元数据说 bcftools
     因链接 GSL 而受 GPL 管辖，而**同一个包实测并未启用 GSL**。
     结论：**许可声明这类"第三方说法"，必须区分"谁说的"与"测出来的"** ——
     并把可测的部分做成门禁（`check_no_gsl.sh` 四道检查 + 负向测试），
     而不是抄进文档当承诺。
  7. **工具缺失会被误读成阴性结果。** 我用 `strings | grep -c gsl_` 得到 0 就差点
     下结论；其实 `strings` 根本没装，那 0 是命令失败。**任何"扫描类"检查都必须
     先证明工具在、且能对已知阳性样本报警**（这正是负向测试的作用）。
  8. **"一个任务修好了"不等于"这一类问题修好了"。** 本轮连续三次撞上同一个模式：
     · T1 的 digest 绑定了源码 —— T2 连 pin 都没有；
     · T1 的 `_runs_repro3` 补登记了 —— T2 的 `_runs` 照样漏着；
     · `IMAGE_DIGEST.json` 只做了 T1。
     **修完一处必须立刻问"同一个缺陷类还有谁"。** 所以本轮把工具**提到仓库级并参数化**，
     用一条检查管住所有任务，而不是复制粘贴第二份。
  9. **不被消费的产物会静默腐烂。** T2 的两个 schema 因为没有任何代码引用，
     坏掉（非法 JSON）很久都没人知道。**"有文件"不等于"有约束"** ——
     产物必须接上真实数据（`validate_schemas.py` 现在会把它们拿去校验 4,726 条）。
  10. **能验的东西不要写成"无法验证"。** T2 的 HF 上传状态长期被标成
      "需联网才能复核"，但 `hf repo list --format json` 给一个 `storage` 字段，
      **不需要下载任何内容**就能看出来是 `0 B` —— 于是那句"已上传并逐字节比对"
      其实是假的，而"无法验证"这个标签让它躲过了所有检查。
      **把懒惰说成局限，会让假话安全地待在文档里。**
  11. **枚举式清单必然漏，要用检查兜住。** 本轮三次撞上同一件事
      （`_runs_repro3`、`tasks/T2/_runs`、T2 的全量 items/truth/audit）。
      清单是人写的，人会忘；所以每一条"必须排除"的约定都要配一个检查，
      把"漏了"变成**失败**而不是**静默放行**。
  12. **"只扫两份文档"等于给第三份文档开豁免。** 本轮两个检查器各犯一次：
      T2 的字段数只扫根 README + DATACARD（漏了 `tasks/T2/README.md` 的旧值 40,110）；
      T1 的区间只扫 2 份文档（漏了 `research/` 与 `baseline/README.md`）。
      **覆盖面本身就是个需要被检查的东西** —— 现在两处都改成"全文档数值矛盾扫描"。
      对应地 T1 的区间扫描清单从 9 份加到 10 份（14→15 条断言）。
  13. **手工维护的第二份副本必然漂移。** `tasks/T2/data/public/README.md` 是
      数据集卡的**手工复制**，实测比卡片少 820 B、缺了"尚未上传"警示；
      而它正是**要上传到 HF 的那一份**。凡"同一内容存在两份"，
      就必须让第二份**由第一份生成**（现在是 `split_public_rotation.py` 生成 +
      逐字节一致性检查）。附带一个 Windows 陷阱：`write_text` 默认把 `\n` 翻成
      `\r\n`，生成物与真源**哈希不同**（8043→8218 B）—— 必须 `newline=""`。
  14. **检查器的"自述覆盖"必须用已知阳性钉住。** T2 的 `check_no_leakage.py`
      是那道"生命线"，docstring 明写会查 `NM_/NC_/NG_/NR_/XM_/XR_`，
      但实测**7/11 种形态永远漏检**（真实写法 `NM_000277.3` 中间有下划线，
      而 pattern 要求数字紧跟 `NM`）—— 连真值 HGVS 里出现 376 次的
      `NM_001754.5` 都在漏检那类里。
      **变异测试（把已知阳性逐个注入）应该是每个"扫描类"检查器的标配**；
      本轮给 T2 的检查器加了 `--self-test`（8 类 pattern × 32 个阳性），
      它**当场又抓出第二条坏 pattern**（三段式 `12-102852862-G-T` 完全漏检）。
      放宽 pattern 时同时验了误报：对全部 4,726 条题面的所有字段扫描，**0 误报**。
  15. **"文档里写过"不等于"有东西在守着"。** 两个判分器的自检
      （T1 的 1.0/0.25、T2 的 11/11）此前**都只写在文档里**，
      没有任何自动检查在跑它们 —— 而 T1 那份文档给出的命令
      （`grade.py --self-test`）**连 flag 都不存在**。
      数字是真的，但**没有东西能保证它一直是真的**。
      现在两者都进了 `run_all_checks.py` 第 6g 步。
      → 凡"某检查已通过"的声明，都要问一句：**是谁在反复跑它？**
  16. **产物可复现，结论才可复现。** DATACARD 里的 κ 数字是从 rubric 套件
      **重新生成的产物**里读出来的，而 `verify_rubric_claims.py` 只比对
      "文档 vs 产物"—— **它无法发现产物本身不可复现**。
      实测 11 个产物重跑两次逐字节相同（确定性成立），
      新增 `verify_rubric_determinism.py` 把这个性质固定下来，
      并做负向测试（注入一个随机字段 → 立刻报"不可复现"）。
      **"文档与产物一致"和"产物可复现"是两件事**，前者不蕴含后者。
  17. **检查"状态"不等于检查"动作"。** 本轮所有既有检查都在验
      "仓库里的状态对不对"（轮换池有没有被排除、镜像 pin 对不对），
      **但没有一个在看"你打算上传什么"** —— 而 T2 的发布集里，
      正确目录与错误目录**只差一个 `/public`**，错一次就把
      「轮换池永不公开」永久变成假话。
      → 教训：**凡"不可撤销的操作"，都要在动手前对它本身建一道检查**
      （`verify_upload_preflight.py`），而不是只检查操作完的状态。
  18. **给别人照抄的命令，必须自己先跑通。** 我在上传手册里写了一段
      `python -c @"..."@` 的内联比对 —— 而本项目在 Windows/PowerShell 上
      被内联脚本的引号问题坑过多次（本轮写手册时又踩一次）。
      随后把比对逻辑移进脚本（`--compare-with`）并加了负向测试。
      **文档里的命令是产品的一部分**：跑不通的命令 = 不成立的承诺。

---

## 4. v1 范围：切入点 A —— 生信实操榜（VeriBench-Bio）

### 4.1 选题标准（六条全满足才收）

- [ ] 真值来自**权威公开**资源（非自算）
- [ ] CPU-only 可跑，**全集 <30 分钟**
- [ ] 许可允许公开再分发，或只需分发"脚本 + accession + 参考答案"
- [ ] 有明确、可自动化的评分量（F1 / 相关系数 / 集合重叠…）
- [ ] 污染风险可控（时间切分 / 程序化生成 / 私有轮换）
- [ ] 不触碰生物安全红线（§8）

### 4.2 题目清单（已由 `research/DATA_LICENSES.md` 定稿）

| # | 题目 | 真值类型 | 真值来源 | 评分量 | 30min CPU | 状态 |
|---|---|---|---|---|---|---|
| T1 | 变异检出 | **authoritative** | GIAB / NIST **v5.0q**（基于 T2T-HG002 v1.1）；主样本 **HG002 / RM 8391** | SNP/INDEL P/R/F1（hap.py + RTG vcfeval，BSD-2） | ⚠️ 仅限 **chr20 10–12 Mb + 预置 BAM** | ✅ 可做 |
| T2 | 变异解读（**身份脱敏 + 时间切分**） | **authoritative** | ClinVar **3★（reviewed by expert panel）**；set-F1 真值取 **ClinGen EREPO** 的 Applied Evidence Codes | 5 类准确率 + 秩距离 + **判据 set-F1** + 方向性惩罚 | ✅ | ✅ **可做，题池 3,545 条**（见 `tasks/T2/README.md`） |
| T3 | 蛋白结构任务 | **authoritative** | **PDB（CC0）** | 待定 | ✅ | ✅ 可做 |
| T4 | 本体/功能注释 | **authoritative** | **GO（CC BY 4.0）** | 待定 | ✅ 秒级 | ✅ 可做 |
| T5 | 宏基因组物种组成 | **authoritative** | **CAMI2**（替代 Cuatro Ciénegas） | 丰度相关性 / 分类学精确率 | ✅（MetaPhlAn 省内存） | ✅ 可做 |
| T6 | 直系同源聚类 | **authoritative** | **QfO**（改用 *S. coelicolor* / *M. tuberculosis*） | 聚类准确率 | ✅ | ✅ 可做 |
| T7 | 转录本定量 | ⚠️ **reference-implementation** | GEUVADIS **无官方真值** → 降级为"参考实现的输出" | 与参考实现输出的一致性（**不是准确率**） | ✅ | ⚠️ 只能进"可复现性"分区 |
| T8 | 差异表达 | ⚠️ **reference-implementation** | GEO **无真值** → 同 T7 | 与参考实现输出的一致性 | ✅ | ⚠️ 只能进"可复现性"分区；改用 **PyDESeq2(MIT)** 避开 R 的 GPL 陷阱 |

**已放弃的题目（原则 2 执行结果）**：
- ❌ **Micrococcus 直系同源聚类** —— QfO 无该场景的权威真值 → 整题放弃，改用 QfO 的 *S. coelicolor* / *M. tuberculosis*
- ❌ **Cuatro Ciénegas 物种组成** —— 无真值 → 改用 CAMI2

**T7/T8 必须诚实处理**：这两题被降级后，**不得**与 T1–T6 混排在同一张准确率榜上；leaderboard 中单独分区，标注 `truth_type=reference-implementation`，对外描述为"**可复现性**"而非"准确率"。参照实现必须**唯一锁定**——因为 **kallisto ≠ salmon**（见 §5.5），两个工具的输出数值不可互换。

**T1 的 30 分钟代价必须写明**：为守住预算，本题**预置已比对好的 BAM**（chr20 10–12 Mb，约 2 Mb），只考变异检出、不考比对。这是刻意的范围收缩，不是能力缺失——DATACARD 里要主动说明。

**污染风险分级（必须写进 DATACARD）**：ClinVar 解读 **极高**、GEO DE **高**、GEUVADIS 定量 中、GIAB 变异检出 **低**、宏基因组 低、PDB/GO 低。高风险题一律需要时间切分或程序化生成。

### 4.3 评测契约（输出什么）

每个任务产出统一格式，**必须包含时间与成本**：

```json
{
  "task_id": "T1",
  "score": 0.9123,
  "metric": "f1_snp",
  "wall_clock_sec": 412,
  "peak_rss_mb": 2048,
  "cpu_count": 2,
  "image_digest": "sha256:...",
  "manifest_hash": "sha256:...",
  "status": "ok"
}
```

榜单必须同时展示**分数 + 耗时 + 镜像 digest**——只报分数不报成本的榜是误导。

### 4.4 T1 工具链决策（已定，依据 §5.6 与一手许可核验）

**结论：v1 不打包 GATK4。T1 默认工具链全部宽松许可，零 copyleft。**

| 组件 | 许可 | 核验状态 |
|---|---|---|
| **FreeBayes** | **MIT** | ✅ 已亲手读 `LICENSE` 原文（Erik Garrison / Gabor Marth："Permission is hereby granted, free of charge … without restriction"） |
| **RTG `vcfeval`** | **BSD 2-Clause** | ✅ 已亲手读 `LICENSE.txt` 原文 |
| **`hap.py`** | **simplified BSD**（`src/` 子目录） | ✅ 已亲手读 `LICENSE.txt` 原文 |
| `samtools` / `bcftools` / `htslib` | MIT / Expat（htslib 的 `cram/` 为 Modified-BSD-3；bcftools 为 MIT-or-GPL 双许可） | ✅ **2026-09 已按镜像内实际版本逐个 tag 读上游 `LICENSE` 原文**（samtools 1.16.1 / bcftools 1.16 / htslib 1.16），链接见 `NOTICE` [A] 块。⚠️ **bcftools 绝不能启用 GSL**（否则转为 GPL-governed；上游默认关闭，构建期门禁 `check_no_gsl.sh` 四道检查强制，见 §12） |

**为什么不用 GATK4（虽然它是 Apache-2.0）**：它的官方运行环境会**一次性**引入**专有 Intel oneMKL、GPL 的 R/GSL、LGPL 的 `htsjdk-tribble`（不可剥离）、双许可的 `jgrapht`**（§5.6③④）。换成 FreeBayes 后这些问题**同时消失**，镜像**体积大幅缩小**——而这与"30 分钟 CPU-only、任何人都能复现"的核心卖点**直接一致**。

**GATK4 的处置**：作为**可选层**在文档中给出自建方法，由接受相应义务的使用者自行构建；**v1 镜像不含它**，README 需说明。

**副作用（正面）**：§5.6 的 LGPL/NOTICE/`zip -d` 剥离工作**对 v1 镜像不再必需**。但仍保留在文档中，因为 (a) 将来若加回 GATK4 就要用；(b) 它记录了一次真实的许可审计，本身就是本项目"可信性"叙事的一部分。

---

## 5. 切入点 C：题级 provenance ledger（贯穿始终，不单列工作量）

### 5.1 ledger 字段（每题一条，缺字段即拒收）

| 字段 | 说明 |
|---|---|
| `item_id` | 稳定 ID |
| `task` | T1..Tn / R（rubric 题） |
| `source_type` | `public_dataset` \| `derived_from_paper` \| `synthetic` |
| `source_url` / `accession` | DOI / GEO / ENA / PMC ID |
| `license_spdx` | SPDX 标识；不确定写 `unknown` |
| `redistribution_ok` | bool（能否随仓库分发原件） |
| `commercial_ok` | bool |
| `contains_human_data` | bool |
| `contains_restricted_data` | bool（受控访问 / 需 IRB） |
| `derivation` | 从原文如何生成的（改写 / 截取 / 程序化生成） |
| `evidence_quote` | 若有原文依据，附引文与位置 |
| `reviewer` / `review_status` | 谁核过 |
| `created_at` | 时间戳 |

### 5.2 自动许可审计

`scripts/audit_licenses.py` 必须能在 CI 里**让不合规的题目把构建打红**：
- 任何 `license_spdx == unknown` 且 `redistribution_ok == true` → 失败
- 任何 `commercial_ok == true` 但 SPDX 属 `-NC-` → 失败
- 任何 `contains_restricted_data == true` 却出现在公开目录 → 失败
- 任何 `ND` 许可却被标记为 `derivation: rewritten` → 失败

这在竞品里没人做，成本低、辨识度高，且是真实痛点（BioProBench 就被卡住）。

### 5.3 许可白名单与三条已核实的坑（2026-09 法律尽调结论）

**白名单（只有这些可用）：`CC0-1.0` / `CC-BY-4.0` / `CC-BY-3.0` / 公有领域（public domain）。**
**黑名单：一切 `-NC-`（禁商用）与 `-ND-`（禁衍生）与 `-SA-`（传染）。**

| 坑 | 事实 | 对我们的动作 |
|---|---|---|
| **1. 可商用 ≠ 可用** | **CC BY-ND 禁止衍生作品，而"把原文内容转成评测题/改写"本身就是衍生作品** | **ND 一律不可用**，不是"标注一下就行" |
| **2. arXiv 默认许可不是开放许可** | 默认 "perpetual, non-exclusive license 1.0" 明确 LIMITS RE-USE OF ANY TYPE FROM OTHER ENTITIES；ToU 禁止把 e-prints 存到自家服务器对外服务。**仅元数据是 CC0，正文不是** | 若 rubric 题用到 arXiv，必须**逐篇解析 OAI-PMH licence 字段**，只取 CC0/CC BY；**不许把 arXiv 当"安全区"** |
| **3. 摄入即侵权理论已被起诉主张** | *Elsevier et al. v. Meta*（S.D.N.Y.，2026-05-05）主张损害发生在 **POINT OF INGESTION**，"我只内部建库、不再分发原文"正是其打击目标 | 我们只处理**白名单许可**的公开语料；不建订阅期刊内部库；对"我们拥有 XX 万篇论文语料"这类表述**一律回避** |

**补充**：`protocols.io` 属于"词法 CC-BY、实际被平台合同封死"（其 §4.A 禁批量下载/建库/衍生），**不适合作为评测语料来源**。另外 Springer Nature 同时拥有最大 protocol 库与其源语料并从两侧限制竞争者——**不要依赖单一出版集团的语料**。

### 5.4 已核实的一手结论（GIAB / PMC / vcfeval）

**① 变异检出题的主样本必须是 HG002，不能用 HG001。**
NIST 原文：HG002–HG005（Ashkenazi/Han trio）来自 PGP，是「selected because, unlike the pilot genome, they are **consented for commercial redistribution**」，FAQ 第 11 问重申。
→ **HG001/NA12878（HapMap 来源）的捐献同意未明确覆盖商用再分发。** 数据本身是 NIST 作品、公有领域，但样本同意存在瑕疵 → **HG001 不纳入"明确可商用"的声明范围**。

**② HG002 的 v4.2.1 自 2025-11 起 deprecated，已被 v5.0q 取代。**
v5.0q 基于 **T2T-HG002 v1.1** 组装，覆盖 GRCh37 / GRCh38 / T2T-CHM13v2.0。若坚持用 v4.2.1，**DATACARD 必须写明 deprecated**。

**③ vcfeval 不是非商用许可，是 BSD-2-Clause（推翻原假设）。**
RTG Tools 的 LICENSE 是标准 **BSD 2-Clause**，README 自述 "provided under the Simplified BSD License"；hap.py 的 LICENSE 也确认「RTGtools for variant comparison: Simplified BSD license」。
→ **含 hap.py + vcfeval 的镜像可公开分发、可商用。**
⚠️ 唯一注意：**RTG Core 是另一个独立商业产品，不得混入镜像。**

**④ PMC 分发层已于 2026-08 被移除 —— 基于 `oa_file_list.csv` 的许可筛选流水线已死。**
- `oa.fcgi?id=PMC13900` → **HTTP 404**（实测）
- `https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.csv` → **HTTP 404**（实测）；`oa_comm/`、`oa_noncomm/`、`oa_other/` 已移除
- FTP 现仅剩 `PMC-ids.csv.gz`
- 现行合法路径只有 4 条：**AWS Cloud Service / OAI-PMH / E-utilities / BioC API**；官方明文「Systematic retrieval (or bulk retrieval) of articles through any other automated process is **prohibited**」
- **替代做法**：S3 bucket `pmc-oa-opendata`（匿名 `--no-sign-request`）读 `metadata/PMC<id>.<ver>.json` 的 **`license_code`** 字段；或 OAI-PMH `set=pmc-open` 解析 `<dc:rights>`
- 实测（2026-09-12）：OA Subset **8,219,033** 条中，"可再分发+可改作+可商用"（CC0+CC BY+**CC BY-SA**）= **5,421,148**；NC 类合计 2,380,218（**29.0%**）；非 CC 残留约 405,639
- ⚠️ **NCBI 自己推荐的商用检索式对我们的用例是错的**：它包含 `cc by-nd`（禁改作）与 `author manuscript`（TDM 许可，**不授予再分发权**）
- ⚠️ **我们的白名单比"合法"更严**：我们排除 `-SA-`（传染性），因此可用池是 **CC0 + CC BY**，**小于** 5,421,148。这是刻意选择——为了让本项目的产出维持单一许可，而不被迫 share-alike。（仅 CC0+CC BY 的确切条目数由 `research/DATA_LICENSES.md` 最终版给出。）

### 5.5 工具链许可与容器策略（结论已反转：**零 GPL 可行**）

**✅ 已逐个核实：全部题目都能用纯 MIT / BSD / Apache 工具链实现，无 GPL 依赖。**

| 工具 | 许可（已核实） | 备注 |
|---|---|---|
| hap.py + RTG **vcfeval** | **BSD-2-Clause** | GA4GH 官方组合；**RTG Core ≥3.13 起也已改 BSD** |
| **GATK4（≥4.2）** | **Apache-2.0** | ⚠️ 真正的非商用陷阱是 **GATK3**（Broad 学术非商用专有协议 + 禁再分发 + phone-home）——**不要用** |
| **salmon（≥2.0）** | **BSD-3** | 「salmon 是 GPLv3」的判断**已更正**（GPLv3 只适用旧版） |
| **STAR（≥2.7.2a）** | **MIT** | 「STAR 是 GPLv3」的判断**已更正** |
| kallisto | **BSD-2**（注意文件名是小写 `license.txt`） | |
| minimap2 / bwa-mem2 / samtools / htslib | **MIT** | |
| bcftools | **双许可 MIT 或 GPL → 可主动择 MIT** | |
| **PyDESeq2** | **MIT** | 用于 T8，避开 R 生态 |
| DESeq2 | LGPL(≥3) | 尽量不用 |
| edgeR / limma | **GPL(≥2)** | ⚠️ **在 R 进程内加载 = 结合作品** → T8 因此改 PyDESeq2 |
| vcfdist | GPLv3 | ✅ **已确认完全不需要** |

**⚠️ kallisto ≠ salmon（必须记住的一条）**：kallisto 用 pseudoalignment，salmon 用 selective alignment，**per-transcript 数值不可互换**。→ 每题必须**锁定唯一参考工具**，并按**该工具自己的输出**评分（T7 尤其如此），否则一致性指标没有意义。

**容器策略（结论已反转）**：既然零 GPL 可行，**直接发布预构建镜像即可**，不必走"只发 Dockerfile"的保守路线。已核实的法律依据：GPLv3 §0「convey = 使他人可复制；单纯网络交互而无副本转移不算 convey」、§2「do not convey 的行为无附加条件」→ 纯 Dockerfile 不构成 convey；§5 的 aggregate 定义使"我方 MIT 代码 + 独立 GPL 二进制同处一镜像"成为聚合，**不传染我方代码**；**触发 §6 的是发布预构建镜像**。仅当必须引入 GPL 工具时，才退回分层镜像 + `/licenses/` + `GPL_SOURCES.md`。

**容器许可政策（已修订 —— 依据见 §5.6）**：
- **禁止**：GPL / AGPL / **专有非开源**（如 Intel oneMKL）/ 非商用组件
- **允许但须附合规材料**：LGPL（上游源码 URL 与精确版本、书面要约、可重新链接性说明），统一放 `/licenses/` 并在 DATACARD 列明；**能用宽松许可或可择许可时优先规避**（如 `jgrapht` 显式择 EPL-1.0）
- ⚠️ **`"镜像内不得含 GPL"` 按字面不可能满足**（`bash`/`coreutils`/`sed`/`tar`/`grep` 本身就是 GPL 二进制，存在于每个 Ubuntu 镜像里）→ 正确语义见 **§5.6 ⑤**，**建议先与法务确认**
- **以工具上游 LICENSE 为准，不信 conda recipe 的 license 字段**（`htsjdk` 的 POM 谎称 MIT 就是实例）

> 以上为有依据的风险判断，不是法律意见。

### 5.6 GATK4 实测审计（字节码可达性 + 二进制内容 + conda 环境）

> ⚠️ **本节为第二次修订。** 第一版依据"jar 内含 GPLv3 BWA 与静态链接 LGPL libuuid"修订了政策，**该前提经逐文件核验后不成立，已更正**。**结论方向未变（默认镜像仍要处理），但风险来源换了地方。**

**① 运行时没问题。** 对官方 `gatk-4.7.0.0.jar` 做字节码可达性分析：从 HaplotypeCaller 出发的 **763 类闭包里 `utils/bwa/` 完全不可达（0 个 BWA 类）**，`org.genomicsdb.*` 的 JNI 类也不可达（只有 GATK 自己 `tools/genomicsdb/` 下的配置包装类）。native 库只在 `GenomicsDBImporter` / `GenomicsDBFeatureReader` / `GenomicsDBQuery(Stream)` 构造时、或 FeatureDataSource 输入路径为 GenomicsDB 路径时加载 —— **"预置 BAM + 单样本 HaplotypeCaller"两个条件都不满足**。→ 我们的用法确实同时绕过 BWA 与 GenomicsDB。

**② 官方镜像默认仍要处理，但原因不是 GPL。** 义务附着在"**分发副本**"上，**与代码是否执行无关**。官方 `gatk-package-4.7.0.0-local.jar` 实测确实内含 `libbwa.Linux.so`（744,135 B）与 `libtiledbgenomicsdb.so`（25,391,160 B）。**但两者经核验都不构成 copyleft 问题**：

- **BWA 在那个 pin 住的 commit（`cb950614`）是 Apache-2.0，不是 GPLv3。** 该 commit 完整 75 项文件树里**唯一的许可文件是 `LICENSE.txt` = Apache-2.0**（9,618 B），**无 `COPYING`、0 个 GPL 头**；其 Makefile 的 `LOBJS` 加 sed 补丁共 15 个目标文件，**无一 GPL**（master 上唯一带 GPL 头的 `bwt_gen.c` 不在该树里）。上游确实换过许可（2011 首提交有 `COPYING`=GPLv3；v0.7.17/18/19 与 master 是 GPLv3），**属上游许可管理缺陷**，写进风险登记即可。
- **libuuid 是 BSD-3-Clause，不是 LGPL。** 被链接的源文件 `e2fsprogs/lib/uuid/gen_uuid.c` 头部逐字是 Theodore Ts'o 的三条款 BSD；Ubuntu `libuuid1` 与 conda-forge 的 copyright 也都是 BSD-3-Clause。**是 GenomicsDB 自己的 LICENSE 把它写成 LGPLv2 —— 上游写错了（高估）。**
- `libcsv` **完全没有被链入**（已被上游排除）。

**→ 剥离动作依旧建议，但性质是"清掉署名义务"而非"清掉 GPL"**：
```bash
zip -d /gatk/gatk.jar 'libbwa.*' 'libtiledbgenomicsdb.*' 'libfml.*'
```
外加 `MODIFICATIONS.md`（Apache-2.0 §4(b) 要求标注修改）。
**B 的真问题是署名缺失**：`gatk-bwamem-jni` 只有 `LICENSE(BSD-3)` 一个许可文件、**无 NOTICE、无 BWA 归属**；官方 jar 内所有 notice/license/copying 文本里 **bwa/BWA/libuuid/uuid/libcsv 全 0 命中** —— 内含约 744 KB 受 Apache-2.0(+MIT) 治理的代码却**没有任何对应许可文本**。这是 **Apache-2.0 §4 / MIT 署名义务的违反，不是 GPL 传染**。
README 仍需说明：**BwaSpark / PathSeq / SV / FilterAlignmentArtifacts 及 GenomicsDB 相关工具将不可用（预期 `UnsatisfiedLinkError`），对 T1 无影响。**

**③ ⚠️ 真正的问题（两处，且都在执行路径上）**：

| 组件 | 实际许可 | 为什么必须处理 |
|---|---|---|
| `com.github.samtools:htsjdk:5.0.0` 的 **`htsjdk/tribble/**`（22 个文件）** | **LGPL-2.1** | **POM 只写 MIT**，但 `FeatureCodec.java` 逐字写 "licensed under the terms of the GNU Lesser General Public License (LGPL), Version 2.1"（同批还有 `samtools/seekablestream/**`、`samtools/util/ftp/**`）。**GATK 的 `FeatureDataSource` 直接 import `htsjdk.tribble.*`，而它在 HaplotypeCaller 的 763 类闭包内** → 任何 `--dbsnp` / `--known-sites` 必然走到。**无法剥离。** 下游 notice 几乎必然漏掉它（因为 POM 说谎）。 |
| `org.jgrapht:jgrapht-core/io:1.1.0` | **LGPL-2.1 或 EPL-1.0（双许可，被许可方择一）** | `Graph.java` 逐字 "dual-licensed under either (a) the terms of the GNU Lesser General Public License version 2.1 … or (per the licensee's choosing) (b) … Eclipse Public License v1.0"。**⇒ 我们可显式择 EPL-1.0，完全避开 LGPL §6 的重链接义务。** 这是本次审计最省事的一个发现。 |
| jar 内 vendored `gnu.getopt:java-getopt:1.0.13` | LGPL-2.0 | ✅ **源码义务已满足**：jar 内已随附完整 `Getopt.java` / `LongOpt.java` 与 `COPYING.LIB` |

**④ ⚠️ 最严重的一层不在 GATK 里，在 conda 环境**（这才是必须自己写 Dockerfile 的原因）：
- **Intel oneMKL 是专有闭源组件**：`scripts/gatkcondaenv.yml.template` 逐字含 `conda-forge:blas=1.0=mkl` 与 `pytorch=2.1.0=*mkl*100`；conda-forge 配方标注 `license: LicenseRef-IntelSimplifiedSoftwareOct2022` + **`license_family: Proprietary`**；ISSL 原文 "provided in binary form only … No reverse engineering, decompilation, or disassembly…"，**源码不可得** —— 比 LGPL 更值得警惕。
- **真 GPL**：`r-base=4.3.1`（GPL-2+）、其硬运行依赖 **`gsl`（GPL-3+）**、`r-gplots` / `r-catools` / `r-gtools` / `r-mass` / `r-mgcv` 等（GPL-2+），以及 `gcc_impl` / `gxx_impl` / `gfortran_impl`（GPL-3 编译器二进制）。
- **真正在用的 LGPL 共享库是 `liblzma5`（LGPL-2.1+，动态链接，义务易满足）**。
- 澄清（避免误伤）：**bcftools 1.13 走 MIT 分支**（未链接 libgsl，Ubuntu copyright 的 GPL 警告不成立）；**bedtools 2.30 上游是 MIT**（v2.25 才是 GPL-2，Ubuntu 元数据陈旧）；**apt 装的二进制里没有 GPL/LGPL 被静态链接**（唯一静态链接是 tabix 内嵌 htslib，属 MIT/BSD-3）。
- **⇒ 解法：自己写 Dockerfile —— 去掉 R，BLAS 从 mkl 换成 openblas/blis。** GPL 与专有组件同时消失，镜像体积也会大幅下降。

**⑤ 🔴 最重要的政策提醒：`"镜像内不得含 GPL"` 按字面根本不可能满足。**
`bash` / `coreutils` / `sed` / `tar` / `grep` / `gzip` / `make` / `wget` / `git` / `dpkg` **本身就是 GPL-2/GPL-3+ 二进制，存在于每一个 Ubuntu 镜像里**。
→ 该政策只能理解为：**"不得含与我们应用构成组合作品、或我们需要依赖其核心功能的 GPL 组件"**。按此理解：
- GPL userland → **聚合放行**
- `libgcc` / `libstdc++` / `libgomp`（GPL-3 WITH GCC-exception-3.1）、OpenJDK（GPL-2 WITH Classpath-exception-2.0）→ **假阳性放行**
- **真正要处理的是：MKL、GSL、R、htsjdk-tribble、jgrapht**
→ **建议先与法务澄清这条政策的语义**，它决定后面所有取舍。

**⑥ 替代路径（若要求完全无 copyleft）**：比对工具 **minimap2 = MIT**；**bwa-mem2 = MIT，但必须 pin ≥2.0**（`NEWS.md` 载 "Changed the license from GPL to MIT"，2.0 之前是 GPL；v2.3 全源码 GPL 关键词 0 命中；**残留注意**：派生文件只署 Intel+Heng Li，未完整保留上游 DFCI/Broad/GRL 署名，属署名卫生问题而非许可有效性问题）。避免 `bowtie2` / `HISAT2` / `dragmap` / `Strelka2`（GPL-3）。**STAR = MIT**。
Caller：**DeepVariant = BSD-3-Clause**、**FreeBayes = MIT**、`bcftools` + htslib = MIT/Expat（⚠ **GSL 陷阱**：启用 GSL 会使 bcftools 转为 GPL-governed，构建时**绝不能开**，默认关闭）。
**必须排除**：**VarScan 是非商用专有**（README 原文 "free for non-commercial use by academic, government, and non-profit/not-for-profit institutions"）—— 正是我们政策禁止的；**Sentieon 商业专有、EULA 禁再分发，不能进公开镜像**；`LoFreq` 仓库自称 MIT 但 `src/cdflib90.README` 无许可条款、其 LICENSE 引用的 samtools/htslib LICENSE 均 404 → 要用必须 pin 精确版本重读。

**⑦ 实测证伪的常见误解（别被误导）**：`org.jpmml:pmml-model:1.4.8` 是 **BSD-3-Clause**（不是 AGPL —— AGPL 在姊妹项目 `pmml-evaluator`，**要查我们清单里有没有它**）；`org.json:json:20231013` 是 **Public Domain**（"Good, not Evil" 已不在）；`gsalib` 是 **MIT**；`MUMmer 4.0.0rc1` 是 **Artistic-2.0**（其 §5 要求提供源码指引，GATK 已在 jar 内 `README.TXT` 给了 mummer4 tarball URL —— **这条必须在我们的 NOTICE 里继承**）。
另：`jersey`（CDDL-1.1 或 GPL-2.0-CE，**择 CDDL**）、`javassist`（MPL-1.1 / LGPL-2.1 / Apache-2.0 三许可 → **显式选 Apache-2.0，义务消失**）、`netty-tcnative-boringssl`（只需复制 OpenSSL/SSLeay 致谢句；那里的 "non-commercial" 是 SSLeay 原文 "free for commercial and non-commercial use"，是**允许**商用，不是限制）。

**⑧ 一份不完整的 SBOM（必须取并集）**：官方 `gatk.jar` 保留了 `META-INF/maven/*/pom.properties`，**共 308 项** —— 但**漏掉** `picard`、**`htsjdk`**、`barclay`、`fastutil`、`freemarker`、`objenesis`、`gkl`、`gnu.getopt`（分别是 Gradle 或老式 Ant 构建、不带 pom.properties）。
→ **必须与自己的依赖解析取并集**，否则**恰好会漏掉 htsjdk 这个 LGPL 项**。
⚠️ **绝不能用 jar 内的许可文件当清单**：shadowJar 合并时同名 `META-INF/NOTICE` 只留一份（实测只剩 Spark ML 一条）。

**⑨ 镜像声明最小清单**：`/licenses/` 下放 `README.md`（许可边界 + 已知能力损失）、`MODIFICATIONS.md`、`GATK-LICENSE.TXT`、`NOTICE`、`THIRD-PARTY-LICENSES.md`（由 308 项 `pom.properties` **∪ 自有依赖解析**生成）、`texts/`（LGPL-2.1、LGPL-2.0、**EPL-1.0**、CDDL、Apache/MIT/BSD、**Artistic-2.0**、boringssl-OpenSSL-SSLeay 致谢、HDF5）。
`NOTICE` 硬项：① GATK Apache-2.0 + 修改声明；② **htsjdk：MIT 但 tribble 等 22 文件为 LGPL-2.1**（POM 没写，必须我们自己写）；③ **jgrapht：本项目显式选择 EPL-1.0**；④ `gnu.getopt` LGPL-2.0；⑤ **MUMmer Artistic-2.0 + 源码 URL**（Artistic-2.0 §5 强制，不可省）；⑥ gsalib MIT；⑦ Intel MKL 的 ISSL 声明；⑧ R/GSL 的 GPL 声明；⑨ `liblzma5` LGPL-2.1+；⑩ 启动可见的 LGPL "prominent notice"（LGPL-2.1 §6 要求）。
若采用"剥离 + 自建精简 Dockerfile（去 R、换 BLAS）"，NOTICE 可大幅精简。

**⑩ 本轮未闭合（列入下一轮）**：**`hap.py` 与 `vcfeval` 的许可未在本轮核实**（我先前依据另一路调研判定 vcfeval=BSD-2，**需再确认一次**）；未能检视运行中的镜像（本机 Docker daemon 未运行）→ 建议跑 `docker run --rm broadinstitute/gatk:4.7.0.0 sh -c 'conda list -n gatk | grep -iE "mkl|^gsl|r-base"'` 确认 MKL/GSL/R 确实被解析安装；**未做运行时 dlopen 验证** → 建议 `strace -f -e trace=openat` 跑一次 HaplotypeCaller，预期 `libbwa` / `libtiledbgenomicsdb` 无输出。

---

## 6. 切入点 B：LLM 裁判可靠性元评测（第二个支柱）

**为什么必须有**：榜单若用 LLM judge 打分而不报一致性，整张榜不可信。这是当前生态的普遍缺陷，也是我们能低成本做出的、最容易被引用的贡献。

- **题源**：PMC OA Subset 中**仅 CC0 + CC BY** 的子集（**必须逐篇记 `license_code`**）
  - ✅ **已实测的确切检索式**：`("cc0 license"[filter] OR "cc by license"[filter]) AND "open access"[filter] NOT "pmc embargo"[filter]` → **5,418,532 条（占 OA Subset 65.9%）**
  - 排除 CC BY-SA 只损失 **2,516 条（0.03%）** → **"排除传染性许可"这个决定几乎不花钱**，更该坚持
  - ⚠️ **NCBI 官方推荐的商用检索式对我们错误**：必须剔除 `cc by-nd license[filter]`（禁改作）与 `author manuscript[sb]`（默认 TDM，**不授予再分发权**）。照抄官方式会让我们把**没权利改写**的文章做成题目。
  - ⚠️ **PMC 批量通道已于 2026-08 变更**：`oa_file_list.csv` 与 `oa.fcgi` 均实测 **HTTP 404**，`oa_comm/`、`oa_noncomm/`、`oa_other/` 已移除；合法路径只剩 **AWS Cloud Service / OAI-PMH / E-utilities / BioC API**。推荐 S3 `pmc-oa-opendata`（匿名 `--no-sign-request`）读 `metadata/PMC<id>.<ver>.json` 的 **`license_code`**（无 10k 上限；E-utilities 的 ESearch 有 10k 上限）。**不许写爬虫。**
  - ✅ **已实测的 `license_code` 取值**（2026-09，自 S3 抽样 50 条）：字段名就是 **`license_code`**；观测到 **`"CC BY"`（45/50）**、**`"CC BY-NC-ND"`（5/50）**，以及**老记录为 `null`**。
  - ⚠️ **由此暴露的两个陷阱（都会直接坑到我们）**：
    1. **`null` 很常见**（老 OA 记录普遍没有许可码）→ 一律按 `unknown` 处理、**不得进公开题库**（审计器 **R7** 会拦）。
    2. **`"CC BY"` 不带版本号** → **不能直接当 `CC-BY-4.0`**。必须**从文章 XML 里的许可 URL 解析版本**（如 `creativecommons.org/licenses/by/4.0/`），并把 `license_code` 与 `license_spdx` **两个字段都记进台账**。
  - 📌 **可直接使用的取数方式（已实测可用）**：
    - 列举：`https://pmc-oa-opendata.s3.amazonaws.com/?list-type=2&prefix=metadata/&max-keys=1000`（匿名可读，返回 `NextContinuationToken` 翻页）
    - 元数据：`https://pmc-oa-opendata.s3.amazonaws.com/metadata/PMC<id>.<ver>.json`
    - 正文：元数据里的 `text_url` / `pdf_url` / `xml_url` 是 `s3://` 路径，改成同域 HTTPS 即可取（自带 `md5` 校验）
  - 不使用 PMC logo。
- **题量**：150–200 道"审稿式"开放题，每题 **3–5 条 rubric**
- **标注**：双人独立标注 + 分歧仲裁；公开 **Cohen's κ**（含每 rubric 项的分项一致性）
- **产物**：公开 judge prompt、judge 模型版本 pin、**失效案例集**（judge 判错的典型样本）
- **可选加分**：与人类专家打分对照，报告 judge 的系统性偏差（如偏长、偏好格式、对单位错误不敏感）

> 这一格已核实为空白：现有工作要么不发榜，要么用 judge 但不报 κ。

---

## 7. 反污染与榜单生命周期

- **私有轮换集**：留 20% 不公开，用于检测榜单是否被过拟合（对标 LAB-Bench 的做法）
- **程序化生成优先**：能程序化生成的题（参数化合成、变体组合）优先，便于轮换
- **时间切分**：对 ClinVar 这类会持续更新的真值，只使用"模型训练截止之后"的提交
- **明示生命周期**：DATACARD 中写明"本榜有效期约 6–12 个月"，主动承认会饱和——这是可信度的一部分

## 8. 生物安全红线（硬性）

**不做**：增强传播力 / 致病性 / 免疫逃逸、毒素合成、select agents、基因驱动、生殖系编辑。
**只做**：拒答正确性、风险识别、以及"模型是否会在被拒绝的边界上含糊其辞"。

- 高危题**抽象化**，去掉序列、菌株、剂量参数
- 敏感子集 **gated release + canary string**
- 需 **≥1 名生物安全背景审阅者**签字（写进 DATACARD）
- 背景：北京智源 2026-07 已公开警示 LLM agent 生物安全风险；arXiv:2604.19811 已将"能力测量"本身视为风险信号

---

## 9. 交付物清单（v1）

```
bio-eval/
├── README.md                  # 一页看懂：是什么、怎么跑、怎么看榜
├── SPEC.md                    # 本文件
├── LICENSE                    # 代码许可（建议 Apache-2.0）
├── docs/
│   ├── DATACARD.md            # 数据卡：来源、规模、许可、污染、生命周期、审阅者
│   ├── SAFETY.md              # 生物安全声明与红线
│   └── JUDGE_RELIABILITY.md   # κ 报告 + 失效案例
├── schema/
│   ├── item.schema.json
│   └── ledger.schema.json
├── ledger/items.jsonl         # 题级 provenance ledger
├── tasks/T1..Tn/              # 每题：Dockerfile / run.sh / grade.py / truth 指针
├── rubric/                    # 150–200 道开放题 + rubric
├── judge/                     # judge prompt（版本 pin）+ 元评测脚本
├── scripts/
│   ├── audit_licenses.py      # CI 红线
│   └── run_all.py             # 一条命令跑全集并出 manifest
└── leaderboard/               # 公开自助榜（静态站点）
```

**v1 完成的定义（四件套齐备才算成立）**：
1. 可复现 manifest（一条命令 + 哈希）
2. κ 报告（含失效案例）
3. **真实榜单**（不是示例数据）
4. SAFETY + DATACARD + license 文档

### 9.1 DATACARD 必写 6 条（逐字模板见 `research/DATA_LICENSES.md` §16）

1. **总体许可**：内容 CC BY 4.0 / 代码 MIT / Apache-2.0；第三方组件逐项标注。
2. **每条样本必须带** `source_license` / `license_url` / `retrieval_date` / `redistributable` / `modifications` —— **这是防"第 6 天翻车"的核心机制**（BioProBench 就是在这里倒的）。
3. **GIAB 专属**：HG002 可商用；**HG001 不作可商用声明**；版本 deprecated 说明（v4.2.1 → v5.0q）。
4. **GEO / SRA / ENA 专属**：不分发原始数据；**GEO 根本没有 license 字段**、NCBI 无法代其授予许可；无受控数据；脚本遵守速率规范。
5. **PMC 专属**：仅 CC0 + CC BY；逐条记 `license_code`；不使用 PMC logo。
6. **容器专属**：镜像内为纯 MIT/BSD/Apache、不含 GPL 或非商用组件；**以工具上游 LICENSE 为准，不信 conda recipe 的 license 字段**。

## 10. 时间表（7–10 天）

| 天 | 任务 | 出口标准 |
|---|---|---|
| D1 | 冻结数据源与许可；建 ledger schema + 审计脚本 | `audit_licenses.py` 能在 CI 打红 |
| D2 | 打通 T1（变异检出）端到端 + 容器 | 30 分钟内出分，manifest 有哈希 |
| D3 | T2/T3 落地；私有轮换集切分 | 3 题可跑全 |
| D4 | T4 落地 + 补齐被否题目的替代集 | 4–6 题可跑全 |
| D5 | rubric 题撰写 + 双标注（上半） | 100 题完成，κ 可算 |
| D6 | 双标注（下半）+ 分歧仲裁 + κ | κ 报告初稿 |
| D7 | judge 元评测 + 失效案例集 | JUDGE_RELIABILITY.md |
| D8 | leaderboard + README + DATACARD/SAFETY | 四件套齐备 |
| D9 | 外部复现验证（换机器跑一遍）+ 修 | 第三方可复现 |
| D10 | 发布 + 写一篇说明性文章留存 | 公开可用 |

## 11. 主要风险与对策

| 风险 | 对策 |
|---|---|
| 许可第 6 天翻车（BioProBench 前车之鉴：523,784 条仅 350,565 条可发布） | D1 冻结；CI 红线（`scripts/audit_licenses.py`，R0–R9 已实测）；只分发脚本+accession 而非原始数据 |
| 真值不权威 → 榜单不可信 | 原则 2：绝不自算真值；找不到权威真值就**放弃该题** |
| LLM 裁判不可信 | §6 元评测 + κ + 失效案例；必要时对客观题用确定性打分器 |
| 榜单被污染/过拟合 | §7 私有轮换集 + 时间切分 + 生命周期声明 |
| 30 分钟约束被打破 | 每题独立计时门禁，超时即视为设计失败而非放宽预算 |
| **容器混入 copyleft / 专有组件**（实测：`htsjdk-tribble` 是 **LGPL-2.1 且在 HaplotypeCaller 执行路径上、POM 谎称 MIT**；`jgrapht` 为 LGPL-2.1/EPL-1.0 双许可；**conda 环境含专有 Intel oneMKL 与 GPL 的 R/GSL**） | 自建 Dockerfile（**去 R、BLAS 换 openblas**）；`jgrapht` **显式择 EPL-1.0**；`htsjdk-tribble` 写进 NOTICE；`zip -d` 剥掉两个 `.so` + `MODIFICATIONS.md`；`/licenses/` 按 §5.6⑨ 配齐 |
| **"镜像内不得含 GPL"这条政策本身不可满足** | 需与法务澄清语义（GPL userland = 聚合放行；真目标是 htsjdk/GSL/R/MKL），否则规则无法执行（§5.6⑤） |
| **上游分发层消失**（已发生：PMC OA 分发层 2026-08 移除） | 不把任何单一上游当永久可用；采集脚本只依赖**官方许可通道**（S3 / OAI-PMH / E-utilities / BioC）；把"通道失效"写进 DATACARD 的已知限制 |
| **污染**（ClinVar 解读**极高**、GEO DE 高） | 时间切分（只用模型训练截止后的提交）+ 程序化生成 + 20% 私有轮换集；DATACARD 公开污染风险分级（§4.2） |
| **无权威真值却当真值用**（T7/T8 已降级） | 审计器 **R10** 强制 `truth_note`、**R11** 禁止无真值条目公开；T7/T8 只进"可复现性"分区，**绝不与准确率榜混排**；参考实现唯一锁定（kallisto ≠ salmon） |
| 生物安全 | §8 红线 + 去参数化 + gated release + 审阅者签字 |
| 大厂快速补位 | 我们的护城河是**许可洁净 + 公开自助榜 + 裁判可靠性**，不是题量；大厂无动机做"公开自助" |

---

## 12. 待办（阻塞项）

**已由 `research/DATA_LICENSES.md` 解决**：题目清单与许可策略（§4.2 / §5.4 / §5.5 已冻结）、T5/T6 替换（CAMI2 / QfO）、工具链许可（零 GPL 可行）、代码许可（Apache-2.0 + 内容 CC BY 4.0）。

> ⚠️ **本节在 2026-09 做过一次全面核对。** 此前 12 项里有 **6 项其实早已完成**
> 却仍标着未勾选，而"D2 开工前"这个时限也早已过去。
> **一份过时的待办清单比没有清单更糟** —— 它会让人去重做已经做完的事。
> 现在每一项都注明**证据**（文件存在 / 门禁在 Dockerfile 里 / 审计器判定）。

**已完成（附证据）：**

- [x] ~~抽查 PMC 样本确认 `license_code` 拼写~~ → `"CC BY"` / `"CC BY-NC-ND"` / `null`（§6）
- [x] ~~确认 S3 匿名读取是否开放~~ → `pmc-oa-opendata` 匿名可列举、可读元数据与正文
- [x] ~~写 `scripts/pmc_ingest.py`~~ → **已落地**（fail-closed：只收 `CC BY`/`CC0`，
      排除 `null`/`is_manuscript`/`is_retracted`，并从 XML 解析 CC BY 版本号）
- [x] ~~确认 GATK4 的两个许可边界~~ → §5.6（含两处自我更正）
- [x] ~~GATK4 相关合规工作~~ → **v1 不打包 GATK4**（§4.4）
- [x] ~~在 DATACARD 里写明"v1 镜像不含 GATK4 及原因"~~ → `docs/DATACARD.md` §5 与 `NOTICE`
      的"刻意不包含的组件"块
- [x] ~~确认 bcftools 未启用 GSL~~ → **镜像构建期门禁 `tasks/T1/scripts/check_no_gsl.sh`**，
      四道检查（动态依赖 / 静态字节 / **行为** / 文件系统），任一失败即中断构建。
      ⚠️ 2026-09 加强：原版只有 `ldd | grep libgsl`，**有三个盲区**（静态链接看不见、
      **39 个插件没扫**、不验行为）。背景是 Debian 元数据声称该包因 GSL 受 GPL 管辖
      （见 `docs/DATACARD.md` §5.2 的四条实证排除）。已做负向测试
- [x] ~~再确认 `hap.py` 的许可~~ → **问题不存在**：`tasks/T1/Dockerfile` 明写
      "只用 vcfeval 评分；刻意不用 hap.py，避免引入 boost 构建链"。
      **镜像里没有 hap.py，所以没有它的许可问题。** vcfeval 的 BSD-2 已核验
- [x] ~~记录 3 项上游不可核实的已知限制并写进 DATACARD~~ → `docs/DATACARD.md` §4.3
      （dbGaP DUA 页 404、EGA 条款 DNS 不可达、GEO 政策页只能读 2024 存档镜像）
- [x] ~~输出 `docs/SAFETY.md` 与 `docs/DATACARD.md`~~ → 均已写出（且由
      `scripts/verify_datacard.py` 逐条核对断言）
- [x] ~~代码许可落地~~ → `LICENSE`（Apache-2.0，正文与 apache.org 官方源**逐行比对通过**）
      + `NOTICE`（第三方组件，分"已核验上游 LICENSE"与"仅有包元数据"两块）

**仍未完成：**

- [x] ~~核验 `samtools` / `bcftools` / `htslib` 的**上游 LICENSE 原文~~ →
      **2026-09 已完成**：按镜像内实际版本（samtools 1.16.1-1、bcftools 1.16-1、
      htslib 1.16+ds-3）逐个 tag 读上游 `LICENSE`，三条链接写进 `NOTICE` ** [A] 块**。
      附带发现 `htslib` 的 `cram/` 是 Modified-BSD-3（不只是 MIT）。
      由 `scripts/verify_notice.py` 强制：[A] 每条必须给出上游出处（含负向测试）。
      **仍留在 [B] 未核验**的只有 OpenJDK 与 Debian userland。
- [ ] **法务确认**：`bwa-mem2` 的 MIT 主张是否覆盖其 GPLv3 时代继承的代码
      （核实前**不得**写"可商用"）。v1 不需要 BWA（T1 预置 BAM），此项只为将来预留
- [ ] **法务确认三项**：① `"镜像内不得含 GPL"` 的语义；② 同上；③ 依赖清单里是否含
      `pmml-evaluator`（**AGPL** —— 注意别与 BSD-3 的 `pmml-model` 混淆）

---

## 13. 当前阻塞项（按"卡住谁"排序）

### 13.1 卡在**人**上：rubric 题的人工复核（24 题）

第三支柱的 24 道题 `review_status=pending`，**在人工复核前不得进入公开榜单**
（审计器 W1 只警告、不致命，但计分入口会检查）。复核表已生成：
`rubric/docs/WHAT_TO_DO_NOW.md` → `rubric/review/REVIEW_SHEET.md`。
填 `rubric/review/review_verdicts.jsonl` 即可推进。

**这道关必须由人过**，不能由我代劳：让我审我自己出的题，
等于用同一套偏见做质检。本轮已经证明了这一点——我的两处错误
（27 篇人类数据全填 true、PMC11900006 误判）**都是别人发现的**。

### 13.2 卡在**两个真人**上：人类天花板 κ

`rubric/` 的核心方法论主张是"**人类之间的一致率是裁判可靠性的上限**"，
因此天花板必须由**两位真人**独立标注产生。一位 AI + 一位真人不是天花板，
是"AI 与人类的一致率"，是另一个量。当前只有 fixture 的合成标注
（天花板 κ 二次加权 0.8415），**必须标注为"流程校准"，不得当作结果发布**。

#### 13.2a 我此前把这道关说得**比实际更死**（本轮更正）

我前几轮反复说"需要两个真人，硬阻塞"。**这对"相对天花板"是对的，
但对"裁判 vs 人类"是错的** —— 后者只需要**一位**真人：

| 想要的量 | 需要几位真人 | 现在有吗 |
|---|---|---|
| **裁判 vs 人类**的一致性（最基本的一个数） | **1 位** | ❌ 一位都没有 |
| 人类之间的天花板（相对值的分母） | 2 位 | ❌ |

所以现状比我说的好一点：**你先标一遍，就能得到一个真实可报的 κ**，
只是它的解释要等第二位标注者到位才能完整（没有分母就不能说"相对天花板是多少"）。

#### 13.2b 更要紧的：**标注工具本身是坏的**（本轮才发现）

说"卡在真人"之前应该先确认"真人来了能不能做"。本轮查了，答案是**不能**：

> `make_annotation_sheets.py` **根本不接受作答输入**。
> 它只从 `--items` 生成标注表，于是标注者看到的是
> 「问题 + 评分标准 + `分数：______`」—— **却没有任何要评的回答**。
>
> rubric 评的是"**某份回答**满足了没有"。没有回答就没法评。
> **那张表是不可用的。**

这个缺陷能一直存在，是因为人工标注这一步**从来没有真正跑过**——
而它又是第三支柱对外声明的硬阻塞。**工具与声明的流程对不上，没人发现。**

连带的第二处不一致：`kappa.py` 的配对键是 `(item_id, criterion_id)`，
即**"一题一答"**的假设；而实际的裁判实验是**一题三答**（浅/中/优）。
两处合起来说明同一件事：这套工具是**为一个从未跑通的流程**写的。

**本轮修的三处（都可复验）：**

1. `make_annotation_sheets.py` **要求 `--answers`**；没有作答就拒绝生成
   （不再产出不可用的表）。标注表里出现【待评的回答】，
   标注单位从 `(题, 标准)` 改成 **`(题, 回答, 标准)`**
2. `kappa.py` 的配对键加入 `answer_id`（缺省值保证旧夹具仍可用），
   条目总分按 `(题, 回答)` 汇总。**新增一条自检用例**：
   同一题 3 份回答必须算 3 个配对 —— 否则别人可以把键改回两元组而自检照样通过
3. **防覆盖保护**：若目标标注文件里已有任何非空分数，重生成**直接拒绝**
   （要覆盖必须显式 `--force`）。人工标注是最贵、最不可逆的一步，
   而重跑一次生成脚本就能清空它 —— 这个损失必须被挡住

**并且把量级从"永远不会被做"缩到"一次坐得完"**：
全量是 24 题 × 3 答案 × ~4.2 标准 = **303 个评分点**；
试点（`make_pilot.py`）取 `R-0001..R-0006` = **72 个**。

> 试点**不按"哪几道好看"选样**，就取题号最前的 6 道。
> 若专挑判别力好的题，算出的 κ 会偏乐观，而试点的目的恰恰是在投入全量之前
> 发现"这套标准到底能不能被人一致地读"。**为结果好看而选样，正是本项目一直在避免的事。**

#### 13.2c 补上"这条链从来没被跑过"这个根因

13.2b 修了工具，但**修工具不等于以后不会再坏**。真正的根因是：
**这条链从来没有任何东西在跑**。工具写了、文档写了、对外声明它是硬阻塞，
却没有一次端到端运行去验证"人来了能不能做"。

所以新增 `rubric/scripts/test_annotation_chain.py`，并用**合成标注者**把整条链跑一遍：

```
题面 + 作答 → 生成标注表 → 合成 A/B 填分 → --validate → kappa.py → judge_eval.py
```

它已进 `run_all_checks.py` 的固定环节（第 2b 步）。**它不证明标注质量，只证明管道通** ——
合成标注者的分数取自裁判本身、**不是人类数据，不得引用**。

并做了**负向测试**：把生成器改回原来的坏行为（模板丢掉 `answer_id`、
表内不写回答），链路演练会以退出码 1 失败并指出"标注表里含 0 段待评回答"。
**一个在工具坏掉时仍然报成功的测试是摆设**，所以这一步必须验。


### 13.3 ~~卡在上游：源文截断~~ → **已修复**

原问题：`rubric/items/sources/` 下 24/27 篇 `.txt` 被截断在 20,000 字符
（`fetch_source_text.py` 的旧默认值），本轮的人类数据误判正由此产生。

修复：
- `fetch_source_text.py` 默认 `--max-chars 0`（不截断），新增 `--force`，并在
  manifest 里记录 `chars_total` / `chars_saved` / `truncated` —— **截断这件事本身
  从此是记录在案的，不再是静默的**
- 27 篇全部重取：1,466,549 字符（原约 540,000），`truncated` 全为 false，官方 md5 27/27 齐全
- `classify_human_data.py` 增加**截断守卫**：发现截断就拒绝下结论并提示先取全文
- 截断版已备份至 `items/sources_trunc20000/` 以便对照

**重验结果（全文下、而不是截断文本下）**：
- 反抄袭（12 词连续重合）：**0 命中**，覆盖 1.47M 字符（原先只有 ~540K，任何
  落在 20,000 字符之后的整句抄录都是**看不见的**）
- 数字保真（`check_numeric_fidelity.py`）：核对 **155 个数字，0 个未找到**，
  1 个正确标注为四舍五入（题面写"约 5900"，原文是 5903）
- 人类数据裁决：用**方法学段落**复核 8 个争议条目，全部与裁决一致
  （见 `human_data_basis.json` 的 `_fulltext_verification`）

### 13.3b 新增：不依赖人类标注的效度证据（裁判区分度）

`judge_discrimination.py`：同一裁判对同一题的**三档答案**（浅/中/优）是否给出
递增分数。设计上堵住三个假阳性来源：

1. **档位对裁判不可见** —— 输入文件名是散列 ID（`make_blind_judge_set.py`），
   否则测的是"裁判会不会顺着文件名给分"
2. **答案对评分标准不可见地写成** —— 写答案的子agent 只拿到题面，没拿到 criteria
   （`make_blind_items.py`），否则测的是"裁判会不会照着得分点打分"
3. **同题三档由同一批裁判评** —— 否则差异可能来自裁判间方差

局限（必须随结果一起报告）：答案由模型生成、非真实考生作答 → 这是**区分度**证据，
不是**效度**证据；写答案与当裁判是同一模型家族 → 存在自我偏好偏差。
**它只能证明"能分开"，不能证明"分得对"。**

**已跑完的结果（24 题 / 101 条标准）**：

| 指标 | 值 |
|---|---|
| 归一化得分 浅 / 中 / 优 | 0.393 / 0.686 / 0.886（满分 1.0） |
| 优 − 浅 差距 | 0.494（归一化） |
| 整题严格单调（浅<中<优） | 20/24 = 83.3% |
| 至少 优>浅 | 23/24 = 95.8% |
| 唯一反向的题 | R-0016（浅 1.25 > 中 1.00 = 优 1.00） |

### 13.3c 为什么要跑第二轮：**没有重复测量就分不清"标准坏了"和"这次手抖了"**

第一轮标准级诊断给出 11 条"饱和"（三档同分）+ 13 条"反向"（浅档不低于优档），
看起来像是 rubric 大面积失效。但每个 (题, 档) 只有 **1 次**判定——单次抖动与真实缺陷
**无法区分**。

于是做了第二轮独立评判（另起 6 个裁判，同输入、同协议，明令禁读第一轮结果与映射表）：

| 指标 | 值 |
|---|---|
| 二次加权 κ（裁判自己 vs 自己） | **0.9494**（Po 0.9686 / Pe 0.3805） |
| 完全一致 | 265/303 = 87.5% |
| 相差 ≤1 分 | 303/303 = 100% |
| 平均绝对差 | 0.1254 分（满分 2） |

**两组数字必须一起读**：只看区分度像"rubric 失效"；只看重测像"裁判很稳"。
合起来才是结论——**裁判稳定，所以那些失败不是手抖，是标准本身判不动**。
第二轮一筛：第一轮的 24 条里只有 **18 条复现**，另 13 条是噪声。

**18 条确认真缺陷**（9 饱和 + 9 反向）已落成可执行的
`rubric/docs/RUBRIC_V1.1_REVISION_LIST.md`（由 `make_revision_list.py` 生成，
改了数据就重新生成，不手改）。含 6 类**结构性**写法缺陷（会在新标准里复发），
每类都标注了有多少个裁判**独立**提出：

1. **合取式 2 分锚点没有部分给分规则**（9/12 裁判独立提出，稳定性损失头号来源）
2. **跨标准重复计分**（6/12）
3. **1 分锚点用否定式清单而非正面描述**（7/12）
4. **锚点要求题面里推不出的事实**（4/12）
5. **"若只能补做一项"的 0 分档不可达**（4/12）
6. **枚举式锚点**（5/12）

**一条重要的负面结论**：裁判的**自一致性 κ（0.9494）高于** fixture 上测得的
**人类之间天花板 κ（0.8415）**，也高于裁判与人类的 κ（0.7091）。
这不出人意料——同一个模型、同一份提示词，当然比自己与别人之间更一致——
但它正是**为什么自一致性不能当作效度**的直接证据。一个比人类彼此更"稳定"的裁判，
报告的是它自己的确定性，不是它判得对。

⚠️ 注意可比性缺陷：0.9494 来自**真实 24 题**，0.8415 / 0.7091 来自
**合成 fixture**。跨数据集比较只能当作**提示**，不是严格对照。要在同一题集上
比较，必须先取得真实的人类双标注（§13.2）。

### 13.3d 改写 v1.1，并**实测改写到底有没有用**

诊断出 18 条确认缺陷 + 6 类结构缺陷后，按 `rubric/docs/REVISION_RULES_V1.1.md` 重写了
评分标准（**96/101 条被改动**），然后做了一次**受控前后对照**：

> **同一批 72 份答案**（写答案时看不到任何一版的标准）、同一批题目，
> 唯一变量是 criteria 的锚点结构 → 差异可归因到改写本身。
> 两版都跑**两轮**评判，否则会把"标准坏"和"这次手抖"混在一起比。

结果（`rubric/docs/V1.0_VS_V1.1.md`，由 `compare_rubric_versions.py` 生成）：

| 指标 | v1.0 | v1.1 | 变化 |
|---|---|---|---|
| **确认缺陷标准数** | 18 | **16** | −2 |
| 　饱和 | 9 | 8 | −1 |
| 　反向 | 9 | 8 | −1 |
| 至少 优>浅（整题） | 95.8% | **100%** | +4.2 |
| 严格单调（浅<中<优） | 83.3% | 79.2% | **−4.1** |
| 裁判重测 κ | 0.9494 | 0.9636 | +0.014 |
| 两次完全一致 | 87.5% | 91.1% | +3.6 |

拆开看：**修好 7 条 · 仍在 11 条 · 新引入 5 条**。

**结论必须照实说：这次改写只带来了很小的净收益，而且有代价。**
改动了 96/101 条标准，净效果只有 −2 条缺陷；同时**新造出 5 条缺陷**。
"我们重写了 rubric 并改进了它"是**不成立**的说法。

**为什么改写效果有限（这是比数字更重要的发现）**

两轮裁判的独立反馈高度一致地指向同一个根因，而改写**没有解决它，只是把它挪了个位置**：

> 绝大多数回答会**点出缺陷**，但不会**写出这个缺陷的后果**。而几乎每条标准的
> 2 分锚点都要求"指出 X **并**说明 X 的后果/方向"。于是这类回答两档都不落，
> 只能按"不确定给低分"压到 1。

v1.1 把合取式锚点从「X 且 Y 且 Z」改成了「核心论断 + 至少 N 项」——
**但合取并没有消失，只是下沉了一层**：现在变成「核心论断 **且** N 项支撑」。
所以同类回答依旧卡在 1 与 2 之间，只是卡的位置换了一处。

**真正的修法只能在两处之一**（这是留给下一个版本的决策，不是本轮能自动解决的）：
1. **改题面**：明确要求回答"说明该缺陷如何影响结论"——让后果成为题目的一部分；
2. **改评分**：明确写"用 rubric 的术语点出该偏倚/来源即计 2，不要求另述后果"——
   承认点名本身已是能力证据。

另有一处**我自己引入的缺陷**：为落实 R4（防跨标准重复计分），我给多条
"补做一项实验"的标准加了注「缺陷识别计入 c1–c3，本条只评所选方案本身的针对性」。
裁判指出这个注**与同一条锚点里"方案须直接针对①中认定的最弱环节"自相矛盾**——
要判断方案是否对准①，恰恰需要那个被划出去的缺陷识别。这很可能是
v1.1 新增 5 条缺陷的部分来源。

### 13.3e 我上一轮的归因被打脸了：分歧并不主要在"后果分句"

上一节我写"根因是回答点出缺陷却不写后果"。那是**从 12 个裁判的主观反馈里读出来的**，
不是测出来的。所以我把它测了一遍（`boundary_analysis.py`）：

| 版本 | 分歧总数 | 0↔1 | 1↔2 | 跨两档 | 1↔2 占分歧 |
|---|---|---|---|---|---|
| v1.0 | 38 | 14 | 24 | 0 | 63.2% |
| v1.1 | 27 | 12 | **15** | **0** | **55.6%** |
| | | | | | |

结论：**"后果分句"只解释了 55.6%**，另有 **44.4% 落在 0↔1**——
即"完全没提到"与"提到了但很浅"之间。这部分**改题面救不了**。

我上一轮说"真正的修法只有两条（改题面 / 改锚点）"，**这个说法是错的**：
它只覆盖了大约一半的问题。

一个附带的好消息：**跨两档翻转是 0**。裁判从不会把同一份回答一次判 0 一次判 2，
量表虽然粗，但没有失控。

### 13.3f "那把量表改粗成二档不就好了"——测了，不行

既然中间那档最难切，自然会想：三档是不是不如二档可靠？
这个问题**不需要新数据**：同一个裁判给的 0/1/2 事后合并成二档，重算一致性即可
（`scale_reliability.py`）。

| 编码 | v1.0 完全一致 / κ | v1.1 完全一致 / κ |
|---|---|---|
| 三档 0/1/2（二次加权） | 87.5% / **0.9494** | 91.1% / **0.9636** |
| 二档A「有没有谈到」 | 95.4% / 0.8268 | 96.0% / 0.8374 |
| 二档B「有没有做全」 | 92.1% / 0.8400 | 95.0% / 0.8992 |

**三档更可靠，两版都是。** 而且这张表正好演示了一个陷阱：
二档的表面一致率（96%）**高于**三档（91%），看一致率会以为二档更好；
但 **κ 反而掉到 0.8992**——因为合并档位把分歧折进了同一档，
一致率是虚高的，κ 扣掉"碰巧一致"后才露出真相。

**所以"改粗量表"这个看起来很自然的修法被否掉了。** 三档保留了真实信息，应当保留。

### 13.3g 下一步：按**边界类型**分别处理（已落进改写清单）

既然两类边界各占一半，改法也必须分开——而这件事**不需要人来判断**，测出来是哪类就改哪类。
`make_revision_list.py` 现在会为每条漂移标准标注**漂移边界**：

- **标 `1↔2` 的** → 改 1/2 档锚点：要么明确"点名即满分"，要么要求写后果。
  这两种写法**二选一**，不能含糊（含糊正是漂移来源）。
- **标 `0↔1` 的** → 改 0/1 档锚点：把 0 档从"未提及 X"这种纯否定，
  改成"什么样算没提到"的正面描述。**改题面在这里无效。**

### 13.3h 我上一轮的承诺（"两种写法各测一遍"）建立在一个被推翻的前提上

上一节结尾我说：会把 `1↔2` 的两种写法各测一遍，用数据替人选。**这个计划作废了**，
因为在动手前先验了一个前提：**改措辞对一条标准到底有没有用？**

答案要分情况，而分数本身看不出来。分数只告诉我"中档和优档同分"，
但**原因有三种**，处置完全不同：

| 情形 | 现象 | 改措辞有用吗 |
|---|---|---|
| (a) 中档泛泛、优档点出了缺陷 | 两档写得**不同** | ✅ 有用（1 vs 2 能分开） |
| (b) 两档都点出了缺陷、都没写后果 | 两档写得**相同** | ❌ 没用（改完一起升降，还是同分） |
| (c) 两档表现相同且都做对了 | 标准**太容易** | ❌ 没用（除非提高门槛或删除） |

判据不在分数里，**在裁判写的 evidence 里**——它逐条记录了给分时回答写了什么。
于是把所有 16 条缺陷的 evidence 并排读出来（`evidence_inspect.py`）：

| 处置 | 条数 | 标准 |
|---|---|---|
| **改措辞多半无效** | 7 | R-0005/c4、R-0006/c3、R-0010/c3、R-0015/c1、R-0017/c3、R-0020/c4、R-0024/c1 |
| **测试对该条不适用** | 2 | R-0011/c4、R-0012/c4 |
| 可能有效 | 2 | R-0007/c3、R-0023/c4 |
| 需人工读原文 | 5 | R-0002/c2、R-0003/c3、R-0008/c2、R-0016/c3、R-0020/c3 |

**所以"把两种写法各测一遍"是错的**：在 7 条上两种写法结果必然相同
（两档回答写得一样），测了也分不出高下——那是对噪声调参。

### 13.3i 我的区分度检验本身有设计缺陷（这条最重要）

上表里有 2 条判成"**测试对该条不适用**"，原因值得单独讲：

> R-0012/c4 的**浅档答案拿了 2 分**（它写了"横断面设计只能说明相关，不能说明因果"），
> 而**优档答案拿 0 分**（"未涉及"）。R-0011/c4 同型。

这不是标准坏了，是**我的答案档位标签对它不适用**：
浅/中/优是子agent 对**整份答案**的总体质量判断，**不是逐条标准的**。
一份总体平庸的答案完全可能在某一条标准上答得比"优秀答案"好。

后果有两层：

1. **`weak < medium < strong` 不是一个合法的逐条效度判据。** 它默认了档位排序在
   *每一条*标准上都成立，而这个前提是假的。
2. **8 条"反向"里有一部分是我的检验误报，不是 rubric 缺陷。** "饱和"类不受影响
   （三档同分说明该条**确实**不追踪总体质量），但"反向"类必须逐条看 evidence 才能定性。

**修法**：区分度结论必须**附 evidence 复核**，不能只看分数排序。
`defect_triage.py` + `evidence_inspect.py` 就是这个复核，现在是一键流程的一部分。

### 13.3j 这个循环到此为止：合成答案能给的信号已经取尽

把上面全部合起来看，剩下能靠"改措辞 + 合成答案"拿到的收益已经很小：

- 16 条确认缺陷里，**7 条改措辞无效**（回答在那一维上没有差别）
- **2 条是我的检验误报**（档位标签不对齐）
- 只剩 **2 条**（R-0007/c3、R-0023/c4）明确值得改措辞
- 另 5 条要人工读原文才能定性

**根本原因**：合成答案只能检验"标准能否追踪**总体质量**"，
而一份 rubric 的效度最终是"专家会不会这么判"——那是**人类判断**，
不是总体质量排序能替代的。所以真正的下一步是 §13.2 那条（两个真人标注），
它卡在人上；在拿到它之前，继续在这套合成答案上调 rubric 是**边际收益递减**。

### 13.3k 又推翻了 §13.3j —— 而且这次是**替 rubric 平反**

§13.3j 我下了结论"16 条确认缺陷里 9 条改措辞无效，标准考错了东西"。
那是从一个**有缺陷的检验**里推出来的。所以我换了个设计重测。

**新设计：操纵检验（manipulation check）**

对每条标准 X，拿同一份答案做**最小改动**得到两份：
A+ 让 X 要求的要素**明确存在**；A− **只把该要素拿掉**，其余逐字不动。
（改动幅度实测：A+ 比底本 +3%~+32%，A− 比底本 −12%~+1%，两组只差那一处。）
然后盲评两轮，看 A+ 是否 > A−。

这个设计**天然逐条**，不依赖任何整体质量标签，从根上消掉了 §13.3i 那个混淆。
关键是同时抽 **10 条两轮都判 healthy 的标准做对照**——先证明检验能区分好坏，再用它定罪。

**结果（26 条标准 × 2 变体 × 2 轮 = 104 次评判）**：

| 组 | 条数 | 敏感 | 不敏感 | 敏感率 |
|---|---|---|---|---|
| 对照（healthy） | 10 | 9 | 0（1 不稳） | **90%** |
| 目标（"确认缺陷"） | 16 | 15 | 1 | **94%** |

**目标组与对照组敏感率基本相同。**

这意味着：**那些标准没有坏。** 当差异被造得明确时，裁判能稳定地把
A+ 与 A− 分开（15/16）。所以之前那些"饱和/反向"，**不是标准判不动，
而是我那套合成答案在这些维度上本来就没有差别**——测出来的是**答案集的性质**，
不是 rubric 的性质。

**连带结论（必须写清，因为它推翻了本文件前面几节）**：

1. **§13.3j 的"9 条改措辞无效 → 标准考错维度"是误判。** 准确说法是：
   *我的浅/中/优答案在那个维度上写得一样*，与标准好坏无关。
2. **v1.1 那次大改写（96/101 条）基本是不必要的。** 它没带来增益，
   正是因为要修的东西不在标准里。这不代表改写"有害"——它的净效果近似于零，
   但花掉了一轮多的工作量。
3. **§13.3h 的"缺陷分诊"整表需要重读**：它的输入（区分度结果）本身测错了东西。
4. **真正坏掉的只有 1 条**：R-0015/c1——即使把差异造得明确，两轮都判 2 vs 2，
   它**在任何答案上都给满分**，是货真价实的失效标准。

**因此：这套 rubric 的可用性比我前面几轮报告的要好得多。**
24 道题、101 条标准里，能被证伪的只有 1 条。剩下的问题**不在标准**，
而在"没有真人标注去确立天花板"（§13.2）。

**教训（比结论更重要）**：
- 一个检验的**输入**如果是错的，它的结论再精致也是错的。§13.3i 那个混淆
  （档位标签 ≠ 逐条维度）一直写在检验里，我却先用它给 9 条标准定了罪。
- **必须先证明检验能区分好坏（对照组），再用它定罪（目标组）。**
  这次对照组 90%、目标组 94%——两个数一摆，结论就自己反过来了。
- 我连续三轮给出了三个不同的结论（13.3h 改措辞、13.3j 改维度、13.3k 标准没坏）。
  前两个都是从一个未经验证的检验里推出来的。**这不是"迭代逼近"，是没做对照。**

### 13.3l 收口：**正式版是 v1.2，不是 v1.1**

**v1.0 的 101 条标准里，只有一个缺陷是"不依赖任何裁判就能核验"的**：

> `R-0020/c1` 的标准正文写"文中 P 值在 0.01–0.06 之间"，
> 而题面从头到尾**没给任何 p 值** → 裁判无法核实该要件 → 该档不可判。
> （次要问题：该论文实际用了 **Holm–Bonferroni** 校正，
> 所以原表述暗示的"未校正"本身也与事实不符。）

这是 `check_anchor_grounding.py` 检出的：把标准**正文与三档锚点**里的数字抽出来，
逐个到题面里找。**这类检查不需要跑模型、不需要裁判、成本近零**，
却能判定"这一档到底能不能判"——它比前面所有基于裁判的检验都更硬。

**因此 v1.2 = v1.0 + 这一处修复，别的都不动。**

| 版本 | 相对 v1.0 的改动 | 依据 | 状态 |
|---|---|---|---|
| v1.0 | — | — | 原始版 |
| v1.1 | **96 条** | 区分度检验——**该检验已证明测错东西**（§13.3i/§13.3k） | ⛔ **已废弃** |
| **v1.2** | **1 条** | `check_anchor_grounding.py`（可核验） | ✅ **正式版** |

**为什么不用 v1.1**：它带着 96 处未经验证的修改。一份以"可证明没编造"为卖点的基准，
**自己带着 96 处无证据的改动发布，本身就是不诚实**。v1.1 里确实有少数改动是对的
（R-0020/c1 的 R2 修复、以及若干 R4 跨标准重复计分的归属注记——后者来自裁判的
**定性**反馈，不是那个失效的检验），但没法把"对的"从"多余的"里干净地筛出来，
所以取**最小改动**这条更保守的路。

**已知但未处理的问题（留给有证据时再动）**：
- 裁判定性指出多条标准之间**跨标准重复计分**（同一句同时满足两条）。
  v1.1 用注记处理过，但那批改动整体不采信，所以这个问题**仍然存在**。
- `R-0015/c1` 在操纵检验里判为"不敏感"，但**这是变体构造的限制而非真实缺陷**：
  该要素贯穿整份答案，A− 无法在不阉割答案的前提下把它拿掉（变体作者已明确说明）。
  故**不改动**。
- `check_anchor_grounding.py` 只抓**数字型**要件。文字型要件
  （如"未按泪液流率归一化"）抓不到，仍需人工复核。

**给下游一句话**：读 rubric 请读 `items/items_v1.2.jsonl`。
`items_v1.1.jsonl` 保留仅为审计痕迹，**不要使用**。

### 13.4 仍需**双源确认**的许可（未核实前不得写"可商用"）

- [ ] `bwa-mem2` 的 MIT 主张是否覆盖其 GPLv3 时代继承的代码
- [x] ~~`samtools` / `bcftools` / `htslib` 上游 LICENSE 原文~~ → **2026-09 已核验**
      （按镜像内实际版本逐个 tag 读原文；`NOTICE` [A] 块给出链接；由
      `scripts/verify_notice.py` 强制 [A] 条目必须带出处）。
      GSL 那半也已从"只看 `ldd`"升级为**四道检查的构建期门禁**
      （`check_no_gsl.sh`，含行为验证与负向测试，见 §12 与 `DATACARD` §5.2）
- [x] ~~`hap.py` 与 `vcfeval` 的许可~~ → **`hap.py` 不在镜像里**
      （Dockerfile 明写"只用 vcfeval 评分"），所以它没有许可问题；
      `vcfeval` 属 RTG Tools，BSD-2 已核验上游 LICENSE 原文

### 13.5 法务确认三项（我不能替法务下结论）

① `"镜像内不得含 GPL"` 的语义（bash/coreutils 本身就是 GPL，字面不可能满足）；
② `bwa-mem2` 见上；③ 依赖清单是否含 `pmml-evaluator`（**AGPL**，勿与 BSD-3 的 `pmml-model` 混淆）。
