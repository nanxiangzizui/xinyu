"""test_rolecard_wiki.py — P9i Wiki 正文直连（离线；fetch 注入）。"""
from __future__ import annotations

import urllib.parse

import rolecard_wiki


def _card(**overrides) -> dict:
    card = {"origin": "known", "work": "崩坏：星穹铁道", "name": "青砚",
            "identity": "旅人", "setting": "", "voice": "轻", "address": "你",
            "examples": [], "taboos": [], "lore": []}
    card.update(overrides)
    return card


def _body(text: str = "角色" * 200) -> str:
    return (f'<html><div class="mw-parser-output"><p>{text}</p></div>'
            '<div class="printfooter">页脚</div></html>')


def test_wiki_prefix_maps_known_works():
    """只有映射内的作品才直连 Wiki；未知作品返回空串。"""
    assert rolecard_wiki.wiki_prefix("崩坏：星穹铁道") == "https://wiki.biligame.com/sr/"
    assert rolecard_wiki.wiki_prefix("Honkai: Star Rail") == "https://wiki.biligame.com/sr/"
    assert rolecard_wiki.wiki_prefix("原神") == "https://wiki.biligame.com/ys/"
    assert rolecard_wiki.wiki_prefix("某虚构作品") == ""


def test_wiki_url_quotes_name_and_uses_focus():
    """角色名做 URL 编码；盲点优先用 focus 的专名。"""
    url = rolecard_wiki.wiki_url(_card())
    assert url == "https://wiki.biligame.com/sr/" + urllib.parse.quote("青砚")
    focus_url = rolecard_wiki.wiki_url(_card(), focus="白泽")
    assert focus_url.endswith(urllib.parse.quote("白泽"))


def test_wiki_urls_try_base_before_parenthesized_alias():
    """卡名带括号别名时，Biligame 角色页在基名；先试基名，再试全名。"""
    card = _card(name="白厄（卡厄斯兰那）")
    urls = rolecard_wiki.wiki_urls(card)
    assert urls[0].endswith(urllib.parse.quote("白厄"))
    assert urls[1].endswith(urllib.parse.quote("白厄（卡厄斯兰那）"))
    assert rolecard_wiki.wiki_url(card) == urls[0]


def test_rows_falls_back_to_full_name_when_base_missing():
    """基名 404 时继续试全名；两个都失败才交给搜索兜底。"""
    card = _card(name="白厄（卡厄斯兰那）")
    seen = []

    def _fetch(url):
        seen.append(url)
        if url.endswith(urllib.parse.quote("白厄")):
            return "", "http_404"
        return _body(), ""

    rows = rolecard_wiki.rows(card, fetch=_fetch)
    assert len(rows) == 1
    assert rows[0]["url"].endswith(urllib.parse.quote("白厄（卡厄斯兰那）"))
    assert len(seen) == 2


def test_fetch_text_extracts_body_and_strips_tags():
    """只取 mw-parser-output，去掉标签后截断；短正文视为没有。"""
    page = _body("角色" * 200)
    text, error = rolecard_wiki.fetch_text(
        "https://wiki.biligame.com/sr/青砚", fetch=lambda url: (page, ""))
    assert error == "" and "角色" in text and "<p>" not in text
    short, short_error = rolecard_wiki.fetch_text(
        "https://wiki.biligame.com/sr/青砚",
        fetch=lambda url: ('<div class="mw-parser-output">短</div>'
                           '<div class="printfooter">', ""))
    assert short == "" and short_error == "no_body"


def test_rows_only_for_known_mapped_cards():
    """原创卡/未知作品不直连；known + 映射作品返回一条 Wiki 正文行。"""
    page = _body()
    fetch = lambda url: (page, "")
    assert rolecard_wiki.rows(_card(origin="original"), fetch=fetch) == []
    assert rolecard_wiki.rows(_card(work="某虚构作品"), fetch=fetch) == []
    rows = rolecard_wiki.rows(_card(), fetch=fetch)
    assert len(rows) == 1
    assert rows[0]["url"].endswith(urllib.parse.quote("青砚"))
    assert rows[0]["snippet"]
