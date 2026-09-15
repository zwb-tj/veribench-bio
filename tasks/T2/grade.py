#!/usr/bin/env python3
"""VeriBench-Bio · T2 判分器（变异解读）

被测系统对每道题给出：分类 + 它认为成立的 ACMG 判据码。

评分由**四个互相独立的量**组成，**不把它们揉成一个不透明的分数**：

  1. `classification_credit`  —— 主分。在有序尺度上算部分分（P > LP > VUS > LB > B），
                                 并对"跨越 VUS 判到反方向"额外惩罚。
  2. `criteria_f1`            —— 判据集合的 micro-F1。**这是"真推理 vs 蒙对标签"的判别器**：
                                 蒙对标签的模型列不对判据。
  3. `canary_consistency`     —— **诊断量，不计入主分**。金丝雀配对题测的是"答案会不会
                                 随证据合理移动"，它不是准确率，不能混进同一个分母。
  4. `directional_error_rate` —— 把致病判成良性（或反之）的比例，单独报出。

主分 `score = 0.6 × classification_credit + 0.4 × criteria_f1`。
**权重是我们的约定，不是推导出来的** —— 所以两个分量都单独报出，任何人都可以自行重新加权。

用法：
    python3 grade.py --items items.jsonl --truth truth.jsonl --answers answers.jsonl --out result.json
    python3 grade.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 有序尺度：分类 → 秩
# ---------------------------------------------------------------------------
CLASS_RANK = {
    "Benign": 0,
    "Likely benign": 1,
    "Uncertain significance": 2,
    "Likely pathogenic": 3,
    "Pathogenic": 4,
}
RANK_CLASS = {v: k for k, v in CLASS_RANK.items()}

#: 容忍被测系统输出常见变体（大小写、缩写、同义词）
ALIASES = {
    "b": "Benign", "benign": "Benign",
    "lb": "Likely benign", "likely benign": "Likely benign", "likely_benign": "Likely benign",
    "vus": "Uncertain significance", "uncertain": "Uncertain significance",
    "uncertain significance": "Uncertain significance",
    "lp": "Likely pathogenic", "likely pathogenic": "Likely pathogenic",
    "likely_pathogenic": "Likely pathogenic",
    "p": "Pathogenic", "pathogenic": "Pathogenic",
}

#: 评分常数（改动必须同步文档，否则前后结果不可比）
DIST_STEP = 0.25       # 秩距离每增加 1，扣 0.25
OPPOSITE_FACTOR = 0.5  # 跨越 VUS 判到反方向，额外乘 0.5
W_CREDIT = 0.6         # 主分里 classification_credit 的权重（约定值）
W_CRITERIA = 0.4       # 主分里 criteria_f1 的权重（约定值）

VALID_CRITERIA = {
    "PVS1",
    *(f"PS{i}" for i in range(1, 5)),
    *(f"PM{i}" for i in range(1, 7)),
    *(f"PP{i}" for i in range(1, 6)),
    "BA1",
    *(f"BS{i}" for i in range(1, 5)),
    *(f"BP{i}" for i in range(1, 8)),
}

#: 基础码前缀（ClinGen 会写 `PP1_Moderate` / `PM2_Supporting` 这类**带强度修饰**的码）
_BASE_RE = __import__("re").compile(r"^(PVS1|PS[1-4]|PM[1-6]|PP[1-5]|BA1|BS[1-4]|BP[1-7])")


def canonicalize_criteria(raw_tokens) -> tuple[list[str], list[str]]:
    """把判据 token 规范化成**基础码**（去掉强度修饰）。

    为什么必须做：
      ClinGen EREPO 的判据字段会写 `PP1_Moderate`、`PM2_Supporting` 这类形式。
      如果只规范化预测、不规范化真值，真值里那些带修饰的码就**永远匹配不上**，
      结果是 oracle（照抄真值）的判据 F1 也只能拿到 0.67 —— 这就是本 bug 的指纹。

    返回 (规范码去重保序, 无法识别的原始 token)。**调用方必须把"无法识别"的数量报出来**
    （原则 7：成功必须可计数），否则解析失败会静默地压低分数。
    """
    ok: list[str] = []
    bad: list[str] = []
    for tok in raw_tokens or []:
        s = str(tok).strip()
        if not s:
            continue
        t = s.upper().split("(")[0].strip().replace(" ", "")
        m = _BASE_RE.match(t.split("_")[0])
        if m:
            code = m.group(1)
            if code not in ok:
                ok.append(code)
        else:
            bad.append(s)
    return ok, bad


def normalize_class(raw: object) -> str | None:
    s = str(raw or "").strip()
    if s in CLASS_RANK:
        return s
    key = s.lower().replace("-", " ").strip()
    if key in ALIASES:
        return ALIASES[key]
    # 再试一次去掉多余空格
    key2 = " ".join(key.split())
    return ALIASES.get(key2)


def side(rank: int) -> int:
    """-1 = 良性侧，0 = VUS，+1 = 致病侧。"""
    return -1 if rank < 2 else (0 if rank == 2 else 1)


def rank_credit(pred_rank: int, true_rank: int) -> float:
    dist = abs(pred_rank - true_rank)
    credit = max(0.0, 1.0 - DIST_STEP * dist)
    if side(pred_rank) != side(true_rank) and side(pred_rank) != 0 and side(true_rank) != 0:
        credit *= OPPOSITE_FACTOR
    return credit


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[错误] {path}:{i} 不是合法 JSON：{exc}") from exc
    return rows


# ---------------------------------------------------------------------------
# 评分
# ---------------------------------------------------------------------------


def grade(items: list[dict], truth: list[dict], answers: list[dict]) -> dict:
    truth_by_id = {t["item_id"]: t for t in truth}
    items_by_id = {it["item_id"]: it for it in items}

    problems: list[str] = []
    per_item: list[dict] = []

    # 只对**真实题**算准确率；金丝雀单独统计
    real_ids = [iid for iid, it in items_by_id.items() if not it.get("canary")]
    canary_ids = [iid for iid, it in items_by_id.items() if it.get("canary")]

    credit_sum = 0.0
    exact = 0
    directional_errors = 0
    scored = 0
    truth_unparsable = 0  # 真值里出现无法识别的判据码的题数（原则 7：必须计数）

    inter = pred_total = true_total = 0  # 判据 set-F1 的 micro 累加
    criteria_scored = 0

    ans_by_id: dict[str, dict] = {}
    for a in answers:
        iid = a.get("item_id")
        if iid in ans_by_id:
            problems.append(f"答案里 item_id={iid} 重复出现，取第一条")
            continue
        ans_by_id[iid] = a

    for iid in sorted(real_ids):
        t = truth_by_id.get(iid)
        if t is None:
            problems.append(f"{iid} 缺真值，跳过计分")
            continue
        a = ans_by_id.get(iid)
        if a is None:
            problems.append(f"{iid} 未作答，计 0 分")
            per_item.append({"item_id": iid, "status": "missing", "credit": 0.0})
            scored += 1
            continue

        true_cls = t.get("assertion_normalized")
        true_rank = CLASS_RANK.get(true_cls)
        if true_rank is None:
            problems.append(f"{iid} 真值分类 {true_cls!r} 不在 5 类内，跳过")
            continue

        pred_cls = normalize_class(a.get("classification"))
        if pred_cls is None:
            problems.append(f"{iid} 作答分类 {a.get('classification')!r} 无法归一化，计 0 分")
            per_item.append({"item_id": iid, "status": "unparsable", "credit": 0.0})
            scored += 1
            continue

        pred_rank = CLASS_RANK[pred_cls]
        credit = rank_credit(pred_rank, true_rank)
        credit_sum += credit
        scored += 1
        if pred_rank == true_rank:
            exact += 1
        if side(pred_rank) != side(true_rank) and side(pred_rank) != 0 and side(true_rank) != 0:
            directional_errors += 1

        # --- 判据 set-F1 ---
        # 真值与预测**用同一个规范化函数**（否则真值里带强度修饰的码永远匹配不上）
        t_canon, t_bad = canonicalize_criteria(t.get("criteria_met"))
        p_canon, p_bad = canonicalize_criteria(a.get("criteria_met"))
        t_crit, p_crit = set(t_canon), set(p_canon)
        if t_bad:
            truth_unparsable += 1
        if p_bad:
            problems.append(f"{iid} 作答含无法识别的判据码（已忽略）：{p_bad}")
        item_f1 = None
        if t_crit:
            criteria_scored += 1
            inter += len(t_crit & p_crit)
            pred_total += len(p_crit)
            true_total += len(t_crit)
            p_ = len(t_crit & p_crit) / len(p_crit) if p_crit else 0.0
            r_ = len(t_crit & p_crit) / len(t_crit)
            item_f1 = 0.0 if (p_ + r_) == 0 else 2 * p_ * r_ / (p_ + r_)
        per_item.append(
            {
                "item_id": iid,
                "status": "ok",
                "predicted": pred_cls,
                "truth": true_cls,
                "credit": round(credit, 6),
                "criteria_f1": None if item_f1 is None else round(item_f1, 6),
                "criteria_missed": sorted(t_crit - p_crit),
                "criteria_spurious": sorted(p_crit - t_crit),
                "criteria_truth_unparsable": t_bad,
            }
        )

    classification_credit = round(credit_sum / scored, 6) if scored else None
    exact_accuracy = round(exact / scored, 6) if scored else None
    directional_error_rate = round(directional_errors / scored, 6) if scored else None

    if pred_total + true_total > 0:
        p_micro = inter / pred_total if pred_total else 0.0
        r_micro = inter / true_total if true_total else 0.0
        criteria_f1 = 0.0 if (p_micro + r_micro) == 0 else round(
            2 * p_micro * r_micro / (p_micro + r_micro), 6
        )
    else:
        criteria_f1 = None

    # --- 金丝雀：只算"方向一致性"，**不计入主分** ---
    pairs: dict[str, list[str]] = {}
    for iid in canary_ids:
        t = truth_by_id.get(iid) or {}
        anchor = t.get("canary_pair") or (items_by_id[iid].get("canary_of"))
        if anchor:
            pairs.setdefault(anchor, []).append(iid)

    canary_ok = canary_total = 0
    canary_detail: list[dict] = []
    for anchor, members in sorted(pairs.items()):
        a_ans = ans_by_id.get(anchor)
        a_cls = normalize_class(a_ans.get("classification")) if a_ans else None
        if a_cls is None:
            problems.append(f"金丝雀配对 {anchor} 的母题未作答/无法归一化，该对跳过")
            continue
        for cid in members:
            t = truth_by_id.get(cid) or {}
            expected = t.get("canary_expected", "unchanged")
            c_ans = ans_by_id.get(cid)
            c_cls = normalize_class(c_ans.get("classification")) if c_ans else None
            if c_cls is None:
                canary_total += 1
                canary_detail.append({"anchor": anchor, "canary": cid, "expected": expected,
                                      "actual": "missing", "ok": False})
                continue
            delta = CLASS_RANK[c_cls] - CLASS_RANK[a_cls]
            if expected == "unchanged":
                ok = delta == 0
            elif expected == "flip_more_pathogenic":
                ok = delta > 0
            elif expected == "flip_more_benign":
                ok = delta < 0
            else:
                ok = False
                problems.append(f"金丝雀 {cid} 的 canary_expected={expected!r} 未知")
            canary_total += 1
            canary_ok += 1 if ok else 0
            canary_detail.append(
                {"anchor": anchor, "canary": cid, "expected": expected,
                 "delta_rank": delta, "ok": ok}
            )

    canary_consistency = round(canary_ok / canary_total, 6) if canary_total else None

    if classification_credit is None:
        score = None
    elif criteria_f1 is None:
        score = classification_credit
        problems.append("无可评分判据（真值判据全为空），主分退化为仅 classification_credit")
    else:
        score = round(W_CREDIT * classification_credit + W_CRITERIA * criteria_f1, 6)

    status = "ok"
    if score is None:
        status = "failed"
    elif problems:
        status = "ok-with-warnings"

    return {
        "task_id": "T2",
        "status": status,
        "score": score,
        "score_weights": {
            "classification_credit": W_CREDIT,
            "criteria_f1": W_CRITERIA,
            "note": "权重是声明式约定，不是推导结果；两个分量都单独报出，可自行重新加权",
        },
        "classification_credit": classification_credit,
        "exact_accuracy": exact_accuracy,
        "criteria_f1": criteria_f1,
        "directional_error_rate": directional_error_rate,
        "canary_consistency": canary_consistency,
        "canary_note": "金丝雀是**诊断量**，测的是答案是否随证据合理移动；不计入主分与准确率",
        "counts": {
            "items_total": len(items),
            "items_real": len(real_ids),
            "items_canary": len(canary_ids),
            "scored": scored,
            "criteria_scored": criteria_scored,
            "truth_criteria_unparsable": truth_unparsable,
            "answers": len(answers),
            "canary_pairs_scored": canary_total,
        },
        "problems": problems,
        "per_item": per_item,
        "canary_detail": canary_detail,
    }


# ---------------------------------------------------------------------------
# 自检：判分器自己必须先被测过
# ---------------------------------------------------------------------------


def self_test() -> int:
    truth = [
        {"item_id": "DEMO-001", "assertion_normalized": "Pathogenic",
         "criteria_met": ["PVS1", "PM2", "PP3"]},
        {"item_id": "DEMO-002", "assertion_normalized": "Benign", "criteria_met": ["BA1"]},
        {"item_id": "DEMO-003", "assertion_normalized": "Uncertain significance",
         "criteria_met": ["PM2", "BP4"]},
        {"item_id": "DEMO-004", "assertion_normalized": "Pathogenic",
         "criteria_met": ["PVS1", "PM2", "PP3"]},
        {"item_id": "DEMO-005", "assertion_normalized": "Benign", "criteria_met": ["BA1"],
         "canary_expected": "flip_more_benign", "canary_pair": "DEMO-002"},
    ]
    items = [
        {"item_id": "DEMO-001", "canary": False},
        {"item_id": "DEMO-002", "canary": False},
        {"item_id": "DEMO-003", "canary": False},
        {"item_id": "DEMO-004", "canary": False},
        {"item_id": "DEMO-005", "canary": True, "canary_of": "DEMO-002"},
    ]
    answers = [
        # 1 完全正确
        {"item_id": "DEMO-001", "classification": "Pathogenic", "criteria_met": ["PVS1", "PM2", "PP3"]},
        # 2 正确，判据正确
        {"item_id": "DEMO-002", "classification": "Benign", "criteria_met": ["BA1"]},
        # 3 差一档（VUS → LP）：距离 1，同侧 → 0.75
        {"item_id": "DEMO-003", "classification": "Likely pathogenic", "criteria_met": ["PM2"]},
        # 4 判反方向（P → B）：距离 4，跨侧 → 0
        {"item_id": "DEMO-004", "classification": "Benign", "criteria_met": []},
        # 5 金丝雀：相对母题（Benign）更良性？秩不能再降 → 应为不满足
        {"item_id": "DEMO-005", "classification": "Benign", "criteria_met": ["BA1"]},
    ]

    r = grade(items, truth, answers)
    failures: list[str] = []

    def expect(cond: bool, msg: str) -> None:
        print(f"  [{'ok' if cond else 'FAIL'}] {msg}")
        if not cond:
            failures.append(msg)

    print("=== T2 判分器自检 ===")
    credit_by_id = {p["item_id"]: p.get("credit") for p in r["per_item"]}
    expect(credit_by_id["DEMO-001"] == 1.0, f"完全正确 → credit 1.0（实得 {credit_by_id['DEMO-001']}）")
    expect(credit_by_id["DEMO-003"] == 0.75, f"差一档同侧 → 0.75（实得 {credit_by_id['DEMO-003']}）")
    expect(credit_by_id["DEMO-004"] == 0.0, f"判反方向 → 0.0（实得 {credit_by_id['DEMO-004']}）")
    # 4 条真实题：(1.0 + 1.0 + 0.75 + 0.0) / 4
    expect(r["classification_credit"] == round(2.75 / 4, 6),
           f"classification_credit = 0.6875（实得 {r['classification_credit']}）")
    expect(r["exact_accuracy"] == round(2 / 4, 6),
           f"exact_accuracy = 0.5（实得 {r['exact_accuracy']}）")
    expect(r["directional_error_rate"] == round(1 / 4, 6),
           f"directional_error_rate = 0.25（实得 {r['directional_error_rate']}）")
    expect(r["counts"]["items_real"] == 4, f"真实题 4 条（实得 {r['counts']['items_real']}）")
    expect(r["counts"]["items_canary"] == 1, f"金丝雀 1 条（实得 {r['counts']['items_canary']}）")
    # 判据 micro-F1：交集 PVS1,PM2,PP3,BA1,PM2 = 5；pred 总数 7；true 总数 7
    expect(r["criteria_f1"] is not None, "criteria_f1 有值")
    expect(r["canary_consistency"] == 0.0,
           f"金丝雀方向未变（Benign→Benign）→ 一致性 0（实得 {r['canary_consistency']}）")
    expect(r["status"] == "ok-with-warnings" or r["status"] == "ok", f"status={r['status']}")

    print()
    if failures:
        print(f"❌ 自检未通过（{len(failures)} 项）")
        return 1
    print("✅ T2 判分器自检通过")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="T2 判分器（变异解读）")
    ap.add_argument("--items", help="题面 JSONL")
    ap.add_argument("--truth", help="真值 JSONL")
    ap.add_argument("--answers", help="作答 JSONL")
    ap.add_argument("--out", help="结果输出路径")
    ap.add_argument("--self-test", action="store_true", help="自检判分逻辑")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not (args.items and args.truth and args.answers):
        ap.error("需要 --items / --truth / --answers，或使用 --self-test")

    result = grade(
        load_jsonl(Path(args.items)),
        load_jsonl(Path(args.truth)),
        load_jsonl(Path(args.answers)),
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"结果写入 {args.out}")
    print(text)
    return 0 if result["score"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
