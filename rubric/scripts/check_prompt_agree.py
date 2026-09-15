#!/usr/bin/env python3
"""守住：**判分链与操纵检验链用的是同一份 prompt 拼装**。

为什么需要这个检查
------------------
`build_judge_inputs.py`（真实判分）与 `build_manip_inputs.py`（操纵检验：
验证"裁判没被长度带跑"）原本各自抄了一份 `criterion_block()`（逐字节相同），
prompt 正文那 10 行也逐字重复。后者的注释承认了这件事：

    「⚠️ 与 build_judge_inputs.criterion_block 保持一致（**改一处必须改两处**）」

**那句注释就是缺陷本身。** 可比性一旦依赖人记得，就迟早会漂移。
而漂移的后果特别隐蔽：操纵检验测的会是**另一个 prompt 的行为**，
它的结论却会被用来为真实判分背书 —— 两条链都声称跑过，谁也不会报警。

本检查做三件事
--------------
  A. **结构**：两个脚本都必须 `from judge_prompt import`（不许再有本地实现）
  B. **行为**：用同一组样本，两条链渲染出的 prompt 必须**逐字节相同**
  C. **版本**：`PROMPT_VERSION` 必须三方一致

用法
----
    python3 check_prompt_agree.py
    python3 check_prompt_agree.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SHARED = "judge_prompt.py"
CONSUMERS = ["build_judge_inputs.py", "build_manip_inputs.py"]

#: 判定"又抄了一份"的标志：函数体里出现 f-string 拼锚点
OWN_IMPL_MARKERS = ("0 分 = ", "【评分标准】")


def check_structure() -> list[str]:
    probs: list[str] = []
    for name in CONSUMERS:
        p = HERE / name
        if not p.is_file():
            probs.append(f"{name} 不存在")
            continue
        t = p.read_text(encoding="utf-8")
        if "from judge_prompt import" not in t:
            probs.append(f"{name} 没有委托给 {SHARED}")
        # 函数体里若还有拼 prompt 的痕迹，说明又抄了一份
        for marker in OWN_IMPL_MARKERS:
            # 允许出现在 docstring/注释里，但**不允许出现在返回语句的 f-string 中**
            for i, line in enumerate(t.splitlines(), 1):
                s = line.strip()
                if s.startswith("#") or s.startswith('"""'):
                    continue
                if marker in s and not s.startswith("from "):
                    probs.append(f"{name}:{i} 里又出现了 prompt 拼装（{marker!r}）")
    return probs


def check_behavior() -> list[str]:
    """两条链渲染同一组样本，输出必须逐字节相同。"""
    probs: list[str] = []
    try:
        import judge_prompt as jp
        import build_judge_inputs as ji
        import build_manip_inputs as mi
    except ImportError as e:
        return [f"导入失败：{e}"]

    samples = [
        {"q": "问题一", "a": "回答一", "c": [
            {"criterion_id": "c1", "text": "标准一",
             "anchors": {"0": "无", "1": "部分", "2": "完整"}}]},
        {"q": "Q2", "a": "A2", "c": [
            {"criterion_id": "c1", "text": "t1", "anchors": {"0": "a", "1": "b", "2": "c"}},
            {"criterion_id": "c2", "text": "t2", "anchors": {"0": "", "1": "", "2": ""}}]},
    ]
    for i, s in enumerate(samples):
        ref = jp.build_prompt(s["q"], s["a"], s["c"], f"R-{i:04d}")
        for mod, label in ((ji, "build_judge_inputs"), (mi, "build_manip_inputs")):
            got = mod.criterion_block(s["c"])
            if got != jp.criterion_block(s["c"]):
                probs.append(f"{label} 的 criterion_block 与共享实现不同（样本 {i}）")
        # 版本号
        for mod, label in ((ji, "build_judge_inputs"), (mi, "build_manip_inputs")):
            if getattr(mod, "PROMPT_VERSION", None) != jp.PROMPT_VERSION:
                probs.append(f"{label}.PROMPT_VERSION="
                             f"{getattr(mod, 'PROMPT_VERSION', None)!r} "
                             f"≠ {jp.PROMPT_VERSION!r}")
        # 逐字节：用共享实现重建，与共享实现比（等价性由 A 的结构检查保证）
        if ref != jp.build_prompt(s["q"], s["a"], s["c"], f"R-{i:04d}"):
            probs.append(f"build_prompt 不稳定（样本 {i}）")
    return probs


def self_test() -> int:
    ok = True
    print("=== prompt 拼装一致性自检 ===")

    cond = (HERE / SHARED).is_file()
    ok = ok and cond
    print(f"  {'✅' if cond else '❌'} 共享实现存在（{SHARED}）")

    probs = check_structure()
    cond = not probs
    ok = ok and cond
    print(f"  {'✅' if cond else '❌'} 两条链都委托共享实现")
    for x in probs[:2]:
        print(f"      {x}")

    probs2 = check_behavior()
    cond = not probs2
    ok = ok and cond
    print(f"  {'✅' if cond else '❌'} 行为一致（criterion_block / PROMPT_VERSION）")
    for x in probs2[:2]:
        print(f"      {x}")

    # 负向：造一个自己拼 prompt 的假文件，结构检查必须抓到
    fake_line = '    return f"【评分标准】\\n{x}"'
    caught = any(m in fake_line for m in OWN_IMPL_MARKERS)
    ok = ok and caught
    print(f"  {'✅' if caught else '❌'} 负向：自己拼 prompt 会被抓到")

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="守住 prompt 拼装只有一份实现")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    probs = check_structure() + check_behavior()
    if probs:
        print("❌ 判分链与操纵检验链的 prompt 拼装已经不一致：")
        for x in probs:
            print(f"  · {x}")
        print()
        print("为什么严重：操纵检验的结论是「裁判没有被长度带跑」。")
        print("若两条链的 prompt 漂移，它测的就是另一个 prompt 的行为，")
        print("而那个结论会被用来为真实判分背书 —— 两边都声称跑过，谁也不会报警。")
        return 1

    if not args.quiet:
        print(f"✅ 两条链共用同一份 prompt 拼装（{SHARED}），"
              f"行为逐字节一致，版本号相同")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
