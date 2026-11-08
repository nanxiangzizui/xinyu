# 心屿 MindIsle

> 面向大学生的情绪陪伴对话系统 —— 三角色状态机 + 安全否决层。
> 不做诊断，不替代真人，不做"多智能体"的表演。

**这是一个课程实践项目。** 它演示的是"如何把安全边界写进系统结构"，而不是"AI 能治好谁"。

## 现在是什么状态

| | |
|---|---|
| 计划 | ✅ 执行书已冻结（文件内版本 v1.1）|
| 代码 | 🟨 S1 完成、S2 主体落地、S13 完成：`pytest` **53 passed**，`contract_check` **11/11 + 5/5 + 20/20**；S2 还剩人设/危机文案盲读与 `v0.2` tag |
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
├─ app.py            Streamlit 页面：聊天 / 侧栏 / 免责声明 / 资源卡 / 记忆面板
├─ agent.py          call_llm / build_system_prompt / safe_json / 重试 / MOCK 三剧本
├─ roles.py          5 套人设卡 + 3 套主题 + RULES 20 条（唯一来源）
├─ coordinator.py    三角色状态机 + 会话聚合 + 只升不降
├─ guardian.py       规则扫描 → 豁免 → 分级 → 复核 → 重写 / 复检 / 安全兜底（短路在 app.py）
├─ memory.py         白名单读写 + 备份 + 坏文件自愈 + 一键清空 + match_lore（200 字摘要 S17 接）
├─ resources.py      情绪标签 → 资源卡
├─ logger.py         结构化日志（9 字段，不写用户原文）
├─ theme.py          三套配色 sakura / matcha / sunset（S19 计划）
├─ metrics.py        四指标脚本（S24 计划，只读测试集）
├─ contract_check.py 11 个签名 + 5 个常量 + 20 条规则校验
├─ step/             S01–S26 分步执行手册（怎么做看这里）
├─ tests/            test_guardian(22) / test_memory(9) / test_agent(6) / test_roles(5)
│                    test_flow(4) / test_log(2) —— 合计 48（考核口径）
├─ data/memory/      memory.json（不进仓库）
└─ docs/             项目文档、PPT、证据、比赛要求
```

## 边界（写死，不许漂移）

- **做**：倾听 / 在合适时机给方向 / 危险时短路并给资源 / 记住少量结构化信息 / 让用户随时删记忆
- **不做**：诊断疾病、给药物剂量、真实危机干预、语音视频、向量记忆、多 Agent 投票、前后端分离
- **不说**：多智能体、多模态、心理医生、能识别所有危机、有效缓解焦虑（详见执行书 §1.3 禁用词表）

## 危机资源（已内置，改前先确认可拨）

120 / 110 ｜ 全国心理援助热线 12356 ｜ 学校心理中心 0571-87713518（工作日）

## 许可与声明

课程实践作品，非医疗器械、非心理服务。所有演示对话均为虚构用例（执行书附录 C），不含真实用户数据。
