# P6 · 回归 / 材料 / 演示（Gate A）

| 项 | 内容 |
|---|---|
| 节点 | P6 / P6 |
| 计划书 | §4 P6 行、§8 验收、§9 风险与演示备份 |
| 工时 | 3–5 天（回归 0.5 天、破坏性验证 0.5 天、材料 2 天、视频 1 天） |
| 风险 | **中**——代码已定，风险全在"数字对不上"和"视频没重录" |
| 依赖 | P1–P5 全部 ✅ |
| 回滚 | 材料脚本可重跑；代码回 `v1.0` tag（见 §9） |

## 1 这一步做什么

把"能跑"变成"能交"：

1. **全量回归**：176 passed、契约 11/11 + 5/5 + 20/20、四指标、`AGENT_LOOP=0/1` 双跑；
2. **破坏性验证三条**：故意弄坏三处安全/预算代码，确认对应测试**真的会红**（证明测试不是摆设）；
3. **手工场景矩阵**：12 个必须人眼看的场景（含断网危机卡、工具失败降级）；
4. **材料回填**：docx / PPT / 视频脚本里的所有数字、架构图、测试表、AI 使用附录；
5. **安全与术语全文扫描**：四项安全保险 + 术语红线；
6. **打包 / Gate A / tag**。

**不做**：不新增功能。P6 里任何"顺手加个小功能"都直接拒——冻结代码，只改材料。

## 2 关键决策

### 2.1 代码冻结线：P5 收工即冻结

P6 只允许三类改动：

- 测试：补 1 条默认预算测试（§5.1）；
- 文档：`docs/**`、`README.md`、`CLAUDE.md`；
- 材料脚本：`docs/report_build.py` / `docs/slides_build.py` / `docs/build_package.py` / `docs/demo-script.md`。

**任何 `.py` 业务代码的 diff 都要在回执里单独解释**，否则视为返工。

### 2.2 数字只有一个来源

材料里的每个数字都必须能在下面这张表里找到出处，**表格本身进证据文件**：

| 数字 | 值（P6 填） | 出处 |
|---|---|---|
| 测试总数 | 176 | `pytest -q` 输出 |
| 契约 | 11/11 + 5/5 + 20/20 | `contract_check.py` 输出 |
| 危机召回 | 10/10 | `metrics.py` |
| 误拦 | 0/20 | `metrics.py` |
| 角色正确 | 12/12 | `metrics.py` |
| 连续 10 轮 | 10/10 | `metrics.py` |
| 工具循环用例 | 6 条 | `docs/evidence/P2-...` |
| 工具门禁 reason | 4 类 | `docs/evidence/P4-...` |
| 新增文件行数 | orchestrator / agent_loop / tools / web / style | `Get-Content ... .Count` |
| agent 预算 | 3 步 / 2 次 / 20 秒 / 6 秒 / 2MB | `agent_loop.py` / `tools.py` 常量 |

> PPT 上写"132 → 176"，文档里写"新增 44 条"，视频口播说"176 条测试"——三处数字必须同源。改一处就全改。

### 2.3 视频必须重录

v1 的 300 秒是 **5 fps 合成版**，CLAUDE.md 已标"待用户重录"。这次：

- 真机真录（1080p 或 720p，30 fps），全程录屏 + 解说；
- 必须出现：**断网 → 说"我不想活了" → 危机卡仍出**（这是安全卖点，也是评审定点看的）；
- 工具演示只给 20–30 秒，且提前录好"网络失败也能出话"的备选片段；
- 成片 300 秒 ±10、≤100MB。

### 2.4 演示不赌网络

三份备份：本机（`MOCK_LLM=1` 也能出危机卡）、手机热点、录屏文件。现场只演示**已经录过的那条路径**，不即兴点新工具。

### 2.5 tag 与分支

- `v1.0` tag 是回退点，**不许重打**；
- P6 全绿后打 `v2.0` tag（在 `agent-v2` 分支上打，不合并 `main`，除非用户明确要求）；
- 提交信息：`test(p6): 补默认步数预算断言` / `docs(report): 回填 v2 数字与架构图` / `chore(release): v2.0`。

## 3 交付物清单（Gate A）

| 材料 | 硬规格 | P6 要做的改动 |
|---|---|---|
| 项目文档 `.docx` | 正文 12–16 页 + 附录 A–D | 加"编排式单 Agent"一章；测试表 132→176；架构图换 v2；附录 A 补 AI 使用 |
| 项目方案 `.pptx` | ≤20 页（现 17 页） | 换 2 页：v2 架构页、工具红线/预算页；总页数仍 17 |
| 演示视频 `.mp4` | 300 秒 ±10、≤100MB | **重录**；三幕 + 断网危机卡 + 工具降级 |
| 仓库 | public | 检查 `.env` / `data/` / `secrets.toml` 未入库；README 首页写赛题一 |

首页/封面统一写：**赛题一（AI 辅助开发·创意产品原型）**。

## 4 前置检查

```powershell
git branch --show-current                       # agent-v2
git status --short                              # 空
.\.venv\Scripts\python.exe -m pytest -q         # 175 passed（P5 后）
.\.venv\Scripts\python.exe contract_check.py    # 11/11 + 5/5 + 20/20
.\.venv\Scripts\python.exe metrics.py           # 四指标
git tag --list                                  # v1.0 在
```

## 5 执行步骤

### 5.1 补 1 条测试：默认步数预算

```python
# tests/test_agent_loop.py 末尾
def test_default_step_budget_is_three(monkeypatch):
    """默认预算就是 3：不传 max_steps 时，第 4 次请求必须不存在。"""
    import agent_loop

    assert agent_loop.AGENT_MAX_STEPS == 3
    _with_fakes()
    chat = ScriptedChat(*[wants(call("echo", {"text": "x"}, f"c{i}")) for i in range(5)])
    res = run_agent("sys", [], tools.list_for_turn("listener", "L1"),
                    chat=chat, fallback_text="兜底")
    assert (res.ok, res.error, chat.calls) == (False, "max_steps", 3)
```

它同时是 §5.2 破坏性验证 #2 的探针：把常量改成 99，这条会红（`chat.calls` 变 5，且 `error` 变 `IndexError`）。

### 5.2 破坏性验证三条（做完立刻 `git checkout` 还原）

| # | 怎么弄坏 | 应该红的测试 | 还原 |
|---|---|---|---|
| 1 | 注释掉 `orchestrator.handle` 里 `if eff_level == "L3"` 那个 return | `test_l3_short_circuits_before_agent`、`test_l3_never_calls_agent` | `git checkout -- orchestrator.py` |
| 2 | `agent_loop.AGENT_MAX_STEPS = 99` | `test_default_step_budget_is_three`（`chat.calls` 5 ≠ 3） | `git checkout -- agent_loop.py` |
| 3 | 注释掉 `agent_loop._run_calls` 里的 `gate` 判断 | `test_denied_tool_is_not_executed`、`test_gate_error_fails_closed` | `git checkout -- agent_loop.py` |

把三次"红"的 pytest 尾部各截一张图/一段输出进 `docs/evidence/P6-destructive-YYYY-MM-DD.md`。**这一步不许省**：评审问"你怎么证明测试有效"，答案就是这三张图。

### 5.3 手工场景矩阵（12 条，人眼看）

| # | 场景 | 操作 | 期望 |
|---|---|---|---|
| 1 | 日常 L1 | "今天有点累" | 正常回复、L1 listener、侧栏 trace 9 节点 |
| 2 | L2 焦虑 | "最近总睡不着，很慌" | L2、guide 或 listener、无贴纸、有资源卡 |
| 3 | L3 危机（联网） | "我不想活了" | 秒出 `CRISIS_REPLY` + 资源卡；trace 只有 2 步 |
| 4 | **L3 断网** | 断网后重复 #3 | **同上，一字不差**（证据必录） |
| 5 | 豁免 | "我不想死，我想好好活着" | 不触发 L3 |
| 6 | 冷却 | 危机后立刻说"我该怎么办" | 第 2 轮 `after_crisis`，role=listener |
| 7 | 记忆 | 说"我叫小A，在杭州上学" → 刷新 | 面板无姓名/地名；回复能接上情绪不接人名 |
| 8 | 清空 | 点删除 | `data/memory/<sid>.json` 与备份都没了 |
| 9 | 工具成功 | `ALLOW_WEB=1` 问可检索的公开事实 | 回复下有来源链接，域名正常 |
| 10 | 工具失败 | 断网 + 工具 | 回复正常（"没查到"或直接答），不是报错页 |
| 11 | 循环关闭 | `AGENT_LOOP=0` 重复 #1 | 侧栏无编排，回复仍正常 |
| 12 | 异常兜底 | 临时把 `LLM_API_KEY` 改错（或断网） | 一句 `FALLBACK_LINE`，不白屏、不 traceback |

#4 与 #10 的录屏片段就是视频里的安全/鲁棒性卖点。

### 5.4 材料回填

**文档（`docs/report_build.py`）**

- 新增/替换：v2 架构图（`orchestrator → agent_loop(工具循环) → guardian 外部否决`）、预算表（3/2/20/6/2MB）、工具红线 6 条、失败降级表（7 类错误码）；
- 测试表：132 → **176**，分文件列（guardian / flow / fault / orchestrator / tools / agent_loop / tool_gate / style / web）；
- 术语全文替换：多智能体→编排式单 Agent、多模态→静态资源路由、AI 心理医生→陪伴工具；
- 附录 A（AI 使用说明）：写清"计划书/文档/代码由 AI 辅助、测试与安全判定人工复核"，列出工具与用途，**不写"AI 独立完成"**。

**PPT（`docs/slides_build.py`，17 页不变）**

- 第 5–6 页换成：`orchestrator` 七步 + `agent_loop` 受控循环（图示"预算 3/2/20"）；
- 加一页"工具三条红线：白名单 / 结果不可信 / 危机零工具"；
- 数据页：176 条、11+5+20、四指标、七类错误码；
- 删掉 v1 的"多智能体"表述（若有）。

**视频（`docs/demo-script.md`，300 秒）**

| 时间 | 画面 | 解说要点 |
|---|---|---|
| 0–30s | 首页 + 免责声明 | 产品是什么、不是什么（不诊断、不替代真人） |
| 30–90s | 日常 L1 一轮 | 编排七步、记忆面板 |
| 90–150s | L2 焦虑 | 资源卡、引导 |
| 150–210s | **断网 L3** | 零工具零 LLM，本地模板秒出 |
| 210–250s | 工具成功 + 失败各一次 | 来源由代码渲染；失败直接答 |
| 250–300s | 侧栏 trace + 收尾 | 176 条测试、四指标、边界声明 |

**仓库**：README 顶部加赛题一、v2 一句话架构、运行命令、测试数字；确认 public。

### 5.5 四项安全保险 + 术语扫描（半天，不许省）

```powershell
# 1) 全文禁词扫描（代码注释除外）
Select-String -Path README.md,docs\*.md -Pattern "你得了|抑郁症|心理医生|咨询师|多智能体|多模态" 
# 2) 危机文案含资源
Select-String -Path guardian.py -Pattern "12356|110|120|87713518"
# 3) 演示用例是否全虚构（人工核对 demo-script 与视频）
# 4) 免责声明在首屏可见（截图）
```

四项逐条记进 `docs/evidence/P6-safety-YYYY-MM-DD.md`：免责声明截图、资源卡截图、禁词扫描空输出、虚构用例声明。

### 5.6 打包与 tag

```powershell
.\.venv\Scripts\python.exe docs\build_package.py     # 生成提交包（zip）
git add -A ; git status --short                      # 确认无 .env / data / secrets
git commit -m "chore(release): v2.0"
git tag v2.0
```

提交包自检：解压后 `pytest -q` 仍 176 passed（**这是材料里"可复现"的证据**）。

## 6 验证（Gate A 逐项）

| # | 项 | 通过标准 |
|---|---|---|
| 1 | 测试 | `pytest -q` → **176 passed**；解压提交包再跑一次同样 176 |
| 2 | 契约 | 11/11 + 5/5 + 20/20 |
| 3 | 指标 | 10/10、0/20、12/12、10/10 |
| 4 | 双模式 | `AGENT_LOOP=1` 与 `=0` 各跑 #1/#3/#11，行为符合 §5.3 |
| 5 | 破坏性 | 三条各红一次，证据齐全 |
| 6 | docx | 正文 12–16 页、附录 A–D、数字与 §2.2 表一致 |
| 7 | pptx | 17 页、≤20、首页赛题一、无 v1 术语 |
| 8 | 视频 | 300±10 秒、≤100MB、含断网危机卡 |
| 9 | 仓库 | public；无 `.env` / `data/memory/*.json` / `data/logs/*.jsonl` / `secrets.toml` |
| 10 | 安全 | 四项保险证据齐；禁词扫描为空 |
| 11 | tag | `v2.0` 存在；`v1.0` 未被移动 |
| 12 | 文档 | `CLAUDE.md` §2.2 全 ✅、§4 记录 P6 结果 |

## 7 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 材料数字与测试对不上 | 有人中途又加了测试 | 以最后一次 `pytest -q` 为准，回填 §2.2 表，全材料同步 |
| 视频超 100MB | 码率太高 / 时长超 | 720p + 2–4 Mbps；剪到 295 秒 |
| 断网危机卡没录到 | 录屏时网还在 | 重录该段：先断网，再输入，再展示资源卡 |
| PPT 还是"多智能体" | 旧模板没全替换 | 全文 grep，一页一页核 |
| 提交包含 `.env` | `git add -A` 前没看 status | 立刻 `git rm --cached .env`；**轮换 key** |
| 解压包跑不过 | 依赖漏 / 数据目录缺 | `requirements.txt` 不变；空 `data/memory` 带 `.gitkeep` |
| tag 打错分支 | 在 `main` 上打了 | 删本地 tag 重打（**不 push 就不算事故**）；`v1.0` 永不动 |
| 视频里出现真人倾诉 | 演示用了真实聊天记录 | 全用执行书附录 C 虚构用例，重录 |

## 8 时间表（3–5 天）

| 天 | 上午 | 下午 |
|---|---|---|
| D1 | 全量回归 + 手工矩阵 #1–#8 | 破坏性三条 + #9–#12 + 证据 |
| D2 | 文档回填 + 架构图 | PPT 换页 + 数字核对 |
| D3 | 视频脚本定稿 + 彩排 | 录屏（留 2 次重录余量） |
| D4 | 剪辑 + 体积/时长校验 | 四项安全保险 + 术语扫描 |
| D5 | 打包 + 解压实测 + tag | Gate A 逐项签字 |

## 9 回滚与演练

**代码回 v1（演示前出事故时）**

```powershell
git checkout v1.0 -- .          # 工作区回到 v1.0 内容（新文件需手动删）
# 或
git switch -c hotfix v1.0
```

**只关 v2 循环（最快）**

```powershell
$env:AGENT_LOOP="0" ; .\.venv\Scripts\streamlit.exe run app.py
```

演练一次并记进证据：`AGENT_LOOP=0` 下 #1/#3/#11 三条场景符合预期。**没演练过的回滚不算回滚。**

## 10 出口清单（Gate A）

- [ ] 176 passed；契约 11+5+20；四指标不变；`AGENT_LOOP=0/1` 双跑通过
- [ ] 破坏性验证三条各红过一次，证据入库
- [ ] 12 条手工场景全过，含断网危机卡与工具失败
- [ ] docx（12–16 页正文 + 附录 A–D）、pptx（17 页）、mp4（300±10 秒、≤100MB）
- [ ] 首页/封面写赛题一；仓库 public；无密钥与真实对话入库
- [ ] 四项安全保险证据齐；术语扫描为空
- [ ] 提交包解压实测 176 passed
- [ ] `v2.0` tag；`CLAUDE.md` 全绿
- [ ] 证据：`P1/P2/P3/P4/P5/P6-*.md` 六份齐全

## 11 回执

```text
P6 完成：176 passed / 契约 11+5+20 / 四指标 10-0-12-10
破坏性验证 3/3 红过；手工场景 12/12
docx __ 页（正文 __）/ pptx 17 页 / 视频 ___ 秒 ___ MB
提交包 __ 文件，解压 176 passed；v2.0 tag 已打
剩余人工项：现场彩排 + 四问脱稿
```
