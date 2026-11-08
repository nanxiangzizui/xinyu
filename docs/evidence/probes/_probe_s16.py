# -*- coding: utf-8 -*-
"""S16 证据探针：3 次真实 L2 → 第 3 轮聚合升 L3 短路；随后平静句回到地板 L2。"""
import io, json, os, sys, tempfile, pathlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
os.environ["MOCK_LLM"] = "1"
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

tmp = pathlib.Path(tempfile.mkdtemp())
import memory, logger, agent
from guardian import CRISIS_REPLY
memory.DATA_DIR = tmp / "mem"
logger.LOG_DIR = tmp / "logs"

calls = []


def fake(messages, temperature=0.7):
    head = messages[0]["content"]
    kind = ("review" if head == agent.REVIEW_SYS
            else "rewrite" if head == agent.REWRITE_SYS else "gen")
    calls.append((kind, temperature))
    text = {"gen": "我听着呢。", "review": '{"pass": true, "reason": ""}',
            "rewrite": "不该用到"}[kind]
    return {"text": text, "ok": True, "error": "", "latency_ms": 0}


agent.call_llm = fake
from streamlit.testing.v1 import AppTest

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
turns = ["没意思", "没意思", "没意思", "今天吃什么", "今天吃什么", "今天吃什么"]
for i, text in enumerate(turns, 1):
    calls.clear()
    at.chat_input[0].set_value(text).run()
    rows = [json.loads(l) for f in (tmp / "logs").glob("*.jsonl")
            for l in f.read_text(encoding="utf-8").splitlines()]
    row = rows[-1] if rows else {}
    sent = at.session_state["messages"][-1]["content"]
    print(f"第{i}轮 {text!r}")
    print("  exceptions:", len(at.exception), "| calls:", calls)
    print("  level/action/role:", row.get("level"), row.get("action"), row.get("role"),
          "| reason:", at.session_state.get("last_reason"))
    print("  rule_ids:", row.get("rule_ids"), "| levels 窗口:", at.session_state.get("levels"))
    print("  发的是危机模板:", sent == CRISIS_REPLY, "| 资源卡:", len(at.info))
print("最终 exceptions:", len(at.exception))
