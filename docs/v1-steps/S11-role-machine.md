# S11 · 三角色状态机

| 项 | 内容 |
|---|---|
| 步骤 | S11 / 26 |
| 阶段 | W2 |
| 工时 | 4 人时（P2） |
| 风险 | 中——决策错了不会出安全事故，但演示会显得"笨" |
| 依赖 | S10 |
| 回滚 | `git checkout -- coordinator.py app.py` |

## 1 这一步做什么

实现 `coordinator_decide(memory, user_text, level)`：决定这一轮用**倾听者 / 引导者 / 危机**哪个角色说话。

产出：

1. `coordinator_decide` 纯函数（3 参数，不读会话状态）
2. `enforce_cooldown(decision, cooldown_left, ever_crisis)` 冷却与降级（把状态留在 app）
3. `app.py` 接上冷却计数
4. 4 条测试

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 判定 | 关键词集合 + 等级 | 不用模型判角色（省一次调用，且可解释） |
| 状态 | `st.session_state["cooldown"]` | **不进 memory.json**，它是 UI 状态 |
| 降级 | 纯函数 | 冷却/历史危机只作用于"引导者" |

## 3 前置检查

```powershell
pytest tests/test_guardian.py -q      # 16 passed
python -c "import coordinator; print(coordinator.coordinator_decide({}, '我该怎么办', 'L1'))"
```

## 4 硬要求

1. **L3 永远 crisis**，不看用户说什么。危机时"给建议"是错的。
2. **crisis → listener，永不回 guide**：一次危机之后，本会话不再进引导者（靠 `ever_crisis`）。
3. 冷却期（`COOLDOWN=3` 轮）内降为 listener，理由写 `crisis_cooldown`。
4. `reason` 用固定枚举，不许自由文本：`crisis_shortcircuit / user_ask_advice / sustained_negative / default / crisis_cooldown / after_crisis`。
5. 纯函数：不写文件、不读 `st`。

## 5 执行步骤

### 5.1 判定顺序（自上而下，命中即返回）

| 序 | 条件 | role | reason |
|---|---|---|---|
| 1 | `level == "L3"` | crisis | crisis_shortcircuit |
| 2 | 冷却中 / 本会话有过危机 | listener | crisis_cooldown / after_crisis |
| 3 | 有求助词（怎么办/建议/该不该/如何/怎么选/帮我分析）且 level != L3 | guide | user_ask_advice |
| 4 | 其他 | listener | default |

### 5.2 代码

```python
ADVICE_WORDS = ("怎么办", "建议", "该不该", "如何", "怎么选", "帮我分析", "要不要")

def coordinator_decide(memory: dict, user_text: str, level: str) -> dict:
    """选角色。只读 memory 的 current_role，不读也不写会话状态。"""
    if level == "L3":
        return {"role": "crisis", "reason": "crisis_shortcircuit"}
    if any(w in (user_text or "") for w in ADVICE_WORDS):
        return {"role": "guide", "reason": "user_ask_advice"}
    return {"role": "listener", "reason": "default"}
```

`memory` 本步**只用于**判 `current_role == "crisis"`（历史遗留），其余不看。别用它判情绪——情绪靠 level。

### 5.3 冷却（app 侧，可测的纯函数）

```python
def enforce_cooldown(decision: dict, cooldown_left: int, ever_crisis: bool) -> dict:
    """冷却期内降为 listener；本会话有过危机则永不回 guide。"""
    if decision["role"] != "guide":
        return decision
    if ever_crisis:
        return {"role": "listener", "reason": "after_crisis"}
    if cooldown_left > 0:
        return {"role": "listener", "reason": "crisis_cooldown"}
    return decision
```

### 5.4 app 接线

```python
cd = coordinator_decide(memory, user_text, pre["level"])
cd = enforce_cooldown(cd, st.session_state.get("cooldown", 0), st.session_state.get("ever_crisis", False))
if pre["level"] == "L3":
    st.session_state["cooldown"] = COOLDOWN
    st.session_state["ever_crisis"] = True
st.session_state["cooldown"] = max(0, st.session_state.get("cooldown", 0) - 1)
```

顺序：先判 L3（置冷却）→ 再减 1。这样 L3 那轮之后还有 `COOLDOWN-1` 轮余量。

### 5.5 四条测试

| # | 输入 | 期望 |
|---|---|---|
| 1 | level=L3，文本="今天天气不错" | crisis（等级压倒文本） |
| 2 | level=L1，"我该怎么办" | guide / user_ask_advice |
| 3 | level=L1，"今天好累" | listener / default |
| 4 | guide + `ever_crisis=True` | listener / after_crisis |

## 6 验证

```powershell
pytest -q                        # 39 passed
streamlit run app.py
```

页面手测三句：`我好累` → 倾听；`我该怎么办` → 引导；`我不想活了` → 危机 + 之后三轮都不给建议。

## 7 回滚

```powershell
git checkout -- coordinator.py app.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 危机后还给你建议 | 只看了 level，没记 ever_crisis | 必须两个条件都判 |
| 每句都进 guide | 求助词太宽（把"怎么"也算） | 用词表，别用"怎么"这种半句 |
| 刷新后冷却没了 | cooldown 存在 session_state | 属预期，写进报告"刷新重置会话状态" |
| reason 出现自由文本 | 顺手写了原因 | 枚举必须固定，日志要统计 |

## 9 出口清单

- [ ] 4 条测试绿，`pytest -q` 39 passed
- [ ] 页面手测三句符合预期
- [ ] reason 只用六个枚举值
- [ ] coordinator 没有 `import streamlit`

## 10 回执

```text
S11 完成：4 passed / 三角色可用 / 危机后不回 guide
下一步：S12 日志与侧栏（打 tag v0.2）
```