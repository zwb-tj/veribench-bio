#!/usr/bin/env python3
"""按 manifest.json 校验一份下载副本的完整性。

为什么需要它
-----------
"上传成功了"这句话本身不可信 —— 上传工具可能报 0 字节却打印 OK。
唯一能证明"别人下到的和我们手上的**字节一致**"的方法是：**重新下载，逐个比对 sha256**。
这也是本项目"可被第三方复现"承诺的兑现方式：任何人拿到数据集，都能自己验一遍。

用法：
    # 1) 下载（或让第三方下载）
    hf download <user>/<repo> --repo-type=dataset --local-dir ./t1-data

    # 2) 校验
    python verify_manifest.py --manifest ./t1-data/manifest.json --root ./t1-data

退出码：0 = 全部一致；1 = 有不一致或缺失；2 = 用法错误。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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

    ap = argparse.ArgumentParser(description="按 manifest 校验数据集完整性")
    ap.add_argument("--manifest", required=True, help="manifest.json 路径")
    ap.add_argument("--root", required=True, help="待校验的数据根目录")
    ap.add_argument("--quiet", action="store_true", help="只输出结论")
    args = ap.parse_args(argv)

    mpath, root = Path(args.manifest), Path(args.root)
    if not mpath.is_file():
        print(f"[错误] manifest 不存在：{mpath}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"[错误] 数据目录不存在：{root}", file=sys.stderr)
        return 2

    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    if not files:
        print("[错误] manifest 里没有 files 列表", file=sys.stderr)
        return 2

    print(f"manifest : {mpath}")
    print(f"标题     : {manifest.get('title', '(无)')}")
    print(f"生成时间 : {manifest.get('generated_at', '(无)')}")
    print(f"条目数   : {len(files)}")
    print()

    ok = 0
    problems: list[str] = []

    for f in files:
        rel = f["path"]
        want_bytes, want_hash = f["bytes"], f["sha256"]
        p = root / rel

        if not p.is_file():
            problems.append(f"缺失     {rel}")
            if not args.quiet:
                print(f"  [缺失] {rel}")
            continue

        got_bytes = p.stat().st_size
        if got_bytes != want_bytes:
            problems.append(f"大小不符 {rel}（期望 {want_bytes}，实得 {got_bytes}）")
            if not args.quiet:
                print(f"  [大小不符] {rel}  期望 {want_bytes}  实得 {got_bytes}")
            continue

        got_hash = sha256_file(p)
        if got_hash != want_hash:
            problems.append(f"哈希不符 {rel}")
            if not args.quiet:
                print(f"  [哈希不符] {rel}\n      期望 {want_hash}\n      实得 {got_hash}")
            continue

        ok += 1
        if not args.quiet:
            print(f"  [OK]   {rel}  ({want_bytes:,} B, {want_hash[:16]}…)")

    # 额外文件（不在 manifest 里）—— 仅提示，不算失败
    listed = {f["path"] for f in files}
    extras: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if rel not in listed and p.name not in {"manifest.json", "sources.json", "README.md"}:
                extras.append(rel)
    if extras and not args.quiet:
        print("\n  [提示] 以下文件不在 manifest 中（不影响校验结果）：")
        for e in extras:
            print(f"         {e}")

    print()
    if problems:
        print(f"❌ 校验未通过：{len(problems)} 项问题（{ok}/{len(files)} 通过）")
        for p in problems:
            print(f"   - {p}")
        return 1

    print(f"✅ 校验通过：{ok}/{len(files)} 个文件与 manifest 完全一致（字节级）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
