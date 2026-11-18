"""test_relax.py — P17b/c：六个放松页的路由、会话状态与安全边界。"""
from __future__ import annotations

import urllib.parse

import pytest

from pipeline import Chat
import relax_data


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _open(key: str):
    at = Chat(enter=False).at
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"
    return at


def _click(at, key: str):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"


def test_breath_has_no_chat_input_and_returns_home():
    at = _open("home_breath")
    assert at.session_state["mode"] == "relax"
    assert at.session_state["relax_page"] == "breath"
    assert len(at.chat_input) == 0
    _click(at, "relax_home")
    assert at.session_state["mode"] == "home"


def test_ground_steps_advance_and_reset():
    at = _open("home_ground")
    assert at.session_state["relax_ground_step"] == 0
    _click(at, "ground_next")
    assert at.session_state["relax_ground_step"] == 1
    _click(at, "ground_reset")
    assert at.session_state["relax_ground_step"] == 0


def test_break_switches_action_without_scoring():
    at = _open("home_break")
    before = at.session_state["relax_micro_idx"]
    assert 0 <= before < len(relax_data.MICRO_ACTIONS)
    _click(at, "break_next")
    assert at.session_state["relax_micro_idx"] != before


def test_journal_is_session_only_and_tear_clears_it():
    at = _open("home_journal")
    _by_key(at.text_area, "relax_worry").set_value("明天的事").run()
    _by_key(at.text_area, "relax_control").set_value("先喝口水").run()
    assert at.session_state["relax_worry"] == "明天的事"
    assert at.session_state["relax_control"] == "先喝口水"
    assert "messages" not in at.session_state or at.session_state["messages"] == []
    assert "last_trace" not in at.session_state
    _click(at, "relax_tear")
    # 控件本身会以空值重新登记 key；内容被清空即为“撕掉”，不要求 key 消失。
    assert at.session_state["relax_worry"] == ""
    assert at.session_state["relax_control"] == ""


def test_sound_page_is_quiet_by_default_and_has_credits():
    at = _open("home_sound")
    assert at.session_state["relax_page"] == "sound"
    text = " ".join(str(item.value) for item in at.caption)
    assert "默认是静的" in text or any("默认是静的" in str(x.value) for x in at.markdown)
    # 来源说明必须在页面上，不靠模型生成。
    assert any("Wikimedia Commons" in str(x.value) for x in at.markdown)


def test_links_page_uses_only_whitelisted_https():
    links = relax_data.safe_links()
    assert len(links) == 5
    labels = {item["label"] for item in links}
    assert {"古诗文网", "PixelThoughts"} <= labels
    assert not {"explore.org 自然直播", "Google Arts & Culture"} & labels
    assert all(item["url"].startswith("https://") for item in links)
    assert all(urllib.parse.urlsplit(item["url"]).hostname in relax_data.LINK_HOSTS
               for item in links)
    at = _open("home_links")
    assert at.session_state["relax_page"] == "links"
    text = " ".join(str(item.value) for item in at.caption)
    assert "将离开本站" in text


def test_unknown_relax_page_falls_back_to_breath():
    at = Chat(enter=False).at
    at.session_state["mode"] = "relax"
    at.session_state["relax_page"] = "not-a-page"
    at.run()
    assert not list(at.exception)
    assert at.session_state["relax_page"] == "not-a-page"
    # 页面内容回落到呼吸页，但不改用户存的 page（避免刷新时反复跳）。
    assert len(at.chat_input) == 0


@pytest.mark.parametrize("key,page", [
    ("home_breath", "breath"),
    ("home_ground", "ground"),
    ("home_break", "break"),
    ("home_journal", "journal"),
    ("home_sound", "sound"),
    ("home_links", "links"),
])
def test_each_relax_page_has_no_chat_and_no_trace(key, page):
    at = _open(key)
    assert at.session_state["relax_page"] == page
    assert len(at.chat_input) == 0
    assert "messages" not in at.session_state or at.session_state["messages"] == []
    assert "last_trace" not in at.session_state
