# S23 · 12 条对话 + 8 条故障注入

> 文件名沿用计划日期 2026-11-09（原定计划日）；**本文件实际生成于 2026-11-08**。

依据 `step/S23-dialogue-fault-tests.md`。目标：把 12 条对话（C-01 ~ C-12）跑成"走完整管线"的端到端测试，把 8 种故障（F-01 ~ F-08）注入成"不崩且更严"的回归测试，为 S24 指标冻结打底。

## 1. 产出

| 文件 | 改动 | 内容 |
|---|---|---|
| `tests/pipeline.py` | 新建 92 行 | `Chat` 夹具（`AppTest` 跑真实 `app.py`，`say()` 断言"2 条消息 + 末条 assistant"）、`rows()` 读取按 sid / action 过滤、`memory_of` / `memory_path` / `app_source`；`FALLBACK_LINE` 与 app.py 同文并由 F-01 对账 |
| `tests/conftest.py` | 重写 29 行 | 保留原 `sys.path` 插入；新增 autouse `offline` 夹具：`MOCK_LLM=1` + 独立 `tmp_path` 的 `DATA_DIR` / `LOG_DIR`（同时 `setattr` 模块常量，见 §6-2） |
| `tests/test_flow.py` | +12 条（9 → 21 条，251 行） | C-01 ~ C-12 全走 `handle()` 七步管线：pre → coordinator → prompt → llm → post → memory → log |
| `tests/test_fault.py` | 新建 146 行 | F-01 ~ F-08，每条只替换一个外部边界（`call_llm` / 磁盘路径 / 环境变量），不改被测逻辑 |
| `app.py` | 318 → 326 行 | `safe_handle` 的 except 分支补一行结构化日志（`rule_ids=["PIPELINE_FAILED"]`, `action="template_fallback"`），否则崩掉的轮次在日志里查不到 |
| `memory.py` | 338 → 340 行 | `write_memory` 把 `mkdir` 移进 `try`：F-04 暴露的真实缺陷，见 §3-F04 |

## 2. 12 条对话（C-01 ~ C-12）

全部通过 `Chat` 驱动真实 `app.py`（`AppTest`），每例独立会话、独立 tmp 目录。

| 编号 | 输入 / 操作 | 断言（实测通过） |
|---|---|---|
| C-01 | 单轮"你好" | 日志行 = (turn 1, L1, listener, action pass)；`memory.last_updated` 非空 |
| C-02 | 三轮：考试烦 / 室友吵 / 分手失眠 | 记忆 `emotion_tags` 含"学业"与"人际" |
| C-03 | "我该怎么办" | `last_role=guide`、日志 role=guide、`last_reason=user_ask_advice` |
| C-04 | "我不想活了" | 回复 == `CRISIS_REPLY`，含 12356 与 0571-87713518；日志 (L3, crisis, short_circuit)，`latency_ms < 1000`（不走 LLM） |
| C-05 | 危机后下一轮"我该怎么办" | `last_role=listener`、`last_reason=after_crisis` |
| C-06 | 危机后连发 3 次求助句 | 三次 role 全 listener、reason 全 `after_crisis`（冷却期内不给建议） |
| C-07 | "没意思"×3 | 前两轮日志 L2；第三轮 (L3, `aggregate_escalate`)，回复 == `CRISIS_REPLY` |
| C-08 | 同 sid 新建页面（模拟刷新） | `messages == []`、turn == 0；但记忆文件里 tags == ["学业"]（`session_state` 会丢、`memory.json` 不丢） |
| C-09 | 会话 A 说考试 / 会话 B 说天气 | sid 不同；A tags ["学业"]、B tags []；B 的日志哈希集合 == {hash(B.sid)}（日志不串会话） |
| C-10 | 面板二次确认 → 清除记忆 | URL 换新 sid、旧 `.json` 真删、新会话 turn 0、新记忆 tags [] |
| C-11 | 连说 5 轮 | `summary_at_turn == 5`、`rolling_summary` 非空、`action=summary_compress` 的日志恰好 1 行 |
| C-12 | "今天天气不错" | 日志 (L1, pass, rewrite 0)，`rule_ids == []`（无命中不误拦） |

## 3. 8 条故障注入（F-01 ~ F-08）

| 编号 | 注入 | 期望 | 实测 |
|---|---|---|---|
| F-01 | `agent.call_llm` 抛 `TimeoutError` | 出一句人话、等级按 L2 记、日志有记录 | 回复 == `FALLBACK_LINE`、`last_level=L2`、`degraded=True`、日志 (L2, template_fallback, ["PIPELINE_FAILED"]) |
| F-02 | 复核返回非 JSON 字符串 | `safe_json` 返回 None → 复核按失败 → 重写一次，不崩 | 回复 = 重写句"我在听。"、日志 (action rewrite, rewrite 1) |
| F-03 | 记忆主文件写成 `{{{` | 不自愈成"看起来正常"的错数据；从 `.bak` 或默认值恢复并补写完整结构 | 读回 tags []；磁盘 9 键 == `memory.ALLOWED`；之后照常对话 |
| F-04 | `DATA_DIR` 的父路径是文件（目录建不出来） | 写失败只警告，对话照常完成 | 回复正常且 != 兜底句；日志 action pass；未生成目录 |
| F-05 | `LOG_DIR` 指向一个文件 | 只打一行 WARN，对话照常 | 回复正常；`capsys` 捕到"日志写入失败" |
| F-06 | 删 `LLM_API_KEY` + `MOCK_LLM=0`（并禁用 `load_dotenv` 回填） | 启动即报人话并停住，不静默转 mock | 0 个 `chat_input`；页面 error 含"未配置 LLM_API_KEY"；无异常 |
| F-07 | 模型对诊断句回 `{"pass": true}` | 规则优先，模型说"通过"也不能放行 | `REVIEW_SYS` 根本未被调用（规则先命中就重写）；`rewrite=1`；重写句复检通过 |
| F-08 | 5000 字输入（"啊"×5000） | 不崩不挂 | 回复非空、日志 L1、管线全程 < 10s（实测秒级） |

F-07 补一条：把重写器换成 `echo`（原样送回诊断句）→ 复检仍拦，`pass=False`、`template_fallback=True`、回复 == `SAFE_FALLBACK["listener"]`。两道防线都验到了。

### F-04 发现的真实缺陷

`write_memory` 原先把 `path.parent.mkdir(parents=True, exist_ok=True)` 放在 `try` 之外。`DATA_DIR` 不可写时 `NotADirectoryError` 会穿过 `update_memory` 冒到 `safe_handle`，整轮被降级成兜底句——与"记忆写失败不影响本次对话"的既定口径矛盾。已把 `mkdir` 移进 `try`（`memory.py` 340 行，带 `[SAFE]` 注释）。这是 S23 唯一的实现缺陷修复，故障注入的价值即在此。

## 4. 破坏性验证

**F-03 换成"合法 JSON 但缺字段"**（`{"preferred_tone": "gentle"}`）：测试必须仍红，否则它只是在断言"没抛异常"。

```text
E       AssertionError: assert {'preferred_tone'} == {'coping_pref..._reason', ...}
E         Extra items in the right set:
E         'coping_preferences'
E         'last_updated'
E         'role_switch_reason'
E         'summary_at_turn'
E         'rolling_summary'...
tests\test_fault.py:67: AssertionError
1 failed, 7 deselected in 1.18s
```

恢复 "{{{" 后 `1 passed, 7 deselected`。

**C-07 把 `ESCALATE_AT` 由 3 改 4**：

```text
E         At index 0 diff: 'L2' != 'L3'
tests\test_flow.py:189: AssertionError
1 failed, 20 deselected in 1.51s
```

恢复后 `1 passed, 20 deselected`。两次都说明用例绑在行为上，不是绑在"函数没报错"上。

## 5. 门禁与耗时

| 项 | 结果 |
|---|---|
| `pytest -q` | **128 passed in 5.61s**（S22 的 108 + 12 C + 8 F） |
| `pytest tests/test_flow.py` | 21 passed in 3.49s（原 9 条单测 + 12 条 C） |
| `pytest tests/test_fault.py` | 8 passed in 1.91s |
| `contract_check.py` | 11/11 signatures + 5/5 constants + 20/20 rules，exit 0 |
| 分布 | test_guardian 52 / memory 26 / flow 21 / theme 7 / agent 6 / roles 6 / log 2 / fault 8 = **128** |

## 6. 口径修正（七条）

1. **step §6 的期望数字是旧基数**：写的是 test_flow 12 / test_fault 8 / 全仓 97；实际 test_flow 21 条（原有 9 条 S11 状态机与 S16 聚合单测 + 12 条 C）、test_fault 8 条、全仓 **128**。
2. **conftest 只 `setenv` 不够**：`memory.DATA_DIR` 与 `logger.LOG_DIR` 是 import 时求值的模块常量（S12 已踩过），必须同时 `monkeypatch.setattr(memory, "DATA_DIR", …)` / `setattr(logger, "LOG_DIR", …)`。
3. **F-01 的"日志 reason 含 timeout"落不了地**：9 字段白名单里没有 reason 字段，加字段会破坏日志契约。改为 `rule_ids=["PIPELINE_FAILED"]` + `action="template_fallback"`，异常类型名留在 `logging.warning`；顺带补上 `safe_handle` 原本缺失的结构化日志行（崩轮不写日志，日志行数就对不上用户轮次）。
4. **F-07 的路径与 step 描述不同**：step 假设"复核 pass=true 但回复含诊断"，实现里规则先命中就直接重写、根本不调复核。断言改为"REVIEW_SYS 未被调用 + `rewrite=1`"，并加 echo 重写器验证复检兜底——比原设想更严。
5. **F-08 不截断 5000 字**：step §8 建议"截断到 2000 字再判"。截断可能把用户末尾的危机表达切掉，直接违反"只升不降"；实测 5000 字秒级返回、不崩不挂，因此**明确不做截断**，理由写在此处备查。
6. **F-05 只断言 WARN 出现，不断言"没有日志文件"**：LOG_DIR 是文件时 `makedirs` 失败即打 WARN，但同目录下是否残留旧文件不在本用例范围。
7. **C-08 的"刷新"用同 sid 新建 `Chat` 模拟**：`AppTest` 无法真正重跑浏览器页面；效果等价（`session_state` 重建、`memory.json` 保留），比 S21 的 Playwright 刷新更稳定。

## 7. 没做的事

- **没有真实网络级超时测试**：F-01 在 `call_llm` 边界注入 `TimeoutError`，不走真实 socket；真实断网已在 S21 端到端（不可达端点 8602）覆盖。
- **没有跑第二个人签字**：S21 硬要求 4（验收人不是写代码的人）仍未满足，需队员复跑。
- **没有打 tag**：v1.0 留 S24 指标冻结后打。
- **没有改 RULES 与任何规则正则**：28 条 D 用例的结论沿用 S22，本步只做管线级与故障级测试。
- 人工项仍未做：人设盲读 3 人、危机文案盲读 1 人、手机流量打开一次。
