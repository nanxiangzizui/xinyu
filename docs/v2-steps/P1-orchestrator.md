# P1 · 抽出 `orchestrator.py`（零行为变化）

| 项 | 内容 |
|---|---|
| 节点 | P1 / P6 |
| 计划书 | §2 目标架构、§3.2 函数边界、§4 P1 行、§7 代码落点 |
| 工时 | 1 天（熟悉代码的人 3–4 小时） |
| 风险 | **中**——搬错一行就是"悄悄改了行为"，人眼很难发现，只能靠 §6 的验证表 |
| 依赖 | P0 ✅ |
| 回滚 | `git checkout -- app.py tests/; Remove-Item orchestrator.py, tests/test_orchestrator.py` |

## 1 这一步做什么

把 `app.py` 里**固定七步管线**（`handle` / `safe_handle` 及其 6 个私有 helper）原样搬进新的 `orchestrator.py`，`app.py` 只留 UI。**不新增任何业务判断，不改任何等级、日志、文案。**

产出：

1. `orchestrator.py`（≤250 行）：`safe_run()` 唯一公开入口 + `handle()` + 6 个搬过来的私有函数 + `trace`（附加字段，P1 不渲染）。
2. `app.py`：326 行 → ≤250 行，只留 `_bridge_secrets` / `get_session_id` / `_config_gate` / `_render_history` / `_clear` / `_sidebar` / `main`。
3. `tests/pipeline.py`：新增 `pipeline_source()`（见 §5.3，**这是 P1 唯一允许改的测试文件之一**）。
4. `tests/test_fault.py:23`：一行断言跟着搬家（见 §5.3）。
5. `tests/test_orchestrator.py`（新，5 条）。

**不做**：不接 agent loop（P2）、不改 `contract_check.py`（`safe_run` 不进 11 条契约）、不动 `guardian` / `coordinator` / `memory` / `roles` / `logger`。

## 2 四个关键决策（先看，再动手）

### 2.1 `st.session_state` 摘出去：加 `state` 参数

`_mark_crisis` / `_maybe_compress` / `_effective_level` / `_log_turn` / `handle` 都读写 `st.session_state`。`orchestrator` **不许 import streamlit**（否则没法单测，也违背"编排与 UI 分离"）。

做法：这些函数各加一个 `state: dict` 参数，`safe_run(..., state=None)` 在入口处 `state = {} if state is None else state`。`app.py` 直接传 `st.session_state`（它本身是 mapping，`.get` / `[]=` 行为与 dict 一致），测试传普通 `dict`。

> **为什么不能默认成模块级全局 dict**：两次请求会共享冷却，跨会话污染。`None → {}` 每次新建，是唯一安全默认。

### 2.2 边界调用一律走**模块属性**，不许 `from x import fn`

原来 `app.py` 用 `from agent import call_llm`。搬到 `orchestrator` 后必须改成：

```python
import agent                       # ✅
resp = agent.call_llm(messages)    # ✅ 运行时取属性，monkeypatch 才生效
```

```python
from agent import call_llm         # ❌
resp = call_llm(messages)          # ❌ 名字在 import 时绑死，测试打桩打不到
```

**为什么**：`AppTest` 每次 rerun 都会重新执行脚本里的 import，所以 `from ... import` 在界面路径上恰好还能被 `monkeypatch.setattr(agent, "call_llm", boom)` 打中；但**直接调 `orchestrator.handle()` 的单测不会重新 import**，`F-01/F-02/F-07` 这类打桩会静默失效（不报错，只是不生效）。统一走模块属性，两种调用方式都正确。

`guardian` / `coordinator` / `memory` 同样按模块属性调用。常量（`CRISIS_REPLY` 之类）可以 `from`，它们不打桩。

### 2.3 `trace` 是**附加字段**，不算行为变化

`handle` 返回的 dict 加一个 `"trace": list[dict]`，每条 `{"node","status","latency_ms","detail"}`，`detail` 只放等级 / 角色 / 状态。

- P1：`app.py` **不读**它，侧栏不渲染，日志字段一个不加 → 对用户是零变化。
- P4：侧栏"本轮编排"直接渲染它，来源链接也由代码从 trace 之外的 `sources` 渲染。

> **为什么现在就加**：P1 的验收要"节点顺序没变"，没有 trace 就只能靠 `caplog` 数行数，脆且读不出顺序。加一个不渲染的字段，成本一行、收益是 P1 自己可验证。

**trace 里绝对不许出现**：用户原句、回复原文、prompt、工具返回内容。P1 就写死这条，P2 起才有工具。

### 2.4 `safe_handle` 改名 `safe_run`，`handle` 保留原名

计划书 §3.2 的公开名是 `orchestrator.safe_run(...)`。全仓只有 `app.py:309` 一个调用点（`grep safe_handle` 可验），改名成本 1 行；**`handle` 与 6 个私有函数一个都不改名**——P1 的验收标准就是 diff 里逻辑行数≈0。

## 3 搬什么：符号对照表

`app.py` 现文件 326 行，实测行号如下（**动手前先自己 `grep -n` 复核一遍，行号会随提交漂移**）：

| 符号 | 现在位置 | 搬到 `orchestrator` 后的签名 | 改动 |
|---|---|---|---|
| `FALLBACK_LINE` | `app.py:62` | 模块常量 | 原样搬走，`app.py` 不再定义 |
| `_mark_crisis` | `app.py:82-91` | `_mark_crisis(state)` | 加 `state`，`st.session_state` → `state` |
| `_log_turn` | `app.py:93-101` | `_log_turn(sid, level, role, rule_ids, action, rewrite, t0, state)` | 加 `state`（**放在最后**，前 7 个参数不动） |
| `_effective_level` | `app.py:103-112` | `_effective_level(raw, state)` | 加 `state` |
| `_maybe_compress` | `app.py:115-138` | `_maybe_compress(sid, level, role, history, t0, state)` | 加 `state` |
| `_crisis_result` | `app.py:141-150` | `_crisis_result(sid, pre, escalated, t0, state, trace)` | 加 `state` / `trace` |
| `_log_and_result` | `app.py:153-176` | `_log_and_result(sid, pre, dec, eff_level, escalated, post, resp, reply, t0, state, trace)` | 加 `state` / `trace`，dict 多 `"trace"` 键 |
| `handle` | `app.py:179-203` | `handle(text, sid, history, persona_id, state=None)` | 加 `state`，节点调用换 `_timed` |
| `safe_handle` | `app.py:206-223` | **`safe_run(text, sid, history, persona_id, state=None)`** | 改名 + 加 `state` |

**留在 `app.py`（不许搬）**：`_bridge_secrets`（:`25`）、`get_session_id`（:`70`）、`_config_gate`（:`226`）、`_render_history`（:`237`）、`_clear`（:`243`）、`_sidebar`（:`263`）、`main`（:`280`）、`SID_RE`（:`67`）、`DISCLAIMER`（:`58`）、`NET_HINT`（:`63`）、`DEFAULT_PERSONA`（:`64`）。

## 4 前置检查（开工 3 分钟）

```powershell
cd "D:\deepseek harness\xinyu-agent"
git branch --show-current                        # agent-v2
git status --short                               # 空
.\.venv\Scripts\python.exe -m pytest -q          # 132 passed
.\.venv\Scripts\python.exe contract_check.py     # 11/11 + 5/5 + 20/20
Select-String -Path app.py -Pattern "^def (handle|safe_handle)"   # 179 行 / 206 行
```

再确认三处**不能忘的现状**（搬错这三处最伤）：

1. `app.py:190-192`：冷却先读后减，`-1` 在 `enforce_cooldown` **之后**。
2. `app.py:111`：`levels` 只存 `eff if eff == "L3" else raw`（存地板抬上来的 L2 会让平静轮自己凑成第 3 次）。
3. `app.py:145-146`：聚合升级用 `aggregate_escalate`，原始 L3 用 `short_circuit`。

## 5 执行步骤

### 5.1 新建 `orchestrator.py`

先写"骨架 + 3 个 helper"，再把 §3 表里的函数**整段剪切**过来（**不要重写**，只做 §3 表里那几处机械改动）。

```python
"""orchestrator.py — 固定编排：判危 → 聚合 → 路由 → 冷却 → 事实 → prompt → 生成 → 审 → 记 → 摘要 → 日志。

[SAFE] 本模块不 import streamlit：会话状态由调用方以 mapping 传入
（app 传 st.session_state，测试传普通 dict）。顺序在本文件里是唯一事实来源；
节点内部逻辑仍留在各自模块，本文件不复制任何业务判断。
"""
from __future__ import annotations

import logging
import time

import agent
import coordinator
import guardian
import memory
from logger import log_turn, session_hash
from roles import COOLDOWN, N_WINDOW

logger = logging.getLogger(__name__)

FALLBACK_LINE = "我这边刚刚卡了一下，但我在。你可以再说一句吗？"


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _node(trace: list[dict], node: str, status: str, ms: int, detail: str = "") -> None:
    """记一步编排；detail 只准放等级/角色/状态，不放原句、不放 prompt、不放回复。"""
    trace.append({"node": node, "status": status, "latency_ms": ms, "detail": detail})


def _detail(out: object) -> str:
    """从节点返回值里挑一句可公开的说明；挑不出就返回空串。"""
    if not isinstance(out, dict):
        return ""
    parts = [str(out[key]) for key in ("level", "role") if out.get(key)]
    if "ok" in out:
        parts.append("ok" if out["ok"] else str(out.get("error") or "fail"))
    return " ".join(parts)


def _timed(trace: list[dict], node: str, fn, *args, **kwargs):
    """跑一个节点并记 trace；异常照常上抛（兜底只在 safe_run，节点层不许吞）。"""
    t0 = time.perf_counter()
    try:
        out = fn(*args, **kwargs)
    except Exception:
        _node(trace, node, "error", _ms(t0))
        raise
    _node(trace, node, "ok", _ms(t0), _detail(out))
    return out
```

搬完后 `handle` 长这样（**对照 `app.py:179-203` 逐行核**，只多了 trace 与 `state`）：

```python
def handle(text: str, sid: str, history: list[dict], persona_id: str,
           state: dict | None = None) -> dict:
    """七步固定管线；异常交给 safe_run，不在这里吞。"""
    state = {} if state is None else state
    t0, trace = time.perf_counter(), []
    facts = memory.read_memory(sid)                                   # 局部名不许叫 memory！
    pre = _timed(trace, "pre_check", guardian.guardian_pre_check, text)
    eff_level, escalated = _timed(trace, "aggregate", _effective_level, pre["level"], state)
    if eff_level == "L3":
        # [SAFE] L3 一律短路，这一轮到此为止；等级不许被后续步骤下调。
        _node(trace, "short_circuit", "ok", _ms(t0), "L3")
        return _crisis_result(sid, pre, escalated, t0, state, trace)
    dec = _timed(trace, "coordinator", coordinator.coordinator_decide, facts, text, eff_level)
    # [SAFE] 冷却/历史危机只降 guide，不碰 crisis；L3 已短路，等级不会被这里下调。
    dec = _timed(trace, "cooldown", coordinator.enforce_cooldown, dec,
                 state.get("cooldown", 0), state.get("ever_crisis", False))
    state["cooldown"] = max(0, state.get("cooldown", 0) - 1)
    lore = _timed(trace, "lore", memory.match_lore, text, sid)
    prompt = _timed(trace, "prompt", agent.build_system_prompt, persona_id, facts, lore)
    resp = _timed(trace, "generate", agent.call_llm,
                  [{"role": "system", "content": prompt}, *history[-10:]])
    post = _timed(trace, "post_check", guardian.guardian_post_check,
                  text, resp.get("text", ""), eff_level, dec["role"])
    reply = post.get("fixed_reply") or resp.get("text") or FALLBACK_LINE
    _timed(trace, "memory_write", memory.update_memory, sid, text, reply)
    _maybe_compress(sid, eff_level, dec["role"], history, t0, state)
    return _log_and_result(sid, pre, dec, eff_level, escalated, post, resp, reply,
                           t0, state, trace)
```

> **第一坑（会直接 NameError）**：原 `app.py:182` 的局部变量叫 `memory`。搬成模块属性调用后，`memory = read_memory(sid)` 会把模块 `memory` 遮住，后面 `memory.match_lore` 立刻炸。必须改名 `facts`（或用 `mem`），**这是本次唯一允许的改名**。

`safe_run`（由 `safe_handle` 改名）：

```python
def safe_run(text: str, sid: str, history: list[dict], persona_id: str,
             state: dict | None = None) -> dict:
    """任何异常都变成一句人话；日志只记类型名，不记原文与堆栈。"""
    state = {} if state is None else state
    t0 = time.perf_counter()
    try:
        return handle(text, sid, history, persona_id, state)
    except Exception as exc:                       # 边界：界面永不显示 traceback
        logger.warning("pipeline_failed session=%s error=%s", sid[:6], type(exc).__name__)
        # [SAFE] 判危失败时风险未知，按中风险记录；绝不按 L1 当“没事”。
        try:
            _log_turn(sid, "L2", "listener", ["PIPELINE_FAILED"],
                      "template_fallback", 0, t0, state)
        except Exception:                          # 边界：日志本身失败也不许抛回界面
            pass
        return {"reply": FALLBACK_LINE, "level": "L2", "role": "listener",
                "reason": "default", "degraded": True, "trace": []}
```

**唯一可观察到的文字变化**：`logger.warning` 的 logger 名从 `app` 变 `orchestrator`（`logging.getLogger(__name__)` 的结果）。结构化 JSONL 一字不变，测试也不断言 logger 名，属可接受。

### 5.2 改 `app.py`

1. 删掉 §3 表里搬走的 9 个符号（含 `FALLBACK_LINE`）。
2. import 段收缩（原 `:43-54` 那一块）：

```python
from logger import session_hash                                  # noqa: E402
from memory import clear_memory                                  # noqa: E402
from orchestrator import safe_run                                # noqa: E402  顺序要紧
from panel import LEVEL_LABELS, REASON_LABELS, ROLE_LABELS, render_panel  # noqa: E402
from resources import pick_resources                             # noqa: E402
from theme import inject_theme, theme_picker                     # noqa: E402
```

删掉的：`agent`、`coordinator`、`guardian`、`roles`、`memory` 的其余函数、`time`、`re`（`re` 若只服务 `SID_RE` 则保留）、`uuid`（`_clear` 与 `get_session_id` 还要用，保留）。

> **[SAFE] 顺序是硬约束**：`orchestrator` 在 `_bridge_secrets()`（`app.py:41`）**之后** import。`memory.DATA_DIR` 是 import 时定死的模块常量，提前 import 会让线上 Secrets 里的 `DATA_DIR` 失效。`test_f06` 与 `F-04` 直接盯着这条。

3. `main()` 里那一行（原 `:309-310`）：

```python
result = safe_run(text, sid, st.session_state.messages,
                  st.session_state.persona_id, st.session_state)
```

`st.session_state["turn"] += 1`（原 `:303`）**留在 app**：轮次计数是 UI 责任，P1 搬走它就等于改了 `_log_turn` 读到的 `turn`。

### 5.3 改两处测试（P1 唯一允许的测试改动）

**(a) `tests/pipeline.py:91`** — 新增一个读两份源码的 helper（`FALLBACK_LINE` 搬家后，原 `app_source()` 断言必然红）：

```python
def pipeline_source() -> str:
    """兜底句在 orchestrator 里，渲染在 app 里：源码级断言要看两份。"""
    return (pathlib.Path(APP).read_text(encoding="utf-8")
            + pathlib.Path(ROOT / "orchestrator.py").read_text(encoding="utf-8"))
```

**(b) `tests/test_fault.py:23`** — 一行：

```python
assert FALLBACK_LINE in pipeline.pipeline_source()   # 兜底文案与 orchestrator/app 同步
```

> 这不是"改测试凑绿"：断言的对象没变（兜底句必须出现在管线源码里），只是源码从 1 个文件变 2 个文件。**其余 131 条一个字都不许动**；动了就是行为变了，回头查 §2。

## 6 新增 `tests/test_orchestrator.py`（5 条）

直接调 `orchestrator.handle()`，不走 AppTest——这正是 §2.1 摘掉 streamlit 换来的能力。

```python
"""test_orchestrator.py — P1：编排顺序 / 兜底 / trace 不含原文 / state 跨轮。

不走 AppTest：orchestrator 不依赖 streamlit，传普通 dict 就能测。
"""
from __future__ import annotations

import json

import agent
import guardian
import orchestrator
import pipeline
from roles import COOLDOWN

MARK = "ZzqMarker9"          # 特征串：日志与 trace 里都不许出现


def test_l3_short_circuits_before_agent(monkeypatch):
    """L3 不进生成：把 call_llm 换成炸弹，跑通即证明没调。"""
    def boom(*args, **kwargs):
        raise AssertionError("L3 不许调模型")

    monkeypatch.setattr(agent, "call_llm", boom)
    res = orchestrator.handle("我不想活了", "t1", [], "sister_heart", {})
    assert (res["level"], res["role"], res["short_circuit"]) == ("L3", "crisis", True)
    assert res["reply"] == guardian.CRISIS_REPLY


def test_node_order_is_unchanged():
    """顺序即契约：少一步/多一步都算改了行为。"""
    res = orchestrator.handle("你好", "t2", [], "sister_heart", {})
    assert [s["node"] for s in res["trace"]] == [
        "pre_check", "aggregate", "coordinator", "cooldown",
        "lore", "prompt", "generate", "post_check", "memory_write"]


def test_exception_becomes_fallback_and_logged(monkeypatch):
    """生成抛异常 → 一句人话 + L2 + PIPELINE_FAILED，绝不按 L1 记。"""
    def boom(*args, **kwargs):
        raise TimeoutError()

    monkeypatch.setattr(agent, "call_llm", boom)
    res = orchestrator.handle("今天很累", "t3", [], "sister_heart", {})
    assert res["reply"] == orchestrator.FALLBACK_LINE
    assert (res["level"], res["role"], res["degraded"]) == ("L2", "listener", True)
    row = pipeline.reply_rows("t3")[-1]
    assert (row["level"], row["action"], row["rule_ids"]) == (
        "L2", "template_fallback", ["PIPELINE_FAILED"])


def test_trace_and_log_carry_no_user_text():
    """同一条特征串：trace 没有，JSONL 也没有。"""
    res = orchestrator.handle(f"{MARK} 今天有点累", "t4", [], "sister_heart", {})
    assert MARK not in json.dumps(res["trace"], ensure_ascii=False)
    blob = json.dumps(pipeline.rows("t4"), ensure_ascii=False)
    assert MARK not in blob


def test_state_threads_cooldown_across_turns():
    """同一个 state 连跑两轮：冷却真的留下来了（漏传 state 会这里红）。"""
    state: dict = {}
    orchestrator.handle("我不想活了", "t5", [], "sister_heart", state)
    assert (state["cooldown"], state["ever_crisis"]) == (COOLDOWN - 1, True)
    res = orchestrator.handle("我该怎么办", "t5", [], "sister_heart", state)
    assert (res["role"], res["reason"]) == ("listener", "after_crisis")
```

> 第 5 条是本轮最值钱的测试：`state` 漏传时，冷却只活一轮，界面上表现为"危机后第 2 轮又开始给建议"——这种退化没有任何报错，只有这条能抓。

## 7 验证（逐行跑，过不了不许进 P2）

| # | 动作 | 期望 |
|---|---|---|
| 1 | `.\.venv\Scripts\python.exe -m pytest -q` | **137 passed**（132 旧 + 5 新） |
| 2 | `.\.venv\Scripts\python.exe contract_check.py` | `11/11 + 5/5 + 20/20`（契约一步没动） |
| 3 | `.\.venv\Scripts\python.exe metrics.py` | 召回 10/10、误拦 0/20、角色 12/12、连续 10 轮 10/10 |
| 4 | `Select-String -Path app.py,orchestrator.py -Pattern "safe_handle"` | 无输出（改名成功） |
| 5 | `(Get-Content app.py).Count` / `(Get-Content orchestrator.py).Count` | ≤250 / ≤250 |
| 6 | `$env:MOCK_LLM="1"; .\.venv\Scripts\streamlit.exe run app.py` | 三轮日常正常；说"我不想活了"秒出危机卡；刷新记忆还在；清空真删 |
| 7 | `Get-Content data\logs\<今天>.jsonl \| Select-Object -Last 3` | `action` 仍是 `pass / rewrite / template_fallback / short_circuit` 四值，`aggregate_escalate` 只在聚合升级时出现；9 字段一个不多 |
| 8 | 侧栏 | 风险等级 / 角色 / 切换原因 / 轮次 与 P1 前一致 |
| 9 | `git diff --stat` | `app.py` 只减不增；`orchestrator.py` 是新增；`guardian/coordinator/memory/roles/logger` **零改动** |

存证：把 #1 #2 #3 的输出贴进 `docs/evidence/P1-orchestrator-2026-11-13.md`，附 `git diff --stat` 与一张侧栏截图。

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `NameError: name 'memory' is not defined` / `'dict' object has no attribute 'match_lore'` | 局部变量 `memory` 遮住模块名 | 改名叫 `facts`（§5.1） |
| `test_f01` 红：`FALLBACK_LINE in app_source()` | 兜底句搬到 orchestrator | 走 §5.3 两处改动 |
| `monkeypatch agent.call_llm` 不生效（测试假绿/假红） | `from agent import call_llm` | 改成 `import agent` + `agent.call_llm` |
| 危机后第 2 轮又切回 guide | app 没把 `st.session_state` 传进去，`state` 每轮新建 | `safe_run(..., st.session_state)` |
| 首屏就报缺 Key / 记忆目录不对（线上） | `orchestrator` 在 `_bridge_secrets()` 之前被 import | 把 import 挪回 `:41` 之后 |
| 侧栏轮次恒为 0 | `turn += 1` 被一起搬走了 | 留在 `app.main` |
| 日志 `turn` 全 0 | `_log_turn` 里 `state.get("turn", 0)` 但 state 没传 | 同第 4 行 |
| 日志出现第 10 个字段 | 有人往 `log_turn` 塞了 trace 信息 | 立刻删；trace 只进返回值 |
| `app.py` 反而变长 | 视图函数沉进了 orchestrator，或留了旧副本 | 旧函数整段删掉，不留"兼容" |
| C-01/C-05/C-09 之一红 | 顺序或字段变了 | 按 §3 表逐函数比对 `app.py` 原实现 |

## 9 回滚

```powershell
git checkout -- app.py tests/pipeline.py tests/test_fault.py
Remove-Item orchestrator.py, tests/test_orchestrator.py
.\.venv\Scripts\python.exe -m pytest -q        # 回到 132
```

P1 是零行为变更，回滚不该有任何副作用；如果回滚后测试不绿，说明有别的东西被改了，先 `git status` 看清楚。

## 10 出口清单

- [ ] 137 passed；契约 `11/11 + 5/5 + 20/20`；四指标不变
- [ ] `app.py` ≤250 行；`orchestrator.py` ≤250 行；`safe_handle` 全仓 0 处
- [ ] `guardian.py` / `coordinator.py` / `memory.py` / `roles.py` / `logger.py` **零 diff**
- [ ] 日志 9 字段与 action 四值实测无变化；侧栏显示与 P1 前一致
- [ ] `trace` 节点顺序 = 9 个节点；trace 与 JSONL 都不含特征串
- [ ] 证据落 `docs/evidence/P1-orchestrator-YYYY-MM-DD.md`
- [ ] `CLAUDE.md` §2.2 的 P1 改 ✅，§4 加一行结果

## 11 回执

```text
P1 完成：137 passed（132+5）/ 契约 11+5+20 / app.py 326→___ 行 / orchestrator ___ 行
trace 9 节点顺序一致 / 日志 9 字段与四值不变 / 冷却跨轮生效
下一步：P2 tools.py + agent_loop.py（先接 echo / fake_search 假工具）
```
