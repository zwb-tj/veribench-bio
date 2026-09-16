#!/usr/bin/env python3
"""生成 v1.2：**v1.0 + 一个可核验的修复**，别的都不动。

为什么回到 v1.0 而不是用 v1.1
-----------------------------
v1.1 改了 96/101 条标准。那些改动的动机是"区分度检验发现的缺陷"，
而那个检验后来被证明**测错了东西**（它的档位标签是整份答案的，不是逐条标准的，
见 SPEC §13.3i）。操纵检验（§13.3k）显示那些标准**本来就没坏**。

所以 v1.1 里绝大多数改动是**没有证据支撑**的。对一份以"可证明没编造"
为卖点的基准来说，带着 96 处未经验证的修改发布，本身就是一种不诚实。

**原则：每一处改动都要能指向一个可核验的缺陷。**

目前能核验的缺陷只有 1 个：

  R-0020/c1 的标准**正文**写"文中 P 值在 0.01–0.06 之间"，
  但题面从头到尾没给任何 p 值 → 裁判无法核实该要件 → 该档不可判（R2 违例）。
  （另有一个次要问题：该论文实际用了 Holm–Bonferroni 校正，
   所以"未校正"这个暗示本身也与事实不符。）

修法：把该 p 值区间删掉，保留"检验数量 vs 亚组规模"这一实质要求。

v1.1 也修了这一条，且修法等价 —— 这一处 v1.1 是对的。

用法：
    python3 make_v1.2.py --out ../items/items_v1.2.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# 每处改动都必须写明：改什么、为什么、依据哪个可核验的检查。
FIXES: list[dict] = [
    {
        "item_id": "R-0020",
        "criterion_id": "c1",
        "old_text": "是否指出 7 个标志物 × 多组比较再加亚组分析构成大量检验，"
                    "而亚组仅约 27 人，文中 P 值在 0.01–0.06 之间的结果是否经多重比较校正仍稳健不明",
        "new_text": "是否指出 7 个标志物 × 多组比较再加亚组分析构成大量检验，"
                    "而亚组仅约 27 人，多重比较校正与否会直接决定关键结果是否稳健",
        "reason": "正文断言『文中 P 值在 0.01–0.06 之间』，但题面未给任何 p 值 → "
                  "裁判无法核实（R2 违例，由 check_anchor_grounding.py 检出）。"
                  "另：该论文实际使用 Holm–Bonferroni 校正，原表述暗示『未校正』亦与事实不符。",
        "check": "check_anchor_grounding.py",
    },
]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="生成 v1.2")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    rows = [json.loads(l) for l in (ROOT / "items" / "items.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]

    applied = 0
    for fix in FIXES:
        for it in rows:
            if it["item_id"] != fix["item_id"]:
                continue
            it["rubric_version"] = "1.2"
            for c in it["criteria"]:
                if c["criterion_id"] != fix["criterion_id"]:
                    continue
                if c["text"] != fix["old_text"]:
                    print(f"❌ {fix['item_id']}/{fix['criterion_id']}: 原文与预期不符，"
                          f"拒绝改写（fail-closed）")
                    print(f"   实际：{c['text'][:90]}")
                    return 1
                c["text"] = fix["new_text"]
                c["revision_note"] = f"v1.2：{fix['reason']}（依据 {fix['check']}）"
                applied += 1

    if applied != len(FIXES):
        print(f"❌ 只应用了 {applied}/{len(FIXES)} 处修改")
        return 1

    # 未改动的题目也要标版本，否则无法区分"看过且没改"与"没看过"
    for it in rows:
        it.setdefault("rubric_version", "1.2")

    op = Path(args.out)
    op.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="")
    print(f"✅ v1.2 生成：{len(rows)} 题 / "
          f"{sum(len(r['criteria']) for r in rows)} 条标准 → {op}")
    print(f"   改动 {applied} 处（每一处都有可核验依据）：")
    for fix in FIXES:
        print(f"     {fix['item_id']}/{fix['criterion_id']}  依据 {fix['check']}")
    print()
    print("   相对 v1.0：只动这一处。相对 v1.1：撤销 95 处无证据支撑的改写。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
