"""_probe_s20.py — AppTest 验证 lore 进 prompt、同会话第 4 轮起不再注入（MOCK）。"""
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ["MOCK_LLM"] = "1"

import agent
import logger
import memory

memory.DATA_DIR = pathlib.Path(tempfile.mkdtemp())
logger.LOG_DIR = pathlib.Path(tempfile.mkdtemp())

gen_prompts: list[str] = []
calls: list[str] = []


def fake(messages, temperature=0.7):
    head = messages[0]["content"]
    if head == agent.REVIEW_SYS:                 # S14 复核：干净句直接放行
        calls.append("review")
        return {"text": '{"pass": true, "reason": ""}', "ok": True,
                "latency_ms": 1, "degraded": False}
    if head == agent.REWRITE_SYS:
        calls.append("rewrite")
        return {"text": "我在，慢慢说。", "ok": True, "latency_ms": 1, "degraded": False}
    calls.append("gen")
    gen_prompts.append(head)
    return {"text": "听起来考试这件事压得你有点喘不过气。", "ok": True,
            "latency_ms": 1, "degraded": False}


agent.call_llm = fake

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
at.run()
for _ in range(4):
    at.chat_input[0].set_value("快考试了，有点慌").run()

print("exceptions:", len(at.exception))
print("calls:", calls)
for i, prompt in enumerate(gen_prompts, 1):
    print(i, "has_lore:", "补考或重修" in prompt, "bg_lines:", prompt.count("背景（"))
print("4th_gen_has_lore:", "补考或重修" in gen_prompts[-1])
print("messages:", len(at.chat_message))