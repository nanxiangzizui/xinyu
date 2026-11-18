# P17 · 首屏放松入口（列表式首页 + 九个小工具）

> 状态：**已落地（2026-11-18）**；D17-1~5 已拍板，D17-9/10/11 已拍板（3 个文字游戏全加、按读音接龙、独立卡片），首发 12 项；基线从 **430 passed**（P16）升到 **467 passed**，契约 11/11 + 5/5 + 20/20。
> 环境音按用户 D17-2 改为 Wikimedia Commons 公开音频（浏览器点击后加载）；本机下载 TLS 失败，未打包音频文件，页面写明来源/许可与失败提示。
> 范围：只改「入口层」——首屏从聊天框改成列表，新增六个本地放松小工具、三个文字小游戏与独立测试页；**不碰** `guardian` / `coordinator` / `RULES` / `orchestrator` 的判定逻辑，不动 `memory.json` 白名单，不加依赖。
> 依据：用户 2026-11-18 口述需求（m00002）+ 桌面 `加入功能.txt`（7 类放松方式与 MVP 建议）+ 现有 P11/P13/P14 的交互口径。

## 1. 做什么

现在一进站点就是聊天框。改成：

```text
心屿
这是一个情绪陪伴工具，不是心理咨询，也不能替代真人帮助。……

今天想怎么待一会儿？
不用选对。哪个看起来不费力，就点哪个。

陪伴
  与心屿聊聊天            说说现在就好
  给心屿一张角色卡        写一张卡，让一个虚构角色陪你说话

先让身体慢一点
  跟着呼吸                吸 4 秒，呼 6 秒，约 1 分钟
  5-4-3-2-1 接地          把注意力挪回身边
  一分钟微休息            随机一个小动作

不用说话的方式
  写下来                  两行字，只留在这台设备
  环境音                  雨 / 风 / 海浪，默认静音
  看看别处                几个外面的一分钟

动动脑子，不费劲
  趣味小测试              四个小游戏，不是心理测评
  脑筋急转弯              想不出来也没关系
  猜谜语                  给点提示再看答案
  成语接龙                按读音接，接不上我帮你接

  不知道选哪个？[随便来一个]

如果你现在就需要帮助
  12356 / 110 / 120 / 校心理中心 0571-87713518
```

点击后的行为：

| 入口 | 目标 | 关键点 |
|---|---|---|
| 与心屿聊聊天 | `mode="companion"` | 原来的 A 模式原样保留：首屏 5 题、聊天、侧栏记忆面板、趣味测试侧栏入口 |
| 给心屿一张角色卡 | `mode="rolecard"` | 原来的 B 模式原样保留：免责 gate → 建卡 / 聊天；`ROLECARD=0` 时首页不显示 |
| 六个放松入口 + 三个文字游戏 | `mode="relax"` + `relax_page` | 全部本地、确定性、无 LLM、无判级；文字游戏无计时、无排名；随时可回首页 |
| 趣味小测试 | `mode="quiz"` | 独立页；报告仍进 `messages`，多一个「聊一聊这个结果」回陪伴模式 |
| 随便来一个 | `mode="relax"` + 随机页 | 只在九个本地页里挑，不挑聊天 / 角色卡 / 测试 |

**一句话**：首页只负责「选一个入口」，不接管聊天、不判级、不写记忆。

## 2. 关键决策

| 编号 | 结论 | 理由 |
|---|---|---|
| **D17-1** | 默认 `mode="home"`；`HOME_HUB=0` 可回退到原来的陪伴首屏 | 出问题一键回退，不用 revert 一批文件；与 `AGENT_LOOP` / `ROLECARD` 同思路 |
| **D17-2** | 首发 12 个入口：2 个陪伴入口 + 6 个放松入口 + 4 个「动动脑子，不费劲」（趣味测试 + 3 个文字游戏） | 覆盖「身体、感官、文字、声音、外面、轻游戏、文本游戏」；每个都能在 1–3 分钟里停 |
| **D17-3** | 环境音用 **Wikimedia Commons 公开音频**，浏览器点击后才加载；不打包音频文件 | 用户 2026-11-18 拍板「上网搜集音频，然后调用」；雨/海浪为 Public domain，风为 CC BY-SA 4.0，页面署名；服务端不取音频，加载失败有提示 |
| **D17-4** | 「写下来」只放 `st.session_state`，**不落盘、不进记忆、不进日志** | 用户文件里说「本地保存」，但本项目的数据红线更严：不存原文；关页即清 |
| **D17-5** | 趣味测试做**独立页**，同时保留侧栏入口；报告仍进 `messages` | 首页点进来是一个完整页面，不会一进来就被聊天框包围；「聊一聊」再回 companion |
| **D17-6** | 外链只做 `st.link_button`，**不嵌 iframe、不内嵌直播** | 广告 / 隐私 / 版权 / 网络不可控；新窗口 + 「将离开本站」即可 |
| **D17-7** | 所有放松页不调用 `agent` / `orchestrator` / `guardian`，不判级 | 这些是确定性小工具，不是对话；出故障也不该影响聊天安全链路 |
| **D17-8** | 把 `app.py` 的 A 页代码抽到 `companion_ui.py`，`app.py` 只做路由 | 首页、聊天、角色卡、测试、放松五态塞进 234 行会涨到 400+；先拆再加 |
| **D17-9** | 加 3 个文字小游戏：脑筋急转弯 / 猜谜语 / 成语接龙 | 2026-11-18 用户拍板「3 个都加」；本地词库、无 LLM、无计时、无排名 |
| **D17-10** | 成语接龙按**读音**接：同字或同音（声母+韵母，声调不计）都算 | 用户拍板「按读音即可」；拼音写在词库里，不引入 `pypinyin` 之类的新依赖 |
| **D17-11** | 三个游戏做独立卡片，放在「动动脑子，不费劲」组 | 用户拍板「独立卡片」；每页只做一件事，不合成一个大杂烩页 |

### 2.1 为什么不是「所有功能都搬上来」

- **渐进肌肉放松 / 睡前故事 / 番茄钟**：需要更长的音频或计时编排，首发先不做；`relax_data.py` 留位置，二期再加。
- **2048 / 数独 / 拼图 / 填色**：是「玩游戏」不是「放松一下」，容易变成新的时间黑洞；与「随时可停」冲突。
- **找错别字 / 诗词填空 / 故事接龙 / 20 问**：更像做题，或需要 LLM / 知识库；首发只做三个轻量文字游戏，这些放到二期再评估。
- **第三方嵌入的直播 / 白噪音**：不可控的广告、追踪、断流与版权；只做外链。
- **AI 现场生成冥想指导**：多一次 LLM 调用就多一次延迟、失败与越界风险；首发全部用写死的短文案。
- **任何心理测评 / 诊断式问卷**：趣味测试已明确「不是心理测评」；首页不再放第二套问卷。

## 3. 列表内容与文案

### 3.1 首发 12 项

| # | 分组 | 标题 | 描述（首页一行） | 打开后 |
|---|---|---|---|---|
| 1 | 陪伴 | 与心屿聊聊天 | 不用组织语言，说说现在就好。 | A 模式聊天 |
| 2 | 陪伴 | 给心屿一张角色卡 | 写一张卡，让一个虚构角色陪你说话。 | B 模式 gate / 建卡 / 聊天 |
| 3 | 先让身体慢一点 | 跟着呼吸 | 吸 4 秒，呼 6 秒；不想数就看着圆慢慢变大变小。 | 呼吸动画 + 开始/暂停/重来 |
| 4 | 先让身体慢一点 | 5-4-3-2-1 接地 | 看 5 样、摸 4 样、听 3 种……把注意力挪回身边。 | 一次一步，可跳过 |
| 5 | 先让身体慢一点 | 一分钟微休息 | 随机一个小动作；不想动就坐着，也算休息。 | 随机动作 + 30 秒计时 |
| 6 | 不用说话的方式 | 写下来 | 两行字，只留在这台设备的这一页。 | 两个 textarea + 撕掉 |
| 7 | 不用说话的方式 | 环境音 | 雨、风、海浪；默认不播放，点一下才开始。 | Commons 公开音频 + 音量 + 定时 |
| 8 | 不用说话的方式 | 看看别处 | 几个外面的一分钟；会离开本站。 | 5 个白名单外链 |
| 9 | 动动脑子，不费劲 | 趣味小测试 | 四个小游戏，不是心理测评；随时可以关。 | 独立测试页 |
| 10 | 动动脑子，不费劲 | 脑筋急转弯 | 想不出来也没关系，答案本来就很绕。 | 看答案 / 换一题 |
| 11 | 动动脑子，不费劲 | 猜谜语 | 一句谜面，给点提示再看答案。 | 提示 / 看答案 / 换一个 |
| 12 | 动动脑子，不费劲 | 成语接龙 | 按读音接，接不上我帮你接。 | 输入四字成语 + 帮我接一个 |

### 3.2 文案底线

- 用「可以试试」「不想做也没关系」「随时可以停」，不用「你应该」「必须」「坚持」。
- 不写「缓解焦虑」「改善睡眠」「疗愈」「治疗」「专业评估」；不承诺效果。
- 不写「你属于」「你有……倾向」；测试页继续用「这只是个小游戏」。
- 文字游戏不写「答对了 / 答错了 / 得分 / 排行榜」；看答案用「看答案」，不用「提交」。
- 首页标题不写「心理援助」「危机干预」，只写「如果你现在就需要帮助」。
- 所有页面顶部的 `DISCLAIMER` 保持不变；首页底部再放一次资源，不折叠成小字。

### 3.3 危机资源

首页底部常驻一块**不折叠**的资源区（`st.container(border=True)`，不用 `expander`），内容直接读 `resources.pick_resources("L3", [])`：

```text
如果你现在就需要帮助
全国心理援助热线：12356（24 小时，免费）
紧急求助：110 / 120
校心理中心：0571-87713518（工作日）
```

不新增第二份热线常量，避免数字漂移；`resources.py` 不动。

## 4. 交互与状态

### 4.1 `mode` 五态

```text
home       首页列表（默认；HOME_HUB=0 时不存在）
companion  A 陪伴模式
rolecard   B 角色卡模式
quiz       趣味测试独立页
relax      本地放松页（二级页面由 relax_page 决定）
```

`relax_page` 取值：`breath` / `ground` / `break` / `journal` / `sound` / `links` / `brain` / `riddle` / `idiom`。

### 4.2 导航

- `home.goto(mode, page=None)`：唯一的跳转 helper，写 `st.session_state["mode"]`，需要时写 `relax_page`，再 `st.rerun()`。
- `goto("home")` 在 `HOME_HUB=0` 时自动改去 `companion`；`goto("rolecard")` 在 `ROLECARD=0` 时自动改去 `companion`。
- 首页顶部两项必须排在最前：聊天第一、角色卡第二。
- 侧栏保留：
  - companion：`rc_to_rolecard`（B 可用时）+ `nav_home`（首页可用时）
  - rolecard：`rc_to_companion` + `nav_home`
  - quiz / relax：`nav_home`
  - home：不重复放「回首页」，只放主题选择器
- 角色卡 L3 结束页在原有「我好些了，继续吧」「重新开始」「回到陪伴模式」之外，补一个「回首页」`rc_home`。

### 4.3 状态隔离

| 状态 | 归属 | 切页 / 刷新 |
|---|---|---|
| `messages` / `turn` / `last_level` / `ever_crisis` / `levels` | A 会话 | 去首页再回来仍在；刷新即空（与现在一致） |
| `rc_*` | B 会话 | 去首页再回来仍在；刷新走 gate（与现在一致） |
| `quiz_*` | 测试页 | 离开测试页时 `reset_state()`；报告已进 `messages`，不丢 |
| `relax_*` | 放松页 | `relax_page`、`relax_ground_step`、`relax_micro_idx`、两个 journal 输入；只活在本会话 |
| `word_*` | 文字游戏 | 题目序号 / 是否看答案 / 接龙链；只活在本会话，输入不写盘、不进日志 |
| `mode` | 页面路由 | 刷新回 `home`（`HOME_HUB=0` 回 `companion`） |

**不新增任何磁盘文件。** 放松页不碰 `memory.py` / `episode_store.py` / `logger.py`；「写下来」也不碰。

## 5. 接口

### 5.1 新文件

```text
home.py
  enabled() -> bool                         # HOME_HUB != "0"
  rolecard_enabled() -> bool                # ROLECARD != "0"
  goto(mode: str, page: str | None = None) -> None
  render() -> None                          # 12 张卡 + 随便来一个 + 帮助
  pick_random() -> str                      # 九个本地 relax_page 之一

relax_data.py
  BREATH_IN_S=4 / BREATH_OUT_S=6 / BREATH_ROUNDS=5 / BREAK_SECONDS=30
  GROUNDING: tuple[tuple[str, int, str], ...]          # 看5/摸4/听3/闻2/尝1
  MICRO_ACTIONS: tuple[str, ...]
  GENTLE_LINES: tuple[str, ...]
  JOURNAL_PROMPTS: tuple[tuple[str, str], ...]
  EXTERNAL_LINKS: tuple[dict, ...]                     # title/url/host/note
  LINK_HOSTS: frozenset[str]
  safe_links() -> list[dict]                           # https + host 白名单，坏链接丢掉
  WORD_PAGES: dict[str, tuple[str, str]]               # 三个文字游戏的标题 / 一句说明

relax_ui.py
  PAGES: dict[str, tuple[str, str]]                    # 九个本地页的标题 / 一句说明
  render() -> None                                     # 读 relax_page，未知页回首页
  # 私有：_breath / _grounding / _break / _journal / _sound / _links
  # brain / riddle / idiom 委托 word_games.render(page)

word_games.py
  BRAIN_TEASERS: tuple[tuple[str, str], ...]           # 题目 / 答案
  RIDDLES: tuple[tuple[str, str, str], ...]            # 谜面 / 谜底 / 提示
  IDIOMS: tuple[tuple[str, str, str], ...]             # 成语 / 首字拼音 / 尾字拼音（无声调）
  render(page: str) -> None                            # brain / riddle / idiom
  _render_reveal_game(...)                             # 两个揭示类共用
  _render_idiom() -> None
  _clean_idiom(text: str) -> str
  _next_idiom(current: tuple[str, str, str]) -> tuple[str, str, str] | None

relax_media.py
  breath_html() -> str
  sound_html() -> str
  timer_html(seconds: int = 30) -> str
```

`relax_media` 只返回**完全自包含**的 HTML/CSS/JS 字符串，由 `streamlit.components.v1.html` 渲染；不发请求、不引用 CDN、不写 cookie。

### 5.2 `companion_ui.py`

从 `app.py` 原样搬迁，不改行为：

```text
render(sid: str) -> None        # 原 _companion
_turn(sid) -> None              # 原 _turn
_sidebar(sid) -> None           # 原 _sidebar
_clear(sid) -> None             # 原 _clear
DEFAULT_PERSONA / NET_HINT
```

`app.py` 保留：`_bridge_secrets` / `get_session_id` / `_config_gate` / `DISCLAIMER` / `main` / 侧栏导航。`main` 只做：

```python
mode = st.session_state.get("mode") or ("home" if home.enabled() else "companion")
# 非法 / 被开关关掉的 mode 回落 companion
if mode == "home": home.render()
elif mode == "companion": companion_ui.render(get_session_id())
elif mode == "rolecard": rolecard_ui.render()
elif mode == "quiz": quiz_ui.render_page(get_session_id())
elif mode == "relax": relax_ui.render()
```

### 5.3 既有文件的最小改动

```text
quiz_ui.py
  render(sid, standalone=False)          # 原签名兼容
  render_page(sid) -> None               # 独立页：声明 + 回首页 + 聊一聊
  _close / _declaration / _done 加 standalone 分支

rolecard_ui.py
  render_ended 加 rc_home；import home

onboard.py
  首屏 5 题多一个条件：messages 里已有 quiz 报告时不出现（只改显示，不改写入）

app.py
  _SECRET_KEYS 加 HOME_HUB
  去掉 A 页函数，改路由与侧栏导航

tests/pipeline.py
  Chat(..., enter=True)：初始在 home 时自动点 home_chat
  click(key) / messages 容错；app_source / pipeline_source 拼上 companion_ui.py
```

**不动**：`orchestrator.py` / `guardian.py` / `coordinator.py` / `memory.py` / `agent.py` / `roles.py` / `resources.py` / `contract_check.py` 的签名与判定。

## 6. 六个放松页与趣味测试的细节

### 6.1 跟着呼吸（`breath`）

- 4 秒吸、6 秒呼，5 轮（约 50 秒）；圆随呼吸放大 / 缩小。
- 默认静止，按钮「开始」；运行中「暂停」；「重来」回到第一轮。
- 页面内显示「第 N / 5 轮」「吸气 / 呼气」；结束后「这一轮做完了，想继续就再点一次开始」。
- `prefers-reduced-motion: reduce` 时不放大缩小，只保留文字与计时。
- 不自动开始、不发声、不写状态到磁盘。

### 6.2 5-4-3-2-1 接地（`ground`）

- 一次只显示一步：看 5 样 → 摸 4 样 → 听 3 种 → 闻 2 种 → 尝 1 种。
- 按钮「下一步」/「跳过这一步」/「从头开始」；步骤进度条。
- 不要求输入，不记录用户写了什么；最后一句「没感觉也没关系，至少你把注意力挪开了一会儿」。

### 6.3 一分钟微休息（`break`）

- 从 `MICRO_ACTIONS` 里按 `relax_micro_idx` 取一条；「换一个」循环下一条。
- 配一句 `GENTLE_LINES`，再挂一个 30 秒倒计时组件（`timer_html(30)`）。
- 文案「不想动也没关系，坐着也算休息」。

### 6.4 写下来（`journal`）

- 两个 `st.text_area`：
  - 「现在最占心思的一件事」
  - 「今天我能控制的一件小事」
- 说明：「不用写完整，几个词也行。只留在这台设备的这一页；不会发给心屿，也不会写进记忆。点『撕掉』就清空。」
- 只有「撕掉这几行」按钮；没有「保存」、没有下载、没有提交。
- 实现上只读写 `st.session_state`，**不 import** `memory` / `episode_store` / `logger`。

### 6.5 环境音（`sound`）

- 三种：雨 / 风 / 海浪；按钮切换，默认静音。
- 用 Wikimedia Commons 的三段公开音频，`<audio loop preload="none">`；第一次点击才 `play()`，1.5 秒淡入；「停止」0.5 秒淡出。
- 音量滑杆 0–100；定时 5 / 10 / 15 分钟 / 不限时，到点自动停。
- 音频 URL 写死在 `relax_media.py`，不接收用户 URL、不拼查询参数；服务端不替用户下载音频，浏览器直接向 Commons 取。
- 来源与许可写在页面上：雨 / 海浪 Public domain（雨作者 ezwa），风 CC BY-SA 4.0，均来自 Wikimedia Commons；加载失败显示「这段声音没加载出来，换一个试试」。
- 没有任何 `autoplay`；刷新页面不会自动响。

### 6.6 看看别处（`links`）

- 首发 5 个，全部 `https` 且 host 在 `LINK_HOSTS`：
  - WindowSwap（`window-swap.com`）
  - 古诗文网（`gushiwen.cn`）
  - PixelThoughts（`pixelthoughts.co`）
  - Weave Silk（`weavesilk.com`）
  - AutoDraw（`autodraw.com`）
- 2026-11-18 按用户反馈，原 explore.org 与 Google Arts & Culture 加载慢，已换成古诗文网与 PixelThoughts；仍是 5 个白名单外链。
- 每个用 `st.link_button`，新窗口；下面写「将离开本站；对方站点可能有广告或推荐」。
- `safe_links()` 先过 `web.is_safe_url` 再比对 host；坏链接直接不渲染，不给「打不开」的假按钮。
- 不嵌 iframe、不抓取对方内容、不显示对方页面的截图。

### 6.7 趣味小测试（`quiz`）

- 首页点进来是独立页：标题 + 一句「四个小游戏，不是心理测评」+ 原 P13 的声明 / 选题 / 答题 / 结果。
- 报告仍由 `quiz.report` 生成、仍进 `messages`、仍带 `quiz` 标记、仍不算一轮。
- 结果页多一个「聊一聊这个结果」：把 `pending_turn="帮我分析分析这个结果"`、`mode="companion"` 后 `reset_state()`；companion 自动跑一轮，再保留输入框；报告已在 `messages` 里，可直接接着聊。
- 「回首页」「先不测」「不测了」「关掉」在独立页都回首页并 `reset_state()`；不会一关又弹回声明。
- 从结果页点「聊一聊」进 companion 时，若 `messages` 里已有 `quiz` 报告，`onboard.render` 不再弹 5 题（多一个「已有 quiz 报告」条件）；避免做完 12 题又被问 5 题。
- 侧栏 `quiz_entry` 保留，旧测试与老用户路径不变。

### 6.8 三个文字小游戏（`brain` / `riddle` / `idiom`）

- 三页都只读本地词库，不调用 LLM、不判级、不写盘、不进 `messages` / `trace`。
- 脑筋急转弯 / 猜谜语：揭示类，不要求输入，不判对错；「换一题」循环，不抓网络。
- 成语接龙：按读音接（同字或同音，声调不计）；输入只在本会话；「帮我接一个」由代码补；没有计时、分数、排行榜。
- 具体数据、校验文案与测试见 §14。

## 7. 专项规则

### 7.1 安全

- 首页、所有放松页和三个文字游戏都不调用 LLM、不判级；聊天仍走 `orchestrator.safe_run`，L3 仍出资源卡。
- 首页底部热线来自 `resources.pick_resources("L3", [])`；不新增、不改数字。
- 呼吸 / 环境音 / 微休息都写明「不舒服就停」；不写疗效。
- 外链只走白名单；不把用户 URL 拼进页面，不让模型生成链接。
- 环境音默认静音；动画默认不动；`prefers-reduced-motion` 有降级。

### 7.2 数据与隐私

- 放松页不写 `data/memory`、不写 `data/logs`、不进 `trace`、不进 prompt。
- 「写下来」与成语接龙的输入只活在本会话；不提供导出 / 云同步 / 跨刷新。
- 测试结果仍只进 `data/memory/quiz/<sid>.json`；清空对话一起删（沿用 P13）。
- 外链不携带会话 id、不带用户输入；`st.link_button` 只拿固定 URL。

### 7.3 无障碍与移动端

- 所有按钮有文字标签，不靠图标；颜色不用红色，不闪烁，动画可暂停。
- 呼吸圆在 reduced-motion 下不缩放；文字仍更新。
- 列表卡片在 390px 宽度下按钮不被裁切；`st.columns([0.76, 0.24])`，长文案换行。
- 键盘 Tab 能依次到每张卡；回车可触发。

### 7.4 不加依赖

- 只用现有 `streamlit`（含 `streamlit.components.v1`）、标准库。
- `requirements.txt` 不改；不引入 `requests`、`numpy`、`pydub`、任何音频库。
- `relax_media` 的 JS 不引用 CDN。

## 8. 改动清单与行数预算

| 文件 | 现状 | 预计 | 说明 |
|---|---:|---:|---|
| `app.py` | 234 | ≤120 | 只留 secrets / sid / config gate / 路由 / 侧栏导航 |
| `companion_ui.py` | 新 | ≤150 | 原 `_companion` / `_turn` / `_sidebar` / `_clear` 搬迁 |
| `home.py` | 新 | ≤170 | 12 张卡 + 随机 + 帮助 + `goto` |
| `relax_data.py` | 新 | ≤180 | 文案 / 步骤 / 动作 / 外链白名单 / 文字游戏元数据 |
| `relax_ui.py` | 新 | ≤320 | 六个放松页 + 三个文字页委托 + 未知页回退 |
| `word_games.py` | 新 | ≤330 | 三个文字游戏的数据 / 揭示 / 接龙校验 |
| `relax_media.py` | 新 | ≤260 | 呼吸 / 环境音 / 倒计时三段自包含 HTML |
| `quiz_ui.py` | 132 | ≤180 | `standalone` 分支 + 独立页 + 聊一聊 |
| `rolecard_ui.py` | 263 | ≤275 | 只加 `rc_home` |
| `onboard.py` | 133 | ≤135 | 已有 quiz 报告时不弹 5 题 |
| `tests/pipeline.py` | 97 | ≤125 | 自动进 companion + source 拼接 |
| `tests/test_home.py` | 新 | ~8 条 | 首页路由 / 开关 / 帮助 |
| `tests/test_relax.py` | 新 | ~10 条 | 六页交互 / 数据不落盘 |
| `tests/test_relax_media.py` | 新 | ~4 条 | HTML 静态断言 |
| `tests/test_word_games.py` | 新 | ~9 条 | 揭示 / 提示 / 接龙 / 数据完整性 / 不落盘 |

所有 `.py` 仍 ≤350 行、单函数 ≤40 行；超了先拆函数，不删注释凑数。

## 9. 测试

### 9.1 旧测试迁移

- `tests/pipeline.Chat()`：首次 `run()` 若 `mode == "home"`，自动点 `home_chat` 进 companion；这样 `test_flow` / `test_onboard` / `test_quiz_ui` / `test_rolecard_app` 的现有用法基本不动。
- `Chat(enter=False)`：留给首页测试，停在 home，不自动进聊天。
- `app_source()` 拼 `app.py + companion_ui.py`；`pipeline_source()` 再拼 `orchestrator.py`。`test_turn` 的「先落库再渲染」和 `test_fault` 的兜底句继续可查。
- `test_rolecard_app` 的「默认 mode」断言改成「夹具进入后是 companion」；新增 `Chat(enter=False)` 断言默认是 home。

### 9.2 新增测试

`tests/test_home.py`（8）：

1. 默认 `mode=home`，没有 `chat_input`，12 张卡 key 齐全。
2. 点聊天 → `mode=companion`，出现输入框。
3. 点角色卡 → gate，未勾选不出现聊天。
4. 点呼吸 → `mode=relax` / `relax_page=breath`；「回首页」回 home。
5. 点测试 → `mode=quiz`，声明页，没有 `chat_input`；`quiz_page_home` 回首页。
6. 「随便来一个」落在九个本地 relax 页之一。
7. 首页常驻 12356 / 0571-87713518。
8. `HOME_HUB=0` 时默认 companion，首页卡不出现。

`tests/test_relax.py`（13）：

1. 呼吸页无 `chat_input`，能回首页。
2. 接地下一步 / 从头来改 `relax_ground_step`。
3. 微休息「换一个」换动作。
4. 写下来输入在重跑后还在；「撕掉」清空。
5. 写下来的文字不进 `messages`、不建 `last_trace`。
6. 环境音页默认静的，页面有 Wikimedia Commons 署名。
7. 外链全部 https + host 白名单；页面有「将离开本站」。
8. 未知 `relax_page` 不崩，回落到呼吸页。
9–13. 六个放松页逐个断言无 `chat_input`、不建 `messages` / `last_trace`（参数化 6 条，含呼吸）。

`tests/test_relax_media.py`（4）：

1. 呼吸 HTML 默认 `animation-play-state: paused`，含 `prefers-reduced-motion` 与 4/6 秒文案。
2. 环境音 HTML 有 3 个 `<audio preload="none">`、三个 Commons URL、无 `autoplay`、有署名。
3. 环境音有淡入 / 音量 / 5·10·15 分钟定时 / 加载失败提示。
4. 倒计时 HTML 有「开始 30 秒」，`setInterval` 只在点击回调里，页面加载不自动开始。

`tests/test_quiz_ui.py` 追加（1）：

1. 首页点测试 → 独立页答完 → 点「聊一聊」→ `mode=companion`、`pending_turn` 已消费、报告仍在 `messages`、输入框回来。

`tests/test_word_games.py`（11）：

1. 三个题库条数 30 / 30 / 120，题目形状正确。
2. 成语都是 4 个汉字，首尾拼音是无声调 ASCII。
3. `BY_TEXT` / `STARTS` 索引与 `IDIOMS` 一致。
4. `_clean_idiom` 去空格、拒标点 / 长度不对。
5. `_next_idiom` 按尾音找、排除自身。
6. 死路返回 `None`。
7. 脑筋急转弯「看答案」出现答案、「换一题」换题。
8. 猜谜语先提示后答案。
9. 合法成语（同音）接上并推进当前成语。
10. 字数不对给提示，不写 `messages`。
11. 死路点「帮我接一个」提示换开头。

实测：**430 + 8 + 13 + 4 + 1 + 11 = 467 passed**。新增测试不联网，LLM 一律 MOCK。

## 10. 验证

### 10.1 自动

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe contract_check.py
.\.venv\Scripts\python.exe metrics.py
```

期望：pytest 全绿；契约 11/11 + 5/5 + 20/20；四指标 10/10、0/20、12/12、10/10（P17 不碰 A 管线，数字应不变）。

### 10.2 人工

- [ ] 桌面 1440×900 与手机 390×844：12 张卡不裁切，按钮可点。
- [ ] 首屏没有 `chat_input`；点聊天才出现输入框与 5 题。
- [ ] 每个放松页都能「回首页」，再进聊天，历史还在。
- [ ] 呼吸：默认不动；开始后 4 秒 / 6 秒节奏；暂停后停住；重来归零；DevTools 模拟 reduced-motion 后圆不缩放、文字仍走。
- [ ] 环境音：进页静音；点「雨」才响；音量可调；定时到点停；「停止」立即停；刷新不自动响；断网/加载失败显示「没加载出来，换一个」，页面不崩。
- [ ] 外链：新窗口打开；有「将离开本站」；不嵌 iframe；断网时按钮仍在但不假装能打开。
- [ ] 写下来：输入后切首页再回来还在；点「撕掉」清空；`data/memory` 与 `data/logs` 里搜不到输入文字。
- [ ] 测试独立页：声明 → 选题 → 答题 → 结果 → 聊一聊；回首页不会一关又弹声明。
- [ ] 文字游戏：脑筋急转弯 / 猜谜语看答案后能换题；成语接龙同字能接、同音不同字能接、声调不同不拦；点「帮我接一个」不卡死；全程无倒计时 / 分数 / 排行榜。
- [ ] 文字游戏断网也能玩；页面不请求网络，`data/memory` 与 `data/logs` 里没有接龙输入。
- [ ] 断网 + MOCK：首页、呼吸 / 接地 / 微休息 / 写下来 / 外链、九个本地页、测试页都能开；环境音只影响声音，不影响页面；聊天 L3 仍出资源卡。
- [ ] 侧栏「回首页」「角色卡模式」「返回陪伴模式」按钮不打架；`ROLECARD=0` / `HOME_HUB=0` 各试一次。

证据：`docs/evidence/P17-home-2026-11-18.md`（测试输出、行数、人工勾选、两张开机截图）。

## 11. 实施顺序

严格按六步，每步可单独回滚：

| 步骤 | 做什么 | 出口 |
|---|---|---|
| **P17a** | 抽 `companion_ui.py`，`app.py` 变路由；首页只放两张陪伴卡；`HOME_HUB` 开关；`Chat()` 自动进 companion | 旧测试全绿；首页默认、可进聊天；430 + 3 左右 |
| **P17b** | `relax_data.py` + `relax_ui.py` 的接地 / 微休息 / 写下来 / 外链；首页六张放松卡先接这四个 | 四个页面可用；写下来不落盘；+8 左右 |
| **P17c** | `relax_media.py` 呼吸 + 环境音 + 倒计时；接 `breath` / `sound` | 默认静音 / 默认不动；暂停与定时可用；+6 左右 |
| **P17d** | `quiz_ui.render_page` + 首页测试卡 + 聊一聊；侧栏入口保留 | 独立页完整走通；旧侧栏测试仍绿；+2 |
| **P17e** | `word_games.py` + 首页三张文字卡；脑筋急转弯 / 猜谜语 / 成语接龙；按读音接龙 | 三页可用、无 LLM / 无联网 / 无计时；输入不落盘；+9 左右 |
| **P17f** | 全量回归 + 人工清单 + 行数 + 证据 + 更新 `CLAUDE.md` §2.2/§4 | 467 / 契约 / 四指标 / 证据归档 |

P17a 不写任何放松工具；P17b 不碰音频；P17c 不碰测试；P17d 不碰聊天；P17e 不碰聊天与安全链路。任何一步失败只回滚该步。

## 12. 失败与回滚

| 现象 | 处理 |
|---|---|
| 首页路由把聊天弄丢 | `HOME_HUB=0`，默认回 companion；首页代码留着不执行 |
| `components.html` 在某些环境不渲染 | 呼吸 / 环境音卡片先隐藏，只留文字版接地 / 微休息 / 写下来 / 外链；聊天与测试不受影响 |
| Commons 音频加载失败 | 显示「这段声音没加载出来，换一个试试」；不自动重试、不弹权限；其它页不受影响 |
| 外链打不开 | 按钮仍在但文案说明「将离开本站」；`safe_links()` 只过滤明显坏 URL，不做可用性探测 |
| 测试独立页状态卡住 | 点「回首页」时 `reset_state()`；再进重新看声明 |
| 写下来被误写盘 | 代码层不 import 写盘模块；测试断言 `data/memory` / `data/logs` 无输入文字 |
| 文字游戏拼音表写错 | 同字仍可直接接（代码先判同字）；测试对每条拼音做格式断言，错表在测试里红，不在运行时猜 |
| 成语接龙走进死路 | 当前读音没有可接成语时显示「换一个开头吧」，不把用户卡死在输入框 |
| 行数超预算 | 先拆私有函数，再拆文件；不许删注释或空行凑数 |

**无数据迁移**：不新增磁盘格式；`data/memory/quiz/` 与现有记忆文件不变。回滚不需要清数据。

## 13. 出口

- [ ] 首屏默认是列表，顶部依次是「与心屿聊聊天」「给心屿一张角色卡」
- [ ] 六个放松入口 + 三个文字游戏 + 趣味测试入口都能打开、能回首页
- [ ] 首页与所有放松 / 文字页不调用 LLM、不判级、不写记忆 / 日志 / trace
- [ ] 呼吸默认不动、可暂停；环境音默认静音、可调音量、可定时；reduced-motion 有降级
- [ ] 外链全部 https + 白名单 + 新窗口 + 「将离开本站」，无 iframe
- [ ] 写下来只活在本会话，清空即清；测试结果仍只进 `quiz_store`
- [ ] 成语接龙同字 / 同音都能接，声调不计；无计时、无分数；输入不落盘
- [ ] 文字游戏离线可玩，运行时不请求网络；资源不够时用开发期补库，不在页面里抓网页
- [ ] 聊天 / 角色卡 / 测试的原有行为不变；L3 资源卡仍出
- [ ] `HOME_HUB=0` 与 `ROLECARD=0` 都能一键回退
- [ ] `pytest` 全绿（467）、契约 11+5+20、四指标不变
- [ ] 证据归档到 `docs/evidence/P17-home-2026-11-18.md`

## 14. 文字小游戏（2026-11-18 已拍板：D17-9/10/11）

用户 2026-11-18 拍板：3 个都加、独立卡片、成语接龙按读音。保持和现有放松页同样的边界：**本地词库、无 LLM、无计时、无排名、无对错评分**；一次 1–3 分钟，随时回首页。

> 已按 12 项执行：§1/§3 加 3 个文字入口，§4 的 `relax_page` 增加 `brain` / `riddle` / `idiom`，§8/§9/§11 的预算与测试数已上浮。若以后要砍，只删这三页，不影响原 9 项。

### 14.1 首页怎么放

「换个方式待一会儿」改名「动动脑子，不费劲」，放 4 项：

| # | 标题 | 描述（首页一行） | 打开后 |
|---|---|---|---|
| 9 | 趣味小测试 | 四个小游戏，不是心理测评；随时可以关。 | 原独立测试页 |
| 10 | 脑筋急转弯 | 想不出来也没关系，答案本来就很绕。 | 看答案 / 换一题 |
| 11 | 猜谜语 | 一句谜面，给点提示再看答案。 | 提示 / 看答案 / 换一个 |
| 12 | 成语接龙 | 按读音接，接不上我帮你接。 | 输入四字成语 + 帮我接一个 |

「随便来一个」的候选从 6 个原放松页扩到 9 个（6 个原放松页 + 3 个文字游戏），仍不抽聊天 / 角色卡 / 测试。

### 14.2 三个页面

**脑筋急转弯（`brain`）**

- 数据：20–30 条 `(题目, 答案)`；只用经典、答案唯一、不过分依赖方言的题。
- 交互：题目卡片 +「看答案」/「换一题」；不要求输入，不打分，不判断对错。
- 看答案后只显示答案和一句「想不出来也没关系，这类题本来就很绕」。
- 状态：`word_brain_idx` / `word_brain_reveal`；换题时重置 reveal。
- 内容避开死亡、自伤、疾病、暴力、歧视、政治、宗教、恐怖；不写「答对了/答错了」。

**猜谜语（`riddle`）**

- 数据：20–30 条 `(谜面, 谜底, 提示)`；提示只给类别或一个字，不直接给答案。
- 交互：「给点提示」→「看答案」→「换一个」；同样不输入、不打分。
- 状态：`word_riddle_idx` / `word_riddle_hint` / `word_riddle_reveal`。
- 谜底要唯一；避免「棺材 / 鬼 / 死」这类会造成不适的谜面。

**成语接龙（`idiom`）**

- 词库：120–150 条常见四字成语，`IDIOMS` 每条是 `(成语, 首字拼音, 尾字拼音)`；拼音**无声调**、ASCII 小写，`ü` 写 `v`。只收中性或偏积极的，避开死亡、疾病、暴力、贬义。多音字按成语里的读法记。
- 规则：按**读音**接——候选首字与上一个成语尾字**同字或同音**（声母 + 韵母相同；声调不计）都算；只接受词库内成语；输入 4 个字，`max_chars=8`，用 `st.form(clear_on_submit=True)`。
- 为什么把拼音写进词库：不引入 `pypinyin` 之类的新依赖；每条成语只记首尾两个音节，测试能直接查；用户输入的成语必须已在词库，才不会出现「不会算拼音」的第三种情况。
- 反馈：
  - 不是 4 字 →「接龙要四个字，再试一个？」
  - 读音不对 →「上一个成语最后一个字是「海」（hai），要接「hai」或同音字开头的成语」
  - 词库没有 →「这个我还没收进小本子；可以换一个，或点『帮我接一个』」
  - 同字接上 → 追加到链，显示「这一串已经有 N 个了」
  - 同音不同字接上 → 追加，补一句「同音也算，接上了」
- 不会接：点「帮我接一个」，由代码从词库里挑一个合法成语接上；点「换一个开头」重置。没有倒计时、没有分数、没有排行榜。
- 状态：`word_idiom_chain` / `word_idiom_start` / `word_idiom_msg`；只活在本会话，不写盘、不进日志、不进记忆。
- 死路：当前读音没有可接成语时，直接显示「这个读音我这边接不下去了，换一个开头吧」，不把用户卡死。

### 14.3 实现

新增 `word_games.py`（≤330 行）：

```text
BRAIN_TEASERS: tuple[tuple[str, str], ...]
RIDDLES: tuple[tuple[str, str, str], ...]
IDIOMS: tuple[tuple[str, str, str], ...]  # (成语, 首字拼音, 尾字拼音)
BY_TEXT: dict[str, tuple[str, str, str]]  # 成语 -> 三元组，用户输入必须命中
STARTS: dict[str, tuple[tuple[str, str, str], ...]]  # 首字拼音 -> 候选
render(page: str) -> None               # brain / riddle / idiom
_render_reveal_game(...)                # 脑筋急转弯 / 猜谜语共用
_render_idiom() -> None
_clean_idiom(text: str) -> str
_next_idiom(current: tuple[str, str, str]) -> tuple[str, str, str] | None
```

- `relax_ui.PAGES` 增加 3 个页面；`render()` 碰到 `brain` / `riddle` / `idiom` 时委托 `word_games.render(page)`，`relax_ui.py` 不再自己长三套逻辑。
- `home.py` 增加 3 张卡；标题与描述放在 `relax_data.WORD_PAGES`，避免首页和页面各写一份。
- 不 import `agent` / `orchestrator` / `guardian` / `memory` / `logger`；只用 `streamlit` 与标准库。
- 用户输入只放 `st.session_state`；不写 `data/memory`、`data/logs`、`messages`、`trace`。
- 词库构建 `BY_TEXT` / `STARTS` 两个映射；去重与「每条 4 个汉字」由 `test_word_games.py` 直接断言，运行时不做静默跳过——内容表写错就在测试里红。
- `_next_idiom(current)` 先找同字开头（`成语[-1] == 候选[0]`），再找尾字拼音相同（`current[2] == 候选[1]`）；都没有返回 `None`，由页面显示换开头。

### 14.4 测试与预算

`tests/test_word_games.py`（9 条）：

1. 脑筋急转弯：无 `chat_input`、不调用 LLM；「看答案」出现答案，「换一题」换题并收起答案。
2. 猜谜语：先提示后答案；「换一个」重置提示与答案。
3. 成语接龙：字数不对、读音不对各给对应提示。
4. 同字能接；不同字但同音（如 `ren` 接 `ren`）也能接；声调不同不拦。
5. 合法成语接上后链变长，计数增加；「帮我接一个」能接上。
6. 词库没有的成语给友好提示，不判用户「错」；「换一个开头」重置链。
7. 数据完整性：成语都是 4 字、无重复、≥120 条；拼音字段是无声调 ASCII 小写；三道游戏的数据都不含敏感词表中的词。
8. 三个页面都不写盘、不写日志、不进 `messages`；源码不 import 对话 / 安全模块。
9. 文字游戏不联网：即使 `ALLOW_WEB=1`，页面也不调用 `web.search`。

预算：`word_games.py` ≤330；`relax_ui.py` 从 ≤300 调到 ≤320；`home.py` 从 ≤150 调到 ≤170；`relax_data.py` 从 ≤160 调到 ≤180。测试预计 **430 + 24 + 9 ≈ 463 passed**。

### 14.5 实施位置

D17-9 已通过，在 §11 的 P17d（测试独立页）之后插入 **P17e 文字小游戏**，原 P17e 全量回归顺延为 **P17f**：

```text
P17a 路由 / 首页 / companion_ui
P17b 呼吸 / 接地 / 微休息
P17c 写下来 / 环境音
P17d 外链 / 测试独立页
P17e 脑筋急转弯 / 猜谜语 / 成语接龙
P17f 全量回归 / 人工 / 证据
```

### 14.6 其他建议与取舍

- **找错别字 / 诗词填空**：文本类，但更像「做题」，容易把放松页变成考试；首发不做，最多放到二期。
- **一句话故事接龙**：需要另一个「接话的人」；要么调用 LLM（违反放松页不调模型的边界），要么退化成写下来；不做。
- **冷笑话 / 温柔提示**：微休息页已有 `GENTLE_LINES`，不单独开页。
- **文字版 20 问**：需要知识库和决策树，且容易变成「AI 猜你」，与「不评判」的基调冲突；不做。

### 14.7 资源不足与联网

- 首发目标：30 条脑筋急转弯、30 条谜语、120–150 条成语；每条都人工过一遍，确保不吓人、不贬低、不涉及疾病/死亡/暴力。
- 资源不够时，**开发期**用 `web.search` 找候选，核对谜底、成语写法和拼音，人工过审后写进 `word_games.py`；不在页面运行时抓网页。
- 成品**运行时不自动联网**：断网也能玩；避免不可信网页、广告、版权和「答案每次不一样」。`test_word_games.py` 断言即使 `ALLOW_WEB=1` 页面也不调用 `web.search`。
- 如果你要的是「用户点开时实时检索补题」，那要另加 `WORD_GAMES_WEB` 开关（默认关）、只查白名单、答案仍以本地词库为准；这会增加延迟和不可信内容，建议二期再做。

## 15. 拍板状态

### 15.1 已拍板（2026-11-18）

| 编号 | 问题 | 结论 |
|---|---|---|
| **D17-9** | 是否加 3 个文字小游戏？ | 已拍板：3 个都加——脑筋急转弯 / 猜谜语 / 成语接龙 |
| **D17-10** | 成语接龙按字还是按音？ | 已拍板：按读音；同字或同音都算，声调不计 |
| **D17-11** | 三个游戏独立卡片还是合成一页？ | 已拍板：独立卡片，放「动动脑子，不费劲」组 |

> 基础设计 D17-6/7/8 已在 §2 定稿：外链只 `st.link_button`、放松页不调对话 / 安全链路、抽 `companion_ui.py`；它们不在本轮待拍板里，避免和文字游戏的编号混在一起。

### 15.2 仍需拍板

| 编号 | 问题 | 我的建议 |
|---|---|---|
| **D17-1** | 首发就做这 12 项，还是先做原 9 项、文字游戏放二期？ | 12 项一起做；六个放松工具都很薄，文字游戏也只读本地词库，拆开反而多轮联调 |
| **D17-2** | 环境音用 WebAudio 合成，还是放音频文件 / 外链？ | 用户拍板：上网搜集音频后调用。落地为 Wikimedia Commons 公开音频，浏览器点击后加载；本机 TLS 下载失败，因此不打包文件；页面标来源/许可与失败提示 |
| **D17-3** | 「写下来」要不要落盘？ | 不落盘，只放会话；要留存就以后单独做「导出」，不能默认写原文 |
| **D17-4** | 测试做独立页，还是点进去直接跳聊天？ | 独立页 + 「聊一聊这个结果」；侧栏入口保留 |
| **D17-5** | 默认首页，还是加开关默认关闭？ | 默认首页 + `HOME_HUB=0` 回退；上线前用开关做一次对照 |

拍板 D17-1~5 后按 §11 从 P17a 开始；未拍板前不改任何代码。
