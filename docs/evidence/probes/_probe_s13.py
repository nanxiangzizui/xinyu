# -*- coding: utf-8 -*-
"""S13 证据探针：模型返回诊断句时，界面只能看到兜底句。"""
import io, json, os, sys, tempfile, pathlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
os.environ["MOCK_LLM"] = "1"

tmp = pathlib.Path(tempfile.mkdtemp())
import memory, logger, agent
memory.DATA_DIR = tmp / "mem"
logger.LOG_DIR = tmp / "logs"

BAD = "你这是抑郁症，建议服药。"
agent.call_llm = lambda messages, temperature=0.7: {
    "text": BAD, "ok": True, "error": "", "latency_ms": 0}

from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app.py", default_timeout=30).run()
at.chat_input[0].set_value("最近很难受").run()

print("exceptions:", len(at.exception))
msgs = at.session_state["messages"]
for m in msgs:
    print(m["role"], "->", repr(m["content"]))
sent = msgs[-1]["content"]
print("原文是否发出:", BAD in sent)
print("是否兜底:", sent.startswith("我在。你愿意说多少都可以"))
print("degraded:", at.session_state["degraded"])
logs = list((tmp / "logs").glob("*.jsonl"))
rows = [json.loads(l) for f in logs for l in f.read_text(encoding="utf-8").splitlines()]
print("日志:", rows)
print("日志含原文:", any(BAD in json.dumps(r, ensure_ascii=False) for r in rows))
# 第二条: 干净回复必须原样通过
agent.call_llm = lambda messages, temperature=0.7: {
    "text": "听起来今天挺耗人的。", "ok": True, "error": "", "latency_ms": 0}
at2 = AppTest.from_file("app.py", default_timeout=30).run()
at2.chat_input[0].set_value("今天有点累").run()
print("正常轮:", repr(at2.session_state["messages"][-1]["content"]))
print("exceptions2:", len(at2.exception))
