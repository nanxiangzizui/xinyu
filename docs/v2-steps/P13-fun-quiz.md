# P13 · 侧栏趣味测试小游戏（4 个 / 每题 ≤12 / 声明 + 报告 + 自然讨论）

> 状态：2026-11-17 **已完成**。基线 371 → **405 passed**；契约 11/11 + 5/5 + 20/20；四指标 10/10、0/20、12/12、10/10。
> 范围：只做 A 陪伴模式的「趣味游戏」入口。**不是心理测评**；不碰 `guardian` / `coordinator` 的判定逻辑、不动 `RULES`、不加依赖。
> 依据：用户 2026-11-17 的口述需求（m00001）+ 同日晚的三处修订（m00125）+ 桌面 `测试网址.txt`。

## 1. 做什么

左侧栏加一个入口：一句文案 + 一个按钮。点开后是**内联卡片**（与 P11 首屏问答同形，不新增 mode、不挡 `chat_input`）：

声明 → 先选一个游戏 → 一次一题（≤12 题）→ 结果卡 → AI 出一份**只总结、不引导**的报告 → 末尾问「想与我探讨一下测试结果吗？」→ 用户想聊就自然聊。

| 用户原话 | 落地 |
|---|---|
| 「这不是心理健康测试」 | 声明卡在**每次点开**时出现，勾选「我知道了，这只是个小游戏」后才能开始；文案里不出现「测评 / 诊断 / 你属于」 |
| 「AI 不应直接将测试结果作为标准代入对话」 | ① 结果**不进 `memory.json`**，只存 `data/memory/quiz/<sid>.json` 这一区；② 只有用户自己提起测试/结果名时才召回；③ `SPEECH_RULES` 第 13 条全局口径；④ 报告过 `guardian`；⑤ `memory_extract.A_SYS` 明确不记 |
| 「题目不能太多，15 道内」 | 4 个游戏分别 **12 / 10 / 12 / 10 题**；`MAX_QUESTIONS = 15` 由测试锁死 |
| 「先让用户选择测其中一个」 | 声明页先选游戏（radio），选中才进题；不会四个一起铺开 |
| 「写进一个特殊的记忆区，AI 不主动想起」 | 单独文件 + `recall()` 话头门；prompt 只在命中时多一行 `_quiz_text` |
| 「联网不要显示出来，拿不准时后台自动检索」 | 报告前静默查一次，只取白名单站点的正文片段（≤2 条 ×120 字），**不取网址、不进消息** |

## 2. 关键决策

| 编号 | 结论 | 理由 |
|---|---|---|
| Q1 入口 | 侧栏 caption（用户原句）+ 按钮「来做个小测试」；卡片内联 | 与 P11 同构；新增 mode 会把 A/B 两态变三态 |
| Q2 题目集 | 分院帽 / 阵营坐标 / 四维小性格 / 六种小动物 | 参考站点里能过安全审的就这几类；全部 ≤12 题 |
| Q3 结果落盘 | **落盘到独立小本子**，不写 `memory.json` | 用户要「特殊记忆区」：能跨刷新对比，又不污染 8 字段白名单 |
| Q4 MBTI 壳 | 保留四维，但全中文、不出现字母 | 卡内与报告都不冒充官方；副标题写「和任何官方人格测验都没有关系」 |
| Q5 联网 | 只在报告前静默查一次；`ALLOW_WEB=1` 且非 MOCK 才开 | 不需要改 `tools` / `agent_loop`；默认关；失败就当没有 |
| Q6 讨论守卫 | 不加专用守卫：`SPEECH_RULES` 第 13 条 + `guardian` + 报告层把说教句换模板 | 少一个否决点，避免与 `guardian` 职责重叠 |
| Q7 讨论轮（m00425 追加） | 要「分析」时给维度抓手 + 一条怎么聊的指令，并让「每轮只做一件事」让位 | 用户反馈只回一句反问；3–5 句、200 字内，先给内容再提问，不下结论 |

### 2.1 四个小游戏

| id | 名称 | 结果 | 题数 | 每题选项 | 计分 |
|---|---|---|---|---|---|
| `house` | 四院分院帽 | 4 | 12 | 4 | 多票取最高（平票取组内靠前） |
| `align` | 阵营小坐标 | 4 | 10 | 4 | 双轴（秩序/随性 × 热心/自守），**不用「善良/邪恶」** |
| `temper` | 四维小性格 | 16 | 12 | 2 | 四个二分各 3 题取多数，结果名全中文 |
| `beast` | 六只小动物 | 6 | 10 | 3 | 多票取最高 |

**明确不做**：黑暗人格（darkfactor）、字母圈（zyuxian）、政治倾向（politiscals / github.io）、负面人格（arealme difficult-person）、DnD 九宫格（来源是 github.io 转载）。理由：自我污名、尺度、与情绪陪伴无关、来源不明。

**参考白名单**（`LOOKUP_DOMAINS`，只认 host 本身与子域）：
`16personalities.com` / `16type.com` / `jungus.cn` / `totypes.com` / `arealme.com` / `cnenn.cn` / `advanced-personality.com` / `apesk.com` / `yuzeli.com` / `cnpsy.net` / `wizard-tool.com`。白名单内没命中就不引用。

## 3. 接口（已落地）

```text
quiz_data.py   MAX_QUESTIONS=15 / OPTION_MIN=2 / CTA / DECLARATION / LOOKUP_DOMAINS
               QUIZZES: dict[str, dict] / ORDER: tuple[str, ...]
quiz.py        get(qid) -> dict | None
               score(quiz, answers: list[int]) -> dict          # key/name/line/scores/quiz/title
               host_allowed(url) -> bool
               reference(quiz, result) -> list[str]             # 静默参考，不含网址
               report(quiz, result) -> str                      # 代码拼标题与 CTA
quiz_store.py  read_store(sid) / write_store(sid, store) / append(sid, result) -> bool
               recall(sid, text) -> str                         # 命中话头才返回块
               clear(sid) -> bool / count(sid) -> int
quiz_ui.py     entry() / render(sid) / clear(sid) / reset_state()
```

动过的既有签名：无。`orchestrator.handle` 只在内部多读一次 `quiz_store.recall`；`chat_ui.accept` 的轮次口径多排除 `quiz` 标记。

## 4. 数据结构

```python
# quiz_data.QUIZZES[qid]（手写时题目是元组，导入时 _rows() 转成 dict）
{"id": "house", "title": "四院分院帽", "subtitle": "……",
 "lookup": "分院帽 四个学院 性格 特点",
 "dims": ("brave", "smart", "kind", "ambition"),
 "dim_names": {"brave": "勇气", ...},
 "groups": ((0, 1, 2, 3),),                 # 结果键 = 各组最高分维名用 "|" 连接
 "questions": ({"q": "题干", "opts": (("选项", "维度名"), ...)}, ...),
 "results": {"brave": {"name": "勇气院", "line": "……"}}}

# data/memory/quiz/<sid>.json —— 特殊记忆区，最多 20 条
{"attempts": [{"quiz": "house", "title": "四院分院帽", "key": "brave",
               "name": "勇气院", "scores": {"勇气": 6, "思辨": 2}, "ts": 1763...}]}
```

- **只存游戏名 / 结果名 / 维度分**，不存答案、不存原话、不存网址。
- 会话状态：`quiz_state`（ack / run / done）、`quiz_id`、`quiz_answers`、`quiz_result`、`quiz_pick`、`quiz_ack`。

## 5. 流程

1. 侧栏点「来做个小测试」→ `quiz_state="ack"`（**每次都重新看声明**）。
2. 勾选 + 选一个 → 开始 → `quiz_state="run"`，`quiz_answers=[]`。
3. 一次一题，答完追加下标；最后一题的按钮是「看结果」。
4. `quiz.score` → `quiz.reference`（静默，白名单，失败为空）→ `agent.call_llm(QUIZ_REPORT_SYS)` → `guardian.guardian_post_check`。
5. 报告消息 = 「《标题》的结果：<结果名>」+ 模型正文（≤200 字，去掉模型自加的 CTA）+ `CTA`，带 `quiz: True`。
6. `quiz_store.append(sid, result)` 落盘 → 消息进 `messages` → `quiz_state="done"`。
7. 之后用户自己说「上次那个测试」→ `quiz_store.recall` 命中 → `orchestrator` 把块塞进 `facts["_quiz_text"]` → `agent._facts_block` 拼进 prompt。

## 6. 专项规则

- **声明**：`DECLARATION` 三条（不是测评 / 不拿结果判断、不主动提、单独存、清空一起删 / 最多 12 题随时关），每次开卡片都显示，勾选才能开始。
- **报告不引导**：`QUIZ_REPORT_SYS` 要求只总结、2–4 句、90 字内；标题行与 CTA 由代码拼，模型写不出第二个结果名、也写不出第二句 CTA。
- **报告过 guardian**：`guardian_post_check(prompt, body, "L1", "listener")`；不通过、`template_fallback`、或命中 `preachy` 都用模板（`result["line"]` + 「这只是一个游戏标签」）。
- **特殊记忆区**：`recall()` 只认 `CUES`（测试/测验/小游戏/答题/问卷/做过的题/那个题）或已存的 title/name；命中才把「[趣味测试记录]」块交出去，块首写明「只在对方自己提起测试时用；不要主动提，不要拿结果评价对方」。
- **不进 memory.json**：`memory_extract.A_SYS` 新增第 9 条，明确测试结果和答案都不记。
- **静默联网**：`ALLOW_WEB=1` 才查；`host_allowed` 先过 `web.is_safe_url`（https、非内网）再比对白名单；只取 snippet，不取 url；异常吞掉只记类型名。
- **清空**：`app._clear` 的清理 tuple 加 `quiz_ui.clear`，一起删正文 / `.bak` / `.tmp`。
- **讨论轮（m00425）**：`CUES` 额外收「这个结果 / 这份结果 / 那份结果」（不收光秃秃的「结果」，否则「结果我还是没去」也会把块勾出来）；命中 `ANALYZE_CUES` 时块里追加一条怎么聊的指令：先说最高的一项、再说最低的一项、最后合起来说一句，3–5 句、200 字内，先给内容再提问，不要整条只有一句反问，不下结论、不建议改变。`_note_line` 只解释最近一次、且只解释有分的项（`quiz_data.dim_notes`，22 条）。
- **风格层让位**：`SPEECH_RULES` 第 13 条追加「对方想聊结果时，『每轮只做一件事』让位：先从最高的一项说起，讲具体一点，可以多说两句，别只回一句反问。」
- **不占轮次**：报告消息带 `quiz` 标记，`chat_ui.accept` 求和时排除它和 `opening`。

## 7. 改动清单

| 文件 | 行数 | 改了什么 |
|---|---|---|
| `quiz_data.py` | 269 | 新增：题库、声明、CTA、白名单、`_rows()`、`dim_notes`（22 条维度解释） |
| `quiz.py` | 154 | 新增：计分 / 静默检索 / 报告 |
| `quiz_store.py` | 171 | 新增：特殊记忆区（原子写、上限 20、话头召回、分析指令） |
| `quiz_ui.py` | 132 | 新增：入口 / 声明 / 答题 / 结果卡 |
| `app.py` | 234 | 侧栏入口、主区卡片、`_clear` 一起删、抽出 `_turn()` |
| `orchestrator.py` | 246 | `facts` 后加 3 行召回；`_mark_crisis` 搬去 `coordinator.mark_crisis` |
| `coordinator.py` | 113 | 新增 `mark_crisis(state)`（原样搬迁） |
| `agent.py` | 277 | `QUIZ_REPORT_SYS` / `MOCK_QUIZ_REPORT` / `_facts_block` 读 `_quiz_text` |
| `chat_ui.py` | 74 | 轮次排除 `quiz` 消息 |
| `style.py` | 170 | 第 13 条说话规则（含讨论轮让位） |
| `memory_extract.py` | 182 | `A_SYS` 第 9 条 |

## 8. 测试（38 条）

- `tests/test_quiz.py`（18）：题量 ≤15、选项与维度齐全、结果键覆盖每组坐标、计分确定性与平票规则、坏答案忽略、无病名词、无 MBTI 字母、`host_allowed` 四种坏 URL、静默检索开关 / 白名单过滤 / 异常兜底、报告标题与 CTA 由代码拼、模型失败与说教句换模板、**特殊记忆区只在话头命中时进 prompt**、**要分析时块里带维度解释与怎么聊的指令且 prompt ≤1800**。
- `tests/test_quiz_store.py`（12）：落盘往返、不存答案与网址、无话头不召回、按结果名召回、跨会话隔离、块首口径、维度解释只出现一次且 0 分项不解释、分析话头才加指令、截图原句能召回而日常「结果……」不召回、20 条上限、坏数据丢弃、清空。
- `tests/test_quiz_ui.py`（8）：侧栏入口不挡聊天、声明与输入框共存、未勾选不能开始、关掉后要重新勾、完整一局出报告并落盘、报告不算一轮、结果不进 `memory.json`、清空连小本子一起删。

## 9. 验证

```text
pytest -q                        417 passed in 23.34s
contract_check.py                11/11 + 5/5 + 20/20
metrics.py                       10/10 · 0/20 · 12/12 · 10/10
prompt（含分析块，5 人设）        最坏 1669 / 1800
块体积                           「帮我分析分析这个结果」249 字
行数                             orchestrator 250 / app 234 / quiz_data 269 / quiz_store 171
```

证据：`docs/evidence/P13-quiz-2026-11-17.txt`。

## 10. 失败与回滚

- 报告生成失败 → 模板兜底（不影响聊天等级）。
- 检索失败 / 非白名单 / 未开 `ALLOW_WEB` → 视为没有参考，报告照写。
- 小本子读坏 → 当空；写失败只记类型名，不阻塞本轮。
- 回滚：删 `quiz_*.py` + `app.py` 里 3 处调用 + `orchestrator` 3 行 + `chat_ui` 一处条件即可；无数据迁移（`data/memory/quiz/` 可直接删）。

## 11. 出口

- [x] 侧栏入口、声明 gate、4 个游戏、每题 ≤15
- [x] 报告只总结、不引导；CTA 由代码拼
- [x] 结果只进特殊记忆区，`memory.json` 无痕迹
- [x] 无话头不召回；有话头才拼进 prompt
- [x] 静默检索只认白名单，不显示来源
- [x] 用户要分析时先讲维度、不只回一句反问（m00425）
- [x] 清空对话连小本子一起删
- [x] 405 passed / 契约 11+5+20 / 四指标不变
