#!/usr/bin/env python3
"""VeriBench-Bio 许可与安全红线审计（CI 门禁）。

设计意图：把"许可洁净"从文档里的一句承诺，变成一段能让构建失败的代码。
竞品里没有人这么做 —— 而 BioProBench 正是因为在第 N 天才发现许可问题，
523,784 条实例里只有 350,565 条能公开（其余因来源许可受限只能内部保留）。

用法：
    python scripts/audit_licenses.py ledger/items.jsonl        # 审计台账
    python scripts/audit_licenses.py ledger/items.jsonl --require-file   # CI 模式
    python scripts/audit_licenses.py --self-test               # 自检审计器本身

退出码：
    0 = 无致命违规（警告不算失败）
    1 = 存在致命违规
    2 = 用法/文件错误
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# 策略常量（改这里 = 改项目红线，请同步 SPEC.md §5.3 与 docs/DATACARD.md）
# --------------------------------------------------------------------------

#: 唯一允许的许可栈。大厂与既有基准踩过的坑：LAB-Bench 是 CC-BY-SA（传染）、
#: BioEval 数据是 CC-BY-NC（禁商用）。
WHITELIST = {
    "CC0-1.0",
    "CC-BY-4.0",
    "CC-BY-3.0",
    "CC-BY-2.0",
    "PUBLIC-DOMAIN",
    "US-GOV-PUBLIC-DOMAIN",
}

UNKNOWN_VALUES = {"", "unknown", "none", "n/a", "na", "unclear", "tbd", "?"}

#: 任何非 none 的加工都会产生衍生作品 —— 而 CC BY-ND 禁止衍生作品。
#: 因此 ND 许可对这个项目等于"不可用"，不是"标注一下就行"。
DERIVATIVE = {"extracted", "rewritten", "translated", "programmatic"}

REQUIRED_FIELDS = (
    "item_id",
    "task",
    "truth_type",
    "source_type",
    "source_ref",
    "source_license_code",
    "license_url",
    "retrieval_date",
    "license_spdx",
    "redistribution_ok",
    "commercial_ok",
    "contains_human_data",
    "contains_restricted_data",
    "visibility",
    "derivation",
    "review_status",
    "created_at",
)


def norm(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def is_unknown_license(license_spdx: object) -> bool:
    return norm(license_spdx) in UNKNOWN_VALUES


def has_tag(license_spdx: object, tag: str) -> bool:
    return tag.upper() in norm(license_spdx).upper()


# --------------------------------------------------------------------------
# 审计规则
# --------------------------------------------------------------------------


def audit_item(item: dict, index: int) -> tuple[list[str], list[str]]:
    """返回 (致命违规, 警告)，每项为 "R# 说明" 形式。"""
    fatal: list[str] = []
    warn: list[str] = []

    item_id = item.get("item_id") or f"<第 {index} 行>"

    missing = [f for f in REQUIRED_FIELDS if f not in item]
    if missing:
        return [f"R0 缺少必填字段: {', '.join(missing)}"], []

    license_spdx = item["license_spdx"]
    unknown = is_unknown_license(license_spdx)
    public = item.get("visibility") == "public"
    redistribution_ok = bool(item.get("redistribution_ok"))
    commercial_ok = bool(item.get("commercial_ok"))
    derivation = norm(item.get("derivation"))
    platform = norm(item.get("source_platform"))
    safety = norm(item.get("safety_review"))
    truth_type = norm(item.get("truth_type"))

    # R1 许可不明却允许再分发 —— 等于把风险写进了开源仓库
    if unknown and redistribution_ok:
        fatal.append(
            f"R1 许可为 {license_spdx!r} 却声明 redistribution_ok=true，"
            "必须核实许可或改为 false"
        )

    # R2 声明可商用但许可是 -NC-
    if commercial_ok and has_tag(license_spdx, "-NC-"):
        fatal.append(f"R2 许可 {license_spdx!r} 含 -NC-（禁商用）却声明 commercial_ok=true")

    # R3 受控数据出现在公开目录
    if item.get("contains_restricted_data") and public:
        fatal.append("R3 contains_restricted_data=true 却 visibility=public（受控数据不得公开）")

    # R4 ND 许可 + 衍生加工
    if has_tag(license_spdx, "-ND-") and derivation in DERIVATIVE:
        fatal.append(
            f"R4 许可 {license_spdx!r} 含 -ND-（禁衍生）却执行了 derivation={derivation!r}；"
            "转成评测题/改写本身就是衍生作品"
        )

    # R5 允许再分发但不在白名单内（SA 传染同样在此被拦下）
    if redistribution_ok and not unknown and norm(license_spdx) not in {
        w.lower() for w in WHITELIST
    }:
        fatal.append(
            f"R5 许可 {license_spdx!r} 不在白名单内却声明 redistribution_ok=true；"
            f"白名单: {', '.join(sorted(WHITELIST))}"
        )

    # R6 arXiv 默认许可不是开放许可（仅元数据是 CC0），不许当安全区
    if platform == "arxiv" and norm(license_spdx) not in {w.lower() for w in WHITELIST}:
        fatal.append(
            f"R6 source_platform=arxiv 而许可 {license_spdx!r} 不在白名单；"
            "arXiv 默认许可 LIMITS RE-USE OF ANY TYPE，必须逐篇解析 OAI-PMH licence 字段"
        )

    # R7 公开条目许可必须已知
    if public and unknown:
        fatal.append(f"R7 visibility=public 但许可为 {license_spdx!r}，公开条目必须核实许可")

    # R8/R9 生物安全
    if safety == "rejected" and public:
        fatal.append("R8 safety_review=rejected 的条目仍标记为 public")
    if safety == "gated" and public:
        fatal.append("R9 safety_review=gated 的条目必须门控发布，不得进入 public 目录")

    # R10 非权威真值必须写明来源与锁定版本（T7/T8 的诚实处理）
    if truth_type != "authoritative" and not str(item.get("truth_note") or "").strip():
        fatal.append(
            f"R10 truth_type={truth_type!r} 但未提供 truth_note；非权威真值必须说明来源、"
            "为何不权威、以及锁定的参考实现及其精确版本"
        )

    # R11 无真值的题目不得计分，也不得公开
    if truth_type == "none" and public:
        fatal.append("R11 truth_type=none 的条目不得进入公开榜单（无真值即不可计分）")

    # R12 contains_human_data 必须有可审计的依据，且依据与布尔值自洽
    # 起因：本项目曾把 27 篇（含蜜蜂转录组、大鼠心梗模型、叙述性综述）一律标成
    # contains_human_data=true。裸布尔没有任何可核对的痕迹，所以这个错误既不会
    # 被审计器发现，也无法被第三方复核。现在强制给出 basis。
    TRUE_BASES = {"human_subjects_primary", "human_biospecimen"}
    # human_aggregate_only 是 2026-09 补的：把本 schema 用于真实数据（gnomAD v4 频率）时
    # 才发现"来自人类但已完全聚合、不含个体记录"没有安放处，前四个取值都不合适。
    FALSE_BASES = {"human_secondary_review", "human_aggregate_only", "non_human_only"}
    chd = item.get("contains_human_data")
    basis = norm(item.get("human_data_basis"))
    if "contains_human_data" in item:
        if basis not in (TRUE_BASES | FALSE_BASES | {"unknown"}):
            fatal.append(
                "R12 缺少或非法的 human_data_basis——裸布尔不可审计，"
                "必须声明判定依据（human_subjects_primary / human_biospecimen / "
                "human_secondary_review / non_human_only / unknown）"
            )
        elif basis == "unknown":
            if public:
                fatal.append("R12 human_data_basis=unknown 的条目不得公开（未判定即不可发布）")
        elif basis in TRUE_BASES and chd is not True:
            fatal.append(f"R12 human_data_basis={basis!r} 对应 contains_human_data=true，实际为 {chd!r}")
        elif basis in FALSE_BASES and chd is not False:
            fatal.append(f"R12 human_data_basis={basis!r} 对应 contains_human_data=false，实际为 {chd!r}")

    # W1 未复核条目（构建期允许，计分前必须清零）
    if norm(item.get("review_status")) != "reviewed":
        warn.append(f"W1 review_status={item.get('review_status')!r}，进入公开榜单前必须复核")

    return fatal, warn


def audit_items(items: list[dict]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    fatal_all: list[tuple[str, str]] = []
    warn_all: list[tuple[str, str]] = []
    for i, item in enumerate(items, start=1):
        item_id = item.get("item_id") or f"<第 {i} 行>"
        fatal, warn = audit_item(item, i)
        fatal_all.extend((item_id, msg) for msg in fatal)
        warn_all.extend((item_id, msg) for msg in warn)
    return fatal_all, warn_all


# --------------------------------------------------------------------------
# 自检：证明审计器本身能正确打红（不是"跑通了等于没问题"）
# --------------------------------------------------------------------------


def _base(**overrides: object) -> dict:
    item: dict = {
        "item_id": "T1-0001",
        "task": "T1",
        "truth_type": "authoritative",
        "source_type": "public_dataset",
        "source_platform": "giab",
        "source_ref": "NIST v4.2.1",
        "source_license_code": "public-domain (US Government work)",
        "license_url": "https://www.nist.gov/open/license",
        "retrieval_date": "2026-09-15",
        "license_spdx": "CC0-1.0",
        "redistribution_ok": True,
        "commercial_ok": True,
        "contains_human_data": True,
        "human_data_basis": "human_subjects_primary",
        "contains_restricted_data": False,
        "visibility": "public",
        "derivation": "none",
        "safety_review": "not-applicable",
        "review_status": "reviewed",
        "created_at": "2026-09-15T00:00:00Z",
    }
    item.update(overrides)
    # 若调用方改了 contains_human_data 却没说依据，自动配一个自洽的默认值。
    # 否则每个改这个布尔值的用例都会连带触发 R12，把"被测规则"淹没在噪声里。
    # 显式传入 human_data_basis（包括 None）时不覆盖——R12 的用例正依赖这一点。
    if "human_data_basis" not in overrides and "contains_human_data" in overrides:
        item["human_data_basis"] = (
            "human_subjects_primary" if item["contains_human_data"] else "non_human_only"
        )
    return item


SELF_TEST_CASES: list[tuple[str, dict, set[str]]] = [
    ("合规样本", _base(), set()),
    ("缺字段", {k: v for k, v in _base().items() if k != "license_spdx"}, {"R0"}),
    (
        "许可不明却可再分发",
        _base(license_spdx="unknown", redistribution_ok=True, visibility="internal"),
        {"R1"},
    ),
    (
        "NC 却声明可商用",
        _base(license_spdx="CC-BY-NC-4.0", redistribution_ok=False, commercial_ok=True,
              visibility="internal"),
        {"R2"},
    ),
    ("受控数据公开", _base(contains_restricted_data=True), {"R3"}),
    (
        "ND 却改写",
        _base(license_spdx="CC-BY-ND-4.0", redistribution_ok=False, commercial_ok=True,
              derivation="rewritten", contains_human_data=False),
        {"R4"},
    ),
    (
        "SA 传染被拦",
        _base(license_spdx="CC-BY-SA-4.0", commercial_ok=True),
        {"R5"},
    ),
    (
        "arXiv 默认许可被拦",
        _base(source_platform="arxiv", license_spdx="ARXIV-DEFAULT-1.0",
              redistribution_ok=False, commercial_ok=False, contains_human_data=False),
        {"R6"},
    ),
    (
        "公开但许可未知",
        _base(license_spdx="unknown", redistribution_ok=False, commercial_ok=False,
              contains_human_data=False),
        {"R7"},
    ),
    ("安全审阅否决却公开", _base(safety_review="rejected"), {"R8"}),
    ("门控条目混入公开", _base(safety_review="gated"), {"R9"}),
    (
        "非权威真值却无说明",
        _base(truth_type="reference-implementation"),
        {"R10"},
    ),
    (
        "无真值却公开",
        _base(truth_type="none", truth_note="该任务不存在权威真值，仅作可复现性对照"),
        {"R11"},
    ),
    # R12：裸布尔不可审计。以下三个用例分别覆盖缺依据、依据与布尔矛盾、未判定却公开
    (
        "人类数据只给裸布尔",
        _base(contains_human_data=True, human_data_basis=None),
        {"R12"},
    ),
    (
        "依据与布尔自相矛盾",
        _base(contains_human_data=False, human_data_basis="human_subjects_primary"),
        {"R12"},
    ),
    (
        "人类数据依据未判定却公开",
        _base(contains_human_data=True, human_data_basis="unknown"),
        {"R12"},
    ),
]


def run_self_test() -> int:
    failures: list[str] = []
    for name, item, expected in SELF_TEST_CASES:
        fatal, _ = audit_item(item, 1)
        got = {msg.split(" ", 1)[0] for msg in fatal}
        status = "ok" if got == expected else "FAIL"
        if got != expected:
            failures.append(f"{name}: 期望 {sorted(expected)} 实得 {sorted(got)}")
        print(f"  [{status}] {name}: 触发 {sorted(got) or '无'}")

    print()
    if failures:
        print(f"自检未通过（{len(failures)}/{len(SELF_TEST_CASES)} 失败）:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"自检通过：{len(SELF_TEST_CASES)} 个用例全部符合预期。")
    return 0


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------


def load_ledger(path: Path) -> list[dict]:
    items: list[dict] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[错误] {path}:{lineno} 不是合法 JSON：{exc}") from exc
        if not isinstance(obj, dict):
            raise SystemExit(f"[错误] {path}:{lineno} 顶层必须是 JSON 对象")
        items.append(obj)
    return items


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认不是 UTF-8，中文输出会乱码
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(description="VeriBench-Bio 许可与安全红线审计")
    parser.add_argument("ledger", nargs="?", help="ledger JSONL 路径")
    parser.add_argument("--self-test", action="store_true", help="自检审计器规则")
    parser.add_argument(
        "--require-file",
        action="store_true",
        help="台账文件不存在时视为失败（CI 模式）",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not args.ledger:
        parser.error("需要提供 ledger 路径，或使用 --self-test")

    path = Path(args.ledger)
    if not path.exists():
        msg = f"台账不存在：{path}"
        if args.require_file:
            print(f"[失败] {msg}", file=sys.stderr)
            return 2
        print(f"[提示] {msg}（构建期允许为空，CI 请加 --require-file）")
        return 0

    items = load_ledger(path)
    fatal, warn = audit_items(items)

    print(f"审计台账：{path}")
    print(f"条目数：{len(items)}")
    print()

    for _item_id, msg in fatal:
        print(f"  [致命] {msg}")
    for _item_id, msg in warn:
        print(f"  [警告] {msg}")

    print()
    if fatal:
        print(f"审计未通过：{len(fatal)} 条致命违规，{len(warn)} 条警告。")
        print("不合规的题目不得进入公开评测集 —— 请修正台账或将其标记为 internal。")
        return 1

    print(f"审计通过：0 条致命违规，{len(warn)} 条警告。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
