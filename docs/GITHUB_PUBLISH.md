# 发布到 GitHub —— 操作手册

> 目标：把 `bio-eval/` 这个**目录**变成一个公开的 GitHub 仓库。
> 本手册按 Windows + PowerShell 写。**先读完第 0 步再动手。**

---

## 0. ⚠️ 为什么这件事要先建检查再动手

推到 GitHub 与传到 HF 有一个共同点：**历史不可撤销**。
即使随后 `git rm` 并强推，内容仍可能留在 fork、缓存、以及别人已经 clone 的副本里。

而本仓库里**确实存在"绝不能公开"的东西**：

| 路径 | 内容 | 后果 |
|---|---|---|
| `tasks/T2/data/truth.jsonl` | **4,726 条答案，含全部 937 条轮换池答案** | 一旦公开，「轮换池永不公开」永久变成假话，且它检测过拟合的能力一并作废 |
| `tasks/T2/data/items.jsonl` | 4,726 条题面（含轮换池题面） | 同上 |
| `tasks/T2/data/rotation/` | 轮换池本体 | 同上 |
| `tasks/T1/_data/` | 171 MB 运行期数据 | 体积 + 无意义 |
| `rubric/items/sources/` | **别人的论文全文** | 版权 |

这些路径散在目录树里，而 `git add .` 会**抓走一切**。
所以顺序必须是：**先生成 `.gitignore` 并验证它真的生效，再考虑 `git add`。**

本项目这一轮已经反复讲过同一条：
**不可撤销的操作，要在动手前对它本身建一道检查。**

---

## 1. 生成并验证 `.gitignore`

`.gitignore` **不是手写的** —— 它由 `scripts/not_published.json`
（"什么不该对外"的唯一真源）自动生成：

```powershell
# 仓库根（bio-eval/）
python scripts/generate_gitignore.py
python scripts/generate_gitignore.py --self-test    # 用真 git 验证关键路径确实被忽略
```

`--self-test` 会调 `git check-ignore` 逐条确认，**不是字符串匹配**。
（这一点很重要：第一版自检与生成器共享了同一个错误假设 —— 给文件条目也拼了尾斜杠 ——
于是**自检通过、而 4,726 条答案实际没被忽略**。用真 git 才查出来。）

想亲眼看到它怎么拦人，可以临时把某个关键文件加进白名单再跑 `--check`。

---

## 2. 密钥与本机路径扫描

```powershell
python scripts/scan_secrets.py
python scripts/scan_secrets.py --self-test
```

它查三类：**凭据**（HF token / GitHub PAT / AWS key / 私钥 / 硬编码口令）、
**本机绝对路径**、**邮箱**。输出必须是：

```
✅ 未发现任何凭据
✅ 未发现本机绝对路径
```

> 检查器自己也会被扫。第一版把假 token 写在 `scan_secrets.py` 里当自测样本，
> 于是全仓扫描每次都报"6 处凭据" —— **检查器把自己变成了假警报源**。
> 现已用运行时拼接绕开，并把本文件加入 `SELF_SKIP`。

---

## 3. 清室检验：确认"只给会发布的那部分"也能跑通

这是本仓库最贴近"第三方 clone 下来会怎样"的检查：

```powershell
python scripts/clean_room_check.py
```

它只复制**会被发布的文件**到临时目录，并在那里重跑两套检查。
失败通常意味着**某个脚本依赖了一个不发布的文件** —— 那正是第三方会卡住的地方。

---

## 4. 初始化仓库并**检查暂存区**（这一步是关卡）

```powershell
# 仓库根（bio-eval/）
git init
git add -A

# ⚠️ 关卡：以下五个必须全部是 False
git diff --cached --name-only | Select-String -Pattern "rotation|data/truth|data/items|data/audit"
# 期望：无输出（或只有 *.py 脚本名里含 rotation 的那两个 —— 那是文件名，不是数据）
```

再确认体积合理：

```powershell
git diff --cached --name-only | Measure-Object        # 约 690 个文件
```

**如果上面那条 grep 打出了 `tasks/T2/data/truth.jsonl` 这类路径，立刻停止**，
回到第 1 步检查 `.gitignore`，并 `git rm --cached -r .` 后重来。

---

## 5. 提交

```powershell
git config user.name  "zwb-tj"
git config user.email "<你的 GitHub 邮箱>"     # 不要写真实私人邮箱到公开仓库里
git commit -m "VeriBench-Bio v0.2: T1 + T2 shipped, rubric structural pass"
```

建议在首个提交里就把这件事说清楚（本仓库的诚实风格）：

```
VeriBench-Bio — 一个针对"可信性"而不是"能力覆盖"的生信基准。

状态（照实说）：
- T1 变异检出：已完成并实测（五次独立重跑得分完全一致）
- T2 变异解读：本地完成并实测；**尚未上传 HF**（仓库已建，storage 0 B）
- rubric 第三支柱：结构完成，**人类天花板尚未取得**
- 真实榜单：0 条

本仓库里刻意保留了纠错记录（SPEC §3.1 等），
因为"只展示结论、不展示纠错过程的基准，无法让第三方判断它有多可信"。
```

---

## 6. 建远端并推送

先在网页建**空**仓库（**不要**勾 "Add a README" / ".gitignore" / "license"，
否则远端会先有提交，推送时要额外处理）。

```powershell
git branch -M main
git remote add origin https://github.com/<用户名>/veribench-bio.git
git push -u origin main
```

---

## 7. 推送后验证（别跳过）

**① 在网页上确认**：文件数约 690；`tasks/T2/data/` 下**只有** `check_no_leakage.py` /
`build_t2.py` / `T2_DATASET_CARD.md` / `split_public_rotation.py` 等脚本，
**没有** `truth.jsonl` / `items.jsonl` / `audit.jsonl`。

**② 换个目录 clone 一份，在新克隆里跑全套检查**（这才是真正的"第三方复现"）：

```powershell
git clone https://github.com/<用户名>/veribench-bio.git "$env:TEMP\bb-verify"
cd "$env:TEMP\bb-verify"
python run_all_checks.py
```

预期：**大部分通过**，少数因缺生成物而 `SKIP`（这正常 —— 数据要自己取）。
凡 `❌` 都要查：它意味着第三方 clone 下来会卡住。

**③ 确认 GitHub 的 secret scanning 没有告警**（仓库 Settings → Security）。

---

## 8. 之后的常规动作

- 每次改完 `scripts/not_published.json`，都要 `python scripts/generate_gitignore.py` 重新生成
  （`--check` 模式会在过期时报错，可以挂在 CI 里）
- 提交前跑 `python run_all_checks.py`；发布前跑 `--clean-room`
- **`git add .` 之前永远先 `git status --short` 看一眼** ——
  这是最后一道、也是最便宜的一道防线

---

## 9. 一句话

**HF 上传传错会把答案公开；GitHub 推送传错会把答案永久公开。**
两者的差别只是"能不能挽回"。所以这两件事的第 0 步都不是操作，而是**检查**。
