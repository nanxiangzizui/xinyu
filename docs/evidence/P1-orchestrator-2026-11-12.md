# P1 证据 · orchestrator 抽取（2026-11-12）

> 阶段：CLAUDE.md §2.2 P1 ｜ 分支 `agent-v2` ｜ 依据 `docs/v2-steps/P1-orchestrator.md`
> 出口：**行为零变化**；132 旧用例全绿 + 5 条新用例 = **137 passed**；C-01 / C-05 / C-09 不变。

## 1 改了什么

| 文件 | 行数 | 内容 |
|---|---|---|
| `orchestrator.py`（新） | 186 | 七步编排 + 9 节点 trace + `safe_run` 兜底；不 import streamlit，状态由 `state` 参数传入 |
| `app.py` | 174（原 326） | 只留 UI：免责声明 / session / 侧栏 / 渲染 / 清空；`main()` 只调 `safe_run(...)` |
| `tests/test_orchestrator.py`（新） | — | 5 条：L3 不调模型 / 9 节点顺序 / 异常兜底 / trace+日志无特征串 / state 跨轮冷却 |
| `tests/pipeline.py` | — | 新增 `pipeline_source()`（app.py + orchestrator.py 两份源码） |
| `tests/test_fault.py` | 1 行 | F-01 源码断言改用 `pipeline_source()` |

**未动**：`guardian.py` / `coordinator.py` / `memory.py` / `roles.py` / `logger.py` / `resources.py`（`git diff` 零改动），契约 11 条未变。

## 2 接口

```text
orchestrator.handle(text, sid, history, persona_id, state=None) -> dict   # 异常上抛
orchestrator.safe_run(text, sid, history, persona_id, state=None) -> dict # 任何异常 → 一句人话
```

- 返回 dict 在原 5 键（reply / level / role / reason / degraded）之外新增 `trace`。
- trace 节点（正常轮，按序）：`pre_check` / `aggregate` / `coordinator` / `cooldown` / `lore` / `prompt` / `generate` / `post_check` / `memory_write`；L3 轮为 `pre_check` / `aggregate` / `short_circuit`。
- `detail` 只放等级 / 角色 / ok 之类的状态字，**不含原文、prompt、回复**。

## 3 验证输出（2026-11-12 本机）

### 3.1 pytest

```text
........................................................................ [ 52%]
.................................................................        [100%]
137 passed in 6.13s
```

### 3.2 contract_check（契约 11/11 + 5/5 + 20/20）

```text
11/11 signatures OK
5/5 constants OK
20/20 rules OK
```

### 3.3 metrics（四指标与 v1 完全一致）

```text
recall       10/10 = 100.0%
false_block  0/20 = 0.0%
role         12/12 = 100.0%
stable       10/10 = 100.0%
```

### 3.4 冒烟（真 AppTest 驱动 app.py，MOCK_LLM=1 + 临时 DATA_DIR/LOG_DIR）

脚本：`docs/evidence/p1_smoke_2026-11-12.py`（可重跑，不碰仓库 `data/`、不联网）

```text
turn 1: role=listener level=L1 reply_len=12
turn 2: role=listener level=L1 reply_len=12
turn 3: role=guide level=L1 reply_len=12 OK
turn 4: role=crisis level=L3 reply_len=131 OK
turn 5: role=listener level=L2 reply_len=12 OK
--- 同 sid 重进：消息清空、记忆仍从磁盘读回 ---
messages restored (expect 0): 0
memory fields: ['coping_preferences', 'current_role', 'emotion_tags', 'last_updated', 'preferred_tone', 'role_switch_reason', 'rolling_summary', 'summary_at_turn', 'unresolved_issues']
--- 结构化日志 ---
rows: 6 reply_rows: 5
field set: ['action', 'latency_ms', 'level', 'rewrite', 'role', 'rule_ids', 'session_hash', 'ts', 'turn']
actions: ['aggregate_escalate', 'pass', 'short_circuit', 'summary_compress']
last row: {"action": "aggregate_escalate", "latency_ms": 6, "level": "L2", "rewrite": 0, "role": "listener", "rule_ids": [], "session_hash": "5b1a022acf13", "ts": "2026-11-12T21:36:11", "turn": 5}
log leaks user text: no
```

要点：第 4 轮 L3 走 `short_circuit`；第 5 轮被窗口抬到 L2（`aggregate_escalate`）且角色回 listener（冷却），与 v1 行为一致；日志仍是 9 字段、不含用户原文。

> 注：脚本退出码 1 是 PowerShell 把 Streamlit 的 `missing ScriptRunContext` WARNING（写 stderr）当 `NativeCommandError`，脚本自身断言全过。

### 3.5 源码级

```text
git status --short                  → 仅 app.py / tests/* / 新增 orchestrator.py
(Get-Content app.py).Count          → 174
(Get-Content orchestrator.py).Count → 186
Select-String safe_handle           → 无输出（旧名已清零）
```

## 4 与 P1 文档的偏差（唯一一处）

- 文档 §6 第 3 条示例写 `orchestrator.handle(...)` 断言兜底，但 §5.1 明确「handle 让异常上抛，兜底只在 safe_run」。
- 实际测试改用 `orchestrator.safe_run`，断言不变：`FALLBACK_LINE` + `level=L2` + `role=listener` + `degraded=True` + 日志留 `PIPELINE_FAILED` 一行。

## 5 回滚

```powershell
git checkout v1.0 -- app.py tests/pipeline.py tests/test_fault.py
Remove-Item orchestrator.py, tests/test_orchestrator.py
```
或直接 `git reset --hard v1.0`（`agent-v2` 尚未合入 `main`）。
