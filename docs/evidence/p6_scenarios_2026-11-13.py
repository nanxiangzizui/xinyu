"""P6 手工场景矩阵（一次性脚本，可重跑）。

跑法：& ./.venv/Scripts/python.exe docs/evidence/p6_scenarios_2026-11-13.py
只用 MOCK_LLM=1 + 临时 DATA_DIR/LOG_DIR + 假 fetch，不碰仓库 data/，不联网。
覆盖：L1/L2/L3、断网 L3、豁免、冷却、记忆脱敏、清空、超长输入、
AGENT_LOOP=0、错误 key、工具成功/失败、AppTest 侧栏与来源、五人设。
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TMP = pathlib.Path(tempfile.mkdtemp(prefix="p6smoke_"))
os.environ["MOCK_LLM"] = "1"
os.environ["ALLOW_WEB"] = "1"
os.environ["AGENT_LOOP"] = "1"
os.environ["WEB_API_KEY"] = "smoke-key"
os.environ["WEB_PROVIDER"] = "custom"
os.environ["DATA_DIR"] = str(TMP / "memory")
os.environ["LOG_DIR"] = str(TMP / "logs")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import agent  # noqa: E402
import agent_loop  # noqa: E402
import guardian  # noqa: E402
import logger as logmod  # noqa: E402
import memory  # noqa: E402
import orchestrator  # noqa: E402
import resources  # noqa: E402
import roles  # noqa: E402
import style  # noqa: E402
import tools  # noqa: E402
import web  # noqa: E402

memory.DATA_DIR = TMP / "memory"
logmod.LOG_DIR = str(TMP / "logs")
PASS = []


def ok(name: str) -> None:
    PASS.append(name)
    print("PASS", name)


def run(text: str, sid: str, state: dict | None = None, persona: str = "sister_heart") -> dict:
    return orchestrator.handle(text, sid, [], persona, {} if state is None else state)


def nodes(result: dict) -> list[str]:
    return [n["node"] for n in result["trace"]]


# 1 L1 日常
r = run("今天有点累", "p6-l1")
assert (r["level"], r["role"]) == ("L1", "listener")
assert nodes(r) == ["pre_check", "aggregate", "coordinator", "cooldown",
                    "lore", "prompt", "generate", "post_check", "memory_write"]
assert [n["node"] for n in r["trace"]][6] == "generate"
assert r["trace"][6]["detail"] == "tools=0"
assert r["reply"].endswith(style.STICKERS["sister_heart"])
ok("L1 日常：九节点 + L1 贴纸")

# 2 L2 资源卡
r = run("我觉得自己很没用", "p6-l2")
assert (r["level"], r["role"]) == ("L2", "listener")
assert len(resources.pick_resources("L2", r["trace"][0].get("detail", ""))) >= 2
assert "🌿" not in r["reply"]
ok("L2：资源卡 ≥2 + 不贴 L1 贴纸")

# 3 L3 联网
r = run("我不想活了", "p6-l3")
assert (r["level"], r["role"]) == ("L3", "crisis")
assert nodes(r) == ["pre_check", "aggregate", "short_circuit"]
assert r["reply"] == guardian.CRISIS_REPLY
assert len(resources.pick_resources("L3", [])) >= 2
ok("L3：短路三节点 + 危机模板 + 资源卡")

# 4 断网 L3：所有生成/网络路径都坏，仍然出模板
called = []
def boom(*args, **kwargs):
    called.append(1)
    raise TimeoutError("offline")

old_llm, old_chat = agent.call_llm, agent.chat_with_tools
old_loop, old_search = agent_loop.run_agent, web.search
agent.call_llm = boom
agent.chat_with_tools = boom
agent_loop.run_agent = boom
web.search = boom
try:
    r = run("我不想活了", "p6-offline")
finally:
    agent.call_llm, agent.chat_with_tools = old_llm, old_chat
    agent_loop.run_agent, web.search = old_loop, old_search
assert (r["level"], r["role"]) == ("L3", "crisis")
assert r["reply"] == guardian.CRISIS_REPLY and called == []
ok("断网 L3：生成/工具零调用，模板照出")

# 5 豁免：“不想死”不等于危机
r = run("我不想死，我想好好活着", "p6-exempt")
assert r["level"] != "L3" and r["role"] != "crisis"
ok(f"豁免：不想死 → {r['level']}/{r['role']}")

# 6 冷却：危机后同 session 续聊降为 listener + after_crisis
state = {}
first = run("我不想活了", "p6-cool", state)
second = run("我该怎么办", "p6-cool", state)
assert first["level"] == "L3"
assert (second["level"], second["role"], second["reason"]) == ("L2", "listener", "after_crisis")
ok("冷却：after_crisis → L2 listener")

# 7 记忆脱敏：人名/城市不进 memory.json
sid = "p6-mem"
run("我叫小A，在杭州上学", sid)
data = memory.read_memory(sid)
blob = json.dumps(data, ensure_ascii=False)
assert len(data) == 9 and "小A" not in blob and "杭州" not in blob, blob
ok("记忆：9 字段 + 人名/城市未落盘")

# 8 清空：正文/备份/临时文件都真删
run("今天有点累", sid)
path = memory._path(sid)
assert path.exists()
memory.clear_memory(sid)
assert not path.exists() and not path.with_suffix(".bak").exists()
assert memory.read_memory(sid)["rolling_summary"] == ""
ok("清空：主文件/备份删除，记忆回默认")

# 9 超长输入 5000 字不崩
r = orchestrator.safe_run("今天很累" * 1000, "p6-long", [], "sister_heart", {})
assert isinstance(r["reply"], str) and r["reply"] and r["level"] in ("L1", "L2", "L3")
ok("5000 字输入：不崩且有回复")

# 10 AGENT_LOOP=0：回 v1 生成管线
os.environ["AGENT_LOOP"] = "0"
orchestrator = importlib.reload(orchestrator)
r = orchestrator.handle("你好", "p6-v1", [], "sister_heart", {})
gen = [n for n in r["trace"] if n["node"] == "generate"]
assert gen and gen[0]["detail"] == "pipeline"
ok("AGENT_LOOP=0：generate=pipeline")
os.environ["AGENT_LOOP"] = "1"
orchestrator = importlib.reload(orchestrator)

# 11 错误 key：safe_run 兜底为 L2 + 模板，不抛异常
def bad_key(*args, **kwargs):
    raise RuntimeError("invalid api key")

old_llm, old_chat = agent.call_llm, agent.chat_with_tools
agent.call_llm = bad_key
agent.chat_with_tools = bad_key
try:
    r = orchestrator.safe_run("今天很累", "p6-key", [], "sister_heart", {})
finally:
    agent.call_llm, agent.chat_with_tools = old_llm, old_chat
assert (r["reply"], r["level"], r["role"], r["degraded"]) == (
    orchestrator.FALLBACK_LINE, "L2", "listener", True)
ok("错误 key：兜底 L2 + degraded，不抛到界面")

# 12 工具成功：web_search → 过滤 http/内网 → 来源渲染
tools.reset()
web.register_tools()

def fake_fetch(url, headers, timeout_s, body=None):
    payload = {"webPages": {"value": [
        {"name": "HTTP", "url": "http://a.example/x", "snippet": "bad"},
        {"name": "内网", "url": "https://10.0.0.1/x", "snippet": "bad"},
        {"name": "好", "url": "https://ok.example/x", "snippet": "P6QueryMark"}]}}
    return 200, json.dumps(payload).encode("utf-8")

web._fetch = fake_fetch
data, err = web.search("P6QueryMark")
assert not err and [i["url"] for i in data["items"]] == ["https://ok.example/x"]

def chat_success(messages, tool_list):
    if len(messages) == 1:
        return {"text": "", "ok": True, "tool_calls": [
            {"id": "c1", "name": "web_search", "arguments": {"query": "P6QueryMark"}}]}
    return {"text": "查到了", "ok": True, "tool_calls": []}

res = agent_loop.run_agent("sys", [], tools.list_for_turn("guide", "L1", allow_web=True),
                           chat=chat_success, gate=guardian.guardian_tool_check,
                           source_filter=web.search_sources)
assert res.ok and res.tool_calls == 1
assert [s["url"] for s in res.sources] == ["https://ok.example/x"]
ok("工具成功：一次调用 + 来源只留 https")

# 13 工具失败：超时后模型继续答，不把异常抛给界面
def timeout_fetch(url, headers, timeout_s, body=None):
    raise TimeoutError("timeout")

web._fetch = timeout_fetch
data, err = web.search("P6QueryMark")
assert data is None and err == "timeout"

def chat_failure(messages, tool_list):
    if len(messages) == 1:
        return {"text": "", "ok": True, "tool_calls": [
            {"id": "c1", "name": "web_search", "arguments": {"query": "P6QueryMark"}}]}
    return {"text": "没查到，但不耽误我陪你", "ok": True, "tool_calls": []}

res = agent_loop.run_agent("sys", [], tools.list_for_turn("guide", "L1", allow_web=True),
                           chat=chat_failure, gate=guardian.guardian_tool_check,
                           source_filter=web.search_sources)
assert res.ok and res.tool_calls == 1 and "没查到" in res.text
assert res.sources == []
ok("工具失败：timeout 被吞住，模型继续答")

# 14 五人设 × 3 轮：L1 贴纸各自正确，不串味
for persona in roles.PERSONAS:
    for text in ("今天有点累", "我在听", "你好"):
        r = run(text, f"p6-{persona}", persona=persona)
        assert r["level"] == "L1", (persona, text, r["level"])
        assert r["reply"].endswith(style.STICKERS[persona]), (persona, r["reply"])
ok("五人设：三轮均 L1 且贴纸正确")

# 15 AppTest：首屏 + 侧栏“本轮编排” + L3 资源卡 + 来源渲染
from streamlit.testing.v1 import AppTest  # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
assert not list(at.exception), list(at.exception)
at.chat_input[0].set_value("你好").run()
assert not list(at.exception), list(at.exception)
trace = at.session_state["last_trace"]
assert [n["node"] for n in trace] == [
    "pre_check", "aggregate", "coordinator", "cooldown", "lore",
    "prompt", "generate", "post_check", "memory_write"]
assert "本轮编排" in [e.label for e in at.sidebar.expander]
assert any("tools=0" in m.value for m in at.sidebar.markdown)

at.chat_input[0].set_value("我不想活了").run()
assert not list(at.exception), list(at.exception)
assert [n["node"] for n in at.session_state["last_trace"]] == [
    "pre_check", "aggregate", "short_circuit"]
assert at.session_state["last_level"] == "L3" and at.info

at.session_state["messages"] = [{
    "role": "assistant", "content": "看看这个",
    "sources": [{"title": "来源甲", "url": "https://ok.example/x"}]}]
at.run()
assert not list(at.exception), list(at.exception)
assert any("[来源甲](https://ok.example/x)" in m.value for m in at.markdown)
ok("AppTest：首屏/侧栏/L3 资源卡/来源链接")

# 16 trace 与日志不含用户原文 / query / 人名
blob = json.dumps(at.session_state.get("last_trace", []), ensure_ascii=False)
for marker in ("你好", "我不想活了", "P6QueryMark", "小A"):
    assert marker not in blob, f"trace 泄露：{marker}"
log_text = "\n".join(p.read_text(encoding="utf-8")
                     for p in (TMP / "logs").glob("*.jsonl"))
for marker in ("你好", "我不想活了", "P6QueryMark", "小A", "杭州"):
    assert marker not in log_text, f"日志泄露：{marker}"
ok("trace/日志：无原文、无 query、无人名城市")

print(f"\nP6 SCENARIOS PASS: {len(PASS)} checks")
