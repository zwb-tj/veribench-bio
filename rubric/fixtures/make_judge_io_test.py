#!/usr/bin/env python3
"""为 judge I/O 链造测试数据（**夹具**，不是真实模型输出）。

两种模式：
    --mode answers                    生成 answers_fake.jsonl
    --mode outputs --index I --outdir O  按 index 生成每题一个 judge JSON

用途：在接真实模型之前，先证明
    build_judge_inputs → （judge 运行）→ parse_judge_outputs
这条链能跑通，且**缺项会被响亮报出来**。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="judge I/O 夹具")
    ap.add_argument("--mode", required=True, choices=["answers", "outputs"])
    ap.add_argument("--items")
    ap.add_argument("--index")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--break-one", action="store_true",
                    help="故意破坏一条（缺文件/非法分数），用来验证解析器会报错")
    args = ap.parse_args(argv)

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    if args.mode == "answers":
        items = load(Path(args.items))
        p = out / "answers_fake.jsonl"
        with p.open("w", encoding="utf-8") as fh:
            for i, it in enumerate(items):
                # 造一个"质量参差"的回答：偶数题答得较全，奇数题答得敷衍
                if i % 2 == 0:
                    body = ("我们首先检查了批次效应，用 PCA 与 SVA 两种方法评估，"
                            "发现样本按处理分组而非按批次聚集；随后用置换检验评估显著性，"
                            "并报告了效应量与置信区间。局限在于样本量偏小，"
                            "无法排除反向因果，需要纵向随访数据。")
                else:
                    body = "结果看起来是可信的，因为方法很常用，而且作者做了统计检验。"
                fh.write(json.dumps({"item_id": it["item_id"], "answer": body,
                                     "model": "FIXTURE", "run": 1}, ensure_ascii=False) + "\n")
        print(f"已写出 {p}（{len(items)} 条假作答）")
        return 0

    # mode == outputs
    index = load(Path(args.index))
    n = 0
    for k, rec in enumerate(index):
        iid = rec["item_id"]
        if args.break_one and k == 0:
            continue                      # 故意缺一个文件
        scores = []
        for j, cid in enumerate(rec["criterion_ids"]):
            if args.break_one and k == 1 and j == 0:
                sc = 7                    # 故意给非法分数
            else:
                sc = (k + j) % 3
            scores.append({"criterion_id": cid, "score": sc,
                           "evidence": "（夹具）" })
        (out / f"{iid}.json").write_text(
            json.dumps({"item_id": iid, "scores": scores}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        n += 1
    print(f"已写出 {n} 个 judge 输出到 {out}" + ("（并故意破坏 1 条）" if args.break_one else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
