# S01 · 环境与仓库初始化

| 项 | 内容 |
|---|---|
| 步骤 | S01 / 26 |
| 阶段 | W1 · 骨架期 |
| 工时 | 3 人时（P1 主做，P6 配合） |
| 风险 | **低**——只建目录和本机环境，没有业务逻辑 |
| 依赖 | 无 |
| 回滚 | 删 `.venv`，`git reset --hard` 到首次提交之前 |

## 1 这一步做什么

把"一台干净的 Windows 机器"变成"能跑这个项目的机器"。产出五样：

1. 仓库初始化（`git init`，分支 `main`，首次提交）
2. 目录骨架：`data/memory`、`data/logs`、`docs/evidence`、`tests`
3. 虚拟环境 `.venv`，四个依赖装好
4. `.env`（从 `.env.example` 复制），密钥只在本机
5. 验证 `.gitignore` 真的挡住了 `.env` 和 `data/*`

**不做**：不写任何 `.py` 业务代码（那是 S02 起）。

## 2 技术栈

| 用途 | 工具 | 版本要求 | 备注 |
|---|---|---|---|
| 解释器 | Python | **3.11.x** | 3.12/3.13 也能跑，但机房是 3.11，统一 |
| 隔离 | venv | 标准库 | 不用 conda，不用 poetry |
| 依赖 | pip | 任意 | 国内加 `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| 版本控制 | Git + GitHub Desktop | 任意 | 命令行与 Desktop 二选一，别混着提交 |

## 3 前置检查（三条命令，全过再往下）

```powershell
py -3.11 -V              # 期望 Python 3.11.x
git --version            # 期望 git version 2.x
pwd                      # 期望 …\心理委员
```

**本机实况（2026-11-09 已装好）**：Python **3.11.9**，位置 `C:\Users\<用户名>\AppData\Local\Programs\Python\Python311\python.exe`，用 `py -3.11` 调用。
裸 `python` 指向 **Anaconda 的 3.14.6**——所以 **不要用 `python -m venv`**，会建出 3.14 的环境。全程两条命令：建环境 `py -3.11 -m venv .venv`；之后跑东西用 `.\.venv\Scripts\python.exe`（或激活后用 `python`，激活会把它排到 PATH 最前）。

**换台机器时**（比如队友的笔记本）：`py -3.11 -V` 报错就去 python.org 装 3.11.x 并勾 Add python.exe to PATH，装完 `py -0p` 确认列表里有 `-V:3.11`。没有 3.11 的机器不许开工，否则四个人四个版本，`pip list` 对不上。

> ⚠️ 已知风险：项目路径含**中文**（心理委员）和**空格**（deepseek harness）。
> 多数情况没问题，但若出现 `ModuleNotFoundError` 或 Streamlit 静态资源 404，
> 把整个项目复制到 `D:\xinyu` 再跑一次——这是最快的排除法，别耗两小时。

## 4 硬要求

- 依赖**只能**是 `requirements.txt` 里那四个：streamlit / openai / python-dotenv / pytest。
- `.env` 永不进仓库；只提交 `.env.example`。
- 目录名全小写、无空格：`data/memory`、`data/logs`、`docs/evidence`。
- 首次提交里**不能**有 `.venv/`、`.env`、`data/` 下的任何文件。

## 5 执行步骤

### 5.1 初始化仓库

```powershell
cd "D:\deepseek harness\心理委员"
git init
git branch -M main
git status --short
```

### 5.2 建目录与占位文件

```powershell
New-Item -ItemType Directory -Force data\memory, data\logs, docs\evidence, tests | Out-Null
"# 证据归档"      | Set-Content -Encoding utf8 docs\evidence\README.md
"# 测试目录"      | Set-Content -Encoding utf8 tests\README.md
```

> `data/` 空目录 Git 不跟踪，靠 `.gitignore` 里的规则挡住即可，不用放 `.gitkeep`。

### 5.3 建虚拟环境并装依赖

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -V                                   # 激活后应显示 3.11.x，仍是 3.14 就是激活没生效
python -m pip install --upgrade pip
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pip list
```

`pip list` 里必须能看到：`streamlit 1.3x`（装到的是 1.67）、`openai 1.x`、`python-dotenv 1.x`、`pytest 8.x/9.x`。

本机实测（2026-11-09）：`streamlit 1.67.0 / openai 1.109.1 / python-dotenv 1.2.4 / pytest 9.2.0`，`streamlit hello` 在本项目路径（中文 + 空格）上起得来，HTTP 200。

### 5.4 配置密钥

```powershell
Copy-Item .env.example .env
notepad .env
```

先填 `LLM_API_KEY`（没有就先留空，S04 的 MOCK 模式不需要）。其余键**保持默认**：代码只读 `.env.example` 里已有的变量，不要自己加。

### 5.5 验证忽略规则（这一步最容易被跳过，也最容易出事）

```powershell
"SECRET=1" | Add-Content .env
git status --short
git check-ignore -v .env
```

期望：`git status` **看不到** `.env`；`check-ignore` 打印 `.gitignore:1:.env` 这类匹配行。

### 5.6 首次提交

```powershell
git add .
git status --short          # 逐行看，确认没有 .env / .venv / data
git commit -m "chore: 初始化仓库与目录骨架"
git log --oneline
```

## 6 验证

| # | 命令 / 动作 | 期望结果 |
|---|---|---|
| 1 | `py -3.11 -V` 且 `.\.venv\Scripts\python.exe -V` | 两条都是 Python 3.11.x |
| 2 | `pip list \| findstr /i "streamlit openai dotenv pytest"` | 四行都在 |
| 3 | `git check-ignore .env` | 输出 `.env`（退出码 0） |
| 4 | `git status --short` | 空输出 |
| 5 | `Get-ChildItem -Recurse -Directory` | 有 data\memory、data\logs、docs\evidence、tests |
| 6 | 删掉 `.venv` 后重跑 5.3 | 能重装成功（证明步骤可复现） |

> 第 6 条不要嫌麻烦：这是唯一能证明"换个人也能搭起来"的动作，出问题越早越好。

## 7 回滚

```powershell
deactivate
Remove-Item -Recurse -Force .venv
Remove-Item -Recurse -Force .git        # 仅当仓库是这一步刚建的
```

只回滚依赖不删仓库：`Remove-Item -Recurse -Force .venv` → 重跑 5.3。

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `Activate.ps1 因为在此系统上禁止运行脚本` | 执行策略 | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `pip` 卡在下载 | 网络 | 加 `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| `git status` 里出现 `.env` | `.gitignore` 没生效 | 检查文件是否是 UTF-8 无 BOM；`git check-ignore -v .env` 看匹配 |
| `python` 打开应用商店 | 没装 Python 或 PATH 未勾选 | 重装时勾 Add python.exe to PATH |
| Streamlit 启动报编码错误 | 控制台代码页 | `chcp 65001` 后重试 |
| `pip install -r requirements.txt` 报 `UnicodeDecodeError: 'gbk' codec can't decode` | `requirements.txt` 里有中文注释，旧版 pip 按系统 locale（GBK）读文件 | **`requirements.txt` 只许 ASCII**（已改英文注释）；遇到先 `python -m pip install --upgrade pip` 再装 |
| `python -V` 显示 3.14.x、路径在 Anaconda 下 | PATH 里 Anaconda 排在前面 | **不要改系统 PATH**（会弄坏 conda）；建环境用 `py -3.11`，跑命令用 `.\.venv\Scripts\python.exe` |
| `py` 不是内部或外部命令 | Python Launcher 没装（极简安装勾掉了） | 重跑安装包 → Modify → 勾 `py launcher` |

## 9 出口清单

- [ ] `py -3.11 -V` = 3.11.x，且 `.\.venv\Scripts\python.exe -V` = 3.11.x
- [ ] 四个依赖装好，`pip list` 能对上
- [ ] `.env` 已建且**不在** `git status` 里
- [ ] 四个目录都在
- [ ] 首次提交完成，`git log` 有一条记录
- [ ] 删掉 `.venv` 能按 §5.3 重建

## 10 回执（照这个格式发群里）

```text
S01 完成：Python 3.11.x / 依赖 4 个已装 / .env 已被忽略 / 首次提交 abc1234 / 重建验证通过
卡点：无（或写具体报错原文）
```
