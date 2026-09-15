# 把 T2 数据集上传到 Hugging Face —— 操作手册

> T1 的手册见 `HF_UPLOAD.md`。T2 的流程相似，但**有一个必须读懂的区别**（见第 0 步）。
> 本手册按 Windows + PowerShell 写。

> ### 本手册里的路径都是**相对仓库根**的
> 除第 0 步的"致命不对称"那一节外，命令一律假设当前目录是**仓库根**（`bio-eval/`）：
>
> ```powershell
> cd <你 clone 下来的路径>\bio-eval     # 例如 D:\work\veribench-bio\bio-eval
> ```
>
> 早期版本写死了作者的绝对路径 —— 那让命令在别人机器上必然失败，
> 也把作者的目录结构写进了公开仓库。现已改为可移植写法
> （由 `scripts/scan_secrets.py` 的"本机绝对路径"一类检查守着）。

---

## 0. ⚠️ 先读懂：T2 的上传集有一个"致命的不对称"

T2 的 `tasks/T2/data/` 下有**两组**看起来很像的数据：

| 路径 | 条数 | 上传？ |
|---|---|---|
| `tasks/T2/data/public/` | **3,789** | ✅ **只传这个** |
| `tasks/T2/data/rotation/` | 937 | ❌ 永不公开（用于检测过拟合） |
| `tasks/T2/data/`（全量） | **4,726** | ❌ **含轮换池 937 条的题面与答案** |

**`public/` 与上一级目录只差一个路径段。** 一条手滑的
`hf upload zwb-tj/<repo> data .` 会把全部 937 条轮换池的答案公开 ——
而且**不可撤销**：数据一旦公开过，"轮换池从未发布"这句话就永远不再成立，
它对"是否有人在公开集上过拟合"的检测能力也一并作废。

**所以上传前必须先跑预检**（它会逐文件列出、并拦住任何含轮换池内容的文件）：

```powershell
# 在仓库根（bio-eval/）执行
python scripts/verify_upload_preflight.py --dir tasks/T2/data/public
```

预期输出：列出 4 个文件（`items.jsonl` / `truth.jsonl` / `audit.jsonl` / `README.md`），
每个都标注"不含轮换池 id ✅"，最后一行是
`✅ 上传集预检通过`。**不是这个结果就不要继续。**

想亲眼看到它怎么拦人，可以故意指向错误的目录：

```powershell
python scripts/verify_upload_preflight.py --dir tasks/T2/data
# → ❌ 4 处问题 —— **不要上传**：… items/truth/audit 各含 937 条轮换池 id
```

---

## 1. 现状（2026-09 实测）

| 项 | 状态 |
|---|---|
| HF 仓库 | `zwb-tj/biobench-lite-t2-acmg-variant-interpretation` **已创建** |
| 仓库内容 | **空**（`hf repo list` 实测 `storage = 0 B`） |
| Visibility | Private |
| 待上传 | `tasks/T2/data/public/` 的 4 个文件（约 4.9 MB） |

确认一下（不需要 token 也能看到自己的仓库列表）：

```powershell
hf repo list --repo-type dataset
```

T2 那一行的 `STORAGE` 应为 `0 B`，上传后会变成约 `4.9 MB`。

---

## 2. 确认已登录

```powershell
hf auth whoami
```

没登录就 `hf auth login`（token 需要 **Write** 权限）。

---

## 3. 上传

> ⚠️ PowerShell 里 `<` 是保留的重定向符，**不要用 `<用户名>/<仓库名>` 这种占位写法**，
> 会被整个拒绝执行。把用户名直接写出来。

```powershell
cd "tasks/T2/data/public"

hf upload zwb-tj/biobench-lite-t2-acmg-variant-interpretation . . --repo-type=dataset
```

三个位置参数：`仓库id` `本地路径` `仓库内路径` —— 这里是"当前目录 → 仓库根目录"。

> **为什么在 `public/` 里执行**：这样 `.` 天然就是正确的上传集。
> 千万不要回到 `data/` 去执行。

---

## 4. 上传后验证（**别跳过**，这一步才是产品本身）

**① 条目数对不对**：HF 上应有 4 个文件，`items.jsonl` 与 `truth.jsonl` 各 **3,789 行**。

**② 从 HF 重新下一份，逐字节比对**（这才是真正的验证——证明别人下到的和我们的字节一致）：

```powershell
hf download zwb-tj/biobench-lite-t2-acmg-variant-interpretation --repo-type=dataset `
            --local-dir "$env:TEMP\hf-t2-verify"

# 回到仓库根
cd ../..        # 若当前在 tasks/T2/data/public
python scripts/verify_upload_preflight.py --dir tasks/T2/data/public `
       --compare-with "$env:TEMP\hf-t2-verify"
```

预期最后一行：`✅ 下载回来的那份与本地待上传的**逐字节一致**`。

> **不要把比对写成一段内联 Python。** 本手册第一版给了个 `python -c @"..."@`
> 的写法，而本项目在 Windows/PowerShell 上被内联脚本的引号坑过多次 ——
> **给别人照抄的命令必须在我这里先跑通过**。所以比对逻辑写进了脚本
> （`--compare-with`），它自己也有负向测试（改一个字节就必须报不一致）。

**③ 再验一次"公开集里没有轮换池"**（针对**下载下来的那份**，而不是本地的）：

```powershell
python scripts/verify_upload_preflight.py --dir "$env:TEMP\hf-t2-verify"
```

**④ 确认 Private 时匿名读不到。**

---

## 5. 上传完成后告诉我什么

1. **仓库全名**与 **Visibility**（现在应为 Private；确认无误后再考虑转 Public）
2. 第 4 步 ②③ 的结果
3. `hf repo list` 里 T2 那行的 `STORAGE`

我会据此更新 `docs/DATACARD.md` 与 `README.md`（现在写的是"尚未上传"，
由 `scripts/verify_t2_claims.py` 的 `check_hf_upload_state()` 按实测核对 ——
**你上传之后，那条检查会自动开始要求文档改成"已上传"**）。

---

## 6. 一句话提醒

**T1 的错误是"传多了文件会让人困惑"；T2 的错误是"传错目录会把 937 条答案公开"。**
所以 T2 的第 0 步（预检）不是形式主义 —— 它是这个数据集唯一不可回退的那一步。
