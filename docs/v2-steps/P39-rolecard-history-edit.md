# P39 角色卡对话记录 + 对话中改卡（已实现）

- 用户需求（m00001）：①角色卡模式保留对话，能像其他 AI 平台一样选择历史对话进入；②对话途中实时查看和更改角色卡内容。
- 用户确认（m00151）：列表标题用「卡名 + 时间」，其余按本计划执行。
- 实现日期：2026-11-21
- 基线：678 passed → 结果：**699 passed**；契约 11/11 + 5/5 + 20/20。

## 1. 目标与非目标

### 目标

1. B 模式每段对话按浏览器 URL 的 `sid` 落盘；刷新、关页、重新进入后可以从「对话记录」继续。
2. 列表同时显示卡名、轮次、更新时间、是否已暂停；支持继续、二次确认删除、新建对话。
3. L3 暂停的对话重新打开时仍是结束页；点「我好些了，继续吧」后沿用同一段记录，`ever_crisis` 与风险地板不丢。
4. 对话页顶部可展开「当前角色卡」，查看全部字段；可编辑除 `name` / `work` / `origin` 外的字段，保存后下一轮立即生效。
5. 编辑不换 `rc_sid`、不清空消息、不重置轮次、不切换 `rolecard_memory` 的卡键。

### 非目标

- 不做账号、云同步、跨设备；不做对话搜索、重命名、分支、导出。
- 不做「一张卡对应多段对话」的卡库；每段对话保存自己的卡快照。
- 不改 A 模式：陪伴模式聊天仍只在 `st.session_state`，刷新即失。
- 不改 `roles.RULES` 20 条、`guardian`、`coordinator`、`memory` 八字段白名单、`orchestrator` 九节点、契约 11 条。
- 不为对话记录调用 LLM 生成标题或摘要；标题只用卡名与本地时间。

## 2. 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 记录归属 | `$DATA_DIR/rolecards/chats/<sid>/` | 与 A 模式的 URL `sid` 身份一致；不同访客不串记录；`data/**` 已 gitignore |
| 一段对话的边界 | 一个 `rc-` id 一条 JSON | 与旧 `rc_sid` 同形，日志/排障可关联 |
| 卡的范围 | 每段对话保存卡快照 | 历史可复现；当前项目没有卡库，不能假设「最新卡」就是当时那张 |
| 对话中改名 | 锁定 `name` / `work` / `origin` | `rolecard_memory.card_key = sha256(name\|work)[:12]`，改名会静默换长期记忆文件 |
| 状态持久化 | 只存白名单 9 键 | 恢复后仍按 `ever_crisis` / `levels` / `risk_signals` 的地板走；`last_trace` 不落盘 |
| 上限 | 每 sid 30 段；每段 400 条消息 | 防目录无限增长；超出保留最近 400 条并标 `truncated` |
| 标题 | `卡名 · MM-DD HH:MM` | 用户指定；不把首句原文带进列表 |
| 开关 | `ROLECARD_HISTORY=1`、`ROLECARD_EDIT=1` | 默认开；`=0` 回到 P38 行为，便于回滚 |

## 3. 存储格式

路径：

```text
$DATA_DIR/rolecards/chats/<sid>/<rc-xxxxxxxxxxxx>.json
```

一条记录：

```json
{
  "version": 1,
  "id": "rc-ab12cd34ef56",
  "created_at": 1763690000.0,
  "updated_at": 1763690300.0,
  "title": "阿岚 · 11-21 10:58",
  "card": {"kind": "rolecard", "name": "阿岚", "...": "..."},
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "parts": ["..."], "sources": [], "gap": null}
  ],
  "state": {
    "turn": 1,
    "cooldown": 0,
    "ever_crisis": false,
    "levels": ["L1"],
    "risk_signals": ["无"],
    "last_level": "L1",
    "last_role": "listener",
    "last_reason": "default",
    "degraded": false
  },
  "ended": false,
  "truncated": false
}
```

### 写入时机

- 用户消息 append 后、调用模型前：生成到一半刷新，至少不丢刚说的话。
- assistant 消息与 `_finish_turn` 更新后：保存完整一轮。
- 编辑角色卡保存后：保存新卡快照。
- L3：先 `mark_crisis`、`rc_ended=True`、保存，再 `st.rerun()`；不会只留在内存。
- 恢复：先 `mark_resumed`、`rc_ended=False`、保存，再 rerun。
- 删除：`delete` 删主文件、`.bak`、`.tmp`；`clear` 删整个 sid 目录。

### 边界清洗

- `sid` 走 `memory.ID_RE`（1–32 位字母/数字/下划线/短横线）。
- `conv_id` 必须是 `^rc-[a-f0-9]{12}$`。
- 卡走 `rolecard.normalize` + `rolecard.validate`；不合法整条不读/不写。
- 消息只留 `user` / `assistant`；`parts` 只留字符串；`sources` 只留 `https://`；`gap` 只留固定键。
- `state` 白名单 + 夹紧；`ever_crisis = raw or "L3" in levels`，手改文件不能把 L3 洗白。
- 坏 JSON、坏卡、坏时间戳返回空/跳过，不把列表页打崩。

## 4. 页面流程

```text
gate（免责勾选）
  └─ rc_card 非空
       ├─ rc_ended=True  → 结束页（历史 + 资源 + 下一步 + 恢复/对话记录/陪伴）
       └─ rc_ended=False → 聊天页（历史 + 当前角色卡 + 输入 + 侧栏）
  └─ rc_view == "form"   → 建卡表单（新建对话）
  └─ 有历史记录          → 对话记录列表（继续 / 删除 / 新建）
  └─ 无历史记录          → 建卡表单（保持旧行为）
```

### 对话记录页

- 每条：标题、`N 轮 · 更新于 MM-DD HH:MM · 已暂停`（如已结束）。
- 「继续」：`load_into_session` 恢复卡、消息、状态、`rc_sid`、`ended`，再 rerun。
- 「删除」：先出确认条，确认后真删；删除当前会话时重置页面状态，防止下一句写回。
- 「＋ 新建对话」：新 `rc_sid`、空消息、新 state，回到建卡表单；上一段记录保留。
- 页头明示：只存在当前部署磁盘；同一链接的人能看到；云上重新部署可能丢。

### 对话中改卡

- 聊天页顶部 `st.expander("当前角色卡 · 卡名")`，只读展示身份、设定、口吻、称呼、对方身份、动作、示例、禁忌、角色认知。
- 「编辑这张卡」把字段写入 `rc_edit_*` 草稿；表单可改：
  - 身份、设定、口吻、称呼、对方身份、动作、两组示例、禁忌、角色认知。
- 锁定只读：角色名、作品名、来源。说明「这些决定长期记忆归到哪张卡；要换请新建对话」。
- 保存：
  1. `rolecard.normalize`；
  2. `rolecard.validate`；
  3. 用当前卡的长期记忆块预演 `rolecard.build_prompt`，超过 `MAX_PROMPT_CHARS=5000` 拒绝；
  4. 成功：更新 `rc_card`、`rc_last_card`、`save_last(card)`、当前对话记录；下一轮 `safe_run` 用新卡。
- 失败：错误留在表单原位，卡、消息、`rc_sid`、轮次都不变。
- `ROLECARD_EDIT=0`：不渲染面板。

## 5. 文件改动

| 文件 | 行数 | 作用 |
|---|---:|---|
| `rolecard_chat_store.py` | 316 | 纯存储：清洗、原子写、列表、读取、删除、上限 |
| `rolecard_conversations.py` | 121 | 会话胶水 + 列表 UI：reset / save_current / load / 删除 / 新建 |
| `rolecard_edit.py` | 157 | 对话中查看/编辑卡；校验与 5000 字预算 |
| `rolecard_ui.py` | 310 | 路由、保存点、L3 先保存再停、侧栏入口 |
| `about.py` | 136 | 新增「角色卡对话记录（原文）」计数与删除；更新数据说明 |
| `app.py` | 151 | `rolecard_ui.render(sid)`；`ROLECARD_HISTORY` / `ROLECARD_EDIT` 进 Secrets 白名单 |
| `tests/test_rolecard_chat_store.py` | 134 | 9 条存储测试 |
| `tests/test_rolecard_history_app.py` | 156 | 7 条历史流程测试 |
| `tests/test_rolecard_edit_app.py` | 116 | 5 条编辑流程测试 |
| `tests/test_help.py` | 349 | counts 断言加 `rolecard_chats` |

## 6. 验收

- 发一轮 → 同 `sid` 刷新 → 列表出现该记录 → 继续 → 消息、轮次、卡恢复。
- 新建对话不覆盖旧记录；删除必须二次确认；删当前记录后下一句不会写回。
- L3 记录打开仍是结束页；恢复后 `ever_crisis` 仍为真，下一轮至少 L2。
- 改 `voice` / `identity` 保存后：`rc_sid`、消息、轮次不变；下一轮 prompt 含新值；刷新后新卡仍在。
- 非法内容、超过 5000 字被拒；`name` / `work` 不可改。
- `ROLECARD_HISTORY=0` 不落盘、不显示列表；`ROLECARD_EDIT=0` 不显示编辑入口。
- `pytest -q` **699 passed**；`contract_check.py` 11/11 + 5/5 + 20/20。

## 7. 回滚与已知限制

- 回滚：`ROLECARD_HISTORY=0` 停止读写记录；`ROLECARD_EDIT=0` 隐藏编辑。代码保留，旧行为由开关恢复。
- 已知限制：
  - 同一 URL 多标签同时聊会以最后一次保存为准，可能互相覆盖。
  - 云上磁盘是临时的，休眠/重部署会清空；页面已明示。
  - 记录不加密；能拿到同一 URL 的人能看到同一 `sid` 的记录。
  - `rolecard_form.py` 仍是 352 行（P39 之前既有），P39 只 import `save_last`，未继续扩大。
  - 本轮的验证是 AppTest，不含真实浏览器截图。
