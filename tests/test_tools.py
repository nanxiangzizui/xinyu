"""test_tools.py — 白名单 / schema / 超时 / 大小 / L3 零工具。"""
from __future__ import annotations

import time

import pytest

import tools


@pytest.fixture(autouse=True)
def fresh_registry():
    tools.reset()
    tools.register_fakes()
    yield
    tools.reset()


def test_unknown_tool_is_rejected():
    res = tools.execute("shell", {})
    assert (res.ok, res.error) == (False, "unknown_tool")


def test_bad_args_are_rejected():
    assert tools.execute("echo", {"txt": "hi"}).error == "bad_args"
    assert tools.execute("echo", {"text": 1}).error == "bad_args"
    assert tools.execute("echo", "hi").error == "bad_args"


def test_handler_exception_becomes_error_name():
    tools.register(tools.ToolSpec("boom", "炸", {}), lambda: (_ for _ in ()).throw(ValueError()))
    res = tools.execute("boom", {})
    assert (res.ok, res.error) == (False, "ValueError")


def test_slow_tool_is_marked_timeout():
    tools.register(tools.ToolSpec("slow", "慢", {}, timeout_s=0.001),
                   lambda: time.sleep(0.01) or {"ok": 1})
    assert tools.execute("slow", {}).error == "timeout"


def test_too_large_result_is_rejected(monkeypatch):
    monkeypatch.setattr(tools, "TOOL_MAX_BYTES", 10)
    tools.register(tools.ToolSpec("big", "大", {}, max_bytes=10),
                   lambda: {"blob": "x" * 100})
    assert tools.execute("big", {}).error == "too_large"


def test_l3_and_crisis_get_no_tools():
    assert tools.list_for_turn("crisis", "L3") == []
    assert tools.list_for_turn("listener", "L3") == []
    assert tools.list_for_turn("crisis", "L2") == []


def test_network_tools_hidden_without_allow_web():
    tools.register(tools.ToolSpec("web_search", "搜", {}), lambda: {})
    names = [t["function"]["name"] for t in tools.list_for_turn("guide", "L1")]
    assert "web_search" not in names
    names = [t["function"]["name"]
             for t in tools.list_for_turn("guide", "L1", allow_web=True)]
    assert "web_search" in names


def test_network_tools_are_l1_only():
    """L2 不把用户原文发给第三方；web 只在 L1 出现。"""
    tools.register(tools.ToolSpec("web_search", "搜", {}), lambda: {})
    names = [t["function"]["name"]
             for t in tools.list_for_turn("guide", "L2", allow_web=True)]
    assert "web_search" not in names
