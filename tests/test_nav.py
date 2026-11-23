"""test_nav.py — P41 全局「返回上一级」：页面顶部（分界线右侧）的按钮 + 会话内页面栈。

验证四件事：首页不可用；每个子页都有、都能回；退的是来路而不是写死的父页；
没有来路时回最上一级。不碰模型、不写记忆。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import Chat

ROOT = Path(__file__).resolve().parents[1]


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _click(at, key):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"


def test_home_has_back_button_but_disabled():
    at = Chat(enter=False).at
    btn = _by_key(at.button, "nav_back")
    assert btn.label == "← 返回上一级"
    assert btn.disabled is True
    # 位置：在分界线右侧的主区，不在侧栏里。
    assert "nav_back" not in [b.key for b in at.sidebar.button]


def test_back_button_is_page_top_before_title():
    """按钮在标题之上、配色之前：源码顺序也必须一样。"""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert src.index("back_button()") < src.index('st.title("心屿")')
    assert src.index("back_button()") < src.index("theme_picker()")


@pytest.mark.parametrize("key, mode", [
    ("home_chat", "companion"),
    ("home_rolecard", "rolecard"),
    ("home_breath", "relax"),
    ("home_quiz", "quiz"),
    ("home_help_self", "help"),
    ("home_about", "about"),
])
def test_every_page_has_back_and_returns_home(key, mode):
    at = Chat(enter=False).at
    _click(at, key)
    assert at.session_state["mode"] == mode
    assert _by_key(at.button, "nav_back").disabled is False
    _click(at, "nav_back")
    assert at.session_state["mode"] == "home"
    assert _by_key(at.button, "nav_back").disabled is True


def test_help_scene_backs_to_index_not_home():
    """子页的上一级是来路：索引 → 场景 → 索引 → 首页。"""
    at = Chat(enter=False).at
    _click(at, "home_index")
    assert at.session_state["help_page"] == "index"
    _click(at, "idx_sleep")
    assert at.session_state["help_page"] == "sleep"
    _click(at, "nav_back")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "index"
    _click(at, "nav_back")
    assert at.session_state["mode"] == "home"


def test_about_paper_backs_to_about():
    at = Chat(enter=False).at
    _click(at, "home_about")
    _click(at, "about_paper")
    assert at.session_state["help_page"] == "paper"
    _click(at, "nav_back")
    assert at.session_state["mode"] == "about"


def test_relax_journal_from_index_backs_to_index():
    """同一个 relax 页可以从首页或索引进来：退回到真正的那条路。"""
    at = Chat(enter=False).at
    _click(at, "home_index")
    _click(at, "idx_journal")
    assert at.session_state["mode"] == "relax"
    assert at.session_state["relax_page"] == "journal"
    _click(at, "nav_back")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "index"


def test_back_without_history_goes_home():
    """直接落到子页（没有来路）时，上一级是首页。"""
    at = Chat(enter=False).at
    at.session_state["mode"] = "help"
    at.session_state["help_page"] = "accompany"
    at.session_state["nav_last"] = ("help", "accompany")
    at.session_state["nav_stack"] = []
    at.run()
    assert not list(at.exception)
    _click(at, "nav_back")
    assert at.session_state["mode"] == "home"


def test_back_to_rolecard_keeps_the_card_session():
    """回角色卡不是新建会话：rc_* 仍在，不能退回免责页/空表单。"""
    at = Chat(enter=False).at
    _click(at, "home_rolecard")
    sid = at.session_state["rc_sid"]
    _click(at, "rc_to_companion")
    assert at.session_state["mode"] == "companion"
    _click(at, "nav_back")
    assert at.session_state["mode"] == "rolecard"
    assert at.session_state["rc_sid"] == sid


# P42：侧栏常驻「与心屿交流一下」——任何页面都能一步回陪伴模式。
TALK = "与心屿交流一下"


def test_sidebar_talk_button_on_home():
    at = Chat(enter=False).at
    btn = _by_key(at.sidebar.button, "nav_talk")
    assert btn.label == TALK
    assert btn.disabled is False


@pytest.mark.parametrize("key", [
    "home_index", "home_help_self", "home_about",
    "home_breath", "home_quiz", "home_rolecard",
])
def test_talk_button_stays_on_every_page(key):
    """侧栏入口不随页面消失：六个入口进去后都还在、都可点。"""
    at = Chat(enter=False).at
    _click(at, key)
    btn = _by_key(at.sidebar.button, "nav_talk")
    assert btn.label == TALK
    assert btn.disabled is False


def test_talk_button_is_before_theme_picker():
    """侧栏第一项是它，配色排在后面。"""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert src.index("talk_button()") < src.index("theme_picker()")


def test_talk_button_goes_to_companion_and_back_returns():
    """点它进陪伴模式；返回键仍能退回刚才那一页（来路照常入栈）。"""
    at = Chat(enter=False).at
    _click(at, "home_about")
    _click(at, "nav_talk")
    assert at.session_state["mode"] == "companion"
    assert _by_key(at.sidebar.button, "nav_talk").disabled is True
    _click(at, "nav_back")
    assert at.session_state["mode"] == "about"


def test_talk_button_in_companion_is_disabled():
    at = Chat().at
    assert at.session_state["mode"] == "companion"
    assert _by_key(at.sidebar.button, "nav_talk").disabled is True


# P43：页面内部不再重复「回首页」——页首返回键与侧栏出口已经够了。
IN_PAGE_HOME_KEYS = ("relax_home", "quiz_home", "quiz_page_home",
                     "help_home", "rc_home")


@pytest.mark.parametrize("key, mode", [
    ("home_breath", "relax"),
    ("home_quiz", "quiz"),
    ("home_help_self", "help"),
    ("home_rolecard", "rolecard"),
])
def test_pages_do_not_repeat_home_button(key, mode):
    at = Chat(enter=False).at
    _click(at, key)
    assert at.session_state["mode"] == mode
    keys = {b.key for b in at.main.button}
    assert not (keys & set(IN_PAGE_HOME_KEYS)), keys


def test_sidebar_home_button_still_there_and_single():
    """侧栏「回首页」保留，且不同时出现两个（角色卡页曾重复）。"""
    at = Chat(enter=False).at
    _click(at, "home_rolecard")
    homes = [b for b in at.sidebar.button if b.label == "回首页"]
    assert [b.key for b in homes] == ["home_back"]
