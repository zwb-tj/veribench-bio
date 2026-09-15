#!/usr/bin/env python3
"""用 JSON Schema 校验数据 —— 此前这一步**不在自动检查里**。

这是一个真实的漏洞
------------------
仓库里有两份 schema（`schema/ledger.schema.json`、`rubric/schema/rubric-item.schema.json`），
它们定义了台账与题目的**必填字段、枚举取值、pattern**。审计器 R0/R12 也依赖它们。

但是：**schema 与数据是否一致，此前只靠我在命令行里手动跑 `jsonschema` 验证过几次，
没有任何一条自动检查在做这件事。**

后果很具体：schema 和数据可以各自漂移而无人发现 ——
比如有人给 schema 加了个必填字段，而 101 条标准里一条都没补；
或者 schema 把 `license_spdx` 限定成枚举，而台账里冒出一个白名单外的值。
**这两件事审计器都不查。**

关于 jsonschema 这个依赖
------------------------
本仓库的 Python 代码**零第三方依赖**（见 `check_env_deps.py`）。
`jsonschema` 是**可选**的：装了就用它做完整校验，没装就 **SKIP 并明说"本次未校验"**。
—— 不自己写一个残缺的校验器冒充完整校验（那会给出虚假的信心），
也不把一个可选工具变成硬依赖。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

TARGETS = [
    # (数据文件, 对应 schema, 说明)
    ("rubric/items/items_v1.2.jsonl", "rubric/schema/rubric-item.schema.json", "rubric 正式版题目"),
    ("rubric/items/items.jsonl", "rubric/schema/rubric-item.schema.json", "rubric 原始版 v1.0"),
    ("ledger/items.jsonl", "schema/ledger.schema.json", "主台账（T1/T2/R 全部条目）"),
    # 2026-09 补：T2 的两个 schema 此前**完全没有被任何代码引用** ——
    # 后果是它们各自带着一个非法的 ASCII 双引号（中文串内）**烂了很久也没人知道**，
    # 直到新加的 `verify_json_files.py` 才扫出来。schema 不被消费 = 不会漂移报警，
    # 但它同时也不再是约束。把它们接上真实数据。
    ("tasks/T2/data/items.jsonl", "tasks/T2/schema/t2-item.schema.json", "T2 题面"),
    ("tasks/T2/data/truth.jsonl", "tasks/T2/schema/t2-truth.schema.json", "T2 真值"),
]


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="JSON Schema 校验")
    args = ap.parse_args(argv)

    try:
        import jsonschema  # noqa: PLC0415
    except ImportError:
        print("SKIP: 未安装 jsonschema —— **本次未做 schema 校验**")
        print("      （它是可选依赖；仓库代码本身零第三方依赖。"
              "pip install jsonschema 可启用这一步）")
        return 0

    n_ok = n_bad = n_skip = 0
    problems: list[str] = []
    for data_rel, schema_rel, label in TARGETS:
        data_p, schema_p = ROOT / data_rel, ROOT / schema_rel
        if not data_p.is_file():
            print(f"⏭ {label}: 缺 {data_rel}")
            n_skip += 1
            continue
        if not schema_p.is_file():
            print(f"❌ {label}: 缺 schema {schema_rel}")
            problems.append(f"{label}: schema 文件不存在")
            n_bad += 1
            continue
        schema = json.loads(schema_p.read_text(encoding="utf-8"))
        rows = [json.loads(l) for l in data_p.read_text(encoding="utf-8").splitlines() if l.strip()]
        bad = 0
        first = ""
        for i, r in enumerate(rows, 1):
            try:
                jsonschema.validate(r, schema)
            except jsonschema.ValidationError as exc:
                bad += 1
                if not first:
                    key = r.get("item_id") or r.get("criterion_id") or f"第 {i} 行"
                    first = f"{key}: {str(exc).splitlines()[0][:110]}"
        if bad:
            print(f"❌ {label}: {len(rows)} 条中 {bad} 条不合 schema")
            print(f"      首个：{first}")
            problems.append(f"{label}: {bad} 条不合")
            n_bad += 1
        else:
            print(f"✅ {label}: {len(rows)} 条全部合 schema")
            n_ok += 1

    print()
    if problems:
        print(f"❌ {n_bad} 个数据集不符合 schema：")
        for p in problems:
            print(f"   {p}")
        print("\n   修哪个？**先确认是数据错了还是 schema 错了** —— 别默认数据错。")
        return 1
    print(f"✅ schema 校验通过（{n_ok} 个数据集，跳过 {n_skip} 个）")

    # ---- schema 与审计器是否同步 -------------------------------------------
    # ⚠️ "必填字段"有两个真源：schema 的 `required` 与审计器的 `REQUIRED_FIELDS`。
    #    两者可以各自漂移而无人发现 —— 本轮就发现 ledger.schema.json **本身是非法 JSON**
    #    （JSON 串里混了 ASCII 引号），而审计器照样通过，因为它**根本不读 schema**。
    #    所以这里显式比对，把"两个真源"的差异摆出来。
    import ast as _ast
    import re as _re
    sch_p = ROOT / "schema" / "ledger.schema.json"
    aud_p = ROOT / "scripts" / "audit_licenses.py"
    if sch_p.is_file() and aud_p.is_file():
        sch_req = set(json.loads(sch_p.read_text(encoding="utf-8")).get("required", []))
        src = aud_p.read_text(encoding="utf-8")
        # ⚠️ 审计器用的是**元组** `REQUIRED_FIELDS = (...)`，第一版正则只匹配 `[...]`，
        #    于是把它解析成 0 个字段，报出"17 个 vs 0 个"的假差异。
        #    提取别人的数据结构时，别假设它是哪一种容器。
        m = _re.search(r"REQUIRED_FIELDS\s*=\s*[\[(](.*?)[\])]", src, _re.S)
        aud_req: set[str] = set()
        if m:
            for node in _ast.walk(_ast.parse("x=[" + m.group(1) + "]")):
                if isinstance(node, _ast.Constant) and isinstance(node.value, str):
                    aud_req.add(node.value)
        print()
        print(f"必填字段的两个真源：schema {len(sch_req)} 个 · 审计器 {len(aud_req)} 个")
        only_s = sorted(sch_req - aud_req)
        only_a = sorted(aud_req - sch_req)
        if only_s or only_a:
            print(f"  ⚠️ 只在 schema 里：{only_s or '无'}")
            print(f"  ⚠️ 只在审计器里：{only_a or '无'}")
            print("  → 两者不一致。**必须确认是哪一个该改**，否则数据可能满足一个、违反另一个。")
        else:
            print("  ✅ 两个真源一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
