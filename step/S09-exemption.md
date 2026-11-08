# S09 · 豁免引擎（小句级判定）

| 项 | 内容 |
|---|---|
| 步骤 | S09 / 26 |
| 阶段 | W2 |
| 工时 | 4 人时（P3） |
| 风险 | **高**——这是全项目最容易出错的一步。写错了要么把危机豁免掉（事故），要么全量误拦（体验崩） |
| 依赖 | S08 |
| 回滚 | `git checkout -- guardian.py tests/test_guardian.py` |

## 1 这一步做什么

实现 `guardian_pre_check` 的**判定内核**：把一段话切成小句，逐句判 X → H → W，取最高等级。

产出：

1. `split_clauses()` / `_hits()` / `scan()` 三个函数
2. `guardian_pre_check(user_text)` 返回四键结构
3. `tests/test_guardian.py` 6 条（D-21 ~ D-25 + 1 条回归）

**不做**：不生成回复、不短路、不写日志（S10 做）。

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 切句 | `re.split` | 中英文标点都要覆盖 |
| 匹配 | 预编译 `COMPILED` | 用 `.search` 不用 `.fullmatch` |
| 判级 | 纯函数 `_rank()` | L1 < L2 < L3，只用比较 |
| 防退化 | 硬词黑名单 | 见 §5.3 |

## 3 前置检查

```powershell
python contract_check.py    # 20/20 rules OK
python -c "import guardian; print(guardian.guardian_pre_check('你好'))"   # 现在是 L1 空壳
```

## 4 硬要求

1. **按小句判定，不按整段判定**。原因见 §5.1，这是本步的核心。
2. 等级只升不降：一段话里任何一个小句判到 L3，整体就是 L3。
3. `rule_ids` 去重且保序（按 X→H→W 出现顺序）。
4. `exempted` 只有在"整段唯一的命中都被豁免"时才为 `true`。
5. 纯函数：不读文件、不写文件、不调 LLM、不看全局状态。同样输入永远同样输出。

## 5 执行步骤

### 5.1 为什么必须切小句

如果"先跑 X 再跑 H"，会出这个事故：

| 输入 | 整段匹配 | 结果 | 应该 |
|---|---|---|---|
| 累死了，不想活了 | X04 命中"累死了" → 整段豁免 | L1 ❌ | **L3** |
| 笑死，我今天想死 | X04 命中"笑死" → 整段豁免 | L1 ❌ | **L3** |
| 我不想死 | X01 命中 | L1 ✅ | L1 |

小句级判定后：第一句豁免、第二句 H01 命中 → 取最大值 L3。**X 的豁免范围只到自己所在的那个小句为止。**

### 5.2 三个函数

```python
CLAUSE_SPLIT = re.compile(r"[，。！？；、,.!?;~～\n\r]+")

def split_clauses(text: str) -> list[str]:
    """按中英文标点切成小句；丢掉空白句。"""
    return [c.strip() for c in CLAUSE_SPLIT.split(text or "") if c.strip()]

def _hits(clause: str, group: str) -> list[dict]:
    """返回该小句命中的某个组的规则（按 RULES 里的顺序）。"""
    out = []
    for r in RULES:
        if r["group"] != group:
            continue
        m = COMPILED[r["rule_id"]].search(clause)
        if m:
            out.append({"rule": r, "span": (m.start(), m.end())})
    return out
```

### 5.3 硬词保护（防止"否定式绕过"）

```python
# 这些词只要出现在 X 命中范围之外，就拒绝豁免——它们是"真的要出事"的信号
HARD_WORDS = ("不想活", "活不下去", "自杀", "自残", "割腕", "遗书", "撑不下去", "熬不下去")

def _covered(clause: str, hard: str, span: tuple[int, int]) -> bool:
    """硬词是否落在豁免命中范围内（在范围内才允许被豁免）。"""
    for m in re.finditer(re.escape(hard), clause):
        if not (span[0] <= m.start() and m.end() <= span[1]):
            return False
    return True
```

例：`不想死但是不想活` → X01 命中"不想死"（span 覆盖"不想死"），但"不想活"在范围外 → 拒绝豁免 → 继续判 H → L3。

### 5.4 scan()

```python
def scan(user_text: str) -> dict:
    """小句级扫描，返回 pre_check 的四键结构。"""
    level, ids, reasons, any_exempt = "L1", [], [], False
    for clause in split_clauses(user_text):
        x = _hits(clause, "X")
        exempt_ok = False
        if x:
            hit = x[0]
            if all(_covered(clause, h, hit["span"]) for h in HARD_WORDS if h in clause):
                exempt_ok = True
                ids.append(hit["rule"]["rule_id"])
                reasons.append(hit["rule"]["why"])
                if hit["rule"]["action"] == "floor_l2":
                    level = _raise(level, "L2")
                else:
                    any_exempt = True
        if exempt_ok:
            continue
        h = _hits(clause, "H")
        if h:
            level = "L3"
            ids += [i["rule"]["rule_id"] for i in h]
            reasons += [i["rule"]["why"] for i in h]
            continue
        w = _hits(clause, "W")
        for i in w:
            ids.append(i["rule"]["rule_id"])
            reasons.append(i["rule"]["why"])
            level = _raise(level, i["rule"]["level"])
    return {"level": level, "rule_ids": _dedup(ids), "exempted": any_exempt and level == "L1",
            "reason": "；".join(_dedup(reasons)) or "未命中规则"}
```

`_raise(current, new)` 只升不降：`return new if RANK[new] > RANK[current] else current`，并在此行上方写注释"等级只升不降"。

### 5.5 guardian_pre_check（本步先返回 scan，S10 再包一层）

```python
def guardian_pre_check(user_text: str) -> dict:
    """安全检查入口：只判等级，不生成回复。纯函数。"""
    return scan(user_text)
```

## 6 验证

### 6.1 六条用例（写进 test_guardian.py）

```python
CASES = [
    ("我不想死", "L1", "X01"),
    ("如果我考不好就想死", "L1", "X02"),
    ("电影里的主角自杀了", "L1", "X03"),
    ("今天累死了", "L1", "X04"),
    ("我室友说他不想活了", "L2", "X05"),
    ("累死了，不想活了", "L3", "H01"),   # 回归：豁免不许跨小句
]
```

```powershell
pytest tests/test_guardian.py -q    # 6 passed
```

### 6.2 手测（必须自己敲，不要只看测试绿）

```powershell
python -c "from guardian import guardian_pre_check as g; [print(repr(t), g(t)['level'], g(t)['rule_ids']) for t in ['我不想死','累死了，不想活了','笑死，我想死','不想死但是不想活','我室友说他不想活了','今天天气不错']]"
```

期望：L1 / **L3** / **L3** / **L3** / L2 / L1。

## 7 回滚

```powershell
git checkout -- guardian.py tests/test_guardian.py
```

本步不碰数据、不碰网络，回滚零成本。

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| "累死了，不想活了"判成 L1 | 没切小句 / 豁免跨句生效 | 按 §5.1 改；这是回归用例，测试红了就说明改坏了 |
| "我不想死"判成 L3 | 没加 X 组，或 X 排在 H 后面 | 顺序必须 X → H → W |
| "我室友说他不想活了"判成 L3 | X05 的 action 写成了 log_only | X05 必须是 `floor_l2` |
| 英文句号切不开 | 分隔符漏了 `.` | 正则里中文、英文标点都要有 |
| 大段文本很慢 | 每个小句都全量扫 20 条 | 20 条 × 小句数，量级可忽略；真慢再上 Aho-Corasick（不建议） |

## 9 出口清单

- [ ] 6 条用例全绿，其中"累死了，不想活了"= L3
- [ ] 手测 6 句期望值全对
- [ ] `guardian_pre_check` 无副作用（不写文件、不打日志）
- [ ] `rule_ids` 无重复
- [ ] `contract_check.py` 11/11 仍然通过

## 10 回执

```text
S09 完成：6/6 用例 / 跨句豁免已封堵 / contract 11/11
下一步：S10 短路与资源卡（第一次让危机回复真的发出去）
```
