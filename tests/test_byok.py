"""tests/test_byok.py — 访客自带 Key：格式校验、会话读写、agent 接线、演示模式。

不联网：模型调用全部换成桩客户端；AppTest 只跑首屏与侧栏，不触发真实对话。
"""
from __future__ import annotations

import os

import dotenv
import pytest
from streamlit.testing.v1 import AppTest

import agent
import byok
import pipeline

GOOD = "sk-" + "a" * 32


class _Msg:
    def __init__(self, text: str):
        self.content = text
        self.tool_calls = None


class _Resp:
    def __init__(self, text: str):
        self.choices = [type("Choice", (), {"message": _Msg(text)})()]
        self.usage = None


class _StubClient:
    """只要 chat.completions.create 能返回一条文本即可。"""

    def __init__(self, text: str = "好的。"):
        self.chat = self
        self.completions = self
        self.text = text

    def create(self, **kwargs):
        return _Resp(self.text)


def test_valid_accepts_sk_shapes():
    assert byok.valid(GOOD)
    assert byok.valid("  sk-abc_DEF-1234567890  ")


def test_valid_rejects_other_text():
    for bad in ("", "abc", "sk-", "sk-short", "tvly-" + "a" * 30,
                "sk-" + "a" * 10, "sk-" + "a" * 201):
        assert not byok.valid(bad), bad


def test_clean_strips_quotes_and_spaces():
    assert byok.clean('  "sk-x"  ') == "sk-x"


def test_set_key_stores_valid_and_rejects_invalid():
    state: dict = {}
    assert byok.set_key(GOOD, state)
    assert byok.current(state) == GOOD
    assert byok.set_key("nope", state) is False
    assert byok.current(state) == GOOD


def test_clear_removes_key():
    state: dict = {}
    byok.set_key(GOOD, state)
    byok.clear(state)
    assert byok.current(state) == ""


def test_set_key_does_not_touch_env(monkeypatch):
    """BYOK 只写会话，不许改站点 Key；否则一次填写会影响所有访客。"""
    monkeypatch.setenv("LLM_API_KEY", "sk-" + "e" * 32)
    byok.set_key(GOOD, {})
    assert os.getenv("LLM_API_KEY") == "sk-" + "e" * 32


def test_mode_label_three_states(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert byok.mode_label({}) == "本地演示（无 Key）"
    monkeypatch.setenv("LLM_API_KEY", "sk-" + "b" * 32)
    assert byok.mode_label({}) == "站点演示额度"
    assert byok.mode_label({byok.FIELD: GOOD}) == "你自己的 Key"


def test_call_llm_prefers_session_key(monkeypatch):
    """会话 Key 必须在站点 Key 之前生效，且真的被交给客户端。"""
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.setenv("LLM_API_KEY", "sk-" + "e" * 32)
    seen = {}

    def fake_client(key):
        seen["key"] = key
        return _StubClient()

    monkeypatch.setattr(agent, "_get_client", fake_client)
    agent.set_session_key(GOOD)
    out = agent.call_llm([{"role": "user", "content": "你好"}])
    assert out["ok"] and out["text"] == "好的。"
    assert seen["key"] == GOOD


def test_chat_with_tools_uses_session_key(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.setenv("LLM_API_KEY", "sk-" + "e" * 32)
    seen = {}

    def fake_client(key):
        seen["key"] = key
        return _StubClient()

    monkeypatch.setattr(agent, "_get_client", fake_client)
    agent.set_session_key(GOOD)
    out = agent.chat_with_tools([{"role": "user", "content": "你好"}], [])
    assert out["ok"] and out["tool_calls"] == []
    assert seen["key"] == GOOD


def test_demo_mode_returns_local_script(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    agent.set_session_key("")
    agent.set_demo_mode(True)
    out = agent.call_llm([{"role": "user", "content": "今天有点累"}])
    assert out["ok"] and out["text"] in agent.MOCK_LINES


def test_missing_key_still_raises_without_demo(monkeypatch):
    """配置错误不能被悄悄吞掉：只有 app 层显式开了演示模式才允许走 MOCK。"""
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    agent.set_session_key("")
    agent.set_demo_mode(False)
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        agent.call_llm([{"role": "user", "content": "你好"}])


def test_app_without_key_shows_demo_banner_and_settings(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    at = AppTest.from_file(pipeline.APP, default_timeout=30)
    at.run()
    assert not list(at.exception)
    infos = [el.value for el in at.info]
    assert any("演示模式" in text for text in infos), infos
    assert any(el.label == "DeepSeek API Key" for el in at.text_input)


def test_sidebar_key_switches_to_real_mode(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    at = AppTest.from_file(pipeline.APP, default_timeout=30)
    at.run()

    box = [el for el in at.text_input if el.label == "DeepSeek API Key"][0]
    box.set_value(GOOD)
    [el for el in at.button if el.label == "使用这个 Key"][0].click().run()

    assert not list(at.exception)
    assert at.session_state[byok.FIELD] == GOOD
    infos = [el.value for el in at.info]
    assert not any("演示模式" in text for text in infos), infos
