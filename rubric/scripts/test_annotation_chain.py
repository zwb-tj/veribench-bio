#!/usr/bin/env python3
"""端到端演练**人工标注链路**：造两个合成标注者，把整条链跑通一遍。

为什么必须做这个
----------------
上一轮发现 `make_annotation_sheets.py` **根本不接受作答输入** —— 生成的标注表
没有可评的对象，是不可用的。它能坏那么久，根本原因是：

> **没有任何东西在跑这条链。** 工具写了、文档写了、对外声明它是硬阻塞，
> 但从来没有一次端到端运行去验证"人来了到底能不能做"。

所以本脚本用**合成的**标注者把整条链跑一遍：

    题面 + 作答
      → make_annotation_sheets.py（生成表）
      → 合成 ann_A / ann_B（模拟两位标注者填分）
      → --validate（校验完整性）
      → kappa.py（算一致性）
      → judge_eval.py（把裁判与人类对比）

**它不证明标注质量，只证明管道通。** 这是"先证明工具能用，再请人花 70 分钟"的顺序 ——
反过来做（先请人、再发现工具坏）是不可接受的。

合成分数的来源与局限
--------------------
`ann_A` 直接取**裁判第一轮的分数**（所以它其实不是"人类"）；
`ann_B` 在 A 的基础上扰动一小部分。这只是为了让链路有数据流动，
**绝不代表任何人类标注结果**，脚本会把它们写在临时目录里、跑完即删。

用法：
    python3 test_annotation_chain.py
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent          # rubric/


def sh(args: list[str]) -> tuple[int, str]:
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT))
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="人工标注链路端到端演练")
    ap.add_argument("--seed", type=int, default=20260917)
    ap.add_argument("--perturb", type=float, default=0.15,
                    help="ann_B 相对 ann_A 的扰动比例（用来造出'有分歧'的情形）")
    args = ap.parse_args(argv)

    items_p = ROOT / "annotation" / "pilot" / "items.jsonl"
    ans_p = ROOT / "annotation" / "pilot" / "answers.jsonl"
    for p in (items_p, ans_p):
        if not p.is_file():
            print(f"SKIP: 缺 {p}（先跑 make_pilot.py）")
            return 0

    items = {json.loads(l)["item_id"]: json.loads(l)
             for l in items_p.read_text(encoding="utf-8").splitlines() if l.strip()}
    answers = [json.loads(l) for l in ans_p.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 裁判第一轮的分数 —— 用真实的判分产出做底，数据形态才现实
    blind_map_p = ROOT / "fixtures" / "answers" / "judge_blind" / "_mapping.json"
    judge_dir = ROOT / "fixtures" / "answers" / "judge_out"
    if not blind_map_p.is_file() or not judge_dir.is_dir():
        print("SKIP: 缺裁判产出（judge_blind/_mapping.json 或 judge_out/），无法取底分")
        return 0
    bmap = json.loads(blind_map_p.read_text(encoding="utf-8"))
    # level 名 → 作答文件里的 model 名（answers_flat 用的是 BLIND-weak 这种）
    bid = {(m["item_id"], m["level"]): m["blind_id"] for m in bmap}

    def judge_scores(iid: str, level: str) -> dict[str, int]:
        b = bid.get((iid, level))
        f = judge_dir / f"{b}.json" if b else None
        if not f or not f.is_file():
            return {}
        return {s["criterion_id"]: s["score"] for s in json.loads(f.read_text(encoding="utf-8"))["scores"]}

    tmp = Path(tempfile.mkdtemp(prefix="veribench-annchain-"))
    ok = True
    try:
        print("=== 1) 生成标注表（此前这一步是坏的：没有可评的作答）===")
        for who in ("A", "B"):
            rc, out = sh([sys.executable, str(HERE / "make_annotation_sheets.py"),
                          "--items", str(items_p), "--answers", str(ans_p),
                          "--outdir", str(tmp), "--annotator", who])
            last = out.splitlines()[-3:] if out else []
            print(f"  {'✅' if rc == 0 else '❌'} 标注者 {who}")
            for l in last:
                print(f"      {l}")
            ok = ok and rc == 0

        a_p, b_p = tmp / "ann_A.jsonl", tmp / "ann_B.jsonl"
        if not a_p.is_file():
            print("❌ 标注表没生成出来，链路断在这里")
            return 1

        # 表里必须真的有作答 —— 这正是上一轮修好的那一点，要断言住
        sheet = (tmp / "ann_A_sheet.md").read_text(encoding="utf-8")
        has_answers = sheet.count("### 回答") >= len(answers)
        print(f"  {'✅' if has_answers else '❌'} 标注表里含 {sheet.count('### 回答')} 段待评回答"
              f"（作答文件里有 {len(answers)} 份）")
        ok = ok and has_answers

        print("\n=== 2) 合成两位标注者（A=裁判第一轮分数；B=A 扰动 15%）===")
        rng = random.Random(args.seed)
        rows_a = [json.loads(l) for l in a_p.read_text(encoding="utf-8").splitlines() if l.strip()]
        n_filled = 0
        for r in rows_a:
            # answers_flat 里的 model 是 BLIND-weak 这种；映射回 level
            lvl = str(r["answer_id"]).split("-")[-1]
            sc = judge_scores(r["item_id"], lvl)
            v = sc.get(r["criterion_id"])
            if v is None:
                continue
            r["score"] = v
            n_filled += 1
        a_p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows_a),
                       encoding="utf-8")

        rows_b = []
        n_pert = 0
        for r in rows_a:
            r2 = dict(r)
            if r2["score"] is not None and rng.random() < args.perturb:
                # 挪一档（0↔1 或 1↔2），模拟"人类之间有分歧"
                r2["score"] = min(2, r2["score"] + 1) if rng.random() < 0.5 else max(0, r2["score"] - 1)
                n_pert += 1
            r2["annotator"] = "B"
            rows_b.append(r2)
        b_p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows_b),
                       encoding="utf-8")
        print(f"  A 填了 {n_filled}/{len(rows_a)} 条；B 在 A 基础上扰动 {n_pert} 条")
        if n_filled == 0:
            print("  ❌ 一条都没填上 —— 说明生成的模板与裁判产出对不上（链路断了）")
            return 1
        ok = ok and n_filled == len(rows_a)

        print("\n=== 3) --validate（漏填必须被发现，不能静默当 0）===")
        for who, p in (("A", a_p), ("B", b_p)):
            rc, out = sh([sys.executable, str(HERE / "make_annotation_sheets.py"), "--validate", str(p)])
            print(f"  {'✅' if rc == 0 else '❌'} 校验 {who}：{out.splitlines()[-1] if out else ''}")
            ok = ok and rc == 0

        # 故意挖一个空，验证"漏填会被抓出来"
        rows_a2 = [json.loads(l) for l in a_p.read_text(encoding="utf-8").splitlines() if l.strip()]
        rows_a2[0]["score"] = None
        hole = tmp / "ann_A_hole.jsonl"
        hole.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows_a2),
                        encoding="utf-8")
        rc, out = sh([sys.executable, str(HERE / "make_annotation_sheets.py"), "--validate", str(hole)])
        caught = rc != 0 and "未填" in out
        print(f"  {'✅' if caught else '❌'} 故意留 1 条空 → 校验{'抓到了' if caught else '**没抓到**'}")
        ok = ok and caught

        print("\n=== 4) kappa.py（人类之间的一致性）===")
        rc, out = sh([sys.executable, str(HERE / "kappa.py"), "--a", str(a_p), "--b", str(b_p)])
        print(f"  {'✅' if rc == 0 else '❌'} kappa 退出码 {rc}")
        for l in out.splitlines()[:8]:
            print(f"      {l}")
        ok = ok and rc == 0

        # 关键：一题多答必须被当成多个配对，而不是被压成一条
        n_rows = len(rows_a)
        pairs_ok = f"配对评分点：{n_rows}" in out
        print(f"  {'✅' if pairs_ok else '❌'} 配对数为 {n_rows}（= 评分点数）—— "
              f"若明显更少，说明 answer 维度又丢了")
        ok = ok and pairs_ok

        print("\n=== 5) judge_eval.py（裁判 vs 人类）===")
        arb = tmp / "arb.jsonl"
        # 拿 A 当金标准（仅演示链路，不代表真实仲裁）
        arb.write_text(a_p.read_text(encoding="utf-8"), encoding="utf-8")
        rc, out = sh([sys.executable, str(HERE / "judge_eval.py"),
                      "--items", str(items_p), "--ann-a", str(a_p), "--ann-b", str(b_p),
                      "--judge", str(b_p), "--arb", str(arb), "--out", str(tmp / "je.json")])
        print(f"  {'✅' if rc == 0 else '❌'} judge_eval 退出码 {rc}")
        for l in out.splitlines()[-6:]:
            print(f"      {l}")
        # 用 B 同时当 judge 是刻意的"自比"，必然一致 —— 这一步只验证链路能跑

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 68)
    if ok:
        print("✅ 人工标注链路端到端跑通：生成 → 填分 → 校验 → κ → 裁判对比")
        print()
        print("⚠️ 这只证明**管道通**，不证明任何标注质量。")
        print("   合成标注者的分数取自裁判本身，**不是人类数据**，不得引用。")
        print("   真正的 κ 仍然需要真人（见 annotation/pilot/README_FOR_ANNOTATOR.md）。")
        return 0
    print("❌ 链路有断点 —— **在请真人花 70 分钟之前必须先修好**。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
