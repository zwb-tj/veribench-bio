#!/usr/bin/env python3
"""为**操纵检验**构造 judge 输入（逐条标准，而不是整题）。

为什么不能复用 build_judge_inputs.py
------------------------------------
那个脚本按 `item_id` 组织，且**同题只取第一条作答**——它假定"一题一答"。
但操纵检验是**逐条标准**的：同一道题可能有多条被检验的标准（26 条标准分布在
17 道题上），每条标准各有 A+/A− 两份变体。同一个 item_id 会出现多次。
所以这里改用 `(item_id, criterion_id, variant)` 作为键。

其余部分（怎么把题面+答案+锚点拼成 prompt）**逐字复用** build_judge_inputs 的排版，
否则提示词形态一变，和之前跑出的结果就不可比了。

用法：
    python3 build_manip_inputs.py --plan ../fixtures/answers/manip_plan.json \
        --variants ../fixtures/answers/manip_variants_1.jsonl \
                   ../fixtures/answers/manip_variants_2.jsonl \
        --outdir ../fixtures/answers/manip_inputs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROMPT_VERSION = "judge_prompt_v1.0"


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def criterion_block(criteria: list[dict]) -> str:
    """**已移到 `judge_prompt.py`**（唯一实现）。此处保留为转发。

    原来这里写着「⚠️ 与 build_judge_inputs.criterion_block 保持一致
    （**改一处必须改两处**）」—— 那句提醒本身就是缺陷：
    可比性不该依赖人记得。现在两条链共用 `judge_prompt.py`，
    漂移会被 `check_prompt_agree.py` 抓住。
    """
    from judge_prompt import criterion_block as _cb
    return _cb(criteria)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="构造操纵检验的 judge 输入")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--variants", nargs="+", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args(argv)

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    items = {json.loads(l)["item_id"]: json.loads(l)
             for l in (ROOT / "items" / "items_v1.1.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()}
    variants = []
    for vp in args.variants:
        p = Path(vp)
        if p.is_file():
            variants += load_jsonl(p)

    # (item_id, criterion_id) -> {A_plus, A_minus}
    vmap: dict[tuple[str, str], dict] = {}
    for v in variants:
        vmap[(v["item_id"], v["criterion_id"])] = v

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    missing: list[str] = []

    for spec in plan:
        iid, cid = spec["item_id"], spec["criterion_id"]
        v = vmap.get((iid, cid))
        if not v:
            missing.append(f"{iid}/{cid}")
            continue
        it = items.get(iid)
        if not it:
            missing.append(f"{iid}/{cid}（题面缺失）")
            continue
        crits = it["criteria"]
        for tag, key in (("Aplus", "A_plus"), ("Aminus", "A_minus")):
            ans = v.get(key, "")
            if not ans:
                missing.append(f"{iid}/{cid}/{tag}（空）")
                continue
            # 文件名不含档位含义之外的线索；档位名是必要的，因为它就是被检验的变量
            fname = f"{iid}_{cid}_{tag}.txt"
            from judge_prompt import build_prompt as _bp
            body = _bp(it.get("question", ""), ans, crits, iid)
            # ⚠️ `newline=""` —— 操纵检验输入会被跨机器比对；不加会让两平台字节不同
            (outdir / fname).write_text(body, encoding="utf-8", newline="")
            index.append({
                "item_id": iid, "criterion_id": cid, "variant": tag,
                "group": spec.get("group"),
                "prompt_file": fname,
                "criterion_ids": [c["criterion_id"] for c in crits],
                "prompt_version": PROMPT_VERSION,
            })

    # ⚠️ `newline=""`：同上
    with (outdir / "index.jsonl").open("w", encoding="utf-8", newline="") as fh:
        for r in index:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"操纵检验输入：{len(index)} 份（{len(plan)} 条标准 × 2 变体）→ {outdir}")
    print(f"  目标组 {sum(1 for r in index if r['group'] == 'defect')} 份 · "
          f"对照组 {sum(1 for r in index if r['group'] == 'control')} 份")
    if missing:
        print(f"  ⚠️ 缺 {len(missing)} 项：{missing[:8]}")
        return 1
    print("  ✅ 全部就绪")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
