# P41 · 全站「← 返回上一级」（分界线右侧页首）

日期：2026-11-22 ｜ 基线：724 passed（P40） → **737 passed**
触发：用户 m00002「在这个项目的每一个界面内，在我圈画的这个位置加一个按键，表示返回上一级页面。
点击后返回上一级」；截图圈的是「如果现在很危险」页顶部、侧栏分界线附近。第一版放在侧栏首位
（原侧栏顺序：配色 → 回首页 → 模型设置），用户随后 m00269「把按钮位置移到分界线右侧」，
现渲染在主区顶部、标题「心屿」之上，侧栏恢复「配色 → 回首页 → 模型设置」。

## 一、这次交付了什么

| 改动 | 文件 | 行数 |
|---|---|---|
| 页栈 + 上级判定 + 按钮渲染 | `ui_common.py:63-133`（新增 `NAV_STACK` / `NAV_LAST` / `NAV_MAX`、`nav_page` / `nav_root` / `nav_record` / `_nav_apply` / `nav_back` / `back_button`） | 60 → 133 |
| 渲染顺序：按钮是主区第一项（标题之上），配色仍回侧栏首位 | `app.py:121-133`（`mode = _current_mode()` → `nav_record()` → `back_button()` → `inject_theme(theme_picker())` → `st.title("心屿")` → `st.caption(DISCLAIMER)` → `_config_gate()` → `web.register_tools()` → `_nav()`） | 151 → 153 |
| 13 条新测试 | `tests/test_nav.py` | 117 |

按钮文案 `← 返回上一级`，`key="nav_back"`，自然宽度、主区居左（不再 `use_container_width`，
也不在侧栏里）；在栈底且已在根页（home，或 `HOME_HUB=0` 时的 companion）时 `disabled=True`，
`help` 提示「已经在最上一级」。

## 二、关键决策

- **用页栈，不用「每个 mode 写死一个上级」**。同一个页面能从不同地方进：`relax/journal`
  可以从首页进、也可以从索引页 `idx_journal` 进；角色卡从首页卡进、也能从陪伴侧栏进。
  写死父页会把其中一条路径送错（例如从索引进的「写下来」返回时被送回家，而不是索引）。
- **在 `app.main()` 里对账，不改那 12 处跳转**。`nav_record()` 比较「本帧页面签名」与
  `nav_last`，变了才把上一页压栈；签名 = `(mode, 子页)`，`help` 带 `help_page`、`relax` 带
  `relax_page`，其余 mode 子页为空。这样 `home.goto` / `help_index._enter` / `app._nav` /
  `relax_ui` / `quiz_ui` / `help_pages` / `about` / `rolecard_ui` 的 `st.rerun()` 一律自动覆盖，
  不依赖某处记得调 push。
- **返回先写 `nav_last` 再 `st.rerun()`**：否则下一帧对账会把「刚离开的页」当成新跳转压回去，
  变成前进栈。`_nav_apply()` 在切 mode 前先设子页键，并对角色卡调 `rolecard_ui.ensure_state()`，
  回卡时保留原 `rc_sid` / 会话。
- **位置从侧栏挪到主区（m00269）**：用户要「分界线右侧」。按钮改为主区第一个控件
  （`st.title` 之前渲染），并去掉 `with st.sidebar` / `use_container_width`；`layout="centered"`
  下它落在居中内容列的左缘（1360px 视口 x≈473），不是紧贴分界线，但已在主区页首。
  侧栏因此回到用户最初截图的样子（配色在第一项）。
- **旧的「回首页 / 返回陪伴模式 / 角色卡模式」全保留**：它们是显式出口（不依赖历史），
  删掉会改变已有测试与用户习惯；新按钮是「就近退一步」，两者并存。
- **栈深 `NAV_MAX=20`**：只防无限增长，不参与业务判断；栈不落盘（刷新即空，和 `mode` 同生命周期）。

## 三、验证

```text
.\.venv\Scripts\python.exe -m pytest -q          → 737 passed in 34.10s
.\.venv\Scripts\python.exe contract_check.py     → 11/11 + 5/5 + 20/20
```

新增 13 条（`tests/test_nav.py`）：

- 首页有按钮且禁用；`nav_back` 不在 `at.sidebar.button` 里（位置断言）。
- 按钮渲染在 `st.title("心屿")` 与 `theme_picker()` 之前（源码顺序断言）。
- 六个入口逐一：`home_chat`→companion、`home_rolecard`→rolecard、`home_breath`→relax、
  `home_quiz`→quiz、`home_help_self`→help、`home_about`→about，进去后可点、点完回 home 且按钮转禁用。
- 两级路径：索引 → 睡不着 → 返回索引 → 再返回 home（不是一步跳首页）。
- `about_paper` 返回 about；索引 → `idx_journal`（relax/journal）返回索引。
- 无历史时（手设 `mode=help` / 无栈）返回根页 home。
- 回角色卡保留同一个 `rc_sid`。

行数（python 计数）：`app.py` 153 / `ui_common.py` 133 / `tests/test_nav.py` 117（均 ≤350）。

## 四、浏览器验收（2026-11-22，七张截图）

真机路径：`MOCK_LLM=1` 起 Streamlit（8517）→ 无头 Edge 走 CDP（9223）→ 每步量 DOM 位置并截图；
脚本 `docs/evidence/_p41_shots.mjs`（对照 P31 的 `_p31_shots.mjs`），输出
`docs/evidence/P41-probe-2026-11-22.txt`。

| 截图 | 证明什么 |
|---|---|
| `P41-back-button-2026-11-22/01-home-back-disabled.png` | 首页：按钮在分界线右侧、标题之上，灰色禁用 |
| `02-help-self-back-enabled.png` | 「如果现在很危险」：与用户截图同页，按钮可用，位置同上 |
| `03-back-to-home.png` | 点一次回到首页，按钮重新禁用 |
| `04-index.png` / `05-sleep.png` / `06-back-to-index.png` / `07-back-home-again.png` | 两级路径：睡不着 → 返回索引（不是首页）→ 再返回首页 |

DOM 实测（`P41-probe-2026-11-22.txt`）：侧栏右边界 `sidebarRight=300`、按钮 `backLeft=473`、
`backTop=96`，`backRightOfDivider=true`、`backNearTop=true`；首页 `backDisabled=true`，
help 页 `false`，回到首页后又是 `true`。DOM 里还有一个 0×0 的同文案 button（Streamlit 的隐藏副本），
不影响渲染与点击。

## 五、已知限制

- 只做站内一页一页退；没有接管浏览器后退键（Streamlit 单页 + query 参数，接管会与 Cloud 刷新打架）。
- 栈在 `st.session_state`，刷新 / 新标签页即清空；此时按钮按「无历史」处理，直接回根页。
- `layout="centered"` 下按钮只能落在内容列左缘（x≈473），不紧贴分界线；若要贴线需改 wide 布局，
  会连带改全站内容宽度，本轮不做。
- 同一页从两条路径进入时，栈里可能连着两个相同签名（实际不会：`nav_record` 只在签名变化时压栈）。
- 栈深 20 是防御性上限，正常使用到不了；到顶时最早的条目被丢弃，不影响最近几级返回。
- `help_pages.py` 已 347/350 行，本轮未加内容；下一张静态页仍应先拆文件。
