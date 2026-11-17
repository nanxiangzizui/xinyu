# S10 · 短路主链路 + 危机资源卡

| 项 | 内容 |
|---|---|
| 步骤 | S10 / 26 |
| 阶段 | W2 |
| 工时 | 6 人时（P3 + P1 联调） |
| 风险 | **高**——第一次让"危机回复"真的发给用户，文案必须逐字审 |
| 依赖 | S09 |
| 回滚 | `git checkout -- guardian.py resources.py app.py` |

## 1 这一步做什么

让 L3 触发**短路**：不调用 LLM，直接发出固定的危机回复（含资源）。

产出：

1. `resources.pick_resources(level, emotion_tags)` 真实实现（L3 / L2 / L1 三档资源）
2. `guardian.CRISIS_REPLY` 模板（≤140 字，必含 12356 与 0571-87713518）
3. `app.py` 加入短路分支
4. `tests/test_guardian.py` 追加 10 条（D-01 ~ D-10，十条 H 规则各一条）

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 资源 | 写死的 dict 列表 | 不许联网查、不许让 LLM 生成 |
| 短路 | `if level == "L3"` 提前 return | 放在 `call_llm` **之前** |
| 文案 | 常量字符串 | 换行用 `\n`，不用 markdown 列表符号（Streamlit 会渲染） |

## 3 前置检查

```powershell
pytest tests/test_guardian.py -q     # 6 passed
python -c "import resources; print(resources.pick_resources('L3', []))"   # 现在是 []
```

## 4 硬要求

1. **L3 一律短路**：不生成、不重写、不让人设插手。危机时刻不允许模型自由发挥。
2. 危机文案必须含 `12356`（全国心理援助热线）与校心理中心电话 `0571-87713518`。
3. 文案不许出现：诊断词、追问细节、"我理解你"。
4. `pick_resources` 是**纯函数**：只看 level 与 tags，不读会话、不联网。
5. 资源列表里每条必须是真实可用的：热线 12356 / 110 / 120 / 校心理中心 0571-87713518。

## 5 执行步骤

### 5.1 危机模板（逐字审，不要改标点）

```python
CRISIS_REPLY = (
    "听到你这么说，我很在意你现在的安全。\n\n"
    "先做一件事：找一个此刻能陪着你的人，或打 12356（24 小时热线）。\n"
    "情况紧急请打 110 或 120。\n"
    "校心理中心 0571-87713518（工作日）。\n\n"
    "我不问你发生了什么，也不劝你什么。你想说的时候，我在这儿。"
)
```

三条硬审：

| 检查 | 通过标准 |
|---|---|
| 有资源 | 含 `12356` 且含 110/120 |
| 不追问 | 没有"怎么了""什么时候""为什么" |
| 不长篇 | ≤140 字（当前 125 字，不计换行） |

### 5.2 pick_resources

```python
RESOURCES = {
    "L3": [
        {"title": "全国心理援助热线", "detail": "12356（24 小时，免费）", "kind": "hotline"},
        {"title": "紧急求助", "detail": "110 / 120", "kind": "emergency"},
        {"title": "校心理中心", "detail": "0571-87713518（工作日）", "kind": "campus"},
    ],
    "L2": [
        {"title": "校心理中心", "detail": "0571-87713518（工作日）", "kind": "campus"},
        {"title": "呼吸练习", "detail": "吸气 4 秒，停 2 秒，呼气 6 秒，重复 5 次", "kind": "exercise"},
    ],
    "L1": [],
}

def pick_resources(level: str, emotion_tags: list[str]) -> list[dict]:
    """按等级返回资源卡；L1 不给资源（避免打扰）。"""
    return list(RESOURCES.get(level, []))
```

`emotion_tags` 本步**不用**，保留签名是为了 S20 之后能按标签细分（如"睡眠"给睡眠卫生卡片）。不要为了用而硬塞。

### 5.3 app 里的短路分支

在 `st.chat_input` 之后、`call_llm` 之前插入：

```python
pre = guardian_pre_check(user_text)
if pre["level"] == "L3":
    reply = CRISIS_REPLY
    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)
    for card in pick_resources("L3", []):
        st.info(f"{card['title']}：{card['detail']}")
    st.stop()          # 后面所有步骤都不执行
```

`st.stop()` 是关键：短路的意思就是**这一轮到此为止**，包括不写记忆、不调 LLM。

### 5.4 十条用例

```python
H_CASES = [
    ("我不想活了", "H01"), ("我想自杀", "H02"), ("我在割腕", "H03"),
    ("想跳楼", "H04"), ("我写好遗书了", "H05"), ("我攒了一瓶药", "H06"),
    ("今晚就结束", "H07"), ("我想杀了他", "H08"), ("我撑不下去了", "H09"),
    ("活着没意义", "H10"),
]
```

每条断言两件事：`level == "L3"` 且 `rule_id in rule_ids`。

## 6 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `pytest tests/test_guardian.py -q` | 16 passed |
| 2 | 页面输入"我不想活了" | 直接出危机卡，**不调用 LLM**（MOCK 关掉也能秒回） |
| 3 | 同上，看终端 | 没有 LLM 请求日志 |
| 4 | 输入"今天好累" | 正常走 LLM，不给资源卡 |
| 5 | 数危机文案字数 | ≤140，含 12356 与 0571-87713518 |
| 6 | 找一个人盲读危机文案 | 不觉得被审问、不觉得被敷衍 |

第 2 条是本步的核心验收：**断网也能出危机回复**。

## 7 回滚

```powershell
git checkout -- guardian.py resources.py app.py tests/test_guardian.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 危机时还是调了 LLM | 短路写在 `call_llm` 之后 | 必须在之前，且 `st.stop()` |
| 危机后还能继续聊上一轮上下文 | 消息没 append | 补 append，保持对话连贯 |
| 资源卡重复出现 | 每轮都渲染 | 只在 L2/L3 那一轮渲染一次 |
| 文案被 Streamlit 拆成列表 | 用了 `- ` 或 `1.` | 用 `·` 或纯换行 |
| 热线写成 12355/12345 | 记错 | **12356**，全国统一，2025 年启用 |

## 9 出口清单

- [ ] 16 passed（6 + 10）
- [ ] L3 页面实测：秒回 + 有资源卡 + 无 LLM 调用
- [ ] 危机文案 ≤140 字、含 12356 与 0571-87713518、无追问
- [ ] 校心理中心电话 0571-87713518 已写入文案与资源卡（提交前再拨一次）
- [ ] `contract_check.py` 11/11

## 10 回执

```text
S10 完成：16 passed / L3 断网可用 / 文案 125 字 / 资源 3 条
下一步：S11 三角色状态机
```
