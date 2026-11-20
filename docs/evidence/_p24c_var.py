"""P24 ③ 句长变异：先比措辞，再改代码。

只回答一个问题：往 prompt 末尾追加哪句话，能让「句长变异系数」从 0.09 往上走，
同时不把 chars / echo / concrete 打回去。真实 key、温度 0.7、每人设 6 句。

用法：python docs/evidence/_p24c_var.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ.setdefault("DATA_DIR", str(ROOT / "data" / "memory"))
os.environ.setdefault("LOG_DIR", str(ROOT / "data" / "logs"))
os.environ["MOCK_LLM"] = "0"

import agent      # noqa: E402
import orchestrator  # noqa: E402
import roles      # noqa: E402
import style      # noqa: E402
import style_fingerprint as fp  # noqa: E402

# style_fingerprint.main() 才把这三个模块挂成自己的全局；直接 import 时要自己挂。
fp.roles, fp.orchestrator, fp.style = roles, orchestrator, style

VARIANTS = {
    "base-现有节奏句": "",
    "vA-接原词": "\n（后面那句要用上对方刚说的那个词。）",
    "vB-具体物": "\n（后面那句要带上一样具体的东西：一个时间、一个动作、或一样东西。）",
}

_orig = agent.build_system_prompt
current = {"suffix": ""}


def patched(*args, **kwargs):
    return _orig(*args, **kwargs) + current["suffix"]


agent.build_system_prompt = patched

for name, suffix in VARIANTS.items():
    current["suffix"] = suffix
    data = fp.collect(mock=False)
    out = fp.summarize(data["samples"])
    print(f"\n=== {name} ===")
    print({k: out.get(k) for k in
           ("n", "chars", "sent_mean", "sent_cv", "q_end", "stale", "echo", "concrete")})
    for row in data["samples"][:10]:
        print(f"  {row['persona'][:12]:<13} {row['user'][:10]} -> {row['reply'][:40]}")
