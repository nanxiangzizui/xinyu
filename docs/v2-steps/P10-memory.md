# P10 · 记忆库分层（A 情景记忆 + B 角色卡长期记忆）

> 状态：2026-11-17 用户批准“按这个做”。基线 311 passed（P9l）。
> 范围：只做记忆，不动 guardian / coordinator / RULES / L3 短路；不加依赖、不接数据库、不搭向量库。

## 1. 做什么

- **A 陪伴模式**：在现有 8 字段 + `rolling_summary` 之外，加一层“情景记忆”——
  用户提过的事（搬家、考试、约定）每 5 轮抽一次，相关时能想起并自然提一句。
- **B 角色卡模式**：角色卡会话从“刷新即无”改成“按卡记”——
  摘要 / 当前场景 / 未完成约定 / 情景行，刷新、换 `rc_sid`、重新开始时都还在。
- **两条隐私边界**：现实身份不写；虚拟专名可写，但必须来自卡文本或助手回复。

## 2. 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 骨架 | 文件 2（分层） | 卡 → 当前工作记忆 → 摘要 → 结构化长期记忆，层级清楚 |
| 写入端 | 文件 1（LLM 抽取 + 状态覆盖 + 重要度 + 淘汰） | 用户已授权 LLM 调用；5 轮一次成本可接受 |
| 检索 | 确定性 `cue` + 话题 + 重要度 + 新近度 | 24/60 条规模不需要向量/重排；少一次调用少一个失败模式 |
| 存储 | 本地 JSON，一人一文件 / 一卡一文件 | 冻结技术栈；`memory.json` 8 字段白名单不动 |
| A 存储 | `$DATA_DIR/episodes/<sid>.json` | 与 memory.json 分开，清空时一起删 |
| B 存储 | `$DATA_DIR/rolecards/<card_key>.json` | `rc_sid` 刷新就换，按卡存才接得上 |
| 原文 | 不存 `raw_text` | 不做重排就不需要；转述 + 8 字重合闸足够 |
| 后台线程 | 不做 | Streamlit 重跑 + 线程 + 原子写会打架；同步、失败跳过 |
| 旧事冲突 | 卡优先 | B 记忆只记“这段对话里发生过的”，不能改卡的身份/关系 |

## 3. 接口

新增三个模块，均不 import streamlit：

```text
episode_store.py   read_store(sid) / write_store(sid, store) / read_with_recall(sid, text)
                   append(sid, items, current_len) / mark_try(sid, current_len) / clear(sid)
                   clean_episode(raw, *, allow_actors=False, event_max=50)
                   atomic_write / read_json（两个记忆文件共用的小 IO）
memory_extract.py  maybe_run(is_rolecard, card, sid, facts, history, text, reply)
                   parse_a(raw_text, user_blob) -> list[dict] | None
                   parse_b(raw_text, card, user_blob, assistant_blob) -> dict | None
rolecard_memory.py card_key(card) / read(card, text) / append_extraction(card, clean, current_len)
                   mark_try(card, current_len) / clear(card) / stats(card) / snapshot(card)
```

`agent.build_system_prompt` / `agent.call_llm` / `memory.*` 的签名全部不动。

## 4. 数据结构

A：

```json
{"seq": 7, "last_len": 10, "last_try_len": 0,
 "episodes": [{"cue": "搬家", "topic": "住处",
               "event": "对方提过下个月要搬家，当时有点焦虑",
               "mood": "焦虑", "importance": 2, "seq": 7,
               "recalls": 0, "last_recall_seq": 0}]}
```

B：

```json
{"summary": "……≤300 字……",
 "state": {"scene": "贝洛伯格", "mood": "平静", "relation": "同行者"},
 "threads": ["答应陪对方去城外看雪"],
 "episodes": [{"cue": "看雪", "topic": "约定",
               "event": "你答应带对方去城外看雪",
               "actors": ["昔涟"], "importance": 3,
               "mood": "其他", "seq": 3, "recalls": 0, "last_recall_seq": 0}],
 "seq": 3, "last_len": 10, "last_try_len": 0}
```

闭集：`topic ∈ 学业/升学/人际/亲密关系/家庭/睡眠/求职/经济/住处/健康/约定/其他`；
`mood ∈ 平静/低落/焦虑/生气/开心/疲惫/其他`；`importance ∈ 1/2/3`。

## 5. 写入与召回

1. **触发**：`len(history) + 2` 比上次多 10 条（5 轮）就抽一次；L3 已短路，不会走到；
   MOCK 下整段跳过；失败写 `last_try_len`，再等 5 轮，避免每轮重试。
2. **输入**：最近 5 轮，每条 `memory.scrub` 后截 60 字；A 只给转述，B 额外给卡名/身份/设定和旧摘要。
3. **输出**：一次 JSON。A 0–2 条；B 摘要/状态/线索/情景合并成一个 JSON。
4. **召回**：A 要求 `cue` 命中，按 `4 + importance + 新近度` 取 top 1–2，同一段隔 1 个抽取批次再提；
   B 常驻摘要/状态/线索，情景按 `cue` 取 1 条。总块 ≤500 字（B）/ ≤170 字（A）。
5. **写盘**：tmp + `os.replace`，先备份 `.bak`；坏文件从 `.bak` 读回并修好主文件。

## 6. 虚拟专名怎么放行

- **现实身份不写**：真名、学校、单位、住址、电话、证件、邮箱、链接、病历、药物、诊断。
- **虚拟专名可写**：角色卡、原作资料、助手回复里出现过的角色/地点/组织。
- **代码闸门**（不靠模型自觉）：
  1. B 的 `actors` 必须出现在卡文本或助手回复里，否则过滤掉；
  2. 用户“我叫 X / 叫我 X / 我的名字是 X / 我姓 X”里的 X 进 denylist，任何字段含 X 整条丢；
  3. `event` / `summary` / `threads` 与用户原句有连续 8 字重合即作废；
  4. 病名、药物、医院、诊断、自伤细节词出现即丢；
  5. A 的 `cue` 必须出现在用户原话里，防止模型编一个召不回的 cue。
- 日志只记 `mode / episodes=N / ok / ms`；记忆内容不进 trace、不进 JSONL。

## 7. 步骤

1. `episode_store.py`：存储、清洗、召回、淘汰、清空、共用 IO。
2. `memory_extract.py`：A/B 两套 prompt、JSON 解析、来源闸门、`maybe_run`。
3. `rolecard_memory.py`：卡 key、B 存储、预渲染 `_block`、清空。
4. 接线：`orchestrator.handle`（A 读情景 / B 读卡记忆 / 生成后抽一次）、
   `agent._facts_block`（A 情景块）、`rolecard.build_prompt`（B `_block`）、
   `rolecard_ui` 侧栏（记得 N 段 / 清空）、`app._clear`（连情景一起删）。
5. 上限：A prompt 1200→1400；B prompt 4000→5000。
6. 测试 + 真 key 探针 + 证据 + `CLAUDE.md`。

## 8. 测试

新增 `test_episode_store` / `test_memory_extract` / `test_rolecard_memory`，
并补 `test_orchestrator` / `test_rolecard` / `test_rolecard_flow`。至少覆盖：

- A：5 轮触发 / 4 轮不触发 / cue 不命中不召回 / 冷却 / 24 条淘汰 / 清空三文件 / 坏文件回 .bak；
- A 闸门：抄 8 字拒 / “我叫张三”拒 / 病名药物拒 / 虚拟地名放行；
- B：卡 key 同名同作品共享、不同作品分开 / 刷新后同卡仍能读 / 摘要状态线索注入 / 60 条淘汰 /
  线程 done 删除 / 清空 / `actors` 来源门 / 现实姓名不落盘 / 虚拟地名放行；
- 接线：L3 不抽取 / trace 仍 9 节点且无记忆原文 / A prompt ≤1400 / B prompt ≤5000。

## 9. 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe contract_check.py      # 11/11 + 5/5 + 20/20
```

真 key 探针（`MOCK_LLM=0`）：

1. A：第 1 轮说“下个月搬家”，第 6 轮说“最近好累”——回复能自然带一句；不相关话题不提。
2. B：5 轮建立“一起看雪”，换 `rc_sid` 后说“还记得看雪吗”——回复能接上。
3. B 隐私：对话里说“我叫张三”，落盘文件全文检索不到“张三”；卡里的虚拟地名能检索到。

## 10. 失败与回滚

- 抽取失败：不阻塞回复，`last_try_len` 防重试风暴；旧摘要/旧情景保留。
- 写盘失败：只 `logger.warning`，本轮对话照常。
- 回滚：删除三个新模块的调用即可；`memory.json` / 卡文件格式未改，
  旧版本读不到新文件也不受影响。A 的 `_clear` 多删一个目录，不影响旧逻辑。

## 11. 出口

- **348 passed**（311 + 新增 37 条）；契约 11+5+20；四指标不变（guardian/coordinator 未动）。
- A prompt 最坏 1240/1400；B prompt 最坏 4879/5000；L3 仍零 LLM、零工具。
- 实际行数：`episode_store.py` 319 / `memory_extract.py` 181 / `rolecard_memory.py` 292 / `orchestrator.py` 250（接线后压回上限）。
- A 清空后 `episodes/<sid>.json` 三件套都不在；B 清空后卡记忆三件套都不在。
- 证据 `docs/evidence/P10-memory-2026-11-17.md`，含真 key 探针输出与文件抽查。
