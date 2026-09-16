#!/usr/bin/env python3
"""逐篇为 `contains_human_data` 取证据，**不猜**。

背景（这是一次真实纠错）
--------------------
`candidates.jsonl` 把 27 篇**全部**标成 `contains_human_data=true`，
其中包括蜜蜂转录组、大鼠心梗模型、叙述性综述。而 `precheck_items.py`
又强制"item 的 provenance 必须与 candidates 一致"，于是把同一个错误
复制进了 24 道题。

教训：**"一致性校验"只能用来传递已经验证过的事实**。把一个未经验证的
字段纳入强制一致，等于给它盖了个"已验证"的章，错误反而更难发现。

本脚本的定位
-----------
不做自动判定（那会变成"自算真值"，违反原则②），而是**把证据摆出来**：
对每篇源文，统计人类参与者标记与动物模型标记，并抽出可引用的原句。
人工据此定值，并把依据写进 `human_data_basis` / `human_data_evidence`。

用法：
    python3 classify_human_data.py --sources ../items/sources \
        [--candidates ../items/candidates.jsonl] --out human_data_review.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 人类参与者标记（个体/群体层面）
HUMAN = [
    r"\bpatients?\b", r"\bparticipants?\b", r"\bsubjects?\b", r"\bvolunteers?\b",
    r"\bhealthy controls?\b", r"\bcohort\b", r"\bwe recruited\b", r"\binformed consent\b",
    r"\bthis (?:study|trial) enrolled\b", r"\bcase report\b", r"\bquestionnaire\b",
    r"\binterviews?\b", r"\bblood samples? (?:from|were collected from) (?:patients|subjects|donors)\b",
    r"\bIRB\b", r"\bInstitutional Review Board\b", r"\bEthics Committee\b",
]
# 动物/非人模型标记
ANIMAL = [
    r"\bmice\b", r"\bmouse\b", r"\brats?\b", r"\bmurine\b", r"\bzebrafish\b",
    r"\bSprague[- ]Dawley\b", r"\bC57BL\b", r"\bBALB/c\b", r"\bknockout mice\b",
    r"\bwild[- ]type mice\b", r"\bin vivo\b.*\b(?:mice|rats?)\b",
    r"\bApis mellifera\b", r"\bbees?\b", r"\bhoney ?bee\b", r"\bDrosophila\b",
    r"\bcell lines?\b", r"\bHEK293\b", r"\bHeLa\b", r"\bSH-SY5Y\b",
    r"\bArabidopsis\b", r"\bEscherichia coli\b", r"\by east\b",
]
# 二次文献标记（本身不含个体数据）
SECONDARY = [
    r"\bnarrative review\b", r"\bsystematic review\b", r"\bmeta[- ]analysis\b",
    r"\bthis review\b", r"\bwe (?:review|summarize|discuss)\b", r"\breview (?:aims|focuses)\b",
]


def count(patterns: list[str], text: str) -> tuple[int, list[str]]:
    hits, examples = 0, []
    for p in patterns:
        for m in re.finditer(p, text, re.I):
            hits += 1
            if len(examples) < 3:
                s = max(0, m.start() - 70)
                examples.append(text[s:m.end() + 70].replace("\n", " ").strip())
    return hits, examples


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="逐篇为 contains_human_data 取证据")
    ap.add_argument("--sources", required=True)
    ap.add_argument("--candidates", help="用于对比现有（错误的）取值")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    src_dir = Path(args.sources)
    # ⚠️ `items/sources/` 是**刻意不发布**的（那是别人的论文全文，公开的是改写后的题目）。
    #    所以第三方 clone 下来这里必然为空 —— 那是"没跑"，不是"跑错了"。
    #    用 SKIP 明确区分，别让它看起来像故障（见 run_all_checks.py 的约定）。
    if not src_dir.is_dir():
        print(f"SKIP: 源文目录不存在（{src_dir}）—— items/sources/ 刻意不随仓库发布，"
              f"需先用 fetch_source_text.py 取回")
        return 0
    files = sorted(src_dir.glob("PMC*.txt"))
    print(f"源文目录：{src_dir}  找到 {len(files)} 篇\n")
    if not files:
        print(f"SKIP: 目录存在但一篇源文都没有（{src_dir}）—— 需先跑 fetch_source_text.py")
        return 0

    # ⚠️ 截断会直接毁掉判定：方法学部分被切掉后，只能靠引言里的词频猜，
    #    而引言恰恰在引用**他人**的患者数据。本项目的 PMC11900006 误判就是这么来的。
    #    所以先看清单里的 truncated 标记，有截断就不许下结论。
    trunc: list[str] = []
    mpath = src_dir / "manifest.jsonl"
    if mpath.is_file():
        for line in mpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            m = json.loads(line)
            if m.get("truncated") or m.get("chars_total", 0) > m.get("chars_saved", 0):
                trunc.append(m.get("pmcid", "?"))
    else:
        # 没有清单就退回启发式：恰好等于常见上限长度的文件很可疑
        for f in files:
            n = len(f.read_text(encoding="utf-8", errors="replace"))
            if n in (20000, 50000, 100000):
                trunc.append(f.stem)
    if trunc:
        print(f"⚠️ 有 {len(trunc)} 篇正文被截断：{trunc[:8]}{' …' if len(trunc) > 8 else ''}")
        print("   截断会把方法学部分切掉，而引言里的患者数据往往是**引用他人工作**。")
        print("   判定前请先取全文：fetch_source_text.py --force（默认已不截断）\n")
    else:
        print("✅ 未发现截断（manifest 的 truncated 全为 false）\n")

    cur = {}
    if args.candidates:
        cp = Path(args.candidates)
        if cp.is_file():
            for l in cp.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    r = json.loads(l)
                    cur[r.get("pmcid") or r.get("source_ref")] = r.get("contains_human_data")
            print(f"现有 candidates 取值：{cur}\n")

    out_rows = []
    for f in files:
        pmc = f.stem
        text = f.read_text(encoding="utf-8", errors="replace")
        h, hx = count(HUMAN, text)
        a, ax = count(ANIMAL, text)
        s, sx = count(SECONDARY, text)

        # 建议值只作参考，判定权在人
        if s >= 3 and h < 5:
            guess, why = False, f"二次文献标记 {s} 次，人类个体标记仅 {h} 次"
        elif h > a and h >= 5:
            guess, why = True, f"人类标记 {h} > 非人标记 {a}"
        elif a > h and a >= 3:
            guess, why = False, f"非人模型标记 {a} > 人类标记 {h}"
        else:
            guess, why = None, f"证据不足（人类 {h} / 非人 {a} / 二次文献 {s}）——需人工读原文"

        flag = ""
        if cur.get(pmc) is True and guess is False:
            flag = "  ⚠️ 与现有 true 冲突"
        print(f"{pmc}  人类标记 {h:4d} | 非人标记 {a:4d} | 二次文献 {s:3d}  建议={guess}{flag}")
        print(f"         理由：{why}")
        for e in (hx[:1] + ax[:1]):
            print(f"         证据：「{e[:150]}」")
        print()

        out_rows.append({
            "source_ref": pmc, "human_hits": h, "animal_hits": a, "secondary_hits": s,
            "suggested": guess, "reason": why,
            "human_examples": hx, "animal_examples": ax,
            "current_value": cur.get(pmc),
        })

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out_rows, ensure_ascii=False, indent=2), encoding="utf-8", newline="")
    conflicts = [r for r in out_rows if r["current_value"] is True and r["suggested"] is False]
    unresolved = [r for r in out_rows if r["suggested"] is None]
    print(f"合计 {len(out_rows)} 篇：与现有 true 冲突 {len(conflicts)} 篇，证据不足待人工判定 {len(unresolved)} 篇")
    print(f"证据已写出 → {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
