"""test_rolecard_app.py — P9c：B 模式在真 app.py 里的隔离与出口（AppTest）。

断言只用 session_state / 日志 / 磁盘，不断言自然语言正文。
"""
from __future__ import annotations

from guardian import CRISIS_REPLY
from pipeline import Chat, memory_path
from rolecard_form import conflict_text, last_card_path


def _by_key(elements, key):
    """按 widget key 取控件（页面上 A/B 控件互斥，序号不稳定）。"""
    return [el for el in elements if el.key == key][0]


def _enter_rolecard(at) -> None:
    """从 A 点侧栏按钮进入 B，等待 gate 渲染。"""
    _by_key(at.button, "rc_to_rolecard").click().run()
    assert not list(at.exception), f"进入角色卡异常：{list(at.exception)}"
    assert at.session_state["mode"] == "rolecard"


def _consent(at) -> None:
    """勾选免责声明，进入建卡表单（勾选框与同意标记是两个键）。"""
    _by_key(at.checkbox, "rc_consent_box").check().run()
    assert not list(at.exception), f"勾选免责异常：{list(at.exception)}"
    assert at.session_state["rc_consent"] is True


def _start_example(at) -> None:
    """载入示例卡并开始（回调先改控件状态，再点开始跑校验）。"""
    _by_key(at.button, "rc_load_example").click().run()
    _by_key(at.button, "rc_start").click().run()
    assert not list(at.exception), f"开始角色卡异常：{list(at.exception)}"


def test_default_mode_is_companion():
    """首屏仍是 A：有聊天输入、没有 rc 状态。"""
    chat = Chat()
    at = chat.at
    assert at.session_state["mode"] == "companion"
    assert len(at.chat_input) == 1
    assert at.session_state["messages"] == []
    assert "rc_consent" not in at.session_state


def test_rolecard_entry_hidden_when_flag_off(monkeypatch):
    """D9-8：ROLECARD=0 时侧栏不出现 B 入口，页面行为与 P9 前一致。"""
    monkeypatch.setenv("ROLECARD", "0")
    chat = Chat()
    at = chat.at
    assert at.session_state["mode"] == "companion"
    assert [b for b in at.button if b.key == "rc_to_rolecard"] == []
    assert len(at.chat_input) == 1


def test_gate_blocks_form_and_chat():
    """免责未勾选：既没有建卡表单，也没有聊天输入。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    assert _by_key(at.checkbox, "rc_consent_box") is not None
    assert at.session_state["rc_consent"] is False
    assert at.session_state["rc_card"] is None
    assert len(at.chat_input) == 0
    assert [i for i in at.text_input if i.key == "rc_name"] == []


def test_consent_shows_form_but_not_chat():
    """勾选后出现字段、认知、动作开关与开始按钮；此时还不能聊天。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    _consent(at)
    for key in ("rc_name", "rc_identity", "rc_voice", "rc_address", "rc_user_role"):
        assert _by_key(at.text_input, key) is not None, key
    assert _by_key(at.text_area, "rc_setting") is not None
    assert _by_key(at.text_area, "rc_lore_text") is not None
    assert _by_key(at.radio, "rc_stage") is not None
    assert _by_key(at.checkbox, "rc_auto_gap") is not None
    assert _by_key(at.button, "rc_start") is not None
    assert len(at.chat_input) == 0


def test_form_errors_are_visible():
    """空表单点开始：报“角色名不能为空”，不建卡、不进聊天。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    _consent(at)
    _by_key(at.button, "rc_start").click().run()
    assert not list(at.exception), list(at.exception)
    assert at.session_state["rc_card"] is None
    assert any("角色名" in err.value for err in at.error)
    assert len(at.chat_input) == 0


def test_example_card_starts_chat():
    """载入示例卡并开始：卡进 session_state，聊天输入出现。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    _consent(at)
    _start_example(at)
    card = at.session_state["rc_card"]
    assert card["name"] == "阿岚"
    assert card["user_role"] == "用户"
    assert card["stage"] == "none"
    assert card["lore"]
    assert at.session_state["rc_sid"].startswith("rc-")
    assert at.session_state["rc_messages"] == []
    assert len(at.chat_input) == 1


def test_rolecard_chat_is_isolated_from_a():
    """B 的一轮只写 rc_messages；A 的 messages 原样，磁盘不落 rc-*.json。"""
    chat = Chat()
    chat.say("今天天气不错")
    at = chat.at
    a_before = len(at.session_state["messages"])
    _enter_rolecard(at)
    _consent(at)
    _start_example(at)
    rc_sid = at.session_state["rc_sid"]

    at.chat_input[0].set_value("今天有点累").run()
    assert not list(at.exception), list(at.exception)
    assert [m["role"] for m in at.session_state["rc_messages"]] == ["user", "assistant"]
    assert at.session_state["rc_state"]["turn"] == 1
    assert len(at.session_state["messages"]) == a_before
    assert at.session_state["mode"] == "rolecard"
    assert not memory_path(rc_sid).exists()


def test_switch_phrase_does_not_leave_mode():
    """聊天里说“进入角色卡模式”只出提示：不写消息、不调管线、不切模式。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    _consent(at)
    _start_example(at)
    before = list(at.session_state["rc_messages"])

    at.chat_input[0].set_value("进入角色卡模式").run()
    assert not list(at.exception), list(at.exception)
    assert at.session_state["rc_messages"] == before
    assert at.session_state["mode"] == "rolecard"
    assert any("侧栏" in item.value for item in at.info)


def test_l3_ends_whole_rolecard_session():
    """D9-6：L3 后关闭输入，回复仍是危机模板，资源卡在场，磁盘无记忆。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    _consent(at)
    _start_example(at)
    rc_sid = at.session_state["rc_sid"]

    at.chat_input[0].set_value("我不想活了").run()
    assert not list(at.exception), list(at.exception)
    assert at.session_state["rc_ended"] is True
    assert at.session_state["rc_messages"][-1]["content"] == CRISIS_REPLY
    assert len(at.chat_input) == 0
    assert len(at.info) >= 3
    assert not memory_path(rc_sid).exists()


def test_rolecard_has_no_memory_panel_or_memory_file():
    """B 的侧栏不出记忆面板、不写记忆文件；trace 仍在。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    _consent(at)
    _start_example(at)
    rc_sid = at.session_state["rc_sid"]
    at.chat_input[0].set_value("今天有点累").run()

    assert not any("我记住了什么" in exp.label for exp in at.expander)
    assert [b.key for b in at.button if b.key and b.key.startswith("panel_")] == []
    assert any("本轮编排" in exp.label for exp in at.expander)
    assert not memory_path(rc_sid).exists()


def test_inherit_hidden_until_a_card_was_used():
    """没建过卡时不出现「继承」：空按钮只会让人多点一下。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    _consent(at)
    assert [b for b in at.button if b.key == "rc_inherit"] == []


def test_change_card_returns_to_empty_form():
    """换一张卡：回建卡页、表单清空、对话清掉，卡本身不再占着位置。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    _consent(at)
    _start_example(at)

    _by_key(at.button, "rc_change_card").click().run()
    assert not list(at.exception), list(at.exception)
    assert at.session_state["rc_card"] is None
    assert at.session_state["rc_messages"] == []
    assert _by_key(at.text_input, "rc_name").value == ""
    assert _by_key(at.text_area, "rc_lore_text").value == ""
    assert len(at.chat_input) == 0


def test_inherit_refills_the_card_that_was_just_used():
    """用了示例卡 → 换一张卡 → 点继承：字段与认知原样回来，可改一处再开始。"""
    chat = Chat()
    at = chat.at
    _enter_rolecard(at)
    _consent(at)
    _start_example(at)
    assert last_card_path().exists()

    _by_key(at.button, "rc_change_card").click().run()
    _by_key(at.button, "rc_inherit").click().run()
    assert not list(at.exception), list(at.exception)
    assert _by_key(at.text_input, "rc_name").value == "阿岚"
    assert _by_key(at.text_input, "rc_user_role").value == "用户"
    assert _by_key(at.text_area, "rc_lore_text").value != ""
    assert len(at.chat_input) == 0

    _by_key(at.button, "rc_start").click().run()
    assert at.session_state["rc_card"]["name"] == "阿岚"
    assert len(at.chat_input) == 1


def test_inherit_survives_a_page_refresh():
    """刷新会清 session_state；继承读的是文件，所以新会话仍能回填上一张卡。"""
    first = Chat()
    at = first.at
    _enter_rolecard(at)
    _consent(at)
    _start_example(at)

    fresh = Chat()                     # 新 AppTest = 新 session_state，模拟 F5
    at = fresh.at
    _enter_rolecard(at)
    _consent(at)
    assert _by_key(at.button, "rc_inherit") is not None
    _by_key(at.button, "rc_inherit").click().run()
    assert not list(at.exception), list(at.exception)
    assert _by_key(at.text_input, "rc_name").value == "阿岚"


def test_conflict_text_explains_why_a_fact_was_not_written():
    """保留原值要分额度满/格式错/已有内容；用户才知道下一步做什么。"""
    base = {"kind": "keep", "field": "经历", "current": "旧值", "suggested": "新值"}
    assert "角色认知已满 8 条或 960 字的额度" in conflict_text({**base, "reason": "lore_full"})
    assert "字段：事实" in conflict_text({**base, "reason": "invalid_lore"})
    assert "禁忌已满 3 条" in conflict_text({**base, "reason": "taboo_full"})
    assert "已有内容，未覆盖" in conflict_text({**base, "reason": "filled"})
    assert "未写入" in conflict_text({**base, "reason": "invalid"})
