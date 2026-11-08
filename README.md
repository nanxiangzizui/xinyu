# 心屿 MindIsle

> 面向大学生的情绪陪伴对话系统 —— 三角色状态机 + 安全否决层。
> 不做诊断，不替代真人，不做"多智能体"的表演。

**这是一个课程实践项目。** 它演示的是"如何把安全边界写进系统结构"，而不是"AI 能治好谁"。

## 现在是什么状态

| | |
|---|---|
| 计划 | ✅ 执行书 v1.0 已冻结（见下方"读哪里"）|
| 代码 | ⬜ 0 行，等 W1 |
| 目标 | 4 周交付 + 3 天材料期，6 人小队 |

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

## 快速开始（W1 完成后才有）

```bash
python -m venv .venv
.venv\Scripts\activate
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
├─ agent.py          call_llm / build_system_prompt / 流式 / 重试 / MOCK
├─ roles.py          5 套人设卡 + 3 套主题 + RULES 20 条（唯一来源）
├─ coordinator.py    三角色状态机 + 会话聚合 + 只升不降
├─ guardian.py       规则扫描 → 豁免 → 分级 → LLM 复核 → 短路 / 重写 / 复检 / 日志
├─ memory.py         白名单读写 + 200 字摘要（每 5 轮）+ 备份 + 一键清空 + match_lore
├─ resources.py      情绪标签 → 资源卡
├─ contract_check.py 11 个函数签名校验
├─ tests/            test_guardian.py(28) / test_flow.py(12) / test_fault.py(8)
├─ data/memory/      memory.json（不进仓库）
└─ docs/             报告素材、测试表、证据截图
```

## 边界（写死，不许漂移）

- **做**：倾听 / 在合适时机给方向 / 危险时短路并给资源 / 记住少量结构化信息 / 让用户随时删记忆
- **不做**：诊断疾病、给药物剂量、真实危机干预、语音视频、向量记忆、多 Agent 投票、前后端分离
- **不说**：多智能体、多模态、心理医生、能识别所有危机、有效缓解焦虑（详见执行书 §1.3 禁用词表）

## 危机资源（已内置，改前先确认可拨）

120 / 110 ｜ 全国心理援助热线 12356 ｜ 学校心理中心 0571-87713518（工作日）

## 许可与声明

课程实践作品，非医疗器械、非心理服务。所有演示对话均为虚构用例（执行书附录 C），不含真实用户数据。
