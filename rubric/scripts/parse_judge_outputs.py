#!/usr/bin/env python3
"""解析 judge 的输出（严格 JSON）→ 标准标注 JSONL。

纪律（原则 7：失败必须响亮）
--------------------------
- judge 输出**缺条目 / 多条目 / 分数非法 / item_id 不符** → 全部计数并报出来
- **绝不静默补分**：缺的那条按"未作答"处理，由调用方决定丢弃还是计 0
- 解析失败的文件单独列出来，方便人工去看它到底输出成了什么样

用法：
    python3 parse_judge_outputs.py --index ../runs/judge_inputs_x/index.jsonl \
        --indir ../runs/judge_outputs_x --out ../runs/ann_judge_x.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def extract_json(text: str) -> dict | None:
    """judge 可能把 JSON 包在 ```json ... ``` 里，或者前后带解释文字。都容忍。"""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        i, j = text.find("{"), text.rfind("}")
        if i >= 0 and j > i:
            text = text[i:j + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="解析 judge 输出")
    ap.add_argument("--index", required=True)
    ap.add_argument("--indir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--annotator", default="judge")
    args = ap.parse_args(argv)

    index = [json.loads(l) for l in Path(args.index).read_text(encoding="utf-8").splitlines() if l.strip()]
    indir = Path(args.indir)
    outpath = Path(args.out)

    rows: list[dict] = []
    problems: list[str] = []
    n_ok = n_missing_file = n_bad_json = n_bad_score = n_id_mismatch = 0

    for rec in index:
        iid = rec["item_id"]
        want = list(rec["criterion_ids"])
        f = indir / f"{iid}.json"
        if not f.exists():
            # 也容忍 .txt / .md
            for ext in (".txt", ".md", ".jsonl"):
                alt = indir / f"{iid}{ext}"
                if alt.exists():
                    f = alt
                    break
        if not f.exists():
            problems.append(f"{iid}: judge 输出文件缺失")
            n_missing_file += 1
            continue
        obj = extract_json(f.read_text(encoding="utf-8", errors="replace"))
        if obj is None:
            problems.append(f"{iid}: 输出不是合法 JSON")
            n_bad_json += 1
            continue
        if obj.get("item_id") != iid:
            problems.append(f"{iid}: 输出里的 item_id 是 {obj.get('item_id')!r}，不符")
            n_id_mismatch += 1
            continue
        got = {}
        for s_ in (obj.get("scores") or []):
            cid = s_.get("criterion_id")
            sc = s_.get("score")
            if sc not in (0, 1, 2):
                problems.append(f"{iid}/{cid}: 分数 {sc!r} 不在 0/1/2")
                n_bad_score += 1
                continue
            got[cid] = int(sc)
        if set(got) != set(want):
            problems.append(f"{iid}: 标准编号不符（缺 {sorted(set(want) - set(got))}，"
                            f"多 {sorted(set(got) - set(want))}）")
            continue
        for cid in want:
            rows.append({"item_id": iid, "criterion_id": cid, "score": got[cid],
                         "annotator": args.annotator})
        n_ok += 1

    # ⚠️ `newline=""` —— 写出的 `ann_judge.jsonl` 是**已提交文件**；
    #    不加会让 Windows 写出 CRLF，而 `git status` 因 autocrlf 归一化看不见。
    #    （这类 `X.open("w", ...)` 的**方法**写法曾被我的 AST 批处理漏掉 ——
    #     它只匹配了内建 `open()`。所以检查器要按调用形态而不是按名字找。）
    with outpath.open("w", encoding="utf-8", newline="") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"索引 {len(index)} 条 → 成功解析 {n_ok} 条，写出 {len(rows)} 个评分点")
    print(f"  文件缺失 {n_missing_file} · 非法 JSON {n_bad_json} · "
          f"item_id 不符 {n_id_mismatch} · 分数非法 {n_bad_score}")
    print(f"  → {outpath}")
    if problems:
        print(f"\n⚠️ {len(problems)} 个问题（**不静默补分**）：")
        for p in problems[:15]:
            print(f"   {p}")
        return 1
    print("\n✅ 全部解析成功，无缺项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
