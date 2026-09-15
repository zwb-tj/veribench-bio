#!/usr/bin/env python3
"""上传前预检：**到底哪些文件会被传上去？** —— 在上传之前把这件事查清楚。

为什么需要它
------------
T2 的发布集有一个**致命的不对称**：

    tasks/T2/data/public/    3,789 条  ← 要上传的
    tasks/T2/data/           4,726 条  ← **含轮换池 937 条的题面与答案**

两个路径**只差一个 `/public`**。一条 `hf upload zwb-tj/<repo> data .` 手滑，
就会把「轮换池 937 条永不公开」这句对外声明变成假话 ——
而且是**不可撤销地**变成假话（HF 上公开过的数据无法收回信任）。

现有的检查（`verify_t2_rotation_isolation.py`）验的是"仓库里的状态对不对"，
**它不管"你打算上传什么"**。中间那一步（人敲的命令）此前完全没人守。

本脚本把"上传集"当成一个可检查的对象：
  A. **清单**：逐文件列出将要上传的东西（路径 + 条数 + 大小 + sha256）
  B. **禁令**：上传集里**不得**出现任何轮换池 id（题面或答案）
  C. **禁令**：不得出现 `audit.jsonl` 之外的变异身份（audit 是给核实真值用的，
     已在数据集卡里写明"勿当题面"）
  D. **完整性**：`items` / `truth` / `audit` 三者的 id 集合必须**完全一致**
  E. **卡片**：`README.md` 必须存在且与数据集卡逐字节一致

用法
----
    python3 verify_upload_preflight.py --dir tasks/T2/data/public
    python3 verify_upload_preflight.py --dir tasks/T2/data          # ← 应当失败
    python3 verify_upload_preflight.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
T2DATA = ROOT / "tasks" / "T2" / "data"

#: 上传集里**允许**出现的文件（白名单：少一个都算缺，多一个都算可疑）
ALLOWED = {"items.jsonl", "truth.jsonl", "audit.jsonl", "README.md"}


def _rel(p: Path) -> str:
    """尽量显示相对路径；**在仓库外时退回绝对路径**。

    ⚠️ 不能直接 `p.relative_to(ROOT)`：本脚本的一个**主要用途**就是把
    "从 HF 下载回来的目录"当参数传进来，而那个目录通常在外面
    （如 `$env:TEMP\\hf-t2-verify`）。`relative_to` 会抛 ValueError 直接崩 ——
    手册第 4 步③ 让用户跑的就是这个命令，实测当场崩掉。
    **脚本崩掉比"检查失败"更糟：用户会以为是自己的环境问题。**
    """
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def ids_of(p: Path) -> set[str]:
    out: set[str] = set()
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        i = d.get("item_id")
        if i:
            out.add(i)
    return out


def check(upload_dir: Path) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    notes: list[str] = []

    if not upload_dir.is_dir():
        return [f"上传目录不存在：{upload_dir}"], notes

    rotation_ids = ids_of(T2DATA / "rotation" / "items.jsonl")
    all_ids = ids_of(T2DATA / "items.jsonl")

    # A. 清单
    files = sorted(p for p in upload_dir.iterdir() if p.is_file())
    notes.append(f"上传目录 {_rel(upload_dir)}：{len(files)} 个文件")
    for p in files:
        n = sum(1 for l in p.read_text(encoding="utf-8", errors="replace").splitlines()
                if l.strip()) if p.suffix == ".jsonl" else "—"
        h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        notes.append(f"  {p.name:16} {n if n == '—' else str(n) + ' 行':>12}  "
                     f"{p.stat().st_size:>10,} B  sha256:{h}…")

    # 白名单：多一个文件都要报（可能是不该传的东西混进来了）；少一个也要报。
    # ⚠️ 不按目录名（`public`）判断 —— 手册第 4 步③ 会让人把**下载回来的副本**
    #    （名字通常是 `hf-t2-verify`）当参数传进来复核，那份同样应当齐 4 个文件。
    #    实测：按目录名判断时，对下载副本**静默跳过**了这两项检查。
    extra = {p.name for p in files} - ALLOWED
    if extra:
        problems.append(f"上传目录里有**预期之外**的文件：{sorted(extra)} —— "
                        f"只允许 {sorted(ALLOWED)}")
    missing = ALLOWED - {p.name for p in files}
    if missing:
        problems.append(f"上传目录缺文件：{sorted(missing)} —— "
                        "上传集应当齐 items/truth/audit + README")

    # B/C. 禁令：轮换池 id 绝不能出现
    for p in files:
        if p.suffix != ".jsonl":
            continue
        got = ids_of(p)
        leaked = got & rotation_ids
        if leaked:
            problems.append(
                f"{p.name} 含 **{len(leaked)} 条轮换池 id**（例：{sorted(leaked)[:3]}）—— "
                "轮换池的设计目标就是『永不公开』，这个文件不能上传")
        else:
            notes.append(f"{p.name}: 不含轮换池 id ✅")

    # D. 完整性：三个 jsonl 的 id 集合必须一致
    sets = {p.name: ids_of(p) for p in files if p.suffix == ".jsonl"}
    if len(sets) >= 2:
        names = sorted(sets)
        base = sets[names[0]]
        for n in names[1:]:
            if sets[n] != base:
                problems.append(f"{names[0]} 与 {n} 的 id 集合不一致"
                                f"（{len(base)} vs {len(sets[n])}，"
                                f"独有 {len(base ^ sets[n])} 个）")
        if all(sets[n] == base for n in names):
            notes.append(f"三个文件的 id 集合完全一致（{len(base)} 条）✅")

    # E. 卡片必须存在且与数据集卡一致（同样不按目录名判断，理由见上）
    card = T2DATA / "T2_DATASET_CARD.md"
    rm = upload_dir / "README.md"
    if not rm.is_file():
        problems.append("缺 README.md —— HF 需要它作为数据集卡")
    elif card.is_file() and rm.read_bytes() != card.read_bytes():
        problems.append("README.md 与 T2_DATASET_CARD.md 不一致（应逐字节相同）")
    elif card.is_file():
        notes.append("README.md == 数据集卡（逐字节）✅")

    return problems, notes


def compare_with(local_dir: Path, downloaded: Path) -> tuple[list[str], list[str]]:
    """把"从 HF 下载回来的那份"与本地待上传的那份**逐字节**比对。

    为什么要写进脚本而不是让用户敲一段内联 Python：
    本项目在 Windows/PowerShell 上被内联脚本的引号问题坑过多次
    （`@\"...\"@` here-string 与 `python -c` 都容易被打断）。
    **给别人照抄的命令，必须在我这里先跑通过。**
    """
    problems: list[str] = []
    notes: list[str] = []
    if not downloaded.is_dir():
        return [f"下载目录不存在：{downloaded}"], notes
    names = sorted(p.name for p in local_dir.iterdir() if p.is_file())
    for n in names:
        a, b = local_dir / n, downloaded / n
        if not b.is_file():
            problems.append(f"{n}：下载回来的那份里**没有**这个文件")
            continue
        ha = hashlib.sha256(a.read_bytes()).hexdigest()
        hb = hashlib.sha256(b.read_bytes()).hexdigest()
        if ha == hb:
            notes.append(f"{n}: 逐字节一致 ✅  sha256:{ha[:16]}…")
        else:
            problems.append(f"{n}: **不一致** 本地 {ha[:16]}… vs 下载 {hb[:16]}…")
    extra = {p.name for p in downloaded.iterdir() if p.is_file()} - set(names)
    if extra:
        notes.append(f"（下载回来的还多了：{sorted(extra)} —— 通常是 HF 自己的元数据文件）")
    return problems, notes


def self_test() -> int:
    """负向测试：证明**把整个 data/ 当上传集会被拦下**。"""
    cases = [
        ("正确的上传集 public/", T2DATA / "public", True),
        ("**错误的**上传集 data/（含轮换池答案）", T2DATA, False),
    ]
    ok = True
    for name, d, want_ok in cases:
        probs, _ = check(d)
        passed = (not probs) == want_ok
        if not passed:
            ok = False
        print(f"  {'✅' if passed else '❌'} {name}: "
              f"{'通过' if not probs else f'拦下 {len(probs)} 处'}"
              f"，期望{'通过' if want_ok else '拦下'}")
        if probs and not want_ok:
            for p in probs[:2]:
                print(f"       └ {p[:120]}")

    # ③ **仓库外**的下载副本（手册第 4 步③ 的真实用法）——
    #    这条用例的由来：手册让用户跑
    #    `--dir "$env:TEMP\hf-t2-verify"`，而那个路径在仓库外，
    #    旧代码里的 `upload_dir.relative_to(ROOT)` 直接抛 ValueError 崩掉。
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="preflight-neg-"))
    try:
        local = tmp / "local"
        remote = tmp / "remote"          # ← 仓库外，且名字不是 `public`
        local.mkdir()
        remote.mkdir()
        for n in ("items.jsonl", "truth.jsonl"):
            (local / n).write_text('{"item_id":"A"}\n', encoding="utf-8")
            (remote / n).write_text('{"item_id":"A"}\n', encoding="utf-8")
        p0, _ = compare_with(local, remote)
        same_ok = not p0
        # 篡改一个字节
        (remote / "items.jsonl").write_text('{"item_id":"B"}\n', encoding="utf-8")
        p1, _ = compare_with(local, remote)
        diff_ok = any("不一致" in x for x in p1)

        # 关键：对**仓库外**目录跑 check() 不能崩（要给出结论，而不是 traceback）
        try:
            check(remote)
            outside_ok = True
        except Exception as exc:  # noqa: BLE001
            outside_ok = False
            print(f"       └ 崩了：{type(exc).__name__}: {exc}")

        for label, cond in (("下载比对：一致时通过", same_ok),
                            ("下载比对：改一字节后报不一致", diff_ok),
                            ("对**仓库外**目录跑 check() 不崩", outside_ok)):
            ok = ok and cond
            print(f"  {'✅' if cond else '❌'} {label}")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("负向测试 " + ("全部通过（含 3 个必须失败的用例）" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="上传前预检：确认上传集里没有不该有的东西")
    ap.add_argument("--dir", help="将要上传的本地目录")
    ap.add_argument("--compare-with", metavar="DOWNLOADED_DIR",
                    help="把 --dir 与一个『从 HF 下载回来的目录』逐字节比对（上传后验证用）")
    ap.add_argument("--self-test", action="store_true", help="跑的负向测试")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.dir:
        ap.error("需要 --dir（或用 --self-test）")

    d = Path(args.dir)
    if not d.is_absolute():
        d = ROOT / d

    # 比对模式：只做逐字节比对（下载回来的那份通常缺 README 之外的白名单结构，
    # 所以不重复跑发布集禁令；禁令针对的是"你要传的那份"）
    if args.compare_with:
        cw = Path(args.compare_with)
        if not cw.is_absolute():
            cw = ROOT / cw
        problems, notes = compare_with(d, cw)
        for n in notes:
            print("  " + n)
        if problems:
            print(f"\n❌ {len(problems)} 处不一致 —— 上传可能没成功，或内容被改动过：")
            for p in problems:
                print("   " + p)
            return 1
        print("\n✅ 下载回来的那份与本地待上传的**逐字节一致**")
        return 0

    # ⚠️ 上传集是**生成物**（`split_public_rotation.py` 产出）且**刻意不随仓库发布**
    #    （见 `scripts/not_published.json`：`tasks/T2/data/public`）。
    #    所以清室检验 / 新 clone 里它**本来就不存在** ——
    #    这时必须 **SKIP 且退出码 0**，而不是报"上传目录不存在"（那是假警报，
    #    而假警报会训练人忽略真警报；同类教训见 T1 的 `_data` 与
    #    `record_image_digest` 的 `Unavailable` 态）。
    if not d.is_dir():
        print(f"SKIP: 上传目录不存在 —— {_rel(d)}")
        print("      （它是生成物、刻意不随仓库发布；先跑 split_public_rotation.py）")
        return 0

    problems, notes = check(d)
    for n in notes:
        print("  " + n)
    if problems:
        print(f"\n❌ {len(problems)} 处问题 —— **不要上传**：")
        for p in problems:
            print("   " + p)
        print("\n提醒：T2 的发布集有一个致命的不对称 ——")
        print("  tasks/T2/data/public/  = 3,789 条  ← 上传这个")
        print("  tasks/T2/data/         = 4,726 条  ← **含轮换池 937 条的答案**")
        print("  两个路径只差一个 /public。传错就把『永不公开』变成假话。")
        return 1
    print("\n✅ 上传集预检通过：无轮换池内容、白名单内、id 集合自洽、卡片一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
