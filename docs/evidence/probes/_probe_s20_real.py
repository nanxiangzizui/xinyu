"""_probe_s20_real.py — 真实 DeepSeek：lore 是否被自然带出（对比两个 persona）。"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.pop("MOCK_LLM", None)

import agent
from agent import build_system_prompt, call_llm
from memory import match_lore

CASES = [
    ("sister_heart", "挂科了怎么办", ("补考", "重修", "教务")),
    ("rational_mentor", "挂科了怎么办", ("补考", "重修", "教务")),
    ("rational_mentor", "宿舍跟室友闹矛盾了", ("辅导员", "宿管")),
]
out: list[str] = []
for i, (pid, text, keys) in enumerate(CASES, 1):
    lore = match_lore(text, f"probe_s20_real_{i}_{pid}")
    prompt = build_system_prompt(pid, {}, lore)
    resp = call_llm([{"role": "system", "content": prompt}, {"role": "user", "content": text}])
    reply = resp.get("text", "")
    out.append(f"[{i}] persona={pid} input={text}")
    out.append(f"    lore={lore}")
    out.append(f"    ok={resp.get('ok')} ms={resp.get('latency_ms')} len={len(reply)} "
               f"mentions_fact={any(k in reply for k in keys)}")
    out.append(f"    reply={reply}")

out.append(f"mock={agent._is_mock()}")
pathlib.Path(ROOT / "docs/evidence/probes/_probe_s20_real.out.txt").write_text(
    "\n".join(out), encoding="utf-8")
print("written")
