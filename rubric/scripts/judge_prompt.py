#!/usr/bin/env python3
"""**judge 提示词的拼装** —— 唯一实现。

为什么必须只有一份
------------------
判官链与操纵检验链各自拼装同一段 prompt 文本：

    build_judge_inputs.py   给「裁判打分」造输入
    build_manip_inputs.py   给「操纵检验」造输入（验证结论不是被长度带跑的）

两处的 `criterion_block()` **逐字节相同**，而且 prompt 正文那 10 行
（【问题】/【待评的回答】/【评分标准】/【输出要求】）也**逐字重复**。
`build_manip_inputs.py` 里甚至留着一句注释承认这件事：

    「⚠️ 与 build_judge_inputs.criterion_block 保持一致（改一处必须改两处）」

**"改一处必须改两处"就是缺陷本身，不是提醒。** 它依赖人记得。

为什么危险：操纵检验的结论是"裁判没有被长度带跑"。
如果两条链的 prompt 漂移了，操纵检验测的就是**另一个 prompt 的行为**，
而它的结论会被用来为真实判分背书 —— 两边都声称跑过，谁也不会报警。

本模块只做一件事：把 (题面, 回答, 标准) 拼成与 `judge_prompt_v1.md` 一致的文本。
两条链**必须**都调它，这样"可比性"由代码保证，而不由注释保证。
"""

from __future__ import annotations

#: 与 `judge_prompt_v1.md` 的版本号绑在一起。
#: ⚠️ 改动本文件的排版**必须**同时升这个版本号 ——
#:    否则旧结果与新结果会被当成同一版 prompt 比较。
PROMPT_VERSION = "judge_prompt_v1.0"


def criterion_block(criteria: list[dict]) -> str:
    """把若干条标准（含 0/1/2 锚点）拼成 prompt 里的一段。"""
    parts = []
    for c in criteria:
        a = c.get("anchors") or {}
        parts.append(
            f"{c['criterion_id']}. {c.get('text','')}\n"
            f"  0 分 = {a.get('0','')}\n"
            f"  1 分 = {a.get('1','')}\n"
            f"  2 分 = {a.get('2','')}"
        )
    return "\n\n".join(parts)


def build_prompt(question: str, answer: str, criteria: list[dict], item_id: str) -> str:
    """拼出完整 prompt。**两条链必须都走这里。**

    `item_id` 与 `criterion_ids` 会写进【输出要求】——
    它们是裁判输出能被机器解析回去的前提（少一个就解析不了）。
    """
    return (
        "【问题】\n"
        f"{question}\n\n"
        "【待评的回答】\n"
        f"{answer}\n\n"
        "【评分标准】\n"
        f"{criterion_block(criteria)}\n\n"
        f"【输出要求】只输出 JSON，item_id 必须是 {item_id}，"
        f"criteria 必须且只能包含 {[c['criterion_id'] for c in criteria]}"
    )
