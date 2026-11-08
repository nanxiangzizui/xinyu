# 心屿 MindIsle · 项目状态与规则

> **本文件是唯一状态源。** 其他文件（SKILL.md、README、.mdc）只讲方法、格式和摘要，状态一律以这里为准。
> 最后更新：2026-11-08（规则补丁收尾：53 passed，执行书升 v1.2，待提交 v0.2 tag；W2 两项盲读仍待做）

## 0. 三分钟了解

一句话：**情绪陪伴对话系统。它在"倾听 / 引导 / 危机"三种状态间自动迁移，并有一个一票否决的安全审查层。不做"多智能体"的表演，只做清晰的责任边界。**

- 形态：Streamlit 单页聊天 + 侧栏状态 + 记忆面板 + 资源卡
- 交付：4 周出一个可演示版本 + 3 天材料期，6 人小队
- 尺度：课程实践作业。安全设计要真实，疗效一句不吹
- 规模：11 个 py 文件（约 1200 行）+ 97 条测试（考核口径 48）
- 交什么：**.docx 文档**（含 AI 使用附录）+ **17 页 PPT** + **300 秒录屏视频** + 现场三幕。代码不单独计分

## 1. 权威顺序（冲突时从上往下）

1. 用户在当前对话里的最新指令
2. `心屿MindIsle_工程执行书_v1.0.md`（范围与数字的唯一出处）
3. 本文件（进度与红线）
4. `.claude/skills/xinyu-dev/SKILL.md`（怎么做、坑）
5. `.cursor/rules/xinyu.mdc`（编码时常驻摘要）

**改执行书要用户同意。** 改本文件只需当周负责人 + 队长知会，但必须留下"改了什么 / 为什么"一行。

## 2. 技术栈

### 2.1 固定技术栈（冻结，不许新增依赖）

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11 | 不用 3.12+ 的新语法，学校机房可能是 3.11。**本机裸 `python` 是 Anaconda 3.14，一律用 `py -3.11` 建环境** |
| 界面 | Streamlit ≥1.32 | 单页；`st.chat_message` + `st.chat_input` |
| 模型 | DeepSeek（OpenAI 兼容） | `openai` SDK，`base_url=https://api.deepseek.com` |
| 存储 | 本地 `data/memory/*.json` | 一人一文件；原子写（tmp + replace） |
| 配置 | `python-dotenv` + `.env` | `.env` 永不进仓库 |
| 测试 | pytest | 纯函数优先，不测网络 |
| 部署 | Streamlit Cloud | 密钥走 Secrets，不写代码 |

**不许引入**：LangChain / LangGraph / ChromaDB / FastAPI / React / 任何前端框架 / 任何数据库 / 向量检索。理由见执行书 §2.3 与 §3.0——新手 4 周做不完，且会把调试时间吃光。

### 2.2 分步骤表（进度看这里）

状态：⬜ 未开始 ｜ 🟨 进行中 ｜ ✅ 完成 ｜ ⛔ 已砍

| 步 | 周期 | 状态 | 对应执行书 | 主要组件 | 出口（可验证） |
|---|---|---|---|---|---|
| S0 | 计划期 | ✅ | 全文 | 五份计划书整合 + 执行书 v1.0 | 执行书冻结，范围不再讨论 |
| S1 | W1 | ✅ | §7.1 | 仓库 / 骨架 / `agent.py` / `memory.py` / `app.py` / 部署 | 在线可打开 + 10 轮不崩 + `contract_check` 11/11 + `v0.1` |
| S2 | W2 | 🟨 | §7.2、§4.3、§4.6、§4.7 | 五套人设 + 状态机 + `guardian_pre_check` | C-09 切 crisis；C-01 不误触；日志无原文 + `v0.2` |
| S3 | W3 | ⬜ | §7.3、§4.8、§5 | `guardian_post_check` + 聚合 + 记忆面板 + 主题 + lorebook | 重写日志 `rewrite=1`；风险地板不掉；3 主题不错位 + `v0.3` |
| S4 | W4 | ⬜ | §7.4、§8 | 97 条测试（考核 48）+ 冻结 + 录屏 | 指标达标 + 测试表齐 + `v1.0` |
| S5 | +3 天 | ⬜ | §7.5、§12 | 报告 / PPT / 彩排 / 提交清单 | 逐项打勾，三份备份 |

每周五的验收是**硬门**：不过就打回，不许"下周补"。

**怎么做 = 看 `step/`**：上面 S1–S5 是五个阶段，阶段内拆成 26 个可单独验证、可单独回滚的步骤文件（`step/S01-*.md` … `step/S26-*.md`，总纲是 `step/README.md`）。

| 阶段 | 对应步骤文件 |
|---|---|
| S1 | S01 环境 → S02 骨架契约 → S03 memory → S04 agent → S05 app → S06 部署 v0.1 |
| S2 | S07 人设卡 → S08 RULES → S09 豁免 → S10 短路 → S11 状态机 → S12 日志 v0.2 |
| S3 | S13 post_check → S14 复核 → S15 说教词 → S16 聚合 → S17 摘要 → S18 面板 → S19 主题 → S20 lore → S21 验收 v0.3 |
| S4 | S22 28 条规则单测 → S23 12 对话 + 8 注入 → S24 指标冻结 v1.0 |
| S5 | S25 报告 → S26 PPT 彩排提交 |

做一步就勾 `step/README.md` §7 的那一行，并回填本表状态列。

### 2.3 交什么（比赛要求，2026-11-08 接入）

来源 `docs/AIGC大赛通知-2026.docx`；逐项规格与逐页/逐镜脚本见 `docs/比赛要求对照与提交计划.md`。

| 材料 | 硬规格 | 必须有什么 |
|---|---|---|
| 项目文档 | **.docx**，正文 12–16 页 + 附录 A–D | 背景 / 解决方案 / 技术实现路径 / 团队分工 / 创新点与价值 / 总结与展望 + **附录 A：AI 使用说明** |
| 项目方案 | **.pptx ≤20 页**（做 17 页） | 创作理念 / 问题与需求 / 技术路径 / 设计过程 / 成果与协作 |
| 演示视频 | **MP4 300 秒 ±10，≤100MB，全程录屏 + 解说** | 必须含"断网仍出危机卡"那一段 |
| 现场答辩 | 仅决赛（占 30%） | 三幕 + 四问 + 数据一页 |

预赛 100 分 = 学术诚信 12.5 + 文档 25 + **PPT 37.5** + 视频 25。**代码不单独计分**：功能做到"能演"就停手，时间给材料。

赛题：**赛题一（AI 辅助开发·创意产品原型）**。所有材料首页都写这一行。

**「对 AIGC 技术的理解、选择与组合运用」怎么答** → `docs/比赛要求对照与提交计划.md` §10。要点：只用 DSH 一个开发平台**合规、不扣分**（通知只要求披露，不要求平台数量）；得分点是产品内部的六种能力分工（生成 0.8 / 判别 0.2 / 改写 0.5 / 摘要 → 模型；规则 / 路由 → 代码），加三条低成本证据（双通道对比、参数分档、选型矩阵）。

## 3. 项目结构

```text
心屿/
├─ 心屿MindIsle_工程执行书_v1.0.md   唯一执行依据
├─ README.md                          对外门面
├─ .claude/CLAUDE.md                  本文件（状态源）
├─ .claude/skills/xinyu-dev/SKILL.md  开发技能（按周加载）
├─ .cursor/rules/xinyu.mdc            常驻硬规则
├─ requirements.txt                   冻结依赖（不许加）
├─ .streamlit/config.toml             基色 + 关闭错误详情
├─ app.py            Streamlit 页面与交互
├─ agent.py          call_llm / build_system_prompt / MOCK / 重试
├─ roles.py          5 人设卡 + 3 主题 + RULES 20 条
├─ coordinator.py    三角色状态机 + 会话聚合 + 只升不降
├─ guardian.py       规则 → 豁免 → 分级 → 复核 → 短路 / 重写 / 复检
├─ memory.py         白名单读写 + 摘要节流 + 备份 + 清空 + match_lore
├─ resources.py      情绪 → 资源卡（纯函数）
├─ logger.py         结构化日志（9 字段，不写原文）
├─ theme.py          三套配色（sakura / matcha / sunset）
├─ contract_check.py 11 签名 + 5 常量 + 20 条规则校验
├─ metrics.py        四指标脚本（只读测试集）
├─ utils.py          按需创建：第 2 次重复才搬进来（≤100 行）
├─ tests/            test_memory / test_agent / test_roles / test_log /
│                    test_guardian / test_flow / test_fault（共 97 条）
├─ step/             26 个分步执行文件 + README（怎么做看这里）
├─ data/memory/      memory.json（不进仓库）
├─ data/logs/        YYYY-MM-DD.jsonl（不进仓库）
└─ docs/             报告、PPT、证据截图
```

**六文件边界是硬的**：`roles.py` 是 RULES 与人设的唯一来源；界面不许直接调 `call_llm`；`coordinator` 不许读 `memory` 以外的东西；`guardian` 不依赖界面。

`utils.py` 不是业务模块：只放无业务语义的小工具（时间 / 哈希 / JSON 兜底），出现业务判断即违规；**没有重复就不建**。

## 4. 当前进度

**2026-11-09**

- ✅ 五份计划书已整合评审（`五份计划书整合评审与可行方案.md`）
- ✅ 执行书 v1.0 冻结：3 角色 / 3 决策层 / 20 条规则 / 11 契约 / 48 测试 / 六级砍单
- ✅ 工程脚手架：`README.md`、`.gitignore`、`.env.example`、`requirements.txt`、`.streamlit/config.toml`、`.claude/*`（CLAUDE.md + SKILL.md）、`.cursor/*`
- ✅ 分步执行手册：`step/README.md` + `S01`–`S26` 共 26 个文件（步内合计 116 人时，含测试口径 48 / 自测 49 / 合计 97 条的分层说明）
- ✅ 仓库已初始化（`git init`，分支 `main`，首次提交 `ebf10c4`）；**代码 0 行**
- ✅ 文档审计（2026-11-09）：规则引擎实机验证 34/34（28 条 D + 6 条 C）、日常闲聊误拦 0/20；执行书升 **v1.1**；证据 `docs/evidence/audit-2026-11-09.md`
- ✅ 危机资源电话已填：学校心理中心 0571-87713518（2026-11-09 队内补录；**提交前再拨一次确认**，接通即算核验）
- ✅ Python 版本已定：本机装 **Python 3.11.9**（winget，`py -3.11` 可用；裸 `python` 仍是 Anaconda 3.14，一律不用）；`.venv` 已建好并**验证可重建**（删掉重装成功），实测 `streamlit 1.67.0 / openai 1.109.1 / python-dotenv 1.2.4 / pytest 9.2.0`
- ✅ 本机风险已排除：`streamlit hello` 在中文+空格路径下 HTTP 200，不必搬项目目录；`requirements.txt` 中文注释曾触发 GBK `UnicodeDecodeError`，已改纯 ASCII 并立为红线
- ⬜ 6 人是否都会 Python 未确认（W1 周一环境检查后回填）
- ✅ 比赛要求已接入（2026-11-08）：通知已读并存入 `docs/AIGC大赛通知-2026.docx`；产出 `docs/比赛要求对照与提交计划.md`；S25 改 Word + 附录 A、S26 改 17 页 PPT + 300 秒视频；git remote 已通（github.com/nanxiangzizui/xinyu）、DeepSeek key 实测可用
- ⬜ **当前教学周未确认**——决定到"第 12 周推荐截止"还剩 1/2/3 周，直接决定砍到第几级
- ✅ S02（2026-11-09）：`roles.py` + 五模块空壳 + `contract_check.py` 落地，跑出 **11/11 + 5/5**；故意改签名、改 `TIMEOUT` 两条人工验红；证据 `docs/evidence/2026-11-09-s02-contract.md`
- ✅ S03（2026-11-09）：`memory.py` 全量 219 行（8 字段 + `summary_at_turn` 白名单 / 原子写 + `.bak` / 坏文件自愈 / `scrub` / 真删）；`tests/test_memory.py` **9 passed**；手工验证落盘无原句、坏文件回默认值；证据 `docs/evidence/2026-11-09-s03-memory.md`。口径修正：`summary_at_turn` 按执行书 §5.1.1 定义为“上次压缩轮次”，**不每轮自增**（否则 S17 节流失效）
- ✅ S04（2026-11-09）：`agent.py` 121 行（`call_llm` / MOCK 三剧本 / `safe_json` / 懒加载客户端）；`tests/test_agent.py` **6 passed**（累计 15）；真实调用 `ok=True` 2769ms；证据 `docs/evidence/2026-11-09-s04-agent.md`。口径修正：本机 openai 1.109.1 的 `create()` 不接受 `max_retries`，`timeout=15` 与 `max_retries=1` 放在客户端构造上，否则会被兜底吞成 `TypeError`
- ✅ S05（2026-11-09）：`app.py` 146 行（首屏免责声明 / 聊天区 / 侧栏 / URL 会话 id / 固定七步管线 / 三层兜底）；AppTest 连续 10 轮 **20 条消息 0 异常**，刷新同 sid、记忆面板可读；清空时旧记忆三文件真删并换新 sid；缺 Key 非 MOCK 出兜底句不露堆栈；截图 `docs/evidence/2026-11-09-s05-*.png`；证据 `docs/evidence/2026-11-09-s05-app.md`

- ✅ 复审（2026-11-08，S03–S05 独立验收）：`pytest` 15 passed / `contract_check` 11+5 全绿，AppTest 10 轮 20 条 0 异常；**修 4 个代码缺陷**（记忆自愈会用坏主文件覆盖唯一好备份 / `match_lore` 漏传 sid / 缺 Key 被伪装成网络卡顿 / `degraded` 靠字符串相等判定）+ 8 处文档口径；p5-app 三个提交已 push
- ✅ 外部复核（2026-11-08，另一 agent 独立跑）：两条手工验收全过——①手写坏主文件后一轮真实对话，主文件自动修回、`.bak` SHA-256 前后一致；②改名 `.env` 后 `streamlit run app.py`，首屏红字「未配置 LLM_API_KEY」、输入框 0 个、不出现「我这边刚刚卡了一下」。复核指出的覆盖缺口已补：`test_corrupt_main_recovers_from_backup` 增加「修好后再写一轮，`.bak` 仍是合法旧版」断言（**不新增用例，仍 9 条**），并用变异测试验证（删修复语句 → `1 failed`，恢复 → `15 passed`）。记录在 `docs/evidence/2026-11-09-s03-memory.md` §8
- ✅ S06 部署准备（2026-11-08）：`app.py:24-45` 增加 `_bridge_secrets()`——线上没有 `.env`，密钥只放在 `st.secrets` 里，必须在 `import memory/agent`（`app.py:42-45`）之前把它铺进环境变量；否则 `DATA_DIR` 已被模块级常量定死，`_config_gate` 会误报缺 Key。实测：把 `.env` 改名、只留 `.streamlit/secrets.toml`（`MOCK_LLM="1"`）时 AppTest 一轮正常回复、0 错误 0 异常，`MOCK_LLM` 确由桥接注入。`main` 已 fast-forward 到 `05ad9c3` 并 push（`4ffdae7..05ad9c3`，S03–S05 全部代码进主干）；部署时**分支选 `main`、主文件路径填 `app.py`**
- ⚠️ 线上容器磁盘是临时的：Streamlit Cloud 休眠 / 重部署会清空 `data/memory/*.json`，即「记忆」只在本次运行内保留。演示时同一会话连续操作；报告与 PPT 不许写「长期记忆持久化」
- ✅ **S06 上线（2026-11-08）**：https://xinyu-mindisle.streamlit.app —— 分支 `main`、主文件 `app.py`、Python 3.11、Secrets 填 4 个键；实测打开正常、连聊 2 轮有回复、刷新后会话 id 不变（聊天记录刷新即空，是 S05 §5.2 的既定口径，不是 bug）；**tag `v0.1` 已推**。证据 `docs/evidence/2026-11-09-s06-deploy.md`。未完成：手机流量打开一次（待用户确认）
- ✅ **S07 人设卡（2026-11-08）**：`roles.py` 104 行（`SAFETY_BLOCK` + `BOUNDARIES_COMMON` + 5 张卡 × 9 字段）；`agent.build_system_prompt` 四段拼装（安全区→风格区→事实区→PHI），空事实整段省略，实测 480–532 字；`tests/test_roles.py` **5 passed（累计 20）**，contract 11/11。踩坑：第一版示例写"不要照抄"，模型仍逐字复读，改成"示例只示范语气与句长，不要复用其中任何句子"才生效。证据 `docs/evidence/2026-11-09-s07-personas.md`。未完成：**盲读 3 人**（答卷 `docs/evidence/2026-11-09-s07-blind-sheet.md`）

- ✅ **S08 规则表（2026-11-08）**：`roles.py` 104 → 267 行，`RULES` 20 条（X5 / H10 / W5，每条 11 字段）+ `COMPILED` 容错预编译 + `validate_rules()`；`contract_check.py` 增加规则校验，实测 **11/11 + 5/5 + 20/20 rules OK**，`pytest` **20 passed**。亲手做 3 类故障注入并全部捕获：坏正则（H01 → `(((`）、非法等级（W01 → `L9`）、顺序错（X01/H01 组互换）。一次性交叉核对：D-01~D-15 逐条命中预期规则、D-20/26 无命中、C-09 命中 H01。证据 `docs/evidence/2026-11-09-s08-rules.md`。口径修正：步骤示例用 `sorted()` 查 X→H→W 会因字母序 `H<W<X` 误报，已改显式 `GROUP_ORDER`；`COMPILED` 坏正则不再让 import 崩溃，改由 `validate_rules()` 报具体规则

- ✅ **S09 豁免引擎（2026-11-08）**：`guardian.py` 115 → 130 行（`split_clauses` / `_hits` / `_covered` / `_dedup` / `_raise` / `_exemption` / `_judge_clause` / `scan`）；`guardian_pre_check` 接真实判定，`guardian_post_check` 仍是 S13 空壳。**小句级**：`累死了，不想活了` = L3（`['X04','H01']`）、`笑死了，我今天想死` = L3、`不想死但是不想活` = L3；D-21~D-25 逐条符合（L1×4 / L2×1），`pytest` **26 passed**（新增 6），contract **11/11 + 5/5 + 20/20**。变异验证：只去掉切句仍 6 passed（硬词保护独立兜住），切句+硬词保护同时去掉才让回归用例变红。口径修正：`exempted` 增加 `all_hits_exempt`，W01/W04 这类不抬等级的非豁免命中也算“命中过”，避免误标 exempted。证据 `docs/evidence/2026-11-09-s09-exemption.md`

- ✅ **S10 短路与资源卡（2026-11-08）**：`resources.py` 27 行三档资源（L3×3 / L2×2 / L1 空）+ `guardian.CRISIS_REPLY`（125 字，含 12356 / 0571-87713518 / 110 / 120，无追问、无诊断词）；`app.py` 在 `call_llm` 与 `update_memory` **之前**短路 L3，直接返回 `role="crisis"`；`tests/test_guardian.py` 追加 D-01~D-10，**16 passed（累计 36）**，contract **11/11 + 5/5 + 20/20**。AppTest（`MOCK_LLM=0` + dummy 端点）：L3 `llm_calls=0`、3 张资源卡秒出、消息正常 append；普通句才调 LLM、历史重绘不出卡。口径修正：短路放 `handle()` 内而不是 `main()+st.stop()`（后者会连侧栏一起停掉）；资源顺序按 `step/S10` §5.2（12356 → 110/120 → 校心理中心），不采用 SKILL 旧顺序。未完成：**危机文案盲读 1 人**。证据 `docs/evidence/2026-11-09-s10-shortcircuit.md`

- ✅ **S11 三角色状态机（2026-11-08）**：`coordinator.py` 46 行（`ADVICE_WORDS` / `REASONS` 六枚举 / `coordinator_decide` / `enforce_cooldown`）；判定顺序 L3 → 历史危机 → 求助词 → 默认；`app.py` 接冷却（L3 置 `cooldown=COOLDOWN`、`ever_crisis=True`，先置再减 1），侧栏显示角色 / 等级 / 原因；`tests/test_flow.py` **4 passed（累计 40）**，contract **11/11 + 5/5 + 20/20**。AppTest（MOCK）：C-01 listener、C-05 guide、C-09 crisis，危机后两轮求助仍是 listener/after_crisis，清空后新会话可回 guide；0 异常。口径修正：S11 §6 期望 39 passed 是旧基数（S10 实际 36，+4 = 40）；侧栏提前接真实值（W2 要求“角色与原因可见”，S12 再补日志与中文标签）。证据 `docs/evidence/2026-11-09-s11-state-machine.md`

- ✅ **S12 结构化日志 + 侧栏（2026-11-08）**：`logger.py` 36 行（9 字段白名单 / `session_hash` sha256 前 12 位 / 写失败只 WARN）；`app.py` 在 L3 短路与正常轮各写一行（`action=short_circuit|generate`），侧栏显示 `session_hash` 前 6 位 + 轮次 + 中文等级 / 角色 / 原因 + 记忆摘要 + “清除我的记忆”；清空时旧 `.json/.bak` 真删并换新 sid、轮次归零。`tests/test_log.py` **2 passed（累计 42）**，contract **11/11 + 5/5 + 20/20**。AppTest：3 轮日志 9 字段齐全、原文泄漏 0 条；`LOG_DIR` 指向文件时仅一行 WARN、对话照常。口径修正：S12 §6 期望 41 passed 是旧基数（S11 实际 40，+2 = 42）；步骤测试的 `setenv` 在 import 后不生效，改用 `monkeypatch.setattr(logger, "LOG_DIR", …)`（与 `memory.DATA_DIR` 同口径）；L3 也写日志（SKILL 要求 L3 日志可查）。证据 `docs/evidence/2026-11-09-s12-logging-sidebar.md`。**未完成：`v0.2` tag 与提交（工作区仍压着 S08–S12 改动，待队长确认提交拆分）**

- ✅ **S13 post_check 五步链（2026-11-08）**：`guardian.py` 141 → 169 行（`DIAG` / `RESOURCE` / `SAFE_FALLBACK` / `_violations` / 五步链），`SAFE_FALLBACK["crisis"]` 直连 `CRISIS_REPLY`（兜底与短路同文）；`app.py` 只发 `fixed or 原文`，`action` 由固定 `generate` 改为执行书四值 `pass / rewrite / template_fallback`（`short_circuit` 不变）。**48 passed（+6）**，contract **11/11 + 5/5 + 20/20**；AppTest 把 `agent.call_llm` 换成固定返回「你这是抑郁症，建议服药」→ 界面只有兜底句、日志 `action=template_fallback`、原文泄漏 0；干净回复原样通过不误伤。口径修正：`rewrite` 只记“真的重写过”，本步 `rewriter=None`，所以被拦是 `rewrite=0 + template_fallback=True`，W3 的“`rewrite=1`”留给 S14 截图；`pass=False` 不是“不发”。证据 `docs/evidence/2026-11-09-s13-postcheck.md`

**下一步（S14）**：按 `step/S14-*.md` 把 `rewriter` 接上 LLM 复核与重写，失败按“不通过”处理。

- ✅ **规则缺口补丁 + 复核四项收尾（2026-11-08）**：`roles.py` 只改 4 条正则（X01 否定句补"没有想过/从没想过要"、X03 补"论文/作业/报道"反向分支、H04 补"天台 + 跳下去"并负向断言排除游泳、H06 补"买/囤 + 安眠药"）；`tests/test_guardian.py` +5 条 `GAP_CASES`（D-29~D-32 + 一条护栏），先红后绿；**53 passed**，contract **11/11 + 5/5 + 20/20**。执行书同步升 **v1.2**（附录 B 四条正则 + 变更记录 + 新增附录 D-5，注明不计入分母）。四处决策的处理：①证据日期**不改名**，13 个证据文件头加"实际生成于 2026-11-08"；②规则按上一条补；③S08–S13 拆 5 个提交 + `v0.2`；④执行书 :1128 的"39 passed"旧基数不动。证据 `docs/evidence/2026-11-08-rule-gap-patch.md`

- ✅ **README 修正（2026-11-08）**：状态行从"S02 完成"改到 S13 实际口径；删掉 agent.py 的"流式"（没实现）；guardian / contract_check / tests 的描述改为真实内容；theme.py / metrics.py 标注"S19 / S24 计划"（当时**尚不存在**）。

## 5. 关键约束与红线

### 5.1 三条铁律（架构层面，违反即返工）

1. **只升不降**：任何一层失败（规则异常、LLM 超时、JSON 解析失败），风险等级只能上调；绝不因为"另一处判断没事"而下调。函数里出现等级判断，必须写注释"为什么不能降"。
2. **否决权唯一**：`guardian` 判定不通过，就是不发。没有申诉、没有投票、没有"综合平均"。
3. **责任不越界**：`coordinator` 只决定"现在是谁"（角色），`guardian` 只决定"这句能不能发"（内容）。两者禁止互相调用对方内部逻辑。

### 5.2 安全红线（老师会看，也是唯一真红线）

- **不诊断**：不出现"你得了 / 你有…倾向 / 你可能是抑郁症"。全项目搜索这三个词，只能出现在"禁止出现"的说明里。
- **不承诺保密**：用户问"你会告诉别人吗"，标准答案是"我不会主动告诉任何人，但如果我有理由相信你处于危险中，我会建议你联系真人"。
- **危机必给资源**：L3 短路时必须出 120 / 110 / 12356 / 校心理中心 0571-87713518 四张卡之一，不许只回一句"要坚强"。
- **不只靠 LLM 判危**：规则层（`RULES` 20 条）必须独立可跑；LLM 复核是加分项，不是唯一防线。
- **"不想死" ≠ "不想活"**：先跑豁免正则，再跑命中。`我不想死` 不许触发 crisis。
- **演示只用虚构用例**：全部来自执行书附录 C，绝不用真人倾诉。

### 5.3 范围红线（六级砍单，按顺序砍，不许跳级）

| 级 | 砍什么 | 触发条件 |
|---|---|---|
| 1 | 三套主题 → 一套 | W3 周三还没跑通主题切换 |
| 2 | 迷你 Lorebook（`match_lore`） | W3 周二没跑通 |
| 3 | 五个角色 → 三个（保留 listener 默认 / crisis / guide） | W2 周五人设盲读不达标 |
| 4 | 情绪打卡与趋势图 | S3 结束仍无余量 |
| 5 | 记忆面板的可视化 → 只留"清空"按钮 | W3 周四 |
| 6 | 会话聚合（`N_WINDOW`）→ 单轮判定 | 只剩 2 天 |

**砍单只砍体验，不砍安全与测试。** `guardian.py`、`RULES` 20 条、97 条测试（考核 48）、免责声明、资源卡，任何情况下都不许砍。

### 5.4 术语红线（报告 / PPT / 答辩 / README 都算）

| 禁止 | 改说 |
|---|---|
| 多智能体 / Multi-Agent | 三段职责隔离 / 角色状态机 + 否决层 |
| 多模态 | 静态资源路由（rule-based resource routing） |
| 能识别所有危机 | 对测试集内的危机表达有规则级覆盖 |
| 有效缓解焦虑 | 完成交互功能验证，不声称疗效 |
| AI 心理医生 / 咨询师 | 对话工具 / 陪伴工具 |

代码注释里也别写"Agent 1/2/3"，写 `listener/guide/crisis` 或 `coordinator/guardian`。

### 5.5 数据红线

- `memory.json` 只允许 8 个白名单字段（`preferred_tone / current_role / role_switch_reason / emotion_tags / unresolved_issues / coping_preferences / rolling_summary / last_updated`）+ `summary_at_turn`。
- 绝不写入：人名、地名、学校、病历、药物、身份证、原文摘录。`update_memory` 里必须有 `scrub()` 兜底。
- **`scrub()` 只覆盖手机 / 证件 / 邮箱 / 链接 / 学校名，认不出人名**（实测 `杭州电子科技大学的张三` → `[学校]张三`）。
  人名的防线不是正则，而是“只写标签与摘要、不写原句”；`rolling_summary` 由模型生成，prompt 里已明令禁止人名（S17）。
  验收时说“自动脱敏覆盖五类”，不许说“绝不会出现人名”。
- 日志只记 `session_hash` 与字段，**不记用户原文**。
- 用户点"清空"必须真删（含备份），并给出确认提示。

### 5.6 技术红线

- 单个 `.py` ≤ 350 行；单函数 ≤ 40 行。超了就拆，别硬写。
- 所有 LLM 调用：`timeout=15`、`max_retries=1`、失败走 `safe_default()`，不许让异常冒到界面。
- 所有 LLM 返回的 JSON：`try/except` + 兜底，解析失败按"中风险"处理，不按"没事"处理。
- 魔法数字进常量区，不许散落。
- 不 `print` 用户原文；不在前端展示日志原文（`data/logs/*.jsonl` 只有哈希与字段）。
- `requirements.txt` **只许 ASCII**：旧版 pip 按系统 locale（本机 GBK）读它，中文注释会直接 `UnicodeDecodeError`（2026-11-09 真实踩到）。

## 6. 工作方式与状态维护

### 6.1 分工（执行书 §6.1）

| 成员 | 主责 | 备份 |
|---|---|---|
| P1 队长 | `memory.py`、契约、整合、进度 | P2 |
| P2 | `agent.py`、人设 prompt | P1 |
| P3 | `guardian.py`、`RULES` | P4 |
| P4 | `coordinator.py` | P3 |
| P5 | `app.py`、`resources.py`、主题 | P6 |
| P6 | 测试、部署、文档、录屏 | P5 |

结对：P1-P2 / P3-P4 / P5-P6，每天 15 分钟互看。备份接手的标准是"30 分钟内能让 demo 跑起来"。

### 6.2 一次任务的标准动作

1. **对齐**：读本文件 §2.2 与 §4，确认当前步和出口。
2. **定位**：只读相关的 `SKILL.md` 一节，不要全文读。
3. **改**：最小改动；安全相关改动必须写 `[SAFE]` 标记与理由。
4. **验**：`pytest -q` + `python contract_check.py` + 手动跑一遍受影响路径。
5. **证**：留下截图 / 日志 / 测试输出到 `docs/evidence/`，文件名带日期。
6. **报**：说清"改了什么 / 怎么验的 / 还剩什么"。

### 6.3 状态怎么更新

改完一个出口 → 改 §2.2 状态 → 在 §4 加一行日期与结果 → 周五打 tag。**没更新本文件 = 没做。**

### 6.4 Git

- `main` 保护；每人 `p1-memory` 式分支；周五合并窗口；PR 至少 1 人 review。
- 提交信息：`feat(guardian): 增加第三人称降级` / `fix(memory): 摘要超长截断`。
- 每天收工前 push 自己分支。禁 `push -f`，禁提交 `.env` 与真实对话。

## 7. 常用命令

```bash
# 环境（本机裸 python = Anaconda 3.14，必须用 py -3.11）
py -3.11 -m venv .venv
.venv\Scripts\activate
python -V                                    # 必须是 3.11.x
pip install -r requirements.txt

# 跑
streamlit run app.py
set MOCK_LLM=1 && streamlit run app.py      # 离线演示

# 验
python contract_check.py                     # 期望 11/11 signatures OK
pytest -q
pytest tests/test_guardian.py -q -k crisis   # 单跑高危用例

# 维护
python -c "from memory import clear_memory; clear_memory('demo')"
```

## 8. 验收底线（达不到 = 这周没过）

**W1**：在线可开、10 轮不崩、记忆落盘、免责声明、11/11、MOCK 可跑。
**W2**：C-09 切 crisis、C-01 不误触、日志无原文、角色与原因可见、人设盲读 ≥2/3 分对。
**W3**：重写日志有记录、风险地板不掉、单字段可删可清空、3 主题不错位、lore 可命中。
**W4**：12 对话全过、28 规则高危召回 ≥90% / 误拦 ≤15%、连续 10 轮 10/10、8 故障有记录、5 分钟录屏。

**Gate A（教学班推荐截止 = 第 12 周）**：四份材料齐 —— 文档 .docx、PPT 17 页、视频 300 秒 ≤100MB、仓库 public；首页写明赛题一。**缺视频 = 直接丢 25 分。**
**Gate B（第 15 周决赛）**：5 分钟现场三幕 + 四问脱稿 + 数据一页。
**四项安全保险**（免责声明 / 资源卡核验 / 全文无诊断结论 / 演示全虚构）半天内完成，不许省。

## 9. 注意事项（真实踩过的坑）

- **别先写界面**。先把 `contract_check.py` 和 `call_llm` 跑通，否则界面会变成假数据展览。
- **别让人设 prompt 越权**。人设只改"语气 / 称呼 / 长度"，不许改安全区。危机模板永远由 `guardian` 提供，不由人设生成。
- **规则别写太宽**。第一版宁可漏（漏了有 LLM 复核兜），不要误拦（误拦会让学生觉得"这系统有病"）。但 L3 宁可误报。
- **Streamlit 的状态会丢**。`st.session_state` 不持久，刷新即空；需要跨刷新的东西一律进 `memory.json`。
- **云端密钥**。Streamlit Cloud 用 Secrets，仓库里只留 `.env.example`；一旦泄露立刻换 key。
- **演示别赌网络**。三份备份：本机 + 手机热点 + 录屏。彩排卡一次就改路径。
- **报告里的数字必须能对上测试表**。写"召回 92%"就要有 28 条逐条记录，否则等于自证造假。