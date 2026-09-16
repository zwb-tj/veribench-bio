#!/usr/bin/env python3
"""OBO 1.2 的最小确定性解析器 —— 只取 T4 需要的字段。

为什么不用 pronto / obonet / biopython
--------------------------------------
项目承诺**零第三方依赖**；而且 T4 的卖点是"真值可由原文确定性重算" ——
引入一个会随版本改变行为的库反而削弱这一点。

⚠️ **解析必须按 `[Term]` 块，且必须排除 `is_obsolete: true`。**
实测（2026-09）：`go-basic.obo` 有 **48,340 个 `[Term]` 块**，
其中 **38,092 个非 obsolete**（约 10,248 个是废弃项）。
把 obsolete 项当有效 term 会让题池规模高估 27%，且答案本身是错的。

`cross_check_totals()` 让这类错误喊出来：它用**独立于分块逻辑**的计数做裁判。
"""

from __future__ import annotations

import re
from collections import deque

#: 三个根（无 `is_a` 的 term）。它们的 `depth_to_root` = 0。
#: 实测确认，不是写死的假设 —— `find_roots()` 会重新推导并允许调用方核对。
KNOWN_ROOTS = ("GO:0003674", "GO:0005575", "GO:0008150")


class OboError(ValueError):
    """解析失败 —— 必须响亮，不能静默返回空结果。"""


def parse_terms(text: str) -> dict[str, dict]:
    """解析 `[Term]` 块，返回 {GO ID: {name, namespace, parents, is_obsolete}}。

    ⚠️ 返回**包含** obsolete 项（调用方可能想统计它们）；
    过滤由 `usable_terms()` 负责 —— 职责分开，避免"静默排除"。
    """
    if "[Term]" not in text:
        raise OboError("文件里没有 [Term] 段 —— 不是 OBO 本体？")

    terms: dict[str, dict] = {}
    # `[Term]` 之后到下一个以 `[` 开头的块（或 EOF）算一个块
    for chunk in text.split("\n[Term]")[1:]:
        end = chunk.find("\n[")
        if end != -1:
            chunk = chunk[:end]
        m = re.search(r"^id:\s*(GO:\d+)", chunk, re.M)
        if not m:
            # 没有 id 的 [Term] 块是坏数据 —— 不能静默跳过
            raise OboError(f"[Term] 块缺 id：{chunk[:80]!r}")
        tid = m.group(1)
        if tid in terms:
            raise OboError(f"重复的 term id: {tid}")
        name = re.search(r"^name:\s*(.+)$", chunk, re.M)
        ns = re.search(r"^namespace:\s*(\S+)", chunk, re.M)
        parents = sorted(re.findall(r"^is_a:\s*(GO:\d+)", chunk, re.M))
        obsolete = bool(re.search(r"^is_obsolete:\s*true", chunk, re.M))
        terms[tid] = {
            "name": name.group(1).strip() if name else None,
            "namespace": ns.group(1).strip() if ns else None,
            #: **排序**：让遍历顺序与文件里的书写顺序无关（确定性要求）
            "parents": parents,
            "is_obsolete": obsolete,
        }
    return terms


def usable_terms(terms: dict[str, dict]) -> dict[str, dict]:
    """排除 obsolete 项。**这是题池的真正来源。**"""
    return {k: v for k, v in terms.items() if not v["is_obsolete"]}


def cross_check_totals(text: str, terms: dict[str, dict]) -> None:
    """用**独立于分块逻辑**的判据核对条数。

    判据不共享解析假设：这里按 `id: GO:` 锚点扫全文，不分块、不看 `[Term]`。
    两者不一致说明解析边界错了 —— 抛异常。
    """
    n_anchor = len(re.findall(r"^id:\s*GO:\d+", text, re.M))
    if n_anchor != len(terms):
        raise OboError(
            f"分块解析得到 {len(terms)} 个 term，全文锚点计数为 {n_anchor} —— 解析边界错了")


def find_roots(terms: dict[str, dict]) -> list[str]:
    """返回无 `is_a` 的 **非 obsolete** term（排序，确定性）。

    ⚠️ **必须排除 obsolete。** 实测（2026-09）：不加过滤时有 **10,251 个**
    "无 `is_a`" 的项，其中 **10,248 个是 obsolete** —— 真实根只有 **3 个**
    （molecular_function / cellular_component / biological_process）。

    自检先抓到了这个 bug（合成夹具里 obsolete 项也被算成根），
    然后在真实文件上量出影响：**假根会把 depth_to_root 全部算错**
    （BFS 会把 obsolete 项当成到达点，深度立刻变小）。
    """
    return sorted(k for k, v in terms.items() if not v["parents"] and not v["is_obsolete"])


def depth_to_root(terms: dict[str, dict], start: str, roots: set[str]) -> int | None:
    """沿 `is_a` 向上到**任一根**的最短距离。根本身为 0；到不了返回 None。

    ⚠️ 用**显式队列**而非递归：38,092 个节点的链可能超过 Python 递归深度。
    ⚠️ 父节点**排序后**遍历：最短距离本身唯一，但排序让中间过程也与输入顺序无关。
    ⚠️ **不经过 obsolete 节点**：它们不是合法路由。
       （实测：有效 term 并不指向 obsolete 父节点，所以这是防御性检查，
         但若将来本体变了，这里会立刻发现而不是给出错误的短路径。）
    """
    if start not in terms:
        return None
    if start in roots:
        return 0
    seen = {start}
    q: deque[tuple[str, int]] = deque([(start, 0)])
    while q:
        cur, d = q.popleft()
        for p in terms[cur]["parents"]:      # 解析时已排序
            if p in roots:
                return d + 1
            if p in seen or p not in terms:
                continue
            if terms[p]["is_obsolete"]:
                # obsolete 节点不能作为到根的路径
                continue
            seen.add(p)
            q.append((p, d + 1))
    return None


def metrics_for(terms: dict[str, dict], gid: str, roots: set[str]) -> dict:
    """算 T4 的四个判分量（定义见 tasks/T4/DESIGN.md §3）。"""
    if gid not in terms:
        raise OboError(f"{gid} 不在本体里")
    t = terms[gid]
    if t["is_obsolete"]:
        # ⚠️ **必须报错**，不能静默给一个答案 —— obsolete 项不该出现在题池里
        raise OboError(f"{gid} 是 obsolete 项 —— 不应作为题目")
    d = depth_to_root(terms, gid, roots)
    if d is None:
        raise OboError(f"{gid} 沿 is_a 到不了任何根 —— 图不连通？")
    return {
        "name": t["name"],
        "namespace": t["namespace"],
        "direct_parent_count": len(t["parents"]),
        "depth_to_root": d,
    }


def self_test() -> int:
    """自检：**证明这些函数在坏输入上会失败**。"""
    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            ok = False
        print(f"  {'✅' if cond else '❌'} {label}" + (f"  {detail}" if detail else ""))

    print("=== obo_parse 自检 ===")

    # ① 最小合法本体：一条链 root ← mid ← leaf，外加一个 obsolete
    good = (
        "format-version: 1.2\n"
        "\n[Term]\n"
        "id: GO:0000001\n"
        "name: root term\n"
        "namespace: biological_process\n"
        "\n[Term]\n"
        "id: GO:0000002\n"
        "name: mid term\n"
        "namespace: biological_process\n"
        "is_a: GO:0000001 ! root term\n"
        "\n[Term]\n"
        "id: GO:0000003\n"
        "name: leaf term\n"
        "namespace: biological_process\n"
        "is_a: GO:0000002 ! mid term\n"
        "is_a: GO:0000001 ! root term\n"
        "\n[Term]\n"
        "id: GO:0000004\n"
        "name: obsolete thing\n"
        "namespace: biological_process\n"
        "is_obsolete: true\n"
    )
    terms = parse_terms(good)
    cross_check_totals(good, terms)
    check("解析出 4 个 term（含 obsolete）", len(terms) == 4, str(len(terms)))
    check("usable 为 3 个", len(usable_terms(terms)) == 3, str(len(usable_terms(terms))))
    roots = find_roots(terms)
    check("根只有 1 个", roots == ["GO:0000001"], str(roots))
    check("根 depth=0", depth_to_root(terms, "GO:0000001", set(roots)) == 0)
    check("mid depth=1", depth_to_root(terms, "GO:0000002", set(roots)) == 1)
    # leaf 有 2 个父：经 mid 是 2 步、经 root 是 1 步 → **取最短 = 1**
    check("leaf depth=1（走最短路径）",
          depth_to_root(terms, "GO:0000003", set(roots)) == 1,
          str(depth_to_root(terms, "GO:0000003", set(roots))))

    # ② 负向：缺 [Term] → 必须抛
    try:
        parse_terms("format-version: 1.2\n")
        check("无 [Term] → 抛异常", False, "**没有抛**")
    except OboError:
        check("无 [Term] → 抛异常", True)

    # ③ 负向：**obsolete 项必须报错，不能给答案**（这是题池正确性的关键）
    try:
        metrics_for(terms, "GO:0000004", set(roots))
        check("obsolete 项 → 抛异常", False, "**没有抛**")
    except OboError:
        check("obsolete 项 → 抛异常", True)

    # ④ 负向：交叉核对能抓到"少解析了"（模拟分块边界错误）
    try:
        cross_check_totals(good, dict(list(terms.items())[:2]))
        check("交叉核对能抓到少解析", False, "**没抓到**")
    except OboError:
        check("交叉核对能抓到少解析", True)

    # ⑤ 负向：重复 id
    dup = good + "\n[Term]\nid: GO:0000001\nname: dup\nnamespace: x\n"
    try:
        parse_terms(dup)
        check("重复 id → 抛异常", False, "**没有抛**")
    except OboError:
        check("重复 id → 抛异常", True)

    # ⑥ 确定性：同输入连算 3 次逐位相同
    vals = [metrics_for(parse_terms(good), "GO:0000003", set(find_roots(parse_terms(good))))
            for _ in range(3)]
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
