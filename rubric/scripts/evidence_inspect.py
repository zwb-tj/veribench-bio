#!/usr/bin/env python3
"""对"改措辞可能无效"的那些标准，用裁判的 evidence 原文判定：到底能不能靠改措辞救回来。

决定性问题
----------
一条标准若中档与优档得分相同（比如都是 1），改锚点措辞能不能把它们分开？
**取决于回答本身在这一维度上有没有差别。**

  情形 (a) 中档"只泛泛提到"，优档"点出了具体缺陷但没写后果"
           → 把 2 分改成"点名即满分"，两者就会分开（1 vs 2）→ **改措辞有效**
  情形 (b) 中档与优档**都**"点出了缺陷但没写后果"
           → 改完两条都变 2，**还是分不开** → 改措辞无效

分数本身分不出 (a) 和 (b)，但**裁判写的 evidence 能**：
它逐条记录了给该分时回答里写了什么。所以直接把两档的 evidence 并排读出来。

用法：
    python3 evidence_inspect.py --triage ../fixtures/answers/defect_triage.json
"""

from __future__ import annotations

import argparse
import json
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

    ap = argparse.ArgumentParser(description="按 evidence 判定改措辞是否可行")
    ap.add_argument("--triage", required=True)
    ap.add_argument("--version", default="v1.1")
    ap.add_argument("--all-classes", action="store_true",
                    help="连 V1 一起看。⚠️ 必须看 V1：反向型里有相当一部分不是标准坏了，"
                         "而是**我的答案档位标签对它不适用**（见下）")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    tri = json.loads(Path(args.triage).read_text(encoding="utf-8"))["rows"]
    targets = tri if args.all_classes else [r for r in tri if r["class"] in ("V2", "V3")]
    base = ROOT / "fixtures" / "answers" / ("v1.1" if args.version == "v1.1" else "")
    mapping = json.loads((base / "judge_blind" / "_mapping.json").read_text(encoding="utf-8"))
    idx = {(m["item_id"], m["level"]): m["blind_id"] for m in mapping}

    out = []
    for r in targets:
        iid, cid = r["item_id"], r["criterion_id"]
        print("=" * 78)
        print(f"{iid}/{cid}   run1 {r['run1']}  run2 {r['run2']}  [{r['verdict']}]")
        ev = {}
        for lv in LEVELS:
            bid = idx.get((iid, lv))
            f = base / "judge_out_run1" / f"{bid}.json"
            if not f.is_file():
                continue
            for s in json.loads(f.read_text(encoding="utf-8"))["scores"]:
                if s["criterion_id"] == cid:
                    ev[lv] = s.get("evidence", "")
        for lv in LEVELS:
            if lv in ev:
                print(f"  [{lv:6}] {ev[lv][:210]}")
        # 判定：中档与优档的 evidence 是否描述了不同的"写了什么"
        m, s_ = ev.get("medium", ""), ev.get("strong", "")
        w = ev.get("weak", "")
        # ⚠️ 头号混淆：我的"浅/中/优"是**整份答案**的总体质量标签，
        #    不是逐条标准的。所以完全可能"浅"答案在某条标准上答得比"优"好。
        #    这种情况下 weak ≥ strong 说明**我的测试对该条不适用**，
        #    不能据此判定标准有缺陷。
        weak_positive = ("明确" in w or "指出" in w) and "未涉及" not in w
        strong_negative = "未涉及" in s_
        mentions_consequence = any(k in s_ for k in ("后果", "影响", "因此", "使结论", "不成立", "高估"))
        medium_vague = any(k in m for k in ("泛泛", "笼统", "未涉及", "只提", "没有具体"))
        if weak_positive and strong_negative:
            verdict = ("⚠️ **测试对该条不适用**：浅档 evidence 显示它答到了，"
                       "而优档判「未涉及」——说明档位标签与这条标准的维度不对齐，"
                       "不是标准有缺陷")
        elif mentions_consequence:
            verdict = "可能有效（优档 evidence 里已含后果表述，说明两档写得不同）"
        elif medium_vague:
            verdict = "需人工读原文（中档被判为笼统，优档不是 → 两档可能确有差别）"
        else:
            verdict = "**多半无效**（两档 evidence 描述相近，改措辞只会一起升降）"
        print(f"  → {verdict}")
        out.append({"item_id": iid, "criterion_id": cid, "run1": r["run1"], "run2": r["run2"],
                    "class": r["class"], "evidence": ev, "verdict": verdict})
        print()

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8", newline="")
    n_futile = sum(1 for o in out if "多半无效" in o["verdict"])
    print(f"共 {len(out)} 条；其中 {n_futile} 条的 evidence 显示改措辞多半无效")
    print(f"→ {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
