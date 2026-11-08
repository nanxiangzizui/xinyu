"""coordinator.py — 三角色状态机 + 会话聚合 + 只升不降。"""
from __future__ import annotations

from roles import N_WINDOW

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

# ---- S16：会话聚合 + 风险地板 ----
RANK = {"L1": 1, "L2": 2, "L3": 3}
NAME = {1: "L1", 2: "L2", 3: "L3"}
ESCALATE_AT = 3   # 窗口内 L2+ 达到 3 次才升 L3；用 3 不用 2，见 step/S16 §1


def _rank(level: str) -> int:
    """等级转序数；未知值按 L1 记（窗口只由 pre_check 写入，不接外部输入）。"""
    return RANK.get(level, 1)


def _name(value: int) -> str:
    """序数转等级，并夹在 1..3：聚合溢出也不许产生 L4 这种不存在的等级。"""
    return NAME.get(max(1, min(3, value)), "L1")


def risk_floor(history: list[str], current: str) -> str:
    """窗口内出现过 L2+ → 本轮至少 L2；L3 也只给 L2 地板。

    为什么 L3 不给 L3 地板：L3 当轮已经短路发过资源卡，若之后每轮仍按 L3
    处理，界面会连续五轮重复同一张卡，用户没法继续说话；执行书附录 C 的
    C-12 也要求危机后下一轮是 L2、角色回到 listener。
    为什么不能降：返回值取 max(floor, current)，current 更严重时一定保留。
    """
    recent = (history or [])[-N_WINDOW:]
    floor = 2 if any(_rank(x) >= 2 for x in recent) else 1
    return _name(max(floor, _rank(current)))


def aggregate_level(history: list[str], current: str) -> str:
    """近 N_WINDOW 轮（含本轮）真实 L2 恰好 3 次 → L3，否则走风险地板。

    history 必须是 pre_check 的原始等级（升到 L3 的那轮除外），不能存每轮的
    effective level：否则一次 L2 被地板抬成 L2 后每轮都在“凑数”，三轮就把
    所有用户打成 L3。升级那轮改存 L3，是为了让这 3 次 L2 不再重复触发。
    """
    window = ((history or []) + [current])[-N_WINDOW:]
    if sum(1 for x in window if x == "L2") >= ESCALATE_AT:
        return "L3"
    return risk_floor(history, current)