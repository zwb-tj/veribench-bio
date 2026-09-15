#!/usr/bin/env python3
"""记录 / 核对「镜像 digest ↔ 构建输入」的对应关系。**T1 与 T2 共用这一份实现。**

为什么需要它
------------
2026-09 实测发现：T1 的 `result.json` 里 pin 的镜像 digest 是
`sha256:c33862bb…`，**但那个镜像是「剥离 rtg 捆绑 JRE」之前的旧构建**（469 MB，
里面还留着 `jre/lib/amd64/*.so`）。而仓库当前 `Dockerfile` 构建出来的是
356 MB 的**另一个**镜像。

也就是说：**「digest 已 pin」这个说法，pin 的是一个跟当前 Dockerfile 对不上的镜像。**
而原来的检查只问「result.json 里有没有 digest」—— 有，于是报 ✅。
**一个只看「有没有」的检查，无法发现「对不对」。**

处置：把「对不对」变成可执行的 ——
  · 对构建输入（Dockerfile / run.sh / grade.py / scripts / licenses…）整体取哈希，
    记为 `source_sha256`，与镜像 digest 一起存进 `<task>/IMAGE_DIGEST.json`。
  · 之后任何构建输入被改动，`--check` 就会报「记录的 digest 已与源码脱节，需重建」。
  · 于是 digest **不再是一个孤立的字符串**，而是「由这批源码构建出来的那个镜像」的凭据。

⚠️ 为什么不给每个任务各写一份
--------------------------
T1 先有了这个脚本。补 T2 时如果**复制一份**，就会立刻制造出本项目反复踩的
「同一事实写两遍」bug（schema.required vs 审计器 REQUIRED_FIELDS、
两个工具各存一份 not_published…）。所以这里做成 `--task T1|T2` 参数化的**单一实现**。

用法
----
    # 记录（构建并实跑之后调用）
    python3 record_image_digest.py --task T1 --image-id sha256:1f5c66…

    # 核对（CI / run_all_checks / verify_*_claims 调用）
    python3 record_image_digest.py --task T1 --check
    python3 record_image_digest.py --check-all        # 所有任务

注意
----
`--check` **不重新构建镜像**（那要网络和几分钟）。它验的是「源码有没有动过」，
也就是「这个 digest 还能不能代表当前源码」。真正的等价性仍要靠实跑，
所以记录文件里同时存着实跑证据（得分 / 变异数）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # bio-eval/


class Unavailable(Exception):
    """本机缺少**生成型**构建输入，无法计算可比的 source_sha256。

    这不是错误，是"还没生成"。必须与"源码漂移"分开报 —— 否则新 clone
    或清室检验会收到一堆假警报，而假警报会训练人忽略真警报。
    """

#: 每个任务的构建输入。**加了新的构建输入就要加到这里**，
#: 否则源码改了而哈希不变，这道检查会静默失效。
#:
#: `files` 是固定路径，`globs` 是通配。
#: `generated` 是**由上游数据生成、且刻意不随仓库发布**的构建输入
#:   （如 T2 的 `data/items.jsonl`）。它们缺席时不能算"源码漂移" ——
#:   新 clone 的人本来就没有它们（要跑取数脚本才有）。缺席时**明确 SKIP**。
TASKS: dict[str, dict] = {
    "T1": {
        "dir": "tasks/T1",
        "files": ["Dockerfile", "run.sh", "grade.py", "inspect_image.py"],
        "globs": ["scripts/*.sh", "licenses/**/*"],
        "generated": [],
    },
    "T2": {
        "dir": "tasks/T2",
        "files": [
            "Dockerfile", "run.sh", "grade.py",
            "data/items.jsonl", "data/check_no_leakage.py",
        ],
        "globs": [],
        # items.jsonl 也算构建输入：它是 COPY 进镜像的题面。
        # 它变了而镜像没重建 → "验证过的镜像"与"仓库里的题面"就不是一回事。
        #
        # ⚠️ 但它是**生成物且不发布**（`scripts/not_published.json` 里登记为不发布），
        #    所以清室检验/新 clone 里它不存在。**不存在 ≠ 源码漂移**，
        #    这时必须 SKIP 并说清楚，而不是报"镜像已脱节"（那是假警报）。
        "generated": ["data/items.jsonl"],
    },
}


def build_input_files(task: str) -> tuple[list[Path], list[str]]:
    """返回 (存在的构建输入, 缺席的生成型输入)。

    缺席的**非生成型**输入会在 check() 里被判为失败（源码结构变了）。
    """
    spec = TASKS[task]
    base = ROOT / spec["dir"]
    generated = set(spec.get("generated") or [])
    out: set[Path] = set()
    missing_generated: list[str] = []

    def consider(rel: str, p: Path) -> None:
        if p.is_file():
            out.add(p)
        elif rel in generated:
            missing_generated.append(rel)
        # 非生成型且不存在：不加入，由 check() 用清单比对发现

    for rel in spec["files"]:
        consider(rel, base / rel)
    for pat in spec["globs"]:
        for p in base.glob(pat):
            if p.is_file():
                out.add(p)
    return sorted(out), sorted(missing_generated)


def source_sha256(task: str) -> tuple[str, list[str]]:
    """对构建输入整体取哈希。路径也进哈希，防止改名绕过。

    ⚠️ **不可比时抛 Unavailable**：如果某些**生成型**输入（如 T2 的 `data/items.jsonl`）
    在本机不存在，那么算出来的哈希只覆盖了一部分输入 ——
    拿它去和记录比必然"不等"，但那是**假警报**，不是源码漂移。
    这种情况必须显式区分（清室检验里就撞上了）。
    """
    base = ROOT / TASKS[task]["dir"]
    paths, missing = build_input_files(task)
    if missing:
        raise Unavailable(
            f"[{task}] 缺生成型构建输入 {missing} —— 本机尚未生成，"
            "无法计算可比的 source_sha256")
    h = hashlib.sha256()
    names: list[str] = []
    for p in paths:
        rel = p.relative_to(base).as_posix()
        names.append(rel)
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(p.read_bytes()).hexdigest().encode("ascii"))
        h.update(b"\n")
    return h.hexdigest(), names


def record_path(task: str) -> Path:
    return ROOT / TASKS[task]["dir"] / "IMAGE_DIGEST.json"

def check(task: str) -> int:
    """核对某个任务的记录是否与当前源码对应。

    返回 0（一致）或 1（不一致 / 缺记录）。**不可比时返回 0 但打印 SKIP** ——
    "本机还没生成数据"不是文档错误，不该让检查失败（否则清室检验永远红）。
    """
    rec_p = record_path(task)
    try:
        cur, names = source_sha256(task)
    except Unavailable as exc:
        print(f"SKIP: {exc}")
        return 0
    if not rec_p.is_file():
        print(f"❌ [{task}] 缺 {rec_p.relative_to(ROOT).as_posix()} —— 没有任何 pin 记录")
        return 1
    rec = json.loads(rec_p.read_text(encoding="utf-8"))
    old = rec.get("source_sha256")
    if old == cur:
        print(f"✅ [{task}] 镜像记录与当前源码对应"
              f"（source_sha256 = {cur[:16]}…，覆盖 {len(names)} 个构建输入）")
        print(f"   image_id     = {rec.get('image_id')}")
        print(f"   构建输入      = {', '.join(names)}")
        return 0
    print(f"❌ [{task}] 记录的镜像 digest 已与当前源码脱节 —— 必须重建镜像并重新实跑")
    print(f"   记录 source_sha256 = {str(old)[:16]}…")
    print(f"   当前 source_sha256 = {cur[:16]}…")
    old_files = set(rec.get("files") or [])
    new_files = set(names)
    if old_files - new_files:
        print(f"   记录里有、现在没有：{sorted(old_files - new_files)}")
    if new_files - old_files:
        print(f"   现在有、记录里没有：{sorted(new_files - old_files)}")
    if old_files == new_files:
        print("   （构建输入清单一致 → 是**文件内容**变了）")
    print(f"   重建：docker build -t veribench-bio/{task.lower()}:dev {TASKS[task]['dir']} && "
          f"实跑一遍再 --task {task} --image-id 记录")
    return 1


def self_test() -> int:
    """负向测试：证明"源码一变，检查就失败"。

    这是本项目最核心的一条不变量 —— 如果它在源码变更时仍然报 ✅，
    那 pin 就退化成一句自我表扬（T1 的 digest 正是这么栽的）。
    """
    import shutil
    import tempfile

    global ROOT  # noqa: PLW0603  —— 必须在任何 ROOT 读取之前声明
    ok = True
    real_root = ROOT
    tmp = Path(tempfile.mkdtemp(prefix="rid-selftest-"))
    try:
        ROOT = tmp
        # 造一个最小任务
        t = tmp / "tasks" / "TX"
        t.mkdir(parents=True)
        (t / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        (t / "run.sh").write_text("echo hi\n", encoding="utf-8")
        TASKS["TX"] = {"dir": "tasks/TX", "files": ["Dockerfile", "run.sh"], "globs": []}

        h1, names = source_sha256("TX")

        def rec():
            (t / "IMAGE_DIGEST.json").write_text(json.dumps({
                "task": "TX", "image_id": "sha256:deadbeef",
                "source_sha256": h1, "files": names,
            }), encoding="utf-8")

        def report(name: str, want_ok: bool) -> None:
            rc = check("TX")
            passed = (rc == 0) == want_ok
            nonlocal ok
            if not passed:
                ok = False
            print(f"  {'✅' if passed else '❌'} {name}: 退出码 {rc}，"
                  f"期望{'通过' if want_ok else '失败'}")

        # ⚠️ 必须**边改边查**，不能先把 lambda 收集起来再统一跑。
        #    第一版就是收集成 `cases` 列表、最后一次性执行 —— 结果用例 ⑤ 的改动
        #    泄漏进了前面的用例，①②④ 全部误报失败。
        #    这个 bug 是被**本自检自己**抓出来的（否则我会以为检查坏了）。

        # ① 没记录时必须失败
        report("未记录任何 pin → 失败", False)

        # ② 记录后再查 → 通过
        rec()
        report("记录与源码一致 → 通过", True)

        # ③ 改动一个构建输入 → 必须失败（核心用例）
        (t / "run.sh").write_text("echo CHANGED\n", encoding="utf-8")
        report("**改了一个构建输入 → 失败**", False)

        # ④ 还原 → 重新通过
        (t / "run.sh").write_text("echo hi\n", encoding="utf-8")
        report("还原 → 重新通过", True)

        # ⑤ 只改文件名（内容不变）→ 也必须失败（防"改名绕过"）
        (t / "run2.sh").write_text("echo hi\n", encoding="utf-8")
        TASKS["TX"] = {"dir": "tasks/TX", "files": ["Dockerfile", "run2.sh"], "globs": []}
        report("只改文件名（内容不变）→ 失败（防改名绕过）", False)
    finally:
        ROOT = real_root
        TASKS.pop("TX", None)
        shutil.rmtree(tmp, ignore_errors=True)

    print("负向测试 " + ("全部通过（含 3 个必须失败的用例）" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="记录或核对镜像 digest 与构建源码的对应关系")
    ap.add_argument("--task", choices=sorted(TASKS), help="哪个任务（T1/T2）")
    ap.add_argument("--check-all", action="store_true", help="核对所有任务")
    ap.add_argument("--check", action="store_true", help="核对当前源码是否与记录一致")
    ap.add_argument("--self-test", action="store_true", help="跑的负向测试，证明检查会失败")
    ap.add_argument("--image-id", help="要记录的镜像 ID / digest（sha256:...）")
    ap.add_argument("--run-score", help="实跑得分（可选，作为佐证一起记录）")
    ap.add_argument("--run-variants", help="实跑变异数（可选）")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if args.check_all:
        rc = 0
        for t in sorted(TASKS):
            rc |= check(t)
        return rc

    if not args.task:
        print("需要 --task T1|T2（或 --check-all）", file=sys.stderr)
        return 2

    if args.check:
        return check(args.task)

    if not args.image_id:
        print("需要 --image-id（记录模式）或 --check", file=sys.stderr)
        return 2

    base = ROOT / TASKS[args.task]["dir"]
    cur, names = source_sha256(args.task)
    data = {
        "_comment": "镜像 digest 与构建源码的对应凭据。由 scripts/record_image_digest.py "
                    "写入，由 verify_*_claims.py / run_all_checks.py 核对。"
                    "改动任何构建输入都必须重建镜像、重跑、再重记。",
        "task": args.task,
        "image_id": args.image_id,
        "source_sha256": cur,
        "files": names,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if args.task == "T1":
        data["note"] = (
            "2026-09 修正：此前 result.json pin 的 sha256:c33862bb… 是"
            "「剥离 rtg 捆绑 JRE 之前」的旧镜像（469 MB，含 jre/lib/amd64），"
            "与当前 Dockerfile（第 99 行 rm -rf jre，产物 356 MB）**对不上**。"
            "本文件记录的才是当前源码构建出的镜像。")
    if args.run_score:
        data["run_evidence"] = {
            "score": args.run_score,
            "variants": args.run_variants,
        }
    rec_p = record_path(args.task)
    rec_p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {rec_p.relative_to(ROOT).as_posix()}")
    print(f"   task          = {args.task}")
    print(f"   image_id      = {args.image_id}")
    print(f"   source_sha256 = {cur}")
    print(f"   构建输入       = {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
