# S05 · app.py 最小闭环（聊天页 + 免责声明 + 10 轮不崩）

| 项 | 内容 |
|---|---|
| 步骤 | S05 / 26 |
| 阶段 | W1 |
| 工时 | 5 人时（P5） |
| 风险 | **中**——第一次把全链路接起来，容易暴露前面模块的假设错误 |
| 依赖 | S03 S04 |
| 回滚 | `git checkout -- app.py`（数据不动） |

## 1 这一步做什么

把六个模块按真实顺序串起来，做成一个能连续聊 10 轮不崩的页面。

产出：

1. `app.py`（≤250 行）：顶部免责声明 + 聊天区 + 侧栏
2. **固定管线**（后面 20 步都是往这条管线上换零件）
3. `session_id` 跨刷新保持（`st.query_params`）
4. 手动验收：10 轮不崩 + 刷新后记忆还在

## 2 技术栈

| 用途 | API | 要点 |
|---|---|---|
| 页面 | `st.set_page_config` | `layout="centered"`，title "心屿" |
| 聊天 | `st.chat_message` / `st.chat_input` | 历史放 `st.session_state.messages` |
| 侧栏 | `st.sidebar` | 角色 / 等级 / 记忆面板占位 |
| 会话 id | `st.query_params` | 刷新不丢；缺了就生成 |
| 主题占位 | `st.markdown(..., unsafe_allow_html=True)` | S19 才填 CSS |

## 3 前置检查

```powershell
pytest -q                    # memory 9 + agent 6 全绿
set MOCK_LLM=1
streamlit run app.py         # 能打开即可（还没有内容）
```

## 4 硬要求

1. **免责声明在第一屏**，不许折叠、不许滚屏才看到。
2. 界面**永不显示 traceback**；任何异常 → 一句人话 + 记日志。
3. 界面**不许直接调**模块内部函数；只走管线。
4. `st.session_state` 只放"这一屏的显示状态"，**跨刷新的东西一律进 `memory.json`**。
5. 空回复、超时、`ok=False` 都必须有兜底文案。

## 5 执行步骤

### 5.1 页面骨架

```python
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="心屿 · 情绪陪伴", layout="centered")
st.title("心屿")
st.caption("这是一个情绪陪伴工具，不是心理咨询，也不能替代真人帮助。"
           "如果你或身边的人有危险，请拨打 120 / 110 或 12356。")
```

> 免责声明写成 `st.caption` 而不是 `st.expander`：折叠起来就等于没有，老师第一眼会找它。

### 5.2 session_id 跨刷新

```python
SID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")      # 与 memory.ID_RE 同口径

def get_session_id() -> str:
    raw = st.query_params.get("u")
    raw = raw[0] if isinstance(raw, list) and raw else raw
    if isinstance(raw, str) and SID_RE.fullmatch(raw):
        return raw
    sid = uuid.uuid4().hex[:12]
    st.query_params["u"] = sid
    return sid
```

**必须校验**：sid 会被拼成文件名（`data/memory/<sid>.json`），`?u=../../x` 就是路径穿越。
校验失败不要报错，直接发新 id 即可——用户看不出差别，磁盘层也不会拿到脏字符串。

这是 W1 验收"刷新后记忆还在"的**唯一**正确做法：`session_state` 刷新即空。

### 5.3 固定管线（本文件的核心，背下来）

```python
def handle(text: str, sid: str) -> str:
    memory = read_memory(sid)
    pre = guardian_pre_check(text)                                  # ① 判危
    dec = coordinator_decide(memory, text, pre["level"])            # ② 定角色
    lore = match_lore(text)                                         # ③ 找事实
    persona = st.session_state.get("persona_id", "sister_heart")
    prompt = build_system_prompt(persona, memory, lore)             # ④ 拼 prompt
    resp = call_llm([{"role": "system", "content": prompt},
                     *st.session_state.messages[-10:]])             # ⑤ 生成
    post = guardian_post_check(text, resp["text"], pre["level"], dec["role"])  # ⑥ 审
    reply = post["fixed_reply"] or resp["text"] or FALLBACK_LINE
    update_memory(sid, text, reply)                                 # ⑦ 记
    return reply
```

**顺序不可调换**：先判危再生成（L3 不该花一次 API 调用），生成后必审（模型会说不该说的话）。
管线参数在 S10/S11/S13 会变，但**这七步的顺序**从今天到 v1.0 都不许变。

```python
FALLBACK_LINE = "我这边刚刚卡了一下，但我在。你可以再说一句吗？"
```

### 5.4 兜底：三种"不好看"不能给用户看

| 情况 | 界面表现 |
|---|---|
| `resp["ok"] is False` | 显示 `FALLBACK_LINE`，侧栏小字"网络不稳定" |
| 回复为空字符串 | 同上 |
| 任何 Python 异常 | 同上 + 写一行日志（类型名），**不显示堆栈** |

```python
try:
    reply = handle(text, sid)
except Exception as exc:
    _log_error(sid, type(exc).__name__)
    reply = FALLBACK_LINE
```

### 5.5 侧栏（本步只做占位）

```python
with st.sidebar:
    st.caption(f"会话 {sid[:6]}")
    st.metric("当前角色", "listener")
    st.metric("风险等级", "L1")
    with st.expander("它在记什么"):
        st.json(read_memory(sid))
    if st.button("清空这次对话"):
        clear_memory(sid)
        st.session_state.messages = []
        st.rerun()
```

S12 会把三个 `metric` 换成真实值，S18 会把 `st.json` 换成可操作的记忆面板。

### 5.6 10 轮压测（手动，2 分钟）

连续发这 10 句，中间不刷新：

```text
1 你好
2 最近有点累
3 期末好多事
4 我和室友处得不好
5 睡不着
6 不知道怎么办
7 算了不说了
8 今天吃了火锅
9 有点想家
10 谢谢你
```

要求：每一轮都有回复、侧栏不消失、控制台**没有** Traceback、第 10 轮之后刷新页面历史仍在。

## 6 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `streamlit run app.py` | 页面打开，首屏能看到免责声明 |
| 2 | 发"你好" | 3 秒内有回复（MOCK 立即） |
| 3 | 连发 §5.6 的 10 句 | 无崩溃、无 Traceback |
| 4 | `Ctrl+R` 刷新 | 会话 id 不变，页脚能读到同一份 memory |
| 5 | 点"清空这次对话" | 历史清空，`data/memory/<sid>.json` 消失 |
| 6 | 断网 + MOCK | 仍能回复 |
| 7 | 删掉 `.env` 里的 Key 且非 MOCK | 首屏红字提示缺 Key 并停止，**不渲染输入框** |

第 7 条最容易漏：配置错误要**当场说清楚**，不许伪装成“网络卡了一下”——那会把排查引到网络上去。`app._config_gate()` 就干这一件事。

## 7 回滚

```powershell
git checkout -- app.py
Remove-Item data\memory\*.json -ErrorAction SilentlyContinue
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 刷新后会话 id 变了 | 只 `set` 没 `get` | 先 `get` 再 `set`（见 §5.2） |
| 每刷新一次多一个 session | 同上 | 同上 |
| `st.chat_input` 不显示 | 放在 `st.columns` 里 | 必须在页面顶层调用 |
| 中文首屏慢 | 字体/网络 | 无解，属正常 |
| 侧栏 `st.json` 泄露隐私 | 面板显示原文 | 记忆里本来就不该有原文（S03 保证），面板只显示字段 |

> 注意：本系统**不保存原始对话**，所以刷新后**聊天记录本身不恢复**（恢复的是记忆字段）。
> W1 验收只要求"记忆在"，不要求"聊天记录在"——这点要在报告里写清楚，否则会被当成 bug。

## 9 出口清单

- [ ] 首屏可见免责声明（截图存 `docs/evidence/`）
- [ ] 10 轮不崩（截图）
- [ ] 刷新后 `data/memory/<sid>.json` 还在且字段有更新（截图）
- [ ] 断网 MOCK 能回
- [ ] 界面无 Traceback
- [ ] `contract_check.py` 11/11、`pytest -q` 全绿

## 10 回执

```text
S05 完成：管线 7 步接通 / 10 轮不崩 / 刷新会话 id 保持 / 断网 MOCK 可回
下一步：S06 部署
```
