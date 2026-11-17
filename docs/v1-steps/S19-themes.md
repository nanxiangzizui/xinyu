# S19 · 三套主题（樱花 / 抹茶 / 落日）

| 项 | 内容 |
|---|---|
| 步骤 | S19 / 26 |
| 阶段 | W3 |
| 工时 | 2 人时（P4） |
| 风险 | 低——纯样式，挂了不影响功能 |
| 依赖 | S18 |
| 回滚 | `git checkout -- theme.py app.py` |

## 1 这一步做什么

把五套主题砍成**三套**（樱花 `sakura` / 抹茶 `matcha` / 落日 `sunset`），用 CSS 变量注入，侧栏可切换。

产出：`theme.py` + 侧栏选择器 + 1 条测试（三个主题 key 齐全）。

**为什么是 3 套不是 5 套**：多两套换不来分数，换来的是四个小时和两处色盲不友好。落日一套已覆盖深色需求。

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 注入 | `st.markdown("<style>...", unsafe_allow_html=True)` | 只注一次，别每轮注 |
| 变量 | CSS 自定义属性 `--xy-*` | 前缀防冲突 |
| 选择 | `st.radio` 放侧栏 | 存 session_state |

## 3 前置检查

```powershell
pytest -q        # 61 passed
```

## 4 硬要求

1. 三个主题 **只改颜色与圆角**，不改布局、不改字号。
2. 对比度：正文与背景 ≥ 4.5:1（用在线对比度检查器验一次，截图存档）。
3. 配色变量名统一 `--xy-{bg,surface,text,accent,border}`。
4. 不引入外部字体与 CDN（离线演示要能跑）。

## 5 执行步骤

### 5.1 三套调色板

```python
THEMES = {
    "sakura": {"bg": "#FFF7F8", "surface": "#FFE9EC", "text": "#3D3230", "accent": "#F7A8B8", "border": "#F3CBD3"},
    "matcha": {"bg": "#F7FAF5", "surface": "#E8F0E3", "text": "#2F3A2C", "accent": "#A8C69F", "border": "#CFE0C6"},
    "sunset": {"bg": "#FFF9F4", "surface": "#FBEEE6", "text": "#3D3230", "accent": "#FF9E6B", "border": "#F6D3BE"},
}
```

### 5.2 注入

```python
def inject_theme(key: str) -> None:
    """注入一次主题 CSS。只改颜色与圆角。"""
    c = THEMES.get(key, THEMES["sakura"])
    st.markdown(f"""<style>
    :root {{ --xy-bg:{c['bg']}; --xy-surface:{c['surface']}; --xy-text:{c['text']};
             --xy-accent:{c['accent']}; --xy-border:{c['border']}; }}
    .stApp {{ background: var(--xy-bg); color: var(--xy-text); }}
    [data-testid="stChatMessage"] {{ background: var(--xy-surface); border-radius: 16px; }}
    </style>""", unsafe_allow_html=True)
```

`st.markdown` 的字符串里**不要**出现三反引号，也别写 markdown 围栏。

### 5.3 侧栏选择

```python
key = st.sidebar.radio("配色", ["sakura", "matcha", "sunset"], index=0,
                       format_func={"sakura": "樱花", "matcha": "抹茶", "sunset": "落日"}.get)
inject_theme(key)
```

## 6 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `pytest -q` | 62 passed |
| 2 | 三套各截一张图 | 存 `docs/evidence/theme-*.png` |
| 3 | 对比度检查 | 三套正文 ≥ 4.5:1 |
| 4 | 断网运行 | 样式正常（无 CDN） |

## 7 回滚

```powershell
git checkout -- theme.py app.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 样式不生效 | `unsafe_allow_html` 没开 | 加上 |
| 侧栏也变色了 | 选择器太宽 | 只改 `.stApp` 与消息气泡 |
| 文字看不清 | accent 色当了正文色 | 正文只用 text 色 |
| 切主题要刷新 | 注入在 rerun 之前 | 放在页面最上方 |

## 9 出口清单

- [ ] 62 passed
- [ ] 三套截图 + 对比度截图
- [ ] 断网可用
- [ ] 只改颜色与圆角

## 10 回执

```text
S19 完成：62 passed / 3 套主题 / 对比度达标
下一步：S20 mini Lorebook
```