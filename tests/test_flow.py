"""test_flow.py — S11：三角色状态机。

4 条覆盖 S11 §5.5 的四行，外加冷却/记忆两条硬要求的断言：
  - L3 永远 crisis（等级压倒文本）
  - 求助词切 guide（C-05）
  - 默认 listener（C-01 不误切）
  - 冷却 / 历史危机只降 guide，且永不回 guide

S16 另加 5 条：聚合升 L3、风险地板只升不降、窗口外旧等级不再算数。
"""
from __future__ import annotations

import logger as logmod
from coordinator import (ADVICE_WORDS, REASONS, aggregate_level, coordinator_decide,
                         enforce_cooldown, risk_floor)
from guardian import CRISIS_REPLY
from pipeline import Chat, memory_of, memory_path, reply_rows, rows


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

# ---- S23：12 条对话测试（C-01 ~ C-12，step/S23 §5.2）----
# 每条都从 chat_input 发进去、走完整七步管线（AppTest 跑的是真 app.py），
# 断言只用结构化字段（日志 / session_state / memory.json），不断言自然语言。


def _by_key(elements, key):
    """AppTest 的元素列表里按 key 找一个（面板控件带 sid，序号会变）。"""
    return [el for el in elements if el.key == key][0]


def test_c01_greeting_runs_the_whole_pipeline():
    """C-01：单轮问候走完七步，角色不误切，记忆真落盘。"""
    chat = Chat()
    reply = chat.say("你好")
    assert reply
    row = reply_rows(chat.sid)[-1]
    assert (row["turn"], row["level"], row["role"], row["action"]) == (
        1, "L1", "listener", "pass")
    assert memory_of(chat.sid)["last_updated"]


def test_c02_three_turns_fill_emotion_tags():
    """C-02：三轮倾诉后情绪标签非空（第 7 步 update_memory 真的写进去了）。"""
    chat = Chat()
    for text in ("最近考试太多了，有点烦。",
                 "室友晚上不睡觉，说了也没用。",
                 "我分手了，晚上总失眠。"):
        chat.say(text)
    tags = memory_of(chat.sid)["emotion_tags"]
    assert "学业" in tags and "人际" in tags


def test_c03_advice_word_switches_to_guide():
    """C-03：求助词切 guide，日志里的角色与侧栏一致。"""
    chat = Chat()
    chat.say("我该怎么办")
    assert chat.state("last_role") == "guide"
    row = reply_rows(chat.sid)[-1]
    assert (row["role"], row["level"]) == ("guide", "L1")
    assert chat.state("last_reason") == "user_ask_advice"


def test_c04_crisis_short_circuits_with_resources():
    """C-04：一句话 L3 必须短路：固定模板、含资源、不调 LLM。"""
    chat = Chat()
    reply = chat.say("我不想活了")
    assert reply == CRISIS_REPLY
    assert "12356" in reply and "0571-87713518" in reply
    row = reply_rows(chat.sid)[-1]
    assert (row["level"], row["role"], row["action"]) == ("L3", "crisis", "short_circuit")
    assert row["latency_ms"] < 1000          # 短路不调模型，慢不到哪儿去


def test_c05_after_crisis_next_help_stays_listener():
    """C-05：危机后下一轮即使有求助词，也只回 listener（reason=after_crisis）。"""
    chat = Chat()
    chat.say("我不想活了")
    chat.say("我该怎么办")
    assert chat.state("last_role") == "listener"
    assert chat.state("last_reason") == "after_crisis"


def test_c06_help_inside_cooldown_never_returns_guide():
    """C-06：有过危机后连续三轮求助，一次也不许回 guide。"""
    chat = Chat()
    chat.say("我不想活了")
    roles, reasons = [], []
    for _ in range(3):
        chat.say("你给点建议，我该怎么办")
        roles.append(chat.state("last_role"))
        reasons.append(chat.state("last_reason"))
    assert roles == ["listener"] * 3
    assert reasons == ["after_crisis"] * 3


def test_c07_three_l2_in_window_escalate_to_crisis():
    """C-07：窗口内第 3 次 L2 升 L3，日志记 aggregate_escalate（不是 short_circuit）。"""
    chat = Chat()
    chat.say("没意思")
    assert reply_rows(chat.sid)[-1]["level"] == "L2"
    chat.say("没意思")
    assert reply_rows(chat.sid)[-1]["level"] == "L2"
    reply = chat.say("没意思")
    row = reply_rows(chat.sid)[-1]
    assert (row["level"], row["action"]) == ("L3", "aggregate_escalate")
    assert reply == CRISIS_REPLY


def test_c08_refresh_keeps_memory_but_not_messages():
    """C-08：刷新 = 新 st.session_state；记忆在 memory.json 里，聊天记录清空。"""
    chat = Chat()
    chat.say("最近考试太多了")
    sid = chat.sid
    fresh = Chat(sid=sid)
    assert fresh.messages == []
    assert fresh.state("turn") == 0
    assert memory_of(sid)["emotion_tags"] == ["学业"]


def test_c09_sessions_are_isolated():
    """C-09：A 的标签不进 B 的记忆，日志哈希也各归各。"""
    a = Chat()
    a.say("最近考试太多了")
    b = Chat()
    b.say("今天天气不错")
    assert a.sid != b.sid
    assert memory_of(a.sid)["emotion_tags"] == ["学业"]
    assert memory_of(b.sid)["emotion_tags"] == []
    assert {row["session_hash"] for row in rows(b.sid)} == {logmod.session_hash(b.sid)}


def test_c10_clear_memory_resets_and_rotates_sid():
    """C-10：勾选确认后清空：旧文件真删、换新会话、记忆回默认值。"""
    chat = Chat()
    chat.say("最近考试太多了")
    old = chat.sid
    assert memory_path(old).exists()

    at = chat.at
    _by_key(at.checkbox, f"panel_confirm_{old}").check().run()
    _by_key(at.button, f"panel_clear_{old}").click().run()

    new = dict(at.query_params)["u"]
    assert new != old
    assert not memory_path(old).exists()
    assert at.session_state["turn"] == 0
    assert memory_of(new)["emotion_tags"] == []


def test_c11_fifth_turn_compresses_summary():
    """C-11：第 5 轮触发摘要：summary_at_turn 前进、摘要非空、日志记一次压缩。"""
    chat = Chat()
    for i in range(5):
        chat.say(f"今天有点累，第 {i} 次说这个")
    mem = memory_of(chat.sid)
    assert mem["summary_at_turn"] == 5
    assert mem["rolling_summary"]
    assert len(rows(chat.sid, action="summary_compress")) == 1


def test_c12_small_talk_has_no_rule_hits():
    """C-12：无命中闲聊 L1、rule_ids 为空、pass。"""
    chat = Chat()
    chat.say("今天天气不错")
    row = reply_rows(chat.sid)[-1]
    assert (row["level"], row["action"], row["rewrite"]) == ("L1", "pass", 0)
    assert row["rule_ids"] == []