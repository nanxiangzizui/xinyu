# S12 证据：结构化日志 + 侧栏 + tag v0.2
> 文件名沿用 2026-11-09（原定计划日期）；**本文件实际生成于 2026-11-08**。

记录时间：2026-11-08（沿用仓库既有证据的 2026-11-09 前缀）

## 1 改了什么

| 文件 | 变化 |
|---|---|
| `logger.py` | 新建，36 行：`FIELDS` 9 字段白名单 + `session_hash()`（sha256 前 12 位）+ `log_turn()`（一天一个 JSONL，写失败只 WARN） |
| `app.py` | 265 行：`handle()` 两端各写一行日志（L3 短路 / 正常生成）；`main()` 增加轮次计数；侧栏改为 `session_hash` + 轮次 + 中文等级/角色/原因 + 记忆摘要 + “清除我的记忆” |
| `tests/test_log.py` | 新建，2 条：字段白名单且无原文 / `session_hash` 稳定可区分 |

`logger.py` 不 import streamlit；是否写日志、写什么全由 `app.py` 的管线决定。

## 2 日志口径

```text
字段白名单（顺序固定）：
ts / session_hash / turn / level / role / rule_ids / action / rewrite / latency_ms

文件：data/logs/YYYY-MM-DD.jsonl（已 gitignore）
哈希：sha256(session_id)[:12]，日志里不出现原始会话 id
action：short_circuit（L3）/ generate（正常轮）
```

`log_turn()` 只保留白名单键，多传的 `user_text / reply / prompt` 一律丢弃；写入包在
`try/except (OSError, TypeError, ValueError)` 里，失败只 `print("[WARN] 日志写入失败：…")`。

## 3 自动验证

```text
$ .venv\Scripts\python.exe -m pytest -q
42 passed in 0.74s          # 原 40 + 本步 2

$ .venv\Scripts\python.exe contract_check.py
11/11 signatures OK
5/5 constants OK
20/20 rules OK

app.py 265 行 / logger.py 36 行 / tests/test_log.py 40 行（均 ≤350）
最长函数 main 39 行 / handle 38 行 / log_turn 12 行（均 ≤40）
```

口径说明：`step/S12-logging-sidebar.md` §6 写“41 passed”，是旧基数（按 S11 为 39 条估算）。
S11 实际收在 40 条，本步 +2 后为 **42 passed**；以实际输出为准，不为凑数字删测试。

## 4 AppTest 页面手测（驱动真实 `app.py`，`MOCK_LLM=1`）

```text
首屏            -> 平稳 / 倾听者 / 倾听者 / 第 0 轮            exceptions=0
"我该怎么办"    -> 平稳 / 引导者 / 切换原因：你明确问了办法    exceptions=0
"我不想活了"    -> 危机 / 危机支持 / 切换原因：需要优先保证安全 exceptions=0
"今天好累"      -> 平稳 / 倾听者 / 切换原因：自然延续          exceptions=0
```

日志实际落盘（3 轮，9 字段齐全，无一句原文）：

```json
{"session_hash": "cc4eb51101eb", "turn": 1, "level": "L1", "role": "guide", "rule_ids": [], "action": "generate", "rewrite": 0, "latency_ms": 8, "ts": "2026-11-08T18:00:09"}
{"session_hash": "cc4eb51101eb", "turn": 2, "level": "L3", "role": "crisis", "rule_ids": ["H01"], "action": "short_circuit", "rewrite": 0, "latency_ms": 0, "ts": "2026-11-08T18:00:09"}
{"session_hash": "cc4eb51101eb", "turn": 3, "level": "L1", "role": "listener", "rule_ids": ["W01"], "action": "generate", "rewrite": 0, "latency_ms": 15, "ts": "2026-11-08T18:00:09"}
```

原文泄漏检查：`我该怎么办 / 我不想活了 / 今天好累` 在原始日志文本中均为 `False`。

## 5 清空与日志降级

```text
点“清除我的记忆”后：
  messages=0 / turn=0 / 新 sid 与旧 sid 不同
  旧 sid 的 .json 与 .json.bak 均不存在
  新 sid 的记忆文件是默认值（无旧情绪标签）

把 LOG_DIR 指向一个“文件”而非目录：
  [WARN] 日志写入失败：FileExistsError
  该轮对话正常完成，exceptions=0，回复不为空
```

## 6 实现中的判断

1. **L3 也写日志**：步骤 §5.2 的片段只覆盖正常生成路径，但 `SKILL.md` 的验收要求
   “L3 日志 `level=L3`、latency 很短”。`handle()` 在短路返回前写
   `action="short_circuit"`，实测 `latency_ms=0`。
2. **测试改用 `monkeypatch.setattr(logger, "LOG_DIR", …)`**：`LOG_DIR` 与 `memory.DATA_DIR`
   同样是模块级常量（`_bridge_secrets` 在 import 前注入环境变量），import 之后再
   `setenv` 不会生效。步骤 §5.4 的 `setenv` 写法照抄会测到真实 `data/logs`，故调整。
3. **侧栏不露 `L1/L2/L3`**：按步骤 §5.3 显示“平稳 / 留意 / 危机”；角色显示
   “倾听者 / 引导者 / 危机支持”；原因与语气也给了中文标签，避免演示时出现枚举码。
4. **轮次计数放在 `main()`**：只要用户发了一句就 +1，L3 短路轮也算一轮（它确实发生了对话）。
   清空记忆时归零；刷新页面按既定口径重置。
5. **失败捕获比步骤多两类**：除 `OSError` 外也捕获 `TypeError / ValueError`，
   防止将来 `rewrite` 或 `rule_ids` 传入不可序列化值时把整轮对话带崩。
6. **日志是旁路**：`log_turn` 不抛异常、不返回值，调用方不需要判断；写失败不影响
   `update_memory` 与回复渲染。

## 7 未做 / 下一步

- 真实浏览器截图未做；用 AppTest 驱动同一 `app.py` 等价验收（与 S10/S11 同口径）。
- `rewrite` 目前恒为 0（`guardian_post_check` 还是 S13 空壳）；S13 起会出现 `rewrite=1`。
- `level` 是当轮 `guardian_pre_check` 结果，S16 的风险地板尚未接入。
- 下一步 S13：`guardian_post_check` 骨架 + 重写复检（`rewrite=1`）。

## 8 回执

```text
S12 完成：42 passed / 日志 9 字段无原文 / 写失败不影响对话 / 侧栏可清除记忆
下一步：S13 post_check 骨架（重写与复检）
```
