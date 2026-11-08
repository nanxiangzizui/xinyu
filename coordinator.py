"""coordinator.py — 三角色状态机 + 会话聚合 + 只升不降。"""
from __future__ import annotations

# 求助词表：宁窄勿宽。只收明确的“要我给办法”，不收“怎么”这种半句，
# 否则“怎么又下雨了”也会切 guide（S11 §8）。
ADVICE_WORDS = ("怎么办", "建议", "该不该", "如何", "怎么选", "帮我分析", "要不要")

# dec.reason 固定枚举（执行书 §11 五条约定第 3 条）：
# sustained_negative 留给 S16 会话聚合，本步不会产出。
REASONS = ("crisis_shortcircuit", "user_ask_advice", "sustained_negative",
           "default", "crisis_cooldown", "after_crisis")


def coordinator_decide(memory: dict, user_text: str, level: str) -> dict:
    """选角色。只读 memory 的 current_role，不读也不写会话状态。

    判定顺序（命中即返回）：
      1. L3 永远 crisis —— 等级压倒文本，危机时给建议是错的。
      2. 记忆里有过危机 → listener —— crisis 之后永不回 guide。
      3. 明确求助 → guide。
      4. 其他 → listener。
    """
    if level == "L3":
        return {"role": "crisis", "reason": "crisis_shortcircuit"}
    # 历史遗留：memory.json 的 current_role 可能停在 crisis（上次会话留下的）。
    # 本会话的冷却由 enforce_cooldown 的 ever_crisis 负责，这条是跨会话兜底。
    if isinstance(memory, dict) and memory.get("current_role") == "crisis":
        return {"role": "listener", "reason": "after_crisis"}
    if any(word in (user_text or "") for word in ADVICE_WORDS):
        return {"role": "guide", "reason": "user_ask_advice"}
    return {"role": "listener", "reason": "default"}


def enforce_cooldown(decision: dict, cooldown_left: int, ever_crisis: bool) -> dict:
    """冷却期内把 guide 降为 listener；本会话有过危机则永不回 guide。

    只作用于 guide：listener / crisis 原样返回。
    先判 ever_crisis 再判 cooldown：危机的“永久”标记比剩余轮数更严格。
    """
    if not isinstance(decision, dict) or decision.get("role") != "guide":
        return decision
    if ever_crisis:
        return {"role": "listener", "reason": "after_crisis"}
    if isinstance(cooldown_left, int) and cooldown_left > 0:
        return {"role": "listener", "reason": "crisis_cooldown"}
    return decision
