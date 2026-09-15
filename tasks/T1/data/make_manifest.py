#!/usr/bin/env python3
"""为 T1 数据集生成 manifest.json（含每个文件的 sha256 与完整溯源）。

为什么必须有 manifest
-------------------
"可被第三方复现"不能是一句口号。manifest 要能让别人回答三个问题：
  1. 这些文件是**哪一天**、从**哪个 URL** 取来的？
  2. 取来的东西**有没有被改过**（sha256）？
  3. 加工步骤是什么、能不能重放（命令 + 参数 + seed）？

用法：
    python3 make_manifest.py --data /data --out /data/manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="生成 T1 数据集 manifest.json")
    ap.add_argument("--data", default="/data", help="数据根目录")
    ap.add_argument("--out", default=None, help="输出路径（默认 <data>/manifest.json）")
    ap.add_argument("--title", default="VeriBench-Bio T1 — HG002 chr20 变异检出")
    ap.add_argument(
        "--license",
        default="公有领域 / 美国政府作品 + HG002 捐献同意覆盖商用再分发",
    )
    args = ap.parse_args(argv)

    root = Path(args.data)
    if not root.is_dir():
        print(f"[错误] 数据目录不存在：{root}", file=sys.stderr)
        return 2

    sources_path = root / "sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8")) if sources_path.exists() else {}

    files: list[dict] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name in {"manifest.json", "sources.json"}:
            continue
        rel = p.relative_to(root).as_posix()
        # `_work/` 是中间产物（如未降采样的区域 BAM，约 80 MB），
        # 不属于公开数据集的一部分 —— 排除，否则 manifest 会列出仓库里没有的文件，
        # 让第三方的完整性校验出现假失败。
        if rel.startswith("_work/"):
            continue
        files.append(
            {
                "path": rel,
                "bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            }
        )

    manifest = {
        "manifest_version": "1.0",
        "title": args.title,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "license": args.license,
        "usage_rights": {
            "redistributable": True,
            "commercial_ok": True,
            "contains_human_data": True,
            "contains_restricted_data": False,
            "basis": "NIST/GIAB 数据为美国政府作品；HG002–HG005 由 PGP 招募，NIST 明确其『consented for commercial redistribution』。HG001/NA12878 未作此声明，本数据集不含它。",
        },
        "generation": {
            "script": "tasks/T1/data/prepare_data.sh",
            "reproducible": True,
            "params": {k: v for k, v in sources.items() if k not in {"sources", "provenance_notes"}},
        },
        "upstream_sources": sources.get("sources", []),
        "provenance_notes": sources.get("provenance_notes", []),
        "files": files,
    }

    out = Path(args.out) if args.out else root / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"已写入 {out}")
    print(f"文件数：{len(files)}，合计 {sum(f['bytes'] for f in files) / 1e6:.1f} MB")
    for f in files:
        print(f"  {f['bytes']:>12,}  {f['sha256'][:16]}…  {f['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
