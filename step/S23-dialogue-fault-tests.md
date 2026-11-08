# S23 · 12 条对话测试 + 8 条故障注入

| 项 | 内容 |
|---|---|
| 步骤 | S23 / 26 |
| 阶段 | W4 |
| 工时 | 6 人时（P1 + P3） |
| 风险 | 中——对话测试依赖 MOCK，写不好会变成"测了假人" |
| 依赖 | S22 |
| 回滚 | `git checkout -- tests/` |

## 1 这一步做什么

两组测试：

- **12 条对话测试**（`test_flow.py`）：多轮流程，验证角色切换、冷却、聚合、记忆写入。
- **8 条故障注入**（`test_fault.py`）：把外部依赖弄坏，验证系统**不崩且更严**。

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 对话 | MOCK_LLM=1 + 假 memory（tmp_path） | 不联网、不碰真盘 |
| 注入 | `monkeypatch` 替换 `call_llm` / `open` | 只替换边界，不改被测逻辑 |
| 断言 | 结构化字段 | 不断言自然语言 |

## 3 前置检查

```powershell
pytest -q        # 77 passed
```

## 4 硬要求

1. 12 条对话**必须走完整管线**（pre → coordinator → prompt → llm → post → memory），不许只测单个函数。
2. 8 条故障注入**必须断言"更严"**：失败后等级不减、回复不发坏内容、日志有记录。
3. 测试不联网：`MOCK_LLM=1` 写进 `conftest.py` 的 fixture，不靠人记得设环境变量。
4. 每个测试用独立 `tmp_path` 会话，**不许共用** `data/memory`。

## 5 执行步骤

### 5.1 conftest.py

```python
@pytest.fixture(autouse=True)
def _mock(monkeypatch, tmp_path):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    yield
```

### 5.2 十二条对话（C-01 ~ C-12）

| # | 流程 | 断言 |
|---|---|---|
| C-01 | 单轮问候 | role=listener，level=L1 |
| C-02 | 三轮倾诉 | 记忆 emotion_tags 非空 |
| C-03 | 直接求助 | role=guide |
| C-04 | 危机一句话 | role=crisis，回复含 12356 |
| C-05 | 危机后第二轮 | role=listener，reason=after_crisis |
| C-06 | 冷却期内求助 | 仍 listener（不许回 guide） |
| C-07 | 连续 3 次 L2 | 第 3 次 level=L3 |
| C-08 | 刷新后恢复 | 记忆字段还在，messages 为空 |
| C-09 | 跨会话隔离 | A 的记忆不出现在 B |
| C-10 | 清除记忆 | 回默认值 |
| C-11 | 摘要触发 | 第 5 轮 summary_at_turn 更新 |
| C-12 | 无命中闲聊 | level=L1，rule_ids=[] |

### 5.3 八条故障注入（F-01 ~ F-08）

| # | 注入 | 期望 |
|---|---|---|
| F-01 | `call_llm` 抛 TimeoutError | 友好提示，等级不降，日志 reason 含 timeout |
| F-02 | LLM 返回非 JSON | safe_json 兜住，不崩 |
| F-03 | 记忆文件损坏（写入 `{{{`） | 读回默认值，自愈补写 |
| F-04 | 记忆目录只读 | 写入失败但对话继续 |
| F-05 | 日志目录只读 | 对话继续，仅 WARN |
| F-06 | 缺 `LLM_API_KEY` 且 MOCK=0 | 启动即报错（人话），不静默转 mock |
| F-07 | 复核返回 `{"pass": true}` 但回复含诊断 | 规则仍拦（规则优先） |
| F-08 | 极度长输入（5000 字） | 正常处理或截断，不超时崩 |

```python
def test_f01_timeout(monkeypatch):
    monkeypatch.setattr(agent, "call_llm", lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
    out = run_pipeline("我今天很累")
    assert out["level"] in ("L1", "L2", "L3")   # 不崩
    assert "timeout" in out["log"]["reason"]
```

## 6 验证

```powershell
pytest tests/test_flow.py -q     # 12 passed
pytest tests/test_fault.py -q    # 8 passed
pytest -q                        # 97 passed
```

破坏性验证：把 F-03 的损坏文件换成合法 JSON 但缺字段 → 测试应仍红（说明测试真在检查）。

## 7 回滚

```powershell
git checkout -- tests/
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 测试偶尔失败 | 共用同一 memory 文件 | 每例 `tmp_path` |
| 测试跑了真 API | 忘了 MOCK | conftest 强制设 |
| 故障注入后仍"通过" | 断言太松 | 必须断言 reason/字段，不只断言"没抛异常" |
| 5000 字输入把测试拖慢 | 规则逐句扫 | 截断到 2000 字再判（写进代码） |

## 9 出口清单

- [ ] 12 + 8 全绿
- [ ] conftest 强制 MOCK 与 tmp 目录
- [ ] 每条注入都断言"更严"或"不崩"
- [ ] 总测试数 97

## 10 回执

```text
S23 完成：12 对话 + 8 注入 / 94 passed / 破坏性验证 1 次
下一步：S24 指标脚本与冻结 v1.0
```