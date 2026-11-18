"""test_quiz_ui.py — P13 侧栏入口与答题流程（AppTest，走真 app.py）。

断言落在 session_state / 磁盘 / 输出文本上，不猜自然语言措辞。
"""
from __future__ import annotations

import quiz_data
import quiz_store
from pipeline import Chat, memory_path


def _by_key(elements, key):
    """按 widget key 取控件（侧栏与主区控件混在同一个列表里）。"""
    return [el for el in elements if el.key == key][0]


def _open(at) -> None:
    _by_key(at.button, "quiz_entry").click().run()
    assert not list(at.exception), f"打开测试异常：{list(at.exception)}"
    assert at.session_state["quiz_state"] == "ack"


def _play(chat: Chat, qid: str = "house") -> dict:
    """从头答完一个游戏，返回结果字典。"""
    at = chat.at
    _open(at)
    _by_key(at.checkbox, "quiz_ack").check().run()
    _by_key(at.button, "quiz_start").click().run()
    assert not list(at.exception), f"开始测试异常：{list(at.exception)}"
    assert at.session_state["quiz_state"] == "run"
    quiz_obj = quiz_data.QUIZZES[qid]
    for idx, item in enumerate(quiz_obj["questions"]):
        _by_key(at.radio, f"quiz_q{idx}").set_value(item["opts"][0][0]).run()
        _by_key(at.button, f"quiz_next{idx}").click().run()
        assert not list(at.exception), f"第 {idx + 1} 题异常：{list(at.exception)}"
    return at.session_state["quiz_result"]


def test_sidebar_entry_does_not_block_chat():
    """入口在侧栏；没点开时主区什么都没有，输入框仍在。"""
    chat = Chat()
    at = chat.at
    assert _by_key(at.button, "quiz_entry").label == "来做个小测试"
    assert len(at.chat_input) == 1
    assert at.session_state["messages"] == []
    assert "quiz_state" not in at.session_state


def test_declaration_appears_and_chat_still_works():
    chat = Chat()
    at = chat.at
    _open(at)
    assert _by_key(at.checkbox, "quiz_ack").value is False
    assert len(at.chat_input) == 1
    assert at.session_state["messages"] == []


def test_cannot_start_before_ack():
    """没勾“我知道了”时开始按钮是禁用的；浏览器点不动，状态也不该变。"""
    chat = Chat()
    at = chat.at
    _open(at)
    assert _by_key(at.button, "quiz_start").disabled is True
    assert at.session_state["quiz_state"] == "ack"
    assert "quiz_answers" not in at.session_state


def test_close_resets_and_asks_for_ack_next_time():
    chat = Chat()
    at = chat.at
    _open(at)
    _by_key(at.button, "quiz_close").click().run()
    assert "quiz_state" not in at.session_state
    assert _by_key(at.button, "quiz_entry") is not None


def test_full_run_reports_and_writes_memory():
    chat = Chat()
    at = chat.at
    result = _play(chat)
    assert at.session_state["quiz_state"] == "done"
    message = chat.messages[-1]
    assert message["quiz"] is True
    assert message["content"].startswith(f"《四院分院帽》的结果：{result['name']}")
    assert message["content"].endswith(quiz_data.CTA)
    assert quiz_store.count(chat.sid) == 1
    assert quiz_store.read_store(chat.sid)["attempts"][0]["name"] == result["name"]


def test_report_is_not_counted_as_a_turn():
    """报告不是一轮对话：轮次不涨，摘要节流也不会被它提前触发。"""
    chat = Chat()
    at = chat.at
    _play(chat)
    assert at.session_state["turn"] == 0
    chat.say("我回来了")
    assert at.session_state["turn"] == 1


def test_result_never_enters_memory_json():
    """[SAFE] 结果只住 quiz 这一区；memory.json 里连结果名都不该出现。"""
    chat = Chat()
    result = _play(chat)
    chat.say("刚才那个游戏挺有意思")
    text = memory_path(chat.sid).read_text(encoding="utf-8")
    assert result["name"] not in text
    assert "四院分院帽" not in text


def test_home_standalone_result_can_start_a_chat():
    """P17d：独立页做完后点“聊一聊”，把结果带回 companion，不重弹 5 题。"""
    chat = Chat(enter=False)
    at = chat.at
    _by_key(at.button, "home_quiz").click().run()
    assert at.session_state["mode"] == "quiz"
    _by_key(at.checkbox, "quiz_ack").check().run()
    _by_key(at.button, "quiz_start").click().run()
    quiz_obj = quiz_data.QUIZZES["house"]
    for idx, item in enumerate(quiz_obj["questions"]):
        _by_key(at.radio, f"quiz_q{idx}").set_value(item["opts"][0][0]).run()
        _by_key(at.button, f"quiz_next{idx}").click().run()
    assert at.session_state["quiz_state"] == "done"
    _by_key(at.button, "quiz_chat").click().run()
    assert not list(at.exception), f"聊一聊异常：{list(at.exception)}"
    assert at.session_state["mode"] == "companion"
    assert "pending_turn" not in at.session_state
    assert at.session_state["messages"][-2]["role"] == "user"
    assert at.session_state["messages"][-1]["role"] == "assistant"
    assert len(at.chat_input) == 1


def test_clear_wipes_quiz_memory():
    """清空对话 = 真删：小本子文件与页内状态一起归零。"""
    chat = Chat()
    at = chat.at
    _play(chat)
    path = memory_path(chat.sid)
    assert (path.parent / "quiz" / f"{chat.sid}.json").exists()
    _by_key(at.checkbox, f"panel_confirm_{chat.sid}").check().run()
    _by_key(at.button, f"panel_clear_{chat.sid}").click().run()
    assert not list(at.exception), f"清空异常：{list(at.exception)}"
    assert quiz_store.count(chat.sid) == 0
    assert "quiz_state" not in at.session_state
