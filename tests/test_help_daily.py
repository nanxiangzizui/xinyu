"""test_help_daily.py — P44 四张日常页 + 统一 60 秒出口。

每页断言：一句能照做的话、一条硬线、零副作用；另外检查 15 个内容页都有
60 秒出口，以及「去和心屿说这件事」真的能进聊天。全静态文案，不测模型。
"""
from __future__ import annotations

import re

import pytest

import help_daily
import help_pages
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
    parts += [str(el.label) for el in at.expander]
    return " ".join(parts)


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


CASES = {
    "love": ("失恋", "今晚只做三件", "别在半夜", "12356"),
    "roommate": ("室友", "12 点后", "换宿", "110"),
    "family": ("和家里", "要不要告诉家里", "先判断今晚安不安全", "110"),
    "money": ("生活费", "校园贷", "这周还差多少", "110"),
}


@pytest.mark.parametrize("page,needles", list(CASES.items()))
def test_daily_page_keeps_its_promises(page, needles):
    chat = _open(page)
    text = _text(chat.at)
    for needle in needles:
        assert needle in text, (page, needle)
    assert list(chat.at.error), f"{page} 缺硬线（必须写清什么时候找真人）"


@pytest.mark.parametrize("page", list(help_daily.RENDERERS))
def test_daily_page_is_registered_and_titled(page):
    assert page in help_pages.TITLES
    assert help_pages.TITLES[page] in _text(_open(page).at)


@pytest.mark.parametrize("page", list(help_daily.RENDERERS))
def test_daily_pages_create_nothing(page):
    chat = _open(page)
    sid = chat.sid
    assert not memory_path(sid).exists(), page
    assert not rows(sid), page


CONTENT_PAGES = (
    "self", "friend", "before", "after", "teacher", "leave", "accompany",
    "aftermath", "sleep", "online", "exam", "love", "roommate", "family", "money",
    "future", "thesis", "shame", "grief",
)


@pytest.mark.parametrize("page", CONTENT_PAGES)
def test_every_content_page_has_sixty_second_exit(page):
    chat = _open(page)
    text = _text(chat.at)
    assert "60 秒内可以做的" in text, page
    assert "这一页只做一件" in text, page
    assert any(b.label == "去和心屿说这件事" for b in chat.at.button), page


def test_sixty_second_button_opens_chat():
    chat = _open("love")
    _by_key(chat.at.button, "help_chat_love").click().run()
    assert not list(chat.at.exception)
    assert chat.state("mode") == "companion"


def _all_texts() -> str:
    groups = (
        help_daily.LOVE_TONIGHT, help_daily.LOVE_DONT, help_daily.LOVE_LINE,
        help_daily.ROOMMATE_DO, help_daily.ROOMMATE_DONT,
        help_daily.ROOMMATE_LINE, help_daily.FAMILY_DO, help_daily.FAMILY_TELL,
        help_daily.FAMILY_DONT, help_daily.FAMILY_LINE, help_daily.MONEY_DO,
        help_daily.MONEY_DONT, help_daily.MONEY_LINE,
    )
    texts = [line for group in groups for line in group]
    for group in (help_daily.LOVE_SAY, help_daily.ROOMMATE_SAY,
                  help_daily.FAMILY_SAY, help_daily.MONEY_SAY):
        texts += [item[1] for item in group]
    for one, small, up in help_daily.SIXTY.values():
        texts += [one, small, up]
    return " ".join(texts)


def test_daily_copy_has_no_diagnosis_and_no_extra_numbers():
    text = _all_texts()
    for word in ("你得了", "抑郁症", "的倾向", "建议服药", "开点药", "确诊"):
        assert word not in text, word
    assert re.findall(r"\d{8}", text) == []
