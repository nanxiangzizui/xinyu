# P43 页面内部不再重复「回首页」

- 日期：2026-11-22
- 触发：用户 m00582「有些页面内部还保留了“回首页”选项，已经多余了，删除类似的“回首页”选项」，截图圈的是「写下来」页内、标题下方的 `回首页`（侧栏的 `回首页` 没有圈）。
- 范围：只删**页面内容区**里的 `回首页`，保留侧栏的全局出口。页首「← 返回上一级」负责就近退一步，侧栏「回首页」负责一步回根，两者分工不同。

## 一、改了什么

| 文件 | 位置 | 改动 |
|---|---|---|
| `relax_ui.py` | `_back()`（原 18-21 行）+ `render()` 末尾调用 | 删除；九个放松 / 文字游戏页不再在标题下画 `回首页` |
| `quiz_ui.py` | `_done()` 里的 `quiz_home`、`render_page()` 里的 `quiz_page_home` | 两处都删；独立测验页与结果页只留「聊一聊 / 再玩一个」与侧栏出口 |
| `help_pages.py` | `_back()`（原 171-177 行）+ `render()` 调用 + `home_enabled` 导入 | 删除；`HOME_HUB=0` 时不再补一个页内 `回首页`，改用页首返回键（根是陪伴模式） |
| `rolecard_ui.py` | `render_sidebar()` 里的 `rc_home` | 删除与 `app._nav` 重复的那一个；角色卡页侧栏现在只有一个 `回首页`（`home_back`） |
| `app.py` | `_nav()` 的 `home_back` | **未动**：侧栏的全局出口保留 |
| `tests/test_nav.py` | 末尾新增 | 5 条：四个页面主区无 `回首页`；角色卡页侧栏 `回首页` 只剩 `home_back` 一个 |
| `tests/test_home.py` / `tests/test_relax.py` | 原 `relax_home` / `quiz_page_home` 点击 | 改用 `nav_back` 回首页（断言的仍是“能回到首页”） |
| `tests/test_help.py` | `test_back_button_only_when_home_hub_off` | 改为 `test_help_page_uses_page_top_back_when_home_hub_off`：断言主区没有 `help_home`，点 `nav_back` 回 `companion` |

## 二、三条决定

1. **只删页面内部、不删侧栏**：用户圈的是内容区；侧栏「回首页」与页首「返回上一级」不是重复——前者一步回根，后者只退一步。删掉侧栏出口会让深页只能逐级退。
2. **`HOME_HUB=0` 不再补页内出口**：原来求助页自己补一个，是因为当时侧栏什么都不留；现在页首返回键的根页是 `companion`，点一下就回去，不需要第二个按钮。
3. **角色卡页的 `rc_home` 是重复项**：`app._nav` 在 `mode != "home"` 时已经画了 `home_back`，`render_sidebar` 又画一个 `rc_home`，同屏两个「回首页」。删 `rc_home`、留 `home_back`。

## 三、验证

```text
.\.venv\Scripts\python.exe -m pytest -q            -> 752 passed in 37.39s
.\.venv\Scripts\python.exe contract_check.py       -> 11/11 + 5/5 + 20/20
```

行数（python 计数）：`relax_ui.py` 131、`quiz_ui.py` 159、`help_pages.py` 337、`rolecard_ui.py` 307、`ui_common.py` 156、`app.py` 155、`tests/test_nav.py` 191、`tests/test_help.py` 349（贴顶，未增）、`tests/test_home.py` 81、`tests/test_relax.py` 146。

真机（`MOCK_LLM=1` + Edge headless + CDP 9225，`docs/evidence/_p43_shots.mjs`）：

| 页面 | 主区「回首页」 | 侧栏「回首页」 | 页首返回键 |
|---|---|---|---|
| 「写下来」journal | 0 | 1 | 有（top=96） |
| 求助页 self | 0 | 1 | 有（top=96） |
| 趣味小测试 | 0 | 1 | 有（top=96） |
| 角色卡模式 | 0 | 1（`home_back`） | 有（top=96） |

- 截图：`docs/evidence/P43-no-redundant-home-2026-11-22/`（01 journal / 02 help-self / 03 quiz / 04 rolecard）。
- 数值：`docs/evidence/P43-probe-2026-11-22.txt`（纯 ASCII）。
- 每页都用「← 返回上一级」回到首页后再进下一页，顺带复验 P41 的返回键。

## 四、已知限制

- 侧栏「回首页」仍在（有意保留）：若希望连它也删掉、只靠返回键逐级退，是一行改动。
- `HOME_HUB=0` 时求助页依赖页首返回键；若浏览器里还没点过任何入口（栈空），返回键回 `companion`，是设计里的兜底根。
- 独立测验结果页现在只剩「聊一聊 / 再玩一个」两个动作，出口在侧栏与页首。
- 历史探针 `docs/evidence/_p26_probe.py` 仍按旧键 `help_home` 写，重跑会失败；它是一次性证据脚本，不随运行时更新。
- 不接管浏览器后退键；刷新会清空页栈（与 P41 一致）。
