"""test_home.py — P17a：首屏列表、入口路由与常驻安全资源（AppTest）。"""
from __future__ import annotations

from pipeline import Chat
import home


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _click(at, key):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"


def test_home_has_twelve_cards_and_no_chat_input():
    at = Chat(enter=False).at
    assert at.session_state["mode"] == "home"
    assert len(at.chat_input) == 0
    keys = {b.key for b in at.button}
    assert set(home.LOCAL_PAGES) <= {k.removeprefix("home_") for k in keys}
    assert {"home_chat", "home_rolecard", "home_quiz", "home_random"} <= keys


def test_home_chat_enters_companion():
    at = Chat(enter=False).at
    _click(at, "home_chat")
    assert at.session_state["mode"] == "companion"
    assert len(at.chat_input) == 1


def test_home_rolecard_enters_gate():
    at = Chat(enter=False).at
    _click(at, "home_rolecard")
    assert at.session_state["mode"] == "rolecard"
    assert at.session_state["rc_consent"] is False
    assert len(at.chat_input) == 0


def test_home_relax_card_routes_and_returns():
    at = Chat(enter=False).at
    _click(at, "home_breath")
    assert at.session_state["mode"] == "relax"
    assert at.session_state["relax_page"] == "breath"
    _click(at, "relax_home")
    assert at.session_state["mode"] == "home"


def test_home_quiz_opens_standalone_page():
    at = Chat(enter=False).at
    _click(at, "home_quiz")
    assert at.session_state["mode"] == "quiz"
    assert at.session_state["quiz_state"] == "ack"
    assert len(at.chat_input) == 0
    _click(at, "quiz_page_home")
    assert at.session_state["mode"] == "home"


def test_home_random_stays_in_local_relax_pages():
    at = Chat(enter=False).at
    _click(at, "home_random")
    assert at.session_state["mode"] == "relax"
    assert at.session_state["relax_page"] in home.LOCAL_PAGES


def test_home_shows_crisis_resources_without_opening_anything():
    at = Chat(enter=False).at
    text = " ".join(str(item.value) for item in at.info)
    assert "12356" in text
    assert "86878592" in text
    assert "信达楼306" in text
    assert "杭电钉" in text


def test_home_flag_off_falls_back_to_companion(monkeypatch):
    monkeypatch.setenv("HOME_HUB", "0")
    at = Chat().at
    assert at.session_state["mode"] == "companion"
    assert len(at.chat_input) == 1
    assert [b for b in at.button if b.key == "home_chat"] == []
