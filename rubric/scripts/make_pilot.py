#!/usr/bin/env python3
"""生成**试点标注包** —— 把"人手标注"从 303 个评分点缩到 ~72 个。

为什么需要缩
------------
第三支柱声明的硬阻塞是"两位真人标注"。但先把量级摊开看：
全量是 **24 题 × 3 份回答 × ~4.2 条标准 = 303 个评分点**。
一个人认真做完要好几小时 —— 这种量级的请求，实际结果是**永远不会被做**。

所以先做一个**试点**：够算出 κ（含 95% CI），但一次坐得完。

选样原则：**不加挑选**
------------------------
取 `R-0001..R-0006`（题号最前的 6 道），**不按"哪几道好看"来选**。
理由：如果试点专挑判别力好的题，算出来的 κ 会偏乐观，
而试点本来就是为了在投入全量之前发现"这套标准到底能不能被人一致地读"。
**为结果好看而选样，正是这个项目一直在避免的事。**

每题给 **3 份回答**（浅/中/优），不是 1 份 —— 因为如果全给"优"，
人可能全打 2 分，方差为零，κ 在数学上无定义。

用法：
    python3 make_pilot.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent          # rubric/
PILOT_DIR = ROOT / "annotation" / "pilot"
N_ITEMS = 6


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    items_path = ROOT / "items" / "items_v1.2.jsonl"
    answers_path = ROOT / "fixtures" / "answers" / "answers_flat.jsonl"
    for p in (items_path, answers_path):
        if not p.is_file():
            print(f"❌ 缺 {p}")
            return 1

    items = [json.loads(l) for l in items_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    pilot = sorted(items, key=lambda r: r["item_id"])[:N_ITEMS]
    keep = {r["item_id"] for r in pilot}

    PILOT_DIR.mkdir(parents=True, exist_ok=True)
    pit = PILOT_DIR / "items.jsonl"
    pit.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in pilot), encoding="utf-8")

    ans = [json.loads(l) for l in answers_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    pans = [a for a in ans if a["item_id"] in keep]
    pat = PILOT_DIR / "answers.jsonl"
    pat.write_text("".join(json.dumps(a, ensure_ascii=False) + "\n" for a in pans), encoding="utf-8")

    n_crit = sum(len(r["criteria"]) for r in pilot)
    # ⚠️ 不能写成长度相乘（`总标准数 × 总回答数`）—— 每份回答只跟**它自己那题**的标准配对。
    #    第一版就是那么算的，报出 432，而真实是 72。
    n_units = sum(len(r["criteria"]) * sum(1 for a in pans if a["item_id"] == r["item_id"])
                  for r in pilot)
    print(f"试点：{len(pilot)} 题（{sorted(keep)}）")
    print(f"  标准数 {n_crit} · 每题的作答 {sorted({sum(1 for a in pans if a['item_id'] == r['item_id']) for r in pilot})} 份")
    print(f"  → **{n_units} 个评分点**（= 各题「标准数 × 该题回答数」之和）")
    print(f"  题面 → {pit}")
    print(f"  作答 → {pat}")

    rc = 0
    for who in ("A", "B"):
        p = subprocess.run(
            [sys.executable, str(HERE / "make_annotation_sheets.py"),
             "--items", str(pit), "--answers", str(pat),
             "--outdir", str(PILOT_DIR), "--annotator", who],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = [l for l in (p.stdout or "").strip().splitlines() if l.strip()][-4:]
        for l in tail:
            print(f"  [{who}] {l}")
        rc = rc or p.returncode

    print()
    print("下一步（**需要两个真人**）：")
    print(f"  1. 标注者 A 读 {PILOT_DIR / 'ann_A_sheet.md'}，填 {PILOT_DIR / 'ann_A.jsonl'}")
    print(f"  2. 标注者 B 读 {PILOT_DIR / 'ann_B_sheet.md'}，填 {PILOT_DIR / 'ann_B.jsonl'}")
    print("     **两人互不可见对方的分数** —— 这是「独立标注」的意思")
    print("  3. 校验：python3 make_annotation_sheets.py --validate annotation/pilot/ann_A.jsonl")
    print("  4. 算 κ：python3 kappa.py --a annotation/pilot/ann_A.jsonl "
          "--b annotation/pilot/ann_B.jsonl")
    print("  5. 有分歧的条目交第三方仲裁，再跑 judge_eval.py 把裁判与人类对比")
    print()
    print("⚠️ 只有一位真人时也能先用：")
    print("   · 你单独标 A 即可算出**裁判 vs 人类**的一致性（这是一个真实可报的数）")
    print("   · 但**人类天花板**（人类 vs 人类）必须两个人 —— 那是相对值的分母")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
