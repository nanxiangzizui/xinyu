# S18 · 记忆面板与导出

| 项 | 内容 |
|---|---|
| 步骤 | S18 / 26 |
| 阶段 | W3 |
| 工时 | 3 人时（P5） |
| 风险 | 低——只读展示，不动业务 |
| 依赖 | S17 |
| 回滚 | `git checkout -- app.py` |

## 1 这一步做什么

给用户一个"我记住了什么"的面板：能看、能改、能删、能导出。这是**记忆透明**的落地，也是答辩时最好讲的一块。

产出：

1. 侧栏记忆面板（8 字段可读化展示）
2. 单字段编辑（只允许改 `preferred_tone` 与 `coping_preferences`）
3. 导出 JSON / 清空
4. 2 条测试

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 展示 | `st.json` + 中文标签 | 不做复杂 UI |
| 编辑 | `st.selectbox / st.text_input` | 只开放两个字段 |
| 导出 | `st.download_button` | 文件名带日期 |

## 3 前置检查

```powershell
pytest -q        # 59 passed
```

## 4 硬要求

1. **只读为主**：8 个字段里只允许用户改 `preferred_tone` 与 `coping_preferences`，其余只显示。
2. 展示前必须过 `scrub()`，防止历史脏数据带出原句。
3. 导出只导出该会话的 JSON，不导出日志、不导出对话记录（本来也没存）。
4. 清空按钮必须有二次确认（`st.checkbox("我确认要清除")`）。

## 5 执行步骤

### 5.1 字段中文映射

```python
LABELS = {
    "preferred_tone": "希望的说话方式",
    "current_role": "当前角色",
    "role_switch_reason": "为什么换角色",
    "emotion_tags": "情绪标签",
    "unresolved_issues": "还没解决的事",
    "coping_preferences": "有用的安抚方式",
    "rolling_summary": "近期概况",
    "summary_at_turn": "概况更新于第几轮",
}
```

`last_updated` 不展示（对用户无意义）。

### 5.2 面板

```python
with st.sidebar.expander("我记住了什么", expanded=False):
    for k, cn in LABELS.items():
        st.caption(cn)
        st.write(memory.get(k) or "—")
    tone = st.selectbox("希望的说话方式", ["温柔", "直接", "轻松", "不评价"], index=0)
    if st.button("保存偏好"):
        memory["preferred_tone"] = tone; write_memory(sid, memory); st.rerun()
```

### 5.3 导出与清空

```python
st.download_button("导出我的记忆", data=json.dumps(memory, ensure_ascii=False, indent=2),
                   file_name=f"memory-{datetime.now():%Y%m%d}.json", mime="application/json")
if st.checkbox("我确认要清除全部记忆"):
    if st.button("清除"):
        clear_memory(sid); st.rerun()
```

### 5.4 两条测试

| # | 用例 | 断言 |
|---|---|---|
| 1 | 面板数据经 `scrub` | 输出里不含 `TEST_SECRET` 这类标记串 |
| 2 | `clear_memory` 后读 | 回到默认 8 字段，无残留 |

## 6 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `pytest -q` | 61 passed |
| 2 | 页面展开面板 | 8 个字段都是中文标签 |
| 3 | 改偏好后刷新 | 偏好保持（已落盘） |
| 4 | 导出 | JSON 可读，无原句 |
| 5 | 勾选确认后清除 | 文件删除、记忆回默认 |

## 7 回滚

```powershell
git checkout -- app.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 面板显示一坨 dict | 直接 st.write(memory) | 按字段拆开展示 |
| 用户改了 current_role | 开放了不该开放的字段 | 只留两个可编辑 |
| 清除后页面仍显示旧记忆 | 清了盘没清 session_state | `st.session_state.pop("memory")` |
| 导出里有角色 prompt | 导出了整个 session_state | 只导 memory |

## 9 出口清单

- [ ] 61 passed
- [ ] 面板 8 字段中文标签
- [ ] 仅两个字段可编辑
- [ ] 导出/清除均可用，清除有二次确认

## 10 回执

```text
S18 完成：61 passed / 面板可读可改可删 / 无原句
下一步：S19 三套主题
```