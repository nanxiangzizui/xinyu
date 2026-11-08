"""test_agent.py — S04 的 6 条离线测试：不联网、不读真实 Key、不 sleep。"""
from __future__ import annotations

import pytest

import agent


@pytest.fixture
def mock_on(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")


def test_mock_same_input_same_output(mock_on):
    """1. MOCK 确定性：同一输入两次，text 完全相同。"""
    msgs = [{"role": "user", "content": "最近有点累"}]
    assert agent.call_llm(msgs)["text"] == agent.call_llm(msgs)["text"]


def test_mock_normal_returns_four_keys(mock_on):
    """2. MOCK 普通输入：四个键齐全，ok=True，error 为空。"""
    got = agent.call_llm([{"role": "user", "content": "在吗"}])
    assert set(got) == {"text", "ok", "error", "latency_ms"}
    assert got["ok"] is True
    assert got["error"] == ""
    assert got["text"]


def test_mock_fail_marker(mock_on):
    """3. 含 __fail__：ok=False，error=MockFailure。"""
    got = agent.call_llm([{"role": "user", "content": "__fail__"}])
    assert got["ok"] is False
    assert got["error"] == "MockFailure"


def test_missing_key_raises_runtime_error(monkeypatch):
    """4. 无 Key 且非 MOCK：抛 RuntimeError，不返回空字符串。"""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("MOCK_LLM", "0")
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        agent.call_llm([{"role": "user", "content": "在吗"}])


def test_safe_json_strips_fence():
    """5. 围栏 JSON：能剥掉并取到字段。"""
    got = agent.safe_json('```json\n{"pass": true, "reason": "ok"}\n```')
    assert isinstance(got, dict)
    assert got["pass"] is True


def test_safe_json_garbage_returns_none():
    """6. 垃圾字符串：返回 None，不是空 dict。"""
    assert agent.safe_json("这不是 JSON") is None
