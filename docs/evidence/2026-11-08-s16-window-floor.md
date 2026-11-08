# S16 会话聚合 + 风险地板

> 文件名沿用计划日期 2026-11-09（原定）；**本文件实际生成于 2026-11-08**。
> 规格：`step/S16-window-floor.md`；对应执行书 §4.6。

## 1. 产出

| 文件 | 内容 |
|---|---|
| `coordinator.py` 46 → 89 行 | `RANK` / `NAME` / `ESCALATE_AT=3` / `_rank` / `_name` / `risk_floor(history, current)` / `aggregate_level(history, current)`；纯函数，不 import streamlit |
| `app.py` 275 → 303 行 | `_effective_level(raw)` 读写 `session_state["levels"]`（窗口只留 5 条）；`handle()` 拆成 `_crisis_result` / `_log_and_result`（`handle` 24 行，`main` 40 行）；L3 分支与正常分支都用 `eff_level` |
| `tests/test_flow.py` 54 → 98 行 | +5 条：空历史、L3 后地板 L2、3 次 L2 升 L3、2 次不升、只升不降不变量 |
| `docs/evidence/probes/_probe_s16.py` | AppTest 连发 3 次“没意思” → 第 3 轮 crisis 卡；随后 3 轮平静句停在地板 L2 |

等级序数 1/2/3；窗口状态 `st.session_state["levels"]`（**不进 memory.json**，刷新即空，与冷却/危机标记同口径）。

## 2. 五条硬要求对账

| 要求 | 实现 | 证据 |
|---|---|---|
| 任何函数返回 ≥ 输入 | `risk_floor` 取 `max(floor, current)`；`aggregate_level` 升级返回 L3、否则走地板 | `test_aggregate_never_lowers_level`（6 种历史 × 3 种当前，36 组断言） |
| 5 轮内 L2 ≥3 次 → L3 | `sum(x == "L2" for x in window) >= ESCALATE_AT`（3） | `test_aggregate_three_l2_in_window_escalates` |
| 窗口只留最近 5 条 | `(levels + [..])[-N_WINDOW:]`，`N_WINDOW` 来自 `roles.py:8`（契约钉死 5） | `app.py` 接线 + probe 打印窗口 |
| 升级写 `action="aggregate_escalate"` | `escalated = eff != raw` 时强制该 action（短路/普通分支一致，单行日志） | probe 第 3 轮日志 |
| 降级只由窗口滑动/冷却驱动 | 无“我没事了”出口：等级只随窗口滑出自然回落 | probe 第 4–6 轮：仍 L2，第 7 轮后才可能回 L1 |

## 3. 门禁（实测）

```text
pytest -q                              69 passed in 0.90s   （64 + 5）
contract_check.py                      11/11 + 5/5 + 20/20
app.py 303 行 / coordinator.py 89 行   均 ≤350；handle 24 行 / main 40 行，均 ≤40
```

## 4. AppTest 端到端（MOCK，`_probe_s16.py`）

```text
第1轮 '没意思'   level/action/role L2 pass listener       rule_ids ['W02']  窗口 ['L2']           资源卡 0
第2轮 '没意思'   level/action/role L2 pass listener       rule_ids ['W02']  窗口 ['L2','L2']      资源卡 0
第3轮 '没意思'   level/action/role L3 aggregate_escalate crisis  rule_ids ['W02']  窗口 ['L2','L2','L3']  资源卡 3
第4轮 '今天吃什么' L2 aggregate_escalate listener          rule_ids []       窗口 ['L2','L2','L3','L1']  资源卡 0
第5轮 '今天吃什么' L2 aggregate_escalate listener          rule_ids []       窗口 ['L2','L2','L3','L1','L1'] 资源卡 0
第6轮 '今天吃什么' L2 aggregate_escalate listener          rule_ids []       窗口 ['L2','L3','L1','L1','L1'] 资源卡 0
最终 exceptions: 0
```

第 3 轮 `calls == []`（没调 LLM），发出的是 `CRISIS_REPLY` 原文，资源卡 3 张；第 4 轮起有 gen + review，但等级停在地板 L2，不再短路——危机后用户还能继续说话，符合 C-12。

## 5. 四处口径修正（实现与 step 示例不同）

1. **地板取“出现过 L2+ → L2”，不照抄 `max(history)`。** step §5.2 的 `max` 会把 `["L3","L2"]` 算成 L3，与它自己的测试表 #2（期望 L2）矛盾。L3 当轮已短路发过资源卡，若地板继续给 L3，之后每轮都重复发同一张卡，用户无法继续；执行书附录 C 的 C-12 也要求危机后下一轮只到 L2。
2. **窗口存 raw 等级，不存每轮 effective level。** 否则一次真实 L2 被地板抬成 L2 后每轮都在“凑数”，三轮就把所有用户打成 L3。唯一例外：升到 L3 的那轮存 L3，让同一批 3 次 L2 不再重复触发升级；probe 第 4 轮即验证不再短路。
3. **升级只数“恰好 L2”，不数 L3。** L3 已经短路，再计入会让窗口在危机后继续判升级；地板负责承载 L3 的余温。
4. **不写两条日志。** step §5.4 示例在聚合升级时另写一行 `aggregate_escalate`，再照常写短路线，会让同一轮计两次、轮次对不上。改为单行日志：`escalated` 时 action 覆盖为 `aggregate_escalate`，其余原因由 `level` / `rule_ids` / `rewrite` 保留。

另：执行书 §4.6 第 3 条写“出现过 L3 → 之后 3 轮地板 L2（COOLDOWN=3）”，本实现按 step §1 的 **窗口 5 轮**（更严格，不会更松）；窗口滑出前地板不撤，故实际为 5 轮左右。COOLDOWN 仍只用于“降 guide”的角色冷却，两者不混用。

## 6. 没做的事

- 未改执行书、`agent.py`、`guardian.py`、`roles.py` 的 RULES 与常量。
- `sustained_negative` 仍留在 `REASONS` 枚举里未产出：聚合升级走的是等级通道，角色 reason 仍是 `crisis_shortcircuit` / `default`。侧栏“切换原因”在危机后会显示“自然延续”，这是 S11 既有口径，未在本步改。
- 人工项（人设盲读 3 人、危机文案盲读 1 人、手机流量打开）仍未做。
