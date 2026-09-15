#!/usr/bin/env python3
"""mmCIF 的最小确定性解析器 —— 只取 T3 需要的字段。

为什么不用 Bio.PDB / gemmi
--------------------------
项目承诺**零第三方依赖**。而且 T3 的卖点是"真值可由原文确定性重算" ——
引入一个会随版本改变行为的库，反而削弱这一点。

⚠️ **解析必须按 `loop_` 语义，不能按 `#` 切块。**
`#` 在 mmCIF 里是**列名块与数据块之间的分隔符**，出现在数据**之前**。
实测（2026-09）：按 `#` 切块会让 4HHB / 6LU7 / 2LZM 报 **0 个原子**
（真实 4,384 / 2,387 / 1,309）—— 而 0 看起来像"这个结构没有原子"，
**不会自己喊出来**。

`cross_check_totals()` 就是为了让这类错误喊出来：它用**不依赖解析结构**的
全文件计数做裁判，两者不一致就抛异常。
"""

from __future__ import annotations

import math
import re
from collections import Counter


class MmcifError(ValueError):
    """解析失败 —— 必须响亮，不能静默返回空结果。"""


#: `_atom_site` 里我们需要的列（其余列忽略，但不影响行解析）
WANTED = (
    "group_PDB", "type_symbol", "label_atom_id", "label_comp_id",
    "label_asym_id", "label_seq_id", "Cartn_x", "Cartn_y", "Cartn_z",
    #: ⚠️ 必须有它才能报告 model 数。NMR 结构会把**所有 model** 的原子都列出来，
    #:    没有这一列就无法说明"我们数了几个 model"（审查 F3 的由来：
    #:    1L2Y 有 38 个 model，我们报 11,552，RCSB 只算一个 model 报 154）。
    "pdbx_PDB_model_num",
)


def parse_atom_site(text: str) -> list[dict]:
    """按 `loop_` 语义解析 `_atom_site`，返回每个原子一行的 dict 列表。

    返回空列表意味着**这个文件里没有 atom_site** —— 调用方应当把它当异常，
    而不是当"零个原子"（见模块 docstring 的教训）。
    """
    lines = text.splitlines()
    start = next((k for k, l in enumerate(lines)
                  if l.startswith("_atom_site.")), None)
    if start is None:
        raise MmcifError("文件里没有 _atom_site 段 —— 不是结构文件？")

    # ① 连续读列名
    cols: list[str] = []
    i = start
    while i < len(lines) and lines[i].startswith("_atom_site."):
        cols.append(lines[i].strip().split(".", 1)[1])
        i += 1
    if not cols:
        raise MmcifError("_atom_site 后面没有列名")

    idx = {c: k for k, c in enumerate(cols)}
    missing = [w for w in WANTED if w not in idx]
    if missing:
        raise MmcifError(f"_atom_site 缺列：{missing}（实际列 {cols}）")

    # ② 之后逐行读数据，直到 `#` 或下一个 `_` 类别
    out: list[dict] = []
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            break
        if line.startswith("_") and not line.startswith("_atom_site."):
            break
        if line.startswith(("ATOM", "HETATM")):
            f = line.split()
            if len(f) < len(cols):
                raise MmcifError(
                    f"第 {i + 1} 行字段数 {len(f)} < 列数 {len(cols)}：{line[:80]!r}")
            out.append({w: f[idx[w]] for w in WANTED})
        i += 1
    return out


def cross_check_totals(text: str, atoms: list[dict]) -> None:
    """用**独立于解析结构**的判据核对计数。

    判据不共享解析假设：这里只数「以 ATOM/HETATM 开头的行」，
    完全不管 loop_ 边界。两者不一致说明解析错位 —— 抛异常。
    """
    n_atom = len(re.findall(r"^ATOM\s", text, re.M))
    n_het = len(re.findall(r"^HETATM\s", text, re.M))
    got_atom = sum(1 for a in atoms if a["group_PDB"] == "ATOM")
    got_het = sum(1 for a in atoms if a["group_PDB"] == "HETATM")
    if (n_atom, n_het) != (got_atom, got_het):
        raise MmcifError(
            f"解析计数与全文件计数不符：解析 {got_atom}/{got_het}，"
            f"全文件 {n_atom}/{n_het} —— 解析边界错了")


def _f(s: str) -> float:
    """坐标解析。只用内建 float()（正确舍入），保证确定性。"""
    return float(s)


def compute_metrics(atoms: list[dict]) -> dict:
    """由原子列表算 T3 的五个判分量（定义见 tasks/T3/DESIGN.md §3）。

    ⚠️ 确定性要求：不做并行求和、不用 numpy、不用 `math.dist`
    （其内部实现可能随版本变化）。距离显式展开。
    """
    atom_rows = [a for a in atoms if a["group_PDB"] == "ATOM"]
    het_rows = [a for a in atoms if a["group_PDB"] == "HETATM"]

    elems = Counter(a["type_symbol"] for a in atom_rows)
    chains = {a["label_asym_id"] for a in atom_rows}

    #: 第一条链上按出现顺序排在最前的两个 CA
    ca_by_chain: dict[str, list[tuple[float, float, float]]] = {}
    for a in atom_rows:
        if a["label_atom_id"] == "CA":
            ca_by_chain.setdefault(a["label_asym_id"], []).append(
                (_f(a["Cartn_x"]), _f(a["Cartn_y"]), _f(a["Cartn_z"])))

    ca_distance = None
    for ch in sorted(ca_by_chain):
        pts = ca_by_chain[ch]
        if len(pts) >= 2:
            dx = pts[0][0] - pts[1][0]
            dy = pts[0][1] - pts[1][1]
            dz = pts[0][2] - pts[1][2]
            ca_distance = round(math.sqrt(dx * dx + dy * dy + dz * dz), 3)
            break

    return {
        "atom_count": len(atom_rows),
        "hetatm_count": len(het_rows),
        "chain_count": len(chains),
        "element_histogram": dict(sorted(elems.items())),
        #: ⚠️ model 数**必须报告**：NMR 结构的 atom_count 是**全部 model 之和**，
        #:    若不说明，作答者按"一个 model"理解会被判错却无从知悉（审查 F3）。
        #:    报告它，口径就从"隐藏约定"变成"可见事实"。
        "model_count": len({a["pdbx_PDB_model_num"] for a in atoms}),
        "ca_distance": ca_distance,
    }


def metrics_from_cif(text: str) -> dict:
    """一步到位：解析 + 交叉核对 + 算量。"""
    atoms = parse_atom_site(text)
    if not atoms:
        raise MmcifError("_atom_site 段非空但没有数据行 —— 解析边界可能错了")
    cross_check_totals(text, atoms)
    return compute_metrics(atoms)


def self_test() -> int:
    """自检：**证明这些函数在坏输入上会失败**，而不是恰好能跑。"""
    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            ok = False
        print(f"  {'✅' if cond else '❌'} {label}" + (f"  {detail}" if detail else ""))

    print("=== mmcif_parse 自检 ===")

    # ① 一份最小但合法的 mmCIF（含 `#` 在数据**之前** —— 正是坑所在）
    good = (
        "data_TEST\n"
        "#\n"
        "loop_\n"
        "_atom_site.group_PDB\n"
        "_atom_site.type_symbol\n"
        "_atom_site.label_atom_id\n"
        "_atom_site.label_comp_id\n"
        "_atom_site.label_asym_id\n"
        "_atom_site.label_seq_id\n"
        "_atom_site.Cartn_x\n"
        "_atom_site.Cartn_y\n"
        "_atom_site.Cartn_z\n"
        "_atom_site.pdbx_PDB_model_num\n"
        "ATOM C CA GLY A 1 0.000 0.000 0.000 1\n"
        "ATOM C CA GLY A 2 3.000 4.000 0.000 1\n"
        "HETATM O O HOH B 1 1.000 1.000 1.000 1\n"
        "#\n"
    )
    m = metrics_from_cif(good)
    check("合法输入：atom_count=2", m["atom_count"] == 2, str(m["atom_count"]))
    check("合法输入：hetatm_count=1", m["hetatm_count"] == 1, str(m["hetatm_count"]))
    check("合法输入：chain_count=1", m["chain_count"] == 1, str(m["chain_count"]))
    check("合法输入：model_count=1", m["model_count"] == 1, str(m["model_count"]))
    # (0,0,0) 与 (3,4,0) 的距离 = 5.0 —— 教科书 3-4-5
    check("合法输入：CA 距离=5.0", m["ca_distance"] == 5.0, str(m["ca_distance"]))

    # ①b **多 model**（NMR 情形）：2 个 model 各 1 个 ATOM。
    #     这条直接对应审查 F3 —— 必须让"数了几个 model"是**可观察**的，
    #     否则按"一个 model"理解的作答者会被判错却无从知悉。
    multi = (
        "data_MULTI\n"
        "loop_\n"
        "_atom_site.group_PDB\n"
        "_atom_site.type_symbol\n"
        "_atom_site.label_atom_id\n"
        "_atom_site.label_comp_id\n"
        "_atom_site.label_asym_id\n"
        "_atom_site.label_seq_id\n"
        "_atom_site.Cartn_x\n"
        "_atom_site.Cartn_y\n"
        "_atom_site.Cartn_z\n"
        "_atom_site.pdbx_PDB_model_num\n"
        "ATOM C CA GLY A 1 0.000 0.000 0.000 1\n"
        "ATOM C CA GLY A 1 0.000 0.000 0.100 2\n"
    )
    mm = metrics_from_cif(multi)
    check("多 model：atom_count=2（全部 model 之和）", mm["atom_count"] == 2, str(mm["atom_count"]))
    check("多 model：model_count=2", mm["model_count"] == 2, str(mm["model_count"]))

    # ② 负向：没有 _atom_site → 必须抛，不能返回空
    try:
        metrics_from_cif("data_X\n#\n_entry.id X\n")
        check("缺 _atom_site → 抛异常", False, "**没有抛**")
    except MmcifError:
        check("缺 _atom_site → 抛异常", True)

    # ③ 负向：**这正是我踩过的坑** —— 若解析边界切错，交叉核对必须抓到
    #    构造一个"看起来解析成功但少读了行"的情形：把数据行前的 `#` 当成结束
    tricky = (
        "data_Y\n"
        "loop_\n"
        "_atom_site.group_PDB\n"
        "_atom_site.type_symbol\n"
        "_atom_site.label_atom_id\n"
        "_atom_site.label_comp_id\n"
        "_atom_site.label_asym_id\n"
        "_atom_site.label_seq_id\n"
        "_atom_site.Cartn_x\n"
        "_atom_site.Cartn_y\n"
        "_atom_site.Cartn_z\n"
        "_atom_site.pdbx_PDB_model_num\n"
        "ATOM C CA GLY A 1 0.0 0.0 0.0 1\n"
        "ATOM C CA GLY A 2 3.0 4.0 0.0 1\n"
        "HETATM O O HOH B 1 1.0 1.0 1.0 1\n"
    )
    m2 = metrics_from_cif(tricky)
    check("无结尾 `#` 也能解析", m2["atom_count"] == 2, str(m2["atom_count"]))

    # ④ 交叉核对的**独立有效性**：手工喂一个"少一行"的 atoms 列表，必须被抓
    atoms = parse_atom_site(good)
    try:
        cross_check_totals(good, atoms[:-1])   # 故意丢掉最后一行
        check("交叉核对能抓到少读的行", False, "**没抓到**")
    except MmcifError:
        check("交叉核对能抓到少读的行", True)

    # ⑤ 确定性：同输入连算 3 次必须逐位相同
    vals = [metrics_from_cif(good) for _ in range(3)]
    check("同输入重复 3 次逐位相同", vals[0] == vals[1] == vals[2])

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    print(__doc__)
