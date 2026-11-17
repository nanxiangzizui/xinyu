# 心屿 MindIsle

> 面向大学生的情绪陪伴对话系统 —— 编排式单 Agent + 三角色状态机 + 安全否决层。
> 不做诊断，不替代真人，不做"多智能体"的表演。

**这是一个课程实践项目。** 它演示的是"如何把安全边界写进系统结构"，而不是"AI 能治好谁"。

## 现在是什么状态

| | |
|---|---|
| 计划 | ✅ 执行书已冻结（文件内版本 v1.2）|
| 代码 | ✅ **v3.0**（2026-11-17，`main` + `agent-v2`，`v1.0` / `v2.0` 为回退点）：P0–P10 完成；`pytest` **348 passed**；`contract_check` **11/11 + 5/5 + 20/20**；四指标 10/10、0/20、12/12、10/10；双模式角色卡、建卡期真实检索、A 情景记忆 + B 角色卡长期记忆；线上 <https://xinyu-mindisle.streamlit.app> |
| 材料 | 🟨 四份齐：[项目文档](docs/01_项目文档.docx)（**26 页**，正文 16 页 + 附录 A–D）· [项目方案](docs/02_项目方案.pptx)（**17 页**）· [演示视频](docs/03_演示视频.mp4)（**300 秒，仍是 v1 合成版，待重录**）· [原型说明](docs/04_原型说明.md)；**材料数字仍是 v2.0 口径**（176 / 167 文件），v3 重打包时统一回填 348；现场彩排待做 |
| 交付 | 4 周出可演示版本 + 3 天材料期，6 人小队 |
| 赛事 | 杭州电子科技大学第二届 AIGC 应用创新大赛 · **赛题一（AI 辅助开发·创意产品原型）** |

## 交什么（比赛规格）

预赛 100 分 = 学术诚信与 AI 使用规范 12.5 + 项目文档 25 + **项目方案 PPT 37.5** + 演示视频 25。**代码不单独计分**，功能做到"能演"即停手，时间给材料。

| 材料 | 硬规格 |
|---|---|
| 项目文档 | `.docx`，正文 12–16 页，末尾**附录 A：AI 使用说明**（关键 Prompt / 迭代过程 / 人工核查）|
| 项目方案 | `.pptx` 17 页（上限 20）|
| 演示视频 | MP4 **300 秒**、≤100MB、全程录屏 + 解说，必须含"断网仍出危机卡"|
| 仓库 | public（可选加分项）|

要求原文与逐页/逐镜脚本：[docs/比赛要求对照与提交计划.md](docs/比赛要求对照与提交计划.md)、[docs/AIGC大赛通知-2026.docx](docs/AIGC大赛通知-2026.docx)。所有材料首页都写"参赛赛题：赛题一"。

## 读哪里（按顺序）

1. **`心屿MindIsle_工程执行书_v1.0.md`** —— 唯一执行依据。范围、机制、排期、测试、演示全在里面。
2. **`.claude/CLAUDE.md`** —— 当前进度、分步骤表、红线。**状态只认这里。**
3. **`.claude/skills/xinyu-dev/SKILL.md`** —— 怎么做：每周的具体步骤、出口、坑。
4. **`.cursor/rules/xinyu.mdc`** —— 写代码时常驻的硬规则摘要。

冲突时：用户最新指令 > 执行书 > `CLAUDE.md` > `SKILL.md` > `.mdc`。

## 三条铁律

1. **只升不降** —— 任何一层失败，风险等级只能上调，绝不因"别处说没事"而下调。
2. **否决权唯一** —— Guardian 说不行就是不行，其他节点没有申诉通道。
3. **责任不越界** —— 状态层只决定"现在是谁"，审查层只决定"这句能不能发"。

## 快速开始（本机已可用）

```bash
py -3.11 -m venv .venv          # 本机裸 python 是 Anaconda 3.14，必须指定 3.11
.venv\Scripts\activate
python -V                        # 必须是 3.11.x
pip install -r requirements.txt
copy .env.example .env          # 填 LLM_API_KEY
streamlit run app.py
```

离线演示（无网络也能跑）：

```bash
set MOCK_LLM=1
streamlit run app.py
```

自检：

```bash
python contract_check.py    # 11/11 signatures OK
pytest -q
```

## 项目结构

```text
心屿/
├─ 心屿MindIsle_工程执行书_v1.0.md   ← 唯一执行依据
├─ README.md                          ← 本文件
├─ app.py            Streamlit 页面：聊天 / 侧栏 / 免责声明 / 资源卡 / 代码来源链接
├─ orchestrator.py   ★v2 P1/P4：九节点编排 + trace + 异常兜底（页面只调 safe_run）
├─ agent_loop.py     ★v2 P2/P4：受控工具循环（步数 / 工具次数 / 总超时 / 门禁 / 来源过滤）
├─ tools.py          ★v2 P2：白名单 / schema / 执行 / 超时 / 大小上限
├─ web.py            ★v2 P3a：web_search（scrub / 七类错误码 / 来源校验）
├─ style.py          ★v2 P5a：口吻层（句尾 / tone hint / 活人感规则，只润色复核通过的输出）
├─ rolecard.py       ★v3：角色卡校验 / B 模式 prompt / 免责与对话规则
├─ rolecard_ui.py    ★v3：建卡 gate / B 模式聊天 / 自动盲点补全
├─ rolecard_form.py  ★v3：建卡表单 / 认知编辑 / 继承上一张卡
├─ rolecard_enrich.py / rolecard_focus.py / rolecard_gap.py / rolecard_wiki.py  ★v3：建卡期检索与盲点
├─ episode_store.py  ★v3：A 情景记忆（24 条，cue 召回）
├─ memory_extract.py ★v3：每 5 轮一次 LLM 抽取（A 情景 / B 卡记忆）
├─ rolecard_memory.py ★v3：B 角色卡长期记忆（60 条）
├─ chat_ui.py        ★v3：A/B 共用聊天渲染 / 连发合并 / 轮次
├─ agent.py          call_llm / build_system_prompt / safe_json / 重试 / MOCK 剧本（生成 / 摘要 / 复核 / 重写）
├─ roles.py          5 套人设卡 + RULES 20 条（唯一来源）
├─ coordinator.py    三角色状态机 + 会话聚合 + 只升不降
├─ guardian.py       规则扫描 → 豁免 → 分级 → 复核 → 重写 / 复检 / 安全兜底 / 工具门禁（短路在 orchestrator.py）
├─ memory.py         白名单读写 + 摘要节流 + 脱敏 + 备份 + 坏文件自愈 + 一键清空 + 迷你 Lorebook
├─ resources.py      情绪标签 → 资源卡
├─ logger.py         结构化日志（9 字段，不写用户原文）
├─ panel.py          记忆面板（8 字段只读 / 两字段编辑 / 导出 / 清空）+ 本轮编排 trace（P4）
├─ theme.py          三套配色 sakura / matcha / sunset + CSS 变量注入
├─ metrics.py        四指标脚本（只读测试集，不调模型）
├─ contract_check.py 11 个签名 + 5 个常量 + 20 条规则校验
├─ docs/v1-steps/    S01–S26 分步执行手册（v1 历史，只读；原 step/ 已归档到这里）
├─ tests/            v1 基线 132 + v2/v3 增量 216 = 348
│                    test_guardian / memory / flow / theme / agent / roles / log / fault / metrics
│                    test_orchestrator / tools / agent_loop / web / tool_gate / style / speech / turn
│                    test_knowledge / rolecard / rolecard_flow / rolecard_app / rolecard_enrich
│                    test_rolecard_gap / rolecard_wiki / episode_store / memory_extract / rolecard_memory
│                    —— 合计 348（考核要求 48）
├─ data/memory/      memory.json（不进仓库）
└─ docs/             项目文档、PPT、证据、比赛要求
   └─ v2-steps/      P1–P6 编排式单 Agent 分步执行手册（v2 增量）
```

## 边界（写死，不许漂移）

- **做**：倾听 / 在合适时机给方向 / 危险时短路并给资源 / 记住少量结构化信息 / 让用户随时删记忆
- **不做**：诊断疾病、给药物剂量、真实危机干预、语音视频、向量记忆、多 Agent 投票、前后端分离
- **不说**：多智能体、多模态、心理医生、能识别所有危机、有效缓解焦虑（详见执行书 §1.3 禁用词表）

## 危机资源（已内置，改前先确认可拨）

120 / 110 ｜ 全国心理援助热线 12356 ｜ 学校心理中心 0571-87713518（工作日）

## 许可与声明

课程实践作品，非医疗器械、非心理服务。所有演示对话均为虚构用例（执行书附录 C），不含真实用户数据。