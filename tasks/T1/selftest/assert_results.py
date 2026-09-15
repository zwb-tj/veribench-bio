#!/usr/bin/env python3
"""断言 T1 判分器的自检结果符合预期值。

期望（推导见 make_synthetic.py 的 docstring）：
  完美解法：SNP F1 = 1.0，INDEL F1 = 1.0，score = 1.0，status = ok
  部分解法：SNP F1 = 0.5，INDEL F1 = 0（解法未产出该类型），score = 0.25
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOL = 1e-3
failures: list[str] = []


def close(a: float | None, b: float, label: str) -> None:
    if a is None or abs(a - b) > TOL:
        failures.append(f"{label}: 期望 {b}，实得 {a}")


def check_perfect(path: Path) -> None:
    r = json.loads(path.read_text(encoding="utf-8"))
    close(r["per_type"]["snps"]["f1"], 1.0, "perfect/snps.f1")
    close(r["per_type"]["indels"]["f1"], 1.0, "perfect/indels.f1")
    close(r["score"], 1.0, "perfect/score")
    if r["status"] != "ok":
        failures.append(f"perfect/status: 期望 ok，实得 {r['status']}")


def check_partial(path: Path) -> None:
    r = json.loads(path.read_text(encoding="utf-8"))
    # SNP：真值 2 个；解法 2 个，1 对 1 错 → TP=1 FP=1 FN=1 → P=S=F1=0.5
    close(r["per_type"]["snps"]["precision"], 0.5, "partial/snps.precision")
    close(r["per_type"]["snps"]["sensitivity"], 0.5, "partial/snps.sensitivity")
    close(r["per_type"]["snps"]["f1"], 0.5, "partial/snps.f1")
    close(r["per_type"]["snps"]["fp"], 1.0, "partial/snps.fp")
    close(r["per_type"]["snps"]["fn"], 1.0, "partial/snps.fn")
    # INDEL：真值 1 个，解法 0 个 → 记 0 分（不是跳过）
    close(r["per_type"]["indels"]["f1"], 0.0, "partial/indels.f1")
    # 宏平均 = (0.5 + 0.0) / 2
    close(r["score"], 0.25, "partial/score")
    if not any("未产出该类型" in p for p in r["problems"]):
        failures.append("partial/problems: 未记录『解法未产出该类型变异』")
    # 关键：不能因为某类型缺失就静默返回 0 而不说明
    if r["status"] == "failed":
        failures.append("partial/status: 不应为 failed")


def main() -> int:
    _ap = argparse.ArgumentParser(
        description="断言 T1 判分器的自检结果符合预期值",
        epilog="例：python3 assert_results.py perfect.json partial.json")
    _ap.add_argument("files", nargs="+", help="要断言的判分结果 JSON")
    files = _ap.parse_args().files
    if len(files) != 2:
        print("用法: assert_results.py <perfect.json> <partial.json>", file=sys.stderr)
        return 2
    check_perfect(Path(files[0]))
    check_partial(Path(files[1]))

    if failures:
        print(f"\n❌ 判分器自检未通过（{len(failures)} 项）：")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\n✅ 判分器自检通过：完美解法 1.0、部分解法 0.25，FP/FN 计数与 problem 记录均符合预期。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
