#!/usr/bin/env python3
r"""**内容级**答案泄露审计：会被 GitHub 公开的每个文件，都不许含轮换池内容。

为什么必须是内容级，而不是文件名级
----------------------------------
本项目此前对"该不该发布"的判断有一条隐含捷径：**看文件名**。
但文件名启发式两头都错：

  · **误报**：`tasks/T2/baseline_public/answers_oracle.jsonl` 名字里带 `answers`，
    看着最可疑 —— 可它只覆盖**公开的 3,789 条**，而公开集的真值本来就要发布
    （不给真值，第三方无法自助评分）。
  · **漏报**：任何**文件名很正常**却内嵌了轮换池 id 的文件。

真正该问的是："这个文件的**内容**里有没有只属于轮换池的东西？"
所以本脚本把每个会被提交的文件当文本扫，判断标准是**轮换池的 item_id 集合**。

判据是"集合交集"，不是"字符串出现"
----------------------------------
第一版直接数 `T2-\d{5}` 的出现，结果 `tasks/T2/grade.py` 被报成泄露 ——
查下去发现那是它 `--self-test` 里的**合成夹具**，ID 恰好和真实轮换池撞号
（夹具写 `…-00002 = Benign`，而真实轮换池是 `Uncertain significance`）。
**撞号会让任何基于字符串的判据误报**，所以本脚本额外做一步：
对命中处**核对标签是否与真实轮换池一致** —— 只有"ID 与标签都对得上"才算泄露。

（该夹具现已改用 `DEMO-xxx` 这类一眼可辨的合成 id —— 见
`tasks/T2/grade.py`。**测试夹具不该复用真实数据的标识符**：
它会污染所有基于 id 的审计，本轮就让我自己连误报两版。）

用法
----
    python3 verify_no_answer_leak.py
    python3 verify_no_answer_leak.py --self-test
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
T2DATA = ROOT / "tasks" / "T2" / "data"

ID_PAT = re.compile(r"\bT2-\d{5}[A-Z]?\b")

#: `_record_pairs` 需要"id → 真实标签"，但它是模块级函数（为了可测）。
#: 这里用一个模块级缓存传递，避免给每个调用点都加参数。
rot_labels_cache: dict[str, str] = {}


def _publishable() -> list[Path]:
    """复用 `not_published.json` —— **不另写一份过滤逻辑**（本项目的老毛病）。"""
    man = json.loads((HERE / "not_published.json").read_text(encoding="utf-8"))
    dirs = set(man.get("dirs") or {})
    suf = set(man.get("suffixes") or [])
    nms = set(man.get("names") or {})
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if ".git" in p.parts or any(x in nms for x in p.parts) or p.suffix in suf:
            continue
        if any(rel == d or rel.startswith(d + "/") for d in dirs):
            continue
        out.append(p)
    return sorted(out)


def _ids_and_labels(path: Path) -> dict[str, str]:
    """读一个 jsonl，返回 {item_id: assertion}。非 jsonl / 解析不了则返回 {}。"""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        i = d.get("item_id")
        if i:
            out[i] = d.get("assertion_normalized") or d.get("assertion") or ""
    return out


def load_rotation() -> tuple[set[str], dict[str, str]]:
    """轮换池的 id 集合 + id→标签映射。"""
    ids: set[str] = set()
    labels: dict[str, str] = {}
    for name in ("rotation/items.jsonl", "rotation/truth.jsonl"):
        p = T2DATA / name
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            i = d.get("item_id")
            if i:
                ids.add(i)
                lab = d.get("assertion_normalized") or d.get("assertion")
                if lab:
                    labels[i] = lab
    return ids, labels


def _record_pairs(text: str, rot_ids: set[str]) -> set[str]:
    """从文本里提取「**同一条 JSON 记录内**同时出现 id 与其真实标签」的 id 集合。

    为什么必须按记录解析，而不是按字符窗口找邻近
    --------------------------------------------
    前两版都错在同一件事上：**用"距离"近似"绑定"**。

      · 第一版：`lab in text` —— "标签在文件里"就算泄露。
        于是文件里**别的**夹具写的 `…-00001 → Pathogenic` 那个
        `Pathogenic`，把另一个 id 也算成了泄露。
      · 第二版：改成"标签出现在 id 附近 200 字符内"。
        但夹具是**密集排列**的，邻记录的标签仍落在窗口里 → 依然误报。
        更糟的是：**本脚本自己的注释**（解释这个 bug 时同时写了
        某个轮换池 id 与某个标签）也被判成泄露 —— 检查器把自己报了。

    → 正确做法：**不猜距离，按结构**。JSONL 的每一行就是一条记录，
      解析它、取 `item_id` 与标签字段，二者**在同一对象里**才算泄露。
      只有这样，"id 和标签只是碰巧挨着"才不会误报。

    对非 JSONL（如 `.py` / `.md`）同样适用：整份文件作为"一条记录"解析会失败，
    于是退化为"用 JSON 对象边界切分"—— 若切不出对象，就**不做泄露判定**
    （宁可不报，也不用距离猜测；误报会训练人忽略真报）。
    """
    confirmed: set[str] = set()

    def consider(obj: object) -> None:
        if not isinstance(obj, dict):
            return
        i = obj.get("item_id")
        if not isinstance(i, str) or i not in rot_ids:
            return
        lab = rot_labels_cache.get(i, "")
        if not lab:
            return
        # 同一条记录里，任一"标签类"字段等于真实标签
        for k, v in obj.items():
            if isinstance(v, str) and v == lab:
                confirmed.add(i)
                return

    # ① 先按行试（标准 JSONL）
    got_any = False
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("{") or not line.endswith("}"):
            continue
        try:
            consider(json.loads(line))
            got_any = True
        except ValueError:
            pass

    # ② 再按"对象边界"扫描（覆盖 `.py` 里跨行写的字面量 dict）
    for m in re.finditer(r"\{[^{}]*\"item_id\"[^{}]*\}", text, re.S):
        try:
            consider(json.loads(m.group(0)))
        except ValueError:
            pass

    # ③ 兜底：用 python 字面量语法试（`grade.py` 的夹具是 py dict，键带引号）
    for m in re.finditer(r"\{[^{}]*'item_id'[^{}]*\}", text, re.S):
        try:
            consider(ast.literal_eval(m.group(0)))
        except (ValueError, SyntaxError):
            pass

    return confirmed


def scan(files: list[Path] | None = None) -> tuple[list[str], list[str], int]:
    """返回 (确认的泄露, 疑似撞号, 扫描文件数)。"""
    global rot_labels_cache
    rot_ids, rot_labels = load_rotation()
    rot_labels_cache = rot_labels
    files = files if files is not None else _publishable()
    leaked: list[str] = []
    collisions: list[str] = []
    scanned = 0
    for p in files:
        try:
            if p.stat().st_size > 40 * 1024 * 1024:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        found = set(ID_PAT.findall(text)) & rot_ids
        if not found:
            continue
        rel = p.relative_to(ROOT).as_posix() if ROOT in p.parents else str(p)
        confirmed = sorted(_record_pairs(text, rot_ids))
        if confirmed:
            leaked.append(f"{rel}: **同一条记录内**出现轮换池 id 与其真实标签 {confirmed[:4]}")
        else:
            collisions.append(f"{rel}: 出现轮换池 id {sorted(found)[:4]}"
                              "（未发现与其绑定的真实标签 → 疑似合成夹具撞号）")
    return leaked, collisions, scanned


def self_test() -> int:
    """负向测试：真泄露必须抓到；纯撞号必须**不**算泄露。"""
    import tempfile

    rot_ids, rot_labels = load_rotation()
    if not rot_ids:
        print("SKIP: 缺轮换池数据（未生成）")
        return 0
    sample_id = sorted(rot_ids)[0]
    sample_lab = rot_labels.get(sample_id, "")

    tmp = Path(tempfile.mkdtemp(prefix="leak-audit-"))
    ok = True
    try:
        # ① 真泄露：id + 真实标签都在
        f1 = tmp / "real_leak.jsonl"
        f1.write_text(json.dumps({"item_id": sample_id, "assertion": sample_lab},
                                 ensure_ascii=False) + "\n", encoding="utf-8")
        leaked, coll, _ = scan([f1])
        c1 = bool(leaked)
        ok = ok and c1
        print(f"  {'✅' if c1 else '❌'} 真泄露（id+真实标签）→ {'抓到' if c1 else '漏了'}")

        # ② 纯撞号：id 在，但标签是编的 → 不该算泄露
        f2 = tmp / "collision.jsonl"
        f2.write_text(json.dumps({"item_id": sample_id,
                                  "assertion": "DEFINITELY-NOT-THE-REAL-LABEL"},
                                 ensure_ascii=False) + "\n", encoding="utf-8")
        leaked2, coll2, _ = scan([f2])
        c2 = (not leaked2) and bool(coll2)
        ok = ok and c2
        print(f"  {'✅' if c2 else '❌'} 纯撞号（标签不符）→ "
              f"{'判为疑似而非泄露' if c2 else '被误报成泄露'}")

        # ③ 干净文件
        f3 = tmp / "clean.md"
        f3.write_text("T1 的区间是 chr20:10–12 Mb，与 T2 无关。\n", encoding="utf-8")
        leaked3, coll3, _ = scan([f3])
        c3 = not (leaked3 or coll3)
        ok = ok and c3
        print(f"  {'✅' if c3 else '❌'} 干净文件 → {'不报' if c3 else '误报'}")

        # ④ **关键的近似误报用例**：同一个文件里，id 在里面、
        #    它的"标签"也在里面 —— 但那个标签属于**另一条记录**。
        #    这正是 `tasks/T2/grade.py` 的真实情形（第一版据此误报了 2 处）。
        f4 = tmp / "far_apart.jsonl"
        other_lab = "Pathogenic" if sample_lab != "Pathogenic" else "Benign"
        f4.write_text(
            json.dumps({"item_id": "DEMO-99991", "assertion": sample_lab},
                       ensure_ascii=False)
            + "\n"
            + ("x" * 500) + "\n"          # 拉开距离
            + json.dumps({"item_id": sample_id, "assertion": other_lab},
                         ensure_ascii=False) + "\n",
            encoding="utf-8")
        leaked4, coll4, _ = scan([f4])
        # 该 id 的真实标签虽在文件里，但距离很远 → 不该判为泄露
        c4 = not leaked4
        ok = ok and c4
        print(f"  {'✅' if c4 else '❌'} 标签属**别的记录**（相隔很远）→ "
              f"{'不误报' if c4 else '误报成泄露'}")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("负向测试 " + ("全部通过（含 2 个必须正确区分的用例）" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="内容级答案泄露审计（GitHub 发布前）")
    ap.add_argument("--self-test", action="store_true", help="负向测试")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    rot_ids, _ = load_rotation()
    if not rot_ids:
        print("SKIP: 缺轮换池数据（未生成）—— 无法做内容级审计")
        return 0

    leaked, collisions, scanned = scan()
    print(f"内容级扫描：{scanned} 个会被公开的文件（判据 = 轮换池 {len(rot_ids)} 个 id 的交集）")
    if collisions:
        print(f"\n⚠️ {len(collisions)} 个文件出现轮换池 id，但**未发现对应真实标签**"
              "（疑似合成夹具撞号，非泄露）：")
        for c in collisions:
            print("   " + c)
        print("   建议：把夹具里的 id 改成明显合成的（如 `DEMO-0001`），"
              "避免污染审计判据。")
    if leaked:
        print(f"\n❌ **{len(leaked)} 处确认泄露** —— 绝不能公开：")
        for h in leaked:
            print("   " + h)
        return 1
    print("\n✅ 没有任何公开文件含轮换池内容（id 与真实标签均未出现）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
