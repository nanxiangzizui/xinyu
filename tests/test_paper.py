"""test_paper.py — P40 S5：一页纸只读已有记忆、去数字、不落盘。

三个断言方向：拼出来的是「用户的转述」而不是新数据；手机号 / 日期这类东西
不出现；看完这一页不会凭空产生任何文件。
"""
from __future__ import annotations

import episode_store
import memory
import paper
import quiz_store
from pipeline import Chat, memory_path, rows


def _by_key(elements, key):
    return [el for el in elements if el.key == key][0]


def _click(at, key):
    _by_key(at.button, key).click().run()
    assert not list(at.exception), f"{key} 异常：{list(at.exception)}"


def _text(at) -> str:
    kinds = ("subheader", "markdown", "caption", "info", "code", "error", "success")
    return " ".join(str(el.value) for kind in kinds for el in getattr(at, kind, []))


def _seed(sid: str) -> None:
    memory.write_memory(sid, {
        "preferred_tone": "gentle",
        "emotion_tags": ["学业", "人际"],
        "rolling_summary": "最近在准备考试。室友吵得睡不好。",
        "summary_at_turn": 5,
    })
    episode_store.append(sid, [{"cue": "考试", "topic": "学业",
                                "event": "小组作业拖到最后一晚",
                                "mood": "焦虑", "importance": 2}], 10)
    quiz_store.append(sid, {"quiz": "house", "title": "四院分院帽",
                            "key": "brave", "name": "勇气院",
                            "scores": {"勇气": 6}})


def test_build_uses_existing_memory_only():
    sid = "p40paper01"
    _seed(sid)
    data = paper.build(sid)
    assert any("学业" in row for row in data["state"])
    assert any("温柔" in row for row in data["state"])
    assert any("小组作业" in row for row in data["episodes"])
    assert data["quiz"] == ["四院分院帽 → 勇气院"]


def test_build_without_file_creates_nothing():
    sid = "p40paper_empty01"
    assert not memory_path(sid).exists()
    assert paper.build(sid) == {"state": [], "episodes": [], "quiz": []}
    assert not memory_path(sid).exists()


def test_text_strips_digits_and_keeps_extra():
    sid = "p40paper02"
    _seed(sid)
    text = paper.to_text(sid, "13912345678 我睡不着，明天要交作业")
    assert "139" not in text
    assert "我睡不着，明天要交作业" in text
    for title in ("我这阵子的状态", "最近提过的事", "做过的小测试",
                  "我想补的一句"):
        assert f"【{title}】" in text


def test_text_without_data_still_usable():
    sid = "p40paper_empty02"
    text = paper.to_text(sid)
    assert "给咨询师的一页" in text
    assert "（还没写）" in text
    assert not memory_path(sid).exists()


def test_paper_page_renders_from_about_button():
    chat = Chat(enter=False)
    sid = chat.sid
    _click(chat.at, "home_about")
    _click(chat.at, "about_paper")
    assert chat.state("mode") == "help"
    assert chat.state("help_page") == "paper"
    text = _text(chat.at)
    assert "带一页纸去咨询" in text
    assert "不是病历，也不是量表" in text
    assert "关掉就没了" in text
    assert not memory_path(sid).exists()
    assert not rows(sid)
