# S04 · agent.py 调用层（MOCK / 超时 / 兜底）

| 项 | 内容 |
|---|---|
| 步骤 | S04 / 26 |
| 阶段 | W1 |
| 工时 | 5 人时（P2） |
| 风险 | **中**——外部网络，但已有 MOCK 与兜底，坏了不影响演示 |
| 依赖 | S02 |
| 回滚 | `git checkout -- agent.py tests/test_agent.py` |

## 1 这一步做什么

把"调模型"这一件最不可控的事，包成一个**永远返回 dict、永远不抛异常**的函数。

产出：

1. `call_llm(messages, temperature=0.7) -> dict` 实现
2. MOCK 模式（无网络也能演示、也能跑测试）
3. `safe_json(text)` 解析兜底（S14 会用）
4. `tests/test_agent.py` 6 条

**不做**：`build_system_prompt` 的真实拼接（S07）、流式输出（砍掉了，延迟不值得）。

## 2 技术栈

| 用途 | 手段 | 关键参数 |
|---|---|---|
| SDK | `openai`（OpenAI 兼容） | `base_url="https://api.deepseek.com"` |
| 模型 | `deepseek-chat` | 从 `.env` 读，代码里给默认值 |
| 超时 | SDK 参数 `timeout=TIMEOUT` | 15 秒，不许改大 |
| 重试 | `max_retries=1` | 只重试一次，第二次失败就兜底 |
| 环境 | `python-dotenv` | 入口处 `load_dotenv()` 一次 |

## 3 前置检查

```powershell
python contract_check.py         # 11/11
python -c "import openai; print(openai.__version__)"
```

没有 Key 也能做这一步：全程 `MOCK_LLM=1`。

## 4 硬要求

1. **返回值永远是 dict**，四个键固定：`text / ok / error / latency_ms`。
2. `error` **只放异常类型名**（`TimeoutError`、`APIError`），不放 exception 内容——里面可能带 Key 或用户原文。
3. 缺 `LLM_API_KEY` 且不是 MOCK → **抛 `RuntimeError`**（人话），不许返回空字符串假装成功。
4. MOCK 必须**确定性**：同样输入同样输出，否则测试没法断言。
5. 不打印任何请求/响应正文；只在 debug 级别打长度与耗时。

## 5 执行步骤

### 5.1 客户端（懒加载，别在 import 时建）

```python
from roles import TIMEOUT

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("LLM_API_KEY"),
                         base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"))
    return _client
```

> import 时就建客户端，会让 `contract_check.py` 在没 Key 的机器上直接崩。懒加载是为了让校验脚本永远能跑。

### 5.2 主函数

```python
def call_llm(messages: list[dict], temperature: float = 0.7) -> dict:
    """调模型。永不抛异常（缺 Key 除外，那是配置错误，必须当场报）。"""
    if _is_mock():
        return _mock(messages)
    if not os.getenv("LLM_API_KEY"):
        raise RuntimeError("缺少 LLM_API_KEY：请在 .env 填 Key，或设 MOCK_LLM=1 离线运行")

    t0 = time.time()
    try:
        resp = _get_client().chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            messages=messages,
            temperature=temperature,
            timeout=TIMEOUT,
            max_retries=1,
        )
        text = (resp.choices[0].message.content or "").strip()
        return {"text": text, "ok": bool(text), "error": "", "latency_ms": _ms(t0)}
    except Exception as exc:                      # 边界 1/4：LLM 调用
        return {"text": "", "ok": False, "error": type(exc).__name__, "latency_ms": _ms(t0)}
```

**注意 `raise` 的位置**：缺 Key 在 try **之前**，所以它不会被吞掉——这是"只在边界兜底，不吞配置错误"的具体写法（见 mdc §8.2）。

### 5.3 MOCK：三条固定剧本

| 触发 | 返回 | 用途 |
|---|---|---|
| 默认 | 三句共情话之一（按 hash 选，确定性） | 无网络演示、CI 测试 |
| `__fail__` 在最后一条用户消息里 | `ok=False, error="MockFailure"` | 测降级链 |
| `__unsafe__` 在最后一条用户消息里 | 含"你应该振作起来"这种说教句 | 测 S13 重写、S15 说教词 |

```python
def _mock(messages: list[dict]) -> dict:
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if "__fail__" in last:
        return {"text": "", "ok": False, "error": "MockFailure", "latency_ms": 0}
    if "__unsafe__" in last:
        return {"text": "这没什么大不了的，你应该振作起来。", "ok": True, "error": "", "latency_ms": 0}
    idx = abs(hash(last)) % len(MOCK_LINES)
    return {"text": MOCK_LINES[idx], "ok": True, "error": "", "latency_ms": 0}
```

### 5.4 safe_json：模型返回 JSON 的兜底

```python
FENCE = chr(96) * 3            # 三个反引号，避免源码里出现 markdown 围栏

def safe_json(text: str) -> dict | None:
    """剥掉 markdown 围栏后解析。失败返回 None（调用方按中风险处理，不许当无事）。"""
    if not text:
        return None
    s = text.strip()
    if s.startswith(FENCE):
        s = s.split(FENCE)[1]
        s = s[4:] if s.lower().startswith("json") else s
    try:
        data = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None
```

### 5.5 测试（6 条，全部离线）

| # | 用例 | 断言 |
|---|---|---|
| 1 | MOCK 同输入两次 | `text` 完全相同（确定性） |
| 2 | MOCK 普通输入 | `ok is True`，`error == ""` |
| 3 | 消息含 `__fail__` | `ok is False`，`error == "MockFailure"` |
| 4 | 无 Key 且非 MOCK | 抛 `RuntimeError`，message 里有 `LLM_API_KEY` |
| 5 | `safe_json` 带围栏 | 返回 dict，取得到字段 |
| 6 | `safe_json` 垃圾字符串 | 返回 `None`（不是 `{}`） |

第 4 条用 `monkeypatch.delenv("LLM_API_KEY")` + `monkeypatch.setenv("MOCK_LLM","0")`。
**注意**：模块级读环境变量的写法会让 monkeypatch 失效 → 用 `_is_mock()` 函数**每次现读**环境变量。

## 6 验证

```powershell
pytest tests/test_agent.py -q                       # 6 passed
set MOCK_LLM=1
python -c "from agent import call_llm; print(call_llm([{'role':'user','content':'在吗'}]))"
```

期望：`{'text': '...', 'ok': True, 'error': '', 'latency_ms': 0}`

有 Key 的话再跑一次真实调用（把 `MOCK_LLM` 设成 0），确认 `latency_ms` 是几百毫秒到几秒、`ok=True`。

## 7 回滚

```powershell
git checkout -- agent.py tests/test_agent.py
```

MOCK 本身已经是最强兜底：网络坏了、Key 失效了，演示照样能走。**不要因为"延迟不好看"去调大 `max_retries`。**

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `openai.AuthenticationError` | Key 错/欠费 | 换 Key；演示前一定先跑一次真实调用 |
| `APITimeoutError` 频繁 | 网络或模型拥堵 | 保持 15s；失败就走兜底，别加无限重试 |
| monkeypatch 不生效 | 模块 import 时已读了环境变量 | 改成函数内 `os.getenv` |
| 返回 `text=""` 但 `ok=True` | 模型返回空内容 | 用 `bool(text)` 兜住 |
| 中文乱码 | 控制台代码页 | `chcp 65001`；不影响程序逻辑 |

## 9 出口清单

- [ ] `pytest tests/test_agent.py -q` = 6 passed
- [ ] `MOCK_LLM=1` 下断网能出回复
- [ ] 缺 Key 时抛的是 `RuntimeError`（不是空字符串）
- [ ] 真实调用跑通过一次（有 Key 的话）
- [ ] `contract_check.py` 仍 11/11

## 10 回执

```text
S04 完成：6 passed / MOCK 确定 / 真实调用 latency≈___ms / 缺 Key 会明确报错
下一步：S05 app.py
```
