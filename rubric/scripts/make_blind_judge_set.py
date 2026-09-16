#!/usr/bin/env python3
"""把三档答案的 judge 输入混成**档位不可辨**的一套，供裁判盲评。

为什么必须这样
--------------
如果裁判读到的文件名是 `judge_inputs_strong/R-0001.txt`，它就**知道这是"优秀答案"**。
那测出来的不是"标准能否区分好坏"，而是"裁判会不会顺着文件名给分"。
所以：

  1. 三档输入复制进同一个目录
  2. 文件名换成不可辨的散列 ID（不含 item_id、不含档位）
  3. **顺序打乱**（固定种子，可复现）
  4. 映射表写到单独的 `_mapping.json`，**裁判不得读它**，只由分析脚本使用

这样裁判只能看到"一篇题面 + 一份回答 + 评分标准"，与真实评测一致。

用法：
    python3 make_blind_judge_set.py --indirs ../fixtures/answers/judge_inputs_weak \
        ../fixtures/answers/judge_inputs_medium ../fixtures/answers/judge_inputs_strong \
        --outdir ../fixtures/answers/judge_blind --seed 20260913
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

LEVEL_OF_DIR = {"judge_inputs_weak": "weak", "judge_inputs_medium": "medium",
                "judge_inputs_strong": "strong"}


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="构造档位不可辨的 judge 输入集")
    ap.add_argument("--indirs", nargs="+", required=True)
    ap.add_argument("--levels", nargs="+",
                    help="与 --indirs 一一对应的档位（weak/medium/strong）。"
                         "不传就按目录名 `judge_inputs_<level>` 推断 —— "
                         "但依赖目录命名很脆，能显式传就显式传")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=20260913)
    args = ap.parse_args(argv)

    if args.levels and len(args.levels) != len(args.indirs):
        print(f"❌ --levels 有 {len(args.levels)} 个，--indirs 有 {len(args.indirs)} 个，必须一一对应")
        return 1
    level_list = args.levels or [LEVEL_OF_DIR.get(Path(d).name) for d in args.indirs]

    outdir = Path(args.outdir)
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)

    entries = []
    for d, level in zip(args.indirs, level_list):
        dp = Path(d)
        if level is None:
            print(f"❌ 无法判断 {dp.name} 的档位（目录名不是 judge_inputs_<level>，也没传 --levels）")
            return 1
        if level not in LEVEL_OF_DIR.values() and level not in ("plus", "minus"):
            # 主实验用 weak/medium/strong；操纵检验用 plus/minus（A+/A− 变体）。
            # 两者都只是**档位标签**，散列后裁判看不到。
            print(f"❌ 非法档位 {level!r}（允许 weak/medium/strong 或 plus/minus）")
            return 1
        files = sorted(dp.glob("*.txt"))
        for f in files:
            item_id = f.stem
            # 散列 ID：由 item_id+档位+种子决定，可复现，但**不可反推**
            h = hashlib.sha256(f"{item_id}|{level}|{args.seed}".encode()).hexdigest()[:12]
            entries.append({"blind_id": h, "item_id": item_id, "level": level, "src": f})

    rng = random.Random(args.seed)
    rng.shuffle(entries)

    for e in entries:
        shutil.copyfile(e["src"], outdir / f"{e['blind_id']}.txt")

    mapping = [{k: v for k, v in e.items() if k != "src"} for e in entries]
    (outdir / "_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8", newline="")

    # 泄漏检查：文件名里不能出现 item_id 或任何档位字样
    leaked = [p.name for p in outdir.glob("*.txt")
              if "R-0" in p.name or any(lv in p.name for lv in set(level_list))]
    print(f"盲评输入集：{len(entries)} 份 → {outdir}")
    print(f"  档位分布：{ {lv: sum(1 for e in entries if e['level'] == lv) for lv in sorted(set(level_list))} }")
    print(f"  文件名泄漏检查：{leaked or '无'}")
    print(f"  映射表 → {outdir / '_mapping.json'}（**裁判不得读取**，仅供分析脚本使用）")
    print(f"  顺序已按种子 {args.seed} 打乱（可复现）")
    return 1 if leaked else 0


if __name__ == "__main__":
    raise SystemExit(main())
