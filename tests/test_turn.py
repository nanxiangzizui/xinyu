"""test_turn.py — P7c 连发：多段输入合并成一轮，只回一次。

为什么单开一个文件：`tests/pipeline.py` 的 `say()` 断言"一问一答加两条消息"，
连发正好是"多条问、一条答"，两套口径放一起会互相绊。
"""
from __future__ import annotations

from chat_ui import merge_tail
from guardian import CRISIS_REPLY
from pipeline import app_source, reply_rows
from pipeline import Chat


def test_merge_tail_joins_consecutive_users():
    """连着发的几条拼成一段，且 history 里只留一条 user。"""
    msgs = [{"role": "user", "content": "要是我能遇到像她一样的人就好了"},
            {"role": "user", "content": "但是她不可能遇到"}]
    history, merged = merge_tail(msgs)
    assert merged == "要是我能遇到像她一样的人就好了\n但是她不可能遇到"
    assert [m["role"] for m in history] == ["user"]
    assert history[0]["content"] == merged


def test_merge_tail_leaves_a_normal_turn_alone():
    """正常一问一答不动：assistant 是分界线，翻过它就停。"""
    msgs = [{"role": "user", "content": "在吗"},
            {"role": "assistant", "content": "在"},
            {"role": "user", "content": "今天有点累"}]
    history, merged = merge_tail(msgs)
    assert merged == "今天有点累"
    assert history == msgs


def test_burst_gets_one_reply_and_one_turn():
    """连发：三个气泡、一条回复、轮次只涨一次。"""
    chat = Chat("p7-burst")
    at = chat.at
    at.session_state["messages"] = [{"role": "user", "content": "要是我能遇到像她一样的人就好了"}]
    at.chat_input[0].set_value("但是她不可能遇到").run()
    assert not list(at.exception), list(at.exception)
    roles_seen = [m["role"] for m in at.session_state["messages"]]
    assert roles_seen == ["user", "user", "assistant"]
    assert at.session_state["turn"] == 1
    assert len(reply_rows(chat.sid)) == 1


def test_burst_judges_the_whole_utterance():
    """判危必须扫整段：危机在前一条，只传最后一条就会被漏掉。"""
    chat = Chat("p7-burst-crisis")
    at = chat.at
    at.session_state["messages"] = [{"role": "user", "content": "我不想活了"}]
    at.chat_input[0].set_value("你在吗").run()
    assert not list(at.exception), list(at.exception)
    reply = at.session_state["messages"][-1]["content"]
    assert reply == CRISIS_REPLY
    assert at.session_state["last_level"] == "L3"
    assert at.session_state["turn"] == 1
    assert len(at.info) >= 3                     # L3 三张资源卡仍当轮出


def test_reply_is_stored_before_rendered():
    """先落库再渲染：渲染那一帧被打断时，回复还在历史里。"""
    src = app_source()
    store = src.index('"role": "assistant", "content": result["reply"]')
    render = src.index('chat_ui.render_reply(parts')
    assert store < render


def test_sources_render_only_code_filtered_links(monkeypatch):
    """P20：A 模式当轮也要画来源；但只画带 url 的条目（模型自己写的 URL 不认）。"""
    import chat_ui

    drawn: list[str] = []
    monkeypatch.setattr(chat_ui.st, "markdown", lambda text: drawn.append(str(text)))
    chat_ui.render_sources([{"title": "资料页", "url": "https://example.com/a"},
                            {"title": "没有链接"}])
    chat_ui.render_sources([])
    assert len(drawn) == 1
    assert "https://example.com/a" in drawn[0] and "资料页" in drawn[0]
