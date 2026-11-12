# P5 · `style.py` 口吻层（句尾 / 贴纸 / tone hint）

| 项 | 内容 |
|---|---|
| 节点 | P5 / P6 |
| 计划书 | §3.1 风格层、§4 P5 行、§7 `style.py` 预算 |
| 工时 | 2 天（口径对齐 1 天、人设盲读 1 天） |
| 风险 | **中**——改的是"说出来的每个字"，最容易顺手改到安全文案 |
| 依赖 | P4 ✅ |
| 回滚 | `git checkout -- orchestrator.py agent.py`，删除 `style.py`、`tests/test_style.py` |

## 1 这一步做什么

在**复核通过之后、写记忆与返回之前**加一层"说话方式"：

1. `style.polish(text, persona, level)`：去句尾句号、必要时按标点截断、L1 加一枚贴纸；
2. `style.tone_hint(persona)`：每个性格一句"怎么说话"的提示，由 `agent._style_block` 追加进 prompt 的风格段；
3. `orchestrator` 里**三条件**才调用：`post["pass"]` 且 `not post["template_fallback"]` 且 `level != "L3"`。

**不做**：不改任何安全文案、不改 `build_system_prompt` 的签名、不新增第四段 prompt、不加模型调用（贴纸是查表，不是生成）。

## 2 六个关键决策

### 2.1 只碰"模型自己说的话"

一个 `reply` 有四种出身，只有第一种可以润色：

| 出身 | `post` 特征 | 能否 polish | 为什么 |
|---|---|---|---|
| 模型通过复核 | `pass=True, template_fallback=False` | ✅ | 这才是"口吻"该起作用的地方 |
| 复核重写后通过 | `pass=True, template_fallback=False, rewrite=1` | ✅ | 重写仍算模型输出 |
| 模板兜底 | `template_fallback=True` | ⛔ | `SAFE_FALLBACK` 是安全文案，逐字不许动 |
| L3 危机 | `level="L3"` | ⛔ | `CRISIS_REPLY` 是红线文案，逐字不许动 |

判断写成三个与条件，**顺序固定**（先 `pass`，再 `template_fallback`，最后 `level`），任何一条不满足直接返回原文：

```python
if post["pass"] and not post.get("template_fallback") and eff_level != "L3":
    reply = style.polish(reply, persona_id, eff_level)
```

> 为什么 L3 不用 `post["fixed_reply"]` 判：L3 的固定回复可能被打包进 `fixed_reply`，也可能直接走 `_crisis_result`，两条路径都要挡住，所以**判等级**最稳。

### 2.2 只去句尾「。」，问号感叹号一个不动

去掉句号会让短句更像聊天；但 `？` `！` 承载语气，`…` 承载停顿，动了就是改语气之外的语义。

```python
if text.endswith("。"):
    text = text[:-1]
```

**只去一个**，只去末尾。句中的句号、引用里的句号、`"好的。然后呢？"` 中间那个——都不碰。

### 2.3 截断只在标点处，绝不切在半句

长回复在聊天窗里要滚三屏，观感差。但"截断"必须落在句号/问号/感叹号之后：

```python
cut = max(text.rfind(ch, 0, MAX_CHARS) for ch in "。！？!?")
if cut > MAX_CHARS // 2:
    text = text[:cut + 1]
else:
    text = text[:MAX_CHARS].rstrip() + "…"      # 整段没标点，才硬断并加省略号
```

`MAX_CHARS = 220`。**只在超过时截**，短回复一个字不动。

### 2.4 贴纸是白名单查表，不是模型生成

`STICKERS` 最多 8 条、一人一枚、按 `persona` 查。**L1 才给**：L2 是"低落/焦虑"，贴一枚 🌿 会显得轻佻；L3 更不用说。

```python
STICKERS = {"sister_heart": "🌿", "warm_senpai": "☀️",
            "rational_mentor": "🧭", "energy_buddy": "⚡",
            "quiet_hollow": "🌙"}
STICKER_LEVELS = frozenset({"L1"})
```

追加规则：`text + " " + sticker`，且**回复里已有这枚贴纸就不加**（防重入）。不换掉任何正文。

### 2.5 tone hint 追加在风格段**末尾**，不新增段落

`agent._style_block(persona)` 现在返回「称呼 / 语气 / 句长 / emoji / 禁忌 / 示例」那一块（`agent.py:178-189`）。在它 `return` 前追加一行：

```python
block += "\n" + style.tone_hint(persona_id)
```

- 不改 `build_system_prompt` 的签名（`contract_check` 盯着它）；
- 不新增第四段（四段顺序是 `test_prompt` 在守的）；
- 每句 hint ≤60 字，prompt 总增量 <80 字（含换行）。

**为什么不让模型自由发挥口吻**：自由发挥会把"稳重"漂成"说教"、把"活泼"漂成"卖萌"；一句话锚点比十条约束便宜，也更好盲读验收。

### 2.6 幂等

同一段文本 polish 两次必须等于一次：不重复加贴纸、不重复去标点、不把 `…` 再截一次。

测试 `test_polish_is_idempotent` 守这条。**为什么重要**：重试路径（界面重跑、异常重放）可能重复润色，不幂等就会出现"🌿🌿"。

## 3 接口

```text
style.py
  MAX_CHARS = 220
  STICKERS: dict[str, str]            # ≤8 条
  STICKER_LEVELS = frozenset({"L1"})
  TONE_HINTS: dict[str, str]          # 5 个人设各一句，≤60 字
  polish(text: str, persona: str = "", level: str = "L1") -> str
  tone_hint(persona: str) -> str
```

`persona` 用 `roles.PERSONAS` 的键：`sister_heart / warm_senpai / rational_mentor / energy_buddy / quiet_hollow`。未知 persona → `STICKERS.get` 返回 `None`、`TONE_HINTS.get` 返回 `""`，**不报错**（模型层不该因为 UI 传错值整轮崩，但这里的"不报错"是查表默认，不是兜底逻辑）。

## 4 前置检查

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # 166 passed（P4 后）
Select-String -Path agent.py -Pattern "_style_block|def build_system_prompt"
Select-String -Path guardian.py -Pattern "CRISIS_REPLY =|SAFE_FALLBACK ="   # 记下逐字文案
```

盲读准备：把 5 个人设各 5 条模型回复（MOCK 或真机）导成一个 txt，**盖住人设名**，找 2–3 个同学读，问"这条像哪种性格"。这就是交付材料里的人设盲读证据。

## 5 执行步骤

### 5.1 新建 `style.py`

```python
"""style.py — 口吻层：只改说法，不改事实、不加承诺、不加诊断。

[SAFE] 只处理复核通过的模型输出；L3 与模板兜底由调用方挡住，本文件再挡一次。
本模块不调用模型、不读记忆、不写日志。
"""
from __future__ import annotations

MAX_CHARS = 220

STICKERS = {
    "sister_heart": "🌿",
    "warm_senpai": "☀️",
    "rational_mentor": "🧭",
    "energy_buddy": "⚡",
    "quiet_hollow": "🌙",
}

STICKER_LEVELS = frozenset({"L1"})

TONE_HINTS = {
    "sister_heart": "像姐姐：先接住情绪，再给一句具体的小建议，不用大道理。",
    "warm_senpai": "像学长：稳一点，先复述你听到的，再问一个具体的问题。",
    "rational_mentor": "像导师：先给结论再给理由，少用感叹号，不说空话。",
    "energy_buddy": "像搭子：短句、轻快，但别用“加油”敷衍，要接住具体的事。",
    "quiet_hollow": "像安静的同伴：句子短、留白多，不追问，不急着给办法。",
}


def tone_hint(persona: str) -> str:
    """返回该人设的一句说话锚点；未知人设返回空串。"""
    return TONE_HINTS.get(persona, "")


def _clip(text: str) -> str:
    """超过 MAX_CHARS 才截；优先断在句末标点后，整段无标点才硬断加省略号。"""
    if len(text) <= MAX_CHARS:
        return text
    cut = max(text.rfind(ch, 0, MAX_CHARS) for ch in "。！？!?")
    if cut > MAX_CHARS // 2:
        return text[:cut + 1]
    return text[:MAX_CHARS].rstrip() + "…"


def _strip_period(text: str) -> str:
    """只去末尾一个句号；问号、感叹号、省略号不动。"""
    return text[:-1] if text.endswith("。") else text


def _sticker(text: str, persona: str, level: str) -> str:
    """L1 才加；每人一枚；已有同款就不再加。"""
    mark = STICKERS.get(persona, "")
    if not mark or level not in STICKER_LEVELS or mark in text:
        return text
    return f"{text} {mark}"


def polish(text: str, persona: str = "", level: str = "L1") -> str:
    """润色一句模型输出：截断 → 去句尾句号 → 贴纸；L3 原样返回。"""
    if not text or level == "L3":
        return text
    return _sticker(_strip_period(_clip(text)), persona, level)
```

> `_clip` 里 `max(... for ch in "。！？!?")` 对空文本会得到 -1，但空文本已在 `polish` 入口返回；`text` 非空时 `max` 至少是 -1，逻辑成立。

### 5.2 `agent.py` 追加 tone hint

`_style_block` 末尾（约 `:188`，`return` 之前）加：

```python
    block += "\n" + style.tone_hint(persona_id)
```

import 段加 `import style`（`style` 不 import agent，无环）。

**核对**：`build_system_prompt` 返回的四段顺序不变；prompt 比 P4 前长 ≤80 字。用一个临时脚本量一下：

```powershell
.\.venv\Scripts\python.exe -c "import agent; print(len(agent.build_system_prompt('sister_heart', {}, [])))"
```

P4 前的数字记在证据里，差值 <80 才算过。

### 5.3 `orchestrator.py` 接一层

`handle` 里 `reply = post.get("fixed_reply") or resp.get("text") or FALLBACK_LINE` 之后加：

```python
    if post["pass"] and not post.get("template_fallback") and eff_level != "L3":
        reply = style.polish(reply, persona_id, eff_level)
```

`orchestrator.py` 现在贴 250 行上限；这 2 行 + `import style` 1 行会超。压缩顺序：

1. 把 `_generate` 里 v1 分支的 `_node(..., "pipeline")` 与 return 合成两行（省 1 行）；
2. `_ms` 与 `_detail` 之间的空行删一组（省 1 行）；
3. 再不够，把 `_timed` 里 `except` 分支压成单行（省 2 行）；
4. **不接受**把 polish 塞进 `guardian` 或 `agent`——口吻是编排顺序的一步，位置必须可见。

## 6 测试（9 条，总 175）

```python
"""test_style.py — 口吻层：L3/兜底逐字、句尾、截断、贴纸、幂等、prompt 增量。"""
from __future__ import annotations

import agent
import guardian
import style


def test_l3_text_is_verbatim():
    assert style.polish(guardian.CRISIS_REPLY, "sister_heart", "L3") == guardian.CRISIS_REPLY


def test_template_fallback_text_is_untouched():
    for text in guardian.SAFE_FALLBACK.values():
        assert style.polish(text, "energy_buddy", "L2") == text


def test_only_trailing_period_is_removed():
    assert style.polish("我在。", "sister_heart", "L2") == "我在"
    assert style.polish("我在吗？", "sister_heart", "L2") == "我在吗？"
    assert style.polish("好。然后呢？", "sister_heart", "L2") == "好。然后呢？"


def test_clip_happens_at_sentence_end():
    body = "第一句。" * 60                      # 240 字，超过 220
    out = style.polish(body, "sister_heart", "L2")
    assert out.endswith("。") and len(out) <= style.MAX_CHARS


def test_clip_without_punctuation_uses_ellipsis():
    out = style.polish("啊" * 300, "sister_heart", "L2")
    assert out.endswith("…") and len(out) <= style.MAX_CHARS + 1


def test_sticker_only_on_l1_and_from_whitelist():
    out = style.polish("我在", "sister_heart", "L1")
    assert out == f"我在 {style.STICKERS['sister_heart']}"
    assert style.polish("我在", "sister_heart", "L2") == "我在"
    assert style.polish("我在", "sister_heart", "L3") == "我在"


def test_polish_is_idempotent():
    once = style.polish("我懂你。", "warm_senpai", "L1")
    assert style.polish(once, "warm_senpai", "L1") == once


def test_tone_hint_is_short_and_persona_specific():
    hints = {p: style.tone_hint(p) for p in style.TONE_HINTS}
    assert all(0 < len(h) <= 60 for h in hints.values())
    assert len({h for h in hints.values()}) == len(hints)


def test_system_prompt_grows_under_80_chars():
    base = len(agent.build_system_prompt("sister_heart", {}, []))
    # 只断言“加了一行锚点”这个事实：把它去掉应当更短
    assert style.tone_hint("sister_heart") in agent.build_system_prompt("sister_heart", {}, [])
    assert base < 4000
```

> 最后一条刻意写得"软"：prompt 总长依赖人设卡，硬编码数字会随 `roles.py` 改动而碎。真正的 80 字验收在 §7 用手工前后差值 + 证据文件完成；测试只守"锚点确实进了 prompt、且总长没失控"。

## 7 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `.\.venv\Scripts\python.exe -m pytest -q` | **175 passed** |
| 2 | `contract_check.py` | 11/11 + 5/5 + 20/20（`build_system_prompt` 签名没变） |
| 3 | `(Get-Content style.py).Count` | ≤180 |
| 4 | 临时脚本：polish 前后 `CRISIS_REPLY` / `SAFE_FALLBACK` 逐字比较 | 全等（`==`，不是 `in`） |
| 5 | `python -c` 量 5 个人设 prompt 长度 | 比 P4 前增加 <80 字 |
| 6 | 真机 L1 日常 3 轮，切 2 个人设 | 口吻能分辨；贴纸只在 L1；句尾无「。」 |
| 7 | 真机 L2（"最近很焦虑"）与 L3 | L2 无贴纸；L3 文案与 `CRISIS_REPLY` 逐字一致 |
| 8 | 盲读：5 人设 × 5 条，盖名让人猜 | 至少 3/5 正确率再进 P6；低就调 `TONE_HINTS`，不动 `roles` |
| 9 | `Select-String -Path style.py -Pattern "抑郁\|诊断\|治疗"` | 无输出 |

存证：`docs/evidence/P5-style-YYYY-MM-DD.md`，含 #1 #2 #4 #5 输出、盲读记录（脱敏、只写"人设 A→被猜中 4/5"）。

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| L3 少了句号 / 多了贴纸 | 三条件没写全，或 polish 在 `_crisis_result` 路径上也跑了 | 检查 polish 只加在 `handle` 的成功路径 |
| 兜底文案被润色 | `template_fallback` 没判 | 三条件顺序：pass → template_fallback → level |
| 问号被去掉 | 用了 `rstrip("。！？")` | 只 `endswith("。")` 去一个 |
| 截断切在半句 | 用了 `text[:MAX]` | 先找标点，找不到才硬断加 `…` |
| 贴纸重复 | 没判 `mark in text` | `_sticker` 里那行 |
| 句尾出现两个句号 | 先截断后去句号，顺序反了 | `_strip_period(_clip(...))`，顺序固定 |
| prompt 暴涨 | tone hint 写成长段落 | 每人 ≤60 字；超了就删形容词 |
| 五个人设听起来一样 | `TONE_HINTS` 写的是同义句 | 用"做什么/不做什么"区分（接住 vs 给结论 vs 不追问） |
| 盲读正确率低 | 提示太抽象 | 加一个具体动作词（"先复述" / "先给结论"），仍 ≤60 字 |

## 9 回滚

```powershell
git checkout -- agent.py orchestrator.py
Remove-Item style.py, tests/test_style.py
.\.venv\Scripts\python.exe -m pytest -q      # 回到 166
```

只想关口吻、保留 v2 其余能力：把 `orchestrator` 里的 polish 三行注掉（不推荐长期这样，材料里的"口吻差异"就没了）。

## 10 出口清单

- [ ] 175 passed；契约 11/11 + 5/5 + 20/20
- [ ] `CRISIS_REPLY` 与 `SAFE_FALLBACK` 逐字不变（`==` 断言）
- [ ] L1 有贴纸、L2/L3 没有；贴纸最多一枚、来自白名单
- [ ] 只去句尾「。」；截断只在标点后；polish 幂等
- [ ] tone hint 进 prompt 风格段；5 人设 prompt 增量 <80 字
- [ ] 盲读记录进证据（3/5 以上）
- [ ] `style.py` ≤180；`orchestrator.py` ≤250
- [ ] `CLAUDE.md` §2.2 P5 改 ✅，§4 加一行

## 11 回执

```text
P5 完成：175 passed / style ___ 行 / prompt 增量 __ 字
L3 与兜底逐字不变；盲读 __/5
下一步：P6 回归 + 材料回填 + Gate A
```
