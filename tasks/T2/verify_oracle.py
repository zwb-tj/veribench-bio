#!/usr/bin/env python3
"""在容器里**实跑** T2 的三个基线，核对 DATACARD 里记的那三个数。

DATACARD 写着：

    基线 | oracle 1.0000 / all_vus 0.4245 / all_pathogenic 0.3478

这三个数是**天花板与地板的标定**——说明评分尺度不是"什么都能得高分"，
也不是"什么都很低"。它们此前只在构建时算过一次，没人重新测过。

为什么要实跑而不是读旧文件
--------------------------
`baseline/result_*.json` 是当初跑出来的产物。读它只能证明"文件里有这个数"，
不能证明"现在拿同样的输入跑，还能得到这个数"。**前者是记载，后者是复现。**
所以这里真的启容器跑一遍。

（同一个思路见 `tasks/T1/verify_t1_claims.py`：文档里的关键数字要能被重新测出来。）

用法：
    python3 verify_oracle.py                 # 三个基线都跑
    python3 verify_oracle.py --only oracle   # 只跑一个
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tasks/T2/
T2 = HERE
ROOT = HERE.parents[1]                          # bio-eval/
IMAGE = "veribench-bio/t2:dev"

#: 期望值**从 DATACARD 里读**，不在本脚本里另写一份。
#: ⚠️ 第一版把 1.0000 / 0.4245 / 0.3478 硬编码在这里 —— 那就又成了
#: "同一个事实写两遍"：DATACARD 改了、脚本不知道，检查照样通过。
#: **要验的是"文档与实跑是否一致"，所以文档必须是断言的那一方。**
CLAIM_PAT = re.compile(
    r"oracle\s+([\d.]+)\s*/\s*all_vus\s+([\d.]+)\s*/\s*all_pathogenic\s+([\d.]+)")
CLAIM_ORDER = ["oracle", "all_vus", "all_pathogenic"]


def claimed_from_datacard() -> dict[str, float]:
    """从 DATACARD 抽出三个基线值。抽不到就报错（不静默用默认值）。"""
    card = (ROOT / "docs" / "DATACARD.md").read_text(encoding="utf-8")
    m = CLAIM_PAT.search(card)
    if not m:
        raise SystemExit(
            "❌ 没能从 docs/DATACARD.md 里读到基线值。\n"
            "   期望形如：oracle 1.0000 / all_vus 0.4245 / all_pathogenic 0.3478\n"
            "   **不要在本脚本里写死这些数** —— 那样文档改了也发现不了。")
    return dict(zip(CLAIM_ORDER, (float(g) for g in m.groups())))


def run_one(name: str, answers: Path, truth: Path) -> tuple[float | None, str]:
    tmp = Path(tempfile.mkdtemp(prefix=f"t2-{name}-"))
    try:
        shutil.copyfile(answers, tmp / "answers.jsonl")
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{truth.as_posix()}:/data/truth.jsonl:ro",
            "-v", f"{tmp.as_posix()}:/out",
            IMAGE,
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900)
        res_p = tmp / "result.json"
        if not res_p.is_file():
            return None, f"未产出 result.json（退出码 {p.returncode}）"
        res = json.loads(res_p.read_text(encoding="utf-8"))
        return res.get("score"), json.dumps(
            {k: res.get(k) for k in ("classification_credit", "criteria_f1", "exact_accuracy")
             if k in res}, ensure_ascii=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="实跑 T2 基线并与文档比对")
    ap.add_argument("--only", help="只跑某一个基线名")
    args = ap.parse_args(argv)

    truth = T2 / "data" / "truth.jsonl"
    if not truth.is_file():
        print(f"SKIP: 缺 {truth}（T2 数据未生成）")
        return 0

    # Docker 不可用就 SKIP，不假装通过
    if subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                      capture_output=True).returncode != 0:
        print(f"SKIP: 镜像 {IMAGE} 不存在或无 Docker（先构建）")
        return 0

    CLAIMED = claimed_from_datacard()
    print(f"从 docs/DATACARD.md 读到的期望值：{CLAIMED}\n")
    names = [args.only] if args.only else list(CLAIMED)
    results: list[tuple[str, float | None, float, bool, str]] = []
    for name in names:
        ans = T2 / "baseline" / f"answers_{name}.jsonl"
        if not ans.is_file():
            print(f"⏭ {name}: 缺 {ans.name}")
            continue
        print(f"跑 {name} …", end="", flush=True)
        score, extra = run_one(name, ans, truth)
        want = CLAIMED[name]
        ok = score is not None and abs(score - want) < 5e-5
        results.append((name, score, want, ok, extra))
        print(f" 得分 {score}（文档 {want}）{'✅' if ok else '❌'}")

    print()
    w = max(len(n) for n, *_ in results) if results else 8
    print(f"{'基线'.ljust(w)}  {'实测':>8}  {'文档':>8}  结论")
    print("-" * (w + 34))
    for name, score, want, ok, extra in results:
        print(f"{name.ljust(w)}  {score!s:>8}  {want:>8}  {'✅ 一致' if ok else '❌ 不符'}")
        if extra and extra != "{}":
            print(f"{' ' * w}  └ {extra}")
    n_bad = sum(1 for *_, ok, _ in results if not ok)
    print()
    if n_bad:
        print("❌ 实跑结果与文档不符 —— **改文档，不要改事实**。")
        return 1
    print(f"✅ {len(results)} 个基线实跑结果与 DATACARD 记载一致")
    print("   （这是**复现**，不是读旧产物 —— 容器真的跑了一遍）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
