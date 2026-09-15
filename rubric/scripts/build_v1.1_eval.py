#!/usr/bin/env python3
"""一条命令搭出 v1.1 的评判输入（复用 v1.0 那 72 份答案）。

为什么能复用答案
----------------
那 72 份答案是在**看不到 v1.0 评分标准**的条件下写的，自然也没见过 v1.1 的。
所以它们对两版都是"盲"的，可以直接拿来做前后对照——**同答案、同题目，只换 criteria**。

这一步做四件事：
  1. 摊平嵌套答案 → 每档一个文件
  2. 用 **v1.1 的 items** 构造 judge 输入（提示词里会带 v1.1 的标准）
  3. 用**新种子**混成档位不可辨的一套散列名输入（避免与 v1.0 的盲评集重叠）
  4. 把映射表单独落盘（裁判不得读）

跑完把 `judge_blind` 交给裁判，输出到 `judge_out_run1`/`judge_out_run2`，
再跑 `judge_discrimination.py` + `judge_retest.py` + `compare_rubric_versions.py`。

用法：
    python3 build_v1.1_eval.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = sys.executable

ANSWERS = [
    ROOT / "fixtures" / "answers" / "answers_blind_1.jsonl",
    ROOT / "fixtures" / "answers" / "answers_blind_2.jsonl",
]
ITEMS_V11 = ROOT / "items" / "items_v1.1.jsonl"
OUT = ROOT / "fixtures" / "answers" / "v1.1"
LEVELS = ["weak", "medium", "strong"]


def run(cmd: list[str]) -> None:
    print(f"\n$ {' '.join(Path(c).name for c in cmd)}")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [l for l in (p.stdout or "").strip().splitlines() if l.strip()]
    for l in tail[-6:]:
        print("   " + l)
    if p.returncode != 0:
        for l in (p.stderr or "").strip().splitlines()[-6:]:
            print("   ! " + l)
        raise SystemExit(f"命令失败（退出码 {p.returncode}）：{' '.join(cmd)}")


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    if not ITEMS_V11.is_file():
        print(f"❌ 找不到 {ITEMS_V11}——改写批次还没合并")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    indirs = []
    for lv in LEVELS:
        flat = OUT / f"flat_{lv}.jsonl"
        run([PY, str(HERE / "flatten_answers.py"), "--in", *[str(a) for a in ANSWERS],
             "--out", str(flat), "--only-level", lv])
        jd = OUT / f"judge_inputs_{lv}"
        run([PY, str(HERE / "build_judge_inputs.py"), "--items", str(ITEMS_V11),
             "--answers", str(flat), "--outdir", str(jd)])
        indirs.append(jd)

    # ⚠️ 必须换种子：否则散列 ID 与 v1.0 完全相同，而 v1.0 的输出已经落盘，
    #    裁判可能"认出"同一份输入而受上一轮印象影响。
    run([PY, str(HERE / "make_blind_judge_set.py"), "--indirs", *[str(d) for d in indirs],
         "--levels", *LEVELS,
         "--outdir", str(OUT / "judge_blind"), "--seed", "20260914"])

    print("\n✅ v1.1 评判输入就绪。下一步：")
    print(f"   把 {OUT / 'judge_blind'} 下的 72 个 .txt 交给裁判（分 6 批，各 12 份），")
    print("   输出到 judge_out_run1 / judge_out_run2（**两轮**，否则与 v1.0 比较不公平）")
    print("   然后：judge_discrimination.py → judge_retest.py → compare_rubric_versions.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
