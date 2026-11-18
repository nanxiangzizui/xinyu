# P19 聊天页「当前角色」可切换（2026-11-18）

## 1. 用户请求

用户原话（m00001）：

> 现在项目网页中聊天模式下的"当前角色"是无法更改的（我没找到切换按键），请你帮我改成可选择选项

## 2. 问题定位

- 聊天页侧栏的「当前角色」原本是 `companion_ui._sidebar` 里的 `st.metric("当前角色", ...)`，
  值直接来自 `session_state["last_role"]`。
- 这个值由 `coordinator.coordinator_decide` 按"等级 + 文本 + 记忆"算出来，只有三层分支：
  L3 → crisis、记忆里有危机 → listener、命中求助词 → guide、其他 → listener。
- 也就是说：界面上没有任何入口能改它，用户唯一能间接影响它的办法是说"我该怎么办"这类求助词。
  用户的需求是**显式可选**，而不是"再教一遍求助词"。

## 3. 口径与形状

侧栏「当前角色（可切换）」下拉，三个选项：

| 选项值 | 界面文案 | 含义 |
|---|---|---|
| `auto` | 自动判断 | 默认，判定与 P18 完全一致 |
| `listener` | 倾听者 | 手动指定，先接住情绪 |
| `guide` | 引导者 | 手动指定，给具体办法 |

**crisis 不放进选项**：它只由 L3 触发，而且 L3 在 `orchestrator` 第 2 步就已短路、根本不进
`coordinator`。放进下拉框会让人以为"危机能手动点开"，也会让用户以为"危机能手动关掉"。

手动选择**只改角色，不改等级**：`eff_level` 仍由 `guardian_pre_check` + 会话聚合决定，
资源卡仍按等级出。

## 4. 代码改动

### 4.1 `coordinator.py`

```python
ROLE_CHOICES = ("listener", "guide")

def apply_role_choice(decision: dict, choice: str) -> dict: ...
def decide_with_choice(memory: dict, user_text: str, level: str,
                       choice: str = "") -> dict: ...
```

- `REASONS` 末尾加 `"user_choice"`：只在手动切换真的生效时产出，日志/面板能一眼分辨
  "系统判定"和"你自己选的"。
- `apply_role_choice` 的三条边界：`choice` 不在 `ROLE_CHOICES`（含 `""` / `auto` / 未知值）
  → 原样返回；`decision` 已经是这个角色或已是 `crisis` → 原样返回；其他 → 换成 `choice`，
  原因记 `user_choice`。
- `decide_with_choice` 只是 `coordinator_decide` + `apply_role_choice` 的组合，
  `coordinator_decide` 的三参签名与判定顺序一字未动（契约 11 条里的那条照旧 3 参）。

### 4.2 `orchestrator.py`（第 2 个节点）

```python
dec = _timed(trace, "coordinator", coordinator.decide_with_choice,   # 2 定角色
             facts, text, eff_level, state.get("role_choice", ""))
```

位置刻意留在 `coordinator` 节点内部，**没有新增 trace 节点**，九节点顺序不变
（`tests/test_orchestrator.py::test_node_order_is_unchanged` 仍绿），文件仍 250 行。

### 4.3 `companion_ui.py`

- `ROLE_OPTIONS = ("auto",) + coordinator.ROLE_CHOICES`、
  `ROLE_OPTION_LABELS = {"auto": "自动判断", **ROLE_LABELS}`。
- 新增 `_role_picker(role, reason)`：`st.selectbox("当前角色（可切换）", ..., key="role_pick")`，
  选完写 `session_state["role_choice"]`；下面两行 caption：
  「这一轮：{角色} · 切换原因：{原因}」（原 metric + caption 的信息没丢），
  以及手动选择与系统接管冲突时的说明「手动选择从下一轮开始；危机与危机后的缓冲期由系统接管。」
- `_sidebar` 里原来的 `st.metric("当前角色", ...)` 与紧随的 `st.caption("切换原因：…")`
  换成 `_role_picker(role, reason)`，其余不动。
- `_init_state` 的默认值元组加 `("role_choice", "auto")`。

### 4.4 `panel.py`

`REASON_LABELS` 加 `"user_choice": "你自己选的"`，界面上不出现枚举码。

## 5. 安全口径（为什么这样放）

1. **手动选择夹在"定角色"与"冷却"之间**（`[SAFE]`）。`enforce_cooldown` 拿到的才是最终角色，
   所以：本会话出现过危机 → 手动选 guide 也会被降回 listener（reason `after_crisis`）；
   冷却期内 → 降回 listener（reason `crisis_cooldown`）。界面绕不过安全口径。
2. **crisis 不被手动选择改动**（`[SAFE]`）。L3 本来就在 coordinator 之前短路，这里再挡一层，
   以后调用点挪位置也不会出现"危机轮按普通角色回答"。
3. **等级与资源卡不受影响**：手动选择不写 `levels`、不碰 `eff_level`、不碰 `ever_crisis`。
4. **工具能力不变**：`tools.list_for_turn` 只看 `level == "L3"` / `role == "crisis"`，
   L1 才联网；手动切 guide 不会多出工具或联网额度。
5. **B 模式零变化**：`rolecard_ui` 的 `rc_state` 没有 `role_choice` 键，
   `orchestrator.handle` 对 B 也走同一条 `state.get("role_choice", "")` → 空串 → 原样返回。
6. **默认行为就是 P18**：`auto` 时 `apply_role_choice` 直接返回原 decision，
   467 条旧用例（C-01 ~ C-12、四人设、rolecard 全部）一条没改断言。

## 6. 验证

```text
.\.venv\Scripts\python.exe -m pytest -q
474 passed in 27.97s

.\.venv\Scripts\python.exe contract_check.py
11/11 signatures OK
5/5 constants OK
20/20 rules OK
```

新增 7 条测试（`tests/test_flow.py`，467 → 474）：

| 用例 | 断言 |
|---|---|
| `test_role_choice_switches_listener_and_guide` | guide↔listener 可切，原因 `user_choice`；已是该角色时原样 |
| `test_role_choice_ignores_auto_and_unknown` | `""` / `auto` / `crisis` / 未知值原样；`ROLE_CHOICES == ("listener", "guide")` |
| `test_role_choice_never_overrides_crisis` | crisis 不被改成 listener / guide |
| `test_role_choice_cannot_bypass_cooldown` | 手动 guide 仍被 `after_crisis` / `crisis_cooldown` 压回 listener |
| `test_p19_sidebar_switches_role_from_next_turn` | AppTest 选「引导者」→ 下一轮 `last_role=guide`、`last_reason=user_choice`、日志 role=guide |
| `test_p19_crisis_overrides_sidebar_choice` | 选「倾听者」后说危机句 → `CRISIS_REPLY`、`last_role=crisis` |
| `test_p19_choice_cannot_revive_guide_after_crisis` | 危机后选「引导者」→ 下一轮仍是 `listener` / `after_crisis` |

真实渲染探针（`p19_role_switch_2026-11-18.py`，AppTest 跑真 `app.py`，MOCK）：

```text
label    : 当前角色（可切换）
options  : ['自动判断', '倾听者', '引导者']
current  : auto / index 0
caption  : ['这一轮：倾听者 · 切换原因：自然延续']
侧栏 metric 只剩: ['当前风险等级']

--- 选「引导者」后说一句普通的话 ---
caption  : ['这一轮：倾听者 · 切换原因：自然延续', '手动选择从下一轮开始；危机与危机后的缓冲期由系统接管。']
last_role=guide last_reason=user_choice

--- 选「倾听者」后说危机句 ---
last_role=crisis last_reason=crisis_shortcircuit

--- 危机后改选「引导者」，再说一句求助 ---
last_role=listener last_reason=after_crisis
caption  : ['这一轮：倾听者 · 切换原因：本会话出现过危机', '手动选择从下一轮开始；危机与危机后的缓冲期由系统接管。']

--- 选回「自动判断」 ---
last_role=listener last_reason=default
caption  : ['这一轮：倾听者 · 切换原因：自然延续']
```

完整输出见 `p19_role_switch_2026-11-18.txt`。

行数（单文件 ≤350 / 单函数 ≤40）：

```text
companion_ui.py 162 / coordinator.py 141 / orchestrator.py 250 / panel.py 141
tests/test_flow.py 317（测试文件不在行数预算内）
```

## 7. 决策与理由

1. **做成下拉框，而不是两个按钮**：角色是"当前状态"而不是"动作"，下拉框天然表达"现在是哪个"，
   也留得住 `auto` 这个默认态；两个按钮会让"取消手动选择"无处安放。
2. **保留 `auto` 并设为默认**：这是"零行为变化"的唯一办法。默认仍是状态机判定，
   旧用例、四指标、演示脚本都不用改；想手动指定的人才去动它。
3. **crisis 不进选项**：见 §3；同时 `apply_role_choice` 里再挡一层。
4. **把选择接在 `decide_with_choice` 里、不新增节点**：`orchestrator` 有 250 行硬上限和九节点
   顺序测试，新增节点会同时踩两条；在 coordinator 节点内组合，语义上也最贴切
   （"定角色"本来就该包含"用户指定"）。
5. **原因记 `user_choice` 而不是复用 `default`**：侧栏、日志、以后的复盘都要能分清
   "系统自己选的"和"用户自己选的"，否则手动切换在数据上不可见。
6. **文案说"从下一轮开始"**：选择发生在侧栏渲染时，当轮已经答完；下一轮若遇冷却/危机
   还会被系统接管，所以不能承诺"立刻生效"。

## 8. 未做 / 待人工

- 未做真机浏览器截图（本机以 AppTest 驱动真 `app.py` 验证渲染与行为，见 §6）。
- 线上 <https://xinyu-mindisle.streamlit.app> 仍是旧版本；按既定流程在 `agent-v2` 继续开发，
  发布时再合入 `main` 触发重部署。
- 未跑 `metrics.py`：`guardian` / 角色判定 / RULES 均未动，四指标口径不变。
