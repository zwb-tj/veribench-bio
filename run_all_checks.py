#!/usr/bin/env python3
"""一条命令跑完**项目级**检查（T1/T2/台账/DATACARD）。

与 `rubric/run_all_checks.py` 的分工
------------------------------------
- 本文件：项目层的**许可、台账、文档一致性**（跨支柱）
- `rubric/run_all_checks.py`：第三支柱内部的 10 个环节

为什么要单独一个
----------------
本轮发现 `ledger/items.jsonl` **是 0 字节**，而 T1/T2 早已完成 —— 也就是说
README 第 1 条原则"没有台账条目的题目不得进集"**从来没有任何东西在强制执行**。
所以把它变成一条命令：

    python scripts/../run_all_checks.py

退出码非零 = 有问题。**"我记得要检查"必须变成"机器一定会检查"**，
这是本项目反复出现的同一个模式（见 rubric/README.md）。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE          # bio-eval/


#: 每条检查的超时（秒）。**所有检查都必须带超时。**
#:
#: ⚠️ 起因（2026-09）：`docker run ... bash -lc "<probe>"` 在 T1 镜像上
#: **间歇性挂死** —— 实测 15 次里挂 1 次（`rtg version` 从 2 秒变成
#: 20 秒无输出，容器状态 "Up N 分钟" 而 `docker top` 显示没有任何进程）。
#: 没有超时的话，整个套件会**永久卡住**，而 CI 只会显示"一直在跑"。
#: 这类缺陷最阴险的地方：**它看起来像"慢"，不像"坏"**。
DEFAULT_TIMEOUT = 600


def run(cmd: list[str], expect_zero: bool = True) -> bool:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=DEFAULT_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"  ❌ {' '.join(Path(c).name for c in cmd)}  → "
              f"**超时 {DEFAULT_TIMEOUT}s**（挂死，不是慢）")
        return False
    lines = [l for l in ((p.stdout or "") + (p.stderr or "")).strip().splitlines() if l.strip()]
    last = lines[-1] if lines else "(无输出)"
    ok = (p.returncode == 0) if expect_zero else True
    print(f"  {'✅' if ok else '❌'} {' '.join(Path(c).name for c in cmd)}  → {last[:95]}")
    if not ok:
        for l in lines[-8:]:
            print(f"      {l}")
    return ok


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    import argparse
    ap = argparse.ArgumentParser(description="项目级检查")
    ap.add_argument("--clean-room", action="store_true",
                    help="额外跑清室检验：只复制**会被发布的那部分**到临时目录，在那里重跑。"
                         "慢（要复制约 78 MB 并跑两套检查），但能抓到**隐藏依赖未发布文件**"
                         "—— 那是最容易让第三方 clone 下来就卡住的一类问题。")
    args = ap.parse_args()

    py = sys.executable
    S = str(ROOT / "scripts")
    results: list[bool] = []

    print("=== 1) 重新生成主台账（T1/T2/各来源 + rubric 24 条）===")
    results.append(run([py, f"{S}/build_master_ledger.py"]))

    print("\n=== 2) 许可与安全门禁 ===")
    results.append(run([py, f"{S}/audit_licenses.py", "--self-test"]))
    led = ROOT / "ledger" / "items.jsonl"
    if led.is_file() and led.stat().st_size > 0:
        results.append(run([py, f"{S}/audit_licenses.py", str(led)]))
    else:
        print("  ❌ 主台账为空 —— 原则 1 未被执行")
        results.append(False)

    print("\n=== 3) DATACARD / SAFETY / README 的断言与工作区一致性 ===")
    # 卡片与首页里可机械验证的断言逐条对回证据；查不了的明说"无法离线验证"，不假装通过。
    # README 单独查是因为它是**任何人读到的第一个文件**，也最容易烂掉 ——
    # 本轮就在它里面发现 5 个已不存在的路径引用和一句"尚未收录任何题目"（早已不成立）。
    results.append(run([py, f"{S}/verify_datacard.py"]))
    results.append(run([py, f"{S}/verify_readme.py", "--self-test"]))   # 先证明检查器会失败
    results.append(run([py, f"{S}/verify_readme.py"]))
    # 全部文档的路径引用（从 README 推广而来：README 一处就查出 5 个死引用，
    # 说明"文档写了已不存在的文件"是系统性问题是而非个例）
    results.append(run([py, f"{S}/verify_doc_links.py"]))
    # **重新测量** T2 的关键数字（题量/金丝雀/泄漏覆盖面/公开·轮换切分）并与文档比对。
    # 加它的直接原因：文档写着 40,110，实测是 40,170 —— 一个从早期运行留下的旧数字，
    # 恰好落在这个项目最核心的卖点（"0 泄漏"）上。
    results.append(run([py, f"{S}/verify_t2_claims.py"]))
    # 同样地，**重新测量** T1 的关键数字（score / SNP·INDEL F1 / manifest 哈希 / 运行时长）。
    # 第一次跑就抓到一条与事实相反的断言：README 写着"镜像 digest 尚未 pin"，
    # 而 result.json 里一直记着 image_digest。三档结论分开报：
    # 可复算 / 已记录（需原镜像）/ 无法验证（需 Docker 或联网）。
    results.append(run([py, f"{S}/verify_t1_claims.py"]))
    # 第三个支柱同样办（T1/T2 各一个，rubric 也必须有）：
    # 三个支柱的文档数字都被"重新测量 + 比对"覆盖，不留一个special case。
    results.append(run([py, f"{S}/verify_rubric_claims.py"]))
    # rubric 的产物**可复现性**：`verify_rubric_claims.py` 只比对"文档 vs 产物"，
    # **它无法发现产物本身是不可复现的**。而 DATACARD 的 κ 数字就是从这些产物读的。
    # 若两次重跑得到不同的数，文档里的数字就只是"某次运行的快照"。
    # 实测：11 个产物重跑两次逐字节相同（用 --quick 跑核心 4 个，避免套件跑四遍）。
    # 已做负向测试：注入一个 random 字段 → 立刻报"不可复现"。
    results.append(run([py, f"{S}/verify_rubric_determinism.py", "--quick"]))
    # 第四个：T1 的**覆盖区间**。上面三个都是"数字对不对"，这个是"事实对不对"——
    # 区间被写错 5 倍（10–20 Mb vs 实际 10–12 Mb）却全程没人抓到，
    # 因为 verify_t1_claims.py 只扫 2 份文档、而且判据是小数正则，压根匹配不到区间字符串。
    # 现在以 manifest + 真值 BED 两个独立记录为唯一事实，强制核对 9 个文件。
    results.append(run([py, f"{S}/verify_t1_region.py"]))
    # 第五个：T1 的**两个脚本之间**的约定不变量。
    # run.sh 的默认 BAM 少了 `.30x`、默认区间写成 10–20 Mb —— 两个都错，
    # 而且因为**每个 driver 都 export 覆盖了默认值**，所以从来没被执行过、也就没被发现。
    # 这条检查不要 Docker、不要数据：只验"生产方产出的文件名/区间 == 消费方默认读的"。
    results.append(run([py, f"{S}/check_t1_scripts_agree.py"]))
    # 第六个：NOTICE 的 [A]/[B] 分块是否名副其实。
    # 这个分块本身就是"我验到什么程度"的诚实表达；若 [A] 里的组件其实没读过原文，
    # 它会退化成一句自我表扬。检查：[A] 每条必须有上游 LICENSE 出处、
    # 不许两头都列、Dockerfile 装过的组件必须全部声明。
    results.append(run([py, f"{S}/verify_notice.py"]))
    # 第七个：**每个任务**的镜像 pin 是否还由当前源码算得出来。
    # T1 的 digest 曾 pin 成一个"剥离 JRE 之前的旧镜像"；补 T2 时发现 T2 连 pin 都没有。
    # 这正是本项目最该防的"特殊照顾"——一个任务修好了、另一个漏着。
    # 所以这条对 T1/T2 一起验（--check-all），不允许只做一半。
    results.append(run([py, f"{S}/record_image_digest.py", "--check-all"]))
    # 第八个：全仓 JSON / JSONL 能不能解析。
    # 起因：我在 not_published.json 的说明文字里用了 ASCII 双引号（中文串内），
    # 把文件写坏了 —— 那是**同一个错误在本项目的第 9 次**。当时是"下一个脚本刚好要读它"才炸，
    # 纯属运气。加上这条后立刻又抓到 **T2 的两个 schema 文件**（第 10~12 次），
    # 而那两个 schema 因为**没有任何代码引用它们**，坏了很久也没人知道。
    results.append(run([py, f"{S}/verify_json_files.py"]))
    # 第九个：T2「轮换池 937 条永不公开」到底成不成立。
    # 起因：实测发现全量 data/truth.jsonl **含轮换池全部 937 条的答案**，
    # 而它当时不在 not_published.json 里 —— clean_room_check 一直把它当"会发布的文件"
    # 复制进清室目录（已确认发生过）。**这句对外声明此前从未被任何检查验证过。**
    results.append(run([py, f"{S}/verify_t2_rotation_isolation.py"]))
    # 第十一个：**上传集预检** —— "你打算上传什么"这一步此前完全没人守。
    # T2 的发布集有个致命的不对称：`data/public/`（3,789 条，要传）
    # vs `data/`（4,726 条，**含轮换池 937 条答案**），两个路径只差一个 `/public`。
    # 一条手滑的 `hf upload` 就把"永不公开"变成假话，且不可撤销。
    # 现有检查验的是"仓库状态对不对"，**不管人敲的命令**——这里补上那一环。
    results.append(run([py, f"{S}/verify_upload_preflight.py",
                        "--dir", "tasks/T2/data/public"]))
    # 第十二个：`.gitignore` 与唯一真源是否一致。
    # 推到 GitHub 与传到 HF 有一个共同点：**历史不可撤销**。
    # `git add .` 会抓走 `tasks/T2/data/truth.jsonl`（4,726 条答案，
    # **含全部 937 条轮换池答案**）—— 一旦 push，「轮换池永不公开」永久变假。
    # 所以 .gitignore 是**安全属性**：由 not_published.json 生成，不许手写第二份。
    # 第一版生成器给**文件**条目也拼了尾斜杠（`…/truth.jsonl/`），
    # 而 gitignore 里带尾斜杠只匹配目录 → **最危险的文件没被忽略**。
    # 是靠 --self-test 里改用**真 git**（`git check-ignore`）才查出来的。
    results.append(run([py, f"{S}/generate_gitignore.py", "--check"]))
    results.append(run([py, f"{S}/generate_gitignore.py", "--self-test"]))
    # 第十三个：发布前的密钥 / 本机路径扫描。凭据一旦推上去无法收回。
    results.append(run([py, f"{S}/scan_secrets.py"]))
    # 第十六个：**"什么算会被发布"只能有一份实现。**
    # 起因：审计发现同一段遍历+过滤逻辑被抄了三份
    # （print_project_stats / scan_secrets / verify_no_answer_leak），
    # 而**每一份的 docstring 都写着「不另写一份过滤逻辑」**。
    # 三份实测报出 698 / 697 / 698 —— 已经漂移了。
    # 这段逻辑决定"哪些内容会被查泄露、哪些会被查凭据"，是**安全边界**：
    # 它自己第一版漏排除 `.git/`，把 615 个 git 对象算成发布内容（1308 vs 真实 693）。
    results.append(run([py, f"{S}/publishable_files.py", "--self-test"]))
    # 三个消费方现在必须报同一数量（`scan_secrets` 少 1 个是因为它排掉自己 —— 已说明）
    results.append(run([py, f"{S}/check_publishable_agree.py"]))
    # 第十七个：**写文本文件必须指定 `newline=""`**。
    # 起因：实测发现 T2/T3 的 `items.jsonl` 都是 CRLF（本机 Windows 生成），
    # 而它们是镜像 pin 的**构建输入** —— CRLF 版算 `400fe720…`、LF 版算 `be5da56d…`，
    # 于是**同一条 pin 在 Windows 报 ✅、在 Linux 报 ❌**。
    # 更麻烦的是 CI 抓不到：生成物在 clone 里不存在，`--check-all` 会 SKIP。
    results.append(run([py, f"{S}/check_newline_hygiene.py", "--self-test"]))
    results.append(run([py, f"{S}/check_newline_hygiene.py"]))
    # 第十八个：**工作区是否被写成 CRLF**（而 HEAD 是 LF）。
    # 起因：`.gitattributes` 要求 LF、HEAD 里也是 LF，但**工作区**被某段代码
    # 写成了 CRLF 而 **`git status` 看不见** —— `core.autocrlf=true` 会在比较前
    # 归一化。实测全仓有 45 个已跟踪文件处于这种状态。
    # 而 `record_image_digest.py` 是在**工作区字节**上算 source_sha256 的：
    # 污染的工作区算出的 pin 与干净检出（CI/Linux）不一致 →
    # **同一条 pin 一台机器报 ✅、另一台报 ❌**。
    results.append(run([py, f"{S}/check_worktree_lf.py", "--self-test"]))
    results.append(run([py, f"{S}/check_worktree_lf.py"]))
    # 第十九个：**Dockerfile 的门禁阶段是否真的会被构建**。
    # 起因（本轮最严重的一类）：实测 Docker **不构建未被引用的中间阶段** ——
    # `FROM ... AS gate` 后面写再多 RUN，只要最终阶段没 `COPY --from=gate`，
    # Docker 就整个跳过它，所有检查静默不执行，**而构建照样成功**。
    # 证据：往 truth.jsonl 注入错误值后构建仍 exit 0；加上引用后立刻 exit 1。
    # T3 与 T4 都中招（文档里却写着"构建期执行门禁"），T2 因为恰好引用了而幸免。
    results.append(run([py, f"{S}/check_docker_gates.py", "--self-test"]))
    results.append(run([py, f"{S}/check_docker_gates.py"]))
    # 第十四个：**内容级**答案泄露审计。
    # 上面那些验的是"仓库状态"与"上传集"，但**"答案会不会藏在代码/文档里"**
    # 此前从未被验过 —— 而这是最容易被忽略的一条路：`.py` 里的自测夹具、
    # `.md` 里的示例、甚至注释里的 id，都可能把轮换池内容带出去。
    # 判据刻意做成"**同一条记录内** id 与真实标签同时出现"，而不是"字符串出现" ——
    # 后者会把合成夹具的撞号误报成泄露（我自己连误报两版才做对）。
    results.append(run([py, f"{S}/verify_no_answer_leak.py"]))
    results.append(run([py, f"{S}/verify_no_answer_leak.py", "--self-test"]))
    # 第十个：T2 那条"生命线"检查器**自己**有没有漏检。
    # 起因：变异测试发现它的 `RefSeq/转录本 accession` pattern 匹配不到任何
    # 标准写法（`NM_000277.3` 中间有下划线），实测 7/11 种形态永远漏检 ——
    # 而真值 HGVS 里真实存在的形态（`NM_001754.5` 等）全在漏检那类里。
    # 紧接着自检又抓出第二条坏 pattern（三段式 `12-102852862-G-T` 完全漏检）。
    # **一个不能失败的检查比没有更坏** —— 所以每类 pattern 都钉一个已知阳性。
    results.append(run([py, str(ROOT / "tasks" / "T2" / "data" / "check_no_leakage.py"),
                        "--self-test"]))
    # 第十五个：**项目规模数字必须能复算**。
    # 起因：README/DATACARD/简历里反复出现"发布文件数 / 检查步数 / 实跑次数"这类数字，
    # 而同一个数字写在多处必然漂移（本项目已抓到过 40,110 vs 40,170、区间夸 5 倍等）。
    # 这个脚本把它们集中实测一次，供所有文档引用。
    # 它自己的自检还钉住了一条真实 bug：第一版漏排除 `.git/`，
    # 把 615 个 git 对象算进"发布内容"（1308 vs 真实 692）——
    # **而且那个错数字看起来完全正常**。
    results.append(run([py, f"{S}/print_project_stats.py", "--self-test"]))

    print("\n=== 3b) LICENSE 正文是否与官方源一致 ===")
    # 手抄错的许可证正文比没有更糟：它看起来权威但条款可能被改动。
    # 这个脚本联网逐行比对；连不上时**明确退回弱检查并说明未验证**。
    results.append(run([py, f"{S}/verify_license_text.py"]))

    print("\n=== 4) 语法编译（顶层 scripts/）===")
    bad = []
    for f in sorted((ROOT / "scripts").glob("*.py")):
        try:
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
        except SyntaxError as exc:
            print(f"  ❌ {f.name}: 第 {exc.lineno} 行 {exc.msg}")
            bad.append(f.name)
    if not bad:
        print(f"  ✅ {(len(list((ROOT / 'scripts').glob('*.py'))))} 个文件全部可编译")
    results.append(not bad)

    print("\n=== 5) schema 校验（此前不在自动检查里）===")
    # 本轮加这个环节时，它**立刻发现 ledger.schema.json 本身是非法 JSON**
    # （JSON 串里混了 ASCII 引号），而审计器照样通过 —— 因为审计器根本不读 schema。
    # 这就是"schema 与数据可以各自漂移而无人发现"的实例。
    results.append(run([py, f"{S}/validate_schemas.py"]))

    print("\n=== 6) 环境依赖清单（从 import 扫出来，不凭记忆）===")
    results.append(run([py, f"{S}/check_env_deps.py"]))

    print("\n=== 6b) 全仓脚本冒烟测试（每个 .py 都点一遍）===")    # 加这一步的直接原因：`rubric/scripts/make_annotation_sheets.py` 曾经
    # **根本不接受作答输入**，生成的标注表没有可评的对象 —— 而它能坏那么久，
    # 正是因为**没有任何东西在跑它**。本环节对每个脚本跑 `--help`：
    #   · 起不来 → 硬伤（本轮就抓到 manip_analysis.py --help 直接崩）
    #   · 平台专属（resource/pwd 等 Unix-only）→ 标⚠️并明说"本机无法验证"，不算通过
    #   · 能起来但无 --self-test → 列出，提示"行为未被自动验证"
    results.append(run([py, f"{S}/smoke_test_scripts.py"]))
    # 静态扫 argparse 的裸 `%`（会让 --help 崩）。不执行代码，所以比冒烟测试更快更稳。
    results.append(run([py, f"{S}/check_argparse_pct.py"]))

    print("\n=== 6c) 榜单提交校验器（含负向测试）===")
    # v1 四件套里"真实榜单"那一项。校验器本身必须先被证明会拒绝坏提交 ——
    # 一个从不拒绝的校验器等于没有校验器。
    lb = ROOT / "leaderboard" / "selftest_verify_submission.py"
    if lb.is_file():
        results.append(run([py, str(lb)]))
    else:
        print("  ⏭ 尚无 leaderboard/selftest_verify_submission.py")

    print("\n=== 6d) 镜像里被断言的属性（需 Docker + 已构建镜像）===")
    # **"构建成功" ≠ "构建出来的东西满足文档断言"**。这一步把文档断言过的
    # 镜像性质逐条到镜像里查，含行为验证（真的跑一次 rtg version）。
    # 没有 Docker 或没有镜像时输出 SKIP，不算通过也不算失败。
    insp = ROOT / "tasks" / "T1" / "inspect_image.py"
    if insp.is_file():
        results.append(run([py, str(insp), "--image", "veribench-bio/t1:dev"]))
        # T2 的断言不同（无分析工具链，但"镜像里不得含真值"是硬要求）
        results.append(run([py, str(insp), "--image", "veribench-bio/t2:dev"]))
    else:
        print("  ⏭ 尚无 tasks/T1/inspect_image.py")

    print("\n=== 6e) Dockerfile 的 apt 调用是否都被重试包裹 ===")
    # 起因：上游 deb.debian.org 持续 502 会让 `--no-cache` 构建失败，
    # 我给 T1 加了重试，**T2 的两处漏了**。这个检查强制"不许只修一处"。
    results.append(run([py, f"{S}/check_dockerfile_apt.py"]))

    print("\n=== 6f) T2 基线实跑（复现，不是读旧产物）===")
    # DATACARD 记着 oracle 1.0000 / all_vus 0.4245 / all_pathogenic 0.3478。
    # 这一步**真的启容器跑三个基线**，并把期望值**从 DATACARD 读** ——
    # 硬编码期望值等于"同一个事实写两遍"，文档改了也发现不了。
    # T2 判分不需要生信工具，实跑很快（约 1 秒/基线）。
    vo = ROOT / "tasks" / "T2" / "verify_oracle.py"
    if vo.is_file():
        results.append(run([py, str(vo)]))
    else:
        print("  ⏭ 尚无 tasks/T2/verify_oracle.py")

    print("\n=== 6g) T1 判分器自检（合成数据，复现 1.0 / 0.25）===")
    # 文档一直写着"判分器自检 1.0 / 0.25 通过"，但**没有任何自动检查在跑它** ——
    # 而且文档给的命令 `grade.py --self-test` **根本不存在**（T1 的 grade.py 没有该 flag）。
    # 真正的自检是 `tasks/T1/selftest/run_selftest.sh`（容器内 + 合成数据，不需 GIAB）。
    # 它此前只能靠人记得手跑 —— 那就等于"文档里的结论没有被守着"。
    st = ROOT / "tasks" / "T1" / "selftest" / "run_selftest.sh"
    if st.is_file():
        if shutil.which("docker") is None:
            print("  ⏭ 无 docker，跳过（**不算通过**）")
        elif subprocess.run(["docker", "image", "inspect", "veribench-bio/t1:dev"],
                            capture_output=True, timeout=60).returncode != 0:
            print("  ⏭ 镜像 veribench-bio/t1:dev 不存在，跳过（先构建）")
        else:
            results.append(run(["docker", "run", "--rm",
                                "-v", f"{st.parent}:/selftest:ro",
                                "veribench-bio/t1:dev", "-lc",
                                "bash /selftest/run_selftest.sh"]))
    else:
        print("  ⏭ 尚无 tasks/T1/selftest/run_selftest.sh")

    # T2 的判分器有真正的 `--self-test`（与 T1 不同，它不需要 Docker/生信工具）。
    # 文档写着"11/11 通过"，但此前同样**没有任何东西在跑它**。
    t2g = ROOT / "tasks" / "T2" / "grade.py"
    if t2g.is_file():
        results.append(run([py, str(t2g), "--self-test"]))

    print("\n=== 6h) T3（蛋白结构）解析器与判分器 ===")
    # T3 的确定性声明建立在"按 loop_ 语义解析 mmCIF"上。实测过：
    # 按 `#` 切块会让 4HHB/6LU7/2LZM 报 **0 个原子**（真实 4,384/2,387/1,309）——
    # 而 0 看起来像"这个结构没有原子"，不会自己喊出来。
    # 所以解析器的自检里有一条**交叉核对**用例（喂少一行的列表 → 必须抛）。
    t3parse = ROOT / "tasks" / "T3" / "data" / "mmcif_parse.py"
    if t3parse.is_file():
        results.append(run([py, str(t3parse), "--self-test"]))
    else:
        print("  ⏭ 尚无 tasks/T3/data/mmcif_parse.py")

    t3g = ROOT / "tasks" / "T3" / "grade.py"
    if t3g.is_file():
        # 判分器的自检含浮点陷阱的负向用例（epsilon 设在噪声量级上会误判）
        results.append(run([py, str(t3g), "--self-test"]))
    else:
        print("  ⏭ 尚无 tasks/T3/grade.py")

    # T3 端到端（需 docker + 已构建镜像 + 生成物）。
    # ⚠️ 生成物（items/truth）不发布 → 新 clone 里没有 → 必须 SKIP 而非失败。
    t3data = ROOT / "tasks" / "T3" / "data"
    if not (t3data / "truth.jsonl").is_file() or not (t3data / "items.jsonl").is_file():
        print("  ⏭ T3 数据未生成（跑 fetch_mmcif.py）—— 跳过端到端，**不算通过**")
    elif shutil.which("docker") is None:
        print("  ⏭ 无 docker，跳过 T3 端到端（**不算通过**）")
    elif subprocess.run(["docker", "image", "inspect", "veribench-bio/t3:dev"],
                        capture_output=True, timeout=60).returncode != 0:
        print("  ⏭ 镜像 veribench-bio/t3:dev 不存在，跳过（先构建）")
    else:
        # oracle 作答由真值直出 → 必须得 1.0。这验的是"判分器与数据自洽"。
        oracle = ROOT / "tasks" / "T3" / "_runs" / "answers_oracle.jsonl"
        if not oracle.is_file():
            print("  ⏭ 缺 _runs/answers_oracle.jsonl（先跑 oracle 生成）")
        else:
            import tempfile as _tf
            with _tf.TemporaryDirectory(prefix="t3-e2e-") as td:
                shutil.copyfile(oracle, Path(td) / "answers.jsonl")
                p = subprocess.run(
                    ["docker", "run", "--rm",
                     "-v", f"{t3data / 'truth.jsonl'}:/data/truth.jsonl:ro",
                     "-v", f"{td}:/out", "veribench-bio/t3:dev"],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=DEFAULT_TIMEOUT)
                rj = Path(td) / "result.json"
                got = None
                if rj.is_file():
                    try:
                        got = json.loads(rj.read_text(encoding="utf-8"))["score"]
                    except (ValueError, KeyError):
                        got = None
                ok = p.returncode == 0 and got == 1.0
                print(f"  {'✅' if ok else '❌'} T3 容器内端到端（oracle）"
                      f" → score={got} exit={p.returncode}")
                results.append(ok)

    print("\n=== 6i) T4（GO 本体）解析器与判分器 ===")
    # T4 的正确性关键在"**排除 obsolete**"。实测：不过滤时"无 is_a"的项
    # 有 10,251 个（其中 10,248 是 obsolete），而真实根只有 3 个 ——
    # 假根会让 depth_to_root 全部算错。解析器的自检含这条负向用例。
    t4parse = ROOT / "tasks" / "T4" / "data" / "obo_parse.py"
    if t4parse.is_file():
        results.append(run([py, str(t4parse), "--self-test"]))
    else:
        print("  ⏭ 尚无 tasks/T4/data/obo_parse.py")

    t4g = ROOT / "tasks" / "T4" / "grade.py"
    if t4g.is_file():
        results.append(run([py, str(t4g), "--self-test"]))
    else:
        print("  ⏭ 尚无 tasks/T4/grade.py")

    # T4 端到端（需 docker + 镜像 + 生成物）。生成物不发布 → 新 clone 里 SKIP。
    t4data = ROOT / "tasks" / "T4" / "data"
    if not (t4data / "truth.jsonl").is_file() or not (t4data / "items.jsonl").is_file():
        print("  ⏭ T4 数据未生成（跑 fetch_go.py）—— 跳过端到端，**不算通过**")
    elif shutil.which("docker") is None:
        print("  ⏭ 无 docker，跳过 T4 端到端（**不算通过**）")
    elif subprocess.run(["docker", "image", "inspect", "veribench-bio/t4:dev"],
                        capture_output=True, timeout=60).returncode != 0:
        print("  ⏭ 镜像 veribench-bio/t4:dev 不存在，跳过（先构建）")
    else:
        oracle4 = ROOT / "tasks" / "T4" / "_runs" / "answers_oracle.jsonl"
        if not oracle4.is_file():
            print("  ⏭ 缺 _runs/answers_oracle.jsonl（先跑 oracle 生成）")
        else:
            import tempfile as _tf4
            with _tf4.TemporaryDirectory(prefix="t4-e2e-") as td4:
                shutil.copyfile(oracle4, Path(td4) / "answers.jsonl")
                p4 = subprocess.run(
                    ["docker", "run", "--rm",
                     "-v", f"{t4data / 'truth.jsonl'}:/data/truth.jsonl:ro",
                     "-v", f"{td4}:/out", "veribench-bio/t4:dev"],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=DEFAULT_TIMEOUT)
                rj4 = Path(td4) / "result.json"
                got4 = None
                if rj4.is_file():
                    try:
                        got4 = json.loads(rj4.read_text(encoding="utf-8"))["score"]
                    except (ValueError, KeyError):
                        got4 = None
                ok4 = p4.returncode == 0 and got4 == 1.0
                print(f"  {'✅' if ok4 else '❌'} T4 容器内端到端（oracle）"
                      f" → score={got4} exit={p4.returncode}")
                results.append(ok4)


    if args.clean_room:
        print("\n=== 7) 清室检验（只给会被发布的文件，流水线还跑不跑得起来）===")
        # 这个环节在本轮第一次跑时抓到 3 个真问题：两个脚本假设未发布的输入存在、
        # 一个直接 ZeroDivisionError 崩掉。所以它不是形式主义。
        results.append(run([py, f"{S}/clean_room_check.py"]))
    else:
        print("\n=== 7) 清室检验 ===  ⏭ 未启用（加 --clean-room 开启；较慢）")

    n_fail = sum(1 for r in results if not r)
    print()
    if n_fail:
        print(f"❌ 共 {n_fail} 项失败")
        return 1
    print("✅ 项目级检查全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
