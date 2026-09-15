#!/usr/bin/env python3
"""扫**所有 markdown 文件**里指向本仓库的路径，逐个查是否存在。

为什么从 verify_readme 推广到全部文档
-------------------------------------
`verify_readme.py` 在 README 里抓到 **5 个已不存在的路径引用**。那说明"文档写了
已经不存在的文件"是这个仓库的一个**系统性**问题，不是 README 独有的。
而 SPEC.md（65 KB，主设计文档）从来没被这样查过。

第一次跑本脚本时，它在 **SPEC.md 第 12 节开头**抓到：

> **已由 `research/DATA_LICENSES.md` 解决**：题目清单与许可策略…

而 `research/DATA_LICENSES.md` **根本不存在**。主设计文档把"许可策略已解决"
挂在了一个不存在的文件上 —— 这正是"文档漂移"最危险的形态：
**结论还在，依据没了。**

误报控制（踩过的坑都写在代码里）
--------------------------------
  · 外部 id（HF/GitHub 的 `owner/repo`）不是本仓库路径 → 多段路径**必须以已知
    本地顶层目录开头**
  · 裸文件名（`manifest.json`）可能指仓库里任意位置的同名文件 → 递归按 basename 找
  · 命令行片段、URL、`~`/`$` 开头的 token 跳过
  · 明确知道"故意不存在"的（如"榜单还没做"里点名的 `leaderboard/`）走白名单

用法：
    python3 verify_doc_links.py            # 全部 .md
    python3 verify_doc_links.py --fix-list # 只打印问题清单，便于逐条修
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

LOCAL_TOP = {"docs", "scripts", "rubric", "tasks", "schema", "ledger", "tools",
             "src", "tests", "data", "judge", "annotation", "review", "research"}

# 已知"故意不存在"的引用 —— 每一条都要写理由，否则这个白名单会变成"眼不见为净"。
# 脚本会把所有命中白名单的条目**打印出来**，逼人正面处理。
#
# ⚠️ **刻意不发布的路径必须从 not_published.json 读，不能在这里另写一份。**
#    本轮踩到的坑：clean_room_check 把 `rubric/items/sources/` 当"不发布"排除掉，
#    而本脚本不知道，于是把 SPEC / SAFETY 里对它的引用报成死亡链接 ——
#    同一个概念有两份定义，两个工具就会互相打架。
NOT_PUBLISHED_MANIFEST = HERE / "not_published.json"
_EXTRA_ALLOW = {
    "leaderboard/": "README/SPEC 里作为『还没做』说明时点名，本就不该存在",
    "docs/JUDGE_RELIABILITY.md": "设计时规划的 κ 报告，尚未写（人类标注未取得）",
    "scripts/run_all.py": "设计时规划的一键脚本，实际由 run_all_checks.py 承担",
    "judge/": "设计时规划为顶层目录，实际在 rubric/judge/",
    "schema/item.schema.json": "设计时规划，实际只有 ledger.schema.json",
    # GATK4 jar 的内部路径（许可审计引文），不是本仓库路径
    "tools/genomicsdb/": "GATK4 jar 内部路径（许可审计引文）",
    "scripts/gatkcondaenv.yml.template": "GATK4 jar 内部路径（许可审计引文）",
    "src/cdflib90.README": "GATK4 jar 内部路径（许可审计引文）",
    "src/samtools-1.1.LICENSE": "GATK4 jar 内部路径（许可审计引文）",
    "src/main/c/Makefile": "GATK4 jar 内部路径（许可审计引文）",
    "scripts/install_genomicsdb.sh": "GATK4 jar 内部路径（许可审计引文）",
    # 已归档历史记录中被删除的辅助脚本（见文件顶部说明）
    "scripts/_r_extracheck.py": "已归档历史记录中被删掉的脚本",
    "scripts/_stage.py": "已归档历史记录中被删掉的脚本",
    "scripts/_chunk1.py": "已归档历史记录中被删掉的脚本",
    "scripts/_chunk2.py": "已归档历史记录中被删掉的脚本",
    "scripts/_r_build.py": "已归档历史记录中被删掉的脚本",
    "rubric/items/_gen_batch_1.py": "已归档历史记录中被删掉的脚本",
    "rubric/items/_build_batch4.py": "已归档历史记录中被删掉的脚本",
    "rubric/items/batch_1..4.jsonl": "已归档历史记录里的占位写法（非真实文件名）",
    "scripts/classify_human_data.py": "已归档历史记录中的旧路径写法",
}


def _allow_missing() -> dict[str, str]:
    """合并「刻意不发布」（共享清单）与「其它已知不存在」两条来源。"""
    out = dict(_EXTRA_ALLOW)
    if NOT_PUBLISHED_MANIFEST.is_file():
        man = json.loads(NOT_PUBLISHED_MANIFEST.read_text(encoding="utf-8"))
        for d, why in (man.get("dirs") or {}).items():
            out[d.rstrip("/") + "/"] = f"刻意不发布：{why}"
    return out

TOKEN_RE = re.compile(r"`([^`\n]+)`|\[[^\]]*\]\(([^)\n]+)\)")
SKIP_PREFIX = ("http://", "https://", "#", "pip ", "python", "bash", "docker", "hf ",
               "git ", "cd ", "export ", "$", "~", "-", "*", "|")

#: **占位符 / 省略号**，不是真实路径。
#:
#: ⚠️ 这个 bug 只在 Linux 上暴露，Windows 上一切正常 —— 所以必须显式排除，
#:    不能靠"文件系统说它存在"来判断：
#:      · Windows 会把路径尾部的点去掉，于是 `rubric/...` 解析成 `rubric`，
#:        `Path("rubric/...").exists()` 返回 **True**；
#:      · Linux 上 `rubric/...` 是一个叫 `...` 的真实条目，不存在 → False。
#:    结果同一个仓库在 Windows 上"文档链接全对"、在 Linux（= GitHub CI）上"有死链"。
#:    **同一个检查在不同平台上给出不同结论，比它报错更危险** ——
#:    因为你会信任本机那个绿。
PLACEHOLDER_RE = re.compile(r"\.\.\.|<[^>]*>|\{[^}]*\}|^\s*[.]+/?$|[…]")


def looks_like_path(t: str) -> bool:
    t = t.strip()
    if not t or " " in t or "\n" in t or t.startswith(SKIP_PREFIX):
        return False
    # 占位符（`rubric/...`、`<用户名>/...`、`{repo}`）不是路径
    if PLACEHOLDER_RE.search(t):
        return False
    if re.fullmatch(r"[\w./\-*]+/", t):
        return True
    if re.fullmatch(r"[\w./\-]+\.(py|md|json|jsonl|sh|txt|fa|bam|vcf|gz|csv|yml|yaml|toml|cfg|so|jar|zip)",
                    t):
        return True
    return "/" in t and bool(re.fullmatch(r"[\w./\-]+", t))


def self_test() -> int:
    """负向测试 + **跨平台一致性**测试。

    这里最关键的一组用例是"占位符" —— 因为那个 bug 只在 Linux 上暴露：
    Windows 会把 `rubric/...` 解析成 `rubric`（尾部点被去掉），`exists()` 返回 True；
    Linux 上不存在。于是**同一个仓库在两平台上结论相反**。
    所以判据必须是"语法上像不像路径"，而不是"文件系统说它存不存在"。
    """
    MUST_NOT_BE_PATH = [
        "rubric/...",                     # ← 真实踩到的那个
        "tasks/T2/data/public/...",
        "<用户名>/biobench-lite-t1-hg002-chr20",   # 占位符
        "{repo}/items.jsonl",
        "…",
        "docs/DATACARD.md",               # 这些是**真路径**，见下一组
    ]
    MUST_BE_PATH = [
        "docs/DATACARD.md",
        "scripts/verify_doc_links.py",
        "tasks/T2/data/public/",
        "README.md",
        "rubric/items/items_v1.2.jsonl",
    ]
    ok = True
    for t in MUST_NOT_BE_PATH:
        if t in MUST_BE_PATH:
            continue
        got = looks_like_path(t)
        good = not got
        ok = ok and good
        print(f"  {'✅' if good else '❌'} 不当作路径：{t!r}")
    for t in MUST_BE_PATH:
        got = looks_like_path(t)
        ok = ok and got
        print(f"  {'✅' if got else '❌'} 当作路径：  {t!r}")

    # 跨平台：`rubric/...` 在 Windows 上 exists()=True，绝不能被当成"存在即合法"
    import pathlib
    p = pathlib.Path("rubric/...")
    print(f"  ℹ️  本机 Path('rubric/...').exists() = {p.exists()}"
          f"  （Windows=True / Linux=False —— 正因如此，判据不能依赖它）")
    print("跨平台自检 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="文档路径引用检查")
    ap.add_argument("--include-research", action="store_true",
                    help="连 ../research/ 一起扫（那里是调研记录，引用更随意）")
    ap.add_argument("--self-test", action="store_true", help="跨平台负向测试")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    ALLOW = _allow_missing()
    #: 只有**目录项**（以 "/" 结尾）才做前缀匹配，见下面的说明。
    ALLOW_DIR_PREFIXES = tuple(k for k in ALLOW if k.endswith("/"))

    roots = [ROOT]
    if args.include_research:
        roots.append(ROOT.parent / "research")
    mds: list[Path] = []
    for r in roots:
        if r.is_dir():
            mds += [p for p in r.rglob("*.md") if "__pycache__" not in p.parts]
    # 负向测试夹具**故意**写满死引用，不能算进真实检查结果
    mds = [p for p in mds if "_fixtures" not in p.parts]
    mds = sorted(set(mds))
    print(f"扫描 {len(mds)} 个 markdown 文件")

    bad_by_file: dict[str, list[str]] = {}
    checked = 0
    allowed_hits: list[str] = []
    for md in mds:
        text = md.read_text(encoding="utf-8", errors="replace")
        seen: set[str] = set()
        for m in TOKEN_RE.finditer(text):
            tok = (m.group(1) or m.group(2) or "").split("#")[0].strip()
            if not looks_like_path(tok) or tok in seen:
                continue
            seen.add(tok)
            stripped = tok.rstrip("/")
            parts = [p for p in stripped.split("/") if p not in ("", ".")]
            if len(parts) > 1 and parts[0] not in LOCAL_TOP:
                continue
            if len(parts) == 1:
                if any(p.name == parts[0] for p in ROOT.rglob(parts[0])):
                    checked += 1
                continue
            checked += 1
            # ⚠️ 解析基准有歧义，必须把**所有祖先目录**都试一遍。
            #    第一版只试 `md.parent` / `ROOT` / `ROOT/scripts`，于是
            #    `tasks/T1/licenses/MODIFICATIONS.md` 里的 `scripts/patch_rtg_launcher.sh`
            #    （基准是**任务根** `tasks/T1/`）被报成死亡引用。
            #    同一份仓库里三种基准并存：仓库根、任务根、文件所在目录。
            cands = [ROOT / stripped, ROOT / "scripts" / stripped]
            anc = md.parent
            while True:
                cands.append(anc / stripped)
                if anc == ROOT or anc.parent == anc:
                    break
                anc = anc.parent
            if any(c.exists() for c in cands):
                continue
            # 白名单匹配：**三类写法都要认**（第二类是我自己漏掉、清室检验才暴露的）。
            #   · not_published 的目录项（键以 "/" 结尾）→ **前缀匹配**。
            #     "tasks/T1/_data/" 覆盖 "tasks/T1/_data/manifest.json" ——
            #     这正是"共享清单"的本意：文档引用了刻意的非发布区域，不该被当死链。
            #   · **文档里写目录本身**（不带尾斜杠），如 `tasks/T2/_runs`
            #     → 要认成"就是这个目录项"。此前只做前缀匹配，于是这种写法
            #     既不是精确命中（键带斜杠）也不是前缀命中 → 被误报死链。
            #   · _EXTRA_ALLOW 的文件项（不带 "/"）→ **仅精确匹配**
            #     （它们是具体文件名，放宽成前缀会把同目录下的真实死链一起放过）。
            #
            # ⚠️ 2026-09 两次修：第一次只做精确匹配 → "引用目录里的具体文件"误报；
            #    第二次加了前缀匹配 → "引用目录本身"仍误报。**两次都只在清室检验里现形**
            #    （本地文件真实存在，永远绿）。又一次印证：检查的强度和运行环境都要被怀疑。
            if tok in ALLOW or tok.rstrip("/") + "/" in ALLOW or tok.startswith(ALLOW_DIR_PREFIXES):
                allowed_hits.append(f"{md.relative_to(ROOT).as_posix()}: {tok}")
                continue
            bad_by_file.setdefault(md.relative_to(ROOT).as_posix(), []).append(tok)

    # ⚠️ 白名单自身也要被质疑：`research/DATA_LICENSES.md` 被放进白名单是**错的**，
    #    因为 SPEC 把它当作"许可策略已解决"的依据 —— 依据不存在就不叫解决。
    #    所以这里对每条白名单项打印出来，逼人正面处理，而不是默默放行。
    if allowed_hits:
        print(f"\n白名单放行 {len(allowed_hits)} 处（**每一条都该被正面处理，不是眼不见为净**）：")
        for a in sorted(set(allowed_hits)):
            print(f"  · {a}")

    if bad_by_file:
        print(f"\n❌ {len(bad_by_file)} 个文件里有指向不存在路径的引用：")
        for f, toks in sorted(bad_by_file.items()):
            print(f"\n  {f}")
            for t in toks:
                print(f"    · {t}")
    print(f"\n检查了 {checked} 处路径引用")

    if bad_by_file:
        print("\n❌ 文档里指向不存在的路径。**改文档，不要改事实。**")
        return 1
    print("✅ 全部文档的路径引用都存在（白名单除外，且白名单已列出）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
