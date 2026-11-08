# S17 · 摘要节流（rolling_summary）

| 项 | 内容 |
|---|---|
| 步骤 | S17 / 26 |
| 阶段 | W3 |
| 工时 | 3 人时（P5） |
| 风险 | 中——摘要里写进原句就等于把隐私存到磁盘 |
| 依赖 | S16 |
| 回滚 | `git checkout -- memory.py` |

## 1 这一步做什么

让 `rolling_summary` 每 5 轮更新一次（而不是每轮），并且**只写概括，不写原句**。

产出：

1. `should_compress(turn, summary_len, summary_at_turn, level)`：三条件
2. `compress_summary(old, history)`：调一次 LLM 压缩
3. `summary_at_turn` 字段维护
4. 3 条测试

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 判定 | 纯函数 | 三个条件任一命中就压 |
| 压缩 | `call_llm` + `safe_json` | 失败就保留旧摘要（不许写空） |
| 落盘 | 既有 `write_memory` | 不新增路径 |

## 3 前置检查

```powershell
pytest -q                                    # 56 passed
python -c "from roles import SUMMARY_MAX, SUMMARY_EVERY; print(SUMMARY_MAX, SUMMARY_EVERY)"   # 200 5
```

## 4 硬要求

1. **三个触发条件**：① 距上次已满 `SUMMARY_EVERY=5` 轮；② 现有摘要超 `SUMMARY_MAX=200` 字；③ 首次进入 L3（立刻压一次，留档）。
2. 摘要**只许写**：情绪趋势、反复出现的话题、有效/无效的安抚方式。**禁止**写原句、人名、地点、具体事件细节。
3. 压缩失败 → 保留旧摘要 + 记日志，**绝不写空**。
4. 摘要长度硬截断到 200 字（`[:SUMMARY_MAX]`），截断也要记一次日志。
5. `summary_at_turn` 必须与实际压缩同步更新，否则节流失效。

## 5 执行步骤

### 5.1 判定

```python
def should_compress(turn: int, summary_len: int, summary_at_turn: int, level: str) -> bool:
    """三个条件任一成立就压缩；level 只用于"首次危机"判断。"""
    if level == "L3" and summary_at_turn == 0:
        return True
    if turn - summary_at_turn >= SUMMARY_EVERY:
        return True
    return summary_len > SUMMARY_MAX
```

### 5.2 压缩 prompt（关键在"禁止写原句"）

```python
SUMMARY_SYS = ("把下面这段对话概括成不超过 120 字的第三人称摘要。"
               "只写：情绪趋势、反复出现的话题、对方接受/拒绝的安抚方式。"
               "禁止出现：原句引用、人名、地名、机构名、具体事件细节。"
               "只输出摘要正文，不要标题。")
```

### 5.3 压缩函数

```python
def compress_summary(old_summary: str, recent_lines: list[str]) -> str | None:
    """压一次摘要；失败返回 None（调用方保留旧值）。"""
    text = "旧摘要：" + (old_summary or "无") + "\n近期对话：\n" + "\n".join(recent_lines[-SUMMARY_EVERY:])
    out = call_llm([{"role": "system", "content": SUMMARY_SYS},
                    {"role": "user", "content": text}], temperature=0.3)
    if not out.get("ok") or not out.get("text"):
        return None
    return out["text"].strip().replace("\n", " ")[:SUMMARY_MAX]
```

`recent_lines` 由 app 传入"切过标签的短句"，**不要传完整用户原话**；传之前先过一遍 `scrub()`。

### 5.4 接线

```python
mem = read_memory(sid)
if should_compress(turn, len(mem["rolling_summary"]), mem["summary_at_turn"], eff):
    new_sum = compress_summary(mem["rolling_summary"], recent_lines)
    if new_sum:
        mem["rolling_summary"] = new_sum
        mem["summary_at_turn"] = turn
        write_memory(sid, mem)
        log_turn(..., action="summary_compress", ...)
```

### 5.5 三条测试

| # | 场景 | 期望 |
|---|---|---|
| 1 | turn=6, summary_at_turn=1 | True（满 5 轮） |
| 2 | 摘要 210 字 | True（超长） |
| 3 | 压缩返回 None | 旧摘要不变、不写盘 |

## 6 验证

```powershell
pytest -q                        # 59 passed
type data\memory\<sid>.json      # 看 rolling_summary 与 summary_at_turn
```

手测：聊 10 轮，摘要应该只更新 2 次（第 5、10 轮），不是 10 次。

## 7 回滚

```powershell
git checkout -- memory.py app.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 每轮都压缩 | summary_at_turn 没更新 | 写到内存后必须 write_memory |
| 摘要里出现原话 | prompt 没禁 / 传了原话 | 两头都堵：prompt 禁 + 传 scrub 后的短句 |
| 摘要越压越短直到空 | 拿摘要压摘要 | 传近期对话，不是传旧摘要当输入 |
| 200 字截断把句子切断 | 直接切片 | 允许；摘要不是给人读的信 |

## 9 出口清单

- [ ] 59 passed
- [ ] 10 轮只压缩 2 次
- [ ] 摘要无原句、无人名
- [ ] 压缩失败不留空

## 10 回执

```text
S17 完成：59 passed / 10 轮压 2 次 / 失败保留旧值
下一步：S18 记忆面板
```