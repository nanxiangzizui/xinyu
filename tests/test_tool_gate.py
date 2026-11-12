"""test_tool_gate.py — P4：门禁四类 reason / 拒绝不执行 / 门禁故障 fail-closed /
trace 无原文 / sources 由代码过滤 / 默认开启后失败仍走 L2。"""
from __future__ import annotations

import json

import pytest

import agent
import guardian
import orchestrator
import pipeline
import tools
import web
from agent_loop import run_agent

MARK = "Qz9Marker"


@pytest.fixture(autouse=True)
def clean_registry():
    tools.reset()
    yield
    tools.reset()


def _register(name="echo", trusted=True):
    tools.reset()
    tools.register(tools.ToolSpec(
        name, "测试工具", {"type": "object",
                          "properties": {"text": {"type": "string", "default": ""}},
                          "required": []}, trusted=trusted), lambda **kw: {"ok": 1})


def test_gate_denies_crisis_and_l3():
    _register()
    assert guardian.guardian_tool_check("echo", {}, "crisis", "L2")["reason"] == "crisis_no_tool"
    assert guardian.guardian_tool_check("echo", {}, "listener", "L3")["reason"] == "crisis_no_tool"


def test_gate_denies_unknown_and_bad_args():
    _register()
    assert guardian.guardian_tool_check("shell", {})["reason"] == "unknown_tool"
    assert guardian.guardian_tool_check("echo", "no")["reason"] == "bad_args"
    tools.reset()
    tools.register(tools.ToolSpec("need", "x", {"type": "object",
                                                "properties": {"q": {"type": "string"}},
                                                "required": ["q"]}), lambda q: {})
    assert guardian.guardian_tool_check("need", {})["reason"] == "bad_args"


def test_denied_tool_is_not_executed():
    _register()
    ran = []
    tools.register(tools.ToolSpec("echo", "x", {}), lambda: ran.append(1) or {})

    def chat(messages, tool_list):
        if len(messages) == 1:          # run_agent 首调只有 system，一条就够
            return {"text": "", "tool_calls": [
                {"id": "c1", "name": "echo", "arguments": {}}], "ok": True}
        return {"text": "好", "tool_calls": [], "ok": True}

    def deny(name, args):
        return {"allow": False, "reason": "unknown_tool"}

    res = run_agent("sys", [], [], chat=chat, gate=deny)
    assert (res.ok, res.text, ran) == (True, "好", [])


def test_gate_error_fails_closed():
    _register()
    def bad_gate(name, args):
        raise ValueError("gate down")
    res = run_agent("sys", [], [],
                    chat=lambda m, t: {"text": "好", "tool_calls": [
                        {"id": "c1", "name": "echo", "arguments": {}}], "ok": True},
                    gate=bad_gate)
    assert res.tool_calls == 0


def test_trace_has_no_query_text():
    _register("echo")
    def chat(messages, tool_list):
        if len(messages) == 1:
            return {"text": "", "tool_calls": [
                {"id": "c1", "name": "echo", "arguments": {"text": MARK}}], "ok": True}
        return {"text": "好", "tool_calls": [], "ok": True}
    res = run_agent("sys", [], [], chat=chat, gate=guardian.guardian_tool_check)
    assert res.ok and res.tool_calls == 1
    assert MARK not in json.dumps(res.trace, ensure_ascii=False)


def test_sources_are_filtered_by_code():
    _register()
    tools.register(tools.ToolSpec("web_search", "x", {}),
                   lambda: {"items": [{"title": "坏", "url": "http://a.example"},
                                      {"title": "内网", "url": "https://10.0.0.1/x"},
                                      {"title": "好", "url": "https://ok.example/x"}]})
    def chat(messages, tool_list):
        if len(messages) == 1:
            return {"text": "", "tool_calls": [
                {"id": "c1", "name": "web_search", "arguments": {}}], "ok": True}
        return {"text": "好", "tool_calls": [], "ok": True}
    res = run_agent("sys", [], [], chat=chat, source_filter=web.search_sources)
    assert [s["url"] for s in res.sources] == ["https://ok.example/x"]


def test_loop_failure_becomes_template_fallback(monkeypatch):
    """默认 AGENT_LOOP=1 后，chat_with_tools 抛异常仍走 L2 + PIPELINE_FAILED。"""
    assert orchestrator.AGENT_LOOP is True
    def boom(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr(agent, "chat_with_tools", boom)
    # 兜底只在 safe_run（P1 起 handle 让异常上抛）。
    res = orchestrator.safe_run("今天很累", "tg", [], "sister_heart", {})
    assert (res["reply"], res["level"], res["role"]) == (
        orchestrator.FALLBACK_LINE, "L2", "listener")
    assert res["degraded"] is True
    row = pipeline.reply_rows("tg")[-1]
    assert (row["action"], row["rule_ids"]) == ("template_fallback", ["PIPELINE_FAILED"])
