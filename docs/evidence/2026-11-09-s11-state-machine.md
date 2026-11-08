# S11 证据：三角色状态机
> 文件名沿用 2026-11-09（原定计划日期）；**本文件实际生成于 2026-11-08**。

记录时间：2026-11-08（沿用仓库既有证据的 2026-11-09 前缀）

## 1 改了什么

| 文件 | 变化 |
|---|---|
| `coordinator.py` | 46 行：`ADVICE_WORDS` 7 词 + `REASONS` 六枚举 + `coordinator_decide`（L3 → 历史危机 → 求助词 → 默认）+ `enforce_cooldown`（engine 只降 guide） |
| `app.py` | 228 行：L3 短路时 `_mark_crisis()` 置 `cooldown=COOLDOWN`、`ever_crisis=True` 并先置再减 1；非 L3 轮走 `enforce_cooldown` 后减 1；侧栏显示真实角色 / 等级 / 原因；清空对话同时重置冷却与 `ever_crisis` |
| `tests/test_flow.py` | 新建，4 条：L3 压倒文本 / 求助词切 guide / 默认 listener / 冷却与历史危机永不回 guide |

`coordinator.py` 没有 `import streamlit`；所有会话状态只在 `app.py`。

## 2 判定顺序与固定枚举

```text
1. level == "L3"                          -> crisis   / crisis_shortcircuit
2. memory["current_role"] == "crisis"     -> listener / after_crisis
3. user_text 含 ADVICE_WORDS              -> guide    / user_ask_advice
4. 其他                                    -> listener / default

enforce_cooldown(decision, cooldown_left, ever_crisis)：
  role != guide        -> 原样返回
  ever_crisis          -> listener / after_crisis
  cooldown_left > 0    -> listener / crisis_cooldown
  否则                 -> 原样返回

REASONS = (
  "crisis_shortcircuit", "user_ask_advice", "sustained_negative",
  "default", "crisis_cooldown", "after_crisis",
)
```

`sustained_negative` 留给 S16 会话聚合，本步不会产出；其余五个已由单测或 AppTest 实际产生。

## 3 自动验证

```text
$ .venv\Scripts\python.exe -m pytest -q
40 passed in 1.00s          # 原 36 + 本步 4

$ .venv\Scripts\python.exe contract_check.py
11/11 signatures OK
5/5 constants OK
20/20 rules OK

coordinator.py 46 行 / app.py 228 行 / tests/test_flow.py 54 行（均 ≤350）
最长函数 main 40 行 / handle 33 行 / coordinator_decide 18 行（均 ≤40）
```

口径说明：`step/S11-role-machine.md` §6 与 §9 写“39 passed”，是旧基数（按 S10 为 35 条估算）。
S10 实际收在 36 条，本步 +4 后为 **40 passed**；以实际输出为准，不为凑数字删测试。

## 4 AppTest 页面手测（驱动真实 `app.py`，`MOCK_LLM=1`）

```text
最近和室友处得不好，回宿舍就烦 -> listener / L1 / default          infos=0  exceptions=0   # C-01 不误触
今天好累                       -> listener / L1 / default          infos=0  exceptions=0
我该怎么办                     -> guide    / L1 / user_ask_advice  infos=0  exceptions=0   # C-05 切 guide
我不想活了                     -> crisis   / L3 / crisis_shortcircuit infos=3 exceptions=0 # C-09 短路 + 3 张资源卡
我该怎么办                     -> listener / L1 / after_crisis     infos=0  exceptions=0   # 危机后不回 guide
今晚吃什么                     -> listener / L1 / default          infos=0  exceptions=0
你说我该不该放弃               -> listener / L1 / after_crisis     infos=0  exceptions=0   # 仍是 listener
all role/reason assertions: PASS

清空后：messages=0 / cooldown=0 / ever_crisis=False / exceptions=0
清空后输入“我该怎么办” -> guide / L1 / user_ask_advice              # 新会话可重新进 guide
```

结论：三句手测符合预期；危机后连续两轮求助仍为 `listener / after_crisis`；清空对话会重置
冷却与“有过危机”标记，不会把新会话永久锁在 listener。

## 5 四条测试

| # | 输入 | 期望 | 结果 |
|---|---|---|---|
| 1 | `level=L3`，文本“今天天气不错”/“我该怎么办” | crisis / crisis_shortcircuit | PASS（等级压倒文本） |
| 2 | `level=L1`，“我该怎么办” + C-05 原句 + 词表逐词 | guide / user_ask_advice | PASS |
| 3 | `level=L1`，“今天好累” + C-01 原句 | listener / default | PASS（不误切） |
| 4 | guide + `cooldown=2, ever_crisis=False`；guide + `ever_crisis=True`；记忆 `current_role=crisis` | listener / crisis_cooldown；listener / after_crisis；listener / after_crisis | PASS |

每条断言同时检查 `reason` 是否落在 `REASONS` 六枚举内。

## 6 实现中的判断

1. **L3 短路在 `coordinator_decide` 之前**（S10 的既定管线）。因此冷却标记放在 `handle()` 的 L3
   分支里：先 `cooldown=COOLDOWN`、`ever_crisis=True`，再减 1 后返回。效果与步骤 §5.4
   “先判 L3 置冷却 → 再减 1”一致，L3 当轮之后还有 `COOLDOWN-1=2` 轮余量。
2. **侧栏提前接真实值**：W2 验收要求“角色与原因可见”，S11 页面手测也必须看得到角色变化。
   侧栏现在显示 `last_role / last_level / last_reason`；S12 再补结构化日志与中文标签。
3. **`memory["current_role"] == "crisis"` 是跨会话兜底**：目前没有步骤会写这个字段
   （`update_memory` 只写标签 / 摘要），所以它是防御性分支；S18 若开放 `current_role` 编辑，
   这条会立即生效。本会话的“永不回 guide”由 `ever_crisis` 负责，两者不混用。
4. **`after_crisis` 优先于 `crisis_cooldown`**：按步骤 §5.3 原样实现。当前接线中 L3 会同时置
   `ever_crisis=True`，所以实际产出的是 `after_crisis`；`crisis_cooldown` 由第 4 条单测覆盖，
   留给“有冷却但无永久标记”的场景（例如未来从记忆恢复冷却计数）。
5. **清空对话重置状态**：`_clear()` 同时把 `cooldown/ever_crisis/last_*` 归零。否则用户点
   “清空这次对话”后新会话仍永久停在 listener，演示时会被误判成状态机坏了。
6. **`enforce_cooldown` 不修改入参**：降级时返回新 dict；不需要降级时原样返回，便于测试比较。
7. **reason 码采用六枚举，不采用 §4.7 旧表**：执行书 §4.7 的 `risk_short_circuit / help_requested_2x`
   等码与同书 §11 五条约定、S11 §4 的六枚举冲突；按接口契约与 S11 明确要求，统一用
   `crisis_shortcircuit / user_ask_advice / sustained_negative / default / crisis_cooldown / after_crisis`。

## 7 未做 / 下一步

- 结构化日志（`level / role / reason / rule_ids / action / latency_ms`）在 S12；本步不写日志。
- 侧栏的“中文标签 / 记忆摘要”在 S12；本步只接真实值。
- `sustained_negative` 触发条件（连续负性）在 S16 会话聚合；本步只保留枚举。
- 风险地板（L3 后 3 轮保持 L2）在 S16；本步的 `level` 仍是当轮 `guardian_pre_check` 结果。
- 真实浏览器截图未做，用 AppTest 驱动同一 `app.py` 等价验收；如需截图可在 S12 补。
- 下一步 S12：`logger.py` + 侧栏真实值 + tag `v0.2`。

## 8 回执

```text
S11 完成：4 passed（累计 40）/ 三角色可用 / 危机后不回 guide
下一步：S12 日志与侧栏（打 tag v0.2）
```
