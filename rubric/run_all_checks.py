#!/usr/bin/env python3
"""一条命令跑完第二支柱的所有检查。

为什么需要它
-----------
我这轮**第三次**在中文文本里混进 ASCII 双引号，导致 SyntaxError —— 而这类错误
只有真正导入/编译那个文件时才暴露。手跑 `py_compile` 是我临时想起来的，不该靠记得。

所以固化成一个脚本：
    python3 run_all_checks.py

它做三件事：
  1. **语法编译检查**（所有 scripts/ 与 fixtures/ 下的 .py）
  2. **各脚本的自检**（kappa / judge_eval / 结构预检 / 标注校验 / judge I/O 链）
  3. 汇总通过/失败，**失败必须让退出码非零**

顺带记录一个反复出现的教训：**中文文本里出现 ASCII 引号是高频错误**，
所以第 1 步不是形式主义 —— 它是唯一能在"运行前"抓住这类错误的检查。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE  # ← 本文件就在 rubric/ 下。⚠️ 第一版写成 HERE.parent，
             #   结果去编译了 bio-eval/scripts/ 的文件，还报"看不见 kappa.py"。


def clean_pycache() -> int:
    """删掉 __pycache__。⚠️ Python 在 import 时会自动生成它，
    仓库每次跑检查都脏一遍很烦 —— 所以子进程一律带 PYTHONDONTWRITEBYTECODE=1，
    并且每次开跑前先清一次。"""
    n = 0
    for d in ROOT.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
        n += 1
    for f in ROOT.rglob("*.pyc"):
        f.unlink(missing_ok=True)
        n += 1
    return n


def compile_all() -> list[str]:
    bad: list[str] = []
    targets = list((ROOT / "scripts").glob("*.py")) + list((ROOT / "fixtures").glob("*.py"))
    print(f"=== 1) 语法编译检查（{len(targets)} 个文件）===")
    for f in sorted(targets):
        try:
            # ⚠️ 用 compile() 而不是 py_compile：后者会在源码目录里生成 .pyc，
            #    把工作区弄脏（第一版就是这么干的）。compile() 只检查语法、不落文件。
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
            print(f"  ✅ {f.name}")
        except SyntaxError as exc:
            print(f"  ❌ {f.name}: 第 {exc.lineno} 行: {exc.msg}")
            bad.append(f.name)
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ {f.name}: {type(exc).__name__}: {exc}")
            bad.append(f.name)
    return bad


def run(cmd: list[str], expect_zero: bool = True) -> bool:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    combined = [l for l in ((p.stdout or "") + (p.stderr or "")).strip().splitlines() if l.strip()]
    last = combined[-1] if combined else "(无输出)"
    # ⚠️ 「跳过」必须与「通过」区分开。
    #    有些输入是**刻意不发布**的（PMC 全文、判分产出），第三方 clone 下来必然没有。
    #    这种情况下脚本应当输出 `SKIP:` 并以 0 退出 —— 这是"没跑"，不是"跑对了"。
    #    把它算成通过会掩盖问题；算成失败会让第三方卡在一个假故障上。
    #    清室检验（scripts/clean_room_check.py）就是靠这条约定判断的。
    if any("SKIP:" in l for l in combined):
        print(f"  ⏭ {' '.join(Path(c).name for c in cmd)}  → {last[:95]}")
        return True
    ok = (p.returncode == 0) if expect_zero else True
    print(f"  {'✅' if ok else '❌'} {' '.join(Path(c).name for c in cmd)}  → {last[:95]}")
    if not ok:
        # 失败时把最近几行打出来 —— 不能把有用的错误吞掉（本项目原则 7）
        for line in combined[-6:]:
            print(f"      {line}")
    return ok


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    py = sys.executable
    S = str(ROOT / "scripts")
    F = str(ROOT / "fixtures")

    removed = clean_pycache()
    if removed:
        print(f"（已清理 {removed} 个字节码残留）")
    bad = compile_all()

    print("\n=== 1b) 中文串引号自检（我犯过 7 次的错）===")
    # 编译检查已经能抓"会失败"的那种；这个额外抓"藏在三引号里、当前能编译"的隐患。
    run([py, f"{S}/lint_zh.py"])

    print("\n=== 2) 各脚本自检 ===")
    results = [
        run([py, f"{S}/kappa.py", "--self-test"]),
        run([py, f"{S}/judge_eval.py", "--self-test"]),
        run([py, f"{S}/make_annotation_sheets.py", "--items",
             f"{F}/sample_items.jsonl", "--check-only"], expect_zero=True),
        run([py, f"{S}/make_annotation_sheets.py", "--validate",
             f"{F}/fixture_ann_A.jsonl"]),
        # ⚠️ **盲评必须真的是盲的。** 2026-09 发现：标注表把三份回答标成
        #    `BLIND-weak`/`BLIND-medium`/`BLIND-strong` —— `weak`/`strong`
        #    本身就是质量标签，而说明书写着「编号本身不告诉你哪份好」，**那句话是假的**。
        #    后果不是"不够优雅"：标注者照标签走 → κ 假性偏高 → 人类天花板虚高 →
        #    judge 的"相对上限"被压低 → **结论反了**，而数据看起来完全正常。
        run([py, f"{S}/check_annotation_blinding.py", "--self-test"]),
        run([py, f"{S}/check_annotation_blinding.py"]),
        # ⚠️ **判分链与操纵检验链必须用同一份 prompt 拼装。**
        #    2026-09 审计发现两处各抄了一份 `criterion_block()`（逐字节相同），
        #    prompt 正文那 10 行也逐字重复，而 build_manip_inputs 的注释写着
        #    「⚠️ 与 build_judge_inputs 保持一致（**改一处必须改两处**）」——
        #    **那句注释就是缺陷本身**：可比性依赖人记得，就迟早会漂移。
        #    漂移的后果特别隐蔽：操纵检验测的会是**另一个 prompt 的行为**，
        #    而它的结论会被用来为真实判分背书。
        run([py, f"{S}/check_prompt_agree.py", "--self-test"]),
        run([py, f"{S}/check_prompt_agree.py"]),
    ]

    print("\n=== 2b) 人工标注链路端到端演练 ===")
    # ⚠️ 加这一步的直接原因：上一轮发现 `make_annotation_sheets.py` **根本不接受作答输入**，
    #    生成的标注表没有可评的对象，是不可用的 —— 而它能坏那么久，正是因为
    #    **没有任何东西在跑这条链**。工具写了、文档写了、对外声明它是硬阻塞，
    #    却从没有一次端到端运行验证"人来了能不能做"。
    #    这个演练用合成标注者把「生成 → 填分 → 校验 → κ → 裁判对比」跑一遍。
    results.append(run([py, f"{S}/test_annotation_chain.py"]))

    print("\n=== 3) judge I/O 链（含故意破坏，**期望非零退出**）===")
    results.append(run([py, f"{S}/parse_judge_outputs.py",
                        "--index", f"{F}/io/judge_inputs/index.jsonl",
                        "--indir", f"{F}/io/judge_outputs",
                        "--out", f"{F}/io/ann_judge.jsonl"], expect_zero=False))

    print("\n=== 4) 主台账门禁（rubric 题必须过与 T1/T2 相同的 R0–R12）===")
    # 这一节是补的：此前 rubric 与主台账各有一套溯源，主台账的许可门禁
    # 根本管不到 rubric 题。并入之后才有意义。
    items = ROOT / "items" / "items.jsonl"
    if items.is_file():
        led = ROOT / "ledger" / "rubric_items.jsonl"
        results.append(run([py, f"{S}/to_master_ledger.py", "--items", str(items),
                            "--out", str(led), "--created-at", "2026-09-13T00:00:00+00:00"]))
        # ⚠️ 审计器在 bio-eval/scripts/ 下（主台账那套），不在 rubric/scripts/
        auditor = ROOT.parent / "scripts" / "audit_licenses.py"
        if auditor.is_file():
            results.append(run([py, str(auditor), str(led)]))
            results.append(run([py, str(auditor), "--self-test"]))
    else:
        print(f"  ⏭ 尚无 {items.name}，跳过（出题完成后自动纳入）")

    print("\n=== 5) 事实字段裁决核验（contains_human_data）===")    # 这一步防的是本轮真实踩到的坑：某字段被一律填成同一个值却无人发现。
    results.append(run([py, f"{S}/classify_human_data.py",
                        "--sources", str(ROOT / "items" / "sources"),
                        "--candidates", str(ROOT / "items" / "candidates.jsonl"),
                        "--out", str(ROOT / "items" / "human_data_review.json")]))
    if items.is_file():
        results.append(run([py, f"{S}/precheck_items.py", "--items", str(items)]))
        # 裁决文件 ↔ candidates ↔ 题目 三方一致（本轮真实事故的直接防线）
        results.append(run([py, f"{S}/verify_human_data.py"]))
        # 题目引用的数字是否真在原文里（出题时源文被截断，必须对全文重验）
        results.append(run([py, f"{S}/check_numeric_fidelity.py", "--items", str(items),
                            "--sources", str(ROOT / "items" / "sources"),
                            "--out", str(ROOT / "items" / "numeric_fidelity.json")]))

    print("\n=== 6) 裁判区分度（同一裁判对三档答案是否给出递增分数）===")
    # 这条不依赖人类标注，是本项目当前**唯一**能自主取得的效度证据。
    # 缺失裁判产出时跳过而不是失败——因为裁判是由子agent 分批跑的，
    # 没跑完不该让整个检查套件变红。
    blind = ROOT / "fixtures" / "answers" / "judge_blind"
    jout = ROOT / "fixtures" / "answers" / "judge_out"
    jout2 = ROOT / "fixtures" / "answers" / "judge_out_run2"
    if blind.is_dir() and jout.is_dir() and any(jout.glob("*.json")):
        results.append(run([py, f"{S}/judge_discrimination.py",
                            "--blind", str(blind), "--outdir", str(jout),
                            "--out", str(ROOT / "fixtures" / "answers" / "discrimination.json")]))
        # 重测信度：单次判定分不清"标准真缺陷"与"抽样噪声"，必须跑第二轮
        if jout2.is_dir() and any(jout2.glob("*.json")):
            retest_out = ROOT / "fixtures" / "answers" / "retest.json"
            results.append(run([py, f"{S}/judge_retest.py",
                                "--mapping", str(blind / "_mapping.json"),
                                "--run1", str(jout), "--run2", str(jout2),
                                "--out", str(retest_out)]))
            # 把数字落成可执行的改写清单（改了数据就重新生成，别手改文档）
            results.append(run([py, f"{S}/make_revision_list.py",
                                "--retest", str(retest_out),
                                "--discrimination", str(ROOT / "fixtures" / "answers" / "discrimination.json"),
                                "--items", str(items),
                                "--out", str(ROOT / "docs" / "RUBRIC_V1.1_REVISION_LIST.md")]))
        else:
            print("  ⏭ 尚无第二轮裁判产出，跳过重测信度")
    else:
        print("  ⏭ 尚无裁判产出，跳过（跑完 judge_blind 后自动纳入）")

    print("\n=== 7) v1.0 → v1.1 前后对照（需两版各两轮裁判产出）===")
    # 这个对照是**受控实验**：同一批 72 份答案（写答案时看不到任何一版标准）、
    # 同一批题目，唯一变量是 criteria 的锚点结构。两版都必须两轮，
    # 否则会把"标准坏"和"这次手抖"混在一起比。
    V11 = ROOT / "fixtures" / "answers" / "v1.1"
    need = [V11 / "judge_out_run1", V11 / "judge_out_run2"]
    v10bits = [ROOT / "fixtures" / "answers" / "discrimination.json",
               ROOT / "fixtures" / "answers" / "retest.json"]
    if (ROOT / "items" / "items_v1.1.jsonl").is_file() and all(p.is_dir() and any(p.glob("*.json")) for p in need) \
            and all(p.is_file() for p in v10bits):
        v11disc = V11 / "discrimination.json"
        v11ret = V11 / "retest.json"
        results.append(run([py, f"{S}/judge_discrimination.py",
                            "--blind", str(ROOT / "fixtures" / "answers" / "v1.1" / "judge_blind"),
                            "--outdir", str(V11 / "judge_out_run1"), "--out", str(v11disc)]))
        results.append(run([py, f"{S}/judge_retest.py",
                            "--mapping", str(ROOT / "fixtures" / "answers" / "v1.1" / "judge_blind" / "_mapping.json"),
                            "--run1", str(V11 / "judge_out_run1"), "--run2", str(V11 / "judge_out_run2"),
                            "--out", str(v11ret)]))
        results.append(run([py, f"{S}/compare_rubric_versions.py",
                            "--v10-disc", str(v10bits[0]), "--v10-retest", str(v10bits[1]),
                            "--v11-disc", str(v11disc), "--v11-retest", str(v11ret),
                            "--out", str(ROOT / "docs" / "V1.0_VS_V1.1.md")]))
        # 改写清单要对着**改完之后仍然坏掉的**那条，而不是最初的 v1.0 缺陷
        # —— 否则人会照着已经修好的清单再改一遍。
        results.append(run([py, f"{S}/make_revision_list.py",
                            "--retest", str(v11ret), "--discrimination", str(v11disc),
                            "--items", str(ROOT / "items" / "items_v1.1.jsonl"),
                            "--out", str(ROOT / "docs" / "RUBRIC_V1.2_REVISION_LIST.md")]))
        # 先分诊再改写：75% 的"缺陷"改措辞拿不到收益（含 3 条是我自己检验的误报）。
        # 不做这一步就动手改，等于对噪声调参。
        results.append(run([py, f"{S}/defect_triage.py", "--version", "v1.1",
                            "--out", str(ROOT / "fixtures" / "answers" / "defect_triage.json")]))
    else:
        print("  ⏭ v1.1 评判未跑完（需 run1 + run2 两轮），跳过对照")

    print("\n=== 8) 分歧住在哪一档边界 + 量表粒度值不值 ===")
    # 这两条把一个"该改题面还是该改锚点"的判断题变成了测量题。
    # 上一轮我凭裁判的主观反馈断言"根因是后果分句"，实测只解释了 55.6%——
    # 剩下 44.4% 在 0↔1，改题面救不了。所以结论必须先量再下。
    if (ROOT / "fixtures" / "answers" / "retest.json").is_file() and \
            (ROOT / "fixtures" / "answers" / "v1.1" / "retest.json").is_file():
        results.append(run([py, f"{S}/boundary_analysis.py",
                            "--out", str(ROOT / "fixtures" / "answers" / "boundary_analysis.json")]))
        results.append(run([py, f"{S}/scale_reliability.py",
                            "--out", str(ROOT / "fixtures" / "answers" / "scale_reliability.json")]))
    else:
        print("  ⏭ 缺两轮评判结果，跳过")

    print("\n=== 9) 操纵检验（逐条标准：把差异造明确，看裁判分不分得开）===")
    # ⚠️ 这是**唯一**有效的逐条效度检验。第 6/7/8 节那个区分度检验测的是
    #    "标准能否追踪**整体质量**"——它的档位标签是整份答案的，不是逐条标准的，
    #    所以拿它给单条标准定罪是错的（详见 SPEC §13.3i / §13.3k）。
    #    判读顺序**必须先看对照组**：对照不通过就说明检验不成立，
    #    此时不能据此判任何标准有罪。§13.3j 就是因为跳过这一步而误判了 9 条。
    MOUT = ROOT / "fixtures" / "answers"
    if (MOUT / "manip_out_run1").is_dir() and (MOUT / "manip_out_run2").is_dir():
        results.append(run([py, f"{S}/manip_analysis.py",
                            "--plan", str(MOUT / "manip_plan.json"),
                            "--inputs", str(MOUT / "manip_inputs"),
                            "--judge", str(MOUT / "manip_out_run1"), str(MOUT / "manip_out_run2"),
                            "--variants", str(MOUT / "manip_variants_1.jsonl"),
                            str(MOUT / "manip_variants_2.jsonl"),
                            "--out", str(MOUT / "manip_result.json")]))
    else:
        print("  ⏭ 尚无操纵检验评判产出，跳过")

    print("\n=== 10) 锚点事实可判性（R2）与正式版 v1.2 ===")
    # 这是**唯一不依赖任何裁判**的缺陷检查：锚点/正文里若要求了题面没给出的事实，
    # 裁判根本无法核实 → 该档不可判。不需要跑模型就能判定，成本近零。
    results.append(run([py, f"{S}/check_anchor_grounding.py",
                        "--items", str(items),
                        "--out", str(ROOT / "items" / "anchor_grounding.json")]))
    # v1.2 = v1.0 + 可核验的修复。**正式版是 v1.2，不是 v1.1。**
    # v1.1 改了 96/101 条，其动机（区分度检验）已被证明测错了东西（SPEC §13.3i/§13.3k），
    # 绝大多数改动没有证据支撑，故不作为正式版。
    results.append(run([py, f"{S}/make_v1.2.py", "--out", str(ROOT / "items" / "items_v1.2.jsonl")]))
    v12 = ROOT / "items" / "items_v1.2.jsonl"
    if v12.is_file():
        results.append(run([py, f"{S}/check_anchor_grounding.py", "--items", str(v12),
                            "--out", str(ROOT / "items" / "anchor_grounding_v12.json")]))

    n_fail = len(bad) + sum(1 for r in results if not r)
    print()
    if n_fail:
        print(f"❌ 共 {n_fail} 项失败")
        return 1
    print("✅ 全部检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

