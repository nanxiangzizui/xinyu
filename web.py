"""web.py — 网络工具：检索、来源校验、七类错误码。

[SAFE] query 先 scrub 再截断；结果只取 title/url/snippet；链接一律 https 且非内网；
响应边读边截断；日志只记 provider/status/ms/count，不记 query、不记结果原文。
"""
from __future__ import annotations

import json
import logging
import os
import re
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
SNIPPET_MAX = 400
SOURCES_MAX = 3
ERRORS = ("timeout", "http_401", "http_429", "bad_json",
          "too_large", "empty", "bad_url")
PRIVATE_HOSTS = ("localhost", "127.", "10.", "192.168.", "169.254.",
                 "0.0.0.0", "::1")
BOCHA_ENDPOINT = "https://api.bocha.cn/v1/web-search"
TAVILY_ENDPOINT = "https://api.tavily.com/search"
DEFAULT_ENDPOINT = BOCHA_ENDPOINT
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


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


def _has_cjk(text: str) -> bool:
    """中文查询走博查；纯英文 / 技术查询走 Tavily。"""
    return bool(CJK_RE.search(text))


def _key_for(provider: str) -> str:
    """按 provider 取专用 key；WEB_API_KEY 只作旧配置兜底。"""
    name = "BOCHA_API_KEY" if provider == "bocha" else "TAVILY_API_KEY"
    return os.environ.get(name, "") or os.environ.get("WEB_API_KEY", "")


def _pick_provider(query: str) -> str:
    """显式 provider 优先；auto 按语言分流，缺 key 时退到另一家。"""
    forced = os.environ.get("WEB_PROVIDER", "auto").strip().lower()
    if forced in ("bocha", "tavily"):
        return forced
    preferred = "bocha" if _has_cjk(query) else "tavily"
    other = "tavily" if preferred == "bocha" else "bocha"
    return preferred if _key_for(preferred) else (other if _key_for(other) else preferred)


def _endpoint_for(provider: str) -> str:
    """两家 endpoint 分开配；旧 WEB_ENDPOINT 不再参与，避免串到另一家。"""
    if provider == "bocha":
        return os.environ.get("BOCHA_ENDPOINT", DEFAULT_ENDPOINT)
    return os.environ.get("TAVILY_ENDPOINT", TAVILY_ENDPOINT)


def _payload_for(provider: str, query: str) -> dict:
    """博查用 count；Tavily 用 max_results，且只要 snippet，不要正文。"""
    if provider == "bocha":
        return {"query": query, "count": MAX_RESULTS}
    return {"query": query, "search_depth": "basic", "max_results": MAX_RESULTS,
            "include_answer": False, "include_raw_content": False}


def _body_error(data: object) -> str:
    """博查 HTTP 200 也可能带 code=401/429；不能只看 HTTP status。"""
    if not isinstance(data, dict) or data.get("code") is None:
        return ""
    code = str(data.get("code"))
    if code == "200":
        return ""
    if code in ("401", "403"):
        return "http_401"
    return "http_429" if code == "429" else "bad_json"


def _rows(data: dict) -> list | None:
    """兼容博查 data.webPages.value 与旧/顶层 webPages、Tavily results。"""
    pages = data.get("webPages")
    if isinstance(pages, dict) and isinstance(pages.get("value"), list):
        return pages["value"]
    inner = data.get("data")
    if isinstance(inner, dict):
        pages = inner.get("webPages")
        if isinstance(pages, dict) and isinstance(pages.get("value"), list):
            return pages["value"]
        if isinstance(inner.get("results"), list):
            return inner["results"]
    return data["results"] if isinstance(data.get("results"), list) else None


def _normalize(data: object, provider: str) -> tuple[dict | None, str]:
    """优先解博查 data.webPages.value，其次 Tavily results；只挑三字段。"""
    if not isinstance(data, dict):
        return None, "bad_json"
    raw = _rows(data)
    if raw is None:
        return None, "bad_json"
    items = []
    for row in raw[:MAX_RESULTS]:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        if not is_safe_url(url):
            continue
        snippet = row.get("snippet") or row.get("content") or row.get("summary") or ""
        items.append({
            "title": str(row.get("name") or row.get("title") or "")[:TITLE_MAX],
            "url": url,
            "snippet": str(snippet)[:SNIPPET_MAX],
        })
    return {"items": items, "provider": provider}, ""


def _search_remote(query: str, *, fetch=None,
                   provider: str | None = None) -> tuple[dict | None, str]:
    """选 provider → 取专用 key → 发一次请求 → 解包 + body code 映射。"""
    provider = provider or _pick_provider(query)
    key = _key_for(provider)
    if not key:
        return None, "http_401"          # 没配 key 与 key 错，对模型是同一件事
    fetch = fetch or _fetch
    data, err = _post_json(_endpoint_for(provider), _payload_for(provider, query),
                           {"Authorization": f"Bearer {key}"}, fetch, WEB_TIMEOUT_S)
    if err:
        return None, err
    err = _body_error(data)
    if err:
        return None, err
    return _normalize(data, provider)


def search(query: str, *, fetch=None) -> tuple[dict | None, str]:
    """唯一入口：scrub → 截断 → 请求 → 归一；返回 (data, error)。"""
    safe = memory.scrub(str(query or "")).strip()[:QUERY_MAX_CHARS]
    if not safe:
        return None, "empty"
    t0 = time.perf_counter()
    provider = _pick_provider(safe)
    data, err = _search_remote(safe, fetch=fetch, provider=provider)
    ms = int((time.perf_counter() - t0) * 1000)
    count = len((data or {}).get("items") or [])
    # 日志只记四个计数；query 与结果原文一律不进日志。
    logger.info("web provider=%s status=%s ms=%d count=%d",
                provider, err or "ok", ms, count)
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
        tools.ToolSpec("web_search", "查你不确定的人名、角色、作品、梗或事件（只读，只查专名，可带作品名）",
                       {"type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"]},
                       timeout_s=WEB_TIMEOUT_S, trusted=True),
        _handler)
