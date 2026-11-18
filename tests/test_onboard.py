"""test_onboard.py — 开场偏好：翻译表、白名单写入、prompt 注入与首屏卡片。

不测界面文案本身（改字不该变红），只测：答案翻成哪些字段、写入是否越界、
卡片是否挡路、跳过是否留痕。
"""
from __future__ import annotations

import memory
import onboard
import roles
import style
from agent import build_system_prompt
from pipeline import Chat


def _by_key(elements, key):
    """按 widget key 取控件（页面上控件多，序号不稳定）。"""
    return [el for el in elements if el.key == key][0]


def _keys(at):
    return {el.key for el in at.radio if el.key.startswith("ob_")}


def test_derive_maps_mood_and_topic():
    """状态题只产出标签：心情 1 条、心事 1 条，不产出等级。"""
    plan = onboard.derive({"mood": "有点闷", "topic": "和人相处"})
    assert plan["tags"] == ["低落", "人际"]
    assert plan["tone"] == "neutral"


def test_derive_maps_style_to_tone_and_pref():
    """方式题同时决定 preferred_tone 与一条可读的偏好短语。"""
    plan = onboard.derive({"style": "轻松一点", "company": "先自己待会儿"})
    assert plan["tone"] == "light"
    assert plan["prefs"] == ["想轻松一点", "先自己待会儿，不用追问"]


def test_derive_skips_unanswered():
    """全不答 / 答「说不上来」：不回退成猜测，给默认 tone 与空列表。"""
    for answers in ({}, {"mood": None, "topic": "说不上来", "style": "说不好"}):
        plan = onboard.derive(answers)
        assert plan == {"tone": "neutral", "tags": [], "prefs": []}


def test_derive_never_echoes_answer_text():
    """固定选项只翻成表里的值：用户选的原词不会流进记忆。"""
    plan = onboard.derive({"mood": "挺难的", "topic": "家里的事",
                           "style": "直说就行", "start": "先给我一句"})
    assert plan["tags"] == ["低落", "疲惫", "家庭"]
    assert all("挺难的" not in item for item in plan["tags"] + plan["prefs"])


def test_apply_writes_only_whitelisted_fields():
    """写盘后除 8 字段 + summary_at_turn 外不许新增键；标签受上限约束。"""
    sid = "onb-write"
    onboard.apply(sid, {"mood": "挺好", "topic": "学习或工作", "style": "听我说"})
    mem = memory.read_memory(sid)
    assert set(mem) <= memory.ALLOWED
    assert mem["preferred_tone"] == "gentle"
    assert mem["emotion_tags"] == ["平稳", "学业"]
    assert mem["coping_preferences"] == ["先听我说完"]


def test_apply_merges_instead_of_overwriting():
    """重复做开场：语气覆盖，标签与偏好并入历史，不删旧的。"""
    sid = "onb-merge"
    memory.write_memory(sid, {"emotion_tags": ["学业"], "coping_preferences": ["散步"]})
    onboard.apply(sid, {"topic": "和人相处", "style": "轻松一点"})
    mem = memory.read_memory(sid)
    assert mem["emotion_tags"] == ["学业", "人际"]
    assert mem["coping_preferences"] == ["散步", "想轻松一点"]


def test_tone_line_only_for_chosen_tones():
    """neutral 不产生指令行（避免空指令）；三个明确偏好各有一句中文。"""
    assert style.tone_line("neutral") == "" and style.tone_line("weird") == ""
    assert "温柔" in style.tone_line("gentle")
    assert "轻松" in style.tone_line("light")
    assert "结论" in style.tone_line("direct")
    assert set(style.TONE_LABELS) == {"neutral", "gentle", "light", "direct"}


def test_prompt_carries_chinese_tone_line():
    """记忆里的语气偏好要变成中文指令进 prompt，而不是枚举码。"""
    prompt = build_system_prompt("sister_heart", {"preferred_tone": "gentle"}, [])
    assert "温柔一点" in prompt
    assert "gentle" not in prompt
    # neutral 与“没有偏好”同效：不追加空指令。
    assert build_system_prompt("sister_heart", {"preferred_tone": "neutral"}, []) == \
        build_system_prompt("sister_heart", {}, [])


def test_first_screen_offers_five_questions():
    """首屏有卡片、五道单选、聊天输入仍在（引导不挡路）。"""
    at = Chat().at
    assert _keys(at) == {"ob_mood", "ob_topic", "ob_company", "ob_style", "ob_start"}
    assert len(at.chat_input) == 1
    assert at.session_state["messages"] == []


def test_start_saves_preference_and_hides_card():
    """答完点开始：写入语气、卡片消失、只留一行预设结果。"""
    chat = Chat()
    at = chat.at
    _by_key(at.radio, "ob_mood").set_value("有点闷").run()
    _by_key(at.radio, "ob_style").set_value("直说就行").run()
    _by_key(at.button, "ob_submit").click().run()
    assert not list(at.exception), list(at.exception)
    assert at.session_state["onboard_done"] is True
    assert _keys(at) == set()
    assert any("开场偏好：直接" in cap.value for cap in at.caption)
    assert memory.read_memory(chat.sid)["preferred_tone"] == "direct"
    assert memory.read_memory(chat.sid)["emotion_tags"] == ["低落"]


def test_skip_hides_card_and_writes_nothing():
    """跳过：不再显示卡片，也没有任何偏好被写进去（空文件是侧栏读取时补的）。"""
    chat = Chat()
    at = chat.at
    _by_key(at.button, "ob_skip").click().run()
    assert at.session_state["onboard_done"] is True
    assert _keys(at) == set()
    assert not any("开场偏好" in cap.value for cap in at.caption)
    mem = memory.read_memory(chat.sid)
    assert (mem["preferred_tone"], mem["emotion_tags"],
            mem["coping_preferences"]) == ("neutral", [], [])


def test_edit_reopens_the_card():
    """答完还能改：点「改一下」卡片回来，之前的选择仍在控件里。"""
    chat = Chat()
    at = chat.at
    _by_key(at.radio, "ob_mood").set_value("挺好").run()
    _by_key(at.button, "ob_submit").click().run()
    _by_key(at.button, "ob_edit").click().run()
    assert at.session_state["onboard_done"] is False
    assert _by_key(at.radio, "ob_mood").value == "挺好"


def test_start_choice_gives_an_opening_line():
    """选「先给我一句」：确认后立刻有一条不带问号的开场白，而不是没反应。"""
    chat = Chat()
    at = chat.at
    _by_key(at.radio, "ob_start").set_value("先给我一句").run()
    _by_key(at.button, "ob_submit").click().run()
    msgs = at.session_state["messages"]
    assert len(msgs) == 1
    assert msgs[0] == {"role": "assistant",
                       "content": roles.OPENING_STATEMENTS["sister_heart"],
                       "opening": True}
    assert at.session_state["turn"] == 0
    # 首句用户输入之前，预设结果与「改一下」仍然留着。
    assert any("开场偏好" in cap.value for cap in at.caption)


def test_start_choice_ask_me_uses_a_question():
    """选「先问我一句」给问句；选「我自己说」不给任何开场白。"""
    chat = Chat()
    at = chat.at
    _by_key(at.radio, "ob_start").set_value("先问我一句").run()
    _by_key(at.button, "ob_submit").click().run()
    assert at.session_state["messages"][0]["content"] == \
        roles.OPENING_LINES["sister_heart"]

    chat = Chat()
    at = chat.at
    _by_key(at.radio, "ob_start").set_value("我自己说").run()
    _by_key(at.button, "ob_submit").click().run()
    assert at.session_state["messages"] == []


def test_opening_does_not_inflate_first_turn():
    """开场白不是一轮回复：首句用户输入之后轮次仍是 1。"""
    chat = Chat()
    at = chat.at
    _by_key(at.radio, "ob_start").set_value("先给我一句").run()
    _by_key(at.button, "ob_submit").click().run()
    chat.say("今天有点累")
    assert chat.state("turn") == 1
    assert [m["role"] for m in chat.messages] == ["assistant", "user", "assistant"]


def test_edit_replaces_the_old_opening():
    """「改一下」换开口方式：旧开场白撤掉，只留新的那句。"""
    chat = Chat()
    at = chat.at
    _by_key(at.radio, "ob_start").set_value("先给我一句").run()
    _by_key(at.button, "ob_submit").click().run()
    _by_key(at.button, "ob_edit").click().run()
    _by_key(at.radio, "ob_start").set_value("先问我一句")
    _by_key(at.button, "ob_submit").click().run()
    msgs = at.session_state["messages"]
    assert len(msgs) == 1
    assert msgs[0]["content"] == roles.OPENING_LINES["sister_heart"]


def test_chat_works_without_answering():
    """不答直接打字也能聊：卡片随首条消息让位，回复照常。"""
    chat = Chat()
    chat.say("今天有点累")
    at = chat.at
    at.run()                            # 第一帧仍画着卡片，下一帧才收起来
    assert len(at.session_state["messages"]) == 2
    assert _keys(at) == set()
