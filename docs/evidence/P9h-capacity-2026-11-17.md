# P9h · 角色卡信息容量翻倍（2026-11-17）

## 1. 需求

用户指令（2026-11-17）：**“加大角色卡的信息填写容量，字数限制全部翻一倍”**。

本次只放宽角色卡相关字数上限，不改安全文案、不改 A 模式、不改 RULES / guardian / memory 白名单。

## 2. 改了什么

| 常量 / 字段 | 改前 | 改后 |
|---|---:|---:|
| `MAX_PROMPT_CHARS` | 1600 | **3200** |
| `CARD_MAX_TOTAL` | 420 | **840** |
| `FIELD_LIMITS.name`（角色名） | 12 | **24** |
| `FIELD_LIMITS.identity`（身份） | 30 | **60** |
| `FIELD_LIMITS.setting`（设定） | 120 | **240** |
| `FIELD_LIMITS.voice`（说话风格） | 80 | **160** |
| `FIELD_LIMITS.address`（称呼） | 8 | **16** |
| `EXAMPLE_USER_MAX`（示例·用户话） | 30 | **60** |
| `EXAMPLE_ROLE_MAX`（示例·角色话） | 50 | **100** |
| `TABOO_MAX`（每条禁忌） | 12 | **24** |
| `LORE_MAX`（角色认知总量） | 360 | **720** |
| `LORE_ITEM_MAX`（角色认知每条） | 60 | **120** |
| `WORK_MAX`（作品名） | 30 | **60** |
| `ENRICH_QUERY_MAX`（建卡检索词） | 80 | **160** |
| `FACT_MAX_CHARS`（补全单条事实） | 60 | **120** |

**未翻倍的项（不是“填写容量”）**：

- 条数上限不变：示例 2 组、禁忌 3 条、角色认知 6 条、补全事实 8 条。
- `SWITCH_MAX_CHARS` 保持 20：它是“切换句识别”的阈值，不是卡容量；放宽会把长句误判成切换请求。

## 3. 落点

- `rolecard.py`：常量与两处 docstring（840 / 720）。
- `rolecard_enrich.py`：检索词 160、单条事实 120、提取提示改为“不超过120字”。
- `rolecard_ui.py`：设定占位文案与禁忌标签改为读常量，不再写死 120 / 12；其余控件 `max_chars` 本来就引用常量。
- `tests/test_rolecard.py`：`_max_card()` 改为恰好 840 字；字段/认知/预算用例同步；新增 `test_limits_doubled` 锁定翻倍后的常量。
- `tests/test_rolecard_enrich.py`：查询截断 160、事实截断 120、总量冲突用例改为 840。

## 4. 验证

```text
.\.venv\Scripts\python.exe -m pytest -q
273 passed in 10.54s

.\.venv\Scripts\python.exe contract_check.py
11/11 signatures OK
5/5 constants OK
20/20 rules OK

.\.venv\Scripts\python.exe metrics.py
recall       10/10 = 100.0%
false_block  0/20  = 0.0%
role         12/12 = 100.0%
stable       10/10 = 100.0%
```

Prompt 预算（合法上限卡 + 6 条满额角色认知）：

```text
card_size            840
validate             []
example_prompt       948
max_prompt           2398 / 3200
enrich_query_max     160
fact_max_chars       120
```

行数（Python `splitlines()` 口径）：

```text
rolecard.py          234
rolecard_enrich.py   195
rolecard_ui.py       308
chat_ui.py            46
tests/test_rolecard.py          183
tests/test_rolecard_enrich.py   207
```

## 5. 兼容与边界

- 旧卡不受影响：本次只放宽上限，原先合法的卡仍然合法。
- 表单 `max_chars` 随常量变化；用户能输入更多，但提交时仍走同一套 `validate`。
- 卡字段总量 840 与角色认知 720 仍是两个独立预算，互不挤占。
- B 运行时仍然零工具、零联网、零 memory 读写；本次没有改 `orchestrator` 的 B 分支。
- 安全底线、免责声明、L3 短路、gate 文案逐字未动。
