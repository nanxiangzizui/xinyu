"""test_help_index.py — P44/P45：索引页 26 条、搜索、分诊第 5 项、不产生记忆。

索引页只做路由：断言结构（每条目标都存在）+ 真实点击 + 零副作用，
不断言模型（这页根本不调模型）。
"""
from __future__ import annotations

import help_index
import help_pages
import home
import relax_ui
from pipeline import Chat, memory_path


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _click(at, key):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"


def _text(at) -> str:
    kinds = ("subheader", "markdown", "caption", "info", "code", "error", "success")
    return " ".join(str(el.value) for kind in kinds for el in getattr(at, kind, []))


def _items():
    return [item for _, rows in help_index.GROUPS for item in rows]


def test_index_has_26_unique_entries():
    items = _items()
    keys = [item[4] for item in items]
    assert len(items) == 26
    assert len(set(keys)) == 26
    assert all(key.startswith("idx_") for key in keys)


def test_every_index_target_exists():
    """索引里写出的每个目标都必须真有页面：点进去不能是空路由。"""
    for label, _desc, mode, page, _key in _items():
        if mode == "help":
            assert page in help_pages.TITLES, (label, page)
        elif mode == "relax":
            assert page in relax_ui.PAGES, (label, page)
        else:
            assert mode in {"companion", "about", "quiz", "rolecard"}, label
            assert page == "", (label, page)


def test_home_triage_has_five_entries_and_opens_index():
    chat = Chat(enter=False)
    assert chat.state("mode") == "home"
    assert len(home.TRIAGE) == 5
    assert "我遇到一件具体的事" in [label for label, *_ in home.TRIAGE]
    _click(chat.at, "home_index")
    assert chat.state("mode") == "help"
    assert chat.state("help_page") == "index"
    text = _text(chat.at)
    assert "我遇到的是" in text
    assert "26 个入口" in text
    assert "32 个时刻" in text
    assert len([b for b in chat.at.button if b.key.startswith("idx_")]) == 26


def test_index_does_not_create_memory_file():
    """看目录不该产生数据：这页不调 agent、不写记忆。"""
    chat = Chat(enter=False)
    sid = chat.sid
    _click(chat.at, "home_index")
    assert not memory_path(sid).exists()


def test_entry_routes_to_scene_page():
    chat = Chat(enter=False)
    _click(chat.at, "home_index")
    _click(chat.at, "idx_sleep")
    assert chat.state("mode") == "help"
    assert chat.state("help_page") == "sleep"
    assert "躺下 20 分钟" in _text(chat.at)


def test_entry_routes_to_relax_page():
    chat = Chat(enter=False)
    _click(chat.at, "home_index")
    _click(chat.at, "idx_journal")
    assert chat.state("mode") == "relax"
    assert chat.state("relax_page") == "journal"


def test_entry_routes_to_new_daily_page():
    chat = Chat(enter=False)
    _click(chat.at, "home_index")
    _click(chat.at, "idx_roommate")
    assert chat.state("mode") == "help"
    assert chat.state("help_page") == "roommate"
    assert "宿舍是睡觉的地方" in _text(chat.at)


def test_entry_routes_to_future_page():
    chat = Chat(enter=False)
    _click(chat.at, "home_index")
    _click(chat.at, "idx_future")
    assert chat.state("mode") == "help"
    assert chat.state("help_page") == "future"
    assert "毕业 / 考研 / 找工作" in _text(chat.at)


def test_index_search_matches_keyword_not_just_label():
    """搜「校园贷」要能找到「生活费不够」那张卡：关键词不只放在标题里。"""
    chat = Chat(enter=False)
    _click(chat.at, "home_index")
    chat.at.text_input(key="idx_search").set_value("校园贷").run()
    assert not list(chat.at.exception)
    text = _text(chat.at)
    assert "生活费不够 / 兼职被坑" in text
    assert "躺下睡不着" not in text


def test_index_search_filters_and_routes():
    chat = Chat(enter=False)
    _click(chat.at, "home_index")
    chat.at.text_input(key="idx_search").set_value("室友").run()
    text = _text(chat.at)
    assert "室友 / 宿舍住不下去" in text
    assert "躺下睡不着" not in text
    assert len([b for b in chat.at.button if b.key.startswith("idx_")]) == 1
    _click(chat.at, "idx_roommate")
    assert chat.state("help_page") == "roommate"


def test_index_search_no_result_offers_chat():
    chat = Chat(enter=False)
    _click(chat.at, "home_index")
    chat.at.text_input(key="idx_search").set_value("外星人").run()
    text = _text(chat.at)
    assert "没找到" in text
    assert "可能这一页还没做" in text
    _click(chat.at, "idx_no_match_chat")
    assert chat.state("mode") == "companion"
