# S06 · 部署上线 + tag v0.1

| 项 | 内容 |
|---|---|
| 步骤 | S06 / 26 |
| 阶段 | W1 收尾 |
| 工时 | 3 人时（P6） |
| 风险 | **中**——涉及云端密钥，泄露要立刻换 Key |
| 依赖 | S05 |
| 回滚 | 在 Cloud 控制台 Reboot / Redeploy；或先下架 |

## 1 这一步做什么

把本机能跑的页面变成"手机热点下也能打开"的公网链接，并给 W1 收尾打 tag。

产出：

1. GitHub 仓库
2. Streamlit Cloud 上的一枚应用
3. Secrets 配好（Key 不进代码）
4. tag `v0.1`

## 2 技术栈

| 用途 | 平台/工具 | 要点 |
|---|---|---|
| 代码托管 | GitHub | 用 GitHub Desktop 推，别在命令行配 PAT |
| 部署 | Streamlit Community Cloud | 免费、连仓库、连分支 |
| 密钥 | Cloud 的 **Secrets** | TOML 格式，代码里只读 `os.getenv` |
| 版本 | git tag | `v0.1` 打在 W1 最后一次提交 |

## 3 前置检查

```powershell
pytest -q                    # 全绿
python contract_check.py     # 11/11
git status --short           # 空
git log --oneline -3
```

## 4 硬要求

1. **Key 只出现在两处**：本机 `.env`、Cloud Secrets。仓库里只有 `.env.example`。
2. 部署后**必须**用手机流量（不是校园网/家宽）打开一次——这才叫"真的在线"。
3. `requirements.txt` 里不能出现清单之外的包（Cloud 会重新解析）。
4. `data/` 在云端会丢（容器重启即空）。**这是已知限制，写进报告**；演示时同一会话别刷新、别点 Reboot。

## 5 执行步骤

### 5.1 推仓库

```powershell
git remote add origin https://github.com/<你的账号>/xinyu.git
git push -u origin main
```

推送前确认：`git ls-files | Select-String "\.env"` 只能匹配到 `.env.example`。

### 5.2 建应用

1. 打开 share.streamlit.io → New app → 选仓库、分支 `main`、入口 `app.py`
2. Advanced settings → Python version 选 **3.11**
3. Secrets 里粘：

```toml
LLM_API_KEY = "sk-..."
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
MOCK_LLM = "0"
```

4. Deploy，等 2–4 分钟

### 5.3 云端首启检查

| 检查 | 期望 |
|---|---|
| 页面能打开 | 标题 + 免责声明可见 |
| 发一句"你好" | 有回复（不是 `FALLBACK_LINE`） |
| 侧栏会话 id | 有值，刷新不变 |
| 手机流量打开 | 能开（这一步必须做） |

一直显示兜底文案 → 看 Cloud 的 `Manage app → Logs`，90% 是 `LLM_API_KEY` 没读到。

### 5.4 打 tag

```powershell
git tag -a v0.1 -m "W1: 空壳上线，10 轮不崩，记忆落盘"
git push origin v0.1
```

### 5.5 把链接写进三处

`README.md` 顶部、`CLAUDE.md` §4、群里置顶。**只写一处等于没写**，演示那天没人找得到。

## 6 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | 手机流量打开链接 | 能开、能聊 |
| 2 | 连续 10 轮 | 不崩 |
| 3 | 刷新 | 会话 id 与记忆保持（同容器内） |
| 4 | 用无痕窗口打开 | 得到**新的** session，互不污染 |
| 5 | `git tag` | 看到 v0.1 |

第 4 条证明"一人一文件"真的隔离了。

## 7 回滚

| 情况 | 动作 |
|---|---|
| 新版本报错 | Manage app → ⋮ → **Reboot**；仍坏则回滚提交后 redeploy |
| Key 泄露 | 立刻在 DeepSeek 控制台**吊销并新建**，再更新 Secrets；不要只改代码 |
| 完全打不开 | 先看 Logs 前 20 行，别急着重装 |

> 容器重启会清空 `data/memory`，这是设计限制不是 bug。演示前**不要**点 Reboot。

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError` | 依赖没写进 requirements | 本地能跑≠云端能跑，依赖只认 `requirements.txt` |
| 一直 `FALLBACK_LINE` | Secrets 没读到 Key | 变量名大小写、是否保存、是否 redeploy |
| 打开 404 | 入口文件名写错 | 必须是 `app.py` |
| 卡在 "in the oven" | 队列 | 等 5 分钟；仍不行看 Logs |
| 中文变方块 | 云端字体 | S19 统一处理字体回退 |

## 9 出口清单

- [ ] 公网链接可用（手机流量验证）
- [ ] 10 轮不崩
- [ ] 无痕窗口拿到新 session
- [ ] tag v0.1 已推
- [ ] 链接写进 README + CLAUDE.md + 群置顶
- [ ] 至少 4 人各自打开过一次

## 10 回执

```text
S06 完成：链接 ___ / 手机流量可开 / tag v0.1 / 无痕隔离验证通过
W1 结束，进 W2（S07 五张人设卡）
```
