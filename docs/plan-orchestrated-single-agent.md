# 心屿 · 编排式单 Agent 计划书

- 版本：v0.1（计划稿）
- 日期：2026-11-12
- 状态：**方向已定，未动代码**
- 关系：本文件取代 [`docs/plan-orchestration-A.md`](plan-orchestration-A.md) 中“只做多角色编排、不做 agent loop”的部分；A 的职责边界与安全约束继续保留。
- 一句话：**代码守住安全顺序，模型只在一个受控的工具循环里决定“这次怎么回答”；`guardian` 始终在循环外一票否决。**

## 1. 目标与非目标

### 目标

1. 把 `app.py` 的固定七步管线抽成显式的 `orchestrator.py`，编排在代码、界面和材料里都可见。
2. 在“生成”这一步引入**一个**主 agent：它可以调用白名单工具，最多循环 2–3 步，然后给出最终回复。
3. 工具先做接口与假实现，再接网络检索；网络 provider / MCP / key 另行决定，不在本文件里定。
4. `guardian` 从“只审最终回复”升级为“审工具调用 + 审最终回复”，仍然是否决权唯一。
5. L3 危机路径在 agent loop 之前短路，断网也出资源卡。
6. 保留现有 11 个契约、8 字段记忆、20 条规则、132 条测试作为重构基线。

### 非目标

- 不做自由多 agent、不做 agent 之间互相协商、不做共享黑板。
- 不引入 LangGraph / LangChain / 消息总线 / 新数据库。
- 不让 agent 自己写 `memory.json`，不让 agent 自己决定 listener / guide / crisis。
- 不让 agent 直接访问任意 URL、shell、本地文件或密钥。
- 本轮不决定搜索/图片 provider，不决定 MCP 是否必须；这些等网络方案讨论后再定。
- 不重写 `RULES`、`CRISIS_REPLY`、`SAFE_FALLBACK`、`memory` 白名单。

## 2. 目标架构

```text
用户输入
  → app.py（纯 UI）
  → orchestrator.safe_run()
      → guardian_pre_check（本地规则，0 网络）
          → L3：本地 CRISIS_REPLY + 资源卡，直接返回，0 工具
      → coordinator_decide（定角色 listener / guide / crisis）
      → 工具可用性判定（代码决定“这一轮允许哪些工具”）
      → agent_loop.run_agent()
          ├─ 模型决定：直接回答 / 调工具
          ├─ tools.execute()（白名单、schema、超时、大小上限）
          ├─ 工具结果作为“不可信资料”回填
          └─ 最多 MAX_STEPS 步，超限走兜底
      → guardian_post_check（规则 + LLM 复核/重写 + 一票否决）
      → style（口吻 / 句尾 / 贴纸：后续实施）
      → 日志 + trace + 回复
```

### 节点职责

| 节点 | 职责 | 明确禁止 |
|---|---|---|
| `guardian_pre_check` | 本地规则判危、分级 | 不联网、不调 LLM |
| `coordinator_decide` | 定角色 | 不判内容安全、不选工具 |
| 工具可用性判定 | 决定这一轮允许哪些工具 | 不替模型写答案 |
| `agent_loop` | 模型在授权工具内决定是否调用、调用几次 | 不决定角色、不绕过 guardian |
| `tools` | 执行白名单工具、校验参数、限制大小/超时 | 不接受任意 URL、不读本地文件 |
| `guardian_post_check` | 最终回复审查、重写、兜底 | 不改角色、不降等级 |
| `style` | 口吻、句尾、贴纸 | 不碰 L3 / 模板兜底 / 安全区 |
| `orchestrator` | 固定顺序、异常兜底、trace | 不复制节点内部业务逻辑 |
| `app.py` | 页面、聊天区、侧栏、渲染 | 不直接调 LLM、不写业务判断 |

### 关键原则

1. **L3 先于一切工具**：`guardian_pre_check` 在 agent loop 之前；L3 不允许任何工具调用。
2. **代码决定工具边界，模型决定是否使用**：模型不能自己发明工具，也不能访问授权外的东西。
3. **`guardian` 在循环外**：它不是 agent，不参与协商，不被工具结果说服。
4. **工具结果不可信**：只作为资料，不作为指令；来源链接由代码渲染，不让模型编 URL。
5. **记忆写入仍由代码做**：agent 只生成文本，`update_memory` 仍走白名单与 `scrub`。

## 3. 核心接口

### 3.1 数据结构

建议用轻量 dataclass 或 TypedDict，不建 base class / 注册表框架：

```text
ToolSpec:
  name: str
  description: str
  parameters: dict          # JSON schema
  timeout_s: float
  max_bytes: int
  trusted: bool             # 工具输出是否可信；默认 False

ToolResult:
  ok: bool
  data: dict | list | str
  error: str
  source: str               # 来源标识，不写用户原文
  latency_ms: int

AgentResult:
  text: str
  tool_calls: list[dict]
  trace: list[dict]
  usage: dict
  ok: bool

TraceStep:
  node: str
  status: str
  latency_ms: int
  detail: str               # 只放工具名/条数/状态，不放原句
```

### 3.2 函数边界

- `agent.call_llm(messages, temperature=0.7)`：**保持原签名**，继续给 `guardian` 复核/重写和摘要用。
- `agent.chat_with_tools(messages, tools, temperature=0.7)`：新增内部函数，封装 DeepSeek 的 tool calling；不支持 tools 时返回明确错误，不静默降级。
- `agent_loop.run_agent(system_prompt, history, tools, max_steps=3)`：主 agent 循环，返回 `AgentResult`。
- `tools.execute(name, args)`：白名单执行器；`tools.list_for_turn(...)` 决定这一轮可用的工具。
- `guardian.guardian_tool_check(name, args)`：工具调用前的本地门禁；不调 LLM。
- `orchestrator.safe_run(text, sid, history, persona_id)`：编排入口；异常统一走 `FALLBACK_LINE`。

**契约策略**：阶段 2 先不动 11 个契约，`run_agent` 用测试锁接口；如果它成为跨模块稳定 API，再评审是否加入 `contract_check`（变成 12/12），并同步材料。不要一边改契约一边改业务。

### 3.3 预算

```text
AGENT_MAX_STEPS = 3
AGENT_MAX_TOOL_CALLS = 2
AGENT_TOTAL_TIMEOUT_S = 20
TOOL_TIMEOUT_S = 6
TOOL_MAX_BYTES = 2_000_000
```

所有预算进常量区，测试断言“超限会停”，不靠模型自觉。

## 4. 分阶段实施

| 阶段 | 做什么 | 出口 | 预估 |
|---|---|---|---|
| **P0 基线 / 能力探测** | 拉分支；跑 132 + 契约；用一条最小请求探测 DeepSeek 是否支持 `tools`；冻结当前 v1.0 为回退 | 探测结果写进证据；基线全绿 | 0.5–1 天 |
| **P1 orchestrator 抽取** | 把 `handle()` / `safe_handle()` 从 `app.py` 搬到 `orchestrator.py`；app 只留 UI | 行为零变化；132 passed；契约全绿；C-01/C-05/C-09 不变 | 1 天 |
| **P2 接口 + agent loop（假工具）** | 新增 `agent_loop.py`、`tools.py`；实现 `chat_with_tools` / `run_agent`；先接 echo / fake_search 工具；加 `test_agent_loop.py` | 无工具直接答、一次工具后答、步数超限、工具报错、未知工具、L3 不循环 | 2–3 天 |
| **P3 网络工具** | 新增 `web.py`：搜索 / 图片 / 风格包；provider、MCP、key 按网络方案定；先接一个真实搜索做 smoke test | 真实检索成功；超时/401/坏 JSON 有兜底；日志不写 query | 2–4 天（待网络决策） |
| **P4 guardian 工具门禁 + trace UI** | `guardian_tool_check` 接进 loop；侧栏“本轮编排”；来源展示 | 越权工具被拦；trace 不含原文；来源链接由代码渲染 | 1–2 天 |
| **P5 风格层** | `style.py`：`CHAT_STYLE`、句尾、贴纸；接在 guardian 之后 | L3 模板逐字不变；L2 稳重；L1 口语化；贴纸不越界 | 2 天（可并行） |
| **P6 回归 / 材料 / 演示** | 全量测试；手工 5 人设；时事/断网/危机；docx/PPT/视频/提交包；CLAUDE.md | Gate A 仍成立；v2.0 可演示 | 3–5 天 |

**总工期**：单人约 10–16 个工作日；6 人队可并行，但联调、测试、材料仍是瓶颈。如果截止日期很近，建议先做 P0–P2 的“agent-lite”，网络和风格层后置，不要一次性推翻已交付版本。

## 5. 测试计划

### 回归基线

- P1 结束：`pytest -q` **132 passed**；`contract_check` **11/11 + 5/5 + 20/20**。
- P2 起每阶段都跑全量；不允许“先红着，最后一起修”。

### 新增测试

| 文件 | 覆盖 |
|---|---|
| `tests/test_orchestrator.py` | L3 不调 agent / 不调工具；异常走 `FALLBACK_LINE`；节点顺序；trace 不含原文 |
| `tests/test_agent_loop.py` | 直接回答；一次工具后回答；`MAX_STEPS` 停止；未知工具拒绝；工具超时/坏 JSON；guardian 否决后走兜底 |
| `tests/test_tools.py` | 白名单；参数 schema；超时；大小上限；不允许用户 URL；失败返回 `ok=False` |
| `tests/test_web.py`（P3） | 假 transport：成功 / 超时 / HTTP 错误 / 坏 JSON / 超大响应 / 空结果；L3 零网络 |
| `tests/test_style.py`（P5） | 句尾句号、L3 模板逐字不变、贴纸门禁、prompt 预算 |

### 破坏性验证

至少做三次：

1. 删掉 `L3` 短路 → `test_l3_never_calls_agent` 红；
2. 把 `MAX_STEPS` 改成 99 → `test_max_steps_stops` 红；
3. 去掉工具白名单 → `test_unknown_tool_rejected` 红。

### 手工场景

- 5 人设 × 3 轮日常：有口语、无句尾句号、无越界贴纸；
- “今天有什么新闻” → 检索 → 带来源；
- 情绪倾诉 → 不检索；
- L3 → 本地模板 + 3 张资源卡，0 工具；
- 断网 → 普通轮兜底、L3 仍出卡；
- 5000 字输入；刷新；清空；错误 key。

## 6. 安全与隐私

- **L3 永不进 agent loop**：`guardian_pre_check` 在编排最前面；L3 直接返回本地模板。
- **工具白名单**：只允许 `web_search`、`fetch_image`、`style_pack` 等代码注册的工具；禁止 shell、文件、任意 URL。
- **参数校验**：工具名和参数走 schema；不把用户原文当 URL；查询先 `scrub`。
- **输出不可信**：工具返回只作为资料；不执行其中的指令；来源链接由代码渲染。
- **预算**：步数、工具次数、单次超时、总超时、返回大小全部有上限。
- **记忆**：agent 不写 `memory.json`；仍由 `update_memory` 走 8 字段白名单。
- **日志**：9 字段；只记工具名/状态/耗时/条数，不记 query、不记工具原文。
- **危机模板**：`CRISIS_REPLY` / `SAFE_FALLBACK` 逐字不变；风格层与 agent 都不得改写。
- **演示降级**：网络失败、模型失败、工具失败都有固定话术；不把异常冒到界面。

## 7. 代码落点与预算

| 文件 | 变化 | 目标 |
|---|---|---|
| `orchestrator.py`（新） | 搬入 `handle` / `safe_handle`；固定编排；trace | ≤250 行 |
| `agent_loop.py`（新） | `run_agent`、步数/工具预算、工具结果回填 | ≤180 行 |
| `tools.py`（新） | `ToolSpec` / `ToolResult` / 白名单 / schema / 执行 | ≤200 行 |
| `web.py`（P3 新） | 搜索 / 图片 / 风格包；HTTP、超时、大小、schema | ≤250 行 |
| `style.py`（P5 新） | `CHAT_STYLE`、`polish`、`tone_hint`、贴纸 | ≤180 行 |
| `app.py` | 只留 UI；调用 orchestrator；侧栏 trace | 326 → ≤250 行 |
| `agent.py` | 保留 `call_llm`；新增 `chat_with_tools` | ≤300 行 |
| `guardian.py` | 新增 `guardian_tool_check`；最终审查不变 | ≤350 行 |
| `tests/` | 新增 3–4 个测试文件 | 132 → 150+ |

不改：`roles.py` 的 RULES / 安全区、`memory.py` 的 8 字段、`coordinator.py` 的角色判定、`resources.py` 的资源卡、`logger.py` 的 9 字段。

## 8. 演示与材料

- PPT/报告加一张“编排式单 Agent”图：`规则门 → 路由 → 主 agent（工具循环）→ guardian → style`。
- 演示脚本加三段：
  1. 日常聊天：无工具、口语化；
  2. 时事提问：检索 → 来源；
  3. 危机：断网仍出本地资源卡，0 工具。
- 视频重录时把“132 条测试 / 12 个模块”改成实际数字。
- 提交包加 `orchestrator.py` / `agent_loop.py` / `tools.py` / `web.py` / `style.py` 与对应测试。
- `docs/plan-orchestration-A.md` 保留为历史决策；本文件为准。
- 实施完成后回填 `.claude/CLAUDE.md` §2.2 / §4，并更新 `docs/report_build.py` / `docs/slides_build.py` 的数字。

## 9. 风险与回滚

| 风险 | 影响 | 对策 |
|---|---|---|
| DeepSeek 不支持 `tools` | agent loop 无法用标准 tool_calls | P0 先探测；不支持则用 JSON 动作协议，或退回 A+ |
| 多步循环慢 | 演示超时 | `MAX_STEPS=3`、总超时 20s、固定兜底 |
| 非确定 | 演示路径不可复现 | 保留固定降级路径；关键场景用 MOCK 录制备份 |
| 工具注入 | 模型被检索结果带偏 | 工具结果标为不可信；guardian 工具门禁 + 最终否决 |
| 越权工具 | 安全/隐私事故 | 白名单、schema、禁止用户 URL、参数 `scrub` |
| app.py 超 350 行 | 违反技术红线 | P1 先抽 orchestrator；渲染细节继续下放 |
| 测试/材料过期 | 报告数字不实 | P6 统一回填；不先改材料假装完成 |
| 范围滑向多 agent | 工期失控 | 本计划只做单 agent；multi-agent 另立计划 |

**回滚**：保留 `v1.0` 分支/tag；agent loop 用 feature flag（`AGENT_LOOP=0/1`）控制，默认可以先关；出问题直接关 loop，走原 `call_llm` 管线。P1 的 orchestrator 抽取是零行为变更，可单独回滚。

## 10. 待确认

1. P0 的 DeepSeek `tools` 探测结果——决定 agent loop 用标准 tool_calls 还是 JSON 动作协议。
2. 网络检索方案（provider / MCP / key）——P3 的前置条件；未定之前只做假工具。
3. MVP 工具集：先只做 `web_search`，还是同时做 `fetch_image` / `style_pack`。
4. 风格层 P5 是否与 agent loop 并行，还是等 loop 稳定后再做。
5. 契约策略：`run_agent` 保持内部接口，还是升级为第 12 条契约（12/12）。
6. 材料同步范围：docx / PPT / 视频 / 提交包是否全部重做。

## 11. 变更记录

- 2026-11-12：创建 v0.1；确定“编排式单 Agent”，网络检索与 provider 待定，未改代码。
