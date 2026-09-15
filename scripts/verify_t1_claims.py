#!/usr/bin/env python3
"""**重新测量** T1 的关键断言，并与文档里写的数字比对。

和 `verify_t2_claims.py` 同一个思路：T1 的招牌数字（得分、F1、运行时长、manifest 哈希）
都写在 README / DATACARD 里，**但此前从来没有东西把它们与实际产物对过**。

第一次跑本脚本就抓到一条**与事实相反的文档断言**：
README 的 v1 四件套里写着"**镜像 digest 尚未 pin**"，
而 `_runs/result.json` 里明明记着 `image_digest = sha256:c33862bb…`。
（`manifest_hash` 也是记着的，而且可复算。）

之所以能重新测量：T1 的运行产物（`_runs/`）与数据 manifest 都还在本地。

可复算性分三档，脚本会分开报：
  · **可复算**：能从产物重新算出来并与文档对上（如 score = mean(F1_snp, F1_indel)）
  · **已记录**：产物里记着，但需要原镜像才能重新导出（如 image_digest）
  · **无法验证**：需要 Docker + 上游下载（如"重跑 55 秒"）

⚠️ 2026-09 又抓到三条，都是**检查本身太弱**造成的假保证：
  1. **镜像 digest 只验"有没有"，不验"对不对"。** 实测那个 digest 是
     「剥离 rtg 捆绑 JRE 之前」的旧镜像（469 MB，含 `jre/lib/amd64`），
     与当前 `Dockerfile`（356 MB）**根本不是同一个**。现在改成核对
     `IMAGE_DIGEST.json` 里的**构建源码哈希**（用 `record_image_digest.py`
     的同一个实现算，不另写一份）。
  2. **"运行时长 == 55" 是把单点当事实。** 四次独立实跑是 55 / 46 / 41 / 39。
     现在要求文档给出**区间**，并验证本地实测落在区间内。
  3. **实跑证据与 pin 的镜像必须是同一个。** 否则"跑过的"和"pin 的"是两回事，
     新增了一条对照 `_runs_repro2/result.json` 与 `IMAGE_DIGEST.json` 的断言。

用法：
    python3 verify_t1_claims.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                    # bio-eval/
T1 = ROOT / "tasks" / "T1"

results: list[tuple[str, str, bool | None, str]] = []


def add(claim: str, kind: str, ok: bool | None, ev: str) -> None:
    results.append((claim, kind, ok, ev))


def f1_of(name: str) -> float | None:
    p = T1 / "_runs" / "vcfeval" / name / "summary.txt"
    if not p.is_file():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[0] == "None":
            return float(parts[-1])
    return None


def _load_recorder():
    """加载共享的 `scripts/record_image_digest.py` 的**同一个实现**。

    刻意不在这里重写一遍哈希逻辑 —— 「两份真源」是本项目的惯犯 bug
    （schema.required vs 审计器 REQUIRED_FIELDS、两个工具各存一份 not_published…）。
    2026-09 进一步把它从 `tasks/T1/scripts/` 提到仓库级 `scripts/`，
    并参数化成 `--task T1|T2` —— 否则补 T2 时只能再复制一份，就等于又造了两份真源。
    """
    import importlib.util

    p = ROOT / "scripts" / "record_image_digest.py"
    spec = importlib.util.spec_from_file_location("_rid", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    # ⚠️ 必须有 argparse：全仓冒烟测试（smoke_test_scripts.py）对每个 .py 跑
    #    `--help` 并期望退出码 0。此前本脚本没有 argparse，于是 `--help` 会**真的去跑检查**，
    #    一旦查出真问题（比如 digest 与源码脱节）就返回 1，被冒烟测试报成
    #    "这个脚本连 --help 都跑不起来"——**把"检查发现真问题"误报成"脚本坏了"**。
    #    检查器的正确约定是：--help 只打印用法，绝不执行检查。
    ap = argparse.ArgumentParser(
        description="重新测量 T1 的关键断言，并与文档比对（不改任何文件）")
    ap.add_argument("--quiet", action="store_true", help="只打印结论行")
    args = ap.parse_args(argv)

    res_p = T1 / "_runs" / "result.json"
    man_p = T1 / "_data" / "manifest.json"
    if not res_p.is_file():
        print("SKIP: 缺 tasks/T1/_runs/result.json —— T1 未跑过（运行产物不随仓库发布）")
        return 0

    res = json.loads(res_p.read_text(encoding="utf-8"))
    README = (ROOT / "README.md").read_text(encoding="utf-8")
    CARD = (ROOT / "docs" / "DATACARD.md").read_text(encoding="utf-8")
    docs = README + CARD

    # ---- 可复算 ----
    s_snp, s_ind = f1_of("eval_snps"), f1_of("eval_indels")
    if s_snp is not None and s_ind is not None:
        recomputed = (s_snp + s_ind) / 2
        add("score = mean(F1_snp, F1_indel) 可复算", "可复算",
            abs(recomputed - res["score"]) < 1e-9,
            f"({s_snp} + {s_ind}) / 2 = {recomputed:.5f} vs result.json {res['score']}")

        # ⚠️ 不能写成"正确数字出现在 README+DATACARD 拼起来的文本里" ——
        #    那样**只要有一份文档写对就通过**。我第一次的负向测试正是这么漏掉的：
        #    把 README 的 0.84655 改成 0.99999，检查器仍报 ✅，因为 DATACARD 里还有对的。
        #    正确做法：**逐文档**扫 T1 相关行上的数字，任何一个对不上就报错。
        allowed = {f"{recomputed:.5f}", f"{s_snp:.4f}", f"{s_ind:.4f}",
                   f"{res['all_variants']['f1']:.4f}",
                   f"{res['all_variants']['precision']:.4f}",
                   f"{res['all_variants']['sensitivity']:.4f}",
                   f"{res['per_type']['snps'].get('f1', 0):.4f}",
                   f"{res['per_type']['indels'].get('f1', 0):.4f}"}
        allowed = {a for a in allowed if a and not a.startswith("0.0000")}
        bad_nums: list[str] = []
        for name, text in (("README.md", README), ("docs/DATACARD.md", CARD)):
            for ln, line in enumerate(text.splitlines(), 1):
                if not any(k in line for k in ("T1", "得分", "SNP", "INDEL", "score")):
                    continue
                for num in re.findall(r"0\.\d{3,5}", line):
                    if num not in allowed:
                        bad_nums.append(f"{name}:{ln} 出现 {num}")
        add("两份文档里 T1 相关行上的数字都与实测一致", "可复算",
            not bad_nums,
            ("全部一致（允许值 " + "、".join(sorted(allowed)) + "）") if not bad_nums
            else "对不上：" + "；".join(bad_nums[:5]))

    if man_p.is_file():
        raw = man_p.read_bytes()
        add("manifest_hash = sha256(manifest.json) 可复算", "可复算",
            hashlib.sha256(raw).hexdigest() == res.get("manifest_hash"),
            f"实测 {hashlib.sha256(raw).hexdigest()[:24]}… vs 记录 {str(res.get('manifest_hash'))[:24]}…")
        man = json.loads(raw)
        files = man.get("files") or man
        if isinstance(files, dict):
            files = [{"path": k, **(v if isinstance(v, dict) else {"sha256": v})}
                     for k, v in files.items()]
        ok = miss = 0
        for f in files:
            rel, want = f.get("path") or f.get("name"), f.get("sha256")
            fp = T1 / "_data" / rel
            if not fp.is_file():
                miss += 1
                continue
            if want and hashlib.sha256(fp.read_bytes()).hexdigest() == want:
                ok += 1
        add(f"manifest 里 {len(files)} 个文件的 sha256 逐字节可复算", "可复算",
            ok > 0 and miss == 0,
            f"通过 {ok} · 缺文件 {miss}（缺的是未随仓库发布的数据）")

    # ---- 已记录（需原镜像才能重新导出）----
    # ⚠️ 这里**不要**用「文档里没有『尚未 pin』这句话」当判据 ——
    #    那个字符串会被**引用历史错误**的句子命中（我第一次就是这么误报的）。
    manifest_line_checked = bool(
        re.search(r"^- \[x\] \*\*可复现 manifest", README, re.M))

    # ⚠️ 2026-09 修：原来这里只问「result.json 里有没有 digest」—— 有，就报 ✅。
    #    实测发现那个 digest（`sha256:c33862bb…`）是**剥离 rtg 捆绑 JRE 之前**的旧镜像
    #    （469 MB，里面还留着 jre/lib/amd64/*.so），跟当前 Dockerfile
    #    （第 99 行 `rm -rf /opt/rtg-tools/jre`，产物 356 MB）**根本不是同一个镜像**。
    #    「有没有」不等于「对不对」—— 只问存在性的检查，正是本项目反复踩的那类坑。
    #    现在改成核对**源码哈希**：镜像 pin 必须由当前这批构建输入算得出来。
    rid = _load_recorder()
    cur_hash, names = rid.source_sha256("T1")
    rec_p = T1 / "IMAGE_DIGEST.json"
    rec = json.loads(rec_p.read_text(encoding="utf-8")) if rec_p.is_file() else {}
    add("镜像 pin 与当前构建源码对应（不只是「有记录」）", "可复算",
        bool(rec) and rec.get("source_sha256") == cur_hash,
        f"记录 {str(rec.get('source_sha256'))[:16]}… vs 当前 {cur_hash[:16]}…"
        f"（覆盖 {len(names)} 个构建输入）· image_id {rec.get('image_id')}")

    # 实跑证据必须与 pin 的镜像是**同一个** —— 否则「跑过的」和「pin 的」是两回事。
    # ⚠️ 不写死 `_runs_repro2`：每重建一次镜像就会多一个 `_runs_reproN`。
    #    写死目录会让这条断言在下次重建后**静默失效**（找不到文件就跳过），
    #    那正是本项目反复踩的"检查悄悄不跑了"。改成扫全部 repro 记录。
    repro_dirs = sorted(T1.glob("_runs_repro*"))
    matched = None
    for d in repro_dirs:
        rp = d / "result.json"
        if not rp.is_file():
            continue
        try:
            ev = json.loads(rp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if rec and ev.get("image_digest") == rec.get("image_id"):
            matched = (d, ev)
            break
    if matched:
        d, ev = matched
        tc = d / "timing_call.json"
        nvar = json.loads(tc.read_text(encoding="utf-8"))["variants"] if tc.is_file() else "?"
        add("存在与 pin 的镜像**完全一致**的实跑证据", "可复算",
            ev.get("score") == 0.84655 and nvar == 12254,
            f"{d.name}/result.json · digest {str(ev.get('image_digest'))[:20]}… · "
            f"score {ev.get('score')} · 变异 {nvar}")
    else:
        add("存在与 pin 的镜像**完全一致**的实跑证据", "可复算", False,
            f"pin 的是 {str(rec.get('image_id'))[:20]}…，但 {len(repro_dirs)} 个 repro 目录里"
            "没有一个是在该镜像上跑的 —— 必须在该镜像上重跑一遍再 pin")

    # 每一个 `_runs*` 目录都必须在 not_published.json 里被声明为"不发布"。
    # ⚠️ 加这条的直接原因：`_runs_repro3` 建出来之后**忘了登记**，
    #    于是 clean_room_check 把它当成"会被发布的文件"复制进清室目录。
    #    枚举式登记必然会漏 —— 所以用检查把"漏"变成失败，而不是靠人记得。
    # 2026-09 扩展：补 T2 时发现 `tasks/T2/_runs` **也是同样的漏法**。
    #    只查 T1 就等于给自己开特例 —— 所以这里扫**所有 tasks/** 下的 `_runs*`。
    np_p = ROOT / "scripts" / "not_published.json"
    if np_p.is_file():
        np_dirs = set(json.loads(np_p.read_text(encoding="utf-8")).get("dirs") or {})
        undeclared = [
            d.relative_to(ROOT).as_posix()
            for d in sorted((ROOT / "tasks").glob("*/_runs*")) if d.is_dir()
            and d.relative_to(ROOT).as_posix() not in np_dirs
        ]
        add("所有 tasks/*/_runs* 目录都已在 not_published 里登记", "可复算",
            not undeclared,
            "全部已登记" if not undeclared
            else f"**未登记**：{undeclared} —— 它们会被当成发布内容")

    add("README 把「可复现 manifest」勾为完成", "已记录", manifest_line_checked,
        f"README 的 manifest 项{'已勾选' if manifest_line_checked else '**仍是未勾**'}")
    add("工具链已记录", "已记录",
        res.get("toolchain") == {"caller": "freebayes", "grader": "rtg vcfeval",
                                "splitter": "bcftools"},
        json.dumps(res.get("toolchain"), ensure_ascii=False))

    # ⚠️ 以前这里断言 `wall_clock_sec == 55`（单值）。四次独立实跑是 55/46/41/39 ——
    #    挂钟时间本来就会变。把**单点当事实**写进文档，就是在把噪声说成结果。
    #    改成：文档里必须给出**区间**，且本地实测值落在区间内。
    m_range = re.search(r"(\d+)\s*[–\-]\s*(\d+)\s*秒", README)
    if m_range:
        lo, hi = int(m_range.group(1)), int(m_range.group(2))
        measured = res.get("wall_clock_sec")
        add("运行时长以区间记录，且本地实测落在区间内", "可复算",
            isinstance(measured, int) and lo <= measured <= hi,
            f"文档区间 {lo}–{hi} 秒 · 本地实测（run A）{measured} 秒")
    else:
        add("运行时长以区间记录（不是单点）", "可复算", False,
            "README 里找不到「N–M 秒」形式的区间 —— 单点数字会把运行噪声说成事实")

    # ---- 无法验证 ----
    add("在 arm64 上实跑通过", "无法验证", None, "需 Docker + QEMU 环境，本轮未重跑")
    add("HF 数据集 100.4 MB / 7 文件且逐字节一致", "无法验证", None,
        "需联网读取 HF（仓库当前为 Private）")

    w = max(len(c) for c, _, _, _ in results)
    if not args.quiet:
        print(f"{'断言'.ljust(w)}  {'档位':<8}结论")
        print("-" * (w + 40))
        for claim, kind, ok, ev in results:
            mark = "✅" if ok is True else ("❌" if ok is False else "⚠️")
            print(f"{claim.ljust(w)}  {kind:<8}{mark}")
            print(f"{' ' * w}  └ {ev}")

    n_bad = sum(1 for _, _, ok, _ in results if ok is False)
    un = sum(1 for _, _, ok, _ in results if ok is None)
    rep = sum(1 for _, k, ok, _ in results if k == "可复算" and ok)
    print(f"\n共 {len(results)} 条：可复算通过 {rep} · 不符 {n_bad} · 无法验证 {un}")
    if n_bad:
        # 逐条列出不符项，避免 --quiet 时只剩一句结论、看不到是哪条
        for claim, _, ok, ev in results:
            if ok is False:
                print(f"  ❌ {claim}\n     └ {ev}")
        print("❌ T1 的文档断言与实际产物不符 —— **改文档，不要改事实**。")
        return 1
    print("✅ T1 的可复算断言全部与产物一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
