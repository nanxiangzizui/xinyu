"""test_rolecard_history_app.py — P39a：保存、列出、继续、删除与开关。"""
from __future__ import annotations

from pipeline import Chat
import rolecard_chat_store as store


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _to_rolecard(chat: Chat) -> None:
    _by_key(chat.at.button, "rc_to_rolecard").click().run()
    assert not list(chat.at.exception)


def _consent(chat: Chat) -> None:
    _by_key(chat.at.checkbox, "rc_consent_box").check().run()
    assert not list(chat.at.exception)
    assert chat.at.session_state["rc_consent"] is True


def _start_example(chat: Chat) -> None:
    _by_key(chat.at.button, "rc_load_example").click().run()
    _by_key(chat.at.button, "rc_start").click().run()
    assert not list(chat.at.exception)
    assert chat.at.session_state["rc_card"]["name"] == "阿岚"


def _enter_b(chat: Chat) -> None:
    _to_rolecard(chat)
    _consent(chat)
    _start_example(chat)


def _send(chat: Chat, text: str) -> None:
    chat.at.chat_input[0].set_value(text).run()
    assert not list(chat.at.exception), list(chat.at.exception)
    assert chat.at.session_state["rc_messages"][-2] == {"role": "user", "content": text}


def _open_history(chat: Chat) -> None:
    _by_key(chat.at.button, "rc_history").click().run()
    assert not list(chat.at.exception)


def test_one_turn_is_saved_and_listed():
    chat = Chat()
    _enter_b(chat)
    _send(chat, "今天有点累。")
    sid = chat.sid
    assert len(chat.at.session_state["rc_messages"]) == 2
    assert chat.at.session_state["rc_state"]["turn"] == 1
    assert store.count(sid) == 1
    row = store.list_chats(sid)[0]
    assert row["card_name"] == "阿岚" and row["turns"] == 1
    assert row["title"].startswith("阿岚 · ")


def test_reopen_same_sid_restores_and_continues():
    first = Chat()
    _enter_b(first)
    _send(first, "今天有点累。")
    sid = first.sid
    conv = store.list_chats(sid)[0]["id"]

    again = Chat(sid=sid)
    _to_rolecard(again)
    _consent(again)
    assert again.at.session_state["rc_card"] is None
    assert store.count(sid) == 1
    _by_key(again.at.button, f"rc_open_{conv}").click().run()
    assert not list(again.at.exception)
    assert again.at.session_state["rc_sid"] == conv
    assert len(again.at.session_state["rc_messages"]) == 2
    assert again.at.session_state["rc_state"]["turn"] == 1
    assert again.at.session_state["rc_card"]["name"] == "阿岚"

    _send(again, "刚才说到哪儿了？")
    assert len(again.at.session_state["rc_messages"]) == 4
    assert again.at.session_state["rc_state"]["turn"] == 2
    assert store.count(sid) == 1


def test_new_conversation_does_not_overwrite_old():
    chat = Chat()
    _enter_b(chat)
    _send(chat, "第一段。")
    sid = chat.sid
    _open_history(chat)
    _by_key(chat.at.button, "rc_new_chat").click().run()
    assert not list(chat.at.exception)
    _start_example(chat)
    _send(chat, "第二段。")
    rows = store.list_chats(sid)
    assert len(rows) == 2
    assert len({row["id"] for row in rows}) == 2


def test_delete_requires_confirmation_and_really_deletes():
    chat = Chat()
    _enter_b(chat)
    _send(chat, "要删的这一段。")
    sid = chat.sid
    conv = store.list_chats(sid)[0]["id"]
    _open_history(chat)
    _by_key(chat.at.button, f"rc_del_{conv}").click().run()
    assert store.count(sid) == 1          # 只点删除还没确认
    _by_key(chat.at.button, f"rc_del_yes_{conv}").click().run()
    assert not list(chat.at.exception)
    assert store.count(sid) == 0
    assert store.load(sid, conv) is None


def test_l3_record_opens_on_ended_page_and_resume_keeps_floor():
    chat = Chat()
    _enter_b(chat)
    _send(chat, "我不想活了。")
    sid = chat.sid
    assert chat.at.session_state["rc_ended"] is True
    assert chat.at.session_state["rc_state"]["ever_crisis"] is True
    assert store.count(sid) == 1

    again = Chat(sid=sid)
    _to_rolecard(again)
    _consent(again)
    conv = store.list_chats(sid)[0]["id"]
    _by_key(again.at.button, f"rc_open_{conv}").click().run()
    assert again.at.session_state["rc_ended"] is True
    assert len(again.at.chat_input) == 0
    _by_key(again.at.button, "rc_resume").click().run()
    assert again.at.session_state["rc_ended"] is False
    assert again.at.session_state["rc_state"]["ever_crisis"] is True
    _send(again, "今天还好。")
    assert again.at.session_state["rc_state"]["last_level"] in ("L2", "L3")


def test_history_flag_off_is_old_behavior(monkeypatch):
    monkeypatch.setenv("ROLECARD_HISTORY", "0")
    chat = Chat()
    _enter_b(chat)
    _send(chat, "不落盘的一段。")
    assert store.count(chat.sid) == 0
    assert not store._dir(chat.sid).exists()
    assert [b.key for b in chat.at.button if b.key == "rc_history"] == []


def test_about_counts_and_clear_rolecard_chats():
    import about
    chat = Chat()
    _enter_b(chat)
    _send(chat, "关于页要数到这一段。")
    sid = chat.sid
    assert about.counts(sid)["rolecard_chats"] == 1
    assert about.delete(sid, ["rolecard_chats"]) == ["rolecard_chats"]
    assert about.counts(sid)["rolecard_chats"] == 0
