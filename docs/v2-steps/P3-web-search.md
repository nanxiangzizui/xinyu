# P3 · `web.py` 网络工具（搜索 / 图片 / 风格包）

| 项 | 内容 |
|---|---|
| 节点 | P3 / P6 |
| 计划书 | §3.1 工具清单、§4 P3 行、§5 网络与降级、§6 红线 1–5 |
| 工时 | 2–4 天（**其中 1 天是等 D-1 provider 决策**） |
| 风险 | **高**——第一次把外部内容放进上下文；第一次可能因为网络把整轮拖死 |
| 依赖 | P2 ✅ + **D-1 决策**（provider / key / 是否走 MCP） |
| 回滚 | 删除 `web.py`、`tests/test_web.py`，`git checkout -- app.py`，`AGENT_LOOP=0` |

## 0 开工门槛（不满足就别动真网）

P3 分两半，**只有前半可以无条件做**：

| 阶段 | 内容 | 能否先做 |
|---|---|---|
| P3a | `web.py` 接口 + 假 transport 注入 + 七类错误码 + 9 条离线测试 | ✅ 现在就能做，不依赖任何 key |
| P3b | 真 provider 的请求构造 + 一次真实 smoke + `.env` 加 key | ⛔ **D-1 未定前不做** |

D-1 要回答的只有三件事：

1. **哪家**（见 §2.2 决策矩阵）；
2. **key 放哪**（本地 `.env` + Cloud Secrets，都不入库）；
3. **演示用不用真网**（建议：录屏里真网只出现 20 秒，其余走"网络不可用 → 直接答"分支）。

> 没定就做 P3a：它让 P4 的门禁、来源渲染、`allow_web` 开关全部可测，等 provider 定了只补 `_search_remote()` 一个函数。

## 1 这一步做什么

给 agent loop 装**唯一一个**真实工具 `web_search`：

- 输入只有 `query`（字符串，先 `scrub` 再截断 80 字，**不当 URL**）；
- 输出固定 `{"items": [{"title","url","snippet"}], "provider": str}`，≤5 条；
- **七类失败全部变成 `ToolResult(ok=False, error=...)`**，绝不让异常冒到 loop；
- 日志只记 `provider / status / ms / count`，**不记 query、不记结果原文**；
- 结果里的链接**不直接给模型当 URL 用**：`search_sources()` 只输出经过校验的 `{title,url}`，P4 由代码渲染。

`fetch_image`：只留接口与 `bad_url` 校验，**P3 不注册**（D-4：MVP 只做 web_search）。`style_pack` 不进本文件（D-3：静态资源，归 P5）。

产出：

| 文件 | 行数预算 | 内容 |
|---|---|---|
| `web.py` | ≤250 | 常量 / `search()` / `search_sources()` / `_http_get` / 错误映射 / `register_tools()` / （P3b）`_search_remote` |
| `tests/test_web.py` | — | 9 条离线测试（全部假 transport） |
| `app.py` | +2 行 | 启动时 `web.register_tools()`（在 `_config_gate()` 之后） |

## 2 关键决策

### 2.1 provider 藏在一个函数后面

`web.search()` 是唯一对外入口，内部 `_search_remote()` 是**唯一**知道 provider 长什么样的地方。换 provider = 只改这一个函数 + 一个常量。测试全部注入 `fetch=`，一行都不碰真网。

```python
def search(query: str, *, fetch=None) -> tuple[dict | None, str]:
    """返回 (data, error)；error 非空即失败，data 为 None。"""
```

> 为什么返回 tuple 不返回 `ToolResult`：`web.py` 不认识 `tools.ToolResult`（那会让 web 依赖 tools 的运行时类型，P4 再包一层就绕）；tuple 是纯数据，`register_tools` 里的薄壳负责转。

### 2.2 provider 决策矩阵（D-1 用这张表拍板）

| 选项 | 中文效果 | 要 key | 免费额度 | 稳定性 | 结论 |
|---|---|---|---|---|---|
| **博查 Bocha** | 好 | 是 | 有试用 | 国内直连快 | **中文演示首选** |
| Tavily | 中 | 是 | 1000 次/月 | 好 | 英文/技术类首选，中文一般 |
| Brave Search | 中 | 是 | 2000 次/月 | 好 | 备选，中文偏弱 |
| SearXNG 公共实例 | 看实例 | 否 | — | **差**（随时挂） | 只做本地兜底实验 |
| DuckDuckGo HTML | 中 | 否 | — | **差**（易 403） | 不做，违反"演示别赌网络" |

拍板后写进 `.env`：

```text
WEB_PROVIDER=bocha
WEB_API_KEY=...
WEB_ENDPOINT=https://api.bochaai.com/v1/web-search
```

**key 不进仓库**：`.env` 已 gitignore；Cloud 端填 Secrets。`_bridge_secrets()` 已在 `app.py:41` 把 Secrets 桥成环境变量，P3 不用改它。

### 2.3 七类错误码，一个不多

| error | 触发 | 用户/模型看到 |
|---|---|---|
| `timeout` | `urlopen` 超时、DNS 失败、连接被拒 | "工具调用失败：timeout" |
| `http_401` | 401 / 403（key 错或额度尽） | 同上 |
| `http_429` | 429（限流） | 同上 |
| `bad_json` | 响应不是合法 JSON / 缺 `items` | 同上 |
| `too_large` | 响应体 > `TOOL_MAX_BYTES` | 同上 |
| `empty` | 合法 JSON 但 0 条结果 | 同上（模型会换 query 或直接答） |
| `bad_url` | 非 https / 内网地址 / 带 userinfo（`fetch_image` 用） | 同上 |

> `network` 不单列：对用户和模型来说"没拿到结果"就是同一件事，多一个码只会让日志分叉。**但日志里记的是 `type(exc).__name__`**，排查时仍能区分 `URLError` / `socket.timeout`。

### 2.4 边读边截断，绝不 `read()` 到底

```python
body = resp.read(TOOL_MAX_BYTES + 1)      # 多读 1 字节用来判超限
if len(body) > TOOL_MAX_BYTES:
    return None, "too_large"
```

`resp.read()` 无参会把一个 500MB 的错误页全读进内存。多读 1 字节是"判超限"最省内存的写法。

### 2.5 query 先 scrub，再截断，再当纯文本

```python
safe = memory.scrub(query).strip()[:QUERY_MAX_CHARS]
if not safe:
    return None, "empty"
```

`scrub` 会打掉手机/证件/邮箱/链接/学校名——**用户把手机号打进搜索框**是最容易发生的隐私泄漏，P3 必须挡住。`QUERY_MAX_CHARS = 80`：再长不是搜索词，是倾诉。

> 注意：`scrub` 认不出人名。所以 P3 的验收只说"query 经过 scrub 与长度截断"，不许说"query 已脱敏"。

### 2.6 结果当资料，链接由代码渲染

`_search_remote()` 只从响应里挑 `title / url / snippet` 三个字段，**不把原始 JSON 塞给模型**（原始 JSON 里常带广告位、provider 自己的 `site_name`、`datePublished` 等噪声，也更容易夹带指令）。

`snippet` 截断到 160 字，`title` 截断到 60 字，`url` 只允许 `https://`。给了模型也不知道 URL 长什么样——来源链接在 P4 由代码从 `sources` 渲染，模型只负责说"我查了一下"。

### 2.7 `allow_web` 默认假，注册不等于暴露

`register_tools()` 把 `web_search` 放进 `REGISTRY` 并标 `trusted=True`；但 `tools.list_for_turn(..., allow_web=True)` 才把它给模型。`orchestrator.ALLOW_WEB` 来自环境变量，**默认 `0`**。

三层开关，任何一层关掉，模型都看不到网络工具：

```text
ALLOW_WEB=0          → list_for_turn 过滤掉 NETWORK_TOOLS
REGISTRY 为空        → 连过滤都省了（P2 默认状态）
L3 / crisis          → list_for_turn 直接 []
```

## 3 接口

```text
web.py
  WEB_TIMEOUT_S = 6 / MAX_RESULTS = 5 / QUERY_MAX_CHARS = 80 / SNIPPET_MAX = 160
  ERRORS = ("timeout","http_401","http_429","bad_json","too_large","empty","bad_url")
  search(query: str, *, fetch=None) -> tuple[dict | None, str]
  search_sources(data: dict) -> list[dict]          # [{"title","url"}]，P4 渲染用
  register_tools() -> None                          # tools.register(web_search spec, handler)
  is_safe_url(url: str) -> bool                     # https + 非内网 + 无 userinfo

真实 transport（可注入，测试用假的）
  fetch(url: str, headers: dict, timeout_s: float, body: bytes | None = None) -> tuple[int, bytes]
  抛 TimeoutError 表示超时/连不上；抛 ValueError 表示 URL 非法
```

## 4 前置检查

```powershell
.\.venv\Scripts\python.exe -m pytest -q            # 150 passed（P2 后）
Select-String -Path tools.py -Pattern "NETWORK_TOOLS"   # 确认已有 {web_search, fetch_image}
Select-String -Path .env -Pattern "WEB_"                # D-1 定了才有；没有就先做 P3a
```

## 5 执行步骤

### 5.1 新建 `web.py`（P3a：接口 + 假 transport + 错误映射）

```python
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
ERRORS = ("timeout", "http_401", "http_429", "bad_json",
          "too_large", "empty", "bad_url")
PRIVATE_HOSTS = ("localhost", "127.", "10.", "192.168.", "169.254.", "::1")
DEFAULT_ENDPOINT = "https://api.bochaai.com/v1/web-search"   # D-1 定了再改


def is_safe_url(url: str) -> bool:
    """https + 有主机 + 无 userinfo + 非内网。模型没有机会调用它，但 sources 渲染前要过。"""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or "@" in parts.netloc:
        return False
    return not host.startswith(PRIVATE_HOSTS)


def _fetch(url: str, headers: dict, timeout_s: float,
           body: bytes | None = None) -> tuple[int, bytes]:
    """默认 transport：urllib，超时 6 秒，边读边截断。异常归一成 TimeoutError。"""
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read(tools.TOOL_MAX_BYTES + 1)
            return resp.status, body
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
    if status == 401 or status == 403:
        return None, "http_401"
    if status == 429:
        return None, "http_429"
    if status >= 400:
        return None, "bad_json"          # 非 401/429 的 4xx/5xx 与坏响应对模型是同一件事
    if len(raw) > tools.TOOL_MAX_BYTES:
        return None, "too_large"
    try:
        return json.loads(raw.decode("utf-8")), ""
    except (ValueError, UnicodeDecodeError):
        return None, "bad_json"


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
    return _normalize(data), ""
```

> 上面 `_post_json` 的 transport 签名是 `(url, headers, timeout_s, body)`，与 §3 的 3 参数版差一个 `body`——**以本节代码为准**（POST 必须有 body）。P3a 写测试时按 4 参数注入。

### 5.2 归一化与入口（P3a 继续）

```python
def _normalize(data: dict) -> dict:
    """从 provider 响应里只挑三个字段；缺字段的条目直接丢。"""
    raw = data.get("webPages", {}).get("value") or data.get("results") or []
    items = []
    for row in raw[:MAX_RESULTS]:
        url = str(row.get("url") or "").strip()
        if not is_safe_url(url):
            continue
        items.append({"title": str(row.get("name") or row.get("title") or "")[:TITLE_MAX],
                      "url": url,
                      "snippet": str(row.get("snippet") or row.get("content") or "")[:SNIPPET_MAX]})
    return {"items": items, "provider": os.environ.get("WEB_PROVIDER", "custom")}


def search(query: str, *, fetch=None) -> tuple[dict | None, str]:
    """唯一入口：scrub → 截断 → 请求 → 归一；返回 (data, error)。"""
    safe = memory.scrub(str(query or "")).strip()[:QUERY_MAX_CHARS]
    if not safe:
        return None, "empty"
    t0 = time.perf_counter()
    data, err = _search_remote(safe, fetch=fetch)
    ms = int((time.perf_counter() - t0) * 1000)
    count = len((data or {}).get("items") or [])
    logger.info("web provider=%s status=%s ms=%d count=%d",
                os.environ.get("WEB_PROVIDER", "custom"), err or "ok", ms, count)
    if not err and count == 0:
        return None, "empty"
    return (None, err) if err else (data, "")


def search_sources(data: dict | None) -> list[dict]:
    """给 P4 渲染用的来源列表：只保留安全 https 链接，最多 3 条。"""
    out = []
    for item in (data or {}).get("items") or []:
        if is_safe_url(item.get("url", "")):
            out.append({"title": item.get("title") or item["url"], "url": item["url"]})
    return out[:3]
```

### 5.3 注册成工具（P3a 收尾）

```python
def _handler(query: str) -> dict:
    data, err = search(query)
    if err:
        raise RuntimeError(err)          # 由 tools.execute 转成 error=RuntimeError？不行，见下
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
```

> **这里有个坑，必须绕开**：`tools.execute` 把 handler 异常映射成 `error=类型名`，直接 `raise RuntimeError(err)` 会让错误码变成 `RuntimeError`，七类码全丢。所以 `_handler` 不能抛——它要返回一个"失败也合法"的 dict：

```python
def _handler(query: str) -> dict:
    """失败时返回 error 字段，让模型知道没查到；不让 tools 把码改成异常名。"""
    data, err = search(query)
    if err:
        return {"error": err, "items": []}
    return data
```

模型看到 `{"error":"timeout","items":[]}` 会自己决定换个说法或直接答，比一条 `工具调用失败：RuntimeError` 有用得多。**七类码要出现在 `usage`/日志/测试里，不是靠异常类型传递。**

### 5.4 `app.py` 启动时注册

在 `_config_gate()` 之后、`main()` 之前（约 `:232`）加：

```python
import web                                                     # noqa: E402
...
web.register_tools()          # 注册 ≠ 暴露：ALLOW_WEB=0 时模型看不到
```

`web` 的 import 也必须在 `_bridge_secrets()` 之后（它读 `WEB_API_KEY` 时已是 Secrets 桥过来的值）。

### 5.5 P3b（D-1 定了才做）

1. 把 `_search_remote()` 换成 provider 的真实请求（字段名照 §5.2 的 `_normalize` 对齐）；
2. 本地 `.env` 加 `WEB_PROVIDER` / `WEB_API_KEY` / `WEB_ENDPOINT`；
3. 跑一次真实 smoke（不进 pytest）：

```powershell
$env:WEB_API_KEY="..." ; $env:WEB_PROVIDER="bocha"
.\.venv\Scripts\python.exe -c "import web; d,e = web.search('杭州 天气'); print(e, len((d or {}).get('items', [])))"
```

4. Cloud Secrets 填同样三个键；
5. 把 smoke 输出（**不含 query 原文与 key**）贴进证据文件。

## 6 测试（9 条，全部离线）

```python
"""test_web.py — 七类错误码 + scrub + 来源过滤；一个真实域名都不连。"""
from __future__ import annotations

import json

import tools
import web


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
                      {"title": "c", "url": "https://ok.example/x"}]}
    assert [s["url"] for s in web.search_sources(data)] == ["https://ok.example/x"]


def test_registered_tool_hidden_without_allow_web(monkeypatch):
    tools.reset()
    monkeypatch.setenv("WEB_API_KEY", "k")
    web.register_tools()
    names = [t["function"]["name"] for t in tools.list_for_turn("guide", "L1")]
    assert "web_search" not in names
    names = [t["function"]["name"] for t in tools.list_for_turn("guide", "L1", allow_web=True)]
    assert "web_search" in names
    tools.reset()
```

> `test_too_large` 里 handler 先拿到 `body=b"x"*100`，`_post_json` 用 `tools.TOOL_MAX_BYTES` 判超限 → 直接 `too_large`，连 `json.loads` 都不进。注意这个测试依赖 `monkeypatch tools.TOOL_MAX_BYTES`，所以 `_post_json` 里**必须走模块属性** `tools.TOOL_MAX_BYTES`，不能 `from tools import TOOL_MAX_BYTES`。

## 7 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `.\.venv\Scripts\python.exe -m pytest -q` | **159 passed**（150 + 9） |
| 2 | `contract_check.py` | 11/11 + 5/5 + 20/20 |
| 3 | `Select-String -Path tests\test_web.py -Pattern "http"` | 只有 `https://ok.example` / `http://a.example` 这类文档用假域名，**没有一个真实可达域名** |
| 4 | `(Get-Content web.py).Count` | ≤250 |
| 5 | `Select-String -Path web.py -Pattern "requests\|aiohttp\|httpx"` | 无输出（只用 `urllib`） |
| 6 | P3b：真实 smoke（§5.5） | 返回 `0`/`ok` 且 `count` 1–5；`data\logs` 里只有 `web provider=... status=ok` |
| 7 | 断网：拔网线跑 `web.search("测试")` | `(None, "timeout")`，不是异常；agent 那轮仍正常出话 |
| 8 | `ALLOW_WEB=0` 启动，问"帮我查一下…" | 模型不调工具（看不到），正常答 |
| 9 | `ALLOW_WEB=1` + `AGENT_LOOP=1` 启动 | 侧栏 trace 的 generate 出现 `tools=1`；回复里不出现自编 URL |

存证：`docs/evidence/P3-web-YYYY-MM-DD.md`，含 #1 #2 #6 #8 输出；#6 的 query 用虚构词（如"杭州 西湖 开放时间"），不用任何个人化输入。

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 测试里真的连了网 | 忘了注入 `fetch=`，走了默认 transport | `search()` 的 `fetch` 必须显式传；CI 无网也不该红 |
| 错误码永远是 `RuntimeError` | handler 抛异常，被 `tools.execute` 改名 | handler 返回 `{"error": code}`，不抛（§5.3） |
| 日志里有 query | 在 `search` 里把 `safe` 打进日志 | 只记 provider/status/ms/count |
| 模型自己编 URL | 把 `items` 原样给模型 / 让模型渲染来源 | 来源走 `search_sources`，P4 代码渲染 |
| 429 被当成成功 | 只看 `status >= 400` 没先判 429 | 401/403 → `http_401`，429 → `http_429`，**顺序不能反** |
| 大响应把进程读爆 | `resp.read()` 无参 | `read(TOOL_MAX_BYTES + 1)` |
| Cloud 上 `http_401` | Secrets 没填 / 键名不一致 | `.streamlit/secrets.toml.example` 同步加三键；核对大小写 |
| `empty` 太频繁 | provider 参数不对（如 `count` 不支持） | 看 P3b smoke 的原始 status；不许为此放宽成"返回空也算成功" |
| 演示时网络抖动整轮卡 20 秒 | `AGENT_TOTAL_TIMEOUT_S` 太大 / 工具重试 | 不加重试；`TOOL_TIMEOUT_S=6` 到了就降级直接答 |

## 9 回滚

```powershell
Remove-Item web.py, tests/test_web.py
git checkout -- app.py
$env:ALLOW_WEB="0"        # 或干脆清掉
.\.venv\Scripts\python.exe -m pytest -q      # 回到 150
```

网络出问题时的第一处置永远是 `ALLOW_WEB=0`（模型看不到工具，直接答），**不是**去调 `web.py`。

## 10 出口清单

- [ ] P3a：159 passed；七类错误码各有测试；`web.py` ≤250；只用 `urllib`
- [ ] P3b：真实 smoke 通过且证据里无 key、无 query 原文
- [ ] query 经 `scrub` + 80 字截断（测试可证）
- [ ] `search_sources` 丢掉 http / 内网 / userinfo 链接
- [ ] 断网时返回 `timeout` 且当轮仍能出话
- [ ] 日志无 query、无结果原文
- [ ] `CLAUDE.md` §2.2 P3 改 ✅（未做 P3b 就先标 🟨），§4 加一行

## 11 回执

```text
P3 完成：159 passed（150+9）/ provider=___ / 真实 smoke __ 条
七类错误码全绿；断网降级为 timeout；日志无 query
下一步：P4 工具门禁 + 侧栏「本轮编排」
```
