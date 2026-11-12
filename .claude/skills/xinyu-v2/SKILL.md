---
name: xinyu-v2
description: 实现《心屿 MindIsle》v2「编排式单 Agent」时使用（分支 agent-v2，工作区 D:\deepseek harness\xinyu-agent）。涉及抽取 orchestrator.py、手写 agent_loop.py 工具循环、tools.py 白名单与预算、web.py 网络工具、guardian 工具门禁、侧栏「本轮编排」trace、style.py 口吻层、DeepSeek tools 能力探测、P0–P6 阶段验收时先加载本技能。维护 v1 基线（guardian / RULES / memory 白名单 / 契约）改看 xinyu-dev。
---

# 心屿 v2 开发技能（编排式单 Agent）

## 先读哪里：按阶段读，不要一次读完

| 你现在要做的事 | 读取 |
|---|---|
| 新会话：确认阶段与出口 | `.claude/CLAUDE.md` §2.2 状态表 + §4 进度；本文件 §0 §1 |
| P0 复跑基线 / 探测 DeepSeek `tools` | §2 |
| P1 把 `handle` / `safe_handle` 搬进 `orchestrator.py` | §3 |
| P2 写 `tools.py` / `agent_loop.py`（假工具） | §4 |
| P3 写 `web.py`（搜索 / 图片 / 风格包） | §5 |
| P4 接 `guardian_tool_check` + 侧栏 trace | §6 |
| P5 写 `style.py`（口吻 / 句尾 / 贴纸） | §7 |
| P6 回归 / 材料 / 演示 | §8 |
| 报错、测试红、行为变了 | §9 |
| 想加依赖 / 想换框架 / 想让它"更自主" | §10 |

**本文件不维护状态。** 进度只看 `.claude/CLAUDE.md`；本文件只讲"怎么做、做到什么算过、哪里会踩坑"。

## 0. 这个技能管什么

一句话架构：

```text
app.py（纯 UI）→ orchestrator.safe_run()
   → guardian_pre_check（本地规则，L3 直接返回，0 工具 0 LLM）
   → coordinator_decide（定 role）
   → 工具可用性判定（代码决定这一轮允许什么）
   → agent_loop.run_agent（≤3 步，模型决定答还是调工具）
   → guardian_post_check（规则 + 复核 + 一票否决）
   → style（口吻层，L3 与模板兜底不碰）
   → 日志 + trace + 回复
```

四条不变式（改了就是另一种系统，不是 v2）：

1. **L3 永不进 loop**：`guardian_pre_check` 在编排最前面短路，断网也要出本地模板 + 资源卡。
2. **代码定边界，模型定用不用**：工具白名单在代码里；模型不能发明工具、不能给 URL。
3. **guardian 在循环外**：不参与协商、不被工具结果说服、不降等级。
4. **记忆仍由 `update_memory` 写**：agent 只产文本，8 字段白名单与 `scrub` 不动。

## 1. 全局硬规则（每一步都适用）

- **不加依赖**。HTTP 用标准库 `urllib.request`；不许 `requests` / `httpx` / 任何 SDK。`requirements.txt` 不变。
- **不改这五样**：`roles.RULES` 20 条、`CRISIS_REPLY` / `SAFE_FALLBACK` 逐字、`memory` 8 字段白名单、`coordinator` 角色判定、`logger` 9 字段。要动先问。
- **契约先不变**：P1–P5 不动 `contract_check.py` 的 11 条；`run_agent` 若升级为第 12 条契约，单独一轮改并同步材料。
- **测试不联网**：LLM 用 `MOCK_LLM=1`，HTTP 用注入的假 transport（`opener=` / `fetch=` 参数），不许 `monkeypatch` 真实域名。
- **异常不出界面**：所有边界失败 → `ok=False` + 兜底话术 + 一行日志（类型名，不记原文、不记堆栈）。
- **行数预算**：`orchestrator.py` ≤250、`agent_loop.py` ≤180、`tools.py` ≤200、`web.py` ≤250、`style.py` ≤180；`app.py` 只许降不许涨。
- **每步都验**：`pytest -q` 全量 + `python contract_check.py` + 手动跑一条日常、一条 L3。**不许"先红着，最后一起修"。**

## 2. P0：基线复跑 + tools 探测

### 2.1 复跑（迁移后必须先证明无损）

```powershell
.\.venv\Scripts\python.exe -m pytest -q                      # 期望 132 passed
.\.venv\Scripts\python.exe contract_check.py                 # 期望 11/11 + 5/5 + 20/20
.\.venv\Scripts\python.exe metrics.py                        # 四条指标，数字抄进 docs/evidence/
```

数字与 v1.0 基线（132 / 11+5+20 / 召回 10/10 / 误拦 0/20 / 角色 12/12 / 连续 10 轮 10/10）任一不符，先查环境（`py -3.11`、`.venv`、`.env`），不要改代码去凑。

### 2.2 探测 DeepSeek 是否支持 `tools`

写 `docs/evidence/probe_tools_2026-11-12.py`（一次性脚本，可重跑，**不含任何用户数据**）：

- 一个最小 `client.chat.completions.create(model=..., messages=[...], tools=[一个无副作用 echo], tool_choice="auto", timeout=15, max_retries=0)`。
- 三个断言分别打印：①请求是否 200；②`finish_reason` 是否 `tool_calls`；③`message.tool_calls[0].function.arguments` 是否为合法 JSON。
- 用一个**明确要求调工具**的 prompt（"请调用 echo 工具回显 hello"），否则模型多半直接答，探测会假阴性。
- 结果写 `docs/evidence/P0-tools-probe.md`：日期、model、三条结果、原始返回片段（**只贴结构，不贴 key**）。

### 2.3 判定与分叉

| 结果 | 走法 |
|---|---|
| `tool_calls` 正常、arguments 可解析 | 标准路径：`agent.chat_with_tools` 按 OpenAI 协议回填 |
| `finish_reason` 永远 `stop`，无 `tool_calls` | 先换 prompt 再判（见 2.2 的坑），仍不行 → 走 JSON 动作协议兜底 |
| 400 / `tools` 不支持 | 同上走 JSON 动作协议；`agent_loop` 的对外接口不变 |
| 401 / 网络不通 | 先修 key 与网络，不要据此判定"不支持" |

**JSON 动作协议**（兜底方案，接口不变）：system 里附一段"需要资料时只输出 `{"action":"tool","name":..,"args":{..}}`，不需要就正常回答"；`agent_loop` 解析失败按"直接回答"处理并记 `degraded`，**不许**把裸 JSON 当回复发给用户。

### 2.4 出口

- [ ] 探测脚本 + 结论 md 进 `docs/evidence/`
- [ ] 132 passed、契约 11/11 + 5/5 + 20/20、metrics 四条数字记录在案
- [ ] `git grep` 无旧工作区绝对路径（`心理委员`）残留
- [ ] `CLAUDE.md` §2.2 的 P0 改 ✅、§4 加一行结果

## 3. P1：`orchestrator.py` 抽取（零行为变化）

### 3.1 搬什么

从 `app.py` **原样搬**（不改逻辑、不改顺序、不改日志字段）：

| 搬走 | 现在位置 |
|---|---|
| `handle` / `safe_handle` | `app.py:179-223` |
| `_crisis_result` / `_log_and_result` | `app.py:141-176` |
| `_log_turn` / `_effective_level` / `_maybe_compress` | `app.py:93-139` |
| `_mark_crisis` | `app.py:82-91` |

`app.py` 留下的：`_bridge_secrets` / `get_session_id` / `_config_gate` / 渲染 / 侧栏 / `main`。页面里只留一行 `result = orchestrator.safe_run(text, sid, history, persona_id, st.session_state)`。

### 3.2 关键决策：把 Streamlit 摘出去

`_mark_crisis` / `_maybe_compress` / `handle` 里读写 `st.session_state`（`cooldown` / `ever_crisis` / 摘要计数）。`orchestrator` **不许 import streamlit**（否则没法单测、也违背"编排与 UI 分离"）。

做法：加一个 `state: dict` 参数，默认 `None → {}`。`st.session_state` 本身就是 mapping，`app.py` 直接传进去，行为等价；测试传普通 `dict`。所有 `st.session_state.get(k, d)` 改成 `state.get(k, d)`，`state[k] = v` 原样。

### 3.3 三个自检（P1 的"零变化"就靠它们）

1. **顺序**：读记忆 → 判危 → 聚合 → 短路判断 → 定角色 → 冷却 → lore → prompt → 生成 → 审 → 记忆 → 摘要 → 日志。少一步或多一步都算改行为。
2. **日志**：`_log_turn` 的 9 字段与 `action` 四值（`pass / rewrite / template_fallback / short_circuit`，聚合时 `aggregate_escalate`）一字不改。
3. **返回 dict**：`reply / level / role / reason / degraded`（危机分支多 `short_circuit`），字段名不许动，`app.py` 的渲染与侧栏依赖它。

### 3.4 测试

`tests/test_orchestrator.py` 至少四条：

- L3 输入 → `short_circuit=True`、`role=crisis`、**不调 agent**（monkeypatch `agent.call_llm` 为抛异常，跑通即证明没调）；
- 普通输入 → 顺序正确（用 `caplog` 或 trace 断言节点顺序）；
- `agent.call_llm` 抛异常 → 返回 `FALLBACK_LINE`，`degraded=True`，日志有 `PIPELINE_FAILED`；
- trace / 日志不含用户原文（输入一个特征串，断言日志文本里搜不到）。

### 3.5 本步的坑

- **别顺手改名**：`_log_turn` 搬过去就还叫 `_log_turn`。P1 的验收标准是 diff 里的逻辑行数≈0。
- **别在 app.py 留副本**：两处 `handle` = 迟早改一处忘一处，测试也测不到界面那份。
- **`st.session_state` 的默认值**：`get(k, 0)` 与 `get(k) or 0` 不等价，搬的时候照抄原写法。
- **`_config_gate` 留在 app**：它在页面启动时跑，不属于编排。

## 4. P2：`tools.py` + `agent_loop.py`（先接假工具）

### 4.1 `tools.py` 骨架

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str; description: str; parameters: dict      # JSON schema
    timeout_s: float = TOOL_TIMEOUT_S
    max_bytes: int = TOOL_MAX_BYTES
    trusted: bool = False                              # 一律 False，除纯本地计算

@dataclass
class ToolResult:
    ok: bool; data: object = None; error: str = ""
    source: str = ""; latency_ms: int = 0
```

- `REGISTRY: dict[str, ToolSpec]` + `_HANDLERS: dict[str, Callable]`，注册用 `register(spec, fn)`；**没有动态导入、没有插件发现、没有装饰器魔法**。
- `list_for_turn(role, level, allow_web) -> list[dict]`：返回 OpenAI `tools` 数组；L3 或 `allow_web=False` 时返回 `[]`。
- `execute(name, args) -> ToolResult`，七道关，任一不过就 `ok=False` 直接返回：

```text
1 白名单：name not in REGISTRY → error="unknown_tool"
2 schema：必填齐、类型对、无多余键 → error="bad_args"（手写校验，不引 jsonschema）
3 参数清洗：字符串先 scrub()；长度上限；不许出现 http(s):// 或 file:// 或 ../
4 预算：超 TOOL_TIMEOUT_S / TOOL_MAX_BYTES → error="budget"
5 执行：try/except 包住，任何异常 → error=类型名（不记参数）
6 归一化：data 截断到 max_bytes，非 JSON 可序列化对象一律 str
7 记账：latency_ms；日志只写 name/ok/ms/条数
```

**假工具先写两个**：`echo(text)`（回显，用于测回路）与 `fake_search(query)`（返回两条固定假结果 + 假来源，用于测"一次工具后答"）。它们**只在测试与 P2 调试启用**，`AGENT_LOOP` 生产路径不注册。

### 4.2 `agent_loop.py`

```python
def run_agent(system_prompt, history, tools, max_steps=AGENT_MAX_STEPS) -> AgentResult
```

循环骨架（照这个写，别自创）：

```text
messages = [{"role":"system","content":system_prompt}, *history[-10:]]
deadline = now() + AGENT_TOTAL_TIMEOUT_S
tool_calls_used = 0
for step in range(max_steps):
    if now() > deadline: return fallback("timeout")
    resp = agent.chat_with_tools(messages, tools)
    if not resp["ok"]: return fallback(resp["error"])
    msg = resp["message"]
    if not msg.get("tool_calls"): return AgentResult(text=msg["content"], ...)   # 直接答
    messages.append(msg)                     # 必须原样回填 assistant 消息
    for call in msg["tool_calls"]:
        if tool_calls_used >= AGENT_MAX_TOOL_CALLS: return fallback("tool_budget")
        r = tools.execute(call.function.name, parse_json(call.function.arguments))
        messages.append({"role":"tool","tool_call_id":call.id,
                         "content": json.dumps(r.data)[:TOOL_MAX_BYTES]})
        tool_calls_used += 1
return fallback("max_steps")                 # 步数用完还没答 → 兜底，不再试
```

- `max_steps` 用**参数**而非直接读常量，测试才好传 1 / 99。
- 返回 `AgentResult{text, tool_calls, trace, usage, ok}`；`trace` 每步一条 `{node:"agent",status,latency_ms,detail}`，`detail` 只放工具名与条数。
- 超预算统一走 `FALLBACK_LINE` 或调用方给的 `fallback_text`，**不许把中间态（半截答案 + 工具原文）发给用户**。

### 4.3 `agent.chat_with_tools`

- 新增，内部函数；`call_llm` 签名不动（guardian 复核与摘要还在用）。
- `MOCK_LLM=1` 时按"无工具直接答"返回，**不发请求**；测试靠参数注入假响应，别依赖 mock 分支。
- 不支持 tools 的错误（400 / `unsupported`）→ `ok=False, error="tools_unsupported"`，**不静默降级成普通问答**（否则 P0 的结论白做）。
- `timeout=15, max_retries=1`，与 `call_llm` 一致。

### 4.4 六条用例（P2 的出口，一条都不能少）

| 用例 | 断言 |
|---|---|
| 无工具直接答 | `tool_calls == []`，`text` 原样 |
| 一次工具后答 | 第二步返回文本；`tool_calls` 长度 1；tool 消息带 `tool_call_id` |
| 步数超限 | `max_steps=2` 且模型每步都调工具 → `ok=False`/兜底，`trace` 长度 == 2 |
| 工具报错 | 工具抛异常 → `ok=False, error=类型名`，循环继续到下一步或兜底，不崩 |
| 未知工具 | `execute("rm_rf")` → `ok=False, error="unknown_tool"`；`list_for_turn` 里不存在 |
| L3 不循环 | `level=L3` → `run_agent` 根本不被调用（monkeypatch 断言） |

### 4.5 本步的坑

- **assistant 消息必须原样回填**（含 `tool_calls` 与 id），否则第二步 400。
- **`arguments` 是字符串不是 dict**：`json.loads` 套 `try/except`，坏 JSON → `bad_args`，不许直接 `**args`。
- **一轮多个 tool_call**：DeepSeek 可能一次给 2 个，`AGENT_MAX_TOOL_CALLS` 要在**调用前**判，别先执行再判。
- **别用 `while True`**：所有循环必须有 `range(max_steps)` 与 deadline 两道闸。
- **工具结果别塞整页 HTML**：截断在前，`json.dumps` 在后。

## 5. P3：`web.py`（网络工具）

- 只用 `urllib.request`；`Request(headers={"User-Agent": ...})`，`timeout=TOOL_TIMEOUT_S`。
- 读响应**边读边截断**（`resp.read(TOOL_MAX_BYTES + 1)`，超了直接判 `too_large`），不要先 `read()` 再判长度。
- 返回前过 schema：`{"items":[{"title","url","snippet"}], "source": ...}`；字段缺/类型错 → `bad_payload`。
- URL 只允许 `https://`，且**只允许代码里写死的主机**（provider 域名），模型给的 URL 一律拒绝。
- 日志：`tool=web_search ok=1 ms=820 n=5`；**不写 query，不写 URL 参数**。
- 错误分类（测试逐个覆盖）：`timeout` / `http_401` / `http_429` / `bad_json` / `too_large` / `empty` / `bad_url`。
- 测试注入 `fetch=` 假函数返回构造的 bytes，不 monkeypatch 网络。
- P3 前置：provider / key 未定就**只写接口与假实现**，别先接一个要注册的搜索 API。

## 6. P4：工具门禁 + 侧栏「本轮编排」

`guardian_tool_check(name, args) -> {"allow": bool, "reason": str}`：纯本地、不调 LLM、只查表：

| 条件 | 结果 |
|---|---|
| `name` 不在 `REGISTRY` | 拒，`unknown_tool` |
| 本轮 role 为 `crisis` 或 level L3 | 拒，`crisis_no_tool` |
| args 含 URL / 路径 / 超长 | 拒，`bad_args` |
| 其余 | 放行，`ok` |

- 接在 `agent_loop` **每次 `tools.execute` 之前**（双保险：loop 里也判一次），拒了就回一条 `ok=False` 的 tool 消息，让模型改用已有信息作答；**不许**因此改 role 或降 level。
- 侧栏「本轮编排」用 `st.expander` 渲染 `trace`：节点名 / 状态 / 毫秒 / 一句 detail。**不放用户原句、不放工具原文、不放 prompt**。
- 来源链接由代码从 `ToolResult.data` 渲染成 `st.markdown("[标题](url)")`；**不让模型在正文里写 URL**。

## 7. P5：`style.py`（口吻层）

- 位置：`guardian_post_check` **之后**，只对 `post["pass"] and not post["template_fallback"]` 且 `level != "L3"` 生效。
- `polish(text, persona, level) -> str`：去句尾句号、按人设调句长、必要时加一个贴纸；**只做替换与截断，不新增事实、不新增建议**。
- L3 / 模板兜底 / `FALLBACK_LINE`：**逐字返回，一个字符都不许改**（测试直接 `assert out == CRISIS_REPLY`）。
- 贴纸白名单（≤8 个），按 level 分档；L2 不给贴纸，L3 永不给。
- `tone_hint(persona) -> str` 拼进 system prompt 的风格区，不改安全区。
- 测试：L3 逐字不变、L1 口语化（无句尾句号）、L2 稳重（不加贴纸）、prompt 预算不超。

## 8. P6：回归 / 材料 / 演示

- 全量：`pytest -q`（150+）+ 契约 + metrics 四条；数字抄进 `docs/evidence/`。
- 手工场景：5 人设 × 3 轮、时事提问带来源、情绪倾诉不检索、L3 断网出卡、5000 字输入、刷新、清空、错误 key。
- 破坏性验证三条（做完记日志）：删 L3 短路 → `test_l3_never_calls_agent` 红；`MAX_STEPS=99` → 步数用例红；删白名单 → 未知工具用例红。
- 材料：PPT 加一张编排图；docx 数字回填；视频重录时把"132 条测试 / 12 模块"改成实际值；提交包加 5 个新文件与测试。
- 术语：一律"编排式单 Agent"，不写 multi-agent；不写"能识别所有危机"。

## 9. 常见故障

| 现象 | 先查 |
|---|---|
| 第二步 400 `tool_call_id` 相关 | assistant 消息是否原样回填、tool 消息是否带同一个 id |
| 模型永远不调工具 | prompt 是否明确要求、`tools` 是否为空、`tool_choice` 是否 `none` |
| 模型一直调工具不回答 | 是否有 `max_steps` 闸；tool 结果是否太长把上下文挤爆 |
| 测试偶发红 | 是否有真实网络/时间依赖；`MOCK_LLM` 是否漏设 |
| P1 后行为变了 | 顺序、日志 `action`、返回字段三处自检（§3.3） |
| 侧栏 trace 打不开 | `st.expander` 里是否渲染了不可序列化对象 |
| 行数超预算 | 先拆函数；拆完还超再拆文件，别删注释凑数 |

## 10. 不要做的事

- 不换框架：LangChain / LangGraph / 任何 agent 编排库。循环是手写的，这是项目卖点之一。
- 不做多 agent 协商、不做共享黑板、不做"让模型自己决定角色"。
- 不给 agent 加 shell / 文件 / 任意 URL 工具，哪怕"只是调试"。
- 不把工具的 `trusted` 改成 True 来绕过审查。
- 不因为"演示好看"放宽 L3 短路或预算上限。
- 不在同一轮同时改契约与业务；不在 P1 顺手重构 guardian。
