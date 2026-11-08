# -*- coding: utf-8 -*-
"""S17 补充探针：首次 L3 立即留档，且不调任何模型（断网也能出卡）。"""
import io, json, os, sys, tempfile, pathlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
os.environ["MOCK_LLM"] = "1"
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

tmp = pathlib.Path(tempfile.mkdtemp())
import memory, logger, agent
memory.DATA_DIR = tmp / "mem"
logger.LOG_DIR = tmp / "logs"
calls = []


def fake(messages, temperature=0.7):
    calls.append(temperature)
    return {"text": "x", "ok": True, "error": "", "latency_ms": 0}


agent.call_llm = fake
memory.call_llm = fake
from streamlit.testing.v1 import AppTest
from guardian import CRISIS_REPLY

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
calls.clear()
at.chat_input[0].set_value("我不想活了").run()
rows = [json.loads(l) for f in (tmp / "logs").glob("*.jsonl")
        for l in f.read_text(encoding="utf-8").splitlines()]
mem = memory.read_memory(next((tmp / "mem").glob("*.json")).stem)
print("assistant 文案 == CRISIS_REPLY:", at.session_state["messages"][-1]["content"] == CRISIS_REPLY)
print("非摘要调用次数:", len(calls), "（应为 0）")
for r in rows:
    print("日志:", {k: r.get(k) for k in ("turn", "level", "role", "rule_ids", "action")})
print("资源卡:", len(at.info), "| summary_at_turn:", mem["summary_at_turn"])
print("摘要:", mem["rolling_summary"])
print("exceptions:", len(at.exception))
