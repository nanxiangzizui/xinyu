# S15 证据：说教词与 taboos（体验层）

> 文件名沿用 2026-11-09（原定计划日期）；**本文件实际生成于 2026-11-08**。
> 结论一句话：说教句只会被"改写一次"，不会升风险等级、不会换模板；日志能按 `SAYING` 认出来。

## 1 改了什么

| 文件 | 内容 |
|---|---|
| `guardian.py` | 252 → 273 行：`SAYING` 正则（7 词）；`_violations` 追加 `preachy`；`_blocking()` 把 preachy 从"阻断项"里剔除；`_rewrite_once()` 复用剩余预算；`guardian_post_check` 增加 preachy 快路径（不调复核、不升等级、不兜底） |
| `app.py` | 日志在 `pre["rule_ids"]` 后追加 `SAYING`（仅当 `post.reason` 含 `preachy`），与 H / W 组的规则 ID 区分 |
| `tests/test_guardian.py` | +4 条 S15 用例；2 条 S14 用例改用"轻视"类回复，避免被 preachy 快路径短路 |
| `docs/evidence/probes/_probe_s15.py` | AppTest 端到端探针（说教句 / 干净句 / 五卡 taboos 注入） |

`taboos` **不是本步新增的**：5 张卡在 S07 就有该字段（`roles.py:35/50/65/80/95`），
`agent._style_block`（`agent.py:166-177`）已把它拼成"不要这样说：…"注入风格区。
本步只补了"怎么检测被违反"和测试，没有第二条接入口。

## 2 四条硬要求对账

| # | 要求 | 落点 | 证据 |
|---|---|---|---|
| 1 | SAYING 不进 `RULES` | 只在 `guardian.py:146`；`RULES` 仍是 20 条（contract 20/20） | grep：`roles.py` 无 SAYING |
| 2 | 命中 → 只重写，不升级不兜底 | preachy 快路径 → `pass=True, rewrite=1, template_fallback=False` | `test_saying_word_triggers_rewrite_only` |
| 3 | 重写后仍说教 → 允许发出、记账 | `test_rewritten_reply_may_keep_saying_words`：fixed 原样放行，`rewrite=1` | 同左 |
| 4 | 每卡 ≤1 条 taboo 且互不相同 | `test_taboos_are_distinct_and_injected`：len==1 × 5，5 条互异，均出现在 system prompt | 探针 ③ 的打印 |

另有两条边界：重写不可用（模型挂了 / 预算耗尽）→ **发原句**（`rewrite=0`，`test_saying_without_rewrite_still_sends_original`）；
说教**不参与** `guardian_pre_check`，`guardian_pre_check("你应该")["level"] == "L1"`。

## 3 门禁

```text
pytest -q                64 passed in 1.13s
contract_check.py        11/11 signatures OK / 5/5 constants OK / 20/20 rules OK
```

行数：guardian 273 / app 275 / agent 195 / roles 277 / memory 225 / 其余均 <100（全部 ≤350）。

## 4 AppTest 端到端（`docs/evidence/probes/_probe_s15.py`）

```text
① "我好累" + 生成句"你应该早点睡。"
   calls: [('gen', 0.7), ('rewrite', 0.5)]          ← 没有 review，preachy 直接走重写
   发出: '听着挺累的，先歇会儿吧。'
   日志: {'session_hash': '779278c8a7a0', 'turn': 1, 'level': 'L1', 'role': 'listener',
          'rule_ids': ['W01', 'SAYING'], 'action': 'rewrite', 'rewrite': 1,
          'latency_ms': 7, 'ts': '2026-11-08T18:29:06'}
   说教句是否发出: False   原文泄漏: False   exceptions: 0
② "今天有点累" + 干净回复
   calls: [('gen', 0.7), ('review', 0.2)]           ← 无说教词才做 LLM 复核
   日志: rule_ids: [], action: 'pass', rewrite: 0
③ taboos: {'sister_heart': ['我理解你'], 'warm_senpai': ['我当年也是这样'],
           'rational_mentor': ['其实很简单'], 'energy_buddy': ['开心点嘛'],
           'quiet_hollow': ['再多说一点']}
   学长卡提示词片段: '不要这样说：我当年也是这样。'
```

## 5 三处口径修正（已按此实现）

1. **旧基数**：步骤文件写"52 passed"，S14 实际已 60，本步 +4 → **64 passed**。步骤数字按实际记录，不回头改执行书。
2. **日志记 `SAYING`**：step 只说"不改 RULES 统计"，执行书 §5.3.1（`心屿MindIsle_工程执行书_v1.0.md:470`）明确要求日志记 `rule_ids: ["SAYING"]`。实现放 `app.py`（guardian 只返回 `reason="preachy"`），日志字段仍是 9 个。
3. **preachy 快路径不调复核**：说教不是安全事件，没必要多花一次 1.8s 的复核；规则命中的路径（诊断词 / L3 缺资源）仍然"规则优先、直接重写"。这条顺序写进了 `guardian_post_check` 的第一步。

## 6 没做的事

- 没有新增 `RULES` 规则，也没有改 28 条 D 用例的任何期望值。
- 没有做"说教词 → 角色专属 taboo"的映射：当前 7 词是全局的，角色专属 taboo 只经 prompt 约束（无法用规则判定"我理解你"在具体语境里是否冒犯）。
- 盲读项（人设 3 人 / 危机文案 1 人）仍是人工待办，不在本步范围内。
