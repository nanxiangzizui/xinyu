"""test_flow.py — S11：三角色状态机。

4 条覆盖 S11 §5.5 的四行，外加冷却/记忆两条硬要求的断言：
  - L3 永远 crisis（等级压倒文本）
  - 求助词切 guide（C-05）
  - 默认 listener（C-01 不误切）
  - 冷却 / 历史危机只降 guide，且永不回 guide

S16 另加 5 条：聚合升 L3、风险地板只升不降、窗口外旧等级不再算数。
"""
from __future__ import annotations

from coordinator import (ADVICE_WORDS, REASONS, aggregate_level, coordinator_decide,
                         enforce_cooldown, risk_floor)


def test_l3_always_crisis():
    """L3 不看用户说什么：普通句、求助句都必须是 crisis。"""
    for text in ("今天天气不错", "我该怎么办"):
        dec = coordinator_decide({}, text, "L3")
        assert dec == {"role": "crisis", "reason": "crisis_shortcircuit"}, text
        assert dec["reason"] in REASONS


def test_advice_word_switches_guide():
    """C-05 原句含“怎么办”，必须切 guide；词表里每个词单独出现也要命中。"""
    for text in ("我该怎么办", "我不知道怎么办，你说我是不是该放弃"):
        dec = coordinator_decide({"current_role": "listener"}, text, "L1")
        assert dec == {"role": "guide", "reason": "user_ask_advice"}, text
        assert dec["reason"] in REASONS
    for word in ADVICE_WORDS:
        dec = coordinator_decide({}, f"这件事{word}", "L1")
        assert dec["role"] == "guide", word


def test_default_stays_listener():
    """C-01 只是在抱怨室友，没有求助词，不许误切 guide。"""
    assert coordinator_decide({}, "今天好累", "L1") == {
        "role": "listener", "reason": "default"}
    dec = coordinator_decide({}, "最近和室友处得不好，回宿舍就烦", "L1")
    assert dec == {"role": "listener", "reason": "default"}


def test_cooldown_and_after_crisis_never_guide():
    """冷却期降 listener；有过危机永不回 guide；listener/crisis 不受影响。"""
    guide = {"role": "guide", "reason": "user_ask_advice"}
    assert enforce_cooldown(guide, 2, False) == {
        "role": "listener", "reason": "crisis_cooldown"}
    assert enforce_cooldown(guide, 0, True) == {
        "role": "listener", "reason": "after_crisis"}
    assert enforce_cooldown(guide, 0, False) == guide
    listener = {"role": "listener", "reason": "default"}
    assert enforce_cooldown(listener, 2, True) == listener
    # 记忆里的历史危机：本轮即使有求助词，也只回 listener。
    dec = coordinator_decide({"current_role": "crisis"}, "我该怎么办", "L1")
    assert dec == {"role": "listener", "reason": "after_crisis"}
    assert dec["reason"] in REASONS

# ---- S16：会话聚合 + 风险地板（step/S16-window-floor.md） ----

def test_floor_empty_history_returns_current():
    """没有历史时地板就是本轮原文等级，不许凭空抬高。"""
    assert risk_floor([], "L1") == "L1"
    assert aggregate_level([], "L1") == "L1"


def test_floor_crisis_leaves_l2_not_l3():
    """窗口里出现过 L3，之后地板是 L2 而不是 L3。

    危机当轮已经发过资源卡并短路；若地板继续给 L3，之后每一轮都会再次
    短路发同一张卡，用户没法继续说话。执行书附录 C 的 C-12 也要求
    危机后下一轮只到 L2、角色回到 listener。
    """
    assert risk_floor(["L3"], "L1") == "L2"
    assert risk_floor(["L3", "L2"], "L1") == "L2"
    assert aggregate_level(["L3", "L2"], "L1") == "L2"


def test_aggregate_three_l2_in_window_escalates():
    """5 轮内第 3 次 L2 才升 L3；升级看的是真实命中，不是被地板抬上来的等级。"""
    assert aggregate_level(["L2", "L2", "L1"], "L2") == "L3"
    assert risk_floor(["L2", "L2", "L1"], "L2") == "L2"
    # 升级那轮在窗口里记成 L3，下一轮平静句只回到地板 L2，不再重复短路发卡。
    assert aggregate_level(["L2", "L2", "L3"], "L1") == "L2"


def test_aggregate_two_l2_does_not_escalate():
    """只有 2 次 L2 不许升级：用 3 不用 2，避免两次情绪低落就发危机卡。"""
    assert aggregate_level(["L2", "L2"], "L1") == "L2"
    assert aggregate_level(["L2", "L1", "L1"], "L2") == "L2"


def test_aggregate_never_lowers_level():
    """只升不降：任何历史组合下，输出等级都不得低于本轮输入等级。"""
    order = {"L1": 1, "L2": 2, "L3": 3}
    histories = ([], ["L1"], ["L2"], ["L3"], ["L2", "L1", "L3"], ["L1"] * 5)
    for history in histories:
        for current in ("L1", "L2", "L3"):
            assert order[aggregate_level(list(history), current)] >= order[current]
            assert order[risk_floor(list(history), current)] >= order[current]