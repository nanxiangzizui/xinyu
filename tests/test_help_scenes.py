"""test_help_scenes.py — P40 S3：四张新页的承诺、硬线与零副作用。

每页都断言三样：一句能照做的话、一个号码 / 硬线、以及「看完不留下东西」。
不测模型——这四页全是静态文案。
"""
from __future__ import annotations

import pytest

import help_pages
import help_scenes
from pipeline import Chat, memory_path, rows


def _open(page: str) -> Chat:
    chat = Chat(enter=False)
    chat.at.session_state["mode"] = "help"
    chat.at.session_state["help_page"] = page
    chat.at.run()
    assert not list(chat.at.exception), f"{page} 异常：{list(chat.at.exception)}"
    return chat


def _text(at) -> str:
    kinds = ("subheader", "markdown", "caption", "info", "code", "error", "success")
    parts = [str(el.value) for kind in kinds for el in getattr(at, kind, [])]
    # 折叠面板里的正文仍在元素树里，但标题要单独取——AppTest 的 .value 不带它。
    parts += [str(el.label) for el in at.expander]
    return " ".join(parts)


CASES = {
    "aftermath": ("今晚", "72 小时", "等咨询的这两周", "12356"),
    "sleep": ("20 分钟", "别看钟", "两周", "睡眠门诊"),
    "online": ("截图", "不要对骂", "110", "以平台规则和学校规定为准"),
    "exam": ("48 小时", "补考", "12356", "对不起所有人"),
}


@pytest.mark.parametrize("page,needles", list(CASES.items()))
def test_scene_page_keeps_its_promises(page, needles):
    chat = _open(page)
    text = _text(chat.at)
    for needle in needles:
        assert needle in text, (page, needle)
    assert list(chat.at.error), f"{page} 缺硬线（必须写清什么时候找真人）"


@pytest.mark.parametrize("page", list(help_scenes.RENDERERS))
def test_scene_page_is_registered_and_titled(page):
    assert page in help_pages.TITLES
    assert help_pages.TITLES[page] in _text(_open(page).at)


@pytest.mark.parametrize("page", list(help_scenes.RENDERERS))
def test_scene_pages_create_nothing(page):
    chat = _open(page)
    sid = chat.sid
    assert not memory_path(sid).exists(), page
    assert not rows(sid), page


def test_aftermath_is_not_a_week_plan():
    """危机之后最怕堆任务：今晚只给三件，且不写「立刻去咨询」这种做不到的话。"""
    text = _text(_open("aftermath").at)
    assert "让一个人来陪你" in text
    assert "先交给别人收着" in text


def test_friend_page_covers_not_in_crisis_yet():
    """S4：朋友「还没到出事、只是最近不太对」也要有一句能用的。"""
    text = _text(_open("friend").at)
    assert "还没到出事" in text
    assert "我谁都不告诉" in text


def test_friend_page_covers_refusing_to_go():
    """P44：他不肯去时，先问怕什么，再给「我陪你去」和边界。"""
    text = _text(_open("friend").at)
    assert "他不肯去，我怎么劝" in text
    assert "我陪你去" in text
    assert "我不逼你" in text


def test_friend_page_covers_online_bystander():
    """P44：网上看到有人想不开，先私信、别围观、危险打 110 / 120。"""
    text = _text(_open("friend").at)
    assert "网上看到有人想不开" in text
    assert "别在评论区问细节" in text
    assert "110 / 120" in text


def test_online_page_covers_witness():
    """P44：网暴页要告诉旁观者「不转发、不保存、帮存证」。"""
    text = _text(_open("online").at)
    assert "如果你是旁观者" in text
    assert "不转发" in text
    assert "别人肉" in text


def test_exam_page_covers_failing_more_than_one():
    """P44：挂科之外，还要接住退学警告与「花钱消记录」。"""
    text = _text(_open("exam").at)
    assert "退学警告" in text
    assert "补考什么时候" in text
    assert "花钱消记录" in text
