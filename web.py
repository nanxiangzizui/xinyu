"""web.py — 网络工具：检索、来源校验、七类错误码。

[SAFE] query 先 scrub 再截断；结果只取 title/url/snippet；链接一律 https 且非内网；
响应边读边截断；日志只记 provider/status/ms/count，不记 query、不记结果原文。
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import memory
import tools

logger = logging.getLogger(__name__)

WEB_TIMEOUT_S = 6
MAX_RESULTS = 5
QUERY_MAX_CHARS = 80
TITLE_MAX = 60
SNIPPET_MAX = 160
SOURCES_MAX = 3
ERRORS = ("timeout", "http_401", "http_429", "bad_json",
          "too_large", "empty", "bad_url")
PRIVATE_HOSTS = ("localhost", "127.", "10.", "192.168.", "169.254.",
                 "0.0.0.0", "::1")
DEFAULT_ENDPOINT = "https://api.bochaai.com/v1/web-search"   # D-1 定了再改


def _is_private_host(host: str) -> bool:
    """本机 / 内网地址；172.16–172.31 单独判，不做前缀匹配（会误伤 172.32）。"""
    if host.startswith(PRIVATE_HOSTS):
        return True
    parts = host.split(".")
    return (len(parts) == 4 and parts[0] == "172" and parts[1].isdigit()
            and 16 <= int(parts[1]) <= 31)


def is_safe_url(url: str) -> bool:
    """https + 有主机 + 无 userinfo + 非内网。模型没有机会调用它，但 sources 渲染前要过。"""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or "@" in parts.netloc:
        return False
    return not _is_private_host(host)


def _fetch(url: str, headers: dict, timeout_s: float,
           body: bytes | None = None) -> tuple[int, bytes]:
    """默认 transport：urllib，超时 6 秒，边读边截断。异常归一成 TimeoutError。"""
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read(tools.TOOL_MAX_BYTES + 1)
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise TimeoutError(str(exc)) from exc


def _post_json(url: str, payload: dict, headers: dict,
               fetch, timeout_s: float) -> tuple[dict | None, str]:
    """发一次 JSON 请求并解析；所有失败映射到 ERRORS 里的码。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {**headers, "Content-Type": "application/json"}
    try:
        status, raw = fetch(url, headers, timeout_s, body)
    except TimeoutError:
        return None, "timeout"
    except ValueError:                   # transport 契约：URL 非法抛 ValueError
        return None, "bad_url"
    # [SAFE] 顺序不能反：401/403 与 429 各自成码，其余 4xx/5xx 才归 bad_json。
    if status in (401, 403):
        return None, "http_401"
    if status == 429:
        return None, "http_429"
    if status >= 400:
        return None, "bad_json"
    if len(raw) > tools.TOOL_MAX_BYTES:  # 模块属性：测试要能 monkeypatch
        return None, "too_large"
    try:
        return json.loads(raw.decode("utf-8")), ""
    except (ValueError, UnicodeDecodeError):
        return None, "bad_json"


def _normalize(data: object) -> tuple[dict | None, str]:
    """只挑 title/url/snippet 三个字段；形状不对按 bad_json，合法但 0 条按空列表。"""
    provider = os.environ.get("WEB_PROVIDER", "custom")
    if not isinstance(data, dict):
        return None, "bad_json"
    pages = data.get("webPages")
    raw = pages.get("value") if isinstance(pages, dict) else None
    if raw is None:
        raw = data.get("results")
    if not isinstance(raw, list):
        return None, "bad_json"
    items = []
    for row in raw[:MAX_RESULTS]:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        if not is_safe_url(url):
            continue
        items.append({
            "title": str(row.get("name") or row.get("title") or "")[:TITLE_MAX],
            "url": url,
            "snippet": str(row.get("snippet") or row.get("content") or "")[:SNIPPET_MAX],
        })
    return {"items": items, "provider": provider}, ""


def _search_remote(query: str, *, fetch=None) -> tuple[dict | None, str]:
    """D-1 定了 provider 后，整个函数替换成该家的请求；其余代码不动。"""
    endpoint = os.environ.get("WEB_ENDPOINT", DEFAULT_ENDPOINT)
    key = os.environ.get("WEB_API_KEY", "")
    if not key:
        return None, "http_401"          # 没配 key 与 key 错，对模型是同一件事
    fetch = fetch or _fetch
    data, err = _post_json(endpoint, {"query": query, "count": MAX_RESULTS},
                           {"Authorization": f"Bearer {key}"}, fetch, WEB_TIMEOUT_S)
    if err:
        return None, err
    return _normalize(data)


def search(query: str, *, fetch=None) -> tuple[dict | None, str]:
    """唯一入口：scrub → 截断 → 请求 → 归一；返回 (data, error)。"""
    safe = memory.scrub(str(query or "")).strip()[:QUERY_MAX_CHARS]
    if not safe:
        return None, "empty"
    t0 = time.perf_counter()
    data, err = _search_remote(safe, fetch=fetch)
    ms = int((time.perf_counter() - t0) * 1000)
    count = len((data or {}).get("items") or [])
    # 日志只记四个计数；query 与结果原文一律不进日志。
    logger.info("web provider=%s status=%s ms=%d count=%d",
                os.environ.get("WEB_PROVIDER", "custom"), err or "ok", ms, count)
    if not err and count == 0:
        return None, "empty"
    return (None, err) if err else (data, "")


def search_sources(data: dict | None) -> list[dict]:
    """给 P4 渲染用的来源列表：只保留安全 https 链接，最多 3 条。"""
    out = []
    for item in (data or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        if is_safe_url(url):
            out.append({"title": str(item.get("title") or url), "url": url})
    return out[:SOURCES_MAX]


def _handler(query: str) -> dict:
    """失败时返回 error 字段，让模型知道没查到；不让 tools 把码改成异常名。"""
    data, err = search(query)
    if err:
        return {"error": err, "items": []}
    return data


def register_tools() -> None:
    """把 web_search 注册进白名单；是否暴露给模型由 ALLOW_WEB 决定。"""
    tools.register(
        tools.ToolSpec("web_search", "检索公开资料（只读）",
                       {"type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"]},
                       timeout_s=WEB_TIMEOUT_S, trusted=True),
        _handler)
