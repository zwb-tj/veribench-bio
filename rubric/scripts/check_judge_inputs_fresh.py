#!/usr/bin/env python3
"""检查**已提交的 judge 输入是否与当前 items 标准文本一致**。

为什么需要这个检查
------------------
2026-09 实测发现：`items_v1.2.jsonl` 里 R-0020 的 `c1` **标准描述句**被修订过
（提交 `0237494`）：

  旧：「…亚组仅约 27 人，**文中 P 值在 0.01–0.06 之间的结果是否经多重比较校正仍稳健不明**」
  新：「…亚组仅约 27 人，**多重比较校正与否会直接决定关键结果是否稳健**」

而 `fixtures/answers/judge_inputs_*/R-0020.txt` **从未重新生成** ——
三个档位目录里仍含**旧文本**。

⚠️ **但这个检查是"提醒"，不是"叫你去重新生成"。** 原因：
`judge_inputs_*/` 与 `judge_out/*.json` 是**一一对应的历史事实** ——
产物记录"当初喂进去的是什么"，产出记录"裁判据此打了什么"。
实测三档的 c1 `evidence` 里都出现了**旧锚点的措辞**（"校正范围""效应量"），
说明那些分数确实是按当时那份标准打出来的。

**重新生成产物会让历史输出与它的输入不再对应 —— 那是篡改历史，不是修复。**

所以正确处置是：**把脱节显式记录下来**（哪些产物用的是哪版标准），
并在新标准下**另跑一轮**，而不是覆盖旧的。

判据：只比较 `criterion_id` 的**描述句**；锚点（0/1/2 定义）单独核对。
（实测 R-0020 的锚点逐字符全等 —— 只有描述句变了。
 我第一版脚本误报"锚点也变了"，是切片解析的 bug，不是事实；
 这类自我更正必须记下来，否则会把不存在的差异当成发现。）

用法
----
    python3 check_judge_inputs_fresh.py            # 报告脱节（exit 1）
    python3 check_judge_inputs_fresh.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # rubric/
ITEMS = ROOT / "items" / "items_v1.2.jsonl"
JUDGE_DIRS = [
    "fixtures/answers/judge_inputs_weak",
    "fixtures/answers/judge_inputs_medium",
    "fixtures/answers/judge_inputs_strong",
]


def load_items() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for line in ITEMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out[d["item_id"]] = {c["criterion_id"]: c.get("text", "")
                             for c in (d.get("criteria") or [])}
    return out


#: **已知且已接受**的脱节：这些都是历史事实，不是待修项。
#: 每一条都要写清"为什么它是对的" —— 理由为空等于把检查关掉。
#:
#: ⚠️ 把它们列在这里**不是**为了让检查闭嘴，而是把"我们知道这里有分歧"
#:    变成一个**可审计的声明**：谁改了标准、旧分数是按哪版打的。
#:    如果将来有人加了**新的**脱节（不在这个清单里），检查会失败。
KNOWN_STALE: dict[str, str] = {
    "R-0020":
        "c1 的标准描述句在提交 0237494 被改写（旧：『文中 P 值在 0.01–0.06 之间的"
        "结果是否经多重比较校正仍稳健不明』→ 新：『多重比较校正与否会直接决定关键"
        "结果是否稳健』）。**未重新生成产物**，因为 judge_inputs_* 与 judge_out/*.json"
        "一一对应，是历史事实：实测三档 c1 的 evidence 都含旧措辞（『校正范围』"
        "『效应量』），说明那些分数确实按当时那份标准打的。重新生成会让历史输出"
        "与其输入不再对应。**正确处置是在新标准下另跑一轮，而不是覆盖。**",
}


def audit() -> tuple[list[str], list[str]]:
    """返回 (未预期的脱节, 已登记的脱节)。"""
    items = load_items()
    unexpected: list[str] = []
    known: list[str] = []
    for d in JUDGE_DIRS:
        p = ROOT / d
        if not p.is_dir():
            continue
        for f in sorted(p.glob("*.txt")):
            iid = f.stem
            if iid not in items:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            for cid, cur in items[iid].items():
                m = re.search(rf"^{re.escape(cid)}\.\s*(.+)$", text, re.M)
                if not m:
                    unexpected.append(f"{d}/{f.name}: 产物里找不到 {cid}")
                    continue
                if m.group(1).strip() != cur.strip():
                    msg = f"{d}/{f.name}: {cid} 标准描述句与当前 items 不同"
                    if iid in KNOWN_STALE:
                        known.append(msg)
                    else:
                        unexpected.append(msg)
    return unexpected, known


def self_test() -> int:
    """负向测试：**证明这个检查会失败**。"""
    ok = True
    print("=== judge 输入新鲜度自检 ===")

    items = load_items()
    cond = bool(items)
    ok = ok and cond
    print(f"  {'✅' if cond else '❌'} 能读到 items_v1.2（{len(items)} 题）")

    # 正向对照：拿一个**当前**标准文本拼一个假产物，必须判为"一致"
    iid = sorted(items)[0] if items else None
    if iid:
        good = "".join(f"{cid}. {txt}\n"
                       for cid, txt in items[iid].items())
        same = all(
            re.search(rf"^{re.escape(cid)}\.\s*(.+)$", good, re.M).group(1).strip()
            == cur.strip()
            for cid, cur in items[iid].items())
        ok = ok and same
        print(f"  {'✅' if same else '❌'} 正向：与当前文本一致的产物判为一致")

        # 负向：改一个字，必须判为不一致
        cid0 = sorted(items[iid])[0]
        tampered = good.replace(items[iid][cid0], items[iid][cid0] + "【改动】", 1)
        mm = re.search(rf"^{re.escape(cid0)}\.\s*(.+)$", tampered, re.M)
        diff = mm.group(1).strip() != items[iid][cid0].strip()
        ok = ok and diff
        print(f"  {'✅' if diff else '❌'} 负向：被改动的标准文本会被识破")

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="judge 输入是否与当前 items 一致")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--list", action="store_true", help="只列脱节点，不解释")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    unexpected, known = audit()

    if known:
        # 已知脱节：**报告但不失败** —— 它们是历史事实，不是待修项。
        print(f"ℹ️ {len(known)} 处**已登记**的标准描述句脱节（历史事实，不阻塞）：")
        for x in known[:6]:
            print(f"  · {x}")
        print("  （原因见 KNOWN_STALE；处置是在新标准下另跑一轮，不是覆盖旧产物）")
        if not args.quiet:
            print()

    if unexpected:
        print(f"❌ {len(unexpected)} 处**未登记**的脱节：")
        for x in unexpected[:20]:
            print(f"  · {x}")
        if args.list:
            return 1
        print()
        print("含义：这些产物是用旧标准生成的，而现在会拿新标准去解释它们。")
        print()
        print("⚠️ **先判断它是哪一类**：")
        print("  · 若产物是**过时中间物** → 用当前 items 重新生成")
        print("  · 若产物是**历史事实**（配对的裁判产出已存在）→ **不要覆盖**，")
        print("    而应像 R-0020 那样登记进 KNOWN_STALE 并在新标准下另跑一轮")
        return 1

    if not args.quiet:
        n = sum(len(list((ROOT / d).glob('*.txt'))) for d in JUDGE_DIRS if (ROOT / d).is_dir())
        print(f"✅ {n} 个 judge 输入已核对；{len(known)} 处已登记脱节（历史事实）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
