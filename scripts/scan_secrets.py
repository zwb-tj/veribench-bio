"""GitHub 发布前的**密钥/隐私**扫描。

为什么这是发布前第一优先级
--------------------------
推到 GitHub 之后，**历史是不可撤销的**：即使随后删除，内容仍留在 reflog /
fork / 缓存里。本项目这一轮已经反复讲"不可撤销的操作要在动手前建检查"，
而"把 token 推上公开仓库"是典型的一类。

本扫描查三类：
  A. **凭据**：HF token（`hf_…`）、GitHub PAT（`ghp_…`）、AWS key、
     Slack token、私钥块（`-----BEGIN … PRIVATE KEY-----`）、
     以及 `token = "…"` / `password = "…"` 这类赋值形态
  B. **本机绝对路径**：`D:\\software\\DeepSeek Harness` 之类 —— 它泄露
     作者的用户名/目录结构，而且让文档里抄来的命令在别人机器上跑不通
  C. **邮箱 / 用户名**：真实邮箱等（本机路径里也常含用户名）

用法
----
    python3 scan_secrets.py                 # 扫"会被提交的文件"
    python3 scan_secrets.py --self-test     # 负向测试：注入假 token 必须被抓到
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: 只扫文本类文件；跳过二进制（图片/压缩包）以免误报
TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".jsonl", ".sh", ".ps1", ".txt", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".csv", ".tsv", ".html", ".js", ".ts", ".c", ".h",
    ".gitignore", ".dockerignore", ".fai", ".bed",
}

#: 单个文件超过这个大小就跳过（避免把 32 MB 的上游数据当文本扫）
MAX_BYTES = 4 * 1024 * 1024

#: A. 凭据模式。每条都是"确定是密钥"或"极可能是密钥"。
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("HuggingFace token", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b")),
    ("GitHub PAT (classic)", re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")),
    ("GitHub PAT (fine-grained)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("GitHub OAuth/App", re.compile(r"\b(gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b")),
    ("AWS access key id", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    # 赋值形态：`token = "…"` —— 只有值看起来像真密钥（长度够）才报
    ("疑似硬编码凭据赋值",
     re.compile(r"""(?i)\b(api[_-]?key|token|password|passwd|secret)\s*[:=]\s*["']([^"'\s]{16,})["']""")),
]

#: 本机绝对路径（含用户名 / 私有目录结构）
LOCAL_PATH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Windows 用户目录绝对路径", re.compile(r"[A-Za-z]:\\\\?Users\\\\?[A-Za-z0-9._\-]+")),
    ("本项目绝对路径", re.compile(r"[A-Za-z]:\\\\?software\\\\?DeepSeek Harness")),
]

#: 扫描时**跳过的文件**：本文件自己。
#: 理由：它里面写着上面那些 pattern 的**示例字符串**（用于 --self-test 与文档），
#: 若不跳过，全仓扫描会把"检查器的定义"报成"仓库里有本机路径"。
#: **检查器不能把自己变成假警报源** —— 假警报会训练人忽略真警报。
SELF_SKIP = {"scripts/scan_secrets.py"}

#: 邮箱（排除示例用的保留域名，以及**上游发布的联系邮箱** ——
#: 那些是我们引用别人文档时带进来的，不是作者的个人信息）
EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
ALLOWED_EMAIL_DOMAINS = (
    "example.com", "example.org", "users.noreply.github.com",
    "noreply", "email.com",
    # 上游机构的公开联系邮箱（出现在我们引用的第三方文档里）
    "broadinstitute.org", "ncbi.nlm.nih.gov", "nih.gov", "genome.network",
)


def publishable() -> list[Path]:
    """复用 `not_published.json` —— **不另写一份过滤逻辑**（本项目的老毛病）。"""
    man = json.loads((HERE / "not_published.json").read_text(encoding="utf-8"))
    dirs = set(man.get("dirs") or {})
    suffixes = set(man.get("suffixes") or [])
    names = set(man.get("names") or [])
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(part in names for part in p.parts):
            continue
        if p.suffix in suffixes:
            continue
        if any(rel == d or rel.startswith(d + "/") for d in dirs):
            continue
        if ".git" in p.parts:
            continue
        if p.relative_to(ROOT).as_posix() in SELF_SKIP:
            continue
        out.append(p)
    return sorted(out)


def _scan_text(text: str, rel: str) -> list[str]:
    hits: list[str] = []
    for label, pat in SECRET_PATTERNS:
        for m in pat.finditer(text):
            frag = m.group(0)
            # 赋值形态：把捕获到的值再确认一次长度，并允许占位符
            if "赋值" in label:
                val = m.group(2)
                if re.fullmatch(r"(?i)(your|xxx+|placeholder|<.*>|\*+|changeme|"
                                r"\.\.\.|redacted|dummy|fake|sample|test|example).*", val):
                    continue
            line = text[:m.start()].count("\n") + 1
            hits.append(f"{rel}:{line} [{label}] {frag[:24]}…")
    return hits


def scan(files: list[Path] | None = None, *, include_local_paths: bool = True
         ) -> tuple[list[str], list[str], list[str]]:
    """返回 (密钥命中, 本机路径命中, 邮箱命中)。"""
    files = files if files is not None else publishable()
    secrets: list[str] = []
    paths: list[str] = []
    emails: list[str] = []
    for p in files:
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in (
                    ".gitignore", ".dockerignore"):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        rel = p.relative_to(ROOT).as_posix() if ROOT in p.parents else str(p)
        secrets += _scan_text(text, rel)
        if include_local_paths:
            for label, pat in LOCAL_PATH_PATTERNS:
                for m in pat.finditer(text):
                    line = text[:m.start()].count("\n") + 1
                    paths.append(f"{rel}:{line} [{label}] {m.group(0)[:40]}")
        for m in EMAIL.finditer(text):
            dom = m.group(0).split("@", 1)[1].lower()
            if not any(a in dom for a in ALLOWED_EMAIL_DOMAINS):
                line = text[:m.start()].count("\n") + 1
                emails.append(f"{rel}:{line} {m.group(0)}")
    return secrets, paths, emails


def self_test() -> int:
    """负向测试：把各种**假 token** 放进临时文件，必须全部被抓到。

    ⚠️ 样本**在运行时拼接**，不写字面量。
    第一版把 `hf_ABCDEF…` 等假 token 直接写在本文件里 ——
    于是 `scan_secrets.py` **自己**成了扫描对象里的"6 处凭据"，
    每次全仓扫描都报"不要 push"。**检查器不能把自己变成假警报源**：
    假警报会训练人忽略真警报（本项目已反复吃到这个教训）。
    """
    import tempfile

    #: 用拼接绕开"字面量出现在本文件里"（`_` 分隔，扫描时不会命中）
    H = "hf_" + "A" * 36
    G = "ghp_" + "B" * 36
    A = "AKIA" + "C" * 16
    PK = "-----BEGIN RSA " + "PRIVATE KEY-----"

    SAMPLES = [
        ("HuggingFace token", f'token = "{H}"'),
        ("GitHub PAT", f"https://{G}@github.com/x/y"),
        ("AWS key", f'aws_access_key_id = "{A}"'),
        ("private key", PK + "\nMIIabc"),
        ("generic assignment", 'api_key: "' + "s3cr3tV4lueThatIsLongEnough" + '"'),
        ("local path", "cd " + '"' + "D:" + chr(92) + "software" + chr(92)
         + "DeepSeek Harness" + chr(92) + 'bio-eval"'),
    ]
    tmp = Path(tempfile.mkdtemp(prefix="secret-scan-"))
    ok = True
    try:
        for label, content in SAMPLES:
            f = tmp / f"{abs(hash(label))}.txt"
            f.write_text(content, encoding="utf-8")
            s, p, _ = scan([f])
            caught = bool(s or p)
            ok = ok and caught
            which = "密钥" if s else ("本机路径" if p else "**没抓到**")
            print(f"  {'✅' if caught else '❌'} {label:22} → {which}")

        # 反向：**合法内容不能被误报**（否则检查会被忽略）
        CLEAN = [
            "license = 'CC0-1.0'",
            "token 长度为 0 表示未设置",
            "hf auth login   # 会提示粘贴 token",
            "password = 'your-password-here'",
            "https://huggingface.co/settings/tokens",
            "see docs/DATACARD.md §5",
        ]
        for content in CLEAN:
            f = tmp / f"clean{abs(hash(content))}.txt"
            f.write_text(content, encoding="utf-8")
            s, p, e = scan([f], include_local_paths=True)
            clean = not (s or p or e)
            ok = ok and clean
            print(f"  {'✅' if clean else '❌'} 不误报：{content[:46]!r}"
                  + ("" if clean else f"  → {s or p or e}"))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("负向测试 " + ("全部通过" if ok else "**有失败**"))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description="GitHub 发布前：密钥与本机路径扫描")
    ap.add_argument("--self-test", action="store_true", help="负向测试")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    files = publishable()
    print(f"扫描 {len(files)} 个会被提交的文本文件")
    secrets, paths, emails = scan(files)

    if secrets:
        print(f"\n❌ **{len(secrets)} 处疑似凭据** —— 绝不能推上 GitHub：")
        for h in secrets[:30]:
            print("   " + h)
    else:
        print("\n✅ 未发现任何凭据（HF token / PAT / AWS / 私钥 / 硬编码口令）")

    if paths:
        print(f"\n⚠️ {len(paths)} 处**本机绝对路径**（会泄露目录结构与用户名，"
              "且让文档里抄的命令在别人机器上跑不通）：")
        from collections import Counter
        by_file = Counter(h.split(":", 1)[0] for h in paths)
        for f, n in by_file.most_common(12):
            print(f"   {n:4} 处  {f}")
        if len(by_file) > 12:
            print(f"   … 另有 {len(by_file) - 12} 个文件")
    else:
        print("✅ 未发现本机绝对路径")

    if emails:
        print(f"\n⚠️ {len(emails)} 处邮箱：")
        for h in emails[:10]:
            print("   " + h)

    print()
    if secrets:
        print("❌ 有凭据 —— **不要 push**。清理后还要考虑历史（已提交过就要重写历史）。")
        return 1
    if paths:
        print("⚠️ 有本机路径 —— 不致命，但建议在发布前清理"
              "（它们让文档不可移植，并泄露作者目录）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
