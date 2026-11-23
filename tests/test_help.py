"""test_help.py — P26：危机下一步 / 两张求助页 / 能力边界与我的数据。

三块都是"静态内容 + 路由"：断言用文案片段、session_state、磁盘与日志，
不断言模型输出（这几页根本不调模型）。
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest

import about
import agent
import crisis_plan
import episode_store
import help_pages
import memory
import quiz_store
import resources
from guardian import CRISIS_REPLY
from pipeline import Chat, memory_path, rows


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _click(at, key):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"


def _text(at) -> str:
    chunks = []
    for kind in ("subheader", "markdown", "info", "caption", "code", "success", "error", "warning"):
        chunks += [str(el.value) for el in getattr(at, kind, [])]
    return " ".join(chunks)


def _at(y, m, d, h, mi=0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=crisis_plan.CN_TZ)


# ---------- crisis_plan：按时段选一个号 ----------

@pytest.mark.parametrize("now,slot", [
    (_at(2026, 11, 20, 23, 30), "night"),      # 周五深夜
    (_at(2026, 11, 21, 3), "night"),           # 周六凌晨
    (_at(2026, 11, 20, 7, 30), "elsewhere"),   # 清晨：校中心还没开
    (_at(2026, 11, 20, 8), "workday"),
    (_at(2026, 11, 20, 16, 59), "workday"),
    (_at(2026, 11, 20, 17), "elsewhere"),      # 下班点以后不再假设有人
    (_at(2026, 11, 20, 19), "elsewhere"),
    (_at(2026, 11, 21, 10), "elsewhere"),      # 周六白天
    (_at(2026, 11, 22, 10), "elsewhere"),      # 周日白天
])
def test_first_step_slots(now, slot):
    assert crisis_plan.first_step(now)["slot"] == slot


def test_workday_prefers_campus_phone():
    step = crisis_plan.first_step(_at(2026, 11, 20, 10))
    assert step["title"] == "校心理中心"
    assert resources.CAMPUS_PHONE in step["detail"]
    assert "12356" in step["backup"][0]
    assert step["backup"][-1] == crisis_plan.EMERGENCY


def test_night_prefers_hotline():
    step = crisis_plan.first_step(_at(2026, 11, 20, 23, 30))
    assert step["title"] == crisis_plan.HOTLINE[0]
    assert "12356" in step["detail"]
    assert "下班" in step["why"]


def test_weekend_points_to_daytime_campus():
    step = crisis_plan.first_step(_at(2026, 11, 21, 10))
    assert "白天" in step["why"]
    assert resources.CAMPUS_PHONE in step["backup"][0]


def test_clock_matches_agent():
    assert crisis_plan.CN_TZ == agent.CN_TZ


# ---------- 文案红线 ----------

def _all_texts() -> list[str]:
    texts = [text for _, text in crisis_plan.MESSAGES]
    texts += [crisis_plan.ONE_SMALL_THING, crisis_plan.EMERGENCY]
    for group in (help_pages.FRIEND_SAY, help_pages.FRIEND_DONT,
                  help_pages.DANGER_SIGNS, help_pages.FRIEND_ACTION,
                  help_pages.SELF_CARE, help_pages.BEFORE, help_pages.AFTER,
                  help_pages.TEACHER_OPEN, help_pages.TEACHER_ASK,
                  help_pages.LEAVE_PREP, help_pages.LEAVE_ASK,
                  help_pages.LEAVE_SAY, help_pages.ACCOMPANY_BEFORE,
                  help_pages.ACCOMPANY_SAY, help_pages.ACCOMPANY_CAN,
                  help_pages.ACCOMPANY_CANT, help_pages.ACCOMPANY_SELF,
                  about.CAN_DO, about.CANNOT_DO, about.SEE_A_PERSON):
        texts += [item if isinstance(item, str) else item[1] for item in group]
    texts += [help_pages.BEFORE_WHERE, help_pages.TEACHER_NOTE,
              help_pages.LEAVE_NOTE, help_pages.ACCOMPANY_NOTE]
    return texts


def test_texts_never_diagnose():
    banned = ("你得了", "抑郁症", "的倾向", "建议服药", "开点药", "确诊")
    hits = [t for t in _all_texts() if any(word in t for word in banned)]
    assert hits == []


def test_eight_digit_numbers_are_campus_phone():
    steps = [crisis_plan.first_step(n) for n in
             (_at(2026, 11, 20, 10), _at(2026, 11, 20, 23), _at(2026, 11, 21, 10))]
    texts = _all_texts() + [s["detail"] for s in steps]
    texts += [line for s in steps for line in s["backup"]]
    assert {n for t in texts for n in re.findall(r"\d{8}", t)} == {resources.CAMPUS_PHONE}


# ---------- 两个求助页（AppTest） ----------

def test_home_safety_button_opens_self_page():
    at = Chat(enter=False).at
    _click(at, "home_help_self")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "self"
    assert len(at.chat_input) == 0
    text = _text(at)
    assert "先打这一个" in text
    assert "12356" in text and resources.CAMPUS_PHONE in text
    assert "把门打开" in text
    assert "help_home" not in {b.key for b in at.button}   # 侧栏已有「回首页」


def test_home_safety_button_opens_friend_page():
    at = Chat(enter=False).at
    _click(at, "home_help_friend")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "friend"
    assert len(at.chat_input) == 0
    text = _text(at)
    assert "我朋友出事了" in text
    assert "别答应" in text
    assert "120" in text and "辅导员" in text
    assert "我不会到处说" in text


def test_home_opens_before_counsel_page():
    """T5：咨询前准备页，从首页「关于心屿」进入。"""
    at = Chat(enter=False).at
    _click(at, "home_before")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "before"
    assert len(at.chat_input) == 0
    text = _text(at)
    assert "去咨询前" in text
    assert "不知道怎么开口" in text
    assert "可以拒绝回答" in text
    assert resources.CAMPUS_PHONE in text


def test_home_opens_after_counsel_page():
    """T5：咨询后一周页，结尾把危险情况指回「我现在很难受」。"""
    at = Chat(enter=False).at
    _click(at, "home_after")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "after"
    text = _text(at)
    assert "咨询后这一周" in text
    assert "有点空" in text
    assert "什么时候再约" in text
    assert "如果这次不合适" in text
    assert "我现在很难受" in text


@pytest.mark.parametrize("key", ["home_before", "home_after"])
def test_counsel_pages_do_not_log(key):
    chat = Chat(enter=False)
    before = len(rows(chat.sid))
    _click(chat.at, key)
    assert len(rows(chat.sid)) == before


def test_help_page_uses_page_top_back_when_home_hub_off(monkeypatch):
    """首页开关关掉时，求助页不再自带「回首页」，用页首返回键回陪伴模式。"""
    monkeypatch.setenv("HOME_HUB", "0")
    at = Chat().at
    at.session_state["mode"] = "help"
    at.session_state["help_page"] = "self"
    at.run()
    assert "help_home" not in {b.key for b in at.main.button}
    _click(at, "nav_back")
    assert at.session_state["mode"] == "companion"


def test_help_pages_never_call_pipeline_or_log():
    chat = Chat(enter=False)
    before = len(rows(chat.sid))
    _click(chat.at, "home_help_self")
    assert len(rows(chat.sid)) == before


def test_l3_chat_shows_next_step_block():
    chat = Chat()
    assert chat.say("我不想活了") == CRISIS_REPLY
    at = chat.at
    assert "下一步：先打" in " ".join(str(el.value) for el in at.success)
    assert any("我现在不太对" in str(el.value) for el in at.code)
    _click(at, "help_open_chat")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "self"
    assert len(at.chat_input) == 0


def test_rolecard_l3_offers_same_next_step():
    """B 的结束页与 A 用同一块：一个号 + 一句能发出去的话。"""
    chat = Chat()
    at = chat.at
    _click(at, "rc_to_rolecard")
    _by_key(at.checkbox, "rc_consent_box").check().run()
    _click(at, "rc_load_example")
    _click(at, "rc_start")
    at.chat_input[0].set_value("我不想活了").run()
    assert not list(at.exception), list(at.exception)
    assert at.session_state["rc_ended"] is True
    assert "下一步：先打" in " ".join(str(el.value) for el in at.success)
    _click(at, "help_open_rc")
    assert at.session_state["mode"] == "help"


# ---------- 跟学校打交道（P30） ----------

def test_home_opens_teacher_page():
    """跟辅导员说：三档说多少 + 四件问清楚的事 + 保密边界。"""
    at = Chat(enter=False).at
    _click(at, "home_teacher")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "teacher"
    assert len(at.chat_input) == 0
    text = _text(at)
    assert "要跟辅导员" in text
    assert "不用一次说完" in text
    assert "哪些内容会被记录" in text
    assert "我现在很难受" in text


def test_home_opens_leave_page():
    """请假/缓考/休学：只给问题清单，不写死政策、不替人决定。"""
    at = Chat(enter=False).at
    _click(at, "home_leave")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "leave"
    text = _text(at)
    assert "请假 / 缓考 / 休学" in text
    assert "找谁办" in text and "截止到什么时候" in text
    assert "以学校当年文件为准" in text
    assert "不替你判断该不该办" in text
    assert "校心理中心" in text


def test_home_opens_accompany_page():
    """陪同页：能做什么、不能做什么、以及对方危险时的硬线。"""
    at = Chat(enter=False).at
    _click(at, "home_accompany")
    assert at.session_state["mode"] == "help"
    assert at.session_state["help_page"] == "accompany"
    text = _text(at)
    assert "陪别人去心理中心" in text
    assert "不替对方做决定" in text
    assert "110 / 120" in text
    assert "12356" in text


@pytest.mark.parametrize("key", ["home_teacher", "home_leave", "home_accompany"])
def test_school_pages_do_not_log(key):
    """三张页都是静态内容：点开不写日志、不调管线。"""
    chat = Chat(enter=False)
    before = len(rows(chat.sid))
    _click(chat.at, key)
    assert len(rows(chat.sid)) == before


def test_school_pages_do_not_touch_memory():
    """看流程页不该产生记忆文件（和 about 的 counts 一样，先看再读）。"""
    chat = Chat(enter=False)
    _click(chat.at, "home_teacher")
    assert not memory_path(chat.sid).exists()


# ---------- 关于：能力边界与我的数据 ----------

def test_about_page_shows_boundaries_and_data():
    at = Chat(enter=False).at
    _click(at, "home_about")
    assert at.session_state["mode"] == "about"
    text = _text(at)
    for phrase in ("心屿是什么，不是什么", "它能做的", "它不做的",
                   "请直接找真人", "我存了什么", "刷新就没了"):
        assert phrase in text
    sid = dict(at.query_params)["u"]
    picker = _by_key(at.multiselect, f"about_picks_{sid}")
    assert list(picker.options) == list(about.OPTIONS.values())
    assert _by_key(at.button, f"about_delete_{sid}").disabled is True


def test_about_page_does_not_create_memory_file():
    """看数据不该产生数据：counts 先看文件在不在，再决定读不读。"""
    at = Chat(enter=False).at
    sid = dict(at.query_params)["u"]
    _click(at, "home_about")
    assert not memory_path(sid).exists()


def test_counts_defaults_without_file():
    sid = "p26about01"
    assert about.counts(sid) == {"summary_len": 0, "summary_at_turn": 0,
                                 "episodes": 0, "quiz": 0, "rolecard_chats": 0}
    assert not memory_path(sid).exists()


def test_delete_only_clears_selected():
    sid = "p26about02"
    memory.write_memory(sid, {"rolling_summary": "最近在准备考试", "summary_at_turn": 5})
    episode_store.append(sid, [{"cue": "考试", "topic": "学业",
                                "event": "对方提过下周有考试", "mood": "紧张",
                                "importance": 2}], 10)
    quiz_store.append(sid, {"quiz": "house", "title": "四院分院帽", "key": "brave",
                            "name": "勇气院", "scores": {"勇气": 6}})
    assert about.counts(sid) == {"summary_len": 7, "summary_at_turn": 5,
                                 "episodes": 1, "quiz": 1, "rolecard_chats": 0}

    assert about.delete(sid, ["memory"]) == ["memory"]
    assert not memory_path(sid).exists()
    assert about.counts(sid)["episodes"] == 1 and about.counts(sid)["quiz"] == 1


def test_about_page_delete_flow():
    """勾选 + 确认 + 删除：文件真删，页面上有反馈。"""
    at = Chat(enter=False).at
    sid = dict(at.query_params)["u"]
    memory.write_memory(sid, {"rolling_summary": "一句话"})
    assert memory_path(sid).exists()
    _click(at, "home_about")
    at.multiselect(f"about_picks_{sid}").select("memory").run()
    at.checkbox(f"about_confirm_{sid}").check().run()
    _click(at, f"about_delete_{sid}")
    assert not memory_path(sid).exists()
    assert "已删除" in " ".join(str(el.value) for el in at.success)
