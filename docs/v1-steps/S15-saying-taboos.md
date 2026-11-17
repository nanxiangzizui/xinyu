# S15 · 说教词拦截 + 人设 taboos

| 项 | 内容 |
|---|---|
| 步骤 | S15 / 26 |
| 阶段 | W3 |
| 工时 | 2 人时（P2） |
| 风险 | 低——只加判定，不改链路 |
| 依赖 | S14 |
| 回滚 | `git checkout -- guardian.py roles.py` |

## 1 这一步做什么

补上"体验层"的两件小事：**说教句**必须改写（但不进 20 条规则，免得污染召回/误拦指标），**人设 taboos** 必须在生成时就被约束。

产出：

1. `SAYING` 正则（7 个词）放在 post_check 里，命中触发重写
2. `taboos` 注入 `build_system_prompt` 的风格区
3. 2 条测试

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 说教词 | 独立正则，**不进 RULES** | 原因是它属于体验，不影响安全等级 |
| taboos | 拼进风格区 | 每个 taboos ≤ 1 句 |

## 3 前置检查

```powershell
pytest -q      # 50 passed
```

## 4 硬要求

1. `SAYING` **不进 RULES**——20 条规则只负责安全等级，说教词不改等级、只改文案。
2. 命中说教词 → `reasons.append("preachy")` → 走 S14 的重写，**不升级**、**不兜底**（直接兜底太狠，说教不是安全事故）。
3. 重写后仍含说教词 → 允许发出（体验问题不阻塞），但 `rewrite=1` 要记账。
4. taboos 每卡 ≤1 条，且必须是"人设不该做的事"，不是"人设该做的事"。

## 5 执行步骤

### 5.1 说教词

```python
SAYING = re.compile(r"(你应该|你必须|别想太多|这没什么|我当年|你要坚强|振作起来)")

def _violations(reply: str, level: str) -> list[str]:
    bad = []
    ...  # 原有
    if SAYING.search(reply or ""):
        bad.append("preachy")          # 体验层：只触发重写
    return bad
```

注意它不是 `L1/L2/L3` 判定的一部分：`guardian_pre_check` 完全不引用它。

### 5.2 五卡 taboos（体验层，各卡不同）

| 卡 | taboos（这句不许说） |
|---|---|
| sister_heart | "我理解你" 这类空话 |
| warm_senpai | "我当年也是这样" 的经验炫耀 |
| rational_mentor | "其实很简单" 的轻视 |
| energy_buddy | "开心点嘛" 的强行积极 |
| quiet_hollow | "你可以再多说一点" 的追问 |

### 5.3 注入风格区

```python
def _style_block(p: dict) -> str:
    lines = [f"称呼对方为「{p['address']}」，语气：{p['tone']}，一次不超过 {p['sentence_len']} 字左右。"]
    lines += [f"不要说：{t}" for t in p.get("taboos", [])]
    lines += ["示例（照这个语气，不要照抄内容）："] + [f"用户：{u}\n你：{a}" for u, a in p["mes_example"]]
    return "\n".join(lines)
```

## 6 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `pytest -q` | 52 passed |
| 2 | 输入"我好累"，让 MOCK 返回"你应该早点睡" | 触发重写，rewrite=1 |
| 3 | 检查 `guardian_pre_check("你应该")` | 仍是 L1（说教不改等级） |
| 4 | 五卡生成 | 各自不含自己的 taboos 句 |

## 7 回滚

```powershell
git checkout -- guardian.py roles.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 误拦了"你应该不会" | 正则太宽 | 接受；这是体验层，不阻塞 |
| 说教词让 level 变了 | 把 SAYING 混进 RULES | 立刻拆开 |
| taboos 写成"要温柔" | 方向写反了 | 只写"不许做什么" |
| 五卡 taboos 全一样 | 复制粘贴 | 每卡必须能指出"只有它会犯的错" |

## 9 出口清单

- [ ] 52 passed
- [ ] SAYING 不在 RULES 里（grep 确认）
- [ ] 五卡 taboos 互不相同
- [ ] pre_check 不受说教词影响

## 10 回执

```text
S15 完成：52 passed / 说教词只改文案不改等级 / 5 卡 taboos 各异
下一步：S16 会话聚合与风险地板
```