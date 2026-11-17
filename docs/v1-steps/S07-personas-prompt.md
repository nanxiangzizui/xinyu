# S07 · 五张人设卡 + prompt 分区装配

| 项 | 内容 |
|---|---|
| 步骤 | S07 / 26 |
| 阶段 | W2 |
| 工时 | 5 人时（P2） |
| 风险 | **中**——人设越权会污染安全区，这是本项目最容易"悄悄变坏"的地方 |
| 依赖 | S05 |
| 回滚 | `git checkout -- roles.py agent.py`（prompt 改动不动数据） |

## 1 这一步做什么

让"同一个模型"听起来像五个人，同时保证**五个人的安全底线完全一样**。

产出：

1. `roles.py` 里的 `PERSONAS`（5 张卡，字段固定 9 个）
2. `agent.build_system_prompt` 真实实现：**安全区 → 风格区 → 事实区 → PHI** 四段拼装
3. `tests/test_roles.py` 4 条（含"五卡安全区逐字相同"）

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 数据 | 纯 dict / list | 不用 dataclass，不用 pydantic（不为未来抽象） |
| 拼装 | f-string | 分段用固定小节标题，方便日后 diff |
| 校验 | pytest | 断言字符串包含/不包含，不测模型输出 |

## 3 前置检查

```powershell
pytest -q                  # 15 passed（memory 9 + agent 6）
set MOCK_LLM=1
streamlit run app.py       # 能聊，但五个人听起来一样
```

## 4 硬要求

1. **安全区逐字相同**：五张卡共用一个 `SAFETY_BLOCK` 常量，**不许**在卡里写各自的安全句子。
2. 人设只能改四样：**称呼 / 语气 / 句长 / emoji**。改不了安全区、改不了资源卡文案。
3. `boundaries `（合规层）**五卡同文**；`taboos`（体验层）每卡可微调。两层不许合并。
4. 每卡 3 轮 `mes_example`，三条硬约束：**不出现建议句、每轮留开口、不出现诊断词**。
5. prompt 总长 ≤ 1200 字（含事实区），超了砍事实区，不许砍安全区。

## 5 执行步骤

### 5.1 九字段卡结构

```python
PERSONAS = {
    "sister_heart": {
        "name": "知心姐姐",
        "tone": "温暖、慢一点、多用短句",
        "address": "你",
        "sentence_len": 25,          # 参考长度（字）
        "emoji": "少（≤1 个/条）",
        "boundaries": BOUNDARIES_COMMON,     # 五卡同一份
        "taboos": ["不说'我理解你'这种空话"],
        "mes_example": [("我最近好累", "..."), ("嗯", "..."), ("谢谢", "...")],
        "post_history_instructions": "回复前先确认对方此刻的情绪，再开口。",
    },
    # warm_senpai / rational_mentor / energy_buddy / quiet_hollow 同结构
}
```

五张卡的分工（写报告时直接用）：

| id | 名字 | 语气 | 句长 | 适合谁 |
|---|---|---|---|---|
| `sister_heart` | 知心姐姐 | 温暖慢 | 25 | 默认 |
| `warm_senpai` | 温柔学长 | 平视、带一点经验 | 30 | 学业压力 |
| `rational_mentor` | 理性导师 | 清晰、少情绪词 | 20 | 要梳理问题 |
| `energy_buddy` | 元气同伴 | 轻快、有活力 | 20 | 低落但不想被可怜 |
| `quiet_hollow` | 沉稳树洞 | 极简、几乎不评价 | 15 | 不想被追问 |

> `quiet_hollow` 最难写：**极简不等于冷漠**。判据——它每条回复都要留一个"你可以说也可以不说"的余地。

### 5.2 安全区（唯一，五卡共享）

```python
SAFETY_BLOCK = """你是情绪陪伴对话工具，不是心理咨询师，也不是医生。
1. 不做任何诊断：不说"你得了""你有…倾向""你可能是抑郁"。
2. 不承诺保密：被问"你会告诉别人吗"，回答"我不会主动告诉任何人，但如果我有理由相信你处于危险中，我会建议你联系真人"。
3. 不说教：不说"你应该""你必须""别想太多""这没什么""我当年""你要坚强"。
4. 不追问危机细节：不要求对方描述方法、时间、地点。
5. 不提供医疗建议：不推荐药物、剂量、疗法。
6. 回复控制在 3 句以内；对方没有明确求助时，不给建议。"""
```

### 5.3 四段拼装（顺序固定，S05 的管线依赖它）

```python
def build_system_prompt(persona_id: str, memory: dict, lore: list[str]) -> str:
    p = PERSONAS.get(persona_id) or PERSONAS["sister_heart"]
    return "\n\n".join([
        "[安全守则]\n" + SAFETY_BLOCK,                       # ① 安全区
        "[你的说话方式]\n" + _style_block(p),                # ② 风格区
        "[你记得的事]\n" + _facts_block(memory, lore),       # ③ 事实区
        "[最后提醒]\n" + p["post_history_instructions"],     # ④ PHI
    ])
```

**顺序不能变**：安全区在最前（模型对开头最敏感）、PHI 在最后（紧贴用户输入）。
事实区在中间——它是唯一可能为空的一段，空了就整段省略，不要留空标题。

`_style_block` 只做四件事：称呼、语气、句长、emoji + `taboos` + 3 轮 `mes_example`（以"示例（照这个语气，不要照抄内容）"开头）。
`_facts_block` 只放：`preferred_tone / emotion_tags / unresolved_issues / rolling_summary` + `lore` 条目，**不放历史对话**。

### 5.4 三条 mes_example 硬规则（写完自查）

| 规则 | 反例 | 正例 |
|---|---|---|
| 不出现建议句 | "你可以试试每天跑步" | "听起来这周挺熬人的。" |
| 每轮留开口 | "那就这样吧。" | "想说说是什么时候开始的吗？不想说也没关系。" |
| 不出现诊断词 | "你这是焦虑" | "这种紧绷感挺磨人的。" |

> 示例比规则更能塑造语气。**写歪一句示例，等于把安全区削薄一层**——所以三卡写完必须交叉审。

### 5.5 测试（4 条）

| # | 用例 | 断言 |
|---|---|---|
| 1 | 五卡跑 `build_system_prompt` | 五个 prompt 的 `SAFETY_BLOCK` 部分**逐字相同** |
| 2 | 同上 | 每个 prompt 都含"不承诺保密"与"3 句以内" |
| 3 | 未知 persona_id | 回退到 `sister_heart`，不抛异常 |
| 4 | 空 memory + 空 lore | 不出现 `[你记得的事]` 空标题 |

```python
def test_safety_block_identical():
    prompts = [build_system_prompt(pid, {}, []) for pid in PERSONAS]
    assert len({p.split("[你的说话方式]")[0] for p in prompts}) == 1
```

## 6 验证

### 6.1 自动

```powershell
pytest tests/test_roles.py -q          # 4 passed
python contract_check.py               # 11/11
```

### 6.2 盲读（W2 验收的硬指标）

1. 五个人设各生成 3 条回复（用同一批输入：`我最近好累` / `不想说话` / `谢谢你`）
2. 只保留回复文本，**去掉人设名**，打乱顺序
3. 找 3 个没参与的同学，让他们猜"这句是谁说的"
4. **≥2 人分对 ≥3 组**才算过；否则回 §5.1 改语气，别改安全区

> 盲读不过通常不是 prompt 不够长，而是**五个人写得像同一个人的五种客套**。
> 最快的修法：给每张卡定一条"绝不做的动作"（如 `rational_mentor` 绝不用感叹号、`energy_buddy` 绝不说"我理解你"）。

## 7 回滚

```powershell
git checkout -- roles.py agent.py tests/test_roles.py
```

盲读结果的截图存 `docs/evidence/`，文件名带日期与人名（谁读的）。

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 五卡回复几乎一样 | 风格区只改了"名字" | 必须改句长与"绝不做的动作" |
| 人设开始给建议 | 示例里有建议句 | 按 §5.4 逐条重写示例 |
| 危机时人设抢戏 | 危机模板没走 Guardian | 危机回复**永远**由 `resources` 提供，不进人设（S10 保证） |
| prompt 太长导致变慢 | 事实区塞了历史 | 事实区只放 4 个字段 + lore |
| 盲读时被认成同一个 | 三个人都用了"嗯，我在" | 换开场：称呼词、句首词必须不同 |

## 9 出口清单

- [ ] `pytest tests/test_roles.py -q` = 4 passed
- [ ] 五段安全区逐字相同（测试保证）
- [ ] 盲读 ≥2/3 人分对 ≥3 组（截图）
- [ ] 五卡都没有建议句 / 诊断词
- [ ] `contract_check.py` 11/11

## 10 回执

```text
S07 完成：5 卡 / 安全区逐字同 / 盲读 3 人中对 __ 组 / 4 passed
下一步：S08 RULES 20 条
```
