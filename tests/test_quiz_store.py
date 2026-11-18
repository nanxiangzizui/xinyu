"""test_quiz_store.py — P13 特殊记忆区：落盘、召回门、上限、清空。

这一区与 memory.json 无关：只存游戏名、结果名、维度分，不存答案与原话。
"""
from __future__ import annotations

import json

import memory
import quiz_store

SID = "quizstore00001"


def _result(name: str = "勇气院") -> dict:
    return {"quiz": "house", "title": "四院分院帽", "key": "brave",
            "name": name, "scores": {"勇气": 6, "思辨": 2, "仁厚": 0}}


def test_append_and_read_roundtrip():
    assert quiz_store.append(SID, _result()) is True
    rows = quiz_store.read_store(SID)["attempts"]
    assert len(rows) == 1
    assert rows[0]["name"] == "勇气院"
    assert rows[0]["scores"]["勇气"] == 6
    assert quiz_store.count(SID) == 1


def test_store_keeps_no_answers_or_urls():
    """[SAFE] 只存结果，不存答了什么、也不存网址。"""
    quiz_store.append(SID, _result())
    raw = json.loads((memory.DATA_DIR / "quiz" / f"{SID}.json").read_text("utf-8"))
    dump = json.dumps(raw, ensure_ascii=False)
    assert "answers" not in dump
    assert "http" not in dump
    assert "今天" not in dump


def test_recall_needs_a_cue():
    """AI 不会主动想起：没有测试话头，就一个字都不给。"""
    quiz_store.append(SID, _result())
    assert quiz_store.recall(SID, "今天有点累") == ""
    assert quiz_store.recall(SID, "") == ""
    block = quiz_store.recall(SID, "我上次那个测试还挺准")
    assert "[趣味测试记录]" in block
    assert "勇气院" in block


def test_recall_by_result_name():
    quiz_store.append(SID, _result())
    block = quiz_store.recall(SID, "我又测了一次，还是勇气院吗")
    assert "四院分院帽" in block


def test_recall_is_scoped_to_one_session():
    quiz_store.append(SID, _result())
    assert quiz_store.recall("othersid00001", "上次那个测试") == ""


def test_block_says_do_not_volunteer():
    quiz_store.append(SID, _result())
    block = quiz_store.recall(SID, "测试")
    assert "不要主动提" in block
    assert len(block) <= quiz_store.BLOCK_MAX


def test_block_explains_latest_dims_once():
    """m00425：块里只解释最近一次的维度，别把历史几次的说明全堆上来。"""
    quiz_store.append(SID, _result("勇气院"))
    block = quiz_store.recall(SID, "测试")
    assert block.count("维度：") == 1
    assert "勇气=" in block
    assert "仁厚=" not in block          # 0 分的项不解释


def test_analyze_cue_asks_for_substance():
    """用户要分析时补一条怎么聊；只是提一句测试时不给。"""
    quiz_store.append(SID, _result())
    block = quiz_store.recall(SID, "帮我分析分析这个测试")
    assert "先说最高的一项" in block
    assert "不要整条只有一句反问" in block
    plain = quiz_store.recall(SID, "我上次那个测试")
    assert "先说最高的一项" not in plain
    assert len(block) <= quiz_store.BLOCK_MAX


def test_report_screenshot_sentence_hits():
    """m00425 里那句原话必须能召回；日常句“结果我还是没去”不能。"""
    quiz_store.append(SID, _result("野心院"))
    block = quiz_store.recall(SID, "帮我分析分析这个结果")
    assert "野心院" in block
    assert "先说最高的一项" in block
    assert quiz_store.recall(SID, "结果我还是没去") == ""


def test_old_attempts_are_trimmed():
    for i in range(quiz_store.MAX_ATTEMPTS + 5):
        quiz_store.append(SID, _result(name=f"第{i}次"))
    rows = quiz_store.read_store(SID)["attempts"]
    assert len(rows) == quiz_store.MAX_ATTEMPTS
    assert rows[-1]["name"] == f"第{quiz_store.MAX_ATTEMPTS + 4}次"


def test_bad_records_are_dropped():
    assert quiz_store.append(SID, {"quiz": "", "title": "", "name": "", "key": ""}) is False
    assert quiz_store.count(SID) == 0


def test_clear_removes_the_file():
    quiz_store.append(SID, _result())
    assert quiz_store.clear(SID) is True
    assert quiz_store.count(SID) == 0
    assert quiz_store.clear(SID) is False
