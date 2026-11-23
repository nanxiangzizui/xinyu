# P39 证据：角色卡对话记录 + 对话中改卡

- 日期：2026-11-21
- 环境：Windows / Python 3.11 / pytest；`MOCK_LLM=1`，临时 `DATA_DIR`（`tests/conftest.py`）
- 代码：未提交
- 原始输出：`docs/evidence/P39-pytest-2026-11-21.txt`

## 1. 命令与结果

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# 699 passed in 42.55s

.\.venv\Scripts\python.exe contract_check.py
# 11/11 signatures OK
# 5/5 constants OK
# 20/20 rules OK
```

P39 新增 21 条测试，全部通过：

| 文件 | 条数 | 覆盖 |
|---|---:|---|
| `tests/test_rolecard_chat_store.py` | 9 | roundtrip/标题、坏 id/空消息/坏卡、坏 JSON、L3 `ever_crisis`、删除/清空、30 段上限、400 条截断、原子写、保存失败 |
| `tests/test_rolecard_history_app.py` | 7 | 发一轮后列出、同 sid 重开继续、新建不覆盖、删除二次确认、L3 结束页与恢复地板、`ROLECARD_HISTORY=0` 旧行为、关于页计数/清空 |
| `tests/test_rolecard_edit_app.py` | 5 | 面板与 name/work 锁定、改 voice 后下一轮 prompt 生效且状态不变、非法内容拒绝、5000 字预算、`ROLECARD_EDIT=0` 隐藏 |

## 2. 行为证据（AppTest）

### 2.1 保存与恢复

1. 进入角色卡模式，加载示例卡，发一轮。
2. `rolecard_chat_store.count(sid) == 1`，目录下出现 `$DATA_DIR/rolecards/chats/<sid>/rc-*.json`。
3. 用同一个 `Chat(sid=...)` 重建页面，点「对话记录」。
4. 列表显示 `阿岚 · MM-DD HH:MM`，点「继续」后：
   - 历史消息条数恢复；
   - `rc_sid` 仍是原 id；
   - `rc_state["turn"]` 恢复；
   - 再发一句，记录更新而不是新建一条。

### 2.2 L3 暂停

- L3 轮次保存 `ended=true`，并保留 `levels` 中的 `"L3"`。
- 重新打开该记录时进入结束页，有资源卡、下一步、恢复按钮，输入框关闭。
- 点「我好些了，继续吧」后 `ended=false`，仍用同一 `rc_sid`；`ever_crisis` 仍为 `true`，下一轮至少 L2。
- 保存顺序是「先 `mark_crisis`/`rc_ended=True`，再保存，再 rerun」，刷新不会绕过暂停。

### 2.3 对话中改卡

- 聊天页顶部有「当前角色卡 · 卡名」；点「编辑这张卡」后可改 identity / setting / voice / address / user_role / stage / examples / taboos / lore。
- 保存后 `rc_sid`、消息列表、`turn` 不变；下一轮 `safe_call` 的 prompt 里出现新 `voice`。
- 刷新后从记录恢复的是编辑后的卡。
- 非法内容（诊断、专业身份、恋爱等）与超过 5000 字的 prompt 被拒绝，原卡不变。
- `name` / `work` / `origin` 只读；理由写进面板：「它们决定长期记忆归到哪张卡」。

## 3. 数据与安全

- 路径：`$DATA_DIR/rolecards/chats/<sid>/<rc-xxxxxxxxxxxx>.json`。
- 唯一保存聊天原文的边界；只给 B 模式；不写日志、不联网、不进 A 模式 `memory.json`。
- `sid` 走 `memory.ID_RE`，会话 id 走 `^rc-[a-f0-9]{12}$`，防目录穿越。
- 卡走 `rolecard.normalize` + `rolecard.validate`；坏卡不落盘。
- 状态只持久化 9 个白名单键：`turn/cooldown/ever_crisis/levels/risk_signals/last_level/last_role/last_reason/degraded`；`last_trace` 丢弃。
- `ever_crisis` 在读取时重新计算：`raw or "L3" in levels`，手改 JSON 不能把 L3 洗白。
- 原子写复用 `episode_store.atomic_write`（`.bak` + tmp + replace）；删除同时删 `.bak` / `.tmp`。
- 关于页新增「角色卡对话记录（原文）」计数与删除；删除当前记录时重置 `rc_*`，避免下一句写回。
- 页头明示：记录在本地、不加密；同一链接的人能看到；云上重部署可能丢。

## 4. 已知限制

- 同一 URL 多标签同时聊，最后一次保存覆盖前一次，可能丢一轮。
- 云端磁盘是临时的，休眠/重部署会清空；没有云同步。
- 记录是明文 JSON，未加密。
- 本轮验证是 AppTest，没有真实浏览器截图；UI 视觉与移动端布局仍待人工看一眼。
- `rolecard_form.py` 352 行，是 P39 之前既有；本轮只 import `save_last`，没有继续扩大。
- `tests/test_help.py` 349 行，已贴 350 硬顶；下一轮再加关于页用例要先拆文件。

## 5. 回滚

- `ROLECARD_HISTORY=0`：不读写对话记录、不显示「对话记录」入口，回到 P38 的“刷新即失”。
- `ROLECARD_EDIT=0`：不渲染「当前角色卡」编辑面板。
- 两个开关都默认 `1`；代码与记录格式保留，不需要删数据。
