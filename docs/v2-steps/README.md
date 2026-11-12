# v2-steps/ · 编排式单 Agent 分步执行手册

- 依据：[`docs/plan-orchestrated-single-agent.md`](../plan-orchestrated-single-agent.md)（v0.1，2026-11-12）
- 状态源：[`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) §2.2 / §4。**本目录只讲"怎么做、做到什么算过"，不记进度。**
- 基线：tag `v1.0`；`132 passed`；契约 `11/11 + 5/5 + 20/20`；四指标达标（召回 10/10、误拦 0/20、角色 12/12、连续 10 轮 10/10）
- 分支：`agent-v2`（`main` 不动，`v1.0` 是回退点）
- 与 `step/` 的关系：`step/S01–S26` 是 v1 的历史手册，**只读不改**；v2 的一切操作写在本目录。

## 0 怎么用这六份文档

| 时机 | 动作 |
|---|---|
| 开工前 | 读本文件 §1 找当前节点 → 只读那一份的 §1–§4；跑 §4 的"开工检查" |
| 干活时 | 按 §5「执行步骤」逐条做；每完成一小节就跑一次 `pytest -q`，不许攒着一起修 |
| 收工前 | 按文档末「验证」表逐行跑；过不了不许进下一节点 |
| 收工后 | 按 §9/§10 写回执 → 更新 `CLAUDE.md` §2.2 状态 + §4 一行结果 → 提交 |

**一句话架构**（每一步都不许破坏它）：

```text
app.py（纯 UI）→ orchestrator.safe_run()
   → guardian_pre_check（本地规则，L3 短路，0 工具 0 LLM）
   → coordinator_decide → 工具可用性判定（代码定）
   → agent_loop.run_agent（≤3 步、≤2 次工具、总 20s）
   → guardian_post_check（规则 + 复核 + 一票否决）
   → style（口吻层，L3 与模板兜底不碰）→ 日志 + trace
```

## 1 六个节点一览

| 节点 | 操作文档 | 依赖 | 允许动的文件 | 出口（可验证） | 预估 |
|---|---|---|---|---|---|
| **P1** | [`P1-orchestrator.md`](P1-orchestrator.md) | P0 ✅ | 新 `orchestrator.py`、`app.py`、`tests/pipeline.py`、`tests/test_fault.py`、新 `tests/test_orchestrator.py` | **137 passed**（132+5）；`app.py` ≤250 行；日志 action 四值不变；C-01/C-05/C-09 不变 | 1 天 |
| **P2** | [`P2-agent-loop.md`](P2-agent-loop.md) | P1 | 新 `tools.py`/`agent_loop.py`、`agent.py`（+1 函数）、`orchestrator.py`（+生成分支）、新 `tests/test_tools.py`/`test_agent_loop.py` | **150 passed**；六条用例全绿（直接答 / 一次工具 / 步数超限 / 工具报错 / 未知工具 / L3 不循环）；`AGENT_LOOP=0` 时 P1 的 137 条行为不变 | 2–3 天 |
| **P3** | [`P3-web-search.md`](P3-web-search.md) | P2 + **D-1 决策** | 新 `web.py`、`tools.py`（注册）、新 `tests/test_web.py` | P3a **159 passed** + 七类错误各有测试；P3b 真实检索 smoke 通过；日志无 query | 2–4 天（待定） |
| **P4** | [`P4-guardian-tool-gate.md`](P4-guardian-tool-gate.md) | P2（P3 可缺省） | `guardian.py`（+1 函数）、`agent_loop.py`（gate/sources）、`orchestrator.py`（翻转 flag）、`panel.py`（+render_trace）、`app.py` | **166 passed**；越权工具被拦；trace 无原文；来源由代码渲染；`AGENT_LOOP` 默认 1 | 1–2 天 |
| **P5** | [`P5-style-layer.md`](P5-style-layer.md) | P1（可与 P2 并行） | 新 `style.py`、`agent.py`（`_style_block` 一行）、`orchestrator.py`（一处）、新 `tests/test_style.py` | **175 passed**；L3 模板逐字不变；L2 无贴纸；L1 无句尾句号；prompt 增量 <80 字 | 2 天 |
| **P6** | [`P6-regression-materials.md`](P6-regression-materials.md) | P1–P5 | 材料、证据、数字回填；**不改业务代码** | Gate A 成立；**176 passed**；docx/PPT/视频/提交包数字一致 | 3–5 天 |

> **候选设计（未决策，不是开工依据）**：[`P3-content-retrieval-design.md`](P3-content-retrieval-design.md) 记录“本地轻量识别 → orchestrator 路由 → MCP/HTTP 取风格 / 贴纸 / 图片”的三层方案。它**不改计划书与 D-1~D-5**；其中 C0（纯本地识别）可先做，C1 起仍等 D-1。转正前不许按它改代码。

## 2 依赖关系（哪些能并行）

```text
P0 ✅ ─→ P1 ─┬─→ P2 ─┬─→ P3 ──┐
             │       └─→ P4 ──┤
             └─→ P5 ──────────┴─→ P6
```

- **P4 不依赖 P3**：`REGISTRY` 为空时 `list_for_turn` 返回 `[]`，loop 退化成"直接答一次"，门禁与侧栏 trace 照样能测。网络方案没定也可以先做完 P4。
- **P5 可与 P2 并行**：它只碰 `orchestrator` 里 `reply` 那一行之前的位置，两边同时改会冲突——**先定好谁最后合并**，不要两人同时改 `orchestrator.py`。
- **P3 是唯一被外部决策卡住的节点**：没有 provider 就不开工，见 §5 D-1。

## 3 四条不变式（每一步收工都要自查）

1. **L3 先于一切工具**：`guardian_pre_check` 在编排最前面；L3 不进 loop、不调 LLM、断网也出卡。
2. **代码定边界，模型定用不用**：工具白名单在代码里；模型不能发明工具、不能给 URL。
3. **`guardian` 在循环外**：不参与协商、不被工具结果说服、不降等级。
4. **记忆只由 `update_memory` 写**：agent 只产文本；8 字段白名单与 `scrub` 不动。

## 4 每个节点共用的开工 / 收工动作

开工（3 分钟，缺一条就停）：

```powershell
cd "D:\deepseek harness\xinyu-agent"
git branch --show-current                                   # 必须是 agent-v2
git status --short                                          # 必须干净，脏的先提交或 stash
.\.venv\Scripts\python.exe -V                               # 3.11.x
.\.venv\Scripts\python.exe -m pytest -q                     # 上一节点收工时的条数
.\.venv\Scripts\python.exe contract_check.py                # 11/11 + 5/5 + 20/20
```

收工（5 分钟，缺一条算没做完）：

```powershell
.\.venv\Scripts\python.exe -m pytest -q                     # 全绿，条数写进回执
.\.venv\Scripts\python.exe contract_check.py                # 11 条契约一步都不许动
$env:MOCK_LLM="1"; .\.venv\Scripts\streamlit.exe run app.py # 手动两轮：一句日常 + 一句 L3
```

然后把验证输出存进 `docs/evidence/`，文件名带日期与节点：`docs/evidence/P1-orchestrator-2026-11-13.md`。

## 5 开工前必须定的决策（D-1 ~ D-5）

| 编号 | 要定什么 | 最晚什么时候定 | 默认建议（没人反对就按这个走） |
|---|---|---|---|
| **D-1** | 搜索 provider / key / 是否走 MCP | **P3 开工前**（P1/P2/P4/P5 不受影响） | 先不接；`web.py` 只写接口 + 假 transport，P3 保持"未开工" |
| **D-2** | `run_agent` 是否升为第 12 条契约 | P2 收工时 | **不升**。用测试锁接口，`contract_check` 保持 11 条，材料不用重写 |
| **D-3** | "风格包"（style_pack）是不是网络工具 | P3 开工前 | **不是**。静态口吻资源归 `style.py`（P5），`web.py` 只做 `web_search` / `fetch_image` |
| **D-4** | MVP 工具集：只做 `web_search` 还是加 `fetch_image` | P3 开工前 | 先只做 `web_search`；`fetch_image` 推迟到 P6 后（图片直链难核版权） |
| **D-5** | docx / PPT / 视频 / 提交包是否全部重做 | P5 收工后、P6 开工前 | 视频必须重录（132→实际数字）；docx/PPT 改数字 + 加一张编排图，不推翻重写 |

## 6 行数预算台账（每次收工核对）

| 文件 | 上限 | 现状（2026-11-12） | P6 目标 |
|---|---|---|---|
| `app.py` | 350（v2 目标 ≤250） | **326** | ≤250 |
| `orchestrator.py`（新） | 250 | — | ~210 |
| `agent_loop.py`（新） | 180 | — | ~150 |
| `tools.py`（新） | 200 | — | ~190 |
| `web.py`（P3 新） | 250 | — | ~230 |
| `style.py`（P5 新） | 180 | — | ~120 |
| `agent.py` | 300 | 207 | ≤300（+`chat_with_tools`） |
| `guardian.py` | 350 | 305 | ≤340（+`guardian_tool_check`） |
| `panel.py` | 350 | 118 | ≤160（+`render_trace`） |
| `memory.py` | 350 | 338 | **不许涨**（只读引用 `scrub`） |

超预算先拆函数，再拆文件；**不许删注释、删空行凑数**。

## 7 术语与红线速查

| 禁止 | 改说 |
|---|---|
| 多智能体 / Multi-Agent | 编排式单 Agent / 角色状态机 + 否决层 |
| 多模态 | 静态资源路由 |
| 能识别所有危机 | 对测试集内的危机表达有规则级覆盖 |
| 有效缓解焦虑 | 完成交互功能验证，不声称疗效 |
| AI 心理医生 / 咨询师 | 对话工具 / 陪伴工具 |

工具红线（P2–P4 每一条都要在代码里找得到落点）：白名单 / 结果不可信 / 参数校验 / 预算硬上限 / 日志不记 query / `AGENT_LOOP=0` 可关。

## 8 出问题时先看哪

| 现象 | 去哪份文档的"常见失败" |
|---|---|
| 行为变了、日志 action 变了、侧栏数字不对 | `P1-orchestrator.md` §8 |
| 第二步 400 / 模型不调工具 / 一直调工具不回答 | `P2-agent-loop.md` §8 |
| 真机联网超时、401、坏 JSON、日志漏 query | `P3-web-search.md` §8 |
| 工具被拦了但模型答非所问、trace 打不开 | `P4-guardian-tool-gate.md` §8 |
| L3 文案被改了、贴纸越界、prompt 变长 | `P5-style-layer.md` §8 |
| 报告数字与测试对不上、视频超 100MB | `P6-regression-materials.md` §8 |

## 9 变更记录

- 2026-11-12：按计划书 §4 拆出 P1–P6 六份操作文档（每份 11 节：做什么 / 关键决策 / 接口 / 前置 / 执行步骤 / 测试 / 验证 / 常见失败 / 回滚 / 出口 / 回执）；未改任何代码。
- 2026-11-12：新增候选设计 `P3-content-retrieval-design.md`（本地识别 + host 路由 + MCP 取内容），不改计划与 D-1~D-5。
- 各节点出口条数：137 → 150 → 159（P3a）→ 166 → 175 → 176。
