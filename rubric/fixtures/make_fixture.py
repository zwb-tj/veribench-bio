#!/usr/bin/env python3
"""为第二支柱生成**测试夹具**（fixtures）。

⚠️ 重要区分：这些是**用来验证工具链的夹具，不是评测题**。
   真实题目必须来自 PMC OA 的 CC0 / CC BY 论文（见 SPEC §6），
   并且必须逐题过泄露与结构检查。把夹具当真题发布是绝对不能做的。

夹具的作用：在真题目还没写出来之前，先证明
   生成标注表 → 双盲标注 → κ → 仲裁 → judge 元评测
这条链条能跑通、数字算得对、失效案例收集得到。

用法：
    python3 make_fixture.py --outdir . --n-items 40 --seed 7
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

TOPICS = [
    "差异表达分析中批次效应与生物学效应的区分",
    "单细胞聚类分辨率的选择依据",
    "变异致病性判读中人群频率证据的使用",
    "宏基因组物种组成结果的解释边界",
    "蛋白结构预测结果的可靠性评估",
    "多组学整合分析中数据一致性的检验",
]

CRITERIA_TEMPLATES = [
    ("c1", "是否明确指出了所依据的具体证据类型（而非泛泛而谈）",
     "未提及任何具体证据类型", "提到证据类型但未说明它如何支持结论", "明确指出证据类型并说明其与结论的逻辑关系"),
    ("c2", "是否说明了该方法或结论的适用条件与局限",
     "未提及任何适用条件或局限", "提到局限但未说明其影响", "说明局限并解释它对结论强度的影响"),
    ("c3", "是否给出了可被他人复现的具体做法或参数",
     "未给出任何可操作细节", "给出部分参数但不足以复现", "给出的参数与步骤足以被他人复现"),
]


def make_items(n: int, rng: random.Random) -> list[dict]:
    items = []
    for i in range(n):
        topic = TOPICS[i % len(TOPICS)]
        k = i % 3  # 让不同题使用不同数量的标准（3/4/5）
        ncrit = 3 + k
        crits = []
        for cid, text, a0, a1, a2 in CRITERIA_TEMPLATES[:ncrit]:
            crits.append({
                "criterion_id": cid,
                "text": f"{text}（针对：{topic}）",
                "anchors": {"0": a0, "1": a1, "2": a2},
            })
        items.append({
            "item_id": f"R-{i:04d}",
            "question": f"在一项涉及「{topic}」的分析中，研究者得到了一个显著结果。"
                        f"请说明你会如何评估这个结果的可信度，并指出需要哪些额外证据。",
            "context": "（夹具背景，非真实论文）",
            "criteria": crits,
            "provenance": {
                "source_type": "synthetic",
                "source_ref": f"FIXTURE-{i:04d}",
                "source_license_code": "n/a（夹具，非真实数据）",
                "license_spdx": "CC0-1.0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "retrieval_date": "2026-09-12",
                "redistribution_ok": True,
                "commercial_ok": True,
                "contains_human_data": False,
                "contains_restricted_data": False,
                "visibility": "internal",
                "derivation_note": "程序化生成，用于验证工具链；**不得作为评测题发布**",
            },
            "safety_review": "not-applicable",
        })
    return items


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="生成第二支柱测试夹具")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--n-items", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    items = make_items(args.n_items, rng)
    with (out / "sample_items.jsonl").open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")

    # --- 构造四份标注，模拟一条真实的（有瑕疵的）标注流程 ---------------------
    # 真值：每题每条标准的"应得分"（夹具里由程序给定，不是人类判断）
    truth = {}
    for it in items:
        for c in it["criteria"]:
            truth[(it["item_id"], c["criterion_id"])] = rng.choice([0, 1, 2])

    def perturb(base: dict, agree_p: float, rng: random.Random) -> dict:
        out_d = {}
        for k, v in base.items():
            if rng.random() < agree_p:
                out_d[k] = v
            else:
                out_d[k] = max(0, min(2, v + rng.choice([-1, 1])))
        return out_d

    ann_a = perturb(truth, 0.82, rng)          # 标注者 A：与"应得分"82% 一致
    ann_b = perturb(truth, 0.78, rng)          # 标注者 B：略低
    arb = perturb(truth, 0.95, rng)            # 仲裁：接近应得分
    # judge：整体偏松，且有少量大错
    judge = {}
    for k, v in arb.items():
        if rng.random() < 0.12:
            judge[k] = max(0, min(2, v + rng.choice([-2, 2])))   # 大错
        elif rng.random() < 0.35:
            judge[k] = min(2, v + 1)                             # 偏松
        else:
            judge[k] = v

    def dump(name: str, d: dict) -> None:
        with (out / name).open("w", encoding="utf-8") as fh:
            for (iid, cid), s in sorted(d.items()):
                fh.write(json.dumps({"item_id": iid, "criterion_id": cid, "score": s},
                                    ensure_ascii=False) + "\n")

    dump("fixture_ann_A.jsonl", ann_a)
    dump("fixture_ann_B.jsonl", ann_b)
    dump("fixture_arb.jsonl", arb)
    dump("fixture_judge.jsonl", judge)

    print(f"已生成到 {out}：")
    print(f"  sample_items.jsonl   {len(items)} 题 / {len(truth)} 个评分点")
    print(f"  fixture_ann_A.jsonl  （模拟标注者 A）")
    print(f"  fixture_ann_B.jsonl  （模拟标注者 B）")
    print(f"  fixture_arb.jsonl    （模拟仲裁金标准）")
    print(f"  fixture_judge.jsonl  （模拟 judge：偏松 + 少量大错）")
    print("\n⚠️ 这些是**夹具**，只用于验证工具链，不得作为评测题发布。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
