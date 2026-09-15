#!/usr/bin/env python3
"""核对 DATACARD / SAFETY 里**可机械验证**的断言。

为什么需要这个
--------------
这个项目的卖点是"可证明没编造"。那就**不能允许 DATACARD 自己含有未经验证的断言** ——
一张要求别人可信、自己却写满"大概是吧"的卡片，比没有卡片更糟。

本脚本把卡片里能查的句子逐个对回证据：
  · 台账条目数与许可白名单合规（调审计器）
  · `contains_restricted_data` 是否真的全为 false
  · 审计器是否真的实现了 R8 / R9（卡片里点名说"已实现并有自检"）
  · rubric 正式版是否真的 24 题 / 101 条
  · 关键产物文件是否真的存在（`LICENSE` 之类卡片里说"待完成"的，不存在才对）

**查不出来的一律列为 UNVERIFIED**，不假装通过。
比如 HF 上的字节比对结果无法离线复核，就明说"需联网"。

用法：
    python3 verify_datacard.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent          # bio-eval/
REPO = ROOT.parent

results: list[tuple[str, str, str]] = []   # (断言, 结论, 证据)


def add(claim: str, ok: bool | None, evidence: str) -> None:
    results.append((claim, "✅ 通过" if ok is True else ("❌ 不符" if ok is False else "⚠️ 无法离线验证"),
                    evidence))


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    dc = ROOT / "docs" / "DATACARD.md"
    sf = ROOT / "docs" / "SAFETY.md"
    add("DATACARD.md 存在", dc.is_file(), str(dc))
    add("SAFETY.md 存在", sf.is_file(), str(sf))

    aud = ROOT / "scripts" / "audit_licenses.py"
    if aud.is_file():
        src = aud.read_text(encoding="utf-8")
        add("审计器实现了 R8（rejected 却 public → 致命）", "R8 " in src, "audit_licenses.py 含 R8")
        add("审计器实现了 R9（gated 混入 public → 致命）", "R9 " in src, "audit_licenses.py 含 R9")
        add("审计器实现了 R12（human_data_basis 必需）", "R12 缺少或非法" in src, "含 R12 分支")
        p = subprocess.run([sys.executable, str(aud), "--self-test"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        m = re.search(r"(\d+)\s*个用例全部符合预期", p.stdout or "")
        n = int(m.group(1)) if m else -1
        add("审计器 --self-test 16/16 通过", n == 16, f"实测 {n} 个用例")
    else:
        add("审计器存在", False, "找不到 audit_licenses.py")

    # 台账：卡片说 contains_restricted_data 全为 false，且**每道题都可溯源**
    led = ROOT / "ledger" / "items.jsonl"
    if led.is_file() and led.stat().st_size > 0:
        rows = [json.loads(l) for l in led.read_text(encoding="utf-8").splitlines() if l.strip()]
        bad = [r.get("item_id") for r in rows if r.get("contains_restricted_data") is True]
        add("主台账 contains_restricted_data 全为 false", not bad,
            f"{len(rows)} 条，为 true 的：{bad or '无'}")
        tasks = {r.get("task") for r in rows}
        add("主台账覆盖 T1 / T2 / R 三个支柱", {"T1", "T2", "R"} <= tasks,
            f"实际 task 取值：{sorted(tasks)}")
        add("主台账每条都带 human_data_basis", all(r.get("human_data_basis") for r in rows),
            f"{sum(1 for r in rows if r.get('human_data_basis'))}/{len(rows)}")
        # 原则 1：每一道题都可溯源 —— T2 有 4,726 道题，靠 derivation_note 说明覆盖范围
        noteless = [r["item_id"] for r in rows
                    if r.get("task") in ("T1", "T2") and not (r.get("derivation_note") or "").strip()]
        add("T1/T2 台账条目标明了「覆盖哪些题」", not noteless, f"缺说明的：{noteless or '无'}")
    else:
        add("主台账非空（原则 1：没有台账条目的题目不得进集）", False,
            f"{led} 为空 —— T1/T2 已完成却没有台账记录。跑 build_master_ledger.py 补上")

    rub = ROOT / "rubric" / "ledger" / "rubric_items.jsonl"
    if rub.is_file():
        rows = [json.loads(l) for l in rub.read_text(encoding="utf-8").splitlines() if l.strip()]
        bad = [r.get("item_id") for r in rows if r.get("contains_restricted_data") is True]
        add("rubric 台账 contains_restricted_data 全为 false", not bad,
            f"{len(rows)} 条，为 true 的：{bad or '无'}")
        add("rubric 台账全部带 human_data_basis", all(r.get("human_data_basis") for r in rows),
            f"{sum(1 for r in rows if r.get('human_data_basis'))}/{len(rows)}")

    # rubric 正式版：卡片说 24 题 / 101 条
    v12 = ROOT / "rubric" / "items" / "items_v1.2.jsonl"
    if v12.is_file():
        items = [json.loads(l) for l in v12.read_text(encoding="utf-8").splitlines() if l.strip()]
        nc = sum(len(i["criteria"]) for i in items)
        add("rubric 正式版为 24 题", len(items) == 24, f"实测 {len(items)} 题")
        add("rubric 正式版为 101 条标准", nc == 101, f"实测 {nc} 条")
        add("正式版全部标 rubric_version=1.2",
            all(i.get("rubric_version") == "1.2" for i in items),
            f"{sum(1 for i in items if i.get('rubric_version') == '1.2')}/{len(items)}")
        # 卡片说题面不含序列/菌株/剂量参数（SAFETY §3）
        blob = " ".join(i["question"] for i in items)
        risky = [k for k in ("菌株", "剂量参数", "select agent", "基因驱动", "生殖系") if k in blob]
        add("SAFETY：题面不含生物安全高危要素", not risky, f"命中：{risky or '无'}")
    else:
        add("rubric 正式版 items_v1.2.jsonl 存在", False, str(v12))

    # LICENSE 与 NOTICE 应当在（本轮补上），且 LICENSE 正文要与官方源一致
    lic = ROOT / "LICENSE"
    notice = ROOT / "NOTICE"
    add("LICENSE 已落地", lic.is_file(),
        f"{lic} {'存在' if lic.is_file() else '不存在 —— DATACARD §7 的待办项'}")
    add("NOTICE 已落地（第三方组件逐项）", notice.is_file(),
        f"{notice} {'存在' if notice.is_file() else '不存在'}")
    if notice.is_file():
        nt = notice.read_text(encoding="utf-8")
        # NOTICE 必须区分"已核验"与"未逐项核验"——一条不做区分的清单会高估我们查过什么
        add("NOTICE 明确区分『已核验』与『未逐项核验』",
            "VERIFIED FROM UPSTREAM LICENSE TEXT" in nt and "NOT INDIVIDUALLY VERIFIED" in nt,
            "含两个分块标题")
        add("NOTICE 记录了刻意排除的组件及原因",
            "DELIBERATELY NOT INCLUDED" in nt and "dbNSFP" in nt,
            "含排除块，点名 dbNSFP")
        add("NOTICE 点名 GATK3 的非商用陷阱",
            "GATK3" in nt, "含 GATK3 说明")
    add("LICENSE 正文与 apache.org 官方源逐行一致", None,
        "需联网；跑 python scripts/verify_license_text.py 复核（离线只能查结构）")

    # 离线无法验证的，明确标出
    add("HF 数据集逐字节比对（T1 100.4MB / T2 4,726 条）", None,
        "需联网读取 HF 才能复核，本次为离线检查")
    add("T1 实跑 55 秒 / 得分 0.84655", None, "需 Docker + 数据才能复跑")
    add("清室检验（只给会发布的文件）", None,
        "本机清室 ≠ 另一台机器；跑 python scripts/clean_room_check.py 复核（较慢）")
    add("第三方 / 真正的 clean-CI 复现", None,
        "从未做过，卡片已列为待完成 —— 本机清室检验不能替代它")

    w0 = max(len(a) for a, _, _ in results)
    print(f"{'断言'.ljust(w0)}  结论")
    print("-" * (w0 + 40))
    for claim, verdict, ev in results:
        print(f"{claim.ljust(w0)}  {verdict}")
        print(f"{' ' * w0}  └ {ev}")

    n_bad = sum(1 for _, v, _ in results if v.startswith("❌"))
    n_un = sum(1 for _, v, _ in results if v.startswith("⚠️"))
    print()
    print(f"共 {len(results)} 条：通过 {len(results) - n_bad - n_un} · 不符 {n_bad} · 无法离线验证 {n_un}")
    if n_bad:
        print("❌ DATACARD/SAFETY 里有与实际不符的断言 —— 修卡片，不改事实。")
        return 1
    print("✅ 卡片中所有可机械验证的断言均与工作区一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
