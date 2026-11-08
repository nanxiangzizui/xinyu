# S03 · memory.py 全量（白名单 / 原子写 / 损坏恢复）

| 项 | 内容 |
|---|---|
| 步骤 | S03 / 26 |
| 阶段 | W1 |
| 工时 | 6 人时（P1） |
| 风险 | **中**——写文件，写坏了会污染后续演示 |
| 依赖 | S02 |
| 回滚 | `git checkout -- memory.py` + 删 `data/memory/*.json` |

## 1 这一步做什么

把"记忆"做成一个**可以被信任的**模块：只有 9 个字段、只会写合法值、断电不写半个文件、坏了能自愈、说删就真删。

产出：

1. `memory.py` 全量实现（≤220 行）
2. `tests/test_memory.py` 9 条
3. `DEFAULT_MEMORY` 与 `ALLOWED` 白名单

**不做**：摘要压缩（S17）、lore 匹配（S20）、界面（S18）。

## 2 技术栈

| 用途 | 手段 | 要点 |
|---|---|---|
| 存储 | `json` + `pathlib` | 一人一文件 `data/memory/<id>.json` |
| 原子写 | `tmpfile` + `os.replace` | 同目录写临时文件，再原子改名 |
| 备份 | `shutil.copy2` → `.bak` | 只留 1 份，覆盖式 |
| 脱敏 | `re` | 手机 / 证件 / 邮箱 / 链接 / 学校名 |
| 时间 | `datetime.now(timezone.utc).isoformat()` | 统一 UTC，显示时再转 |

## 3 前置检查

```powershell
python contract_check.py           # 11/11 + 5/5
Test-Path data\memory              # True
```

## 4 硬要求

1. **白名单唯一入口**：`write_memory` 收到多余键 → **丢弃**，不报错、不写入。
2. **session_id 必须校验**：只允许 `^[a-zA-Z0-9_-]{1,32}$`，不合格抛 `ValueError`。防 `../` 穿越。
3. 所有字符串字段 ≤ `SUMMARY_MAX`（200），列表 ≤ 8 项，超出截断。
4. 写入顺序：**先写 `.bak` → 再写 `.tmp` → 最后 `os.replace`**。
5. 读取遇到坏 JSON：先试 `.bak`，再失败才回默认值，并**补写一份**默认文件（避免每次读都报错）。
6. 不打印用户原文；日志只写字段名与长度。

## 5 执行步骤

### 5.1 常量与白名单

```python
from roles import SUMMARY_MAX

DATA_DIR = Path(os.getenv("DATA_DIR", "data/memory"))
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

FIELDS = ("preferred_tone", "current_role", "role_switch_reason",
          "emotion_tags", "unresolved_issues", "coping_preferences",
          "rolling_summary", "last_updated")
ALLOWED = set(FIELDS) | {"summary_at_turn"}      # 第 9 个字段，只做计数器

DEFAULT_MEMORY = {
    "preferred_tone": "neutral",
    "current_role": "listener",
    "role_switch_reason": "default",
    "emotion_tags": [],
    "unresolved_issues": [],
    "coping_preferences": [],
    "rolling_summary": "",
    "last_updated": "",
    "summary_at_turn": 0,
}
```

### 5.2 脱敏 `_scrub`

```python
SCRUB_RULES = [
    (re.compile(r"1[3-9]\d{9}"), "[手机]"),
    (re.compile(r"\d{17}[\dXx]"), "[证件]"),
    (re.compile(r"\S+@\S+\.\w+"), "[邮箱]"),
    (re.compile(r"https?://\S+"), "[链接]"),
    (re.compile(r"[\u4e00-\u9fa5]{2,8}(大学|学院|中学|附中|职院)"), "[学校]"),
]

def _scrub(text: str) -> str:
    for pat, rep in SCRUB_RULES:
        text = pat.sub(rep, text)
    return text[:SUMMARY_MAX]
```

### 5.3 原子写 + 备份

```python
def write_memory(session_id: str, data: dict) -> None:
    p = _path(session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    clean = _filter(data)                    # 白名单 + 类型 + 长度
    if p.exists():
        shutil.copy2(p, p.with_suffix(".json.bak"))
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)                       # 原子：要么旧文件，要么新文件
```

`_filter` 做四件事：只留 `ALLOWED` 的键、列表去重去空、字符串 `_scrub` 并截断、`last_updated` 补 UTC 时间。

### 5.4 读取与自愈

```python
def read_memory(session_id: str) -> dict:
    p = _path(session_id)
    for cand in (p, p.with_suffix(".json.bak")):
        if not cand.exists():
            continue
        try:
            return _filter(json.loads(cand.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue                          # 坏文件不抛给界面，继续试备份
    fresh = dict(DEFAULT_MEMORY, last_updated=_now())
    write_memory(session_id, fresh)           # 自愈：补一份合法的
    return fresh
```

> **为什么不抛异常**：这是四类边界之一（文件读）。界面必须永远能拿到一个 dict。
> 但坏文件要**记一行日志**（文件名 + 异常类型），否则永远发现不了磁盘问题。

### 5.5 update_memory：用标签，不存原文

```python
TONE_CUES = {"温柔": "gentle", "别凶": "gentle", "轻松点": "light", "直接点": "direct"}
TAG_RULES = {"考试": "学业", "考研": "升学", "室友": "人际", "分手": "亲密关系",
             "父母": "家庭", "失眠": "睡眠", "实习": "求职", "钱": "经济"}
ASK_CUES = ("怎么办", "该不该", "不知道", "给点建议")
```

决策表（照这个写，不要自由发挥）：

| 输入信号 | 更新字段 | 规则 |
|---|---|---|
| 语气线索词 | `preferred_tone` | 命中即改，取第一个 |
| 话题词 | `emotion_tags` | 映射成**标签**，最多 5 个，去重 |
| 求助句式 | `unresolved_issues` | 追加对应**标签**（不是原句），最多 5 个 |
| 每轮 | `summary_at_turn + 1`、`last_updated` | 必做 |
| 其他 | 不动 | 宁可不记，也不乱记 |

**这一条红线必须写在函数 docstring 里**：`update_memory 只写标签与枚举，绝不写用户原句。`
原因见 `CLAUDE.md` §5.5：一旦存原文，等于把聊天记录落盘，出了事没法解释。

### 5.6 clear_memory

```python
def clear_memory(session_id: str) -> bool:
    p = _path(session_id)
    removed = False
    for cand in (p, p.with_suffix(".json.bak"), p.with_suffix(".json.tmp")):
        if cand.exists():
            cand.unlink()
            removed = True
    return removed
```

必须同时删 `.bak` 与 `.tmp`，否则"清空"是假的。

### 5.7 测试（9 条，全部离线、无网络、无 sleep）

| # | 用例 | 断言 |
|---|---|---|
| 1 | 读不存在的 id | 返回 DEFAULT_MEMORY，且文件被创建 |
| 2 | 写→读往返 | 值一致，`last_updated` 非空 |
| 3 | 白名单 | 传 `{"name": "张三"}`，读回来**没有** `name` |
| 4 | 原子写 | 连写两次，文件是合法 JSON，`.bak` 存在 |
| 5 | 恢复 | 手写坏 JSON + 好 `.bak` → 读回 `.bak` 内容 |
| 6 | 双坏 | 两个都坏 → 回默认值且重新落盘 |
| 7 | 脱敏 | 传 `preferred_tone="13800138000"` → 读回含 `[手机]` |
| 8 | 清空 | 写后 `clear_memory` → 三个文件都没了，返回 True |
| 9 | 非法 id | `clear_memory("../evil")` 抛 `ValueError` |

测试里一律用 `tmp_path` 或 monkeypatch `DATA_DIR`，**不许碰真实 `data/memory`**。

```python
@pytest.fixture
def mem(tmp_path, monkeypatch):
    import memory
    monkeypatch.setattr(memory, "DATA_DIR", tmp_path)
    return memory
```

## 6 验证

```powershell
pytest tests/test_memory.py -q          # 期望 9 passed
```

再手动跑一次"看得见"的验证：

```powershell
python -c "from memory import update_memory,read_memory; update_memory('demo','我最近考试好焦虑，怎么办','嗯'); print(read_memory('demo'))"
Get-Content data\memory\demo.json
```

期望：`emotion_tags` 有 `学业`、`unresolved_issues` 有 `学业`、文件里**没有**"考试好焦虑"这句原文。

## 7 回滚

```powershell
git checkout -- memory.py tests/test_memory.py
Remove-Item data\memory\*.json, data\memory\*.bak -ErrorAction SilentlyContinue
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| Windows 上 `os.replace` 报 PermissionError | 文件被杀毒/编辑器占用 | 关掉预览，或改用 `tmp.unlink(missing_ok=True)` 重试 1 次 |
| 测试污染真实数据 | 忘了 monkeypatch | fixture 里必须改 `DATA_DIR` |
| `ensure_ascii=False` 后中文乱码 | 读的时候用了 `gbk` | 读写都写死 `encoding="utf-8"` |
| 白名单把 `summary_at_turn` 丢了 | `ALLOWED` 少写 | 用 `ALLOWED = set(FIELDS) \| {"summary_at_turn"}` |
| 每次读都重建文件 | 坏文件没删也没备份 | 自愈分支里先写 `.bak` 再落新文件 |

## 9 出口清单

- [ ] `pytest tests/test_memory.py -q` = 9 passed
- [ ] `read_memory` 对坏文件返回 dict 不抛异常（手工造一次坏文件验）
- [ ] `update_memory` 落盘内容里没有任何原句
- [ ] `clear_memory` 删干净三个文件
- [ ] `python contract_check.py` 仍 11/11

## 10 回执

```text
S03 完成：memory.py 210 行 / 9 passed / 坏文件自愈已验证 / 落盘无原文
下一步：S04 agent.py
```
