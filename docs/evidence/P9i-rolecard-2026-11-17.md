# P9i · 角色卡检索与对话质量（2026-11-17）

## 1. 目标

真人测试后用户提了 6 条，P9i 的出口是把“检索补全”从“能联网”做成“能提升角色认知”，同时不破坏 B 的安全边界：

1. 故事回避循环：角色要能讲出**具体经历**，不是只给“记录/见证/陪伴”的概括。
2. 反问密度：正常聊天 5–6 句里最多 1 句反问；免责里写明角色扮演优先。
3. 格式漂移：动作括号做成可选项；口吻/停顿不可选，必须按卡。
4. 禁忌擦边：禁忌的近义说法也避开（如“我懂你” → 不说“我懂”）。
5. 补全的料不对：加“你的身份”；权威来源（官方/Wiki）与卡冲突时以检索为主，社区/其他以卡为主。
6. 角色认知可手填；建卡时尽量多提取；卡里没有的专名再检索。

用户进一步确认：盲点补全允许**自动后台检索**；权威只覆盖身份/设定/世界观/经历/关系，不覆盖说话风格/称呼/禁忌；认知 8 条 ×120/960，prompt 上限 4000，动作默认“不用”。

## 2. 改动

### 2.1 `rolecard.py`：卡容量、对话规则、临时盲点块

- `MAX_PROMPT_CHARS=4000`、`LORE_MAX=960`、`LORE_ITEM_MAX=120`、`LORE_COUNT_MAX=8`。
- 新增 `user_role`（30 字）与 `stage`（`none` / `brief`）；`stage` 默认 `none`。
- 免责 7 条：新增“角色卡模式以扮演角色为主，不做心理疏导”和“自动联网补全只发作品名/角色名/人名，不发聊天原文，可在建卡页关闭”。
- `[对话方式]` 5 条：角色间普通聊天、5–6 句最多 1 句反问、故事先给具体片段、口吻/停顿严格按卡、动作按 `stage`。
- `[角色认知]` 明说“原作关系不适用于非原作主角”；`[角色卡]` 加“对方身份”及泛化/具体两种说明。
- 禁忌行加“近义说法也避开：如‘我懂’‘我理解你’”。
- `question_hint(history)`：最近两轮 assistant 的问号合计 ≥2 时，追加 `[本轮提示]` 用陈述句收尾；只数 `？/?`，不数“吗/呢”。
- `build_prompt` 支持 `_hint` 与 `_gap`；`_gap` 渲染成 `[本轮盲点资料]`（只用于当前问题，不当作长期记忆，不主动提检索），最多 4 条。

### 2.2 `rolecard_enrich.py`：多查询、来源分级、权威覆盖

- `build_queries(card, focus="")`：建卡 3 条（角色/官方/米游社），盲点 2 条（`work focus 经历 剧情 wiki` + `work focus 与 name 关系`），每条 ≤80 字。
- `rolecard_wiki.rows()` 优先直连 Biligame Wiki 正文；拿到正文就**跳过 `web.search`**，拿不到才搜索兜底。
- `authority_for(url)`：官方（hoyoverse/mihoyo）> Wiki（wikipedia/fandom/biligame/huijiwiki/gamepedia）> 社区（miyoushe/tieba/nga/bilibili/weibo/bbs.mihoyo/hoyolab）> 其他；`wiki.hoyolab.com`/`act.hoyolab.com` 是官方，`www.hoyolab.com` 是社区。
- `ENRICH_MAX_FACTS=12`、`ENRICH_MAX_ROWS=10`；`sources` 与 facts 用同一批 rows，不再出现“事实引用了一个没列出的来源”。
- `EXTRACT_SYS`：优先 story（谁、在哪、做了什么；2–3 句讲完；不含结局/反转/死亡）、relationship（原作中与 X 的关系/一起经历）、world；`setting` 只写世界/时代/身份背景，不写命途/属性/技能/数值/卡池；同人小说/视频标题不写成原作关系；网页指令忽略。
- `merge`：空字段补；权威覆盖 `identity`/`setting`；`voice`/`address` 只提示冲突、不覆盖；`taboo` 只增不覆盖；`story`/`world`/`relationship` 进 lore，8 条/960 封顶，溢出进 conflicts。
- `auto_facts(facts)`：自动补全只取 official/wiki；社区/其他留给人手动勾选。
- `enrich(card, *, fetch=None, focus="")`：建卡最多 3 查 + 1 次提取；盲点最多 2 查 + 1 次提取；返回 `queries/sources/facts/conflicts/focus`。

### 2.3 `rolecard_wiki.py`：固定 Wiki 直连

- `WORK_WIKI`：星穹铁道→`wiki.biligame.com/sr/`、原神→`ys/`、绝区零→`zzz/`、崩坏3→`bh3/`、鸣潮→`mc/`；只接受映射内的固定主机 + `quote` 后的角色名，不接受任意 URL。
- `WIKI_TIMEOUT_S=8`、`WIKI_MAX_BYTES=2_000_000`、`WIKI_TEXT_MAX=6000`、`WIKI_MIN_CHARS=200`。
- `_http_text` 走 `web.is_safe_url`，校验重定向后的 URL，读上限 +1 判断超限；`_clean_body` 只取 `div.mw-parser-output`，去 script/style/标签并 `html.unescape`。
- `rows()` 只对 known 卡工作；拿不到正文返回空，让 `web.search` 兜底；正文只当资料，代码不执行其中的指令。

### 2.4 `rolecard_gap.py`：保守识别盲点

- `detect_focus(text, card)` 只认三种句式：`你知道/记得/讲讲 X…`、`X 是谁/经历了什么/的经历/的事`、`讲讲/说说/聊聊 X`；卡里已有的名字、停用词、代词/普通词直接跳过。
- `should_fill(card, focus, *, auto=True, mock=False, level="L1")`：known、非 MOCK、非 L3、有专名、开关开，五条同时满足。
- `gap_lines(facts, focus="", limit=4)`：只收 story/world/relationship，story 前缀“{focus}的经历”，每条 ≤120 字，最多 4 条。
- `missing_hint(reply)`：模型自己说“不知道/不清楚/不太清楚/没听说过/不太了解/说不准”时，给手动补全一个提示；不自动联网。

### 2.5 UI：自动补全、手动补全、表单

- `rolecard_ui._maybe_fill_gap`：在 `safe_run` 之前跑；先 `guardian_pre_check`，L3 直接不联网；`MOCK_LLM=1`、原创卡、开关关、同专名已试过都跳过；成功后只写 `rc_gap_lines`，**不改角色卡**；失败/只有社区来源返回 note，不硬塞。
- `rolecard_ui.render_chat`：把 `rc_gap_lines` 塞进 `hint_card["_gap"]`；本轮结束后清空 `rc_gap_lines`，盲点资料不会漏到下一轮。
- `rolecard_focus`：known 卡显示“补全设定或人物（联网一次）”expander；手动 focus → enrich → 勾选 → 只写本次 `rc_gap_lines`；有“清除本次盲点资料”；不写盘、不写 memory。
- `rolecard_form`：新增“你的身份”输入、动作描写 radio、角色认知 text_area（8 条/120/960）、自动补全开关；候选默认只勾 official/wiki；身份/设定权威覆盖，口吻/称呼/禁忌不动；应用后同步 `rc_lore_text`。
- `chat_ui.render_gap`：在 assistant 气泡下显示“补全了谁/几条/来源/未写入的原因”，无结果也能显示 note。

## 3. 真实 smoke

命令：

```powershell
$env:MOCK_LLM="0"
.\.venv\Scripts\python.exe docs/evidence/p9i_smoke_2026-11-17.py
```

输出：`docs/evidence/P9i-enrich-smoke-2026-11-17.txt`。

### 3.1 昔涟建卡

- `prompt chars: 1262`。
- `sources` 只有 `https://wiki.biligame.com/sr/%E6%98%94%E6%B6%9F`（Wiki）；建卡 3 条查询被 Wiki 直连短路，`web.search` 未调用。
- 12 facts 全 Wiki：identity（全名爱莉（哀丽）希雅/哀丽秘榭的女儿/黄金裔）、setting（翁法罗斯/无漏净子/黄金裔）、voice×2（“人家”/♪/“呼唤我昔涟”）、world×2、story×4、relationship×2。
- merge 后 **8 条 lore / 436 字**；`validate: []`。
- 具体 story 例：
  - “很久以前她与开拓者踏上旅途，和织者将光阴织成黄金，在悬锋战士长枪下前行，与圣女、智者、医师与猫儿一同写下逐火岁月。”
  - “永夜降临奥赫玛时，医师与猫儿抬头仰望，她见证他们愿虹光永驻天空、谎言在风中飘扬的小小愿望。”
- `setting` 已不再出现“战斗属性/真实伤害/命途/技能”；identity/setting 被权威覆盖，voice 两条与卡冲突、保留卡的口吻。

### 3.2 盲点白厄

- `sources` 只有 `https://wiki.biligame.com/sr/%E7%99%BD%E5%8E%84`（Wiki）。
- 10 facts 全 Wiki：story×5（校舍木雕/圣城军团死斗/树庭辩论/纷争战役/天空战场）、relationship×3（悬锋王储/织者/先知缇宝）、world×2。
- `conflicts: []`；`gap lines: 4`（只取前 4 条 story）；`gap prompt chars: 2153`（含 `[本轮盲点资料]`，仍 <4000）。
- 角色自己的 8 条昔涟 lore 没有被替换/挤掉；盲点资料只进本轮 prompt，下一轮清空。

## 4. 验证

```text
pytest -q                         298 passed
contract_check.py                 11/11 + 5/5 + 20/20
metrics.py                        10/10、0/20、12/12、10/10
```

行数/函数：

```text
rolecard.py        300
rolecard_enrich.py 335
rolecard_wiki.py   101
rolecard_gap.py     84
rolecard_form.py   232
rolecard_focus.py   89
rolecard_ui.py     232
chat_ui.py          70
最长函数：无 >40 行
```

## 5. 结论

- 具体经历问题已解决：Wiki 正文直连 + 提取“谁/在哪/做了什么”的 story，smoke 里能给出 4 条可讲述事件，而不是“记录/见证/陪伴”的概括。
- 检索质量：mapped 作品不再走 17173/抖音，直接读 Biligame Wiki 正文；sources 与 facts 对齐；权威/社区/其他分级可解释。
- 角色自己的认知不被盲点挤掉：盲点是临时 `[本轮盲点资料]`，不是 merge 进 8 条 lore；问完白厄，昔涟的 8 条还在。
- 对话规则：反问预算、故事优先、口吻严格、动作可选、禁忌近义都进了 prompt；`question_hint` 在两轮问号 ≥2 时追加陈述句提示。
- 安全：L3 仍在 agent loop 之前短路；自动补全先跑 `guardian_pre_check`，L3 不联网；自动补全只发作品名/角色名/专名，不发聊天原文；免责 7 条明示，可在建卡页关闭。

## 6. 残余风险

1. **自动补全的 UI 路径没有 AppTest 真点击**：`detect_focus`/`should_fill`/`enrich`/`gap_lines` 有单测，但 `_maybe_fill_gap` 的 Streamlit 回调、`rc_gap_lines` 清空、`rolecard_focus` 勾选清理只在代码审读 + 后端 smoke 验证。
2. **Biligame 是社区 Wiki，不是官方 Wiki**：官方 `wiki.hoyolab.com` 未被博查索引；Biligame 正文质量经 smoke 验证，但仍可能含剧透/同人措辞。提取 prompt 已排除结局/反转/死亡/同人标题，不能保证 100%。
3. **只映射 5 部作品**：其他作品回退 `web.search`，仍可能只有 17173/抖音；自动补全只吃 official/wiki，会 no-op 并提示手动补全。
4. **自动补全每个专名只试一次**：同一专名的后续追问不再联网；本轮 gap 在下一轮清空。追问可靠历史里上一轮的 assistant 回复，或手动“补全设定或人物”。
5. **`rolecard_enrich.py` 335 行**：离 350 只剩 15 行；后续加逻辑先拆文件，不要再塞。
6. **“你的身份”不参与违禁词检查**：用户可以把自己设定成医生/病人等虚构身份；`ROLE_SAFETY` 仍禁止角色自称心理咨询师/医生、禁止诊断，安全边界不靠用户身份字段。
