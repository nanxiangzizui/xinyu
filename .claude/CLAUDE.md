# 心屿 MindIsle · 项目状态与规则（v2 · 编排式单 Agent）

> **本文件是唯一状态源。** 其他文件（SKILL.md、README、.mdc、计划书）只讲方法、范围与摘要，进度一律以这里为准。
> 最后更新：2026-11-12（迁入新工作区、切 `agent-v2`、v1.0 冻结为回退基线）
> v1 的完整进度日志已归档到 `docs/archive/CLAUDE-v1.md`，只在查历史时打开。

## 0. 三分钟了解

一句话：**情绪陪伴对话系统。v2 把固定七步管线抽成显式 `orchestrator`，只在"生成"这一步放进一个受控工具循环的 agent；`guardian` 始终在循环外，一票否决。**

- 形态：Streamlit 单页聊天 + 侧栏"本轮编排" + 记忆面板 + 资源卡
- 基线（v1.0，2026-11-08 冻结）：12 个 py / 1,962 行 / **132 passed** / `contract_check` 11/11 + 5/5 + 20/20 / 四指标达标
- v2 增量：新增 `orchestrator.py` / `agent_loop.py` / `tools.py`（P3 `web.py`、P5 `style.py`），测试目标 150+
- 尺度：课程实践作业。安全要真实，疗效一句不吹
- 交什么：**.docx 文档**（含 AI 使用附录）+ **17 页 PPT** + **300 秒录屏** + 现场三幕；**代码不单独计分**

## 1. 权威顺序（冲突时从上往下）

1. 用户在当前对话里的最新指令
2. `docs/plan-orchestrated-single-agent.md`（v2 的范围、接口、阶段与出口）
3. `心屿MindIsle_工程执行书_v1.0.md`（v1 的安全 / 数据 / 术语红线；v2 没写到的以它为准）
4. 本文件（进度与红线）
5. `.claude/skills/xinyu-v2/SKILL.md`（v2 怎么做、坑）+ `.claude/skills/xinyu-dev/SKILL.md`（v1 基线怎么维护）
6. `.cursor/rules/xinyu.mdc`（编码常驻摘要）

冲突时先停手问人，不要自行"综合"。改执行书要用户同意。

## 2. 技术栈与阶段

### 2.1 固定技术栈（冻结，不许新增依赖）

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11 | 不用 3.12+ 语法。**本机裸 `python` 是 Anaconda 3.14，一律用 `py -3.11` 建环境** |
| 界面 | Streamlit ≥1.32 | 单页；`st.chat_message` + `st.chat_input` |
| 模型 | DeepSeek（OpenAI 兼容） | `openai` SDK，`base_url=https://api.deepseek.com` |
| 存储 | 本地 `data/memory/*.json` | 一人一文件；原子写（tmp + replace） |
| 配置 | `python-dotenv` + `.env` | `.env` 永不进仓库 |
| 测试 | pytest | 纯函数优先，不测网络 |
| 部署 | Streamlit Cloud | 密钥走 Secrets，不写代码 |

**不许引入**：LangChain / LangGraph / ChromaDB / FastAPI / React / 任何前端框架 / 任何数据库 / 向量检索。**v2 的 agent loop 是手写的**，不许换成框架、不许加"编排引擎"。

### 2.2 v2 阶段表（进度看这里）

状态：⬜ 未开始 ｜ 🟨 进行中 ｜ ✅ 完成 ｜ ⛔ 已砍

| 阶段 | 做什么 | 状态 | 出口（可验证） |
|---|---|---|---|
| P0 | 基线复跑 + DeepSeek `tools` 能力探测 | ✅ | 探测结果进 `docs/evidence/`；132 passed + 契约全绿 |
| P1 | `app.py` 的 `handle` / `safe_handle` 搬进 `orchestrator.py` | ✅ | **行为零变化**；132 旧 + 5 新 = 137 passed；C-01 / C-05 / C-09 不变 |
| P2 | `agent_loop.py` + `tools.py`（先接 echo / fake_search 假工具） | ✅ | 直接答 / 一次工具后答 / 步数超限 / 工具次数超限 / 工具报错 / 未知工具 / L3 不循环，六条全绿；**137 旧 + 13 新 = 150 passed** |
| P3 | `web.py` 网络工具（搜索 / 图片 / 风格包） | 🟨 | P3a：七类错误码 9 条离线测试全绿（159 passed）、`web.py` 180 行；P3b 真实 provider smoke 等 key |
| P4 | `guardian_tool_check` 接进 loop + 侧栏"本轮编排" | ✅ | **159 旧 + 7 新 = 166 passed**；越权工具被拦；trace 不含原文；来源链接由代码渲染；`AGENT_LOOP` 默认 1 |
| P5 | `style.py` 风格层（口吻 / 句尾 / 贴纸） | ⬜ | L3 模板逐字不变；L2 稳重；L1 口语化；贴纸不越界 |
| P6 | 回归 / 材料 / 演示 | ⬜ | Gate A 仍成立；v2.0 可演示；docx / PPT / 视频数字回填 |

**P0–P4 已完成**；P3b 真实检索仍等 D-1（provider / key），P5 口吻层待做。

### 2.3 v2 预算常量（进常量区，测试断言"超限会停"，不靠模型自觉）

```text
AGENT_MAX_STEPS        = 3
AGENT_MAX_TOOL_CALLS   = 2
AGENT_TOTAL_TIMEOUT_S  = 20
TOOL_TIMEOUT_S         = 6
TOOL_MAX_BYTES         = 2_000_000
AGENT_LOOP             = 1 / 0     # feature flag，出问题一键关回 v1 管线
```

### 2.4 交什么（赛制不变，P6 统一回填数字）

| 材料 | 硬规格 | 必须有什么 |
|---|---|---|
| 项目文档 | .docx，正文 12–16 页 + 附录 A–D | 背景 / 方案 / 技术路径 / 分工 / 创新点 / 总结 + **附录 A：AI 使用说明** |
| 项目方案 | .pptx ≤20 页（做 17 页） | 创作理念 / 问题与需求 / 技术路径 / 设计过程 / 成果 |
| 演示视频 | MP4 300 秒 ±10，≤100MB，全程录屏 + 解说 | 必须含"断网仍出危机卡" |
| 现场答辩 | 仅决赛（30%） | 三幕 + 四问 + 数据一页 |

预赛 100 分 = 学术诚信 12.5 + 文档 25 + **PPT 37.5** + 视频 25。赛题：**赛题一（AI 辅助开发·创意产品原型）**，材料首页都要写。

## 3. 项目结构

```text
xinyu-agent/
├─ 心屿MindIsle_工程执行书_v1.0.md       v1 唯一执行依据（安全/数据/术语红线仍有效）
├─ docs/plan-orchestrated-single-agent.md v2 计划（当前执行依据）
├─ docs/migration-new-workspace.md       迁移说明与验收清单
├─ docs/archive/CLAUDE-v1.md             v1 进度日志（只查历史用）
├─ README.md                             对外门面
├─ .claude/CLAUDE.md                     本文件（状态源）
├─ .claude/skills/xinyu-v2/SKILL.md      v2 开发技能（P0–P6 怎么做）
├─ .claude/skills/xinyu-dev/SKILL.md     v1 开发技能（维护基线时看）
├─ .cursor/rules/xinyu.mdc               常驻硬规则
├─ requirements.txt                      冻结依赖（只许 ASCII）
├─ .streamlit/config.toml                基色 + 关闭错误详情
├─ app.py            只做 UI：页面 / 聊天区 / 侧栏 / 渲染，调 orchestrator
├─ orchestrator.py   ★P1 固定编排顺序 + trace + 异常兜底
├─ agent_loop.py     ★P2 主 agent 循环（步数 / 工具次数 / 结果回填）
├─ tools.py          ★P2 白名单 / schema / 执行 / 超时 / 大小上限
├─ web.py            ★P3 搜索 / 图片 / 风格包（HTTP、超时、大小、schema）
├─ style.py          ★P5 口吻层（句尾 / 贴纸 / tone hint）
├─ agent.py          call_llm / chat_with_tools / build_system_prompt / MOCK
├─ roles.py          5 人设卡 + RULES 20 条（不许改）
├─ coordinator.py    三角色状态机 + 聚合 + 只升不降（不许改判定）
├─ guardian.py       分级 / 豁免 / 复核 / 重写 / 工具门禁
├─ memory.py         8 字段白名单 + 摘要节流 + 备份 + lore（不许改白名单）
├─ resources.py      情绪 → 资源卡（不许改）
├─ logger.py         9 字段结构化日志（不许加字段）
├─ panel.py          记忆面板
├─ theme.py          三套配色
├─ contract_check.py 11 签名 + 5 常量 + 20 条规则
├─ metrics.py        四指标脚本
├─ tests/            132 → 150+；新增 test_orchestrator / test_agent_loop / test_tools
├─ step/             v1 的 26 个步骤文件（历史归档，不再更新）
├─ data/memory/      运行时数据，不进仓库
├─ data/logs/        运行时日志，不进仓库
└─ docs/             报告 / PPT / 视频 / 证据
```

**边界是硬的**（v2 也不能破）：

- UI 不直接调 LLM、不写业务判断，只调 `orchestrator.safe_run()`
- `orchestrator` 只做顺序与兜底，不复制节点内部逻辑
- `guardian` 不依赖 UI、不参与 agent 协商、不被工具结果说服
- `tools` 不接受任意 URL、不读本地文件、不执行 shell
- agent 不写 `memory.json`；写入仍走 `update_memory` 的白名单 + `scrub`

## 4. 当前进度

**2026-11-12 迁移到新工作区（已完成）**

- ✅ 新工作区 `D:\deepseek harness\xinyu-agent`（ASCII、无空格），仓库 `main` @ `f18dbd5`
- ✅ 切 `agent-v2` 分支；`v1.0` tag 保留为回退点
- ✅ 两份计划文档入库（`plan-orchestrated-single-agent.md` / `migration-new-workspace.md`）
- ✅ `.venv` 重建（`py -3.11`，Python 3.11.9），依赖仍是 streamlit / openai / python-dotenv / pytest
- ✅ `.env` 重建（6 键，不入库）；本地不留 `.streamlit/secrets.toml`（会让 `test_f06` 变红），模板见 `.streamlit/secrets.toml.example`，线上 Secrets 在 Cloud 后台填
- ✅ `data/memory`、`data/logs` 空目录（`.gitkeep` 占位）
- ✅ **P0 完成（2026-11-12）**：`pytest` 132 passed、`contract_check` 11/11 + 5/5 + 20/20、`metrics` 四指标全达标；DeepSeek `tools` 探测三关全过（证据 `docs/evidence/P0-tools-probe.md`，结论：走标准 OpenAI `tool_calls` 协议）
- ✅ **P1–P6 执行文档已建（2026-11-12）**：`docs/v2-steps/` 下 README + 六份分步操作手册（P1 orchestrator / P2 agent-loop / P3 web-search / P4 guardian-tool-gate / P5 style-layer / P6 regression-materials），体例同 `step/`（11 节：做什么→决策→接口→前置→步骤→测试→验证→失败→回滚→出口→回执）；**本次只写文档，代码零改动，pytest 仍 132 passed**
- 📝 **P3 内容检索候选设计（2026-11-12，未决策）**：`docs/v2-steps/P3-content-retrieval-design.md` 记录“本地轻量识别 → orchestrator 路由 → MCP/HTTP 取风格 / 贴纸 / 图片”的三层想法；明确 skill 不是运行时能力、host 就是 orchestrator、MCP 只能作白名单工具后端；**不改计划书与 D-1~D-5，P3b 仍等 D-1**
- ✅ **P1 完成（2026-11-12）**：`orchestrator.py`（186 行）接管七步编排 + 9 节点 trace + 异常兜底，`safe_handle` 改名 `safe_run`；`app.py` 326→174 行只留 UI；**137 passed**（132 旧 + `test_orchestrator` 5 新）、`contract_check` 11/11 + 5/5 + 20/20、`metrics` 四指标不变；证据 `docs/evidence/P1-orchestrator-2026-11-12.md`。唯一与文档偏差：P1 文档 §6 示例用 `handle` 断言兜底，实际按 §5.1 改用 `safe_run`
- ✅ **P2 完成（2026-11-12）**：新增 `tools.py`（133 行：ToolSpec/ToolResult/REGISTRY/execute/list_for_turn/echo/fake_search）、`agent_loop.py`（112 行：run_agent + 预算常量）、`agent.chat_with_tools`（+30 行）、`orchestrator._generate`（`AGENT_LOOP=0` 走 v1 call_llm，`=1` 进受控 loop）；新增 `tests/test_tools.py`(7) + `tests/test_agent_loop.py`(6)。出口：**150 passed** / 契约 11+5+20 / 四指标不变；冒烟（AGENT_LOOP=1+MOCK）L3 trace 无 generate、日志 9 字段无原文；证据 `docs/evidence/P2-agent-loop-2026-11-12.md`。`AGENT_LOOP` 默认 0，旧测试零改动。
- ✅ **P3a 完成（2026-11-12）**：新增 `web.py`（180 行：`search` / `search_sources` / `is_safe_url` / 七类错误码 / `register_tools`）与 `tests/test_web.py`(9)；`app.py` 启动时 `web.register_tools()`（注册 ≠ 暴露，`ALLOW_WEB` 默认 0），`_SECRET_KEYS` 补 `WEB_PROVIDER/WEB_API_KEY/WEB_ENDPOINT` 三键；出口：**159 passed**（150 + 9）/ 契约 11+5+20 / 冒烟假 transport 全绿（`docs/evidence/p3_smoke_2026-11-12.py`）；证据 `docs/evidence/P3-web-2026-11-12.md`
- 🟨 **P3b 待做**：真实 provider（D-1）请求构造 + 一次真实 smoke + `.env` / Cloud Secrets 填 key；key 到位前 `web_search` 返回 `http_401`，`ALLOW_WEB=0` 时模型看不到该工具
- ✅ **P4 完成（2026-11-12）**：新增 `guardian.guardian_tool_check`（四 reason：`ok` / `crisis_no_tool` / `unknown_tool` / `bad_args`，gate 异常 fail-closed）；`agent_loop` 接 `gate` + `source_filter`，`AgentResult.sources` 去重保序；`orchestrator._generate` 传门禁与 `web.search_sources`，loop 失败 `raise` 交 `safe_run` 走 L2 模板；`panel.render_trace` 侧栏「本轮编排」；`app` 渲染代码来源；`AGENT_LOOP` 默认翻 1（`=0` 仍回 v1）。出口：**166 passed**（159 + `test_tool_gate` 7）/ 契约 11+5+20 / 四指标不变；冒烟 `docs/evidence/p4_smoke_2026-11-12.py` 全绿；证据 `docs/evidence/P4-tool-gate-2026-11-12.md`
- ⬜ **下一阶段 P5**：按 `docs/v2-steps/P5-style-layer.md` 做 `style.py` 口吻层（L3 模板逐字不变）

**v1.0 基线（2026-11-08 冻结，数字以提交包解压实测为准）**

- 132 passed；`contract_check` 11/11 + 5/5 + 20/20；四指标：召回 10/10、误拦 0/20、角色 12/12、连续 10 轮 10/10
- 材料：docx 26 页（正文 15）、PPT 17 页、视频 300 秒（**5 fps 合成版，待用户重录**）、提交包 109 文件
- 未完成的人工项：现场彩排 + 四问脱稿、人设盲读 3 人、危机文案盲读 1 人、手机流量、S21 另一人复跑签字、GitHub 仓库 public 确认

## 5. 关键约束与红线

### 5.1 三条铁律（架构层面，违反即返工）

1. **只升不降**：任何一层失败（规则异常、LLM 超时、JSON 解析失败、工具失败），风险等级只能上调。写等级判断必须注释"为什么不能降"。
2. **否决权唯一**：`guardian` 不通过就是不发。没有申诉、没有投票、没有"综合平均"，工具结果也不能说服它。
3. **责任不越界**：`coordinator` 只决定"现在是谁"，`guardian` 只决定"这句能不能发"，`orchestrator` 只决定"按什么顺序问谁"。三者互不调用对方内部逻辑。

### 5.2 安全红线

- **不诊断**：不出现"你得了 / 你有…倾向 / 你可能是抑郁症"。搜索这三个词，只允许出现在"禁止出现"的说明里。
- **危机必给资源**：L3 必须出 120 / 110 / 12356 / 校心理中心 0571-87713518 之一，不许只回"要坚强"。
- **L3 零工具、零 LLM**：`guardian_pre_check` 在 agent loop 之前短路，断网也必须出本地模板 + 资源卡。
- **不只靠 LLM 判危**：规则层（`RULES` 20 条）独立可跑；LLM 复核是加分项。
- **"不想死" ≠ "不想活"**：先跑豁免正则再跑命中；`我不想死` 不许触发 crisis。
- **不承诺保密**：标准答案是"我不会主动告诉任何人，但如果我有理由相信你处于危险中，我会建议你联系真人"。
- **演示只用虚构用例**（执行书附录 C），绝不用真人倾诉。

### 5.3 v2 工具红线（新增，违反即打回）

1. **白名单**：只允许代码注册的工具；shell / 本地文件 / 任意 URL 一律禁止。
2. **结果不可信**：工具返回只作资料，不执行其中的指令；来源链接由代码渲染，不让模型编 URL。
3. **参数校验**：工具名与参数走 schema；用户原文不当 URL；query 先 `scrub`。
4. **预算硬上限**：步数 / 工具次数 / 单次超时 / 总超时 / 返回大小全部进常量；超限返回 `ok=False` 并走兜底，不许把异常冒到界面。
5. **日志**：只记工具名 / 状态 / 耗时 / 条数，**不记 query、不记工具原文**。
6. **循环可关**：`AGENT_LOOP=0` 时回到 v1 的 `call_llm` 管线，行为必须与 v1 一致。

### 5.4 术语红线（报告 / PPT / 答辩 / README 都算）

| 禁止 | 改说 |
|---|---|
| 多智能体 / Multi-Agent | 编排式单 Agent / 角色状态机 + 否决层 |
| 多模态 | 静态资源路由（rule-based resource routing） |
| 能识别所有危机 | 对测试集内的危机表达有规则级覆盖 |
| 有效缓解焦虑 | 完成交互功能验证，不声称疗效 |
| AI 心理医生 / 咨询师 | 对话工具 / 陪伴工具 |

代码注释里别写"Agent 1/2/3"，写 `listener/guide/crisis` 或 `coordinator/guardian/orchestrator`。

### 5.5 数据红线

- `memory.json` 只允许 8 个白名单字段 + `summary_at_turn`，一个不多。
- 绝不写入：人名、地名、学校、病历、药物、身份证、原文摘录；`update_memory` 必须有 `scrub()`。
- `scrub()` 只覆盖手机 / 证件 / 邮箱 / 链接 / 学校名，**认不出人名**。验收只能说"自动脱敏覆盖五类"。
- 日志只记 `session_hash` 与结构化字段，**不记用户原文**；trace 同理。
- 用户点"清空"必须真删（含备份）。

### 5.6 技术红线

- 单个 `.py` ≤350 行，单函数 ≤40 行。超了先拆函数再拆文件。
- 所有 LLM 调用：`timeout=15`、`max_retries=1`、失败走兜底，异常不许冒到界面。
- LLM 返回的 JSON：`try/except` + 兜底；解析失败按"中风险"处理，不按"没事"处理。
- 魔法数字进常量区。
- `requirements.txt` **只许 ASCII**（旧 pip 按系统 locale 读，中文注释会 `UnicodeDecodeError`）。
- 新增文件的行数预算：`orchestrator.py` ≤250、`agent_loop.py` ≤180、`tools.py` ≤200、`web.py` ≤250、`style.py` ≤180。

## 6. 工作方式

### 6.1 一次任务的标准动作

1. **对齐**：读本文件 §2.2 与 §4，确认当前阶段和出口。
2. **定位**：只读相关的那一节 SKILL，不要全文读。
3. **改**：最小改动；安全相关改动写 `[SAFE]` 标记与理由。
4. **验**：`pytest -q` + `python contract_check.py` + 手动跑受影响路径。
5. **证**：截图 / 日志 / 测试输出存 `docs/evidence/`，文件名带日期。
6. **报**：说清"改了什么 / 怎么验的 / 还剩什么"。

### 6.2 状态怎么更新

改完一个出口 → 改 §2.2 状态列 → 在 §4 加一行日期与结果。**没更新本文件 = 没做。**

### 6.3 Git

- `main` 不动；v2 全部在 `agent-v2` 分支。
- 提交信息：`feat(guardian): 增加工具门禁` / `refactor(orchestrator): 从 app 抽出七步管线` / `docs(plan): 补 P0 探测结果`。
- 禁 `push -f`；禁提交 `.env`、`.streamlit/secrets.toml`、`data/memory/*.json`、`data/logs/*.jsonl`。
- `v1.0` tag 是回退点，不许重打。

## 7. 常用命令

```powershell
# 环境（本机裸 python = Anaconda 3.14，必须 py -3.11）
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -V                      # 必须 3.11.x
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 跑
.\.venv\Scripts\streamlit.exe run app.py
$env:MOCK_LLM="1"; .\.venv\Scripts\streamlit.exe run app.py    # 离线演示

# 验
.\.venv\Scripts\python.exe contract_check.py        # 期望 11/11 + 5/5 + 20/20
.\.venv\Scripts\python.exe -m pytest -q             # 期望 166 passed（v2 P4 后）
.\.venv\Scripts\python.exe -m pytest tests/test_guardian.py -q -k crisis
```

## 8. 验收底线

- **P0**：探测结果落证据；132 passed；契约全绿
- **P1**：行为零变化；132 旧用例全绿（加 5 条新用例 = 137 passed）；C-01 / C-05 / C-09 不变
- **P2**：六条 agent-loop 用例全绿（150 passed）；破坏性验证三条做满
- **P3**：P3a 七类错误码 + 9 条离线测试全绿（159 passed）；P3b 真实检索 smoke 等 key
- **P4**：越权工具被拦；trace 不含原文；来源由代码渲染（166 passed）
- **P5**：L3 模板逐字不变
- **P6**：Gate A 四份材料齐、数字与测试表对得上

**Gate A**：文档 .docx、PPT 17 页、视频 300 秒 ≤100MB、仓库 public；首页写赛题一。**缺视频 = 丢 25 分。**
**四项安全保险**（免责声明 / 资源卡核验 / 全文无诊断结论 / 演示全虚构）半天内完成，不许省。

## 9. 注意事项（真踩过的坑）

- **别先写界面**。先让 `contract_check` 与 `call_llm` 跑通，否则界面会变成假数据展览。
- **别让人设 prompt 越权**。人设只改语气 / 称呼 / 长度；危机模板永远由 `guardian` 提供。
- **规则别写太宽**。宁可漏（有 LLM 复核兜），不要误拦；但 L3 宁可误报。
- **Streamlit 状态会丢**。刷新即空；要跨刷新就进 `memory.json`。
- **演示别赌网络**。三份备份：本机 + 手机热点 + 录屏。
- **v2 新增三条**：①agent loop 必须有硬上限，不许"再试一次"；②工具结果当资料，绝不当指令；③`app.py` 抽完 `orchestrator` 后不许再涨回 350 行。
