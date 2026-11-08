# 心屿 MindIsle · 项目状态与规则

> **本文件是唯一状态源。** 其他文件（SKILL.md、README、.mdc）只讲方法、格式和摘要，状态一律以这里为准。
> 最后更新：2026-11-09（计划期结束，代码期尚未开始）

## 0. 三分钟了解

一句话：**情绪陪伴对话系统。它在"倾听 / 引导 / 危机"三种状态间自动迁移，并有一个一票否决的安全审查层。不做"多智能体"的表演，只做清晰的责任边界。**

- 形态：Streamlit 单页聊天 + 侧栏状态 + 记忆面板 + 资源卡
- 交付：4 周出一个可演示版本 + 3 天材料期，6 人小队
- 尺度：课程实践作业。安全设计要真实，疗效一句不吹
- 规模：11 个 py 文件（约 1200 行）+ 97 条测试（考核口径 48）+ 8 节报告

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
| 语言 | Python 3.11 | 不用 3.12+ 的新语法，学校机房可能是 3.11 |
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
| S1 | W1 | ⬜ | §7.1 | 仓库 / 骨架 / `agent.py` / `memory.py` 空壳 / `app.py` / 部署 | 在线可打开 + 10 轮不崩 + `contract_check` 11/11 + `v0.1` |
| S2 | W2 | ⬜ | §7.2、§4.3、§4.6、§4.7 | 五套人设 + 状态机 + `guardian_pre_check` | C-09 切 crisis；C-01 不误触；日志无原文 + `v0.2` |
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
- ⬜ 6 人是否都会 Python 未确认（W1 周一环境检查后回填）

**下一步（W1 周一）**：`git init` 建仓 → 按 `step/S01-env-setup.md` 开始，一次只做一步。先跑通 `contract_check.py` 11/11，再做功能。

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
- 日志只记 `session_hash` 与字段，**不记用户原文**。
- 用户点"清空"必须真删（含备份），并给出确认提示。

### 5.6 技术红线

- 单个 `.py` ≤ 350 行；单函数 ≤ 40 行。超了就拆，别硬写。
- 所有 LLM 调用：`timeout=15`、`max_retries=1`、失败走 `safe_default()`，不许让异常冒到界面。
- 所有 LLM 返回的 JSON：`try/except` + 兜底，解析失败按"中风险"处理，不按"没事"处理。
- 魔法数字进常量区，不许散落。
- 不 `print` 用户原文；不在前端展示 `guardian_log` 原文。

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
# 环境
python -m venv .venv && .venv\Scripts\activate
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

**最终提交**：执行书 §12 的清单逐项打勾；四项安全保险（免责声明 / 资源卡核验 / 全文无诊断结论 / 演示全虚构）半天内完成，不许省。

## 9. 注意事项（真实踩过的坑）

- **别先写界面**。先把 `contract_check.py` 和 `call_llm` 跑通，否则界面会变成假数据展览。
- **别让人设 prompt 越权**。人设只改"语气 / 称呼 / 长度"，不许改安全区。危机模板永远由 `guardian` 提供，不由人设生成。
- **规则别写太宽**。第一版宁可漏（漏了有 LLM 复核兜），不要误拦（误拦会让学生觉得"这系统有病"）。但 L3 宁可误报。
- **Streamlit 的状态会丢**。`st.session_state` 不持久，刷新即空；需要跨刷新的东西一律进 `memory.json`。
- **云端密钥**。Streamlit Cloud 用 Secrets，仓库里只留 `.env.example`；一旦泄露立刻换 key。
- **演示别赌网络**。三份备份：本机 + 手机热点 + 录屏。彩排卡一次就改路径。
- **报告里的数字必须能对上测试表**。写"召回 92%"就要有 28 条逐条记录，否则等于自证造假。