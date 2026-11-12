"""P4 冒烟（一次性脚本，可重跑）：门禁 / 来源 / 侧栏编排 / 默认开 loop / =0 回 v1。

跑法：& ./.venv/Scripts/python.exe docs/evidence/p4_smoke_2026-11-12.py
只用 MOCK_LLM=1 + 临时 DATA_DIR/LOG_DIR + 假 fetch，不碰仓库 data/，不联网，不含真人原文。
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TMP = pathlib.Path(tempfile.mkdtemp(prefix="p4smoke_"))
os.environ["MOCK_LLM"] = "1"
os.environ["ALLOW_WEB"] = "1"
os.environ.pop("AGENT_LOOP", None)        # 不设才是在验默认值 1
os.environ["WEB_API_KEY"] = "smoke-key"
os.environ["WEB_PROVIDER"] = "custom"
os.environ["DATA_DIR"] = str(TMP / "memory")
os.environ["LOG_DIR"] = str(TMP / "logs")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import agent_loop  # noqa: E402
import guardian  # noqa: E402
import logger as logmod  # noqa: E402
import memory  # noqa: E402
import orchestrator  # noqa: E402
import tools  # noqa: E402
import web  # noqa: E402

memory.DATA_DIR = TMP / "memory"
logmod.LOG_DIR = str(TMP / "logs")
assert orchestrator.AGENT_LOOP is True, "AGENT_LOOP 默认应为 1"

from streamlit.testing.v1 import AppTest  # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
assert not list(at.exception), list(at.exception)
at.chat_input[0].set_value("你好").run()
assert not list(at.exception), list(at.exception)
trace = at.session_state["last_trace"]
nodes = [n["node"] for n in trace]
print("日常 nodes:", nodes)
assert nodes == ["pre_check", "aggregate", "coordinator", "cooldown",
                 "lore", "prompt", "generate", "post_check", "memory_write"]
gen = trace[6]
print("generate:", json.dumps(gen, ensure_ascii=False))
assert gen["detail"] == "tools=0"
labels = [e.label for e in at.sidebar.expander]
assert "本轮编排" in labels, labels
assert any("tools=0" in m.value for m in at.sidebar.markdown)

at.chat_input[0].set_value("我不想活了").run()
assert not list(at.exception), list(at.exception)
l3_nodes = [n["node"] for n in at.session_state["last_trace"]]
print("L3 nodes:", l3_nodes)
assert l3_nodes == ["pre_check", "aggregate", "short_circuit"]
assert at.session_state["last_level"] == "L3"
assert at.info, "L3 资源卡缺失"

# 来源渲染：只读消息里的 sources，不解析正文链接。
at.session_state["messages"] = [{
    "role": "assistant", "content": "看看这个",
    "sources": [{"title": "来源甲", "url": "https://ok.example/x"}]}]
at.run()
assert not list(at.exception), list(at.exception)
main_md = [m.value for m in at.markdown]
assert any("[来源甲](https://ok.example/x)" in v for v in main_md), main_md[-5:]

# 真实工具链（假 fetch）：web_search → search_sources → AgentResult.sources。
tools.reset()
web.register_tools()

def fake_fetch(url, headers, timeout_s, body=None):
    payload = {"webPages": {"value": [
        {"name": "HTTP", "url": "http://a.example/x", "snippet": "bad"},
        {"name": "内网", "url": "https://10.0.0.1/x", "snippet": "bad"},
        {"name": "好", "url": "https://ok.example/x", "snippet": "P4QueryMark"}]}}
    return 200, json.dumps(payload).encode("utf-8")

web._fetch = fake_fetch
data, err = web.search("P4QueryMark")
assert not err and [i["url"] for i in data["items"]] == ["https://ok.example/x"]

def chat(messages, tool_list):
    if len(messages) == 1:
        return {"text": "", "ok": True, "tool_calls": [
            {"id": "c1", "name": "web_search", "arguments": {"query": "P4QueryMark"}}]}
    return {"text": "查到了", "ok": True, "tool_calls": []}

res = agent_loop.run_agent("sys", [], tools.list_for_turn("guide", "L1", allow_web=True),
                           chat=chat, gate=guardian.guardian_tool_check,
                           source_filter=web.search_sources)
print("agent:", res.ok, res.tool_calls, res.sources)
assert res.ok and res.tool_calls == 1
assert [s["url"] for s in res.sources] == ["https://ok.example/x"]

# 门禁第二道闸：L3/crisis 拒绝，且工具零执行。
ran = []
tools.reset()
tools.register(tools.ToolSpec("echo", "x", {}), lambda: ran.append(1) or {})
verdict = guardian.guardian_tool_check("echo", {}, role="crisis", level="L3")
print("gate:", verdict)
assert verdict == {"allow": False, "reason": "crisis_no_tool"} and ran == []

# trace / 日志都不含原句与 query。
blob = json.dumps(trace + at.session_state["last_trace"], ensure_ascii=False)
for marker in ("你好", "我不想活了", "P4QueryMark"):
    assert marker not in blob, f"trace 泄露：{marker}"
log_text = "\n".join(p.read_text(encoding="utf-8")
                     for p in (TMP / "logs").glob("*.jsonl"))
for marker in ("你好", "我不想活了", "P4QueryMark"):
    assert marker not in log_text, f"日志泄露：{marker}"

# AGENT_LOOP=0：回 v1 管线，generate 记 pipeline。
os.environ["AGENT_LOOP"] = "0"
orchestrator = importlib.reload(orchestrator)
assert orchestrator.AGENT_LOOP is False
old = orchestrator.handle("你好", "p4v1", [], "sister_heart", {})
old_gen = [n for n in old["trace"] if n["node"] == "generate"]
print("v1 generate:", json.dumps(old_gen, ensure_ascii=False))
assert old_gen and old_gen[0]["detail"] == "pipeline"
print("P4 SMOKE PASS")
