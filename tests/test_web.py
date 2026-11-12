"""test_web.py — 七类错误码 + scrub + 来源过滤；一个真实域名都不连。"""
from __future__ import annotations

import json

import pytest

import tools
import web


@pytest.fixture(autouse=True)
def clean_registry():
    """每个用例前后清空白名单，避免 web_search 污染其它测试。"""
    tools.reset()
    yield
    tools.reset()


def fake_fetch_factory(status=200, body=b"{}", raises=None, seen=None):
    def fake(url, headers, timeout_s, payload):
        if seen is not None:
            seen.append((url, payload))
        if raises is not None:
            raise raises
        return status, body
    return fake


def ok_body(*urls):
    rows = [{"name": f"标题{i}", "url": u, "snippet": "摘要"} for i, u in enumerate(urls)]
    return json.dumps({"webPages": {"value": rows}}, ensure_ascii=False).encode("utf-8")


def test_http_401(monkeypatch):
    monkeypatch.setenv("WEB_API_KEY", "k")
    data, err = web.search("天气", fetch=fake_fetch_factory(status=401))
    assert (data, err) == (None, "http_401")


def test_http_429(monkeypatch):
    monkeypatch.setenv("WEB_API_KEY", "k")
    assert web.search("天气", fetch=fake_fetch_factory(status=429))[1] == "http_429"


def test_bad_json(monkeypatch):
    monkeypatch.setenv("WEB_API_KEY", "k")
    assert web.search("天气", fetch=fake_fetch_factory(body=b"<html>"))[1] == "bad_json"


def test_timeout(monkeypatch):
    monkeypatch.setenv("WEB_API_KEY", "k")
    assert web.search("天气", fetch=fake_fetch_factory(raises=TimeoutError()))[1] == "timeout"


def test_too_large(monkeypatch):
    monkeypatch.setenv("WEB_API_KEY", "k")
    monkeypatch.setattr(tools, "TOOL_MAX_BYTES", 10)
    assert web.search("天气", fetch=fake_fetch_factory(body=b"x" * 100))[1] == "too_large"


def test_empty(monkeypatch):
    monkeypatch.setenv("WEB_API_KEY", "k")
    data, err = web.search("天气", fetch=fake_fetch_factory(body=ok_body()))
    assert (data, err) == (None, "empty")


def test_query_is_scrubbed_and_truncated(monkeypatch):
    monkeypatch.setenv("WEB_API_KEY", "k")
    seen = []
    web.search("我电话13800138000" + "啊" * 200,
               fetch=fake_fetch_factory(body=ok_body("https://a.example/x"), seen=seen))
    payload = json.loads(seen[0][1])
    assert "13800138000" not in payload["query"]
    assert len(payload["query"]) <= web.QUERY_MAX_CHARS


def test_sources_drop_http_and_private_hosts():
    data = {"items": [{"title": "a", "url": "http://a.example"},
                      {"title": "b", "url": "https://127.0.0.1/x"},
                      {"title": "c", "url": "https://user:pw@ok.example/x"},
                      {"title": "d", "url": "https://ok.example/x"}]}
    assert [s["url"] for s in web.search_sources(data)] == ["https://ok.example/x"]


def test_registered_tool_hidden_without_allow_web(monkeypatch):
    monkeypatch.setenv("WEB_API_KEY", "k")
    web.register_tools()
    names = [t["function"]["name"] for t in tools.list_for_turn("guide", "L1")]
    assert "web_search" not in names
    names = [t["function"]["name"] for t in tools.list_for_turn("guide", "L1", allow_web=True)]
    assert "web_search" in names
