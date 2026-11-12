# P4 · 工具门禁 + 侧栏「本轮编排」

| 项 | 内容 |
|---|---|
| 节点 | P4 / P6 |
| 计划书 | §3.1 否决层、§4 P4 行、§6 工具门禁、§7 侧栏 |
| 工时 | 1–2 天 |
| 风险 | **最高**——把 `guardian` 接进循环的那一刀，接错就是"工具能绕开否决"或"危机轮被工具拖住" |
| 依赖 | P2 ✅（P3 可选：REGISTRY 为空时也全部可测） |
| 回滚 | `git checkout -- guardian.py orchestrator.py app.py panel.py tests/`；`AGENT_LOOP=0` |

## 1 这一步做什么

四件事，按顺序做，每件都可独立回滚：

1. **`guardian.guardian_tool_check(name, args, role, level)`**——工具门禁，返回 `{"allow","reason"}`，只认四个 reason：`crisis_no_tool / unknown_tool / bad_args / ok`。
2. **接进门禁**——`run_agent` 已有的 `gate` 形参由 `orchestrator` 传进去（P2 只留了参数没用）。
3. **来源由代码渲染**——`run_agent` 加 `source_filter`，`orchestrator` 传 `web.search_sources`；`app.py` 用 `st.markdown` 渲染 `[标题](url)`，模型永远不写 URL。
4. **侧栏「本轮编排」**——`panel.render_trace(trace)`：节点 / 状态 / 毫秒 / detail，**不含任何原句**。

同时把 `AGENT_LOOP` 默认翻成 **1**（v2 正式形态），并处理因此变红的 3 条旧测试（§5.5，必须理解后再动）。

**不做**：不改 `contract_check.py`（D-2：`guardian_tool_check` / `run_agent` 不升契约）、不改 `coordinator`、不加新工具。

## 2 关键决策

### 2.1 门禁放在 `guardian`，不放在 `tools`

`tools.execute` 只管"这个工具存不存在、参数合不合法"——它是**能力**层。**能不能在这个场景用**是安全判断，属于 `guardian`。

| 问题 | 谁回答 | 理由 |
|---|---|---|
| 工具名在注册表里吗？ | `tools` | 能力边界 |
| 参数符合 schema 吗？ | `tools` | 能力边界 |
| 本轮允许用吗（L3 / crisis）？ | `guardian` | 否决权唯一 |
| 结果能不能信？ | 谁都不用信：加 `RESULT_NOTE` | §5.3 结果不可信 |

> 为什么不在 `tools` 里判 L3：`tools` 一旦 import `guardian` 就成环（`guardian` 要 import `tools` 查白名单）。安全判断住 `guardian`，`tools` 保持叶子。

### 2.2 门禁**在 execute 之前**，且失败即拒绝

`_run_calls` 的顺序已经写死：预算 → **门禁** → execute。门禁自身抛异常时按 `allow=False` 处理（P2 代码里已写 `except Exception: verdict={"allow":False,"reason":"gate_error"}`）——**门禁坏了绝不放行**。

### 2.3 L3 是"根本到不了"，不是"到了被拦"

L3 在 `orchestrator.handle` 里 `short_circuit` 提前 return，`_generate` 一行都不会执行。`guardian_tool_check` 里的 `crisis_no_tool` 是**第二道闸**：万一将来有人把 L3 判断挪走，门禁仍然拦得住。

测试要同时断言两件事：`run_agent` 不被调用（P2 已有）+ `guardian_tool_check("web_search", {...}, level="L3")` 拒绝（P4 新增）。**两道都测，才算"零工具"成立。**

### 2.4 来源：模型不写 URL，代码从 `items.url` 挑

数据流只有一条：

```text
web.search → items[].url → web.search_sources()（https + 非内网）→ AgentResult.sources
          → orchestrator 返回 sources → app.py st.markdown("[标题](url)")
```

模型看到的只有 `RESULT_NOTE + items`（含 `url` 字段，供它判断相关性），但它**没有机会**把自己的字符串变成链接——渲染只读 `sources`，不读 `reply`。

### 2.5 `AGENT_LOOP` 默认翻 1，但保留一键关回

```python
AGENT_LOOP = os.environ.get("AGENT_LOOP", "1") == "1"      # P4 起默认开
```

`AGENT_LOOP=0` 时必须与 v1 完全一致——P1 的 `test_node_order_is_unchanged` 与 P2 的旧路径都在守这条。线上出任何怪事，第一动作是设 `AGENT_LOOP=0` 重启。

### 2.6 失败语义：loop 失败 = 生成失败，**不许**变成"看起来正常"

P2 里 `run_agent` 返回 `ok=False`（模型异常 / 超时 / 步数用尽）。P4 在 `_generate` 里把 `ok=False` **转成 raise**，让 `safe_run` 走统一的 L2 + `PIPELINE_FAILED` + `FALLBACK_LINE`。

> 为什么不能直接返回 `res.text`：那会让"循环超步数"这类故障以一句正常回复的形式出现在界面上，日志里也是 `action=pass`——这正是 §8.2 说的"把 bug 变成静默错误"。只有工具**局部**失败（一条 `工具调用失败` 消息）才允许循环继续。

## 3 接口（全部是**加**，不改已有签名）

```text
guardian.py
  guardian_tool_check(name: str, args: dict, role: str = "", level: str = "") -> dict
      {"allow": bool, "reason": "ok|crisis_no_tool|unknown_tool|bad_args"}

agent_loop.py
  AgentResult(..., sources: list = [])                      # 新字段，带默认值
  run_agent(..., *, chat=None, gate=None, source_filter=None, fallback_text="", deadline_s=...)

web.py（P3 已有，这里只调用）
  search_sources(data: dict | None) -> list[dict]

panel.py
  render_trace(trace: list[dict] | None) -> None
```

`gate` 的调用约定固定为 `gate(name, args) -> {"allow","reason"}`；`source_filter` 为 `f(data) -> list[{"title","url"}]`。`orchestrator` 用 `functools.partial` 把 `role/level` 绑进 `guardian_tool_check`。

## 4 前置检查

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # 159 passed（P2+P3）或 150（未做 P3）
Select-String -Path guardian.py -Pattern "^def " | Select-Object -Last 3   # 看行号，305 行的文件
Select-String -Path agent_loop.py -Pattern "gate"      # 确认形参已在但未接
```

`guardian.py` 现在 305 行，加 25 行到 330——**离 350 只剩 20 行**。写的时候别加长注释；超了先删本文件里最啰嗦的旧注释，不许拆文件（契约按文件导函数）。

## 5 执行步骤

### 5.1 `guardian.py` 加门禁

放在 `guardian_post_check` 后面（约 `:300`），import 段加 `import tools`（`tools` 不 import guardian，无环）：

```python
TOOL_DENY_LEVELS = frozenset({"L3"})


def guardian_tool_check(name: str, args: dict, role: str = "",
                        level: str = "") -> dict:
    """工具门禁：只回答 allow/reason，不看结果、不改等级。

    [SAFE] 失败即拒绝（fail-closed）：查不到白名单、参数不对、危机轮，一律不放行。
    这里不能“综合”模型的请求理由——模型说什么都不影响判定。
    """
    if level in TOOL_DENY_LEVELS or role == "crisis":
        return {"allow": False, "reason": "crisis_no_tool"}
    spec = tools.REGISTRY.get(name)
    if spec is None or name not in tools._HANDLERS:
        return {"allow": False, "reason": "unknown_tool"}
    if not isinstance(args, dict):
        return {"allow": False, "reason": "bad_args"}
    for key in (spec.parameters or {}).get("required") or []:
        if key not in args:
            return {"allow": False, "reason": "bad_args"}
    return {"allow": True, "reason": "ok"}
```

> `_HANDLERS` 是下划线名字。要么接受这一个跨模块访问并在注释里说明"注册表与处理器必须同进同出，否则就是半个工具"，要么给 `tools.py` 加 `def has(name)`（+3 行）。**推荐加 `has()`**，别让 guardian 依赖私有名：

```python
# tools.py
def has(name: str) -> bool:
    """是否已注册（spec 与 handler 都在）。"""
    return name in REGISTRY and name in _HANDLERS
```

`guardian_tool_check` 里改成 `if not tools.has(name):`。

### 5.2 `agent_loop.py` 接 `source_filter` 与 `sources`

```python
@dataclass
class AgentResult:
    ...
    sources: list = field(default_factory=list)     # 只放代码校验过的 {title,url}


def _run_calls(calls, msgs, result, gate, source_filter) -> int:
    ...
        res = tools.execute(name, args)
        result.tool_calls += 1
        done += 1
        if res.ok and source_filter is not None:
            result.sources.extend(source_filter(res.data))
        msgs.append(_tool_msg(cid, _payload(res)))
    return done


def run_agent(..., *, chat=None, gate=None, source_filter=None,
              fallback_text="", deadline_s=...):
    ...
        done = _run_calls(calls, msgs, result, gate, source_filter)
```

`sources` 去重 + 截断（同一 URL 多轮重复很正常）：

```python
def _dedup(sources: list[dict], limit: int = 3) -> list[dict]:
    seen, out = set(), []
    for src in sources:
        if src.get("url") and src["url"] not in seen:
            seen.add(src["url"])
            out.append(src)
    return out[:limit]
```

在 `run_agent` 每个 return 前 `result.sources = _dedup(result.sources)`；或只在成功 return 与 `_fail` 里各调一次（`_fail` 也保留已拿到的来源——**失败时来源仍是事实**）。

### 5.3 `orchestrator.py` 接线

```python
import functools
import web                                   # P3 未做时先不 import

AGENT_LOOP = os.environ.get("AGENT_LOOP", "1") == "1"
```

`_generate` 里：

```python
    tool_list = tools_mod.list_for_turn(role, level, allow_web=ALLOW_WEB)
    gate = functools.partial(guardian.guardian_tool_check, role=role, level=level)
    res = agent_loop.run_agent(prompt, history[-10:], tool_list,
                               gate=gate, source_filter=web.search_sources,
                               fallback_text=FALLBACK_LINE)
    _node(trace, "generate", "ok" if res.ok else "error", _ms(t0),
          f"tools={res.tool_calls}")
    if not res.ok:
        # [SAFE] 循环失败=生成失败：交给 safe_run 记 L2 + 兜底，绝不返回“看起来正常”的空话。
        raise RuntimeError(f"agent_loop:{res.error}")
    return {"text": res.text, "ok": True, "sources": res.sources}
```

**行数**：P2 后约 246 行，这里 +4 行 + import 2 行 = 252，**超了**。压缩方案（按顺序试）：

1. 删 `_generate` 里 `v1` 分支那行 detail（少 1 行不行，它是分支）；
2. 把 P1 的 `_detail` 里没用的 `"ok"` 分支删掉（P1 时是预留，现在部分 node 直接传 detail，可删 3 行）；
3. 把 `AGENT_LOOP` / `ALLOW_WEB` 两个常量并进 if 表达式（少 2 行）；
4. 最后才考虑把 `_generate` 移到 `agent_loop`——**移之前先算**：移过去 `agent_loop` 会 import `tools`/`web`/`guardian`，就不再是"纯循环"，得不偿失。

### 5.4 `panel.py` 加 `render_trace`

```python
NODE_LABELS = {"pre_check": "判危", "aggregate": "聚合", "coordinator": "路由",
               "cooldown": "冷却", "lore": "记忆命中", "prompt": "拼 prompt",
               "generate": "生成", "post_check": "复核", "memory_write": "写记忆",
               "short_circuit": "危机短路"}
STATUS_LABELS = {"ok": "✅", "error": "⚠️"}


def render_trace(trace: list[dict] | None) -> None:
    """侧栏「本轮编排」：只渲染节点/状态/毫秒/detail，永不渲染原句与 prompt。"""
    with st.expander("本轮编排", expanded=False):
        if not trace:
            st.caption("本轮没有编排记录")
            return
        for step in trace:
            node = NODE_LABELS.get(step.get("node", ""), step.get("node", "?"))
            mark = STATUS_LABELS.get(step.get("status", ""), "·")
            detail = f" · {step['detail']}" if step.get("detail") else ""
            st.markdown(f"{mark} `{node}` {step.get('latency_ms', 0)} ms{detail}")
```

> trace 的 detail 由 `_node` 写入，只含 `L1/L2/L3`、`listener/guide/crisis`、`tools=N` 这类状态（P1 的 `_detail` 已限定）。**如果有人往 detail 里塞原句，这里是最后一道可见的防线——review 时看到 detail 里有句子就退回。**

### 5.5 `app.py` 三处小改

**(a) 侧栏**：`_sidebar` 里 `render_panel(...)` 之后加

```python
render_trace(st.session_state.get("last_trace"))
```

import 改成 `from panel import LEVEL_LABELS, REASON_LABELS, ROLE_LABELS, render_panel, render_trace`。

**(b) 当前轮回复与来源**（`main()` 里 `safe_run` 之后）：

```python
st.session_state.last_trace = result.get("trace", [])
st.session_state.messages.append({"role": "assistant",
                                  "content": result["reply"],
                                  "sources": result.get("sources") or []})
```

**(c) 历史渲染**：`_render_history` 里每条 assistant 消息后：

```python
for src in msg.get("sources") or []:
    st.markdown(f"- [{src['title']}]({src['url']})")
```

> 来源链接只从 `result["sources"]` 来（P4 已由 `web.search_sources` 过滤），**不解析回复文本里的 URL**。

### 5.6 处理因默认值翻转而红的 3 条旧测试

先跑一遍找红：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

预期恰好 3 条：

| 测试 | 为什么红 | 改法 |
|---|---|---|
| `tests/test_fault.py` F-02 | 打桩 `agent.call_llm`，默认走 `agent.chat_with_tools` | 改打 `agent.chat_with_tools`；断言一字不改（`_generate` 会把 ok=False 转 raise，语义回到 v1） |
| `tests/test_fault.py` F-07 | 同上 | 同上 |
| `tests/test_orchestrator.py::test_exception_becomes_fallback_and_logged` | 同上 | 改打 `agent.chat_with_tools`（或 `monkeypatch.setattr(orchestrator, "AGENT_LOOP", False)` 测 v1 分支——**两种都留**更好：一条测关，一条测开） |

F-02/F-07 的补丁形态：

```python
def boom(*args, **kwargs):
    raise TimeoutError()
monkeypatch.setattr(agent, "chat_with_tools", boom)
```

**不许**为了绿去改断言（例如把 `PIPELINE_FAILED` 改成 `pass`）——那是把降级路径改没了。

## 6 测试（7 条，总 166）

```python
"""test_tool_gate.py — P4：门禁四类 reason / 拒绝不执行 / 门禁故障 fail-closed /
trace 无原文 / sources 由代码过滤 / 默认开启后失败仍走 L2。"""
from __future__ import annotations

import json

import agent
import guardian
import orchestrator
import tools
import web
from agent_loop import run_agent

MARK = "Qz9Marker"


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
        if len(messages) == 2:
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
        if len(messages) == 2:
            return {"text": "", "tool_calls": [
                {"id": "c1", "name": "echo", "arguments": {"text": MARK}}], "ok": True}
        return {"text": "好", "tool_calls": [], "ok": True}
    res = run_agent("sys", [], [], chat=chat, gate=guardian.guardian_tool_check)
    assert MARK not in json.dumps(res.trace, ensure_ascii=False)


def test_sources_are_filtered_by_code():
    _register()
    tools.register(tools.ToolSpec("web_search", "x", {}),
                   lambda: {"items": [{"title": "坏", "url": "http://a.example"},
                                      {"title": "内网", "url": "https://10.0.0.1/x"},
                                      {"title": "好", "url": "https://ok.example/x"}]})
    def chat(messages, tool_list):
        if len(messages) == 2:
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
    res = orchestrator.handle("今天很累", "tg", [], "sister_heart", {})
    assert (res["reply"], res["level"], res["role"]) == (
        orchestrator.FALLBACK_LINE, "L2", "listener")
    assert res["degraded"] is True
```

> 最后一条**同时**是 P4 的语义验收：循环失败不能被当成正常回复。它依赖 `_generate` 的 raise（§5.3）。

## 7 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `.\.venv\Scripts\python.exe -m pytest -q` | **166 passed** |
| 2 | `contract_check.py` | 11/11 + 5/5 + 20/20（契约未加条） |
| 3 | `(Get-Content guardian.py).Count` | ≤350（目标 330） |
| 4 | `Select-String -Path app.py,orchestrator.py,panel.py -Pattern "sk-\|api_key"` | 无输出 |
| 5 | 启动（默认 `AGENT_LOOP=1`，`ALLOW_WEB=0`），问一句日常 | 侧栏「本轮编排」展开有 9 个节点，generate 有 `tools=0` |
| 6 | 说"我不想活了" | 侧栏 trace 只有 pre_check → short_circuit 两步；无 generate；资源卡在 |
| 7 | 临时 `ALLOW_WEB=1` + 假 fetch（本地脚本）触发一次 web_search | 回复下出现"标题"链接；链接域名来自假结果；模型正文里无链接也算通过 |
| 8 | `AGENT_LOOP=0` 重启，再问一句 | 侧栏 trace 的 generate detail 为 `pipeline`，其余不变 |
| 9 | `git diff --stat` | `guardian.py` +25 左右；`memory/coordinator/roles/logger/contract_check` 零改动 |

存证：`docs/evidence/P4-tool-gate-YYYY-MM-DD.md`，贴 #1 #2 #5 #6 截图 + `git diff --stat`。

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 工具仍然执行了（门禁没生效） | `_run_calls` 里 gate 判在 execute 之后 | 顺序必须是 预算 → gate → execute |
| L3 出现工具调用 | `_generate` 被别处调用 / 短路被挪走 | 两道闸都测；短路代码只许在 `handle` |
| 门禁异常导致整轮崩 | gate 异常外抛 | P2 已 try；确认没人在 `_run_calls` 外面再加 gate 调用 |
| 侧栏显示原句 | 有人把 text 写进 detail | detail 只准状态；review 卡这条 |
| 模型自己写 URL | 回复里出现了链接 | 渲染只读 `sources`；**正文不解析** |
| `http://` 链接被渲染 | 没走 `search_sources` | `source_filter` 必须传 `web.search_sources` |
| F-02 红且断言改成 `pass` | 有人为了绿改断言 | 退回去：失败必须是 `template_fallback` + `PIPELINE_FAILED` |
| `guardian.py` >350 行 | 门禁写太胖 | 先删旧注释；不许拆文件 |
| 演示时侧栏空 | `last_trace` 没写进 session_state | `main()` 里那行必须在 `safe_run` 后 |
| v2 默认开启后老用户说"变笨了" | 其实是 loop 里多了一次无工具往返？不会——无 tool_calls 立即返回 | 查 `AGENT_LOOP=0` 对比；对比不出就查 mock/网络 |

## 9 回滚

```powershell
git checkout -- guardian.py orchestrator.py app.py panel.py agent_loop.py tests/
$env:AGENT_LOOP="0"
```

只想关演示、不想回代码：`AGENT_LOOP=0` 一行就回到 v1 管线，trace/来源全部消失（侧栏显示"本轮没有编排记录"），**其余功能不受影响**。

## 10 出口清单

- [ ] 166 passed；契约 11/11 + 5/5 + 20/20
- [ ] 门禁四类 reason 各有测试；拒绝时工具零执行；门禁异常 fail-closed
- [ ] L3 两道闸都测：agent 不被调用 + `guardian_tool_check` 拒绝
- [ ] trace 与日志都不含用户原句（特征串测试）
- [ ] 来源只从 `search_sources` 出，模型正文不参与渲染
- [ ] 侧栏「本轮编排」可用；`AGENT_LOOP=0` 时优雅消失
- [ ] 循环失败 → L2 + `template_fallback` + `PIPELINE_FAILED`（不许静默通过）
- [ ] 证据落 `docs/evidence/P4-tool-gate-YYYY-MM-DD.md`
- [ ] `CLAUDE.md` §2.2 P4 改 ✅，§4 加一行

## 11 回执

```text
P4 完成：166 passed / guardian ___ 行 / 契约 11+5+20
门禁四类 reason 全绿；L3 双闸；trace 无原文；来源代码渲染
AGENT_LOOP 默认 1，=0 可回 v1
下一步：P5 style.py 口吻层
```
