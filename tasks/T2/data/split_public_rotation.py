#!/usr/bin/env python3
"""把 T2 数据切成 **public（可公开）** 与 **rotation（永不公开）** 两部分。

为什么必须切
-----------
T2 的题面与真值**共享 item_id**。如果两者都公开，任何能上网的 agent 都能
按 ID 直接查到答案 —— 防污染设计（题面去标识化）当场作废。

但如果全部不公开，就毁掉了本项目的核心卖点：**"可被第三方复现 + 公开自助榜"**
（竞品尽调显示这恰是大厂不做的空白）。

折中（SPEC §7）：
  · public  80% —— 题面 + 真值都公开，任何人都能自己跑判分、自己验证榜单
  · rotation 20% —— **永不公开**，用于将来检测"是否有人在公开集上过拟合"
  · 两者都带 provenance（audit），但 `audit.jsonl` 含变异身份（HGVS/VariationID），
    因此 **rotation 的 audit 绝不进公开仓库**

用法：
    python3 split_public_rotation.py --data . --outdir . --rotation-frac 0.2 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path


def load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="切分 public / rotation")
    ap.add_argument("--data", default=".")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--rotation-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=20260912)
    args = ap.parse_args(argv)

    data, out = Path(args.data), Path(args.outdir)
    items = load(data / "items.jsonl")
    truth = load(data / "truth.jsonl")
    audit = load(data / "audit.jsonl")
    if not items or not truth:
        print("[错误] 缺 items.jsonl 或 truth.jsonl", file=sys.stderr)
        return 2

    tmap = {t["item_id"]: t for t in truth}
    amap = {a["item_id"]: a for a in audit}

    # 只切分**真实题**；金丝雀是诊断项，随母题一起走（母题在哪边，它就在哪边）
    real = [it for it in items if not it.get("canary")]
    canary = [it for it in items if it.get("canary")]
    canary_by_anchor: dict[str, list[dict]] = {}
    for c in canary:
        canary_by_anchor.setdefault(c.get("canary_of") or "", []).append(c)

    ids = [it["item_id"] for it in real]
    rng = random.Random(args.seed)
    rng.shuffle(ids)
    n_rot = int(len(ids) * args.rotation_frac)
    rotation_ids = set(ids[:n_rot])
    print(f"真实题 {len(ids)} 条 → public {len(ids) - n_rot} / rotation {n_rot}")
    print(f"金丝雀 {len(canary)} 条（跟随母题归属）")

    for split_name, want_rotation in (("public", False), ("rotation", True)):
        si, st, sa = [], [], []
        for it in real:
            is_rot = it["item_id"] in rotation_ids
            if is_rot != want_rotation:
                continue
            si.append(it)
            if it["item_id"] in tmap:
                st.append(tmap[it["item_id"]])
            if it["item_id"] in amap:
                sa.append(amap[it["item_id"]])
            for c in canary_by_anchor.get(it["item_id"], []):
                si.append(c)
                if c["item_id"] in tmap:
                    st.append(tmap[c["item_id"]])
                if c["item_id"] in amap:
                    sa.append(amap[c["item_id"]])
        d = out / split_name
        write(d / "items.jsonl", si)
        write(d / "truth.jsonl", st)
        write(d / "audit.jsonl", sa)
        n_real = sum(1 for x in si if not x.get("canary"))
        print(f"  {split_name:<9} items={len(si)}（真实 {n_real} + 金丝雀 {len(si) - n_real}）"
              f"  truth={len(st)}  audit={len(sa)}")

        # ⚠️ public/ 的数据集卡**由这里生成**，不要手工复制。
        #    2026-09 实测发现：`data/public/README.md` 是一份**手工复制的陈旧副本**
        #    （7,223 B vs 卡片 8,043 B），缺了后来加到卡片里的"尚未上传"警示 ——
        #    如果原样上传，HF 上就会挂着一张写着错误状态的卡。
        #    **手抄的第二份必然漂移**，所以改成从唯一真源生成。
        if not want_rotation:
            # 数据集卡与脚本同目录（`data/`），不在 --outdir 里 —— 用脚本自身位置定位，
            # 这样无论从哪里调用都能找到。（第一版用了未定义的 HERE，会 NameError。）
            card = Path(__file__).resolve().parent / "T2_DATASET_CARD.md"
            if card.is_file():
                # ⚠️ 必须 `newline=""`：Windows 上 `write_text` 默认会把 `\n` 翻成 `\r\n`，
                #    于是"从真源生成"的副本与真源**逐字节不同**（实测 8043 → 8218 B）。
                #    内容一样但哈希不同，会让"两份是否一致"这种检查永远失败。
                #    生成物要么逐字节等于真源，要么这个"单一真源"就是假的。
                (d / "README.md").write_text(card.read_text(encoding="utf-8"),
                                             encoding="utf-8", newline="")
                print(f"  public    数据集卡 ← {card.name}（每次重新生成，防止陈旧副本）")
            else:
                print(f"  ⚠️ 找不到 {card.name}，未能生成 public/README.md")

    print()
    print("⚠️ 上传时：**只上传 public/**。")
    print("   rotation/ 含真值，永不公开；且 audit 内含变异身份（HGVS/VariationID）。")
    print("   更**不要**上传 data/{items,truth,audit}.jsonl（全量 4,726 条）——")
    print("   它们含轮换池的题面与答案。此约束由 scripts/verify_t2_rotation_isolation.py 检查。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
