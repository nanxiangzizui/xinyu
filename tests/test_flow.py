"""test_flow.py — S11：三角色状态机。

4 条覆盖 S11 §5.5 的四行，外加冷却/记忆两条硬要求的断言：
  - L3 永远 crisis（等级压倒文本）
  - 求助词切 guide（C-05）
  - 默认 listener（C-01 不误切）
  - 冷却 / 历史危机只降 guide，且永不回 guide
"""
from __future__ import annotations

from coordinator import ADVICE_WORDS, REASONS, coordinator_decide, enforce_cooldown


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
