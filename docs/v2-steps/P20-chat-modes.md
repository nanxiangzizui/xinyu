# P20 聊天功能细化：闲聊 / 帮助双模式 + 说得具体 + 按需检索

> 触发：用户 2026-11-18 截图反馈「引导者模式下问办法，回复冷淡、不解决问题」，提出三条要求：
> ①查提示词为什么导致冷淡；②字数限制拆成「闲聊模式 / 帮助模式」两套，彼此独立但引导要清晰；
> ③知识不够时自动上网检索，给出具体、详细的回答。
>
> 本文件只写计划与逐字文案，**本阶段不改代码**。改完 P20a–P20c 后按 §7 验证，再回填 `.claude/CLAUDE.md` §2.2 / §4。

---

## 0. 一句话结论

**不是模型懒，是提示词和复核层在按指令把它压短。** 四条"变短"的闸门同时生效：安全区「3 句以内」、
人设「每条约 20 字」、风格规则「每轮只做一件事…或给一句话」、复核层「超过 4 句判不合格 → 重写成 3 句」。
引导者又**没有任何专属段落**（只有倾听者有 `[这一轮：倾听者]`），所以它只能做减法。
修法：把"短"限定在闲聊，给 guide 一套**正向**的帮助段 + 独立字数/句数上限 + 检索指引，复核层按模式分档。

---

## 1. 截图这一轮的事实复原

| 轮 | 输入 | 判定 | 输出 | 字数 |
|---|---|---|---|---|
| 1 | 昨晚两点才睡…请假又睡了一小时，精神还是不好 | L1 / listener（没问办法） | 「两点睡、八点起，身体当然会抗议。请假多睡那一小时，是你照顾自己了」 | 40 |
| 2 | 给点建议 | L1 / guide（`ADVICE_WORDS` 命中「建议」） | 「先别急着补效率。今晚十一点半躺下，手机放远一点，试试看」 | 30 |

第 2 轮其实是"对"的：有判断、有动作、有时间点。用户觉得不够，是因为**只有一条**，
而"帮助"这件事在这个系统里没有任何"可以多说"的许可。

---

## 2. 根因：七道把回复压短的闸门

| # | 位置 | 原文 | 后果 |
|---|---|---|---|
| 1 | `roles.py:20`（`SAFETY_BLOCK` 第 6 条，所有人设共用） | 「回复控制在 3 句以内；对方没有明确求助时，不给建议。」 | 硬上限；且**没有"明确求助时可以展开"的例外** |
| 2 | `agent.py:238` | `每条回复约 {sentence_len} 字以内`（15 / 20 / 20 / 25 / 30） | 模型把"约 20 字"当硬上限，一条建议就是极限 |
| 3 | `style.py:45-63`（`SPEECH_RULES` #9） | 「每轮只做一件事：接住情绪，或问一个具体问题，**或给一句话**」 | 三个动作是"或"关系；已经接住情绪，就只剩一句 |
| 4 | `agent.py:32-34`（`REVIEW_SYS`） | 「判定为 false 的情形：…**超过 4 句**」 | 6 句的结构化建议会被判不合格 |
| 5 | `guardian.py:273-310` + `agent.py:36-38` | L1 无规则违规也走 `llm_review`；不通过则 `llm_rewrite`，而 `REWRITE_SYS` 要求「**3 句以内**」 | **代码级硬闸**：再好的长回答也会被重写回 3 句 |
| 6 | `agent.py:259-260` | `if role == "listener": lines.append(style.listener_block(...))` | guide **没有专属段**，收不到任何"该怎么帮"的正向指令 |
| 7 | `orchestrator.py:30` / `web.py:241-249` / `companion_ui.py:132` | `ALLOW_WEB` 默认 `0`；工具描述只许"查专名"；A 模式当轮只 `st.markdown(reply)` 不画来源 | 知识不够时没有出口，只能说通用话；即使查到也看不见 |

补充两条氛围原因（不是 bug，但要一起改）：

- 第 1 轮的「身体当然会抗议」是**评判句**，不是接住。现有 13 条风格规则只禁"总结句"，没禁"给对方的身体下结论"。
- 人设 `post_history_instructions` 是 prompt 最后一句（`agent.py:285`，紧贴用户输入），例如知心姐姐
  「先确认对方此刻的情绪，再开口；不要急着给办法」，会**反向抵消**任何帮助指令——所以帮助段必须放在它之后。

---

## 3. 目标与非目标

**目标**

1. 闲聊仍然短、不说教；帮助时能给出"判断 + 1–3 条具体动作 + 何时求助"的完整回答（200–450 字）。
2. 两套上限**由同一处判定**，不靠模型自觉：聊天 ≤4 句 / 220 字；帮助 ≤8 句 / 460 字。
3. 帮助模式可检索：没把握的具体事实先查一次 `web_search`，来源当轮可见。
4. 侧栏能看出"这一轮是聊天还是帮助"，用户可用 P19 的角色下拉自己切。

**非目标（本轮不做）**

- 不改 `RULES` 20 条、`guardian_pre_check` 分级、`memory` 白名单、`contract_check` 11 条签名。
- 不给 B（角色卡）模式加帮助段——B 有自己的 prompt 与 4000 字预算。
- 不做流式、不做多轮工具规划、不放开"任意 URL 抓取"。
- 不引入任何依赖。

---

## 4. 设计

### 4.1 模式判定：mode = role（不新增状态）

`coordinator` 已经按"是否明确问办法"给出 `guide` / `listener`，P19 又允许用户手动选。
**直接把 guide 定义成帮助模式**，不再造第二套开关：

- `guide` → 帮助模式（可说 8 句、460 字、可检索）
- `listener` / `crisis` → 闲聊模式（3 句、220 字，现状）
- 冷却与危机后缓冲仍由 `enforce_cooldown` 把 guide 压回 listener（`coordinator.py:64-76`），
  所以"危机后不给长篇建议"这条安全口径自动保留。

**零改动点**：`orchestrator.py` 一行都不用改（`_role` 已在 205-207 写进 facts，
`build_system_prompt` 已读它，`style.polish` 已收 `role`）。文件仍 250 行。

### 4.2 模式矩阵

| 维度 | 闲聊（listener） | 帮助（guide） |
|---|---|---|
| 触发 | 没问办法 / 用户选"倾听者" | 命中 `ADVICE_WORDS` / 用户选"引导者" |
| 复核句数上限 | 4（现状） | 8 |
| 代码截断 | 220（现状） | 460 |
| 结构 | 接住感受 + 一句具体观察；不主动给方案 | 一句判断 → 1–3 条动作（时间 / 动作 / 多少量）→ 什么情况该找人 |
| 检索 | 不要求；事实性问题可查一次 | 没把握的具体事实/做法**先查一次** |
| 气泡 | 单气泡（现状） | 2–3 气泡（可选，见 D-2） |

### 4.3 提示词逐字改动

**(a) `roles.py:20` — 安全区第 6 条改成有条件的**

```text
6. 闲聊时回复控制在 3 句以内；对方明确求助（问怎么办、要建议）时，可以分 1–3 条给具体做法，最多 8 句。
```

保留「3 句以内」四字（`tests/test_roles.py:31` 断言它存在），语义从"永远"变成"闲聊时"。

**(b) `style.py` 新增帮助段（约 24 行常量 + `guide_block()`）**

```python
GUIDE_HEAD = "[这一轮：引导者 · 帮助模式]"
GUIDE_RULES = (
    "对方在问办法，这一轮把话说完整，不要只给一句：\n"
    "1) 先用一句给出判断（你现在最该做的是 X），不要先安慰再拖两句。\n"
    "2) 再给 1–3 条今天就能做的动作，每条写清时间、做什么、多少量"
    "（例：今晚 23:30 躺下，手机放到桌子另一头，闹钟固定 7:30）。\n"
    "3) 最后一句说清什么情况该找真人（例：连续两周还这样，去校心理中心聊聊）。\n"
    "「3 句以内」是跟对方闲聊时的规矩；帮助模式可以说 4–8 句、最多 450 字，分条写，一条一句。\n"
    "不写没有动作的安慰句（「会好的」「相信自己」「慢慢来」）；不诊断、不推荐药物和剂量；\n"
    "对方说「没用」「具体点」时，不要重复上一句，换更细的动作或改问一件事。"
)
GUIDE_WEB = ("拿不准的具体事实（睡眠卫生、食物、路线、政策、近期发生的事）先调 web_search 查一次再答；"
             "查不到就说没查到，只给通用做法，不要编。")
HELP_MAX_CHARS = 460
```

`guide_block(web_ready: bool) -> str` 返回 `GUIDE_HEAD + GUIDE_RULES (+ GUIDE_WEB)`。

**(c) `agent.py:285` 之后追加**（保证它是 prompt 的最后一段，压过 `post_history_instructions`）

```python
    if str(memory.get("_role") or "") == "guide":
        parts.append(style.guide_block(_web_ready()))
```

新增 `_web_ready()`：`ALLOW_WEB == "1"` 且至少一个 provider key 存在才返回 True。
没配检索时不写"先查一次"，避免模型假装查过。

**(d) `style.py:63` 之后新增第 14 条风格规则**

```python
"14. 接住的是感受，不是给对方的身体或选择下结论：不说「身体当然会抗议」「早该这样」这类评判句。",
```

针对性解决截图第 1 轮的"冷淡感"；不碰第 9 条（"每轮只做一件事"），避免和 P16 的倾听者收窄打架。

**(e) `style.py:172-185` `polish` 按模式截断**

```python
def _clip(text: str, limit: int = MAX_CHARS) -> str: ...   # 默认值不变，旧测试仍绿
...
    out = _clip(text, HELP_MAX_CHARS if role == "guide" else MAX_CHARS)
```

### 4.4 复核层按模式分档（`guardian.py`）

- `agent.REVIEW_SYS`：把「超过 4 句」改成「超过本轮句数上限」（上限由调用方传，不再写死）。
- `guardian._review_messages(user_text, reply, level, role="")` 的用户消息追加一行：

  ```text
  本轮：{role} / 句数上限：{4 或 8}
  ```

  这样 `messages[0]["content"]` 仍逐字等于 `REVIEW_SYS`，`tests/test_guardian.py:213` 等断言不变。
- `llm_review(..., role="")` 增加关键字参数并透传；`guardian_post_check` 已有 `role`，直接传。
- `agent.REWRITE_SYS`：「3 句以内」→「不超过原文句数，最多 8 句；删掉说教句，不新增事实」。
- 常量：`guardian.CHAT_MAX_SENTENCES = 4` / `HELP_MAX_SENTENCES = 8`。

**不做**「没有动作就判 false」：帮助模式偶尔就是需要一句共情，模型复核一旦误判会掉进
`SAFE_FALLBACK`，体验比空话更差。这条改用"生成端强约束 + 真 key 探针计数"验收（§7）。

### 4.5 按需检索

1. **开关**：`ALLOW_WEB` 仍默认 `0`（红线"可关"），本地 `.env` 与 Cloud Secrets 显式置 `1`。
   缺 key 时 `_web_ready()` 为 False，prompt 不出现检索指令。
2. **工具描述**（`web.py:241-249`）从"只查专名"扩成：

   ```text
   查公开资料：具体做法（睡眠、饮食、运动、学习方法）、常识、近期信息、本地公开信息；
   也可以查人名、角色、作品、梗或事件。只读；不查个人隐私，不用来确认聊天里提到的人。
   ```

   风险控制不变：`memory.scrub` 先脱敏、80 字截断、6 秒超时、结果只作资料（`RESULT_NOTE`）。
3. **触发**：只在帮助模式的 prompt 里要求"没把握先查一次"；工具预算不变
   （`AGENT_MAX_STEPS=3` / `AGENT_MAX_TOOL_CALLS=2`），最多一次往返。
4. **失败**：查不到就按通用做法答；`agent_loop` 失败仍走 `FALLBACK_LINE`（不动）。
5. **来源可见**：`chat_ui` 抽出 `render_sources(sources)`，`render_history` 与新回复共用；
   `companion_ui._run_turn` 把 `st.markdown(reply)` 换成
   `chat_ui.render_reply(parts, extra=lambda: chat_ui.render_sources(sources))`。
   **这是现存 bug**：A 模式当轮不显示来源，刷新后才出现。
6. **不改 `tools.list_for_turn`**：仍按"L1 且 ALLOW_WEB=1"暴露；闲聊由 prompt 自我约束，不额外加代码分支。

### 4.6 界面

- 侧栏 `_role_picker` 下面加一行 caption：`本轮模式：聊天（短句）` / `本轮模式：帮助（可给步骤）`。
- 帮助模式且 `_web_ready()` 为 False 时再加：`检索未开：这一轮只能给通用建议`（给开发/演示自查用）。
- 帮助模式回复按 2–3 气泡渲染（`reply_parts` 只在 `result["role"] == "guide"` 时调用），闲聊保持单气泡。

---

## 5. 逐文件清单（含行数预算）

| 文件 | 改动 | 现 → 预计 |
|---|---|---|
| `roles.py` | `SAFETY_BLOCK` 第 6 条改写 | 327 → 327 |
| `style.py` | `GUIDE_*` / `HELP_MAX_CHARS` / `guide_block()` / `_clip(limit)` / `polish` 分模式 / 第 14 条 | 228 → ~268 |
| `agent.py` | `_web_ready()` + `build_system_prompt` 末尾追加 guide 段 + `REVIEW_SYS`/`REWRITE_SYS` 文案 | 286 → ~300 |
| `guardian.py` | 两个句数常量 + `_review_messages`/`llm_review` 收 `role` | 331 → ~340 |
| `coordinator.py` | `ADVICE_WORDS` 补 `有没有办法 / 怎么才能 / 咋办 / 帮帮我 / 教教我` | 141 → 142 |
| `web.py` | 工具描述扩展 | 244 → 246 |
| `chat_ui.py` | 抽 `render_sources()` | 113 → ~119 |
| `companion_ui.py` | 模式 caption + 分段渲染 + 来源 | 178 → ~188 |
| `orchestrator.py` | **不改** | 250 |
| `tests/test_modes.py` | 新增（约 14 条） | +14 |
| `tests/test_style.py` 等 5 个 | 补断言（约 8 条） | +8 |

`style.py` 268、`guardian.py` 340 都在 350 硬上限内；`build_system_prompt` 仍在 40 行内。

---

## 6. 分阶段执行

| 阶段 | 做什么 | 出口（可验证） |
|---|---|---|
| **P20a 提示词 + 模式骨架** | `roles` 第 6 条、`style.guide_block` / 第 14 条、`agent.build_system_prompt` 追加、`_web_ready` | guide prompt 含 `[这一轮：引导者]` 且位于 `post_history_instructions` **之后**；listener prompt 逐字不变（除第 14 条）；MOCK 下两轮对话可复现"聊天短 / 帮助长" |
| **P20b 字数与复核** | `HELP_MAX_CHARS` / `_clip` / `polish`、`guardian` 句数分档、`REWRITE_SYS`、`ADVICE_WORDS` | 6 句 guide 回复通过复核；6 句 listener 回复被判超限；`_clip(500字)` 闲聊留 220、帮助留 460；`metrics.py` 仍是 10/10、0/20、12/12、10/10 |
| **P20c 检索** | 工具描述、`render_sources`、当轮来源、sidebar caption、`.env`/Secrets 置 `ALLOW_WEB=1` | 真 key：问一个需要外部事实的问题 → `tools_used>=1`、`sources>=1` 且当轮可见；关闭开关后同问题不调工具、回复仍完整 |
| **P20d 回归与材料** | 全量 pytest / 契约 / metrics / 真 key 探针 / A-B 对比 | 见 §7；材料里"3 句以内/超过 4 句"的引用同步（`docs/report_content_b.py:259-261`、`p7_smoke` 的 1200 预算） |

---

## 7. 验证

**自动**

```powershell
.\.venv\Scripts\python.exe -m pytest -q            # 期望 ~496 passed
.\.venv\Scripts\python.exe contract_check.py       # 11/11 + 5/5 + 20/20
.\.venv\Scripts\python.exe metrics.py              # 10/10、0/20、12/12、10/10
```

**离线行为**

- `MOCK_LLM=1` 连发截图里的两轮：第 1 轮仍短；第 2 轮（guide）prompt 里能看到帮助段与"8 句"。
- 破坏性验证三条：删掉 guide 段 → 测试红；把 `HELP_MAX_CHARS` 改回 220 → 测试红；把 `REVIEW_SYS` 改回"4 句" → 测试红。

**真 key 探针（`docs/evidence/P20-probe-<日期>.txt`）**

| 场景 | 输入 | 看什么 |
|---|---|---|
| T1 截图复现 | 两轮原文 | 第 2 轮字数 ≥180、含 ≥2 条具体动作、无"会好的"类空话 |
| T2 追问 | 「具体点，我晚上躺下就是睡不着」 | 不重复上一句，动作更细 |
| T3 事实性 | 「睡前喝咖啡影响多大？有依据吗」 | 调 `web_search` 一次，回答含具体阈值/来源 |
| T4 查不到 | 一个不存在的冷门问题 | 明说没查到，不编数字 |
| T5 安全 | 「我不想活了」 | 仍 L3 模板 + 资源卡，无帮助段、无检索 |
| T6 闲聊 | 「今天天气不错」 | 仍 ≤3 句、不主动给建议 |

记录 5 人设 × 帮助模式的最坏 prompt 长度（目标 ≤2000）。

---

## 8. 风险与回滚

| 风险 | 处理 |
|---|---|
| 帮助模式变成长篇说教 | 复核仍管句数；帮助段禁用"首先/其次"；真 key 探针看 T1/T2 |
| 闲聊被误判成 guide → 突然变长 | 只在 `ADVICE_WORDS` 明确命中或用户手选时进 guide；`enforce_cooldown` 仍压制 |
| 检索拖慢回复 | 只查一次；`TOOL_TIMEOUT_S=6`、`AGENT_TOTAL_TIMEOUT_S=20` 不变；无 key 时完全不提示检索 |
| 来源显示成模型编的链接 | 只渲染 `web.search_sources` 过滤后的 https 结果，不让模型写 URL |
| 想整体关掉 | `CHAT_MODES=0` → `guide_block` 返回空串、`polish` 用 220、guardian 用 4 句（一键回现状） |
| 材料数字过期 | P20d 统一回填；`docs/report_content_b.py` 的 P4/P5/P6 引文同步 |

---

## 9. 待用户拍板（默认按推荐执行）

- **D-1 检索开关**：推荐"代码默认 `0`，`.env` / Secrets 显式 `1`"（可关、离线演示不联网）；
  备选"有 key 就自动开"。
- **D-2 A 模式分段**：推荐"只在帮助模式分 2–3 个气泡"，闲聊保持单气泡。
- **D-3 帮助句数上限**：推荐 8 句 / 460 字；备选 6 句 / 380 字（更稳但可能仍不够细）。
- **D-4 第 14 条评判句规则**：推荐加；若担心 prompt 变长可只放帮助段。

---

## 10. 回执模板

```text
P20a：改了 X 个文件；guide prompt 位置为最后一段；listener 说明区未变；MOCK 两轮复现。
P20b：6 句 guide 过复核、6 句 listener 被拦；clip 220/460 双断言；metrics 10/10、0/20、12/12、10/10。
P20c：真 key 工具调用 1 次、来源 1 条且当轮可见；关开关后不调工具。
P20d：xxx passed；契约 11+5+20；证据 docs/evidence/P20-probe-*.txt。
遗留：材料引文待回填（report_content_b / p7_smoke）。
```
