# S16 · 会话级聚合 + 风险地板

| 项 | 内容 |
|---|---|
| 步骤 | S16 / 26 |
| 阶段 | W3 |
| 工时 | 4 人时（P1 + P3） |
| 风险 | **高**——两次改动叠加容易把"只升不降"写反，等级降下去就是事故 |
| 依赖 | S15 |
| 回滚 | `git checkout -- coordinator.py app.py` |

## 1 这一步做什么

两件相关的事：

- **风险地板**：等级在窗口内不许降（今天说过 L3，后面 5 轮至少还是 L2）。
- **会话聚合**：5 轮里反复出现 L2，说明不是偶然，升级为 L3。

产出：`risk_floor()` / `aggregate_level()` 两个纯函数 + app 接线 + 4 条测试。

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 窗口 | `list[int]` 存等级序数 | 1=L1 2=L2 3=L3，比字符串好算 |
| 状态 | `st.session_state["levels"]` | 不进 memory.json |
| 判定 | 纯函数 | 可单测、可复现 |

## 3 前置检查

```powershell
pytest -q        # 52 passed
```

## 4 硬要求

1. **只升不降**：任何函数返回的等级 $\ge$ 输入等级。写完全组交叉审这一条。
2. 聚合升级阈值：**窗口 5 轮内 L2 ≥ 3 次 → L3**。用 3 不用 2，理由是"一天里两次'没意思'很正常"。
3. 窗口是**滑动**的，只保留最近 `N_WINDOW=5` 条。
4. 升级后必须写日志 `action="aggregate_escalate"`，便于报告里数次数。
5. 降级只允许由 `COOLDOWN` 到期触发（S11 的 `crisis_cooldown`），不许由"看起来好点了"触发。

## 5 执行步骤

### 5.1 序数换算

```python
RANK = {"L1": 1, "L2": 2, "L3": 3}
NAME = {1: "L1", 2: "L2", 3: "L3"}

def _rank(level: str) -> int: return RANK.get(level, 1)
def _name(n: int) -> str:  return NAME.get(max(1, min(3, n)), "L1")
```

### 5.2 地板

```python
def risk_floor(history: list[str], current: str) -> str:
    """窗口内出现过的最高等级，作为本轮下限。等级只升不降。"""
    if not history:
        return current
    floor = max(_rank(x) for x in history[-N_WINDOW:])
    return _name(max(floor, _rank(current)))
```

### 5.3 聚合

```python
def aggregate_level(history: list[str], current: str) -> str:
    """5 轮内 L2 及以上 ≥3 次 → 升 L3；否则只做地板。"""
    window = (history + [current])[-N_WINDOW:]
    l2plus = sum(1 for x in window if _rank(x) >= 2)
    if l2plus >= 3:
        return "L3"
    return risk_floor(history, current)
```

### 5.4 app 接线

```python
levels = st.session_state.setdefault("levels", [])
raw = pre["level"]
eff = aggregate_level(levels, raw)          # 本轮实际生效等级
if eff != raw:
    log_turn(session_hash=session_hash(sid), turn=turn, level=eff, role="crisis",
             rule_ids=pre["rule_ids"], action="aggregate_escalate", rewrite=0, latency_ms=0)
levels.append(eff); st.session_state["levels"] = levels[-N_WINDOW:]
```

之后所有分支（短路、coordinator、post_check）都用 `eff`，**不许再用 raw**。
grep 检查：`pre["level"]` 在接线之外不应再出现。

### 5.5 四条测试

| # | history | current | 期望 |
|---|---|---|---|
| 1 | [] | L1 | L1 |
| 2 | [L3, L2] | L1 | L2（地板来自 L2，L3 超出窗口另测） |
| 3 | [L2, L2, L1] | L2 | L3（3 次 L2+） |
| 4 | [L2, L2] | L1 | L2（2 次不升级，但地板生效） |

第 4 条是"阈值没用错"的关键：**2 次必须不升级**。

## 6 验证

```powershell
pytest -q      # 56 passed
```

页面手测：连发 3 句"没意思" → 第 3 轮应该出危机卡（聚合升级），日志出现 `aggregate_escalate`。

## 7 回滚

```powershell
git checkout -- coordinator.py app.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 等级会掉下去 | 地板写在聚合之后又被覆盖 | 只允许 `eff` 一个变量往下传 |
| 第 3 次没升级 | 窗口只算 history 不含当前轮 | 用 `history + [current]` |
| 升到 L3 后永远下不来 | 地板窗口是"全部历史" | 只取 `[-N_WINDOW:]` |
| 日志里每轮都 escalate | 拿 eff 与 raw 比，但 history 已含 eff | 先比再 append，顺序不能反 |

## 9 出口清单

- [ ] 56 passed
- [ ] 页面连发 3 次 L2 会升级
- [ ] grep 确认只有 `eff` 往下传
- [ ] `aggregate_escalate` 有日志

## 10 回执

```text
S16 完成：56 passed / 3 次 L2 升级 / 地板生效
下一步：S17 摘要节流
```