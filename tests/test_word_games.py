"""test_word_games.py — P17e：本地文字游戏的数据、拼音与页面行为。"""
from __future__ import annotations

import re

from pipeline import Chat
import word_games


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _open(key: str):
    at = Chat(enter=False).at
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"
    return at


def test_data_sizes_and_shapes():
    assert len(word_games.BRAIN_TEASERS) == 30
    assert len(word_games.RIDDLES) == 30
    assert len(word_games.IDIOMS) == 120
    assert all(len(q) == 2 for q in word_games.BRAIN_TEASERS)
    assert all(len(q) == 3 for q in word_games.RIDDLES)


def test_idioms_are_four_chinese_chars_and_have_pinyin():
    pattern = re.compile(r"^[\u4e00-\u9fff]{4}$")
    pinyin = re.compile(r"^[a-z]+$")
    for text, first, last in word_games.IDIOMS:
        assert pattern.fullmatch(text), text
        assert pinyin.fullmatch(first), (text, first)
        assert pinyin.fullmatch(last), (text, last)
        assert "ü" not in first and "ü" not in last


def test_idiom_indexes_are_consistent():
    for text, first, last in word_games.IDIOMS:
        assert word_games.BY_TEXT[text] == (text, first, last)
        assert (text, first, last) in word_games.STARTS[first]


def test_clean_idiom_accepts_spaces_and_rejects_bad_input():
    assert word_games._clean_idiom(" 一心一意 ") == "一心一意"
    assert word_games._clean_idiom("一心一意。") == ""
    assert word_games._clean_idiom("一心一") == ""
    assert word_games._clean_idiom("一心一意意") == ""


def test_next_idiom_uses_last_sound_and_avoids_itself():
    current = word_games.BY_TEXT["一心一意"]
    nxt = word_games._next_idiom(current)
    assert nxt is not None
    assert nxt[0] != current[0]
    assert nxt[1] == current[2]


def test_next_idiom_returns_none_on_dead_end():
    assert word_games._next_idiom(("测试", "ce", "zzz")) is None


def test_brain_teaser_reveal_and_next():
    at = _open("home_brain")
    assert at.session_state["relax_page"] == "brain"
    _by_key(at.button, "brain_show").click().run()
    assert any("答案" in str(item.value) for item in at.success)
    _by_key(at.button, "brain_next").click().run()
    assert at.session_state["brain_idx"] == 1


def test_riddle_hint_and_answer():
    at = _open("home_riddle")
    _by_key(at.button, "riddle_hint").click().run()
    assert any("提示：" in str(item.value) for item in at.caption)
    _by_key(at.button, "riddle_show").click().run()
    assert any("答案" in str(item.value) for item in at.success)


def test_idiom_accepts_same_sound_and_advances():
    at = _open("home_idiom")
    current = word_games.BY_TEXT["一心一意"]
    at.session_state["idiom_current"] = current
    at.run()
    candidate = next(item for item in word_games.IDIOMS
                     if item[1] == current[2] and item[0] != current[0])
    # 表单控件只在 submit 时把值交回脚本；先 run 会把值冲成空。
    _by_key(at.text_input, "idiom_input").set_value(candidate[0])
    [b for b in at.button if b.label == "接上"][0].click().run()
    assert at.session_state["idiom_current"][0] == candidate[0]
    assert at.session_state["idiom_msg"] == "接上了。"


def test_idiom_rejects_wrong_length_without_writing_messages():
    at = _open("home_idiom")
    _by_key(at.text_input, "idiom_input").set_value("一二三")
    [b for b in at.button if b.label == "接上"][0].click().run()
    assert at.session_state["idiom_msg"] == "要四个汉字，不要标点或空格。"
    assert "messages" not in at.session_state or at.session_state["messages"] == []


def test_idiom_dead_end_suggests_restart():
    at = _open("home_idiom")
    at.session_state["idiom_current"] = ("测试", "ce", "zzz")
    at.run()
    _by_key(at.button, "idiom_help").click().run()
    assert at.session_state["idiom_msg"] == "这条路有点窄，换一个开头吧。"
