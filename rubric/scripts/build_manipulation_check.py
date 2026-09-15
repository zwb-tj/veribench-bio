#!/usr/bin/env python3
"""造"操纵检验"（manipulation check）的输入：逐条标准、而不是整体质量。

为什么要换掉原来的设计
----------------------
原来的区分度检验用「浅/中/优」三档答案，测"标准能否追踪**总体质量**"。
但档位是子agent 对**整份答案**的判断，不是逐条标准的——实测有 3 条标准上
**浅档答到了、优档反而没答到**（R-0003/c3、R-0011/c4、R-0012/c4）。
所以 `weak < medium < strong` 不是一个合法的逐条效度判据。

正确的问题是：
> **这条标准对"它自己声称要测的那个东西"敏感吗？**

检验方法（操纵检验 / manipulation check）：
  对某条标准 X，拿同一道题的同一份答案，做**最小改动**得到两份：

    A+  X 所要求的那个要素**明确存在**
    A−  同一份答案，**只把该要素拿掉**（其余一字不动）

  然后让裁判盲评这两份。若 A+ 的得分 > A−，说明 X **确实对它自己的维度敏感**；
  若两者同分，说明 X 分不出这个差别——**这条标准没有在测它声称要测的东西**。

这个设计**天然是逐条的**，不依赖任何整体质量标签，从根上消掉了那个混淆。

对照组是关键
------------
只测"坏"标准看不出检验本身是否有问题。所以同时抽一批**两轮都判为 healthy**
的标准做**对照**：它们理应通过操纵检验。如果对照组也大量不通过，
那说明**是检验不成立**，不能据此判标准有罪——这正是上一轮教训的推广
（"先证明检验能区分好坏，再用它定罪"）。

用法：
    python3 build_manipulation_check.py --out ../fixtures/answers/manip_plan.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LEVELS = ["weak", "medium", "strong"]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="生成操纵检验计划")
    ap.add_argument("--n-controls", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20260915)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    tri = json.loads((ROOT / "fixtures" / "answers" / "defect_triage.json")
                     .read_text(encoding="utf-8"))["rows"]
    retest = json.loads((ROOT / "fixtures" / "answers" / "v1.1" / "retest.json")
                        .read_text(encoding="utf-8"))
    items = {json.loads(l)["item_id"]: json.loads(l)
             for l in (ROOT / "items" / "items_v1.1.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()}
    # 取"优"档答案作为底本：它在细节上最丰富，便于做最小改动
    mapping = json.loads((ROOT / "fixtures" / "answers" / "v1.1" / "judge_blind" /
                          "_mapping.json").read_text(encoding="utf-8"))
    strong_bid = {m["item_id"]: m["blind_id"] for m in mapping if m["level"] == "strong"}
    answers = {}
    for l in (ROOT / "fixtures" / "answers" / "answers_blind_1.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            answers[r["item_id"]] = next(a["text"] for a in r["answers"] if a["answer_id"] == "strong")
    for l in (ROOT / "fixtures" / "answers" / "answers_blind_2.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            answers[r["item_id"]] = next(a["text"] for a in r["answers"] if a["answer_id"] == "strong")

    # 目标组：16 条确认缺陷
    targets = [{"item_id": r["item_id"], "criterion_id": r["criterion_id"],
                "group": "defect", "class": r["class"], "run1": r["run1"], "run2": r["run2"]}
               for r in tri]

    # 对照组：从 discrimination.json 取 —— ⚠️ 不能用 retest.json 的 criteria_detail，
    # 那是**筛过的**（只留 saturated/inverted），里面永远没有 healthy 条目。
    # 我第一版就踩了这个坑，打印出"对照组 0 条"才发现。
    disc = json.loads((ROOT / "fixtures" / "answers" / "v1.1" / "discrimination.json")
                      .read_text(encoding="utf-8"))
    healthy = [c for c in disc["criteria"] if c["verdict"] == "healthy"]
    rng = random.Random(args.seed)
    rng.shuffle(healthy)
    controls = [{"item_id": d["item_id"], "criterion_id": d["criterion_id"],
                 "group": "control", "class": "healthy",
                 "run1": [d["weak"], d["medium"], d["strong"]], "run2": None}
                for d in healthy[: args.n_controls]]
    print(f"（v1.1 单轮 healthy 标准共 {len(healthy)} 条，抽 {len(controls)} 条做对照）")

    plan = []
    for spec in targets + controls:
        iid, cid = spec["item_id"], spec["criterion_id"]
        it = items.get(iid)
        if not it:
            continue
        crit = next((c for c in it["criteria"] if c["criterion_id"] == cid), None)
        if not crit:
            continue
        plan.append({
            **spec,
            "criterion_text": crit["text"],
            "anchors": crit["anchors"],
            "base_answer": answers.get(iid, ""),
        })

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"操纵检验计划：{len(plan)} 条标准")
    print(f"  目标组（确认缺陷）: {sum(1 for p in plan if p['group'] == 'defect')} 条")
    print(f"  对照组（两轮 healthy）: {sum(1 for p in plan if p['group'] == 'control')} 条")
    print(f"  涉及题目: {len({p['item_id'] for p in plan})} 道")
    print(f"→ {op}")
    print()
    print("下一步：写 A+/A− 变体（每条约 300 字，最小改动）→ 盲评两轮 → 看 A+ 是否 > A−")
    if not plan or any(not p["base_answer"] for p in plan):
        print("⚠️ 有条目缺底本答案")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
