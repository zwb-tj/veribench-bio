#!/usr/bin/env python3
"""判定性检查：重跑 rubric 套件，产物是否**逐字节相同**？

为什么需要它
------------
`rubric/run_all_checks.py` 每次运行都会**重新生成**一批产物
（`retest.json` / `discrimination.json` / `boundary_analysis.json` /
`RUBRIC_V1.x_REVISION_LIST.md` / `V1.0_VS_V1.1.md` 等），而
`docs/DATACARD.md` 与 `README.md` 里的 κ 数字
（如「v1.0 κ=0.9494 → v1.1 κ=0.9636」）就是**从这些产物读出来的**。

`verify_rubric_claims.py` 只比对「文档 vs 产物」——
**它无法发现产物本身是不可复现的**。如果两次重跑得到不同的数，
那么文档里的数字就只是"某一次运行的快照"，而不是一个可复现的事实。
对一个卖点是"可验证"的项目，这个区别是实质性的。

实测（2026-09）：11 个产物在两次重跑之间**全部逐字节相同**，套件是确定性的。
本脚本把该性质固定下来 —— 一旦未来引入随机性（未固定的 seed、
依赖字典顺序、依赖当前时间），这里会失败。

用法
----
    python3 verify_rubric_determinism.py
    python3 verify_rubric_determinism.py --quick   # 只比核心 4 个产物
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUBRIC = ROOT / "rubric"

#: 套件会重写的产物（相对 rubric/）
TARGETS = [
    "docs/RUBRIC_V1.1_REVISION_LIST.md",
    "docs/RUBRIC_V1.2_REVISION_LIST.md",
    "docs/V1.0_VS_V1.1.md",
    "fixtures/answers/retest.json",
    "fixtures/answers/discrimination.json",
    "fixtures/answers/boundary_analysis.json",
    "fixtures/answers/scale_reliability.json",
    "fixtures/answers/defect_triage.json",
    "fixtures/answers/manip_result.json",
    "items/anchor_grounding.json",
    "items/anchor_grounding_v12.json",
]

QUICK = ["fixtures/answers/retest.json", "fixtures/answers/discrimination.json",
         "fixtures/answers/boundary_analysis.json", "fixtures/answers/scale_reliability.json"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "(missing)"


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="核对 rubric 套件是否确定性")
    ap.add_argument("--quick", action="store_true", help="只比核心 4 个产物")
    args = ap.parse_args(argv)

    if not (RUBRIC / "run_all_checks.py").is_file():
        print("SKIP: 没有 rubric/run_all_checks.py")
        return 0

    targets = QUICK if args.quick else TARGETS

    # 只比"现在能算出来"的那些（缺席的不算失败 —— 那是没生成，不是不确定）
    present = [t for t in targets if (RUBRIC / t).is_file()]
    if not present:
        print("SKIP: rubric 产物都还没生成（先跑一次 rubric/run_all_checks.py）")
        return 0

    # 备份，跑两次，比较
    backup = Path(tempfile.mkdtemp(prefix="rubric-det-"))
    try:
        for rel in present:
            d = backup / rel
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(RUBRIC / rel, d)

        for run_i in (1, 2):
            p = subprocess.run([sys.executable, str(RUBRIC / "run_all_checks.py")],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", cwd=str(ROOT), timeout=900)
            if p.returncode != 0:
                print(f"❌ rubric 套件第 {run_i} 次重跑失败（退出码 {p.returncode}）")
                tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-6:]
                for l in tail:
                    print("   " + l)
                return 1
            if run_i == 1:
                h1 = {rel: _sha(RUBRIC / rel) for rel in present}
        h2 = {rel: _sha(RUBRIC / rel) for rel in present}
    finally:
        # 恢复重跑前的产物，保持工作区原状
        for rel in present:
            b = backup / rel
            if b.is_file():
                t = RUBRIC / rel
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(b, t)
        shutil.rmtree(backup, ignore_errors=True)

    diffs = [rel for rel in present if h1[rel] != h2[rel]]
    for rel in present:
        mark = "✅" if h1[rel] == h2[rel] else "❌"
        print(f"  {mark} {rel}")
        if h1[rel] != h2[rel]:
            print(f"       run1={h1[rel][:16]}…  run2={h2[rel][:16]}…")

    print()
    if diffs:
        print(f"❌ {len(diffs)}/{len(present)} 个产物在两次重跑之间**不一致** —— 不可复现")
        print("   → 文档里的 κ 数字只是**某一次运行**的取值，不是可复现的事实")
        print("   → 常见原因：未固定的随机 seed、依赖 dict 顺序、依赖当前时间")
        return 1
    print(f"✅ rubric 套件确定性：{len(present)} 个产物重跑两次**逐字节相同**")
    print("   → 文档里的 κ 数字是从可复现产物读出的，不是某次运行的快照")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
