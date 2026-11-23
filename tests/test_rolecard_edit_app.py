"""test_rolecard_edit_app.py — P39b：对话中查看/改卡与校验边界。"""
from __future__ import annotations

import agent
from pipeline import Chat
import rolecard
import rolecard_chat_store as store
import rolecard_edit


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _enter_b(chat: Chat) -> None:
    _by_key(chat.at.button, "rc_to_rolecard").click().run()
    _by_key(chat.at.checkbox, "rc_consent_box").check().run()
    _by_key(chat.at.button, "rc_load_example").click().run()
    _by_key(chat.at.button, "rc_start").click().run()
    assert not list(chat.at.exception)
    assert chat.at.session_state["rc_card"]["name"] == "阿岚"


def _send(chat: Chat, text: str) -> None:
    chat.at.chat_input[0].set_value(text).run()
    assert not list(chat.at.exception), list(chat.at.exception)


def _open_editor(chat: Chat) -> None:
    _by_key(chat.at.button, "rc_edit_btn").click().run()
    assert not list(chat.at.exception)
    assert chat.at.session_state["rc_edit_open"] is True


def test_panel_shows_current_card_and_locks_identity_keys():
    chat = Chat()
    _enter_b(chat)
    assert chat.at.session_state["rc_card"]["voice"]
    _open_editor(chat)
    for key in ("rc_edit_identity", "rc_edit_voice", "rc_edit_address",
                "rc_edit_user_role"):
        assert any(el.key == key for el in chat.at.text_input), key
    for key in ("rc_edit_setting", "rc_edit_lore_text"):
        assert any(el.key == key for el in chat.at.text_area), key
    assert [el for el in chat.at.text_input if el.key == "rc_edit_name"] == []
    assert [el for el in chat.at.text_input if el.key == "rc_edit_work"] == []
    assert any("名字、作品名和来源不能" in str(el.value) for el in chat.at.caption)


def test_edit_voice_applies_next_turn_without_resetting_session(monkeypatch):
    chat = Chat()
    _enter_b(chat)
    _send(chat, "今天有点累。")
    sid = chat.sid
    old_sid = chat.at.session_state["rc_sid"]
    old_messages = list(chat.at.session_state["rc_messages"])
    old_turn = chat.at.session_state["rc_state"]["turn"]

    _open_editor(chat)
    _by_key(chat.at.text_input, "rc_edit_voice").set_value("只说短句，不绕弯。").run()
    _by_key(chat.at.button, "rc_edit_save").click().run()
    assert not list(chat.at.exception)
    assert chat.at.session_state["rc_card"]["voice"] == "只说短句，不绕弯。"
    assert chat.at.session_state["rc_sid"] == old_sid
    assert chat.at.session_state["rc_messages"] == old_messages
    assert chat.at.session_state["rc_state"]["turn"] == old_turn
    assert store.load(sid, old_sid)["card"]["voice"] == "只说短句，不绕弯。"

    seen = {}
    real = agent.build_system_prompt

    def spy(card, memory, lore):
        prompt = real(card, memory, lore)
        seen["prompt"] = prompt
        return prompt

    monkeypatch.setattr(agent, "build_system_prompt", spy)
    _send(chat, "下一句。")
    assert "只说短句，不绕弯。" in seen["prompt"]

    again = Chat(sid=sid)
    _by_key(again.at.button, "rc_to_rolecard").click().run()
    _by_key(again.at.checkbox, "rc_consent_box").check().run()
    _by_key(again.at.button, f"rc_open_{old_sid}").click().run()
    assert again.at.session_state["rc_card"]["voice"] == "只说短句，不绕弯。"


def test_invalid_content_is_rejected_and_card_stays():
    chat = Chat()
    _enter_b(chat)
    old = dict(chat.at.session_state["rc_card"])
    _open_editor(chat)
    _by_key(chat.at.text_input, "rc_edit_identity").set_value("我是你的心理咨询师").run()
    _by_key(chat.at.button, "rc_edit_save").click().run()
    assert not list(chat.at.exception)
    assert chat.at.session_state["rc_edit_open"] is True
    assert chat.at.session_state["rc_edit_errors"]
    assert chat.at.session_state["rc_card"] == old
    assert any("专业身份" in str(el.value) for el in chat.at.error)


def test_prompt_budget_is_checked_with_current_memory(monkeypatch):
    card = rolecard.normalize(rolecard.EXAMPLE_CARD)
    new_card = dict(card, voice="短句")
    monkeypatch.setattr(rolecard_edit.rolecard_memory, "read",
                        lambda *a, **k: {"_block": "很长" * 3000})
    errors = rolecard_edit._errors(card, new_card)
    assert errors and "提示词" in errors[0]


def test_edit_flag_off_hides_panel(monkeypatch):
    monkeypatch.setenv("ROLECARD_EDIT", "0")
    chat = Chat()
    _enter_b(chat)
    assert [b.key for b in chat.at.button if b.key == "rc_edit_btn"] == []
    assert chat.at.session_state["rc_edit_open"] is False
