#!/usr/bin/env python3
"""**统一的文本写入** —— 保证换行符与平台无关。

为什么需要这个模块
------------------
`Path.write_text()` / `open("w")` 默认 `newline=None`：Python 在 **Windows
把 `\\n` 翻成 `\\r\\n`、在 Linux 不翻**。于是**同一段代码在两平台产出不同字节**。

本项目实测到两种后果：

  ① **pin 在两平台结论相反**（T2/T3 的 `items.jsonl` 是镜像 pin 的构建输入）：
     CRLF 版 `400fe720…` vs LF 版 `be5da56d…`。
  ② **工作区被悄悄污染**：`.gitattributes` 要求 LF、HEAD 里也是 LF，
     但工作区被写成 CRLF 时 **`git status` 看不见**（`core.autocrlf=true`
     会在比较前归一化）。实测全仓曾有 **31 个已跟踪文件**处于这种状态，
     而 `record_image_digest.py` 正是在**工作区字节**上算 `source_sha256`。

为什么抽成模块而不是逐个加参数
------------------------------
实测：`rubric/scripts/` 下 **30 个脚本**都缺 `newline=""`。
逐个改 30 处等于把同一个约定抄 30 遍 —— **而本项目的教训正是
"抄多份的约定必然会漂移"**（见 `scripts/check_publishable_agree.py`
与 `rubric/scripts/check_prompt_agree.py` 的由来）。

所以这里提供两个函数，调用方改成它们即可：

    from textio import write_text, write_jsonl
    write_text(path, content)
    write_jsonl(path, rows)

⚠️ 本模块**不改变**调用方写出的**内容**，只固定换行符 ——
所以历史产物的内容不变，只是字节在不同平台上变得一致。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

#: 统一用 LF。`newline=""` 让 `\n` 原样写入（不做平台翻译）。
_NEWLINE = ""


def write_text(path: Path | str, content: str) -> None:
    """写文本，强制 LF。"""
    Path(path).write_text(content, encoding="utf-8", newline=_NEWLINE)


def read_text(path: Path | str) -> str:
    """读文本，**不做换行翻译**（与 write_text 对称，便于逐字节比对）。"""
    return Path(path).read_text(encoding="utf-8")


def write_jsonl(path: Path | str, rows: Iterable[dict]) -> None:
    """写 JSONL（每行一个对象 + 换行），强制 LF。"""
    Path(path).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8", newline=_NEWLINE)


def write_json(path: Path | str, obj, *, indent: int = 2) -> None:
    """写 JSON（带末尾换行），强制 LF。"""
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n",
                          encoding="utf-8", newline=_NEWLINE)


def self_test() -> int:
    """自检：**证明它真的写 LF**（而不是恰好在本机看起来对）。"""
    import sys
    import tempfile

    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            ok = False
        print(f"  {'✅' if cond else '❌'} {label}" + (f"  {detail}" if detail else ""))

    print("=== textio 自检 ===")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.txt"
        write_text(p, "x\ny\n")
        raw = p.read_bytes()
        check("write_text 写出纯 LF", raw.count(b"\r\n") == 0 and raw == b"x\ny\n",
              repr(raw))

        pj = Path(td) / "b.jsonl"
        write_jsonl(pj, [{"a": 1}, {"b": "中"}])
        rawj = pj.read_bytes()
        check("write_jsonl 写出纯 LF", rawj.count(b"\r\n") == 0,
              f"{rawj.count(b'\r\n')} 个 CRLF")
        check("write_jsonl 可被逐行解析",
              len([l for l in rawj.decode().splitlines() if l.strip()]) == 2)

        pn = Path(td) / "c.json"
        write_json(pn, {"k": "中"})
        check("write_json 写出纯 LF 且末尾有换行",
              pn.read_bytes().count(b"\r\n") == 0 and pn.read_bytes().endswith(b"\n"))

        check("read_text 不做翻译",
              read_text(p) == "x\ny\n", repr(read_text(p)))

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    print(__doc__)
