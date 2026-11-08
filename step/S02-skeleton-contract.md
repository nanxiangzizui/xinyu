# S02 · 六文件骨架 + 契约校验

| 项 | 内容 |
|---|---|
| 步骤 | S02 / 26 |
| 阶段 | W1 |
| 工时 | 4 人时（P1 写骨架，P6 写 `contract_check.py`） |
| 风险 | **低**——只有签名和空壳，没有逻辑 |
| 依赖 | S01 |
| 回滚 | `git checkout -- .` 回到 S01 的提交 |

## 1 这一步做什么

一次性把**六个文件 + 常量 + 契约校验脚本**立起来，让后面 24 步都只做"填一格"，而不是"改结构"。

产出：

1. `roles.py`：五个常量、`RULES`（空表）、`PERSONAS`（空表）、`THEMES`（空表）
2. 其余五个模块：**每个函数都返回安全默认值**的空壳（不是 `NotImplementedError`）
3. `contract_check.py`：检查 11 个签名 + 5 个常量，输出 `11/11 signatures OK`

**关键决定**：空壳返回**安全默认值**（L1 / listener / 空列表），不是抛异常。
这样 S05 的界面从第一天就能跑通全链路，后面每一步只是"把某个格子换掉"，永远可运行、可就地回滚。

## 2 技术栈

| 用途 | 标准库 / 包 | 要点 |
|---|---|---|
| 签名反射 | `inspect.signature` | 用 `str(sig)` 直接比对文本，够用 |
| 退出码 | `sys.exit(1)` | 让 CI 与人工都能一眼判断 |
| 类型注解 | `from __future__ import annotations` | 3.11 也写，防循环引用 |

## 3 前置检查

```powershell
git log --oneline -1        # 期望 S01 的提交
python -V                   # 3.11.x
```

## 4 硬要求

- **函数名、参数名、默认值一个字都不能改**（改 = 全组返工）。
- 单文件行数上限：`roles.py 350` / `memory.py 220` / `agent.py 150` / `coordinator.py 180` / `guardian.py 300` / `app.py 250` / `resources.py 100` / `contract_check.py 120`。
- 常量**只写在 `roles.py` 顶部**，其他模块 `from roles import TIMEOUT`，不许各自定义一份。
- 本步**不建** `utils.py`（还没有重复代码）。

## 5 执行步骤

### 5.1 roles.py（唯一数据源）

```python
"""roles.py — 常量 / 人设卡 / 规则表 / 主题，全项目唯一来源。"""
from __future__ import annotations

TIMEOUT = 15
N_WINDOW = 5
COOLDOWN = 3
SUMMARY_MAX = 200
SUMMARY_EVERY = 5

RULES: list[dict] = []      # S08 填 20 条
PERSONAS: dict = {}         # S07 填 5 张卡
THEMES: dict = {}           # S19 填 3 套
```

### 5.2 五个模块的安全空壳

每个函数的 docstring 写一句"本步先返回什么，Sxx 实现"。签名照抄 §3.3。

```python
# guardian.py
def guardian_pre_check(user_text: str) -> dict:
    """S02 空壳：一律放行 L1。S10 实现规则+短路。"""
    return {"level": "L1", "rule_ids": [], "exempted": False, "reason": "stub"}

def guardian_post_check(user_text: str, reply: str, level: str, role: str) -> dict:
    """S02 空壳：一律通过。S13 实现复核+重写。"""
    return {"pass": True, "reason": "", "fixed_reply": None,
            "rewrite": 0, "template_fallback": False}
```

```python
# coordinator.py
from roles import N_WINDOW, COOLDOWN

def coordinator_decide(memory: dict, user_text: str, level: str) -> dict:
    """S02 空壳：永远 listener。S11 实现状态机。"""
    return {"role": "listener", "reason": "default"}
```

```python
# resources.py
def pick_resources(level: str, emotion_tags: list[str]) -> list[dict]:
    """S02 空壳：不给卡。S10 实现资源表。"""
    return []
```

```python
# memory.py
def read_memory(session_id: str) -> dict: ...
def write_memory(session_id: str, data: dict) -> None: ...
def update_memory(session_id: str, user_text: str, reply: str) -> dict: ...
def clear_memory(session_id: str) -> bool: ...
def match_lore(user_text: str) -> list[str]:
    """S02 空壳：不命中。S20 实现。"""
    return []
```

```python
# agent.py
from roles import TIMEOUT

def call_llm(messages: list[dict], temperature: float = 0.7) -> dict:
    """S02 空壳：返回固定文本。S04 实现真实调用与 MOCK。"""
    return {"text": "（骨架）我在这里。", "ok": False, "error": "not_implemented", "latency_ms": 0}

def build_system_prompt(persona_id: str, memory: dict, lore: list[str]) -> str:
    """S02 空壳：一句占位。S07 实现分区拼接。"""
    return "你是一个倾听者。"
```

### 5.3 contract_check.py

```python
"""contract_check.py — 11 个签名 + 5 个常量，一次校验。"""
from __future__ import annotations
import inspect
import sys

import agent, coordinator, guardian, memory, resources, roles

SPEC = {
    "memory.read_memory": "(session_id: str) -> dict",
    "memory.write_memory": "(session_id: str, data: dict) -> None",
    "memory.update_memory": "(session_id: str, user_text: str, reply: str) -> dict",
    "memory.clear_memory": "(session_id: str) -> bool",
    "memory.match_lore": "(user_text: str) -> list[str]",
    "agent.call_llm": "(messages: list[dict], temperature: float = 0.7) -> dict",
    "agent.build_system_prompt": "(persona_id: str, memory: dict, lore: list[str]) -> str",
    "coordinator.coordinator_decide": "(memory: dict, user_text: str, level: str) -> dict",
    "guardian.guardian_pre_check": "(user_text: str) -> dict",
    "guardian.guardian_post_check": "(user_text: str, reply: str, level: str, role: str) -> dict",
    "resources.pick_resources": "(level: str, emotion_tags: list[str]) -> list[dict]",
}
CONSTS = {"TIMEOUT": 15, "N_WINDOW": 5, "COOLDOWN": 3, "SUMMARY_MAX": 200, "SUMMARY_EVERY": 5}
```

主流程三步，缺一不可：

1. 逐个 `getattr` 取函数 → `inspect.signature` → 与 `SPEC` 比对（**只比参数部分**，返回注解单独比一次）
2. 校验 `roles` 的五个常量值
3. 打印 `11/11 signatures OK` 与 `5/5 constants OK`；有任一不符 → 打印 `FAIL <名字>: 期望 X 实际 Y` 并 `sys.exit(1)`

> 比对时**忽略注解字符串的写法差异**（`dict` 与 `Dict`），只比参数名、顺序、默认值。
> 注解只做"有没有"的检查，不做全文比对——否则改一次 typing 写法就全员报错。

### 5.4 跑第一次

```powershell
python contract_check.py
```

## 6 验证

| # | 动作 | 期望 |
|---|---|---|
| 1 | `python contract_check.py` | 打印 `11/11 signatures OK` 和 `5/5 constants OK`，退出码 0 |
| 2 | 把 `call_llm` 的 `temperature` 改名 → 再跑 | 打印 `FAIL agent.call_llm`，退出码 1 |
| 3 | 改回来再跑 | 恢复 11/11 |
| 4 | 把 `roles.TIMEOUT` 改成 10 → 再跑 | 常量检查失败（第 5 项） |
| 5 | 改回 15 | `5/5 constants OK` |
| 6 | `pytest -q` | 输出 `no tests ran`（退出码 5 是**正常**的，S03 起才有测试） |

> 第 2–5 条必须真做一遍：**一个从没红过的校验脚本等于没有**。做完确认它能在 3 秒内指出问题。

## 7 回滚

```powershell
git checkout -- .
python contract_check.py     # 回到上一步的绿
```

## 8 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: roles` | 工作目录不对 | 必须在项目根目录跑，不是 `step\` 里 |
| 签名对不上，差一个 `-> dict` | `str(sig)` 带返回注解 | 先 `sig.replace(return_annotation, empty)` 再比，或只比 `sig.parameters` |
| 11/11 但 `pytest` 退出码 5 | 没有测试文件 | 正常，S03 会建 |
| `list[dict]` 在 3.8 报错 | 解释器不对 | 用 3.11；文件头加 `from __future__ import annotations` |

## 9 出口清单

- [ ] 八个 `.py` 文件都在（含 `contract_check.py`）
- [ ] `contract_check.py` 输出 11/11 + 5/5
- [ ] 故意改签名能让它变红（亲手验过）
- [ ] 五个常量只在 `roles.py` 定义
- [ ] 任一模块 import 不报错（`python -c "import app"` 除外，app 在 S05）

## 10 回执

```text
S02 完成：8 文件 / contract 11/11 + 5/5 / 故意改签名已验证会红
下一步：S03 memory.py
```
