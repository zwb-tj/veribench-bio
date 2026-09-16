#!/usr/bin/env python3
"""每条缺陷标准到底该改什么？——按"答案里有没有方差"分成三类，避免无效改写。

为什么必须先分这一刀
--------------------
上一轮我打算"把 1↔2 的两种写法各测一遍，用数据替人选"。但有个前提没验：
**如果某一档标准上，中档答案与优档答案表现得一样，那任何锚点措辞都分不开它们。**

举例：某条标准两轮恒为 1（饱和在中间档）。若"中"和"优"都点出了缺陷、
都没写后果，那么：
  · 政策 A（点名即满分）→ 两条都变 2，还是分不开
  · 政策 B（必须写后果）→ 两条都还是 1，还是分不开

**改措辞没用。** 问题不在锚点，在这条标准考的东西上，所有答案水平都一样。
这时候只有两条出路：把该标准**改挂到一个答案之间有差异的维度**上，或**删掉**。

所以本脚本把每条缺陷按"答案方差"分三类，每类对应完全不同的动作：

  · V1 「中≠优」有方差 → 锚点措辞问题 → 值得改写（且要按漂移边界改对应档）
  · V2 「中=优」无方差 → 标准考错了维度 → 改措辞无效，须换维度或删除
  · V3 「恒为 0」无人能得 → 该档不可达 → 检查题面推不出 / 锚点自相矛盾

用法：
    python3 defect_triage.py --out ../fixtures/answers/defect_triage.json
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

    ap = argparse.ArgumentParser(description="缺陷标准分类")
    ap.add_argument("--version", default="v1.1", choices=["v1.0", "v1.1"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    base = ROOT / "fixtures" / "answers" / ("" if args.version == "v1.0" else "v1.1")
    retest = json.loads((base / "retest.json").read_text(encoding="utf-8"))
    disc = json.loads((base / "discrimination.json").read_text(encoding="utf-8"))
    items = {json.loads(l)["item_id"]: json.loads(l)
             for l in (ROOT / "items" / ("items.jsonl" if args.version == "v1.0" else "items_v1.1.jsonl")
                       ).read_text(encoding="utf-8").splitlines() if l.strip()}
    bp = ROOT / "fixtures" / "answers" / "boundary_analysis.json"
    bnd_all = json.loads(bp.read_text(encoding="utf-8")) if bp.is_file() else {}
    bnd = {}
    if args.version in bnd_all:
        v = bnd_all[args.version]
        for d in v.get("details_mid_hi", []):
            bnd[f"{d['item_id']}/{d['criterion_id']}"] = "1↔2"
        for d in v.get("details_0_to_1", []):
            k = f"{d['item_id']}/{d['criterion_id']}"
            bnd[k] = "1↔2 & 0↔1" if k in bnd else "0↔1"

    defects = [d for d in retest["criteria_detail"] if d["reproduced"]]

    # 读裁判 evidence —— 判"改措辞到底有没有用"的唯一依据。
    # 分数只说明"两档同分"，说不出原因；evidence 记录了给分时回答写了什么。
    mapping = json.loads((base / "judge_blind" / "_mapping.json").read_text(encoding="utf-8"))
    idx = {(m["item_id"], m["level"]): m["blind_id"] for m in mapping}

    def evidence(iid: str, cid: str, lv: str) -> str:
        bid = idx.get((iid, lv))
        if not bid:
            return ""
        f = base / "judge_out_run1" / f"{bid}.json"
        if not f.is_file():
            return ""
        for sc in json.loads(f.read_text(encoding="utf-8"))["scores"]:
            if sc["criterion_id"] == cid:
                return sc.get("evidence", "")
        return ""

    rows = []
    for d in defects:
        w, m, s = d["run1"]
        key = f"{d['item_id']}/{d['criterion_id']}"
        ew = evidence(d["item_id"], d["criterion_id"], "weak")
        em = evidence(d["item_id"], d["criterion_id"], "medium")
        es = evidence(d["item_id"], d["criterion_id"], "strong")

        # ① 先查我自己的检验是否对该条不适用：浅档答到了、优档却判「未涉及」
        if ("未涉及" not in ew and ew.strip() and "未涉及" in es):
            cls = "T"
            action = "**检验误报**：档位标签与这条的维度不对齐 —— 不能据此判定标准有缺陷"
        # ② 再查改措辞有没有用：中档与优档是否描述了相同的"写了什么"
        elif len(set(d["run1"])) == 1 and d["run1"][0] == 0:
            cls, action = "V3", "恒为 0：该档不可达 → 查是否依赖题面推不出的事实；否则删除"
        elif m == s and em and es and not any(
                k in es for k in ("后果", "影响", "因此", "使结论", "不成立", "高估")):
            cls, action = "V2", "两档 evidence 描述相近 → **改措辞多半无效**，须换挂维度或删除"
        elif len(set(d["run1"])) == 1:
            fixed = d["run1"][0]
            cls = "V2"
            action = ("恒为 2：标准太容易，三档都答到 → 提高门槛或删除"
                      if fixed == 2 else
                      "三档同分 → 该标准不追踪总体质量，须换挂维度或删除")
        else:
            cls, action = "V1", "有方差 → 按漂移边界改对应档锚点（唯一真正值得改措辞的一类）"
        rows.append({"item_id": d["item_id"], "criterion_id": d["criterion_id"],
                     "run1": d["run1"], "run2": d["run2"],
                     "verdict": d["verdict_run1"], "boundary": bnd.get(key, "（两轮同分，无边界分歧）"),
                     "class": cls, "action": action,
                     "evidence": {"weak": ew, "medium": em, "strong": es}})

    print(f"=== {args.version} 确认缺陷 {len(rows)} 条，按**可修性**分类 ===")
    print()
    for cls, label in [
        ("T", "T **检验误报** → 不是 rubric 缺陷，是我的档位标签不对齐"),
        ("V1", "V1 有方差 → 改锚点措辞有效（按漂移边界改对应档）"),
        ("V2", "V2 无方差/太容易 → **改措辞无效**，须换挂维度或删除"),
        ("V3", "V3 恒为 0 → 该档不可达，查题面/锚点矛盾，否则删除"),
    ]:
        rs = [r for r in rows if r["class"] == cls]
        print(f"--- {label}：{len(rs)} 条 ---")
        for r in rs:
            print(f"   {r['item_id']}/{r['criterion_id']}  run1 {r['run1']} run2 {r['run2']}"
                  f"  [{r['verdict']}]  边界 {r['boundary']}")
        print()

    futile = [r for r in rows if r["class"] in ("V2", "V3", "T")]
    print("=" * 70)
    print(f"**{len(futile)}/{len(rows)} 条（{len(futile) / len(rows) * 100:.0f}%）改措辞拿不到收益**")
    print(f"  其中 {sum(1 for r in rows if r['class'] == 'T')} 条是我自己的检验误报，")
    print(f"  {sum(1 for r in rows if r['class'] in ('V2', 'V3'))} 条是标准考的东西上各档无差别。")
    print("  继续在措辞上打转 = 对噪声调参。")
    fixable = [r for r in rows if r["class"] == "V1"]
    print(f"\n  真正值得改措辞的只有 {len(fixable)} 条："
          f"{'、'.join(r['item_id'] + '/' + r['criterion_id'] for r in fixable) or '（无）'}")
    if len(futile) > len(rows) * 0.5:
        print("\n  ⚠️ 结论：这套合成答案能给的信号已接近取尽。")
        print("     要再往前走，需要的是**真人标注**（SPEC §13.2），不是又一轮措辞调整。")

    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps({"version": args.version, "rows": rows}, ensure_ascii=False, indent=2),
                  encoding="utf-8", newline="")
    print(f"\n明细 → {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
