"""P9b：角色卡模式（B）走 orchestrator 的分支行为；A 的旧路径保持不变。"""
import json

import pytest

import agent
import agent_loop
import coordinator
import guardian
import knowledge
import memory
import orchestrator
import rolecard
import style
import tools as tools_mod
from pipeline import memory_path
from rolecard import EXAMPLE_CARD


def _boom(name):
    def fail(*args, **kwargs):
        pytest.fail(f"B 模式不许调用 {name}")
    return fail


def _run(text="今天有点累", state=None, sid="rc-flow"):
    return orchestrator.handle(text, sid, [], EXAMPLE_CARD,
                               {} if state is None else state)


def test_agent_dispatches_card():
    prompt = agent.build_system_prompt(EXAMPLE_CARD, {"rolling_summary": "MEM_MARK"}, ["LORE_MARK"])
    assert "阿岚" in prompt and "[角色卡]" in prompt
    assert "MEM_MARK" not in prompt and "LORE_MARK" not in prompt
    assert "[你的说话方式]" not in prompt and "[你记得的事]" not in prompt
    a_prompt = agent.build_system_prompt("sister_heart", {}, [])
    assert "[安全守则]" in a_prompt and "[你的说话方式]" in a_prompt


def test_rolecard_no_memory(monkeypatch):
    for name in ("read_memory", "write_memory", "update_memory", "should_compress",
                 "compress_summary", "mark_crisis_summary", "recent_lines"):
        monkeypatch.setattr(memory, name, _boom(f"memory.{name}"))
    res = _run()
    assert res["reply"] and res["level"] in ("L1", "L2")


def test_rolecard_no_tools(monkeypatch):
    monkeypatch.setattr(tools_mod, "list_for_turn", _boom("tools.list_for_turn"))
    monkeypatch.setattr(agent_loop, "run_agent", _boom("agent_loop.run_agent"))
    monkeypatch.setattr(guardian, "guardian_tool_check", _boom("guardian_tool_check"))
    monkeypatch.setattr(agent, "chat_with_tools", _boom("agent.chat_with_tools"))
    res = _run()
    assert res["reply"]


def test_rolecard_l3_short_circuit(monkeypatch):
    for mod, name in ((agent, "call_llm"), (agent, "chat_with_tools"),
                      (agent, "build_system_prompt"), (memory, "read_memory"),
                      (memory, "update_memory"), (memory, "should_compress"),
                      (memory, "write_memory"), (memory, "mark_crisis_summary"),
                      (knowledge, "facts_for")):
        monkeypatch.setattr(mod, name, _boom(name))
    state = {}
    res = orchestrator.handle("我不想活了", "rc-crisis", [], EXAMPLE_CARD, state)
    assert res["reply"] == guardian.CRISIS_REPLY
    assert res["level"] == "L3" and res["short_circuit"] is True
    assert state["ever_crisis"] is True
    assert [n["node"] for n in res["trace"]][-1] == "short_circuit"


def test_rolecard_no_compress(monkeypatch):
    monkeypatch.setattr(orchestrator, "_maybe_compress", _boom("_maybe_compress"))
    monkeypatch.setattr(memory, "should_compress", _boom("memory.should_compress"))
    res = _run(state={"turn": 5})
    assert res["reply"]


def test_rolecard_trace_has_nine_nodes():
    res = _run(text="今天有点累")
    nodes = [row["node"] for row in res["trace"]]
    assert nodes == ["pre_check", "aggregate", "coordinator", "cooldown",
                     "lore", "prompt", "generate", "post_check", "memory_write"]
    blob = json.dumps(res["trace"], ensure_ascii=False)
    assert "阿岚" not in blob and "旧书店" not in blob and "今天有点累" not in blob


def test_rolecard_polish_skipped(monkeypatch):
    monkeypatch.setattr(style, "polish", _boom("style.polish"))
    res = _run()
    assert res["reply"]


def test_rolecard_fallback_in_character(monkeypatch):
    monkeypatch.setattr(agent, "call_llm",
                        lambda *a, **k: {"text": "", "ok": False, "error": "MockFailure"})
    res = _run()
    assert res["reply"] == rolecard.SAFE_FALLBACK
    assert res["degraded"] is True
    monkeypatch.setattr(agent, "call_llm",
                        lambda *a, **k: {"text": "角色内回复", "ok": True, "error": ""})
    monkeypatch.setattr(guardian, "guardian_post_check",
                        lambda *a, **k: {"pass": False, "reason": "x", "fixed_reply": "A 兜底",
                                         "rewrite": 0, "template_fallback": True})
    res2 = _run()
    assert res2["reply"] == rolecard.SAFE_FALLBACK


def test_a_unchanged():
    prompt = agent.build_system_prompt("sister_heart", {}, [])
    assert "[安全守则]" in prompt and "角色卡" not in prompt
    state = {}
    res = orchestrator.handle("你好", "a-flow", [], "sister_heart", state)
    assert res["reply"] and res["level"] in ("L1", "L2")
    assert [n["node"] for n in res["trace"]] == [
        "pre_check", "aggregate", "coordinator", "cooldown",
        "lore", "prompt", "generate", "post_check", "memory_write"]
    assert memory_path("a-flow").exists()
    assert coordinator.effective_level("L1", {}) == ("L1", False)
