"""P10：每 5 轮一次的记忆抽取与来源闸门（A/B 共用）。"""
import json

import episode_store
import memory_extract
import rolecard_memory


def _history(n=8):
    return [{"role": "user" if i % 2 == 0 else "assistant", "content": f"消息{i}"}
            for i in range(n)]


def _fake(monkeypatch, payload):
    monkeypatch.setenv("MOCK_LLM", "0")
    calls = []

    def call(*args, **kwargs):
        calls.append((args, kwargs))
        return payload

    monkeypatch.setattr(memory_extract.agent, "call_llm", call)
    return calls


def test_mock_skips(monkeypatch):
    calls = _fake(monkeypatch, {"ok": True, "text": "{}"})
    monkeypatch.setenv("MOCK_LLM", "1")
    memory_extract.maybe_run(False, None, "s1", {"_last_len": 0},
                             _history(), "我下周要搬家", "嗯")
    assert calls == []


def test_due_after_five_turns(monkeypatch):
    payload = {"ok": True, "text": json.dumps({"episodes": [
        {"cue": "搬家", "topic": "住处", "event": "对方提过下个月要搬家",
         "mood": "焦虑", "importance": 2}]}, ensure_ascii=False)}
    _fake(monkeypatch, payload)
    memory_extract.maybe_run(False, None, "s1", {"_last_len": 0},
                             _history(), "我下周要搬家", "嗯")
    store = episode_store.read_store("s1")
    assert (store["seq"], store["last_len"]) == (1, 10)
    assert store["episodes"][0]["cue"] == "搬家"


def test_not_due_at_four_turns(monkeypatch):
    calls = _fake(monkeypatch, {"ok": True, "text": "{}"})
    memory_extract.maybe_run(False, None, "s1", {"_last_len": 0},
                             _history(6), "我下周要搬家", "嗯")
    assert calls == []


def test_parse_a_rejects_quote():
    blob = "我下个月要搬家，最近有点焦虑"
    data = {"episodes": [{"cue": "搬家", "event": blob, "importance": 2}]}
    assert memory_extract.parse_a(json.dumps(data, ensure_ascii=False), blob) == []


def test_parse_a_rejects_real_name():
    blob = "我叫张三，我下周要搬家"
    data = {"episodes": [{"cue": "搬家", "event": "张三下个月要搬家",
                          "importance": 2}]}
    assert memory_extract.parse_a(json.dumps(data, ensure_ascii=False), blob) == []


def test_parse_a_rejects_sensitive():
    blob = "我下周要搬家"
    data = {"episodes": [{"cue": "搬家", "event": "对方确诊抑郁症，最近很累",
                          "importance": 2}]}
    assert memory_extract.parse_a(json.dumps(data, ensure_ascii=False), blob) == []


def test_parse_a_keeps_virtual_place():
    blob = "我在贝洛伯格下城区，想去看雪"
    data = {"episodes": [{"cue": "看雪", "topic": "约定",
                          "event": "对方住在贝洛伯格的雪原附近，想去看雪",
                          "importance": 2}]}
    out = memory_extract.parse_a(json.dumps(data, ensure_ascii=False), blob)
    assert len(out) == 1 and "贝洛伯格" in out[0]["event"]


def test_parse_b_actors_source_gate():
    card = {"name": "昔涟", "work": "星穹铁道", "lore": ["贝洛伯格"]}
    user_blob = "还记得我们约好一起看雪吗"
    assistant_blob = "当然记得，昔涟答应过你。"
    data = {"summary": "你们约好一起看雪",
            "state": {"scene": "贝洛伯格", "mood": "平静", "relation": "同行者"},
            "threads": [{"text": "一起看雪", "status": "open"}],
            "episodes": [{"cue": "看雪", "topic": "约定",
                          "event": "你答应带对方去城外看雪",
                          "actors": ["昔涟", "张三"], "importance": 3}]}
    clean = memory_extract.parse_b(json.dumps(data, ensure_ascii=False), card,
                                   user_blob, assistant_blob)
    assert clean["episodes"][0]["actors"] == ["昔涟"]
    assert clean["state"]["scene"] == "贝洛伯格"


def test_parse_b_rejects_user_real_name():
    card = {"name": "昔涟", "work": "星穹铁道"}
    user_blob = "我叫张三，我们一起去看雪"
    data = {"summary": "张三和昔涟一起看雪",
            "threads": [{"text": "张三说要一起看雪", "status": "open"}],
            "episodes": [{"cue": "看雪", "event": "张三答应一起看雪",
                          "importance": 3}]}
    clean = memory_extract.parse_b(json.dumps(data, ensure_ascii=False), card,
                                   user_blob, "")
    assert clean["summary"] == ""
    assert clean["threads_open"] == []
    assert clean["episodes"] == []


def test_fail_open_marks_try(monkeypatch):
    calls = _fake(monkeypatch, {"ok": False, "error": "timeout"})
    memory_extract.maybe_run(False, None, "s1", {"_last_len": 0},
                             _history(), "我下周要搬家", "嗯")
    assert episode_store.read_store("s1")["last_try_len"] == 10
    memory_extract.maybe_run(False, None, "s1",
                             {"_last_len": 0, "_last_try_len": 10},
                             _history(), "还在搬家", "嗯")
    assert len(calls) == 1


def test_bad_json_marks_try(monkeypatch):
    _fake(monkeypatch, {"ok": True, "text": "不是 JSON"})
    memory_extract.maybe_run(False, None, "s1", {"_last_len": 0},
                             _history(), "我下周要搬家", "嗯")
    store = episode_store.read_store("s1")
    assert (store["last_try_len"], store["episodes"]) == (10, [])


def test_b_extraction_writes_card_memory(monkeypatch):
    card = {"name": "昔涟", "work": "星穹铁道", "lore": ["贝洛伯格"]}
    payload = {"ok": True, "text": json.dumps({
        "summary": "你们约好一起看雪",
        "state": {"scene": "贝洛伯格", "mood": "平静", "relation": "同行者"},
        "threads": [{"text": "答应去城外看雪", "status": "open"}],
        "episodes": [{"cue": "看雪", "topic": "约定",
                      "event": "你答应带对方去城外看雪",
                      "actors": ["昔涟"], "importance": 3}]}, ensure_ascii=False)}
    _fake(monkeypatch, payload)
    memory_extract.maybe_run(True, card, "rc-1", {"_last_len": 0},
                             _history(), "还记得看雪吗",
                             "当然记得，昔涟答应过你。")
    assert rolecard_memory.stats(card)[0] == 1
    assert "一起看雪" in rolecard_memory.read(card)["_block"]
