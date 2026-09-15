"""造一份**合法**与几份**故意有问题**的提交，验证 verify_submission.py 真的会拒绝。

一个从不拒绝的校验器等于没有校验器。这里覆盖四类问题：
  1. 分数与逐类结果对不上（改过分数）
  2. manifest_hash 与本仓库锁定的不一致（换了数据）
  3. 缺 image_digest（别人无法复现）
  4. 运行时长超预算
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # bio-eval/
V = HERE / "verify_submission.py"

man = ROOT / "tasks" / "T1" / "_data" / "manifest.json"
if not man.is_file():
    print("SKIP: 缺 T1 manifest")
    sys.exit(0)
good_hash = hashlib.sha256(man.read_bytes()).hexdigest()

base = {
    "task_id": "T1",
    "submitter": "selftest",
    "model": "selftest-model",
    "result": {
        "task_id": "T1", "status": "ok", "score": 0.84655,
        "metric": "macro_f1_snp_indel",
        "image_digest": "sha256:c33862bb7ba588e42f98a52bd8b6a3be0df3a120fc081a9acfcd7e90e6f04e1e",
        "manifest_hash": good_hash,
        "wall_clock_sec": 55,
        "per_type": {"snps": {"f1": 0.9087}, "indels": {"f1": 0.7844}},
        "problems": [],
    },
}

cases = [("合法提交（应当通过）", base, True)]

import copy
c = copy.deepcopy(base); c["result"]["score"] = 0.99
cases.append(("分数与逐类结果对不上", c, False))

c = copy.deepcopy(base); c["result"]["manifest_hash"] = "0" * 64
cases.append(("manifest_hash 不一致（换了数据）", c, False))

c = copy.deepcopy(base); c["result"]["image_digest"] = "unknown"
cases.append(("缺 image_digest", c, False))

c = copy.deepcopy(base); c["result"]["wall_clock_sec"] = 99999
cases.append(("运行超预算", c, False))

ok_all = True
for label, payload, want_pass in cases:
    f = HERE / "_selftest_submission.json"
    f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    r = subprocess.run([sys.executable, str(V), "--submission", str(f), "--task", "T1"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    passed = r.returncode == 0
    good = passed == want_pass
    ok_all = ok_all and good
    print(f"{'✅' if good else '❌'} {label} → 退出码 {r.returncode}"
          f"（期望{'通过' if want_pass else '拒绝'}）")
    if not good:
        for line in ((r.stdout or "") + (r.stderr or "")).splitlines():
            if "❌" in line:
                print("      " + line.strip()[:110])
f.unlink(missing_ok=True)

print()
if ok_all:
    print("✅ 负向测试通过：校验器既接受合法提交，也拒绝四类问题")
else:
    print("❌ 负向测试失败")
sys.exit(0 if ok_all else 1)
