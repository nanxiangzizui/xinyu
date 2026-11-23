"""test_survey.py — P44 匿名问卷页：声明、10 题、落盘、管理页、零联动。

断言三类：真访问（AppTest 走 app.py）、真磁盘（JSONL 行数）、真副作用（无记忆/无 LLM）。
"""
from __future__ import annotations

import csv
import io

import agent
import survey_data as D
import survey_store as store
from pipeline import Chat, memory_path


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _click(at, key):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"


def _text(at) -> str:
    kinds = ("subheader", "markdown", "caption", "info", "code", "error",
             "success", "warning")
    return " ".join(str(el.value) for kind in kinds for el in getattr(at, kind, []))


def _open() -> Chat:
    chat = Chat(enter=False)
    _click(chat.at, "nav_survey")
    assert chat.state("mode") == "survey"
    return chat


def _agree(chat: Chat) -> None:
    _by_key(chat.at.checkbox, "survey_consent").check().run()
    assert not list(chat.at.exception)


def _submit(chat: Chat) -> None:
    buttons = [b for b in chat.at.button if "提交" in str(b.label)]
    assert buttons, [str(b.label) for b in chat.at.button]
    buttons[0].click().run()
    assert not list(chat.at.exception), f"提交异常：{list(chat.at.exception)}"


def _fill(chat: Chat, **values) -> None:
    for key, val in values.items():
        group = "multiselect" if isinstance(val, list) else "radio"
        _by_key(chat.at.get(group), key).set_value(val)


def _rows():
    return store.read_all()


def test_entry_is_sidebar_bottom_not_home():
    """P44 修订：入口从首页卡片挪到侧栏最下面（模型设置之后）。"""
    chat = Chat(enter=False)
    labels = [str(b.label) for b in chat.at.sidebar.button]
    assert labels[-1].startswith("匿名问卷"), labels
    assert "匿名问卷" not in _text(chat.at)          # 首页正文里不再出现
    _click(chat.at, "nav_survey")
    assert chat.state("mode") == "survey"


def test_notice_leads_with_purpose_line():
    """第一条隐私声明已删，那个位置改成一句目的说明。"""
    chat = _open()
    text = _text(chat.at)
    assert D.PURPOSE in text
    assert "只用于课程作业统计" not in text
    assert "不收集 IP" in text                       # 其余声明一条不少


def test_no_questions_before_consent():
    chat = _open()
    text = _text(chat.at)
    assert "你的年级" not in text
    assert "不会写入聊天记忆" in text          # 声明先于题目
    assert "不调用 AI" in text


def test_consent_shows_ten_widgets():
    chat = _open()
    _agree(chat)
    labels = " ".join(str(r.label) for r in chat.at.radio)
    labels += " ".join(str(m.label) for m in chat.at.multiselect)
    labels += " ".join(str(t.label) for t in chat.at.text_area)
    assert "你的年级" in labels
    radios = len([r for r in chat.at.radio if str(r.key).startswith("q")])
    multis = len([m for m in chat.at.multiselect if str(m.key).startswith("q")])
    areas = len([t for t in chat.at.text_area if str(t.key).startswith("q")])
    assert (radios, multis, areas) == (6, 3, 1)   # 6 单选 + 3 多选 + 第 10 题


def test_submit_writes_one_row():
    chat = _open()
    _agree(chat)
    _fill(chat, q1_0="大三", q2_0="1–2 次", q4_0=["怕被记录"])
    _submit(chat)
    rows = _rows()
    assert len(rows) == 1
    assert rows[0]["answers"] == {"q1": "大三", "q2": "1–2 次", "q4": ["怕被记录"]}
    assert len(rows[0]["rid"]) == 8 and rows[0]["day"]
    assert "收到了，谢谢" in _text(chat.at)


def test_empty_submit_writes_nothing():
    chat = _open()
    _agree(chat)
    _submit(chat)
    assert _rows() == []
    assert "还没选任何一项" in _text(chat.at)


def test_q5_rejects_three_picks():
    chat = _open()
    _agree(chat)
    _fill(chat, q1_0="大一", q5_0=[D.OPTIONS["q5"][0], D.OPTIONS["q5"][1], D.OPTIONS["q5"][2]])
    _submit(chat)
    assert _rows() == []
    assert "最多选两项" in _text(chat.at)


def test_survey_never_creates_memory():
    chat = _open()
    sid = chat.sid
    _agree(chat)
    _fill(chat, q1_0="大二")
    _submit(chat)
    assert _rows()                                  # 确实写了问卷
    assert not memory_path(sid).exists()            # 但没碰记忆


def test_survey_never_calls_llm(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("问卷页不该调模型")
    monkeypatch.setattr(agent, "call_llm", boom)
    chat = _open()
    _agree(chat)
    _fill(chat, q2_0="没有")
    _submit(chat)
    assert len(_rows()) == 1


def test_admin_hidden_without_password_config(monkeypatch):
    monkeypatch.delenv("SURVEY_ADMIN", raising=False)
    chat = _open()
    labels = [str(el.label) for el in chat.at.expander]
    assert not any("发放人" in lab for lab in labels)


def test_admin_wrong_password_shows_error(monkeypatch):
    monkeypatch.setenv("SURVEY_ADMIN", "s3cret-ok")
    store.append({"q1": "大三"})
    chat = _open()
    _by_key(chat.at.text_input, "survey_admin_pwd").set_value("nope").run()
    assert "密码不对" in _text(chat.at)


def test_admin_right_password_shows_counts_and_downloads(monkeypatch):
    monkeypatch.setenv("SURVEY_ADMIN", "s3cret-ok")
    store.append({"q1": "大三", "q2": "1–2 次"})
    store.append({"q1": "大一"})
    chat = _open()
    _by_key(chat.at.text_input, "survey_admin_pwd").set_value("s3cret-ok").run()
    text = _text(chat.at)
    assert "回收份数" in text and "2" in text
    assert len(chat.at.get("download_button")) == 2


def test_csv_has_twelve_columns():
    rows = [{"rid": "a1b2c3d4", "day": "2026-11-23",
             "answers": {"q1": "大三", "q3": ["自己扛着", "睡觉"], "q10": "多一个夜班"}}]
    table = list(csv.reader(io.StringIO(store.csv_text(rows))))
    assert len(table) == 2
    assert table[0] == ["rid", "day", *D.IDS]
    assert len(table[0]) == 12
    assert table[1][2] == "大三"
    assert table[1][4] == "自己扛着|睡觉"


def test_normalise_flattens_and_caps():
    cleaned = store.normalise({"q10": "第一行\n第二行" + "长" * 300,
                               "q5": list(D.OPTIONS["q5"]), "q1": "大三",
                               "q9": "不在选项里"})
    assert cleaned["q10"].startswith("第一行 第二行")
    assert len(cleaned["q10"]) == D.Q10_MAX
    assert len(cleaned["q5"]) == 2
    assert "q9" not in cleaned


def test_crosses_count_people_not_answers():
    rows = [
        {"answers": {"q2": "3–5 次", "q4": ["怕被记录"], "q5": [D.Q5_NEXT_STEP], "q9": "可能会"}},
        {"answers": {"q2": "没有", "q4": ["怕被记录"], "q5": [D.Q5_NEXT_STEP], "q9": "会"}},
        {"answers": {"q2": "更多", "q4": ["没有这种情况"]}},
    ]
    cross = store.crosses(rows)
    assert cross["had_and_quiet"] == 1     # 只有第 1 行同时满足两件事
    assert cross["step_and_would"] == 2    # 第 2 行虽然「没有」，但确实想走下一步且会去
