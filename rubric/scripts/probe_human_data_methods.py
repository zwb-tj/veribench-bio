"""从全文里抽出「方法/受试者」段落，用于最终判定 contains_human_data。

为什么必须这样做
----------------
之前 24/27 篇只有前 20,000 字符，**方法学部分基本被切掉了**。我于是只能靠
引言里的词频猜，结果把 PMC11900006（本文是商品化人视网膜内皮细胞体外研究，
引言引用了作者既往的患者队列）误判为 human_subjects_primary。

现在有全文了，就直接看方法学部分怎么写的。
"""

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                  # rubric/
DEFAULT_SOURCES = ROOT / "items" / "sources"

#: 默认看这些（`human_data_basis.json` 里争议最大的几条）。
#: 也可以命令行传 `--cases` 覆盖 —— 原版把清单**写死在模块顶层**，
#: 于是任何目录下跑它都会立刻去找 `items/sources/PMC....txt`，
#: 换目录就 FileNotFoundError（由 smoke_test_scripts.py 抓到）。
CASES = [
    "PMC11900003", "PMC11900006", "PMC11900007", "PMC11900012",
    "PMC11900013", "PMC11900017", "PMC11900026", "PMC11900028",
]

PATTERNS = [
    r"[^.]*\b(?:patients?|participants?|subjects?|donors?|volunteers?)\b[^.]*\b(?:were|was)\b[^.]*\b(?:recruited|enrolled|included|randomi[sz]ed|assigned|consented|divided)\b[^.]*\.",
    r"[^.]*\b(?:we|this study|the study)\b[^.]*\b(?:recruited|enrolled|included|collected|obtained)\b[^.]*\b(?:patients?|participants?|subjects?|donors?|samples?|cells?)\b[^.]*\.",
    r"[^.]*\b(?:Ethics|IRB|Institutional Review Board|informed consent)\b[^.]*\.",
    r"[^.]*\b(?:commercial(?:ly)?|purchased|obtained from|Lonza|ATCC|Cell Applications|ScienCell)\b[^.]*\b(?:cells?|cell line)\b[^.]*\.",
    r"[^.]*\b(?:human (?:primary|retinal|umbilical|microvascular|endothelial|monocyte))\b[^.]*\.",
    r"[^.]*\b(?:mice|rats?|murine|Sprague|C57BL|bumble ?bees?|Apis)\b[^.]*\.",
]

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="抽取源文的**方法学段落**，用于判定 contains_human_data（R2 证据）",
        epilog="例：python3 probe_human_data_methods.py --cases PMC11900006 PMC11900012")
    ap.add_argument("--cases", nargs="*", default=CASES, help="要看哪些 PMID/PMCID（默认 8 条争议项）")
    ap.add_argument("--sources", default=str(DEFAULT_SOURCES),
                    help="源文目录（默认 rubric/items/sources；该目录**不随仓库发布**）")
    args = ap.parse_args(argv)

    src = Path(args.sources)
    if not src.is_dir():
        print(f"SKIP: 源文目录不存在（{src}）—— items/sources/ 刻意不随仓库发布，"
              f"需先跑 fetch_source_text.py")
        return 0

    missing = []
    for pmc in args.cases:
        f = src / f"{pmc}.txt"
        if not f.is_file():
            missing.append(pmc)
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        print("=" * 72)
        print(pmc, f"（{len(t):,} 字符）")
        seen = set()
        for pat in PATTERNS:
            for m in re.finditer(pat, t, re.I):
                s = " ".join(t[max(0, m.start() - 40):m.end() + 40].split())
                key = s[:70]
                if key in seen or len(s) < 50:
                    continue
                seen.add(key)
                print("   ·", s[:230])
    if missing:
        print(f"\n⚠️ 缺 {len(missing)} 篇源文：{missing}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
