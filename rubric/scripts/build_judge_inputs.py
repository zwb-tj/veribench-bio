#!/usr/bin/env python3
"""按 judge_prompt_v1.md 的模板，把「题目 + 待评回答」渲染成 judge 可直接消费的输入。

为什么单独一步
------------
judge 的输入格式必须**由程序拼装**，不能手敲 —— 手敲会导致：
  · 不同题目的标准顺序不一致（judge 会答错 criterion_id）
  · 锚点漏贴（judge 就失去判定依据）
  · prompt 版本与跑出来的 κ 对不上（历史结果不可复现）

用法：
    python3 build_judge_inputs.py --items ../items/items.jsonl \
        --answers ../runs/answers_modelX.jsonl --outdir ../runs/judge_inputs_modelX

产出：
    <outdir>/<item_id>.txt      每个 (题目, 回答) 一个完整 prompt
    <outdir>/index.jsonl        item_id / 回答来源 / 相关标准编号
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROMPT_VERSION = "judge_prompt_v1.0"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def criterion_block(criteria: list[dict]) -> str:
    """**已移到 `judge_prompt.py`**（唯一实现）。此处保留为转发，避免外部引用断掉。

    ⚠️ 原来这里和 `build_manip_inputs.py` 各有一份**逐字节相同**的实现，
    且 prompt 正文那 10 行也是逐字重复。那条链的注释写着
    「改一处必须改两处」—— **那句注释就是缺陷本身**：
    操纵检验若与判分用不同的 prompt，它测的就是另一个 prompt 的行为，
    而它的结论会被用来为真实判分背书。现在由 `judge_prompt.py` 保证可比性。
    """
    from judge_prompt import criterion_block as _cb
    return _cb(criteria)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="构造 judge 输入")
    ap.add_argument("--items", required=True)
    ap.add_argument("--answers", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args(argv)

    items = {it["item_id"]: it for it in load_jsonl(Path(args.items))}
    answers = load_jsonl(Path(args.answers))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    index: list[dict] = []
    missing_answer = 0

    ans_by_id: dict[str, str] = {}
    for a in answers:
        iid = a.get("item_id")
        if iid in ans_by_id:
            problems.append(f"{iid}: 作答重复，取第一条")
            continue
        ans_by_id[iid] = a.get("answer", "")

    for iid, it in sorted(items.items()):
        ans = ans_by_id.get(iid)
        if ans is None:
            problems.append(f"{iid}: 缺作答 —— **不静默跳过**，会被记录")
            missing_answer += 1
            continue
        crits = it.get("criteria") or []
        from judge_prompt import build_prompt as _bp
        body = _bp(it.get("question", ""), ans, crits, iid)
        # ⚠️ `newline=""` —— judge 输入会被跨机器比对（本项目已有"重新生成
        #    已提交产物、发现只有 CRLF/LF 不同"的实测记录）。不加会让两平台字节不同。
        (outdir / f"{iid}.txt").write_text(body, encoding="utf-8", newline="")
        index.append({
            "item_id": iid,
            "prompt_file": f"{iid}.txt",
            "criterion_ids": [c["criterion_id"] for c in crits],
            "prompt_version": PROMPT_VERSION,
        })

    # ⚠️ `newline=""`：同上，跨机器比对需要逐字节一致
    with (outdir / "index.jsonl").open("w", encoding="utf-8", newline="") as fh:
        for r in index:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"题目 {len(items)} · 作答 {len(query := ans_by_id)} · 生成 prompt {len(index)}")
    print(f"  prompt 版本：{PROMPT_VERSION}（跑出的 κ 只对本版本有效）")
    print(f"  输出目录：{outdir}")
    if missing_answer:
        print(f"  ⚠️ 有 {missing_answer} 道题缺作答 —— 已计入 problems，不静默跳过")
    if problems:
        print(f"\n发现 {len(problems)} 个问题：")
        for p in problems[:10]:
            print(f"  ⚠️ {p}")
        return 1 if missing_answer else 0
    print("\n✅ 全部题目都有作答")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
