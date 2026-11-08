# -*- coding: utf-8 -*-
"""S17 证据探针：10 轮对话应压缩 2 次（第 5、10 轮），摘要无原句。"""
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
    head = messages[0]["content"]
    kind = ("review" if head == agent.REVIEW_SYS
            else "rewrite" if head == agent.REWRITE_SYS
            else "summary" if head == agent.SUMMARY_SYS else "gen")
    calls.append((kind, temperature))
    text = {"gen": "我听着呢。", "review": '{"pass": true, "reason": ""}',
            "rewrite": "我在。", "summary": agent.MOCK_SUMMARY_LINE}[kind]
    return {"text": text, "ok": True, "error": "", "latency_ms": 0}


agent.call_llm = fake
memory.call_llm = fake          # memory 是 from agent import call_llm，必须分开打补丁
from streamlit.testing.v1 import AppTest

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
turns = [f"第{i}轮，今天有点累" for i in range(1, 11)]
sid = ""
for i, text in enumerate(turns, 1):
    calls.clear()
    at.chat_input[0].set_value(text).run()
    sid = sid or next((tmp / "mem").glob("*.json")).stem
    rows = [json.loads(l) for f in (tmp / "logs").glob("*.jsonl")
            for l in f.read_text(encoding="utf-8").splitlines()]
    row = rows[-1] if rows else {}
    mem = memory.read_memory(sid)
    print(f"第{i}轮 exceptions={len(at.exception)} calls={calls} "
          f"action={row.get('action')} sat={mem['summary_at_turn']} "
          f"summary={mem['rolling_summary'][:24]!r}")
all_rows = [json.loads(l) for f in (tmp / "logs").glob("*.jsonl")
            for l in f.read_text(encoding="utf-8").splitlines()]
comp = [r for r in all_rows if r.get("action") == "summary_compress"]
mem = memory.read_memory(sid)
print("summary_compress 行数:", len(comp), "| 轮次:", [r["turn"] for r in comp])
print("rule_ids:", [r.get("rule_ids") for r in comp])
print("summary_at_turn:", mem["summary_at_turn"], "| 摘要长度:", len(mem["rolling_summary"]))
print("摘要含任意用户原句:", any(t in mem["rolling_summary"] for t in turns))
print("摘要 == MOCK:", mem["rolling_summary"] == agent.MOCK_SUMMARY_LINE)
print("最终 exceptions:", len(at.exception))
