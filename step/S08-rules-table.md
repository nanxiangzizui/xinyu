# S08 · RULES 20 条 + 规则校验

| 项 | 内容 |
|---|---|
| 步骤 | S08 / 26 |
| 阶段 | W2 |
| 工时 | 4 人时（P3） |
| 风险 | **中**——规则写宽了会误拦，写窄了会漏；但本步只落数据，不改行为 |
| 依赖 | S02 |
| 回滚 | `git checkout -- roles.py contract_check.py` |

## 1 这一步做什么

把 `心屿MindIsle_工程执行书_v1.0.md` 附录 B 的 20 条规则，原样落进 `roles.py`，并让 `contract_check.py` 能校验它们没写错。

产出：

1. `RULES` 20 条（X 组 5 + H 组 10 + W 组 5）
2. `validate_rules()` 校验函数
3. `contract_check.py` 增加一行输出：`20/20 rules OK`

**本步不实现匹配逻辑**（那是 S09/S10）。数据集先立起来，是后面所有安全测试的地基。

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 正则 | `re`，**预编译一次**放模块级 | `re.compile(p, re.IGNORECASE)` |
| 校验 | 纯函数，返回错误列表 | 不抛异常，一次报全部问题 |
| 数据 | list[dict] | 字段固定，不许少 |

## 3 前置检查

```powershell
python contract_check.py        # 11/11 + 5/5
python -c "import roles; print(len(roles.RULES))"   # 现在是 0
```

## 4 硬要求

1. **10 个字段一个不能少**：`rule_id / group / pattern / intensity / level / action / exempt / source / version / case_ids`，外加 `why` 便于人读。
2. 顺序固定：**X 组 → H 组 → W 组**。匹配时按这个顺序跑，代码里也不能重排。
3. 正则统一用**原始字符串** `r"..."`，统一 `re.IGNORECASE`。
4. 规则表是**全项目唯一来源**：@ guardian` 与 `coordinator` 只许 `from roles import RULES`，不许各自复制一份。
5. 改任何一条，必须在表下追加一行变更记录（日期 / 原因 / 谁改）。

## 5 执行步骤

### 5.1 直接抄这张表（这就是 RULES）

> ⚠️ 附录 B 里写的 `\|` 是 markdown 转义，**写进 Python 时用单个 `|`**。下面已经是可直接粘贴的形态。

```python
RULES: list[dict] = [
 # ---- X 组：豁免 / 降级（必须先跑）----
 {"rule_id": "X01", "group": "X", "pattern": r"(不|没)想死|不会自杀|没想过自杀", "intensity": "-", "level": "L1", "action": "log_only", "exempt": "denial", "why": "否定/反转：保护性表达"},
 {"rule_id": "X02", "group": "X", "pattern": r"(如果|假如|要是).{0,15}(想死|自杀|不想活)", "intensity": "-", "level": "L1", "action": "log_only", "exempt": "hypothetical", "why": "假设/求助他人"},
 {"rule_id": "X03", "group": "X", "pattern": r"(电影|剧|小说|歌词|主角|游戏|书里).{0,20}(自杀|死了|想死)", "intensity": "-", "level": "L1", "action": "log_only", "exempt": "quotation", "why": "引用/创作"},
 {"rule_id": "X04", "group": "X", "pattern": r"(笑|累|饿|困|烦|气|吓|热|冷)死(了|我)", "intensity": "-", "level": "L1", "action": "log_only", "exempt": "hyperbole", "why": "夸张/补语化"},
 {"rule_id": "X05", "group": "X", "pattern": r"(他|她|朋友|室友|同学).{0,12}(想死|自杀|不想活)", "intensity": "-", "level": "L2", "action": "floor_l2", "exempt": "third_person", "why": "第三人称：不豁免，降 L2"},
 # ---- H 组：高危，短路 ----
 {"rule_id": "H01", "group": "H", "pattern": r"(不想活|活不下去|想死|去死|死了算了)", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "自杀意念直述"},
 {"rule_id": "H02", "group": "H", "pattern": r"(自杀|轻生|了结自己|结束生命)", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "自杀相关表述"},
 {"rule_id": "H03", "group": "H", "pattern": r"(自残|割腕|划手腕|伤害自己)", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "自伤行为"},
 {"rule_id": "H04", "group": "H", "pattern": r"(跳楼|跳桥|上吊|从楼上)", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "具体手段"},
 {"rule_id": "H05", "group": "H", "pattern": r"(遗书|最后一条|交代后事|世界再见)", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "告别/后事"},
 {"rule_id": "H06", "group": "H", "pattern": r"((一把|整瓶|很多).{0,4}药|吞药|吃药自杀)", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "药物准备"},
 {"rule_id": "H07", "group": "H", "pattern": r"(今晚|明天|一会儿).{0,6}(结束|动手|了断|就走了)", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "时间计划"},
 {"rule_id": "H08", "group": "H", "pattern": r"(想杀|弄死|捅了|报复(他|她))", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "他伤意图"},
 {"rule_id": "H09", "group": "H", "pattern": r"(撑不下去|不想再撑|不想继续了|熬不下去)", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "彻底耗竭"},
 {"rule_id": "H10", "group": "H", "pattern": r"(没意义|没价值|累赘).{0,10}(活|死)", "intensity": "强", "level": "L3", "action": "short_circuit", "exempt": "", "why": "自我否定到生存层面"},
 # ---- W 组：弱信号，记日志或抬地板 ----
 {"rule_id": "W01", "group": "W", "pattern": r"(好累|很累|心累|疲惫)", "intensity": "弱", "level": "L1", "action": "log_only", "exempt": "", "why": "疲惫"},
 {"rule_id": "W02", "group": "W", "pattern": r"(没意思|麻木|空落落|无所谓)", "intensity": "弱", "level": "L2", "action": "floor_l2", "exempt": "", "why": "兴趣丧失/疏离"},
 {"rule_id": "W03", "group": "W", "pattern": r"(没用|废物|讨厌自己|失败者)", "intensity": "弱", "level": "L2", "action": "floor_l2", "exempt": "", "why": "无价值感"},
 {"rule_id": "W04", "group": "W", "pattern": r"(失眠|睡不着|整夜|凌晨)", "intensity": "弱", "level": "L1", "action": "log_only", "exempt": "", "why": "睡眠问题"},
 {"rule_id": "W05", "group": "W", "pattern": r"(想消失|想解脱|想逃)", "intensity": "弱", "level": "L2", "action": "floor_l2", "exempt": "", "why": "回避/消失愿望（已知难点）"},
]
```

`source` 与 `version` 统一规则：`source` 填 `"执行书附录B"`（红队反例填 `\"红队反例\"`），`version` 统一 `\"v1\"`。
`case_ids` 有对应用例就填（如 `["D-01", "C-09"]`），没有填空列表——**不许编**。

### 5.2 预编译（省得每次 re.compile）

```python
COMPILED = {r["rule_id"]: re.compile(r["pattern"], re.IGNORECASE) for r in RULES}
```

### 5.3 validate_rules()

```python
def validate_rules() -> list[str]:
    """返回问题列表；空列表 = 合格。一次报全部问题，不要遇错就 return。"""
    errors = []
    ids = [r["rule_id"] for r in RULES]
    if len(ids) != len(set(ids)):
        errors.append("rule_id 有重复")
    for r in RULES:
        for k in ("rule_id", "group", "pattern", "level", "action", "why"):
            if not r.get(k):
                errors.append(f"{r.get('rule_id', '?')} 缺字段 {k}")
        if r.get("level") not in ("L1", "L2", "L3"):
            errors.append(f"{r['rule_id']} level 非法：{r.get('level')}")
        if r.get("action") not in ("short_circuit", "floor_l2", "log_only"):
            errors.append(f"{r['rule_id']} action 非法")
        try:
            re.compile(r["pattern"])
        except re.error as exc:
            errors.append(f"{r['rule_id']} 正则编译失败：{exc}")
    if [r["group"] for r in RULES] != sorted(r["group"] for r in RULES):
        errors.append("顺序错：必须 X → H → W")
    return errors
```

### 5.4 接进 contract_check.py

在常量检查之后加一段：

```python
from roles import validate_rules
errs = validate_rules()
if errs:
    print("RULES FAIL:"); [print(" -", e) for e in errs]; sys.exit(1)
print("20/20 rules OK")
```

## 6 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `python contract_check.py` | 三行：11/11、5/5、20/20 rules OK |
| 2 | 把 H01 的 pattern 改成 `r"((("` | 报"正则编译失败"，退出码 1 |
| 3 | 把 W01 的 level 改成 `L9` | 报"level 非法" |
| 4 | 把一条 H 规则挪到 X 前面 | 报"顺序错" |
| 5 | 全部改回 | 20/20 |
| 6 | `python -c "import roles; print(len(roles.RULES))"` | `20` |

第 2–4 条必须亲手做：校验脚本要能在 3 秒内告诉你"哪条、错在哪"。

## 7 回滚

```powershell
git checkout -- roles.py contract_check.py
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| 正则写成 `\|` 导致永不命中 | 把 markdown 的转义抄进代码 | 代码里只用单个 `\|` |
| 中文标点没覆盖 | 用户打"我不想活了。" | 正则不需要管标点，匹配子串即可 |
| `re.compile` 在 3.11 报 bad escape | 用了 `\d` 之外的非法转义 | 用原始字符串，别手写 `\\d` |
| 一条规则同时命中多组 | 正常 | 由 S09 的优先级裁决，不在本步处理 |
| 改完规则没跑全量 | 忘了回归 | 每次改完必须 `contract_check.py` + W2 的五条用例 |

## 9 出口清单

- [ ] `RULES` 恰好 20 条，X5 / H10 / W5
- [ ] 10 个字段齐全，`case_ids` 没编造
- [ ] `contract_check.py` 输出 20/20 rules OK
- [ ] 三种故意的错误都能被校验脚本抓到（亲手验过）
- [ ] 顺序是 X → H → W

## 10 回执

```text
S08 完成：20 条 / 校验 3 类错误均可捕获 / contract 20/20 rules OK
下一步：S09 豁免引擎（顺序敏感，最容易出错）
```
