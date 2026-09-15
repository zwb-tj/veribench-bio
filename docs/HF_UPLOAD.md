# 把 T1 数据集上传到 Hugging Face —— 操作手册

> 前提：HF 账号已注册（你已完成）。本手册按 Windows + PowerShell 写。

---

## 0. 先确认数据已经准备好

数据准备脚本会在 `bio-eval/tasks/T1/_data/` 生成这些东西：

```
_data/
├── ref/    chr20.fa (+ .fai)              ← 参考序列（UCSC hg38，公有领域）
├── aln/    HG002.chr20.30x.bam (+ .bai)   ← 降采样到 30× 的比对结果（题目输入）
├── truth/  HG002_GRCh38_v5.0q_smvar.region.vcf.gz (+ .tbi)
│           HG002_GRCh38_v5.0q_smvar.benchmark.region.bed   ← 真值 + 高置信区间
├── sources.json                            ← 溯源事实
├── manifest.json                           ← 每个文件的 sha256
└── _work/                                  ← ⚠️ 中间产物，**不要上传**
```

**⚠️ `_work/` 必须排除**：里面是未降采样的区域 BAM（约 80 MB）与参考 SDF（约数百 MB），
都是中间产物，可以用脚本重放。而且它们**不在 manifest 里**——上传它们只会让仓库变大，
并让第三方的完整性校验出现"仓库里有 manifest 没列的文件"这种困惑。

最省事的做法是上传前先把它挪出目录：

```powershell
# 假设当前目录是仓库根（bio-eval/）
Move-Item "tasks/T1/_data/_work" "tasks/T1/_work_backup" -Force
```


**上传前先核对 manifest**（这一步不能省）：

```powershell
cd "tasks/T1/_data"
Get-Content manifest.json | ConvertFrom-Json | Select-Object -ExpandProperty files |
  ForEach-Object {
    $h = (Get-FileHash $_.path -Algorithm SHA256).Hash.ToLower()
    "{0}  {1}" -f $(if ($h -eq $_.sha256) { "OK  " } else { "FAIL" }), $_.path
  }
```

全部 OK 才继续。**如果 FAIL，不要上传——先查为什么。**

---

## 1. 建数据集仓库（网页操作，1 分钟）

1. 打开 <https://huggingface.co/new-dataset>
2. **Owner**：你自己
3. **Dataset name**：`biobench-lite-t1-hg002-chr20`
4. **License**：选 **`other`**（理由见下）
5. **Visibility**：先选 **Private**（确认没问题再改 Public）
6. 点 **Create dataset**

> **为什么选 `other` 而不是 CC0？**
> 这份数据是 **NIST/GIAB 的美国政府作品（公有领域）**，不是我们的作品。
> 我们**没有资格替 NIST 重新声明一个许可**。选 `other` 并在数据集卡里写清真实依据，
> 比随手勾一个 CC0 诚实——这也正是这个项目在做的事（**不信自我声明，只写有依据的**）。

---

## 2. 装 CLI 并登录

```powershell
pip install -U "huggingface_hub[cli]"
hf auth login
```

- 会提示粘贴 token。去 <https://huggingface.co/settings/tokens> 建一个
  **Type = Write** 的 token（不要用 Read）。
- token 只在这次粘贴时用；**不要写进任何文件、不要提交进 git**。

验证登录：

```powershell
hf auth whoami
```

---

## 3. 上传

> ### ⚠️ PowerShell 用户必读：不要用尖括号占位符
> 文档里常写 `hf upload <你的用户名>/<仓库名>` 这种形式，**但在 PowerShell 里 `<` 是保留的
> 重定向运算符**，会直接报 `"<"运算符是为将来使用而保留的` 并**拒绝执行整条命令**
> （本手册第一版就是踩了这个坑）。**请把用户名直接写出来。**
>
> 不确定用户名就先跑：`hf auth whoami`

一条命令，上传整个目录到仓库根目录：

```powershell
cd "tasks/T1/_data"

# 本项目的实际用户名是 zwb-tj（用 hf auth whoami 可确认）
hf upload zwb-tj/biobench-lite-t1-hg002-chr20 . . --repo-type=dataset
```

> 三个位置参数的含义：`仓库id` `本地路径` `仓库内路径`
> 这里是"本地当前目录 → 仓库根目录"。

**如果仓库还不存在，也可以先建**（`--private` 先建私有，确认无误再改公开）：

```powershell
hf repo create zwb-tj/biobench-lite-t1-hg002-chr20 --repo-type dataset --private --exist-ok
```

**上传前先把数据集卡放进去**（HF 会自动把仓库根目录的 `README.md` 当数据集卡）：

```powershell
Copy-Item "tasks/T1/data/HF_DATASET_CARD.md" "tasks/T1/_data/README.md"
```

旧版 CLI 请把 `hf upload` 换成 `huggingface-cli upload`，其余相同。
新版 CLI 中 `hf repo` 已废弃为 `hf repos`（只是警告，不影响使用）。

---

## 4. 上传后验证（别跳过）

**① 网页确认文件都在**：打开 `https://huggingface.co/datasets/zwb-tj/biobench-lite-t1-hg002-chr20/tree/main`

应有 `aln/`、`ref/`、`truth/`、`manifest.json`、`README.md`、`sources.json`。

**② 从 HF 重新下一份，比对 sha256**（这才是真正的验证——证明别人下到的和我们的字节一致）：

```powershell
hf download zwb-tj/biobench-lite-t1-hg002-chr20 --repo-type=dataset `
            --local-dir "$env:TEMP\hf-verify"
```

然后用**第 0 步的同一条命令**核对 `$env:TEMP\hf-verify` 里的文件哈希。

**③ 确认 Private 时可以匿名读、Public 时可以匿名下**：
Private 仓库需要 token 才能下，这是预期的；改成 Public 后匿名应该能下。

---

## 5. 之后要告诉我什么

上传完成后，告诉我：

1. **仓库全名**（`用户名/仓库名`）
2. **Visibility**（Private 还是 Public）
3. 第 4 步两次验证的结果

我会把这些写进 `manifest.json` 的 `files[].url` 和 DATACARD，让整个数据集**从上游到最终文件全链路可追溯**。

---

## 6. 真实体积（已实测，不是估算）

| 文件 | 实测体积 | sha256 前 16 位 |
|---|---|---|
| `ref/chr20.fa` | 65.7 MB | `a704b3a25c698bb5` |
| `ref/chr20.fa.fai` | 23 B | `081e289f1f48b9c9` |
| `aln/HG002.chr20.30x.bam` | 34.6 MB | `66c5869ddec8757e` |
| `aln/HG002.chr20.30x.bam.bai` | 31.7 KB | `747a7f808cf9023b` |
| `truth/…smvar.region.vcf.gz` | 22.0 KB | `369ad69898710a0a` |
| `truth/…smvar.region.vcf.gz.tbi` | 1.1 KB | `95cd6b9d05321421` |
| `truth/…smvar.benchmark.region.bed` | 480 B | `4ede762d0794fcee` |
| **合计** | **100.4 MB** | — |

对 HF 来说很小，不需要 Git LFS 的特殊配置（CLI 会自动处理）。

---

## 7. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `401 Unauthorized` | token 不是 **Write** 类型，或没登录成功（先 `hf auth whoami`） |
| `403 Forbidden` | token 没有该仓库的写权限；确认仓库在你名下 |
| 上传中断 | 重跑同一条 `hf upload` 命令即可，已上传的文件不会重传 |
| 想把 Private 改 Public | 仓库 → Settings → Change visibility |
| 只想上传单个文件 | `hf upload <repo> <本地文件> <仓库内路径> --repo-type=dataset` |

---

## 8. 一句话提醒

**这份数据集的卖点不是"我们有多少数据"，而是"每一步都能被你自己验一遍"。**
所以第 0 步和第 4 步的哈希核对不是形式——**它就是产品本身**。
