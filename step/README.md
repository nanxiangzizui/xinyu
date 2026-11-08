# step/ · 心屿 MindIsle 分步执行手册

**26 个可独立验证、可独立回滚的步骤。** 按编号顺序做，每一步结束时仓库必须是"绿"的：
`contract_check.py` 11/11、`pytest -q` 全过、界面能点开。

> 本目录只讲**怎么做**。做什么、为什么这么做，看 `心屿MindIsle_工程执行书_v1.0.md`；
> 红线与进度看 `.claude/CLAUDE.md`。三者冲突时：执行书 > 本目录 > 其他。

---

## 0 怎么用这套文件

1. 开工前只读本文件 §3（全局约定，10 分钟）。后面 26 个文件不再重复这些内容。
2. **一次只做一步**，不要跳步，不要同时改两个模块。
3. 每个文件固定五段：**§3 前置检查 → §5 执行 → §6 验证 → §7 回滚（先看一眼）→ §9 出口**。
   验证不过，不许进下一步；先进 §7 回滚。
4. 通过后四件事：`git commit` → 打 tag（文件里标了 tag 才打）→ 更新 `CLAUDE.md` §2.2 状态 → 把 §10 回执填一句发群里。
5. 时间不够时**只按 `CLAUDE.md` §5.3 六级砍单顺序砍**，不许自己挑着砍安全模块。

---

## 1 总览表

| 步 | 名称 | 周 | 人时 | 风险 | 依赖 | 关键产出 |
|---|---|---|---|---|---|---|
| S01 | 环境与仓库初始化 | W1 | 3 | 低 | — | 可跑的空工程 |
| S02 | 六文件骨架 + 契约校验 | W1 | 4 | 低 | S01 | 11/11 签名 |
| S03 | memory.py 全量 + 自测 | W1 | 6 | 中 | S02 | 记忆落盘/恢复 |
| S04 | agent.py 调用层 + MOCK | W1 | 5 | 中 | S02 | 能调通模型 |
| S05 | app.py 最小闭环 | W1 | 5 | 中 | S03 S04 | 10 轮不崩 |
| S06 | 部署 + tag v0.1 | W1 | 3 | 中 | S05 | 在线可开 |
| S07 | 五张人设卡 + prompt 分区 | W2 | 5 | 中 | S05 | 盲读可分 |
| S08 | RULES 20 条 + 校验 | W2 | 4 | 中 | S02 | 规则唯一来源 |
| S09 | 豁免引擎（顺序敏感） | W2 | 4 | **高** | S08 | D-21/22/23/25 过 |
| S10 | pre_check 主链路 + 短路 + 资源卡 | W2 | 6 | **高** | S09 | L3 断网可用 |
| S11 | 三角色状态机 | W2 | 4 | 中 | S10 | C-05 切 guide |
| S12 | 日志 + 侧栏 + tag v0.2 | W2 | 3 | 低 | S11 | 日志无原文 |
| S13 | post_check 骨架 + 重写复检 | W3 | 4 | **高** | S10 | rewrite=1 |
| S14 | LLM 复核接入 | W3 | 4 | 中 | S13 | 失败按 L2 |
| S15 | 说教词 + taboos 接入 | W3 | 2 | 中 | S13 | 说教句被改 |
| S16 | 会话聚合 + 风险地板 | W3 | 4 | **高** | S10 | 3 次 L2 升级 |
| S17 | 摘要节流 | W3 | 3 | 低 | S03 | 200 字封顶 |
| S18 | 记忆面板 | W3 | 3 | 低 | S03 | 可删可清空 |
| S19 | 三套主题 | W3 | 2 | 低 | S05 | 切换不错位 |
| S20 | mini Lorebook | W3 | 3 | 低 | S03 | lore 可命中 |
| S21 | 集成验收 + tag v0.3 | W3 | 2 | 低 | 13–20 | 功能完整 |
| S22 | 28 条规则单测 | W4 | 6 | 中 | S09–S16 | 召回/误拦可算 |
| S23 | 12 对话 + 8 故障注入 | W4 | 6 | 中 | S21 | 端到端可复现 |
| S24 | 指标脚本 + 冻结 + tag v1.0 | W4 | 5 | 中 | S22 S23 | 数字能对上表 |
| S25 | 项目文档（Word）+ 附录 A | +3 天 | 15 | 低 | S24 | 六项齐全 + 附录 A |
| S26 | PPT 17 页 / 视频 300 秒 / 彩排 / 提交 | +3 天 | 9 | 高 | S25 | 能讲能演能交 |

步内合计 96（编码 82 + 测试 14）+ 文档 24 = 120 人时。

> **2026-11-08 按比赛要求调整**：PPT 占 37.5%、视频占 25%，且要求 ≤20 页 / 300 秒 ≤100MB。故 S25 13→15（补附录 A）、S26 7→9（17 页 PPT + 300 秒视频），文档预算 20→24。
> 多出的 4 人时按砍单 1/2 级预支：S19 主题三套→一套（省 2）、S20 lorebook（省 3）；若两者都要保，则改砍 S18 面板可视化。
> 规格与逐页/逐镜脚本见 `docs/比赛要求对照与提交计划.md`。
另有 28 人时不在步内：培训 15、周五集成 6、站会机动 7。合计 144，与执行书 §2.1 对齐。

> 与执行书 §2.1 的差别：执行书记的是“编码 80 + 会议 15”；本表把会议拆成“周五集成 6 + 站会 7 = 13”，多出的 2 人时记进编码（82）。**总数 144 不变**，多的 2 人时用于两次周五集成的返工，不从测试或文档里扣。

---

## 2 四道安全阀（每个文件都假设你遵守）

1. **绿不过不进下一步**：三个命令有一个红，就停。
2. **一步一提交**：提交信息写清"改了什么 / 怎么验的"，出问题 `git revert` 一次干净。
3. **安全相关改动的第一行注释写 `[SAFE]`**，并说明为什么不能降级。评审只看带这个标记的 diff。
4. **不许临时加依赖**。要加库 → 先在群里说明 → 改 `requirements.txt` 并说明理由 → 否则一律不加。

---

## 3 全局约定

### 3.1 目录

```text
心屿/
├─ app.py  agent.py  roles.py  coordinator.py  guardian.py  memory.py
├─ resources.py  logger.py  theme.py
├─ contract_check.py  metrics.py  utils.py
├─ tests/  test_memory.py  test_agent.py  test_roles.py  test_log.py
│          test_guardian.py  test_flow.py  test_fault.py
├─ data/memory/*.json    data/logs/YYYY-MM-DD.jsonl        （都不进仓库）
└─ docs/  report.md  slides.pdf  evidence/YYYY-MM-DD-*.png
```

### 3.2 命令（每一步都只跑这三条 + 一条手动）

```powershell
.\.venv\Scripts\Activate.ps1
python contract_check.py      # 期望：11/11 signatures OK
pytest -q                     # 期望：全 passed，0 failed
streamlit run app.py          # 手动：走一遍本步 §6 的场景
```

### 3.3 常量与契约（改动 = 全组返工）

```text
TIMEOUT = 15      N_WINDOW = 5     COOLDOWN = 3
SUMMARY_MAX = 200 SUMMARY_EVERY = 5

memory.py       read_memory(session_id) / write_memory(session_id, data) /
                update_memory(session_id, user_text, reply) /
                clear_memory(session_id) / match_lore(user_text, session_id="") -> list[str]
agent.py        call_llm(messages, temperature=0.7) -> dict
                build_system_prompt(persona_id, memory, lore) -> str
coordinator.py  coordinator_decide(memory, user_text, level) -> dict
guardian.py     guardian_pre_check(user_text) -> dict
                guardian_post_check(user_text, reply, level, role, rewriter=None) -> dict
resources.py    pick_resources(level, emotion_tags) -> list[dict]
```

### 3.4 三个返回结构（字段名不可改，日志与测试都依赖）

```python
pre  = {"level": "L1|L2|L3", "rule_ids": [], "exempted": False, "reason": "..."}
post = {"pass": True, "reason": "", "fixed_reply": None, "rewrite": 0, "template_fallback": False}
dec  = {"role": "listener|guide|crisis", "reason": "default|crisis_shortcircuit|..."}
```

### 3.5 数据结构

- `memory.json` 白名单 8 字段 + `summary_at_turn`：`preferred_tone / current_role / role_switch_reason / emotion_tags / unresolved_issues / coping_preferences / rolling_summary / last_updated`。
- `data/logs/YYYY-MM-DD.jsonl` 每行 9 个字段：`ts / session_hash / turn / level / role / rule_ids / action / rewrite / latency_ms`。**永远不写用户原文。**
- 主题 id：`sakura / matcha / sunset`。人设 id：`sister_heart / warm_senpai / rational_mentor / energy_buddy / quiet_hollow`。

---

## 4 测试口径（为什么最后是 97 条测试，报告只写 48）

| 口径 | 组成 | 用途 |
|---|---|---|
| **考核口径 48 条** | 28 规则（编号 D-01~D-28）+ 12 对话（C-01~C-12）+ 8 故障注入（F-01~F-08） | 报告与答辩只用这个数 |
| 开发自测 49 条 | memory 17 · agent 6 · roles 5 · log 2 · guardian 里 11 条 post_check · flow 里 8 条状态机/聚合 | 保证底层不骗人，不进指标 |
| 合计 97 条 | — | 提交时 `pytest -q` 应显示 97 passed |

**怎么区分**：考核口径只认"带编号的用例"（D-* / C-* / F-* 写在 `@pytest.mark.parametrize` 或函数名里）。
报告写"48/48"，被问"为什么 pytest 是 97"时照上表回答。**两个数都要真实存在，不许只写好看的。**

---

## 5 已裁决的十处文档冲突（照这里执行，别再问）

1. **`guardian_pre_check` 签名**：执行书 §4.5 的代码草稿写 `(user_text, session_state)`，附录 A 与 `.cursor/rules/xinyu.mdc` 写 `(user_text)`。
   → **以单参数为准**。Guardian 一旦能读写会话状态，"否决权唯一"就会被状态污染。冷却计数放在 `coordinator` 与 `app` 里。
2. **`pre_check` 返回值**：执行书 §4.5 有 `pass` 字段，mdc §4 只有四个字段。
   → **四个字段为准**；`pass` 由调用方推导 `level != "L3"`。
3. **规则表字段数**：执行书 §4.2 列 8 个字段，附录 B 的表只画了 7 列。
   → **以 §4.2 为准**（多出的 `source / version / case_ids` 必须写），附录 B 是简写。缺字段的规则不算写完。
4. **`guardian_post_check` 第五个参数 `rewriter`**：执行书 附录 A 只有三个参数，且带 `session_state`。
   → **以 S02 契约为准**：`(user_text, reply, level, role, rewriter=None)`。`rewriter` 只用于测试注入假重写、生产留 `None`；**会话状态不许塞进来**。
5. **`match_lore` 的 `session_id`**：执行书 附录 A 写 `(user_text, memory)`。
   → **以 S02 契约为准**：`(user_text: str, session_id: str = "")`。第二个参数只用于“同会话最多注入 3 次”的计数，不传就退化为不计数。
6. **`pick_resources` 参数顺序**：执行书 附录 A 是 `(emotion_tags, level)`，S02 是 `(level, emotion_tags)`。
   → **以 S02 为准**：`level` 在前——L3 时即使情感标签为空，也必须给资源卡。
7. **`build_system_prompt` 参数**：执行书 附录 A 是 `(role, persona_id, memory, emotion_tags)`，S02 是 `(persona_id, memory, lore)`。
   → **以 S02 为准**：风格由 `persona_id` 决定；安全区是常量、不由参数拼；`lore` 是本项目唯一的外部知识入口。
8. **28 条 D 用例的编号**：执行书 附录 D 是旧稿，与 S10/S22 的用例文本对不上（连 D-06、D-10 的句子都不同）。
   → **以 `step/S10` 与 `step/S22` 为准**；执行书附录 D 按 step 重写（v1.1）。
9. **误拦率的分母**：执行书 §8.2 写“反例集 8 条判 L3 的比例”，S24 写“20 条普通闲聊判 L2+ 的比例”。
   → **以 S24 为准**（20 条分母更稳，8 条被 1 条翻盘）；执行书的“对话级召回 ≥80%”降为观察项，不进验收。
10. **工时 2 人时的挪动**：执行书 §2.1 是“编码 80 + 会议 15”；本册是“编码 82 + 会议 13（周五集成 6 + 站会 7）”。
   → 总数 144 不变，多出的 2 人时用于周五集成返工，**不从测试或文档里扣**。

---

## 6 回滚三级（按顺序试，第 3 级最贵）

| 级 | 场景 | 动作 | 恢复时间 |
|---|---|---|---|
| 1 | 只改了代码，没动数据 | `git checkout -- <文件>` | 10 秒 |
| 2 | 改了数据导致状态脏 | 删 `data/memory/<session>.json` 与 `.bak`，重启页面 | 1 分钟 |
| 3 | 环境坏了、依赖打架 | 删 `.venv` 重建 + `git reset --hard <上一个 tag>` | 10 分钟 |

**永远不要用 `git push -f` 回滚**，那会把别人的分支一起抹掉。回滚也走 PR。

---

## 7 进度勾选表（做完一步就把 ⬜ 改成 ✅，并写日期）

| 步 | 状态 | 完成日期 | 备注 |
|---|---|---|---|
| S01 | ⬜ | | |
| S02 | ✅ | 2026-11-09 | 7 个 .py 空壳；contract 11/11 + 5/5；改签名/改常量已验红（`docs/evidence/2026-11-09-s02-contract.md`） |
| S03 | ✅ | 2026-11-09 | `memory.py` 219 行；9 条测试全过；坏文件自愈与“落盘无原句”已手工验证（`docs/evidence/2026-11-09-s03-memory.md`） |
| S04 | ✅ | 2026-11-09 | `agent.py` 121 行；6 条测试全过；MOCK 跨进程确定；真实调用 ok=True（`docs/evidence/2026-11-09-s04-agent.md`） |
| S05 | ✅ | 2026-11-09 | `app.py` 146 行；七步管线；AppTest 10 轮 20 条消息 0 异常；刷新同 sid / 清空真删 / 缺 Key 兜底（`docs/evidence/2026-11-09-s05-app.md`） |
| S06 | ⬜ | | |
| S07 | ⬜ | | |
| S08 | ⬜ | | |
| S09 | ⬜ | | |
| S10 | ⬜ | | |
| S11 | ⬜ | | |
| S12 | ⬜ | | |
| S13 | ⬜ | | |
| S14 | ⬜ | | |
| S15 | ⬜ | | |
| S16 | ⬜ | | |
| S17 | ⬜ | | |
| S18 | ⬜ | | |
| S19 | ⬜ | | |
| S20 | ⬜ | | |
| S21 | ⬜ | | |
| S22 | ⬜ | | |
| S23 | ⬜ | | |
| S24 | ⬜ | | |
| S25 | ⬜ | | |
| S26 | ⬜ | | |