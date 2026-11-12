# 心屿 · 迁移到新工作区说明

- 日期：2026-11-12
- 适用：把当前仓库从 `D:\deepseek harness\心理委员` 迁到一个新的 DSH / Cursor 工作区，用于“编排式单 Agent”改造
- 原则：**旧工作区不删、先冻结、可回退；新工作区从 Git 历史重建，不复制运行环境与隐私数据**

## 1. 迁移前：先冻结当前版本

在旧工作区执行：

```powershell
cd "D:\deepseek harness\心理委员"
git status --short
git log --oneline -5
git tag
```

要求：

- 当前新增的 `docs/plan-orchestrated-single-agent.md`、`docs/plan-orchestration-A.md`、本文件，先提交并 push；否则 `git clone` 不会带过去。
- `git status` 干净后再迁移。
- 确认 `v1.0` tag 已推到 origin；没有的话补一个基线 tag，例如 `v1.0-baseline`。
- 跑一遍基线：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe contract_check.py
```

期望：**132 passed**；**11/11 + 5/5 + 20/20**。不过就不要迁。

## 2. 选新工作区路径

建议：

```text
D:\xinyu-agent
```

理由：

- ASCII、无空格、路径短，减少 Windows 路径长度、venv、Streamlit、pytest 的奇怪问题；
- 旧路径含中文和空格，虽然本项目验证过能跑，但新项目没必要再赌一次。

如果必须保留中文/空格，迁移后先跑：

```powershell
py -3.11 -m streamlit hello
```

确认能起服务再继续。

## 3. 两种迁移方式

### 方式 A：从远程 clone（推荐）

前提：当前所有提交已 push。

```powershell
git clone https://github.com/nanxiangzizui/xinyu.git D:\xinyu-agent
cd D:\xinyu-agent
git switch -c agent-v2
```

优点：历史、分支、tag 干净；不会把 `.venv`、`.env`、`data/` 带过去。

### 方式 B：复制目录（远程不可用 / 还有未提交内容）

```powershell
robocopy "D:\deepseek harness\心理委员" "D:\xinyu-agent" /E `
  /XD .venv __pycache__ .pytest_cache data `
  /XF .env secrets.toml
```

说明：

- `.git` 会一起复制，历史还在；
- `data/`、`.env`、`.streamlit/secrets.toml` 不复制；
- `robocopy` 返回码 0–7 都算成功，8 以上才是失败；
- 复制后检查：

```powershell
cd D:\xinyu-agent
git status
git fsck
```

如果 `git fsck` 报错，改用方式 A 重新 clone。

## 4. 重建 Python 环境（不要复制 `.venv`）

`.venv` 里有旧路径的 `pyvenv.cfg`，复制过去会坏。必须重建：

```powershell
cd D:\xinyu-agent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -V
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

期望：Python **3.11.x**；依赖仍是 `streamlit / openai / python-dotenv / pytest`，不新增。

如果 PowerShell 不让激活，不必强求 `Activate.ps1`，直接用：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\streamlit.exe run app.py
```

## 5. 配置与密钥

### 本地 `.env`

```powershell
Copy-Item .env.example .env
```

然后手动填：

```text
LLM_API_KEY=...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
MOCK_LLM=0
```

规则：

- `.env` 永不进仓库；
- 不要把旧 `.env` 直接复制进新仓库目录；
- 新工作区建议重新填一次，避免带错 key；
- 后续网络检索的 `SEARCH_API_KEY` / `IMAGE_API_KEY` 等，等方案定了再加到 `.env.example`。

### Streamlit Cloud Secrets

线上不是读 `.env`，是读 `st.secrets`。新仓库部署时在 Streamlit Cloud 后台重新填：

```text
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
MOCK_LLM
```

本地如果要模拟线上，创建 `.streamlit/secrets.toml`，但**不要提交**。

### 数据目录

```powershell
New-Item -ItemType Directory -Force data\memory, data\logs
```

不要从旧工作区复制 `data/memory/*.json` 或 `data/logs/*.jsonl`：

- 可能含真实对话/隐私；
- 新项目要干净基线；
- 需要演示记忆时，用虚构会话重新生成。

## 6. 项目指令与技能

新工作区必须保留：

```text
.claude/CLAUDE.md                     # 项目状态与红线
.claude/skills/xinyu-dev/SKILL.md     # 开发技能
.cursor/rules/xinyu.mdc               # Cursor 常驻规则
docs/plan-orchestrated-single-agent.md
docs/plan-orchestration-A.md
```

在新工作区打开 DSH 会话后：

1. 确认 `.claude/CLAUDE.md` 被加载；
2. 重新加载 `xinyu-dev` 技能；
3. 如果用 Cursor，确认 `.cursor/rules/xinyu.mdc` 生效；
4. **不要复制 `~/.dsh` 的全局会话**；新工作区是新会话，旧会话只作参考。

## 7. 迁移后验证清单

逐条打勾：

| 检查 | 命令 | 通过标准 |
|---|---|---|
| Python 版本 | `.\.venv\Scripts\python.exe -V` | 3.11.x |
| 依赖 | `.\.venv\Scripts\python.exe -m pip list` | 没有多装框架 |
| 测试 | `.\.venv\Scripts\python.exe -m pytest -q` | 132 passed |
| 契约 | `.\.venv\Scripts\python.exe contract_check.py` | 11/11 + 5/5 + 20/20 |
| 离线启动 | `$env:MOCK_LLM="1"; .\.venv\Scripts\streamlit.exe run app.py` | 页面能开、能聊 |
| L3 离线 | MOCK 下输入“我不想活了” | 本地 `CRISIS_REPLY` + 3 张资源卡，0 LLM |
| 秘密未入库 | `git ls-files \| Select-String -Pattern '(^\|/)\.env$\|secrets\.toml\|data/memory\|data/logs'` | 无输出 |
| Git 状态 | `git status --short` | 干净 |
| 旧路径残留 | `git grep -n "deepseek harness"` | 只允许出现在迁移文档/历史里 |

再跑一遍：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe contract_check.py
```

两项都过，才算迁移完成。

## 8. Git 与远程

建议：

```powershell
cd D:\xinyu-agent
git switch -c agent-v2
git remote -v
```

- 同一仓库：新分支 `agent-v2`，不要直接改 `main`；
- 新仓库：`git remote set-url origin <新地址>`，确认 push 权限；
- tag 不要重打；`v1.0` 作为回退点保留；
- 迁移文档本身也提交，方便以后复查。

## 9. 旧工作区怎么处理

**先别删。**

- 旧工作区保留为 `v1.0` 演示备份；
- 新工作区通过测试、能演示后，再决定是否把旧目录归档；
- 演示前至少保留两份可运行副本：旧工作区 + 新工作区；
- 如果新架构翻车，直接回旧工作区，不要现场修。

## 10. 常见坑

| 坑 | 现象 | 处理 |
|---|---|---|
| 复制 `.venv` | Python 找不到、包路径错 | 删掉重建 |
| 忘记 `.env` | 首屏“未配置 LLM_API_KEY” | 重新填 `.env` 或 Secrets |
| 复制 `data/` | 带进真实对话/旧日志 | 不复制，重建空目录 |
| `git clone` 少了未提交文档 | 新工作区没有计划书 | 旧工作区先 commit + push |
| 路径含空格/中文 | Streamlit、pytest 偶发异常 | 换 ASCII 短路径，或先 `streamlit hello` 验证 |
| 旧绝对路径写死 | 构建脚本找不到文件 | `git grep "D:\\"` / `git grep "deepseek harness"` 检查 |
| 云端 Secrets 没填 | 线上报缺 Key | Streamlit Cloud 后台重填 |
| 端口占用 | `streamlit run` 起不来 | 换端口 `--server.port 8502` |
| 直接改 `main` | 出问题难回退 | 用 `agent-v2` 分支 |
| 把 `.env` 提交 | 密钥泄露 | 立即换 key，清理历史 |

## 11. 迁移完成后的第一步

1. 读 [`docs/plan-orchestrated-single-agent.md`](plan-orchestrated-single-agent.md)；
2. 按 P0 做 DeepSeek `tools` 能力探测；
3. 建 `agent-v2` 分支；
4. 先做 P1：把 `handle()` / `safe_handle()` 从 `app.py` 搬到 `orchestrator.py`，**零行为变更**；
5. 跑回 132 passed + 契约全绿，再进 P2。

## 12. 变更记录

- 2026-11-12：创建迁移说明；未移动/删除任何文件。
