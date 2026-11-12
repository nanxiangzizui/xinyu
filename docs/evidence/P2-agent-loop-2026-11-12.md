# P2 证据 · tools.py + agent_loop.py（假工具）

日期：2026-11-12 ｜ 分支：agent-v2 ｜ 依据：docs/v2-steps/P2-agent-loop.md

## 1 出口核对

| 项 | 结果 |
|---|---|
| pytest | **150 passed**（137 旧 + 13 新） |
| contract_check | 11/11 signatures · 5/5 constants · 20/20 rules |
| tools.py / agent_loop.py / orchestrator.py 行数 | 133 / 112 / 235（预算 200 / 180 / 250） |
| 六条用例 | 直接答 / 一次工具 / 步数超限 / 工具次数超限 / 工具报错（未知工具同条）/ L3 不进 loop 全绿 |
| 禁用项 | 无 `while True`、`signal`、`ThreadPool`、`open(`、`subprocess`、`requests` |
| AGENT_LOOP | 默认 `0`；137 条旧测试零改动全绿 |
| 工具日志 | 只有 `name / status / ms`，不记 query、不记结果 |

## 2 pytest

```text
$ ./.venv/Scripts/python.exe -m pytest -q
........................................................................ [ 48%]
........................................................................ [ 96%]
......                                                                   [100%]
150 passed in 6.15s
```

## 3 contract_check

```text
$ ./.venv/Scripts/python.exe contract_check.py
11/11 signatures OK
5/5 constants OK
20/20 rules OK
```

## 4 行数与禁用项

```text
tools.py: 133
agent_loop.py: 112
orchestrator.py: 235
agent.py: 237

Select-String -Path tools.py,agent_loop.py -Pattern 'while True|signal|ThreadPool'   -> 无输出
Select-String -Path tools.py,agent_loop.py -Pattern 'open\(|subprocess|os\.system|requests' -> 无输出
```

## 5 git diff --stat

```text
$ git status --short
 M agent.py
 M orchestrator.py
?? agent_loop.py
?? tests/test_agent_loop.py
?? tests/test_tools.py
?? tools.py

$ git diff --stat
 agent.py        | 30 ++++++++++++++++++++++++++++++
 orchestrator.py | 28 ++++++++++++++++++++++++++--
 2 files changed, 56 insertions(+), 2 deletions(-)
```

guardian.py / coordinator.py / memory.py / roles.py / logger.py / contract_check.py 零改动。

## 6 界面冒烟（AGENT_LOOP=1 + MOCK，docs/evidence/p2_smoke_2026-11-12.py）

```text
turn 1: role=listener level=L1
turn 2: role=listener level=L1
turn 3: role=crisis level=L3
--- 直接看 trace（generate 节点）---
nodes: ['pre_check', 'aggregate', 'coordinator', 'cooldown', 'lore', 'prompt', 'generate', 'post_check', 'memory_write']
generate: [{"node": "generate", "status": "ok", "latency_ms": 0, "detail": "tools=0"}]
L3 nodes: ['pre_check', 'aggregate', 'short_circuit']
--- 结构化日志 ---
rows: 4
field set: ['action', 'latency_ms', 'level', 'rewrite', 'role', 'rule_ids', 'session_hash', 'ts', 'turn']
actions: ['pass', 'short_circuit', 'summary_compress']
log leaks user text: no
--- 临时注册假工具后，MOCK 仍直接答 ---
ok=True text_len=12 tool_calls=0 error=
```

说明：AGENT_LOOP=1 时走 `agent.chat_with_tools`，MOCK 直接答、工具列表为空（生产未注册任何工具）；
L3 轮 trace 里没有 `generate` 节点，证明 loop 根本没被调用。日志仍是 9 字段，无用户原文。

## 7 接口（P3–P5 只加不改）

```text
tools.py
  ToolSpec(name, description, parameters, timeout_s=TOOL_TIMEOUT_S,
           max_bytes=TOOL_MAX_BYTES, trusted=False)
  ToolResult(ok, data, error, source, latency_ms)
  register(spec, fn) / reset() / execute(name, args) -> ToolResult
  list_for_turn(role, level, allow_web=False) -> list[dict]
  register_fakes() -> None            # 仅测试

agent.py
  chat_with_tools(messages, tools, temperature=0.7) -> dict
      {"text", "tool_calls": [{"id","name","arguments"(dict)}], "ok", "error", "usage"}

agent_loop.py
  AGENT_MAX_STEPS=3 / AGENT_MAX_TOOL_CALLS=2 / AGENT_TOTAL_TIMEOUT_S=20
  run_agent(system_prompt, history, tool_list, max_steps=AGENT_MAX_STEPS,
            *, chat=None, gate=None, fallback_text="",
            deadline_s=AGENT_TOTAL_TIMEOUT_S) -> AgentResult
```

`gate` 形参已定死但 P2 不用；P4 直接传 `guardian.guardian_tool_check`，签名不改。

## 8 与步骤文档的两处偏差（均为文档示例笔误，行为不变）

1. **test_tool_error_is_fed_back_and_loop_continues**：文档写 `assert "工具调用失败" in seen[0]`，
   但 `seen[0]` 是第一次回调、最后一条还是 system prompt；工具结果在第二次回调里。
   实际断言改为 `seen[-1]`，测试意图（错误回填后续跑）不变。
2. **chat_with_tools 的 MOCK 分支**：文档写 `{"text": _mock(messages), ...}` 会把 dict 塞进 text；
   实际写 `_mock(messages)["text"]`。

## 9 回滚

```powershell
Remove-Item tools.py, agent_loop.py, tests/test_tools.py, tests/test_agent_loop.py
git checkout -- orchestrator.py agent.py
& ./.venv/Scripts/python.exe -m pytest -q      # 回到 137
```

线上第一处置手段：清掉 `AGENT_LOOP` 环境变量（默认 0 即回到 v1 `call_llm` 管线）。
