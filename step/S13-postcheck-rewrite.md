# S13 · post_check 骨架：重写与复检

| 项 | 内容 |
|---|---|
| 步骤 | S13 / 26 |
| 阶段 | W3 |
| 工时 | 4 人时（P3） |
| 风险 | **高**——这是"否决权唯一"的落地点，写松了整条安全链就断了 |
| 依赖 | S12 |
| 回滚 | `git checkout -- guardian.py app.py` |

## 1 这一步做什么

实现 `guardian_post_check(user_text, reply, level, role, rewriter=None)`：**检查模型的回复**，不过就重写一次，再不过就换成安全模板。

产出：

1. 五步判定链：规则复查 → 重写 → 复检 → 记账 → 兜底
2. `SAFE_FALLBACK` 三个角色各一句
3. 4 条测试（含"复检仍不过必须兜底"）
4. app 接上 `post_check`，不过的回复**绝不发出去**

**本步不接 LLM 重写**（S14 接），本步的重写先用**模板改写**，保证逻辑先跑通。

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 判定 | 正则 `DIAG` + 资源检查 | 纯函数 |
| 重写 | 由调用方传入 `rewriter` 回调 | 本步用桩，S14 换成 LLM |
| 兜底 | 常量模板 | 必须无条件可用 |

## 3 前置检查

```powershell
pytest -q        # 41 passed
```

## 4 硬要求

1. **否决权唯一**：`pass=False` 的回复**任何**上层代码都不许发。重写/兜底是 Guardian 自己的事，不是"上层决定要不要听"。
2. 重写**最多 1 次**（`rewrite ∈ {0,1}`），禁止循环重试。
3. 复检用**同一套规则**，不许"复检放水"。
4. 兜底模板必须含资源（当 level 为 L3 时）且不含诊断词/说教词。
5. 返回字段固定：`pass / reason / fixed_reply / rewrite / template_fallback`。

## 5 执行步骤

### 5.1 检查器

```python
DIAG = re.compile(r"(你(得|患)了|你有.{0,6}倾向|你是.{0,4}症|抑郁症|焦虑症|建议服药|吃药)", re.I)
RESOURCE = re.compile(r"(12356|110|120|校心理中心)", re.I)

def _violations(reply: str, level: str) -> list[str]:
    """检查回复本身的问题；返回原因列表。"""
    bad = []
    if DIAG.search(reply or ""):
        bad.append("diagnosis_language")
    if level == "L3" and not RESOURCE.search(reply or ""):
        bad.append("crisis_missing_resource")
    if not (reply or "").strip():
        bad.append("empty_reply")
    return bad
```

### 5.2 兜底模板

```python
SAFE_FALLBACK = {
    "listener": "我在。你愿意说多少都可以，不想说也没关系。",
    "guide": "我不急着给你答案。你更想先理清哪一件事？",
    "crisis": CRISIS_REPLY,
}
```

注意 `crisis` 直接复用 S10 的常量——**兜底和短路必须同一句话**，否则两处口径会漂。

### 5.3 主函数

参数表与 S02 契约逐字对齐（`rewriter` 在 S02 就写进了空壳与 SPEC）——**只写函数体，不要改签名**，否则 `contract_check.py` 立刻红。

```python
def guardian_post_check(user_text: str, reply: str, level: str, role: str, rewriter=None) -> dict:
    """五步：复查 → 重写 1 次 → 复检 → 记账 → 兜底。不通过就不发。"""
    bad = _violations(reply, level)
    if not bad:
        return {"pass": True, "reason": "", "fixed_reply": None, "rewrite": 0, "template_fallback": False}

    fixed = rewriter(user_text, reply, bad, role) if rewriter else None   # 本步 rewriter=None
    if fixed and not _violations(fixed, level):
        return {"pass": True, "reason": ",".join(bad), "fixed_reply": fixed,
                "rewrite": 1, "template_fallback": False}

    return {"pass": False, "reason": ",".join(bad), "fixed_reply": SAFE_FALLBACK[role],
            "rewrite": 1 if fixed else 0, "template_fallback": True}
```

三段返回都是**成功路径**（都可以发），区别只在 `fixed_reply` 用哪句。
`pass=False` 的含义是"原回复不可用"，**不是"不发消息"**——永远要发一句安全的话。

### 5.4 app 接线

```python
post = guardian_post_check(user_text, raw_reply, pre["level"], cd["role"])
final = post["fixed_reply"] or raw_reply
st.markdown(final)        # 只发 final，raw_reply 不许出现在任何分支里
```

## 6 验证

| # | 输入（伪造 raw_reply） | 期望 |
|---|---|---|
| 1 | "你这是焦虑症" | pass=False，template_fallback=True |
| 2 | L3 但回复不含资源 | pass=False，fixed_reply 含 12356 |
| 3 | "我在听。" | pass=True，rewrite=0 |
| 4 | 注入 rewriter 返回"你这样是抑郁症" | 复检捕获 → 兜底（不许信重写） |

第 4 条是本步最重要的一条：**重写也可能是坏的**，复检不能省。

## 7 回滚

```powershell
git checkout -- guardian.py app.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 诊断句还是发出去了 | app 用了 raw_reply | 只允许 `final` 进 `st.markdown` |
| 重写无限循环 | 用 while 重试 | 只准 1 次，写完就判 |
| 危机回复被换成普通兜底 | role 传错 | 兜底按 role 取，L3 时 role 必是 crisis |
| 空回复被发出去 | 没查 `empty_reply` | 加进 `_violations` |
| 复检用的规则变少了 | 有人"优化"了 _violations | 复检必须调用同一个函数 |

## 9 出口清单

- [ ] 4 条测试绿
- [ ] app 里只发 `final`（grep 一遍 `raw_reply` 的用处）
- [ ] 兜底模板三角色各一句，crisis 与短路同文
- [ ] 重写次数封顶 1

## 10 回执

```text
S13 完成：4 passed / 只发 final / 兜底同文
下一步：S14 接 LLM 复核与重写
```