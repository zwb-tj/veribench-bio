# 公开自助榜

> **状态：已就绪，但尚未启用。** 两个数据集仓库在 Hugging Face 上仍是 **Private**，
> 所以现在没有人能提交。等仓库转公开，把提交放到 `submissions/` 即可。

---

## 一、先讲清楚这个榜**不做什么**

**它不声称"已验证分数"。**

自报的分数，在不重跑的前提下**无法验证** —— 这是事实，不是我们偷懒。
竞品里已经有反例：`bioagent-bench` 的作者自承真值不敢保证，
那是"**要你信**"；本项目不做那种榜。

我们换一条路：**不要求你信，而是让你能查**。

| 榜单不做 | 榜单做 |
|---|---|
| ❌ 声称分数经过验证 | ✅ 明确标注每条为 `self_reported_unverified` |
| ❌ 只收一个分数 | ✅ 收下**复现所需的一切**：数据哈希、镜像 digest、工具链版本、逐类结果 |
| ❌ 拒绝别人复核 | ✅ 任何人拿同样的数据与镜像都能自己重跑并核对 |

所以这个榜的真正价值不是排名，而是**每一条都留下了可复查的痕迹**。

## 二、会被自动检查的四件事

`leaderboard/verify_submission.py` 对每份提交做**内部自洽**检查（不重跑）：

1. **分数能由逐类结果复算出来** —— `score == mean(F1_snp, F1_indel)`。
   这一条挡不住"没跑就报分"，但能挡住"分数与详细结果对不上"（算错或手改）。
2. **数据哈希与本仓库锁定的 manifest 一致** —— 确认大家用的是同一份数据，
   而不是自己改过的版本。
3. **提供了镜像 digest** —— 没有它，别人无法用同一个环境复现。
4. **运行时长在预算内** —— 各任务 1800 秒（SPEC §4.1 的"30 分钟 CPU-only"）。

任一条不过 → **拒绝**。通过 → 标 `internally_consistent_unverified`。

## 三、提交格式

放一个 JSON 到 `submissions/<任务>-<你的标识>.json`：

```json
{
  "task_id": "T1",
  "submitter": "你的名字或组织",
  "model": "你用的模型/方法名",
  "result": { /* 跑完任务后生成的 result.json，原样贴进来 */ }
}
```

`result` 就是 `tasks/T1/run.sh` 跑完后产出的 `result.json`（内容见
`tasks/T1/baseline/freebayes_result.json`）。它必须包含：

| 字段 | 为什么必须有 |
|---|---|
| `score` | 成绩本身 |
| `metric` | 说明这个分数是什么量（如 `macro_f1_snp_indel`） |
| `per_type` | 逐类结果；**脚本要靠它复算 score** |
| `manifest_hash` | 确认用的是同一份数据 |
| `image_digest` | 确认用的是同一个环境 |
| `wall_clock_sec` | 确认没超预算 |
| `toolchain` | 别人要知道你用了什么 |
| `problems` | 必须为空；有问题的运行不该当成绩提交 |

## 四、怎么产生自己的 `result.json`

```bash
cd bio-eval/tasks/T1
bash data/prepare_data.sh                 # 取数据（会校验 sha256）
docker build -t veribench-bio/t1:dev .
bash run.sh                               # 跑任务并评分 → _runs/result.json
```

## 五、榜单本身

`results.jsonl`：一行一条，由 `verify_submission.py --json` 的输出追加而成。
**当前是空文件（0 字节）**，因为还没有公开数据可供提交 —— 空是这个阶段的正确状态，
不是"忘了写"。

一行的形状（**格式说明放在这里，不放文件里** —— 在 JSONL 里塞注释行会破坏逐行解析）：

```json
{"submission": "submissions/T1-xxx.json", "task_id": "T1", "submitter": "…", "model": "…",
 "score": 0.84655, "metric": "macro_f1_snp_indel",
 "image_digest": "sha256:c33862bb…", "manifest_hash": "fa025875…", "wall_clock_sec": 55,
 "status": "internally_consistent_unverified",
 "verification_scope": ["检查了提交内部自洽（分数可由逐类结果复算）",
                        "检查了数据哈希与本仓库锁定的 manifest 一致",
                        "检查了镜像 digest 与运行时长字段存在",
                        "**未**重跑 —— 自报分数在不重跑的前提下无法验证"],
 "problems": []}
```

每条记录都带 `status` 与 `verification_scope` —— 后者逐条列出"查了什么、没查什么"，
所以读者不会误以为"通过校验 = 分数可信"。

## 六、T7/T8 若将来加入：**必须单独分区**

它们没有官方真值，只有"某个锁定版本的参考实现输出"，
`truth_type=reference-implementation`。对外只能描述为**可复现性**，
**绝不与 T1/T2 的准确率榜混排**。参照实现必须唯一锁定 ——
`kallisto ≠ salmon`，两者输出数值不可互换。

## 七、这个榜还没有的部分（照实说）

- **没有真实条目。** 数据集未公开，没人能跑。
- **没有自动提交入口。** 现在是收 PR；没有服务端。
- **没有防重复提交的机制。** 同一个人交多份只靠文件名区分。
- **没有对"同一模型换皮重复提交"的检测。** 这是所有自助榜的通病，我们没有解决它，
  只是把每条的证据留全，让人能自己看出来。

后面两条不是"以后再说"，是**已知的、当前未解决**的问题。
