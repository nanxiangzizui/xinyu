"""test_triage.py — P27 首屏四选一分诊。

分诊只做路由：难受 → 求助页 / 想说说 → 聊天 / 朋友出事 → 朋友页 /
逛逛 → 收起卡片。断言元素、session_state 与磁盘，不碰模型。
"""
from __future__ import annotations

import home
import resources
from pipeline import Chat, memory_path, rows


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _click(at, key):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"


def _keys(at) -> set[str]:
    return {b.key for b in at.button}


def _text(at) -> str:
    chunks = []
    for kind in ("subheader", "markdown", "info", "caption", "code", "success"):
        chunks += [str(el.value) for el in getattr(at, kind, [])]
    return " ".join(chunks)


def test_home_shows_four_choices_and_no_input():
    at = Chat(enter=False).at
    assert {"home_help_self", "home_talk", "home_help_friend",
            "home_browse"} <= _keys(at)
    assert len(at.chat_input) == 0
    assert "你现在想做哪件事" in _text(at)
    keys = [b.key for b in at.button]
    # 两个求助入口排在十二项列表之前：最难受的人不会往下翻。
    assert keys.index("home_help_self") < keys.index("home_chat")
    assert keys.index("home_help_friend") < keys.index("home_chat")


def test_hurt_opens_help_page():
    at = Chat(enter=False).at
    _click(at, "home_help_self")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "self"
    assert len(at.chat_input) == 0
    text = _text(at)
    assert "先打这一个" in text
    assert "12356" in text and resources.CAMPUS_PHONE in text


def test_talk_opens_companion():
    at = Chat(enter=False).at
    _click(at, "home_talk")
    assert at.session_state["mode"] == "companion"
    assert len(at.chat_input) == 1


def test_friend_opens_friend_page():
    at = Chat(enter=False).at
    _click(at, "home_help_friend")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "friend"
    text = _text(at)
    assert "别答应" in text and "120" in text and "辅导员" in text


def test_browse_collapses_but_keeps_safety_buttons():
    chat = Chat(enter=False)
    at = chat.at
    _click(at, "home_browse")
    assert at.session_state[home.BROWSE_KEY] is True
    keys = _keys(at)
    assert "home_talk" not in keys and "home_browse" not in keys
    # 收起后两个求助入口与十二项列表都还在，资源卡也没少。
    assert {"home_help_self", "home_help_friend", "home_triage_on",
            "home_chat", "home_ground"} <= keys
    text = _text(at)
    assert "12356" in text and resources.CAMPUS_PHONE in text


def test_expand_restores_four_choices():
    at = Chat(enter=False).at
    _click(at, "home_browse")
    _click(at, "home_triage_on")
    assert home.BROWSE_KEY not in at.session_state
    assert {"home_help_self", "home_talk", "home_help_friend",
            "home_browse"} <= _keys(at)


def test_browse_writes_no_logs_or_memory():
    chat = Chat(enter=False)
    before = len(rows(chat.sid))
    _click(chat.at, "home_browse")
    assert len(rows(chat.sid)) == before
    assert not memory_path(chat.sid).exists()


def test_compact_safety_still_opens_help():
    at = Chat(enter=False).at
    _click(at, "home_browse")
    _click(at, "home_help_self")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "self"
