"""test_agent_loop.py — P2 六条用例：直接答 / 一次工具 / 步数超限 / 工具报错 / 未知工具 / L3。"""
from __future__ import annotations

import orchestrator
import tools
from agent_loop import run_agent


class ScriptedChat:
    """按脚本顺序返回响应，并记录被问了几次。"""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def __call__(self, messages, tool_list):
        self.calls += 1
        return self.replies.pop(0)


def call(name, args, cid="c1"):
    return {"id": cid, "name": name, "arguments": args}


def answer(text):
    return {"text": text, "tool_calls": [], "ok": True, "error": "", "usage": {}}


def wants(*calls):
    return {"text": "", "tool_calls": list(calls), "ok": True, "error": "", "usage": {}}


def _with_fakes():
    tools.reset()
    tools.register_fakes()


def test_direct_answer_needs_one_turn():
    _with_fakes()
    chat = ScriptedChat(answer("嗯，我在。"))
    res = run_agent("sys", [], tools.list_for_turn("listener", "L1"), chat=chat)
    assert (res.ok, res.text, res.tool_calls, chat.calls) == (True, "嗯，我在。", 0, 1)


def test_one_tool_call_then_answer():
    _with_fakes()
    chat = ScriptedChat(wants(call("echo", {"text": "hi"})), answer("收到了。"))
    res = run_agent("sys", [], tools.list_for_turn("listener", "L1"), chat=chat)
    assert (res.ok, res.text, res.tool_calls, chat.calls) == (True, "收到了。", 1, 2)


def test_step_budget_stops_endless_tool_requests():
    _with_fakes()
    chat = ScriptedChat(*[wants(call("echo", {"text": "x"}, f"c{i}")) for i in range(5)])
    res = run_agent("sys", [], tools.list_for_turn("listener", "L1"),
                    max_steps=1, chat=chat, fallback_text="兜底")
    assert (res.ok, res.error, res.text, chat.calls) == (False, "max_steps", "兜底", 1)


def test_tool_call_budget_stops_extra_calls(monkeypatch):
    _with_fakes()
    monkeypatch.setattr("agent_loop.AGENT_MAX_TOOL_CALLS", 1)
    chat = ScriptedChat(wants(call("echo", {"text": "a"}, "c1"),
                              call("echo", {"text": "b"}, "c2")), answer("好。"))
    res = run_agent("sys", [], tools.list_for_turn("listener", "L1"), chat=chat)
    assert (res.ok, res.tool_calls) == (True, 1)


def test_tool_error_is_fed_back_and_loop_continues():
    _with_fakes()
    seen = []

    def chat(messages, tool_list):
        seen.append(messages[-1].get("content", ""))
        return (wants(call("does_not_exist", {})) if len(seen) == 1
                else answer("换个说法。"))

    res = run_agent("sys", [], tools.list_for_turn("listener", "L1"), chat=chat)
    assert (res.ok, res.text, res.tool_calls) == (True, "换个说法。", 1)
    # 第一次回调最后一条还是 system；工具结果只在第二次回调里（文档示例的下标有误）。
    assert "工具调用失败" in seen[-1]


def test_l3_never_calls_agent(monkeypatch):
    """L3 在 orchestrator 短路：loop 存在也不许被调用。"""
    _with_fakes()
    monkeypatch.setattr(orchestrator, "AGENT_LOOP", True)

    def boom(*args, **kwargs):
        raise AssertionError("L3 不许进 agent loop")

    monkeypatch.setattr("agent_loop.run_agent", boom)
    res = orchestrator.handle("我不想活了", "t9", [], "sister_heart", {})
    assert (res["level"], res["role"]) == ("L3", "crisis")
