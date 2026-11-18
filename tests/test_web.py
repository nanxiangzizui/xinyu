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


def test_tool_description_covers_everyday_howto(monkeypatch):
    """P20：除了专名，睡眠 / 饮食这类“具体怎么做”也要允许查——
    工具描述只写专名，帮助模式就只剩空话。隐私仍不许查。"""
    monkeypatch.setenv("WEB_API_KEY", "k")
    web.register_tools()
    description = tools.REGISTRY["web_search"].description
    assert "具体做法" in description and "睡眠" in description
    assert "人名" in description and "角色" in description
    assert "隐私" in description


def json_body(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def bocha_body(*urls):
    rows = [{"name": f"博查标题{i}", "url": u, "snippet": "博查摘要"}
            for i, u in enumerate(urls)]
    return json_body({"code": 200, "data": {"webPages": {"value": rows}}})


def tavily_body(*urls):
    rows = [{"title": f"Tavily 标题{i}", "url": u, "content": "Tavily 摘要"}
            for i, u in enumerate(urls)]
    return json_body({"results": rows})


def test_bocha_wrapped_response(monkeypatch):
    """博查真实响应在 data.webPages.value；解包不对就会整条 bad_json。"""
    monkeypatch.setenv("WEB_PROVIDER", "bocha")
    monkeypatch.setenv("BOCHA_API_KEY", "b")
    monkeypatch.delenv("WEB_API_KEY", raising=False)
    seen = []
    data, err = web.search("青砚",
                           fetch=fake_fetch_factory(body=bocha_body("https://a.example/x"),
                                                    seen=seen))
    assert (err, data["provider"], data["items"][0]["title"]) == ("", "bocha", "博查标题0")
    assert seen[0][0] == "https://api.bocha.cn/v1/web-search"
    assert json.loads(seen[0][1])["count"] == web.MAX_RESULTS


def test_tavily_results_response(monkeypatch):
    """Tavily 顶层 results；请求体要 max_results，不要博查的 count。"""
    monkeypatch.setenv("WEB_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "t")
    monkeypatch.delenv("WEB_API_KEY", raising=False)
    seen = []
    data, err = web.search("Who is Qingyan",
                           fetch=fake_fetch_factory(body=tavily_body("https://b.example/y"),
                                                    seen=seen))
    payload = json.loads(seen[0][1])
    assert (err, data["provider"], data["items"][0]["title"]) == ("", "tavily", "Tavily 标题0")
    assert seen[0][0] == "https://api.tavily.com/search"
    assert payload["max_results"] == web.MAX_RESULTS and "count" not in payload


def test_auto_routes_chinese_to_bocha(monkeypatch):
    """中文/ACG 查询走博查；两家 key 都在时按语言分流。"""
    monkeypatch.setenv("WEB_PROVIDER", "auto")
    monkeypatch.setenv("BOCHA_API_KEY", "b")
    monkeypatch.setenv("TAVILY_API_KEY", "t")
    monkeypatch.delenv("WEB_API_KEY", raising=False)
    seen = []
    data, err = web.search("青砚是谁",
                           fetch=fake_fetch_factory(body=bocha_body("https://a.example/x"),
                                                    seen=seen))
    assert err == "" and data["provider"] == "bocha"
    assert "bocha" in seen[0][0]


def test_auto_routes_english_to_tavily(monkeypatch):
    """英文/技术查询走 Tavily；同一条查询不会两家都打。"""
    monkeypatch.setenv("WEB_PROVIDER", "auto")
    monkeypatch.setenv("BOCHA_API_KEY", "b")
    monkeypatch.setenv("TAVILY_API_KEY", "t")
    monkeypatch.delenv("WEB_API_KEY", raising=False)
    seen = []
    data, err = web.search("Who is Qingyan in Some Fictional Work",
                           fetch=fake_fetch_factory(body=tavily_body("https://b.example/y"),
                                                    seen=seen))
    assert err == "" and data["provider"] == "tavily" and len(seen) == 1
    assert "tavily" in seen[0][0]


def test_auto_falls_back_when_preferred_key_missing(monkeypatch):
    """只配 Tavily 时中文查询也能跑；不要把空 key 发出去。"""
    monkeypatch.setenv("WEB_PROVIDER", "auto")
    monkeypatch.delenv("BOCHA_API_KEY", raising=False)
    monkeypatch.delenv("WEB_API_KEY", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "t")
    seen = []
    data, err = web.search("青砚是谁",
                           fetch=fake_fetch_factory(body=tavily_body("https://b.example/y"),
                                                    seen=seen))
    assert err == "" and data["provider"] == "tavily"
    assert "tavily" in seen[0][0]


@pytest.mark.parametrize("code,expected", [(401, "http_401"), (403, "http_401"),
                                           (429, "http_429"), (500, "bad_json")])
def test_bocha_body_code_is_mapped(monkeypatch, code, expected):
    """博查可能 HTTP 200 但 body code 非 200；不能当成功解析。"""
    monkeypatch.setenv("WEB_PROVIDER", "bocha")
    monkeypatch.setenv("BOCHA_API_KEY", "b")
    monkeypatch.delenv("WEB_API_KEY", raising=False)
    body = json_body({"code": code, "data": {}})
    assert web.search("青砚", fetch=fake_fetch_factory(body=body))[1] == expected
