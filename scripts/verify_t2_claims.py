#!/usr/bin/env python3
"""**重新测量** T2 的关键断言，并与文档里写的数字比对。

为什么不能只写数字
------------------
T2 的招牌结论是"**0 泄漏，覆盖 N 个字符串字段**"。这个 N 以及其它几个数字
（题量、金丝雀比例、公开/轮换切分）都写在 README 与 DATACARD 里，
**但此前从来没有人把文档里的数字和实际数据对过一遍**。

本轮对了一次，立刻发现文档写 **40,110**，而实际测量是 **40,170** ——
一个从某次早期运行留下的旧数字，谁也没注意。这类错误单个不致命，
但它恰好出现在这个项目**最核心的那个卖点**上。

所以本脚本把"重新测量 + 与文档比对"固定下来：

  · 题量 / 金丝雀数 / 真实条目数          ← 数 items.jsonl
  · 字符串字段数（泄漏检查的覆盖面）        ← 跑 check_no_leakage.py 取它自己报的数
  · 公开集 / 轮换池切分                    ← 数两个文件
  · 泄漏结论本身（0 泄漏）                 ← 跑检查器，非零退出即失败

**只用标准库、只读本地数据**，所以能进常规检查。

用法：
    python3 verify_t2_claims.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                    # bio-eval/
T2 = ROOT / "tasks" / "T2"
DATA = T2 / "data"

results: list[tuple[str, bool | None, str]] = []


def add(claim: str, ok: bool | None, ev: str) -> None:
    results.append((claim, ok, ev))


def count_jsonl(p: Path) -> int:
    return sum(1 for l in p.read_text(encoding="utf-8").splitlines() if l.strip())


#: 镜像 /work 里的文件 ←→ 仓库里的源文件
IMAGE_SOURCE_PAIRS = [
    ("items.jsonl", DATA / "items.jsonl"),
    ("grade.py", T2 / "grade.py"),
    ("run.sh", T2 / "run.sh"),
    ("check_no_leakage.py", DATA / "check_no_leakage.py"),
]


def check_image_matches_source(image: str) -> list[str] | None:
    """把镜像里的 /work 取出来与仓库源码逐字节比对。

    返回不一致清单；`None` 表示无法验证（无 Docker / 镜像不存在）。
    **不用 `docker run`**（那会执行镜像），用 `docker create` + `docker cp`，
    这样即使镜像架构不匹配也能查。
    """
    import hashlib
    import shutil
    import subprocess
    import tempfile

    def sha(b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()

    # ⚠️ `docker` 不存在时必须 **SKIP**，不能崩。
    #    实测：在 Linux CI 环境（没有 docker）里，旧代码直接抛
    #    `FileNotFoundError: [Errno 2] No such file or directory: 'docker'` ——
    #    整个脚本 traceback 退出，**报告的是"脚本崩了"而不是"跳过了"**。
    #    脚本崩掉比检查失败更糟：看日志的人会以为是仓库坏了。
    #    兄弟脚本 `verify_oracle.py` 一直是先 `docker image inspect` 判存在性，
    #    这里对齐同样的做法。
    if shutil.which("docker") is None:
        return None

    cid = subprocess.run(["docker", "create", image], capture_output=True, text=True)
    if cid.returncode != 0:
        return None
    container = cid.stdout.strip()
    tmp = Path(tempfile.mkdtemp(prefix="t2img-"))
    diffs: list[str] = []
    try:
        for name, src in IMAGE_SOURCE_PAIRS:
            dest = tmp / name
            r = subprocess.run(["docker", "cp", f"{container}:/work/{name}", str(dest)],
                               capture_output=True, text=True)
            if r.returncode != 0 or not dest.is_file():
                diffs.append(f"{name}:镜像里取不出来")
                continue
            if not src.is_file():
                diffs.append(f"{name}:仓库缺源文件")
                continue
            if sha(dest.read_bytes()) != sha(src.read_bytes()):
                diffs.append(f"{name}(镜像 {sha(dest.read_bytes())[:8]}… "
                             f"vs 仓库 {sha(src.read_bytes())[:8]}…)")
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
    return diffs


def check_image_pin() -> None:
    """核对镜像 pin 与构建源码的对应（T1 踩过的那个坑，同一个缺陷类）。

    只看"有没有 pin"不够，要验"pin 的对不对"（是否由当前源码构建出来）。
    **刻意不依赖任何数据内容**（不解析 items.jsonl），
    这样即使数据文件被改坏，这条结构性检查仍然能给出结论。
    """
    import importlib.util

    rid_p = ROOT / "scripts" / "record_image_digest.py"
    if not rid_p.is_file():
        add("镜像 pin 与当前构建源码对应", False,
            f"缺 {rid_p.relative_to(ROOT).as_posix()} —— 无法核对 pin")
        return
    spec = importlib.util.spec_from_file_location("_rid2", rid_p)
    assert spec and spec.loader
    rid = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rid)

    rec_p = T2 / "IMAGE_DIGEST.json"
    if not rec_p.is_file():
        add("镜像 pin 与当前构建源码对应", False,
            "缺 tasks/T2/IMAGE_DIGEST.json —— T2 此前根本没有 pin（T1 有）")
        return
    cur, names = rid.source_sha256("T2")
    rec = json.loads(rec_p.read_text(encoding="utf-8"))
    img = rec.get("image_id") or "veribench-bio/t2:dev"
    add("镜像 pin 与当前构建源码对应", rec.get("source_sha256") == cur,
        f"记录 {str(rec.get('source_sha256'))[:16]}… vs 当前 {cur[:16]}…"
        f"（覆盖 {len(names)} 个构建输入）· image_id {img}")

    # 镜像里的 /work 必须与仓库源码逐字节一致 —— 否则"实跑验证过的"
    # 与"仓库里的"就是两回事（T1 的 digest 就栽在这里）。
    diffs = check_image_matches_source(img)
    if diffs is None:
        add("t2 镜像里的 /work 与仓库源码逐字节一致", None,
            "Docker 不可用或镜像不存在，本机无法验证")
    else:
        add("t2 镜像里的 /work 与仓库源码逐字节一致", not diffs,
            "全部一致" if not diffs else "不一致：" + "、".join(diffs))


def check_hf_upload_state() -> None:
    """T2 到底上传了没有？—— 文档说"已上传并逐字节比对"，实测是 0 B。

    2026-09 实测发现：`docs/DATACARD.md` 写着 T2「公开 3,789 条」，
    证据列写的是「上传 + 重新下载逐字节比对」；根 `README.md` 也写「HF 上公开 3,789 条」。
    但 `hf repo list` 显示 T2 仓库 **storage = 0 B** —— 仓库建了，**一个文件都没传**。
    （`tasks/T2/README.md` 的未闭合项里其实一直挂着"尚未上传"，两处自相矛盾。）

    这一类"上传状态"过去被标成"需联网才能复核"。但 `hf` CLI 就在本机，
    而且 `hf repo list` **不需要下载内容**就能给出 storage 字节数 —— 所以它是可验证的。
    **能验的东西不该被写成"无法验证"**（那是把懒惰说成局限）。
    """
    import shutil
    import subprocess

    if not shutil.which("hf"):
        add("T2 的 HF 上传状态与文档一致", None, "本机没有 hf CLI，无法核对（需联网）")
        return
    try:
        p = subprocess.run(["hf", "repo", "list", "--repo-type", "dataset",
                            "--format", "json"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        add("T2 的 HF 上传状态与文档一致", None, "hf CLI 调用失败/超时，无法核对")
        return
    if p.returncode != 0:
        add("T2 的 HF 上传状态与文档一致", None,
            f"hf repo list 退出码 {p.returncode}（可能未登录）；跳过")
        return
    try:
        repos = json.loads(p.stdout)
    except ValueError:
        add("T2 的 HF 上传状态与文档一致", None, "hf 输出不是 JSON，跳过")
        return

    t2 = None
    for r in repos if isinstance(repos, list) else []:
        rid = r.get("id") or r.get("repoId") or ""
        if "veribench-bio-t2" in rid:
            t2 = r
            break
    if t2 is None:
        add("T2 的 HF 上传状态与文档一致", None, "列表里没有 T2 仓库，跳过")
        return

    # ⚠️ `hf repo list --format json` 给的是**字符串**字段 `storage`（如 "0 B" / "100.3 MB"），
    #    不是字节数。第一版去找 `usedStorage`（那是 API 的字段名，不是 CLI 的），
    #    结果永远拿不到值、永远报"无法验证" —— **一个总是 SKIP 的检查等于没有检查**。
    raw = t2.get("storage")
    if raw is None:
        add("T2 的 HF 上传状态与文档一致", None,
            f"hf 输出里没有 storage 字段（实际键：{sorted(t2)}）")
        return
    used = _parse_size(raw)

    # 文档现在应当说"尚未上传"
    says_uploaded = "HF 上公开" in (
        (ROOT / "README.md").read_text(encoding="utf-8"))
    if used == 0:
        add("T2 的 HF 上传状态与文档一致（实测 0 B，文档须说『未上传』）",
            not says_uploaded,
            f"HF storage = {raw!r}（仓库已建、内容为空）；"
            f"根 README {'仍写着『HF 上公开』**与事实不符**' if says_uploaded else '已如实写『尚未上传』'}")
    else:
        add("T2 的 HF 上传状态与文档一致（实测已有内容）", True,
            f"HF storage = {raw!r}")


def _parse_size(s: str) -> int:
    """把 `hf` 的 '0 B' / '100.3 MB' 之类转成字节数（解析不了返回 -1）。"""
    import re as _re

    m = _re.fullmatch(r"\s*([\d.]+)\s*([KMGT]?i?B)\s*", str(s), _re.I)
    if not m:
        return -1
    n = float(m.group(1))
    unit = m.group(2).upper().replace("I", "")
    mult = {"B": 1, "KB": 1000, "MB": 10**6, "GB": 10**9, "TB": 10**12}.get(unit, 0)
    return int(n * mult) if mult else -1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    # ⚠️ 必须有 argparse：全仓冒烟测试对每个 .py 跑 `--help` 并期望退出码 0。
    #    没有 argparse 时 `--help` 会**真的去跑检查**，查出真问题就返回 1，
    #    被冒烟测试误报成"连 --help 都跑不起来"。检查器 --help 只该打印用法。
    ap = argparse.ArgumentParser(
        description="重新测量 T2 的关键断言，并与文档比对（不改任何文件）")
    ap.add_argument("--quiet", action="store_true", help="只打印结论行")
    args = ap.parse_args(argv)

    items_p, truth_p = DATA / "items.jsonl", DATA / "truth.jsonl"
    for p in (items_p, truth_p):
        if not p.is_file():
            print(f"SKIP: 缺 {p.relative_to(ROOT)} —— T2 数据未生成")
            return 0

    # 结构性检查（不碰数据内容）**先跑** —— 见 check_image_pin 的说明。
    check_image_pin()
    # T2 的 HF 上传状态：文档说"已上传并逐字节比对"，实测是 0 B。
    check_hf_upload_state()

    # ⚠️ 数据类检查放在**最前面之前**要先做完整性自检：
    #    如果 items.jsonl 被截断/追加（正是"构建输入变了"的典型表现），
    #    下面 `json.loads` 会直接抛 JSONDecodeError，**在到达 pin 检查之前就崩掉**。
    #    那样"文件被改坏"会被报成"脚本崩了"，而不是"镜像 pin 已脱节"。
    #    这是负向测试抓出来的（往 items.jsonl 追加一行 → 脚本 traceback，没报出真正的问题）。
    #    所以先解析，解析失败就**明确报成一条断言失败**，而不是崩。
    parse_error = None
    try:
        rows = [json.loads(l) for l in items_p.read_text(encoding="utf-8").splitlines()
                if l.strip()]
    except ValueError as exc:
        rows = []
        parse_error = str(exc)

    n_items = count_jsonl(items_p)
    n_canary = sum(1 for r in rows if r.get("canary") is True)
    n_real = n_items - n_canary

    # ⚠️ **逐文档**核对，不能把 README 和 DATACARD 拼起来再 `in`。
    #    拼接的写法有个致命弱点：**只要有一份文档写对就通过**，
    #    另一份写错永远发现不了。这个弱点是在给 T1 做负向测试时暴露的
    #    （两个脚本是照同一个模子写的），随后两边都改成了逐文档。
    DOCS = {
        "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
        "docs/DATACARD.md": (ROOT / "docs" / "DATACARD.md").read_text(encoding="utf-8"),
    }

    def in_each(needle: str) -> tuple[bool, str]:
        """该字符串必须在**每一份**报告了 T2 数字的文档里都出现。"""
        hits = {name: (needle in text) for name, text in DOCS.items()}
        return all(hits.values()), "、".join(f"{n}:{'有' if v else '**没有**'}"
                                            for n, v in hits.items())

    ok_q, ev_q = in_each("4,726 条")
    add("items.jsonl 每一行都是合法 JSON", parse_error is None,
        "全部可解析" if parse_error is None else f"解析失败：{parse_error[:110]}")
    add("题量与文档一致（4,726）", n_items == 4726 and ok_q,
        f"实测 {n_items}；{ev_q}")
    ok_c, ev_c = in_each("1,181 金丝雀")
    add("金丝雀数与文档一致（1,181 = 25%）", n_canary == 1181 and ok_c,
        f"实测金丝雀 {n_canary}（占 {n_canary / n_items * 100:.1f}%）；{ev_c}")
    ok_r, ev_r = in_each("3,545 真实")
    add("真实条目数与文档一致（3,545）", n_real == 3545 and ok_r,
        f"实测真实 {n_real}；{ev_r}")

    # 跑泄漏检查器，取它自己报的字段数 —— **不自己重算**，
    # 因为"覆盖面"的定义属于那检查器；本章要验的是"文档与它一致"。
    chk = DATA / "check_no_leakage.py"
    if not chk.is_file():
        add("泄漏检查器存在", False, "找不到 check_no_leakage.py")
    else:
        p = subprocess.run([sys.executable, str(chk), "--items", str(items_p),
                            "--truth", str(truth_p), "--quiet"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        clean = p.returncode == 0
        add("泄漏检查通过（0 泄漏）", clean,
            "退出码 0" if clean else f"退出码 {p.returncode}：{out.strip()[-120:]}")
        m = re.search(r"字符串字段\s*(\d+)\s*个", out)
        if m:
            n_field = int(m.group(1))
            # ⚠️ 两段式：
            #   ① `in_each` —— 核心两份文档必须**都写对**；
            #   ② **数值矛盾扫描** —— 任何**其它**文档只要提到"N 个字符串字段"，
            #      那个 N 也必须对。加②的直接原因：`tasks/T2/README.md` 一直写着
            #      **40,110**（旧值），而它不在 DOCS 里，所以两份文档都对、它也漏网。
            #      **"只扫两份文档"就等于给第三份文档开了豁免** ——
            #      这和 T1 区间检查只扫 2 份文档是同一个毛病。
            bad = []
            for name, text in DOCS.items():
                for s in re.findall(r"覆盖\s*([\d,]+)\s*个字符串字段", text):
                    if int(s.replace(",", "")) != n_field:
                        bad.append(f"{name} 写 {s}")

            # 扫**所有** T2 相关文档（含 tasks/T2/README.md 与数据卡）
            extra_docs = [
                "tasks/T2/README.md",
                "tasks/T2/data/T2_DATASET_CARD.md",
                "docs/PLAIN_LANGUAGE.md",
            ]
            scanned = 0
            for rel in extra_docs:
                p = ROOT / rel
                if not p.is_file():
                    continue
                scanned += 1
                for ln, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    for s in re.findall(r"([\d,]+)\s*个字符串字段", line):
                        if int(s.replace(",", "")) != n_field:
                            bad.append(f"{rel}:{ln} 写 {s}")
            add("泄漏检查覆盖的字段数与文档一致（逐文档 + 全文档扫描）", not bad,
                f"实测 {n_field}；另扫了 {scanned} 份文档"
                + ("；对不上：" + "、".join(bad) if bad else "；各文档一致"))
        else:
            add("能从泄漏检查输出里读到字段数", False,
                f"没匹配到『字符串字段 N 个』：{out.strip()[-120:]}")

    # 公开集 / 轮换池
    pub, rot = DATA / "public" / "items.jsonl", DATA / "rotation" / "items.jsonl"
    if pub.is_file() and rot.is_file():
        npub, nrot = count_jsonl(pub), count_jsonl(rot)
        o1, e1 = in_each("3,789")
        o2, e2 = in_each("937")
        add("公开集 / 轮换池与文档一致（3,789 / 937）", npub == 3789 and nrot == 937 and o1 and o2,
            f"实测公开 {npub} · 轮换 {nrot}；{e1}；{e2}")
        add("公开 + 轮换 = 全集（不重不漏）", npub + nrot == n_items,
            f"{npub} + {nrot} = {npub + nrot} vs 全集 {n_items}")
    else:
        add("公开集 / 轮换池文件存在", None,
            "缺 public/ 或 rotation/（这两处由 split_public_rotation.py 生成，未随仓库发布）")

    # ---- 镜像 pin 已在前面跑过（check_image_pin）-------------------------------

    w = max(len(c) for c, _, _ in results)
    if not args.quiet:
        print(f"{'断言'.ljust(w)}  结论")
        print("-" * (w + 40))
        for claim, ok, ev in results:
            mark = "✅ 通过" if ok is True else ("❌ 不符" if ok is False else "⚠️ 无法验证")
            print(f"{claim.ljust(w)}  {mark}")
            print(f"{' ' * w}  └ {ev}")

    n_bad = sum(1 for _, ok, _ in results if ok is False)
    un = sum(1 for _, ok, _ in results if ok is None)
    print(f"\n共 {len(results)} 条：通过 {len(results) - n_bad - un} · 不符 {n_bad} · 无法验证 {un}")
    if n_bad:
        for claim, ok, ev in results:
            if ok is False:
                print(f"  ❌ {claim}\n     └ {ev}")
        print("❌ 文档里的 T2 数字与实际不符 —— **改文档，不要改事实**。")
        return 1
    print("✅ T2 的关键数字与文档一致（且泄漏检查实跑通过）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
