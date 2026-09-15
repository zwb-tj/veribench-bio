#!/usr/bin/env python3
"""双盲标注工具：生成标注表 / 校验标注完整性。

工作流（对应 SPEC §6）
--------------------
1. `--generate` 为每位标注者生成**独立**的标注表（Markdown 供人看，JSONL 供程序读）
   —— 两位标注者**互不可见**对方的分数，这是"独立标注"的意思
2. 标注者各自填分（0 未满足 / 1 部分满足 / 2 满足）
3. `--validate` 校验填得完不完整 —— **漏填必须报出来，不能静默当成 0**
   （项目原则 7：成功必须可计数）
4. 用 `kappa.py` 算一致性，用 `judge_eval.py` 做仲裁与 judge 元评测

用法
----
    # 生成
    python3 make_annotation_sheets.py --items items.jsonl --outdir ../annotation --annotator A
    python3 make_annotation_sheets.py --items items.jsonl --outdir ../annotation --annotator B

    # 校验（填完之后）
    python3 make_annotation_sheets.py --validate ../annotation/ann_A.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def load_items(path: Path) -> list[dict]:
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def check_items(items: list[dict]) -> tuple[list[str], list[str]]:
    """结构预检。返回 (problems, warnings)。

    **problems 必须修完才发标注；warnings 需要人工确认。**

    ⚠️ 设计上踩过的坑：第一版把"结论词"当硬问题，结果我自己的夹具里
    「变异致病性判读」这种**合法主题词**也被拦了。
    对**开放题**而言，问"你会如何判断它是否致病"是正当的问题，不是暗示题。
    真正该当硬问题的是**身份泄露**（能让模型去查原文），所以：
      · 身份泄露（DOI / PMC ID / HGVS / accession / 变异名）→ problem（硬拦）
      · 结论词 → warning（需人工确认：它到底是"问题的一部分"还是"答案"）
    """
    problems: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()

    identity_pats = [
        (re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+"), "DOI"),
        (re.compile(r"\bPMC\d{5,}\b", re.I), "PMC ID"),
        (re.compile(r"\b(N[MCGRX]|X[MR]|ENST|LRG_)\d{4,}", re.I), "RefSeq/转录本 accession"),
        (re.compile(r"\b(SCV|VCV|RCV)\d{6,}", re.I), "ClinVar accession"),
        (re.compile(r"\brs\d{3,}\b", re.I), "rsID"),
        (re.compile(r"\b[cnpg]\.[\-\*\d]+[ACGT_]*[<>delinsdupA-Za-z]*\d*", re.I), "HGVS"),
        (re.compile(r"\bchr[\dXYM]+:\d+", re.I), "基因组坐标"),
    ]

    for it in items:
        iid = it.get("item_id", "?")
        if iid in seen:
            problems.append(f"{iid}: item_id 重复")
        seen.add(iid)

        crits = it.get("criteria") or []
        if not (3 <= len(crits) <= 5):
            problems.append(f"{iid}: rubric 条数 {len(crits)}，要求 3–5")
        cids = [c.get("criterion_id") for c in crits]
        if len(set(cids)) != len(cids):
            problems.append(f"{iid}: criterion_id 重复 {cids}")
        for c in crits:
            anchors = c.get("anchors") or {}
            for lvl in ("0", "1", "2"):
                if not (anchors.get(lvl) or "").strip():
                    problems.append(f"{iid}/{c.get('criterion_id')}: 缺 {lvl} 分锚点")

        q = it.get("question") or ""
        ctx = it.get("context") or ""
        if len(q) < 20:
            problems.append(f"{iid}: 题干过短（{len(q)} 字符）")

        # 硬拦：身份泄露（能让模型顺着查原文/数据库）
        for text, where in ((q, "题干"), (ctx, "背景")):
            for pat, label in identity_pats:
                m = pat.search(text)
                if m:
                    problems.append(f"{iid}: {where}含 {label} 身份标识 {m.group(0)!r} —— 会被反查")

        # 软提示：结论词（开放题里可能是正当主题词，需人工判断）
        for w in ("致病", "良性", "pathogenic", "benign"):
            if w.lower() in q.lower():
                warnings.append(
                    f"{iid}: 题干含 {w!r} —— 若它只是问题的一部分（如「如何判读致病性」）可以放行；"
                    f"若它直接给出了答案，就是暗示题，需人工确认")
                break

    return problems, warnings


def load_answers(path: Path) -> dict[str, list[dict]]:
    """读作答文件（judge 链的扁平格式），返回 {item_id: [{answer_id, text}, ...]}。

    ⚠️ **这个函数是本轮补上的，补之前这个脚本根本不接受作答输入。**
    原版只从 `--items` 生成标注表，于是标注者看到的是「问题 + 评分标准 + 分数：____」,
    **却没有任何要评的回答**。rubric 评的是"某份回答满足了没有"，
    没有回答就没法评 —— 那张表是**不可用的**。

    这个缺陷一直没暴露，是因为人工标注这一步**从来没有真正跑过**；
    而它又是整个第三支柱声明的硬阻塞。**工具与声明的流程对不上，没人发现。**

    ⚠️ **盲评（2026-09 修复）**：原版直接把 `model` 字段当 `answer_id`，
    于是标注表里出现 `BLIND-weak` / `BLIND-medium` / `BLIND-strong` ——
    `weak`/`strong` **本身就是质量标签**，与说明书里那句
    「编号本身不告诉你哪份好」**直接矛盾**，也与
    「不要被长度影响」这条核心规则冲突（实测三档长度严格递增 175/207/360 字符）。

    后果不是"不够优雅"，而是**结论会反过来**：标注者照着标签走 → κ 假性偏高 →
    人类天花板虚高 → judge 的"相对上限"被压低。**而数据看起来完全正常。**

    现在改成用**随机盲 id**，与判官侧完全一致
    （`fixtures/answers/judge_blind/_mapping.json` 一直是对的：
    随机 12 位十六进制 + 独立映射表）。判定顺序也**打乱**，
    避免"第一个总是最差"这种位置泄露。
    """
    by_item: dict[str, list[dict]] = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        iid = r.get("item_id")
        text = r.get("answer")
        if not iid or text is None:
            raise SystemExit(f"[错误] {path}:{i} 缺 item_id 或 answer 字段")
        model = str(r.get("model") or "model")
        run = r.get("run")
        aid = model if (run in (None, 1)) else f"{model}#{run}"
        #: 档位（weak/medium/strong）—— **只用于事后分析，绝不进标注表**
        level = model.split("-")[-1] if model.startswith("BLIND-") else None
        by_item.setdefault(iid, []).append(
            {"answer_id": aid, "text": text, "_level": level})
    for iid, lst in by_item.items():
        ids = [x["answer_id"] for x in lst]
        if len(set(ids)) != len(ids):
            raise SystemExit(f"[错误] {iid}: answer_id 重复 {ids} —— 无法区分是几份回答")

    # ---- 换成随机盲 id（并打乱顺序）----------------------------------------
    # 用确定性的种子（题号 + 答案内容），这样**同一个仓库重新生成会得到同样的 id**，
    # 便于复现；但 id 本身与档位无关，无法从 id 反推质量。
    import hashlib as _hashlib
    import random as _random

    for iid, lst in by_item.items():
        for idx, a in enumerate(lst):
            seed_src = f"{iid}\0{idx}\0{a['text'][:200]}".encode("utf-8")
            h = _hashlib.sha256(seed_src).hexdigest()[:12]
            a["answer_id"] = h
        # 打乱展示顺序，避免"位置即档位"
        _random.Random(iid).shuffle(lst)
        #: 映射表（谁来都能核对，但**不进标注表**）
        by_item[iid] = lst
    return by_item


def blind_map_for(answers: dict[str, list[dict]]) -> dict[tuple[str, str], str]:
    """返回 {(item_id, level): blind_id} —— 事后分析用（**不给标注者**）。"""
    out: dict[tuple[str, str], str] = {}
    for iid, lst in answers.items():
        for a in lst:
            lvl = a.get("_level")
            if lvl:
                out[(iid, lvl)] = a["answer_id"]
    return out


def generate(items: list[dict], outdir: Path, annotator: str,
             answers: dict[str, list[dict]], force: bool = False) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    problems, warnings = check_items(items)

    # ⚠️ 防呆：**绝不能默默覆盖已填的标注**。
    #    人工标注是整个第三支柱最贵的一步（要两个真人认真做完），
    #    而重跑一次生成脚本就能把它清空 —— 那种损失是不可逆的。
    #    所以只要目标文件里已经有任何非空分数，就拒绝写入，除非显式 --force。
    tpl = outdir / f"ann_{annotator}.jsonl"
    if tpl.is_file() and not force:
        filled = 0
        for line in tpl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("score") is not None:
                    filled += 1
            except json.JSONDecodeError:
                filled += 1
        if filled:
            print(f"❌ {tpl} 里已有 {filled} 条已填分数 —— **拒绝覆盖**")
            print("   人工标注不可逆，重生成会把它清空。")
            print("   确实要重新生成请加 --force（并先备份）。")
            return 1

    print(f"结构预检：{len(items)} 题 —— 硬问题 {len(problems)}，需人工确认 {len(warnings)}")
    for p in problems[:20]:
        print(f"  ❌ {p}")
    for w in warnings[:10]:
        print(f"  ⚠️ {w}")
    if problems:
        print("  ❌ 必须先修完硬问题才能发标注（身份泄露会让模型直接去查原文）")

    # 每道题必须有作答，否则那张表又变成"没有东西可评"
    no_answer = [it["item_id"] for it in items if not answers.get(it["item_id"])]
    if no_answer:
        print(f"  ❌ {len(no_answer)} 道题没有任何作答：{no_answer[:8]}")
        print("     没有回答就没法评 rubric —— 本版不再生成不可用的表")
        return 1

    n_units = sum(len(it.get("criteria") or []) * len(answers.get(it["item_id"], []))
                  for it in items)

    # 程序读的模板。**标注单位是 (题, 回答, 标准)**，不是 (题, 标准)。
    tpl = outdir / f"ann_{annotator}.jsonl"
    with tpl.open("w", encoding="utf-8") as fh:
        for it in items:
            for a in answers.get(it["item_id"], []):
                for c in it.get("criteria") or []:
                    fh.write(json.dumps({
                        "item_id": it["item_id"],
                        "answer_id": a["answer_id"],
                        "criterion_id": c["criterion_id"],
                        "score": None,          # ← 标注者填 0 / 1 / 2
                        "annotator": annotator,
                        "note": "",
                    }, ensure_ascii=False) + "\n")

    # 盲 id → 档位 的映射表。**绝不能给标注者看**，但必须留下 ——
    # 否则事后无法把"哪份是哪档"对回来，试点就白做了。
    #
    # ⚠️ 这份映射与判官侧 `fixtures/answers/judge_blind/_mapping.json` 是同一思路：
    #    随机 id + 独立映射表。**盲评靠的就是这两者分离。**
    bmap = blind_map_for(answers)
    if bmap:
        map_p = outdir / "_blind_mapping.json"
        rows_out = [{"item_id": iid, "level": lvl, "blind_id": bid}
                    for (iid, lvl), bid in sorted(bmap.items())]
        map_p.write_text(json.dumps(rows_out, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        print(f"  盲 id 映射 → {map_p}（**不要给标注者看**）")

    # 人读的表。
    #
    # ⚠️ 2026-09 重构：原来是「每份回答后面都把 c1–c4 的三档锚点重抄一遍」，
    #    6 题 × 3 回答 × 4 标准 = **同一套标准被抄了 18 遍**，
    #    整份表 24,899 字符里绝大部分是重复 ——
    #    标注者（湿实验背景，非生物统计专业）看完第一题就劝退了。
    #
    #    改成：**每题开头列一次标准与三档锚点**，然后**三份回答并排**，
    #    每份回答下只留一行「c1=__ c2=__ c3=__ c4=__」待填。
    #    · 阅读量降到几分之一（不用反复重读同一套标准）
    #    · 判断更一致（标准只读一次，减少"这次读到的是哪版"的漂移）
    #    · 信息一点没少（锚点仍在，只是不再重复）
    #
    #    ⚠️ 必须保留 `### 回答 \`{answer_id}\`` 这个标记的行 ——
    #    `test_annotation_chain.py` 用 `sheet.count("### 回答")` 断言
    #    "表里确实有 N 段待评回答"。改格式时漏掉它，那条检查就会误报。
    md = outdir / f"ann_{annotator}_sheet.md"
    lines = [
        f"# 标注表 · 标注者 {annotator}",
        "",
        "> **请独立打分，不要与他人讨论。** 每条标准选 0 / 1 / 2。",
        "> 打分对象是**下面给出的那份回答**，不是「你觉得应该怎么答」。",
        "> 不确定时**选 0 并写备注**，不要为了「看起来合理」选中间档。",
        "> 不要修改题号、回答编号与标准编号。",
        "",
        f"共 {len(items)} 题（每题的作答见各节）= **{n_units} 个评分点**。",
        f"填好后把分数写进 `ann_{annotator}.jsonl` 的 `score` 字段。",
        "",
        "**本表怎么读**（每题的结构固定）：",
        "",
        "1. 先读该题开头的【标准与档位】—— 这一题的所有标准与 0/1/2 定义只在**这里出现一次**；",
        "2. 再逐份读下面的回答；",
        "3. 每份回答末尾有一行 `c1=__ c2=__ …`，把分数填在那里。",
        "",
        "> 这样排版是为了让你**只读一遍标准**。原来每份回答都重抄一遍标准，",
        "> 既浪费时间，又容易读到后面忘了前面。",
        "",
        "---",
        "",
    ]
    for it in items:
        lines.append(f"## {it['item_id']}")
        lines.append("")
        lines.append(f"**问题**：{it.get('question','')}")
        lines.append("")
        lines.append("### 本题的标准与档位（**只在此处出现一次**）")
        lines.append("")
        for c in it.get("criteria") or []:
            a = c.get("anchors") or {}
            lines.append(f"**{c['criterion_id']}** — {c.get('text','')}")
            lines.append(f"- `0` {a.get('0','')}")
            lines.append(f"- `1` {a.get('1','')}")
            lines.append(f"- `2` {a.get('2','')}")
            lines.append("")
        lines.append("---")
        lines.append("")
        for ans in answers.get(it["item_id"], []):
            lines.append(f"### 回答 `{ans['answer_id']}`")
            lines.append("")
            lines.append(f"> {ans['text']}")
            lines.append("")
            # 只留一行待填，标准定义不再重抄
            boxes = "  ".join(f"`{c['criterion_id']}=____`"
                              for c in it.get("criteria") or [])
            lines.append(f"**打分**：{boxes}")
            lines.append("")
            lines.append("备注（0 分和 1 分最好写一句依据）：")
            lines.append("")
        lines.append("---")
        lines.append("")
    md.write_text("\n".join(lines), encoding="utf-8")

    print(f"已生成（{n_units} 个评分点）：")
    print(f"  {tpl}")
    print(f"  {md}")
    return 1 if problems else 0


def validate(path: Path) -> int:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    total = len(rows)
    missing: list[str] = []
    bad: list[str] = []
    no_answer_col = 0
    notes_empty = 0
    for r in rows:
        # ⚠️ 键里必须带 answer_id：一题多答时，(题, 标准) 不足以定位一个评分点
        aid = r.get("answer_id")
        if aid is None:
            no_answer_col += 1
        key = f"{r.get('item_id')}/{aid or '?'}/{r.get('criterion_id')}"
        s = r.get("score")
        if s is None:
            missing.append(key)
        elif s not in (0, 1, 2):
            bad.append(f"{key}: score={s!r} 不在 0/1/2")
        if not (r.get("note") or "").strip():
            notes_empty += 1

    print(f"文件：{path}")
    print(f"  记录数：{total}")
    print(f"  已填：{total - len(missing)}   未填：{len(missing)}   非法值：{len(bad)}")
    print(f"  无备注：{notes_empty}（非必填，但 1 分/0 分的判断最好写清依据）")
    if no_answer_col:
        print(f"  ⚠️ {no_answer_col} 条没有 `answer_id` —— 这是旧格式（一题一答时代）；"
              f"一题多答的文件必须带该字段，否则评分点无法定位")
    for x in missing[:10]:
        print(f"  [未填] {x}")
    for x in bad[:10]:
        print(f"  [非法] {x}")
    if missing or bad:
        print(f"\n❌ 校验未通过：{len(missing)} 条未填、{len(bad)} 条非法 —— **不允许静默当成 0**")
        return 1
    print("\n✅ 校验通过：全部已填且取值合法")
    return 0


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="双盲标注：生成 / 校验")
    ap.add_argument("--items")
    ap.add_argument("--answers",
                    help="**必需**。judge 链的扁平格式（item_id/answer/model/run）。"
                         "没有它标注表就没有可评的对象 —— 旧版正是漏了这个参数，"
                         "生成的表不可用。")
    ap.add_argument("--outdir", default="../annotation")
    ap.add_argument("--annotator", default="A")
    ap.add_argument("--validate", help="校验已填好的标注文件")
    ap.add_argument("--check-only", action="store_true", help="只做结构预检，不生成")
    ap.add_argument("--force", action="store_true",
                    help="允许覆盖已填分数的标注文件。默认拒绝 —— 人工标注不可逆")
    args = ap.parse_args(argv)

    if args.validate:
        return validate(Path(args.validate))
    if not args.items:
        ap.error("需要 --items 或 --validate")
    if not args.check_only and not args.answers:
        ap.error("生成标注表必须给 --answers —— 没有作答的标注表是不可用的"
                 "（rubric 评的是「这份回答满足了没有」）")

    items = load_items(Path(args.items))
    if args.check_only:
        problems, warnings = check_items(items)
        print(f"结构预检：{len(items)} 题 —— 硬问题 {len(problems)}，需人工确认 {len(warnings)}")
        for p in problems:
            print(f"  ❌ {p}")
        for w in warnings:
            print(f"  ⚠️ {w}")
        return 1 if problems else 0
    answers = load_answers(Path(args.answers))
    return generate(items, Path(args.outdir), args.annotator, answers, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
