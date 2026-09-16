#!/usr/bin/env python3
"""核对题目里引用的数字是否真在原文里 —— 防"编造数据"。

为什么需要这个
--------------
出题时源文只有前 20,000 字符（方法学与结果大半被切掉）。出题者自称
"已回原文逐字核对"，但**他们能看到的原文本身就是残缺的**。
所以必须再验一遍：题目里引用的百分比、p 值、样本量，在**全文**里到底有没有。

这不是形式检查。一道"审稿式"题目如果引用了一个原文里根本不存在的数字，
那么整道题的"最薄弱环节"就是编造的，而它看起来会非常可信。

判据与局限
----------
- 只查**数字**能否在原文中找到，不判断该数字的用法是否正确（那需要读上下文）
- 中文题面里数字的写法可能与英文原文不同（如 "25 小时" vs "25 h"），
  所以只拿数字本体去搜，且允许 ±1 的格式差异
- **"没找到"不等于"编造"**：可能是单位换算/四舍五入/跨行断字。
  输出是**待人工确认清单**，不是结论。

用法：
    python3 check_numeric_fidelity.py --items ../items/items.jsonl \
        --sources ../items/sources --out ../items/numeric_fidelity.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 百分比 / p 值 / 小数 / 大于等于 3 的整数（2 太小，噪声大）
NUM_PATTERNS = [
    (r"(\d+\.\d+)\s*%", "pct1"),
    (r"(\d+)\s*%", "pct0"),
    (r"[pP]\s*[=＝<>]\s*(\d+\.\d+)", "pval"),
    (r"(\d+\.\d+)", "dec"),
    (r"\b(\d{2,})\b", "int"),
]


def find_all_numbers(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for pat, kind in NUM_PATTERNS:
        for m in re.finditer(pat, text):
            out.setdefault(kind, []).append(m.group(1))
    return out


def source_contains(src: str, token: str, kind: str) -> str:
    """返回 'exact' / 'rounded' / 'missing'。

    分三档而不是两档，是因为第一版只有"找到/没找到"，于是把
    "约 5900 个已批准药物"（原文是 5903）判成了未找到 —— 那其实是一次
    **正确的四舍五入**。二值判定会把诚实改写误报成编造。
    """
    if token in src:
        return "exact"
    # 千分位：13333 → 13,333
    try:
        if kind == "int" and len(token) >= 4:
            if f"{int(token):,}" in src:
                return "exact"
    except ValueError:
        pass
    # 整数的小数点写法：5903 → 5903.0
    if kind == "int" and f"{token}.0" in src:
        return "exact"
    # 小数：允许原文写成整数（74.25 → 74）
    if kind in ("dec", "pct1"):
        if token.split(".")[0] in src:
            return "exact"
    # 四舍五入：题面把 5903 写成"约 5900"。只在题面用了"约/近/大约"类词时才宽容，
    # 否则等于给编造数字开口子。
    if kind in ("int", "dec", "pct0", "pct1"):
        try:
            val = float(token)
        except ValueError:
            return "missing"
        if val > 0:
            tol = max(val * 0.02, 1.0)  # 允许 2% 的舍入
            for m in re.finditer(r"\d+(?:\.\d+)?", src):
                try:
                    other = float(m.group(0))
                except ValueError:
                    continue
                if other != val and abs(other - val) <= tol:
                    return "rounded"
    return "missing"


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="题目引用数字的原文可寻性核验")
    ap.add_argument("--items", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    items = [json.loads(l) for l in Path(args.items).read_text(encoding="utf-8").splitlines() if l.strip()]
    srcdir = Path(args.sources)

    report, total, missing = [], 0, 0
    for it in items:
        iid = it["item_id"]
        ref = (it.get("provenance") or {}).get("source_ref")
        sf = srcdir / f"{ref}.txt"
        if not sf.is_file():
            print(f"⚠️ {iid}: 找不到源文 {ref}.txt")
            continue
        src = sf.read_text(encoding="utf-8", errors="replace")
        src_norm = src.replace(",", "").replace("\n", " ")

        qtext = it.get("question") or ""
        # 题面用了"约/近/大约/左右"才允许四舍五入匹配——否则等于给编造开口子
        allows_rounding = bool(re.search(r"约|大约|近|左右|approximately|about|~", qtext))
        nums = find_all_numbers(qtext)
        # 只保留在题面里出现、且值得核对的（浮点/百分比/p值优先）
        checked, miss, rounded = [], [], []
        seen: set[tuple[str, str]] = set()
        for kind in ("pval", "pct1", "pct0", "dec", "int"):
            for tok in nums.get(kind, []):
                if (tok, kind) in seen:
                    continue
                seen.add((tok, kind))
                # 跳过显然不是数据的数字
                if tok in ("0", "1", "2", "3", "4", "5"):
                    continue
                checked.append(tok)
                verdict = source_contains(src_norm, tok, kind)
                if verdict == "rounded" and not allows_rounding:
                    verdict = "missing"
                if verdict == "missing":
                    miss.append({"value": tok, "kind": kind})
                elif verdict == "rounded":
                    rounded.append(tok)
        total += len(checked)
        missing += len(miss)
        flag = "❌" if miss else ("≈" if rounded else "✅")
        extra = f"，**未找到 {len(miss)} 个**" if miss else (f"，四舍五入 {len(rounded)} 个" if rounded else "")
        print(f"{flag} {iid} ({ref}, 全文 {len(src):,} 字符): 核对 {len(checked)} 个数字{extra}")
        for m in miss:
            print(f"      未在原文找到：{m['value']}  ({m['kind']})")
        for v in rounded:
            print(f"      近似匹配（题面用了『约』类词）：{v}")
        report.append({"item_id": iid, "source_ref": ref, "checked": checked,
                       "not_found": miss, "rounded": rounded})

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="")

    print(f"\n合计：核对 {total} 个数字，未在原文找到 {missing} 个（{missing / total * 100:.1f}%）"
          if total else "\n没有可核对的数字")
    print(f"明细 → {outp}")
    print("\n⚠️ 『未找到』不等于『编造』：可能是单位换算、四舍五入或跨行断字。")
    print("   这是**待人工确认清单**。请逐个回原文看上下文，不要直接判为造假。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
