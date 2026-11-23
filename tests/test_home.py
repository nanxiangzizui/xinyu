"""test_home.py — P17a：首屏列表、入口路由与常驻安全资源（AppTest）。"""
from __future__ import annotations

from pipeline import Chat
import home


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _click(at, key):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"


def test_home_has_compact_sections_and_no_chat_input():
    at = Chat(enter=False).at
    assert at.session_state["mode"] == "home"
    assert len(at.chat_input) == 0
    keys = {b.key for b in at.button}
    card_keys = {item[4] for _, items in home.GROUPS for item in items}
    assert len(home.GROUPS) == 4
    assert card_keys <= keys
    assert home.ABOUT[4] in keys
    assert "home_random" not in keys


def test_home_merges_school_and_counsel_entries():
    """P46：咨询前后不再单独占组，与学校三张页合并；关于心屿收进页尾。"""
    titles = [title for title, _ in home.GROUPS]
    assert "要跟学校打交道时" not in titles
    assert "关于心屿" not in titles
    merged = {item[4] for _, items in home.GROUPS for item in items}
    assert {"home_before", "home_after", "home_teacher",
            "home_leave", "home_accompany"} <= merged
    assert "home_about" not in merged


def test_home_removed_random_button():
    """P46：删掉页尾「随便来一个」，不再有随机跳转。"""
    at = Chat(enter=False).at
    assert "home_random" not in {b.key for b in at.button}
    assert not [b for b in at.button if "随便" in b.label]


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
    _click(at, "nav_back")
    assert at.session_state["mode"] == "home"


def test_home_quiz_opens_standalone_page():
    at = Chat(enter=False).at
    _click(at, "home_quiz")
    assert at.session_state["mode"] == "quiz"
    assert at.session_state["quiz_state"] == "ack"
    assert len(at.chat_input) == 0
    _click(at, "nav_back")
    assert at.session_state["mode"] == "home"


def test_home_about_stays_reachable_from_footer():
    at = Chat(enter=False).at
    _click(at, "home_about")
    assert at.session_state["mode"] == "about"


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
