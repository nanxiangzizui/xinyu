# S12 · 结构化日志 + 侧栏 + tag v0.2

| 项 | 内容 |
|---|---|
| 步骤 | S12 / 26 |
| 阶段 | W2 |
| 工时 | 3 人时（P4） |
| 风险 | 中——日志最容易顺手把用户原句写进去，这是隐私事故 |
| 依赖 | S11 |
| 回滚 | `git checkout -- logger.py app.py`；日志文件直接删 |

## 1 这一步做什么

每次对话写一行 JSON 日志（**不含用户原文**），并在侧栏显示当前状态与"清除记忆"按钮，然后打 `v0.2` 标签。

产出：

1. `logger.py`：`log_turn()` + `session_hash()`
2. 侧栏：当前等级 / 当前角色 / 记忆摘要 / 清除记忆按钮
3. `tests/test_log.py` 2 条（字段白名单、无原文）
4. `v0.2` tag

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 日志 | `json.dumps(ensure_ascii=False)` 追加写 | 一天一个文件 |
| 哈希 | `hashlib.sha256(session_id)[:12]` | 不可逆推，够区分 |
| 侧栏 | `st.sidebar` | 只读展示，不暴露规则细节 |

## 3 前置检查

```powershell
pytest -q          # 39 passed
git status         # 干净
```

## 4 硬要求

1. **日志字段白名单**，只有这 9 个：`ts / session_hash / turn / level / role / rule_ids / action / rewrite / latency_ms`。
2. **绝不写用户原文**、绝不写回复原文、绝不写人设 prompt。
3. 日志写失败不许影响对话：`try/except` 包住，失败只 `print` 一行警告（这是 §8.2 的"边界兜底"）。
4. 日志目录 `data/logs/` 已在 `.gitignore`，不许提交。
5. 侧栏不许显示规则 pattern（会被截图外传，也没意义）。

## 5 执行步骤

### 5.1 logger.py

```python
import hashlib, json, os
from datetime import datetime

LOG_DIR = os.getenv("LOG_DIR", "data/logs")

def session_hash(session_id: str) -> str:
    """session_id 的短哈希，用于日志区分会话但不泄露原始 id。"""
    return hashlib.sha256((session_id or "anon").encode("utf-8")).hexdigest()[:12]

def log_turn(**fields) -> None:
    """追加一行日志；字段白名单之外的键直接丢弃。"""
    allowed = {"ts", "session_hash", "turn", "level", "role", "rule_ids",
               "action", "rewrite", "latency_ms"}
    row = {k: v for k, v in fields.items() if k in allowed}
    row.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        path = os.path.join(LOG_DIR, datetime.now().strftime("%Y-%m-%d") + ".jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"[WARN] 日志写入失败：{type(exc).__name__}")   # 不许影响对话
```

### 5.2 在管线里插一行

```python
t0 = time.perf_counter()
# ... 原有管线 ...
log_turn(session_hash=session_hash(sid), turn=st.session_state.get("turn", 0),
         level=pre["level"], role=cd["role"], rule_ids=pre["rule_ids"],
         action="short_circuit" if pre["level"] == "L3" else "generate",
         rewrite=post.get("rewrite", 0),
         latency_ms=int((time.perf_counter() - t0) * 1000))
```

### 5.3 侧栏

```python
with st.sidebar:
    st.caption(f"会话 {session_hash(sid)[:6]} · 第 {turn} 轮")
    st.metric("当前风险等级", level_label)      # L1 平稳 / L2 留意 / L3 危机
    st.metric("当前角色", role_label)            # 倾听者 / 引导者 / 危机支持
    with st.expander("我记住了什么"):
        st.write({k: memory[k] for k in ("preferred_tone", "emotion_tags", "unresolved_issues")})
    if st.button("清除我的记忆"):
        clear_memory(sid); st.session_state.pop("messages", None); st.rerun()
```

等级显示用**中文标签**，不要直接显示 `L3`（演示时更友好，也不刺激用户）。

### 5.4 两条测试

```python
def test_log_fields_whitelist(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    logger.log_turn(session_hash="abc", user_text="我的秘密", level="L1")
    row = json.loads((tmp_path / f"{datetime.now():%Y-%m-%d}.jsonl").read_text("utf-8"))
    assert "user_text" not in row and "我的秘密" not in json.dumps(row, ensure_ascii=False)

def test_session_hash_stable():
    assert logger.session_hash("u1") == logger.session_hash("u1") != logger.session_hash("u2")
```

## 6 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `pytest -q` | 41 passed |
| 2 | 聊 3 轮，看 `data/logs/*.jsonl` | 3 行，9 个字段，**搜不到原句** |
| 3 | 侧栏点"清除我的记忆" | 记忆文件删除，页面重置 |
| 4 | 把 `LOG_DIR` 指到只读目录 | 对话照常，终端一行 WARN |
| 5 | `git status` | 没有 `data/logs` 被暂存 |

第 4 条别省：日志挂了不能连带对话挂。

## 7 回滚

```powershell
git checkout -- logger.py app.py
git tag -d v0.2          # 如果已经打了
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 日志里出现整段对话 | 把 messages 整个传进 log_turn | 白名单会拦，但别传 |
| 中文变 `\u4f60` | 忘了 `ensure_ascii=False` | 加上 |
| 日志文件被提交 | `.gitignore` 没生效（先 add 过） | `git rm --cached data/logs -r` |
| 侧栏每轮刷新闪一下 | 正常 | 不用管 |

## 9 出口清单

- [ ] 41 passed
- [ ] 日志 9 字段、无原文、写失败不影响对话
- [ ] 侧栏可清除记忆
- [ ] `git tag v0.2` 已打并推送

## 10 回执

```text
S12 完成：41 passed / 日志无原文 / tag v0.2
下一步：S13 post_check 骨架（重写与复检）
```