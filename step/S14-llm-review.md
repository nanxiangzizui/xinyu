# S14 · LLM 复核 + LLM 重写

| 项 | 内容 |
|---|---|
| 步骤 | S14 / 26 |
| 阶段 | W3 |
| 工时 | 4 人时（P3） |
| 风险 | **高**——多一次模型调用就多一次失败可能；失败方向必须"更严"而不是"放过" |
| 依赖 | S13 |
| 回滚 | `git checkout -- guardian.py` |

## 1 这一步做什么

把 S13 的空位填上：`rewriter` 换成"带拒因的 LLM 重写"，并增加一次**LLM 复核**（模型自查回复是否越界）。

产出：

1. `llm_review(user_text, reply, level)` → `{"pass": bool, "reason": str}`
2. `llm_rewrite(user_text, reply, reasons, role)` → 字符串
3. 5 条测试（含超时、返回垃圾 JSON、模型说"通过"但规则说不过）

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 复核 | 第二次 `call_llm`，要求纯 JSON | `temperature=0.2` |
| 重写 | 第三次 `call_llm`"，塞拒因 | `temperature=0.5` |
| 解析 | `safe_json` | 解析失败按"不通过" |
| 超时 | 复用 `TIMEOUT=15` | 超时按"不通过" |

## 3 前置检查

```powershell
pytest -q                  # 45 passed
set MOCK_LLM=1
```

## 4 硬要求

1. **任何异常一律"不通过"**：超时、解析失败、字段缺失、模型胡言——都按未通过处理，走兜底。这是 §"只升不降"在 post_check 的落地。
2. 复核 prompt 里**不给**用户原文之外的任何隐私字段（不给记忆、不给会话历史）。
3. 复核模型说 pass，但**规则说不过** → 仍然不通过（规则优先于模型）。
4. 重写 prompt 必须写明"改哪些、为什么"，否则模型只会换同义词。
5. 复核 + 重写总耗时上限：5 秒（演示体验），超了直接兜底。

## 5 执行步骤

### 5.1 复核

```python
REVIEW_SYS = ("你是内容安全审核员。只输出 JSON：{\"pass\": true 或 false, \"reason\": \"简短中文原因\"}。"
              "判定为 false 的情形：下诊断、推荐药物、承诺保密、追问自杀细节、说教、超过 4 句。")

def llm_review(user_text: str, reply: str, level: str) -> dict:
    """让模型自查回复；任何失败路径都返回 pass=False。"""
    msgs = [{"role": "system", "content": REVIEW_SYS},
            {"role": "user", "content": f"用户说：{user_text}\n助手回复：{reply}\n风险等级：{level}"}]
    try:
        out = call_llm(msgs, temperature=0.2)
        if not out.get("ok"):
            return {"pass": False, "reason": "review_call_failed"}
        data = safe_json(out["text"])
        if not isinstance(data, dict) or "pass" not in data:
            return {"pass": False, "reason": "review_parse_failed"}
        return {"pass": bool(data["pass"]), "reason": str(data.get("reason", ""))[:60]}
    except Exception as exc:                       # 边界兜底：LLM 调用
        return {"pass": False, "reason": f"review_error_{type(exc).__name__}"}
```

### 5.2 重写

```python
REWRITE_SYS = ("你在改写一段心理支持回复。保持原意，只改被标出的问题。"
               "要求：3 句以内、不说教、不诊断、不追问危机细节；危机场景必须包含 12356。只输出改写后的正文。")

def llm_rewrite(user_text: str, reply: str, reasons: list[str], role: str) -> str | None:
    """带拒因重写一次；失败返回 None（由 post_check 走兜底）。"""
    msgs = [{"role": "system", "content": REWRITE_SYS},
            {"role": "user", "content": f"用户说：{user_text}\n原回复：{reply}\n需要修正：{','.join(reasons)}\n角色：{role}"}]
    out = call_llm(msgs, temperature=0.5)
    return out["text"].strip() if out.get("ok") and out.get("text") else None
```

### 5.3 接进 post_check

```python
def guardian_post_check(user_text, reply, level, role, rewriter=None) -> dict:
    # ① 规则复查
    bad = _violations(reply, level)
    # ② 规则不过 → 重写；规则过 → 再复核一次
    if not bad:
        rv = llm_review(user_text, reply, level) if level != "L3" else {"pass": True}
        if rv["pass"]:
            return {"pass": True, "reason": "", "fixed_reply": None, "rewrite": 0, "template_fallback": False}
        bad = [rv["reason"] or "llm_review_rejected"]
    fixed = (rewriter or llm_rewrite)(user_text, reply, bad, role)
    if fixed and not _violations(fixed, level):
        return {"pass": True, "reason": ",".join(bad), "fixed_reply": fixed, "rewrite": 1, "template_fallback": False}
    return {"pass": False, "reason": ",".join(bad), "fixed_reply": SAFE_FALLBACK[role],
            "rewrite": 1 if fixed else 0, "template_fallback": True}
```

`L3 不调复核`：危机回复是固定模板，复核没意义还多耗时。

## 6 验证

| # | 场景 | 期望 |
|---|---|---|
| 1 | MOCK_LLM=1，正常回复 | pass=True，rewrite=0 |
| 2 | `__unsafe__` 剧本（返回说教句） | 规则先拦 → 重写 → 通过或兜底 |
| 3 | 让 `call_llm` 抛超时 | pass=False，template_fallback=True，reason 含 timeout |
| 4 | 复核返回 `not json` | parse_failed → 兜底 |
| 5 | 复核返回 `{"pass": true}` 但回复含"你得了抑郁症" | 规则仍然拦（规则优先） |

第 5 条是"规则优先于模型"的唯一证明，必须过。

## 7 回滚

```powershell
git checkout -- guardian.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 每轮要等 15 秒 | 三次调用串行且超时太宽 | 复核设 5 秒上限；演示前测平均耗时 |
| 兜底出现得特别频繁 | 复核 prompt 太严（把"3 句"当硬失败） | 复核只判安全项，句数交给规则 |
| 重写后语气完全变了 | 没说"保持原意" | 加进 prompt |
| 模型输出带 markdown 围栏 | 没 `safe_json` | 统一走 safe_json |
| 报错日志里出现用户原文 | 记了 msgs | 只记 reason 与类型名 |

## 9 出口清单

- [ ] 5 条测试绿
- [ ] 所有异常路径都返回 pass=False
- [ ] 复核 prompt 不含记忆字段
- [ ] 单轮平均耗时 < 6 秒（记进 evidence）
- [ ] 规则优先于模型（第 5 条测试）

## 10 回执

```text
S14 完成：5 passed / 失败方向全为"更严" / 平均耗时 __ 秒
下一步：S15 说教词 + taboos（体验层收口）
```