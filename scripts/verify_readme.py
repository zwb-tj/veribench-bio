#!/usr/bin/env python3
"""核对 README 里**指向的路径真的存在**、以及关键断言与工作区一致。

为什么值得单独做一个
--------------------
README 是任何人读到的第一个文件，也是**最容易烂掉**的一个：它写的多半是
"当时打算有什么"。本项目本轮检查时发现它指向 **5 个不存在的路径**
（`scripts/run_all.py`、`leaderboard/`、`judge/`、`schema/item.schema.json`、
`docs/JUDGE_RELIABILITY.md`），还写着"**当前尚未收录任何题目**" ——
而当时 T1 早已完成。

一个以"可证明没编造"为卖点的项目，**首页写着已经不成立的话，是最糟的一种不诚实**
（不是故意骗人，是没人检查）。

⚠️ 2026-09 更正一处：上面原写"T1/T2 早已完成并**上过 HF**"——
但实测 `hf repo list` 显示 **T2 仓库 storage = 0 B**（仓库建了，没传内容）。
即**这句注释本身也是错的**，同一类毛病。T2 的上传状态现由
`verify_t2_claims.py` 的 `check_hf_upload_state()` 按实测核对。

本脚本做两件事：
  1. 把 README 里所有看起来像路径的 token 抽出来，逐个查是否存在
  2. 核对几条关键断言（题目数量、支柱状态）与工作区实际一致

用法：
    python3 verify_readme.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent          # bio-eval/

# 反引号里的、或 markdown 链接里的路径形 token
TOKEN_RE = re.compile(r"`([^`\n]+)`|\[([^\]]+)\]\(([^)\n]+)\)")

# 明确允许"不存在"的（比如说"未做"时点名一个还没有的目录）
ALLOW_MISSING = {
    "leaderboard/",
    "docs/JUDGE_RELIABILITY.md",
}

# 已知的本地顶层目录。**多段路径必须以其中之一开头**才算"本地路径声明"。
# ⚠️ 不加这条会误报：`zwb-tj/biobench-lite-t1-hg002-chr20`（HF 仓库 id）与
#    `jang1563/BioEval`（GitHub 仓库 id）也长得像 `a/b`，但它们**不是本仓库路径**。
#    第一版就是这么误报了这两条。
LOCAL_TOP = {"docs", "scripts", "rubric", "tasks", "schema", "ledger", "tools",
             "src", "tests", "data", "judge", "annotation", "review"}

# ---- 目录树（README 的 "## 目录结构" 小节）---------------------------------
# ⚠️ 为什么必须单独检查这一段：README 第 100 行写着「**与真实文件一致**，
#    由 `scripts/verify_readme.py` 强制」—— 但那时**没有任何东西在查它**。
#    实测（2026-10）：树里只有 `T1/` `T2/`，而 `T3/` `T4/` 早已存在；
#    顶层的 `.github/` `leaderboard/` `research/` `tools/` 也一个都没列。
#    这是本项目自己的缺陷类：**声明了守卫，但守卫不存在**。
#    注意旧检查为什么抓不到：`TOKEN_RE` 只匹配反引号与 markdown 链接，
#    而目录树在 ``` 代码块里 —— 它的每一行都**没有被任何检查看过**。
TREE_HEADING_RE = re.compile(
    r"^##\s*目录结构[^\n]*\n+```[a-zA-Z]*\n(.*?)^```", re.S | re.M)

# 顶层条目：行首就是 ├── 或 └──（缩进过的属于子级，见下）
TREE_TOP_RE = re.compile(r"^([├└])──\s+([^\s#]+)")
# 子级条目：4 列前缀（`│   ` 或 4 个空格）后才是 ├── / └──
TREE_CHILD_RE = re.compile(r"^[│ ]{4}([├└])──\s+([^\s#]+)")

# 不要因为"存在但没列进树"就判红的目录：
#   · `.git` / `__pycache__` 是版本控制与解释器元数据，不是项目结构
#   · `_` 开头的是本地产物（如 `_artifacts`），本来就不该对外描述
TREE_SKIP_DIRS = {".git", "__pycache__"}

results: list[tuple[str, bool | None, str]] = []


def add(claim: str, ok: bool | None, ev: str) -> None:
    results.append((claim, ok, ev))


def parse_tree(text: str) -> tuple[set[str], dict[str, set[str]], set[str]] | None:
    """从 README 的目录树代码块里取出：
         (1) 顶层条目集合
         (2) 每个"列出了子项"的顶层目录 → 它列出的子项集合
         (3) 其中**明确省略**了子项的目录（如写 `...` 或一行塞多个名字）

    返回 None 表示**找不到这个小节** —— 调用方必须把它当失败，而不是静默跳过
    （"查不到就说通过"正是本项目反复踩的坑）。

    ⚠️ 为什么要有 (2)(3) 这层而不是硬编码只查 `tasks/`：
    第一版只查顶层 + `tasks/`，于是**下一个层级完全没被看过** —— 我新加一个
    `docs/DRILL_SEEN_A_CHECK_FAIL.md` 之后，树里那句「与真实文件一致」当场变假
    而检查全绿。同一个缺陷类在同一份文件里连着出现两次，说明判据的形状不对：
    正确的判据不是"查两个地方"，而是"**只要树列举了某目录的子项，且没有写省略号，
    这个列举就必须是完整的**"。
    """
    m = TREE_HEADING_RE.search(text)
    if not m:
        return None
    top: set[str] = set()
    children: dict[str, set[str]] = {}
    elided: set[str] = set()
    cur: str | None = None
    for line in m.group(1).splitlines():
        tm = TREE_TOP_RE.match(line)
        if tm:
            # 树里可能写成 `ledger/items.jsonl` —— 顶层条目仍是 `ledger`
            name = tm.group(2).rstrip("/").split("/")[0]
            top.add(name)
            cur = name if line.rstrip().endswith("/") else None
            if cur:
                children.setdefault(cur, set())
            continue
        cm = TREE_CHILD_RE.match(line)
        if cm and cur:
            raw = cm.group(2).rstrip("/")
            # 一行里塞了多个名字（`schema/ judge/ ledger/ ...`）说明是概括写法，
            # 不是完整列举 —— 该目录标为"已省略"，不参与完整性比对。
            if len(raw.split()) > 1 or raw in ("...", "…"):
                elided.add(cur)
            else:
                children[cur].add(raw.split("/")[0] if "/" in raw and raw.endswith(".jsonl") else raw)
    return top, children, elided


def real_top_dirs() -> set[str]:
    return {d.name for d in ROOT.iterdir()
            if d.is_dir() and d.name not in TREE_SKIP_DIRS and not d.name.startswith("_")}


def check_tree(text: str) -> None:
    """三个方向：树里的条目真实存在 / 列举是完整的 / 顶层目录都列了。"""
    parsed = parse_tree(text)
    if parsed is None:
        add("README 有『## 目录结构』代码块（否则本段无从检查）", False,
            "找不到该小节或代码块")
        return
    top, children, elided = parsed

    # 1) 正向：树里写了的，必须真的存在（文件或目录都算）
    ghost = sorted(n for n in top if not (ROOT / n).exists())
    add("目录树里的每个顶层条目都真实存在", not ghost,
        f"树里有但仓库没有：{ghost or '无'}")

    # 2) 正向：树里列出的每个子项也必须真的存在（不限层级）
    ghost_children: list[str] = []
    for parent, kids in children.items():
        for kid in sorted(kids):
            if not (ROOT / parent / kid).exists():
                ghost_children.append(f"{parent}/{kid}")
    add("目录树里列出的子项都真实存在", not ghost_children,
        f"树里有但仓库没有：{sorted(ghost_children) or '无'}")

    # 3) 反向：**只要树列举了某目录的子项、又没写省略号，就必须列全**。
    #    这是把原来的"只查 tasks/"推广成一般规则 —— 否则加一个新文档就能让
    #    「与真实文件一致」这句话变假而检查全绿（本轮第二次犯）。
    incomplete: list[str] = []
    for parent, kids in sorted(children.items()):
        if parent in elided:
            continue                        # 写法是概括（`...` 或一行多个）
        d = ROOT / parent
        if not d.is_dir():
            continue
        real = {p.name for p in d.iterdir()
                if p.name not in TREE_SKIP_DIRS and not p.name.startswith("_")}
        miss = sorted(real - kids)
        if miss:
            incomplete.append(f"{parent}/ 缺 {miss}")
    # tasks/ 下面还有一层（题目目录），单独报，便于定位
    bad_tasks = [x for x in incomplete if x.startswith("tasks/")]
    add("目录树列出的子项是完整的（没写省略号的目录）", not incomplete,
        "；".join(incomplete) or "全部完整")
    add("目录树列全了 tasks/ 下的题目（T1…TN）", not bad_tasks,
        "；".join(bad_tasks) or "无")

    # 4) 反向：真实顶层目录必须在树里出现（**这条才是抓到头一个漏洞的那条**）
    missing_top = sorted(real_top_dirs() - top)
    add("目录树列全了真实的顶层目录", not missing_top,
        f"真实存在但树里没列：{missing_top or '无'}")


def looks_like_path(tok: str) -> bool:
    t = tok.strip()
    if not t or " " in t or "\n" in t:
        return False
    if t.startswith(("http://", "https://", "#", "pip ", "python", "bash", "docker", "hf ")):
        return False
    if t.startswith("-"):          # 命令行 flag
        return False
    # 末尾是 / 的目录、带扩展名的文件、或含 / 的相对路径
    return bool(re.fullmatch(r"[\w./\-*]+/", t)
                or re.fullmatch(r"[\w./\-]+\.(py|md|json|jsonl|sh|txt|fa|bam|vcf|gz|csv|yml|yaml|toml|cfg|gz)", t)
                or ("/" in t and re.fullmatch(r"[\w./\-]+", t)))


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    # --readme 是为了**让这个检查本身可被检验**：硬编码路径的话，
    # 我没法用一个故意写错的 README 去验证它真的会失败。
    # 「检查器自己没被检查过」是这一整轮反复踩的坑。
    import argparse
    ap = argparse.ArgumentParser(description="核对 README")
    ap.add_argument("--readme", default=str(ROOT / "README.md"))
    ap.add_argument("--self-test", action="store_true",
                    help="用一份故意写错的 README 验证本检查器**真的会失败**。"
                         "没被检验过的检查器 = 没有检查器。")
    args = ap.parse_args()

    rd = Path(args.readme)
    if args.self_test:
        rd = HERE / "_fixtures" / "fake_readme.md"
        if not rd.is_file():
            print(f"❌ 缺负向测试夹具 {rd}")
            return 1
    if not rd.is_file():
        print(f"❌ 找不到 {rd}")
        return 1
    text = rd.read_text(encoding="utf-8")

    # ---- 1) 路径存在性 ----------------------------------------------------
    missing: list[str] = []
    checked = 0
    seen: set[str] = set()
    for m in TOKEN_RE.finditer(text):
        tok = m.group(1) or m.group(3) or ""
        tok = tok.split("#")[0].strip()
        if not looks_like_path(tok) or tok in seen:
            continue
        seen.add(tok)

        stripped = tok.rstrip("/")
        parts = [p for p in stripped.split("/") if p not in ("", ".")]

        # 多段路径：必须以已知本地顶层目录开头，否则视为外部 id（HF/GitHub 仓库名等）
        if len(parts) > 1 and parts[0] not in LOCAL_TOP:
            continue
        # 单段（裸文件名/目录名）：只有当仓库里**确实没有**同名文件时才算"缺失"
        if len(parts) == 1:
            name = parts[0]
            if any(p.name == name for p in ROOT.rglob(name)):
                checked += 1
                continue
            # 仓库里没有同名文件 → 可能是外部文件名（如上游的 LICENSE.txt），跳过
            continue

        checked += 1
        if (ROOT / stripped).exists() or (ROOT / "scripts" / stripped).exists():
            continue
        missing.append(tok)

    real_missing = [t for t in missing if t not in ALLOW_MISSING]
    add(f"README 指向的 {checked} 个路径都存在（允许缺失清单除外）",
        not real_missing,
        f"缺失：{real_missing or '无'}")
    for t in real_missing:
        print(f"  ❌ README 指向不存在的路径：{t}")

    # ---- 2) 关键断言 ------------------------------------------------------
    items = ROOT / "rubric" / "items" / "items_v1.2.jsonl"
    if items.is_file():
        rows = [json.loads(l) for l in items.read_text(encoding="utf-8").splitlines() if l.strip()]
        n = len(rows)
        nc = sum(len(r["criteria"]) for r in rows)
        add("README 说的 rubric 题数 = 实际", f"{n} 题" in text, f"实际 {n} 题")
        add("README 说的 rubric 标准数 = 实际", f"{nc} 条标准" in text, f"实际 {nc} 条")

    led = ROOT / "ledger" / "items.jsonl"
    if led.is_file():
        k = len([l for l in led.read_text(encoding="utf-8").splitlines() if l.strip()])
        add("README 说的台账条数 = 实际", f"{k} 条" in text, f"实际 {k} 条")

    # 状态描述不能与事实相反
    add("README 不再声称『尚未收录任何题目』",
        "尚未收录任何题目" not in text,
        "该说法在 T1/T2 完成后已不成立")
    add("README 不再声称 LICENSE 待补",
        "LICENSE 待补" not in text,
        f"LICENSE {'存在' if (ROOT / 'LICENSE').is_file() else '不存在'}")

    # ---- 3) 目录树与实际结构一致 ------------------------------------------
    check_tree(text)

    # v1 四件套的勾选必须与事实一致
    saf = (ROOT / "docs" / "SAFETY.md").is_file() and (ROOT / "docs" / "DATACARD.md").is_file()
    add("README 勾选了『SAFETY+DATACARD+license』且三者确实都在",
        ("- [x] **SAFETY + DATACARD + license 文档**" in text) and saf
        and (ROOT / "LICENSE").is_file(),
        f"SAFETY={saf} LICENSE={(ROOT / 'LICENSE').is_file()}")
    # 「真实榜单」这一项的判据在**本轮变了**：以前是"目录不存在"，
    # 现在是"**还没有真实条目**" —— 提交校验器已就绪（`leaderboard/` 存在），
    # 但 `results.jsonl` 是 0 字节，因为数据集未公开、没人能提交。
    # 就绪 ≠ 完成，所以 README 必须**仍然不勾**这一项。
    lb_res = ROOT / "leaderboard" / "results.jsonl"
    n_entries = 0
    if lb_res.is_file():
        n_entries = sum(1 for l in lb_res.read_text(encoding="utf-8").splitlines() if l.strip())
    add("README 未勾选『真实榜单』（确实还没有任何提交）",
        "- [ ] **真实榜单**" in text and n_entries == 0,
        f"results.jsonl 里有 {n_entries} 条提交")

    w0 = max(len(c) for c, _, _ in results)
    print(f"\n{'断言'.ljust(w0)}  结论")
    print("-" * (w0 + 34))
    for claim, ok, ev in results:
        mark = "✅ 通过" if ok is True else ("❌ 不符" if ok is False else "⚠️ 无法验证")
        print(f"{claim.ljust(w0)}  {mark}")
        print(f"{' ' * w0}  └ {ev}")

    n_bad = sum(1 for _, ok, _ in results if ok is False)
    un = sum(1 for _, ok, _ in results if ok is None)
    print(f"\n共 {len(results)} 条：通过 {len(results) - n_bad - un} · 不符 {n_bad} · 无法验证 {un}")

    if args.self_test:
        # 负向测试：**期望失败**。若这里通过了，说明检查器坏了 —— 那才是真问题。
        if n_bad >= 3:
            print(f"✅ 自检通过：故意写错的 README 被抓出 {n_bad} 条不符（期望 ≥3）")
            print("   → 本检查器确实会失败，不是一个永远说 OK 的摆设。")
            return 0
        print(f"❌ 自检失败：只抓出 {n_bad} 条不符（期望 ≥3）—— 检查器本身有问题")
        return 1

    if n_bad:
        print("❌ README 与实际不符 —— **改 README，不要改事实**。")
        return 1
    print("✅ README 的路径与关键断言均与工作区一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
