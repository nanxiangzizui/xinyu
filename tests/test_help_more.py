"""test_help_more.py — P45 四张日常页：毕业 / 拖延 / 社恐 / 丧亲。

每页断言：一句能照做的话、一条硬线、零副作用；另外检查新文案没有诊断词、
没有多出来的 8 位号码。全静态文案，不测模型。
"""
from __future__ import annotations

import re

import pytest

import help_more
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


CASES = {
    "future": ("毕业", "截止日期", "秋招", "12356"),
    "thesis": ("15 分钟", "查重", "延毕", "12356"),
    "shame": ("离开现场", "呼气 6 次", "社恐", "110"),
    "grief": ("亲人重病", "重大决定", "前两周", "12356"),
}


@pytest.mark.parametrize("page,needles", list(CASES.items()))
def test_more_page_keeps_its_promises(page, needles):
    chat = _open(page)
    text = _text(chat.at)
    for needle in needles:
        assert needle in text, (page, needle)
    assert list(chat.at.error), f"{page} 缺硬线（必须写清什么时候找真人）"


@pytest.mark.parametrize("page", list(help_more.RENDERERS))
def test_more_page_is_registered_and_titled(page):
    assert page in help_pages.TITLES
    assert help_pages.TITLES[page] in _text(_open(page).at)


@pytest.mark.parametrize("page", list(help_more.RENDERERS))
def test_more_pages_create_nothing(page):
    chat = _open(page)
    sid = chat.sid
    assert not memory_path(sid).exists(), page
    assert not rows(sid), page


def test_grief_page_does_not_push_big_decisions():
    """丧亲页要明确挡一下「马上退学 / 卖房 / 辞职」这类决定。"""
    text = _text(_open("grief").at)
    assert "前两周先不做重大决定" in text
    assert "医疗和财产的事" in text


def test_future_page_keeps_the_choice_small():
    """毕业 / 考研 / 找工作页不承诺结果，只把选择缩到两条。"""
    text = _text(_open("future").at)
    assert "缩到两条" in text
    assert "别同时准备所有路" in text


def test_thesis_page_offers_a_fifteen_minute_start():
    """拖延页先给一个 15 分钟的动作，而不是「你要自律」。"""
    text = _text(_open("thesis").at)
    assert "只写 15 分钟" in text
    assert "别等「有整块时间再写」" in text


def test_shame_page_offers_leaving_the_scene():
    """当众被说页先允许离开现场，不要求当场解释清楚。"""
    text = _text(_open("shame").at)
    assert "先离开那个场面" in text
    assert "别当场解释所有细节" in text


def _all_texts() -> str:
    groups = (
        help_more.FUTURE_DO, help_more.FUTURE_DONT, help_more.FUTURE_LINE,
        help_more.THESIS_DO, help_more.THESIS_DONT, help_more.THESIS_LINE,
        help_more.SHAME_DO, help_more.SHAME_DONT, help_more.SHAME_LINE,
        help_more.GRIEF_DO, help_more.GRIEF_DECIDE, help_more.GRIEF_DONT,
        help_more.GRIEF_LINE,
    )
    texts = [line for group in groups for line in group]
    for group in (
        help_more.FUTURE_SAY, help_more.THESIS_SAY,
        help_more.SHAME_SAY, help_more.GRIEF_SAY,
    ):
        texts += [item[1] for item in group]
    return " ".join(texts)


def test_more_copy_has_no_diagnosis_and_no_extra_numbers():
    text = _all_texts()
    for word in ("你得了", "抑郁症", "的倾向", "建议服药", "开点药", "确诊"):
        assert word not in text, word
    assert re.findall(r"\d{8}", text) == []
