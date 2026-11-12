# P0 · DeepSeek `tools` 能力探测报告

- 日期：2026-11-12
- 目的：确认 DeepSeek（OpenAI 兼容接口）是否支持函数调用，决定 P2 的 `agent_loop.py` 走哪条协议
- 结论：**支持标准 OpenAI `tools` / `tool_calls` 协议，三关全过，P2 不需要自造 JSON 动作协议**
- 证据：本目录 `probe_tools_2026-11-12.py`（探测脚本）+ `probe_tools_2026-11-12.out.txt`（原始输出）

## 1. 环境

| 项 | 值 |
|---|---|
| Python | 3.11.9（`py -3.11`，venv `.venv`） |
| openai SDK | 1.109.1 |
| 模型 | `deepseek-chat` |
| base_url | `https://api.deepseek.com` |
| 密钥来源 | `.env` 的 `LLM_API_KEY`（不入库、不打印） |
| 请求特征 | 只发最小测试请求，不含任何用户数据、不含项目 prompt |

## 2. 三关结果

| 关 | 测什么 | 结果 | 关键字段 |
|---|---|---|---|
| case 1 | 普通请求，不传 `tools` | ✅ 正常 | `finish_reason=stop`，`has_tool_calls=False` |
| case 2 | 传 1 个 `echo` 工具，要求模型调用 | ✅ 触发调用 | `finish_reason=`**`tool_calls`**，`n_tool_calls=1`，`tool_names=['echo']`，`args_json_ok=[True]` |
| case 3 | 把 `tool_calls` 原样回填 + 一条 `tool` 消息后再问 | ✅ 两跳闭环 | `finish_reason=stop`，`has_tool_calls=False`，正文 "已调用 echo 工具，返回结果：`hello`" |

三次运行耗时（同一脚本、不同时段）：case 1 约 1.2–2.6 s，case 2 约 0.8–1.4 s，case 3 约 1.5–2.7 s。网络正常时一次工具往返在 3 s 内。

## 3. 对 P2 的直接结论

1. **用标准协议**：`client.chat.completions.create(..., tools=[...], tool_choice="auto")`，从 `choices[0].message.tool_calls` 取调用。不要写自定义 "动作 JSON" 解析。
2. **第二跳必须原样回填**：assistant 消息要带上 `tool_calls`（含每个 `id`），随后紧跟 `{"role":"tool","tool_call_id":..., "content":...}`。漏 `id` 或改结构会 400——这是 P2 最容易写错的一处。
3. **`arguments` 是字符串**：先 `json.loads`，解析失败按工具失败处理（`ok=False`），不许把异常抛给界面。
4. **模型可以不调用工具**：case 1 说明"直接回答"是正常路径，`run_agent` 必须支持 0 次工具调用直接收尾。
5. **预算可算**：单次往返 ≤3 s；`AGENT_MAX_STEPS=3` 最坏 3 次模型调用 ≈ 9 s，仍在 `AGENT_TOTAL_TIMEOUT_S=20` 内，`TOOL_TIMEOUT_S=6` 覆盖单次工具执行。
6. 应急预案（暂不实现）：若将来换到不支持 `tools` 的模型，退回"提示模型输出 `{"action":...}` JSON"的方案；当前无此需要。

## 4. 复现

```powershell
cd "D:\deepseek harness\xinyu-agent"
$env:PYTHONIOENCODING = "utf-8"     # 控制台默认 GBK，中文会乱码，只影响显示
.\.venv\Scripts\python.exe docs\evidence\probe_tools_2026-11-12.py
```

退出码 0 = 三关都跑完；脚本内 `ok=False` 会打印 `error` 字段，便于区分"协议不支持"与"网络/密钥问题"。

## 5. 顺带记录：迁移后的基线复跑（P0 另一半）

| 检查 | 结果 |
|---|---|
| `pytest -q` | **132 passed in 5.21s** |
| `contract_check.py` | 11/11 signatures + 5/5 constants + 20/20 rules |
| `metrics.py` | 召回 10/10、误拦 0/20、角色 12/12、连续 10 轮 10/10 |

注意：本地不要放 `.streamlit/secrets.toml`，否则 `tests/test_fault.py::test_f06`（模拟"没有 Key"）会变红——`app.py` 的 `_bridge_secrets()` 会把 secrets 铺进环境变量。本地开发用 `.env` 即可，线上 Secrets 在 Streamlit Cloud 后台填；模板见 `.streamlit/secrets.toml.example`。
