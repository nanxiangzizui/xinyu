"""test_rolecard_chat_store.py — P39 对话记录的存储边界（纯文件，不跑 AppTest）。"""
from __future__ import annotations

import json
import time

import memory
import rolecard
import rolecard_chat_store as store


def _card() -> dict:
    return rolecard.normalize(rolecard.EXAMPLE_CARD)


def _messages(n: int = 2) -> list[dict]:
    out = []
    for i in range(n):
        out.append({"role": "user", "content": f"第{i}句"})
        out.append({"role": "assistant", "content": f"回应{i}",
                    "parts": [f"回应{i}"], "sources": ["https://example.com/a"]})
    return out


def _state(**over) -> dict:
    base = {"turn": 1, "cooldown": 0, "ever_crisis": False, "levels": ["L1"],
            "risk_signals": ["无"], "last_level": "L1", "last_role": "listener",
            "last_reason": "default", "degraded": False, "last_trace": [["x"]]}
    base.update(over)
    return base


def test_save_load_roundtrip_and_title():
    sid, conv = "p39store01", store.new_id()
    assert store.save(sid, conv, _card(), _messages(), _state(), ended=True)
    rec = store.load(sid, conv)
    assert rec is not None
    assert rec["id"] == conv and rec["ended"] is True
    assert rec["card"]["name"] == "阿岚"
    assert rec["title"].startswith("阿岚 · ")
    assert len(rec["messages"]) == 4
    assert rec["messages"][1]["sources"] == ["https://example.com/a"]
    assert rec["state"]["turn"] == 1
    assert rec["state"]["last_trace"] == []          # 恢复时补空，文件里不存
    raw = json.loads((memory.DATA_DIR.joinpath("rolecards", "chats", sid)
                      / f"{conv}.json").read_text(encoding="utf-8"))
    assert "last_trace" not in raw["state"]
    assert store.count(sid) == 1
    assert [row["id"] for row in store.list_chats(sid)] == [conv]


def test_bad_ids_empty_chat_and_bad_card_are_refused():
    sid, conv = "p39store02", store.new_id()
    assert store.save("../escape", conv, _card(), _messages(), _state()) is False
    assert store.save(sid, "../../x", _card(), _messages(), _state()) is False
    assert store.save(sid, conv, _card(), [], _state()) is False
    assert store.save(sid, conv, {"name": "空卡"}, _messages(), _state()) is False
    assert store.count(sid) == 0


def test_corrupt_file_is_skipped_not_crashing():
    sid, conv = "p39store03", store.new_id()
    folder = memory.DATA_DIR.joinpath("rolecards", "chats", sid)
    folder.mkdir(parents=True)
    (folder / f"{conv}.json").write_text("{not json", encoding="utf-8")
    assert store.load(sid, conv) is None
    assert store.list_chats(sid) == []
    assert store.count(sid) == 1          # 计数只看文件在不在，不读内容


def test_l3_history_keeps_ever_crisis_floor():
    sid, conv = "p39store04", store.new_id()
    assert store.save(sid, conv, _card(), _messages(), _state(levels=["L3"],
                                                              ever_crisis=False))
    rec = store.load(sid, conv)
    assert rec["state"]["ever_crisis"] is True
    assert rec["state"]["levels"] == ["L3"]


def test_delete_and_clear_are_real_deletes():
    sid, first, second = "p39store05", store.new_id(), store.new_id()
    assert store.save(sid, first, _card(), _messages(), _state())
    assert store.save(sid, second, _card(), _messages(), _state())
    assert store.delete(sid, first) is True
    assert store.delete(sid, first) is False
    assert store.count(sid) == 1
    assert store.clear(sid) == 1
    assert store.count(sid) == 0
    assert not memory.DATA_DIR.joinpath("rolecards", "chats", sid).exists()


def test_prune_keeps_newest_thirty():
    sid = "p39store06"
    ids = []
    for _ in range(store.CHAT_MAX + 1):
        conv = store.new_id()
        ids.append(conv)
        assert store.save(sid, conv, _card(), _messages(), _state())
        time.sleep(0.002)
    rows = store.list_chats(sid)
    assert len(rows) == store.CHAT_MAX
    assert ids[0] not in [row["id"] for row in rows]
    assert ids[-1] in [row["id"] for row in rows]


def test_message_cap_keeps_tail_and_marks_truncated():
    sid, conv = "p39store07", store.new_id()
    msgs = [{"role": "user" if i % 2 == 0 else "assistant",
             "content": f"m{i}"} for i in range(store.MESSAGES_MAX + 5)]
    assert store.save(sid, conv, _card(), msgs, _state())
    rec = store.load(sid, conv)
    assert len(rec["messages"]) == store.MESSAGES_MAX
    assert rec["messages"][-1]["content"] == f"m{store.MESSAGES_MAX + 4}"
    assert rec["truncated"] is True


def test_save_is_atomic_and_leaves_no_tmp():
    sid, conv = "p39store08", store.new_id()
    assert store.save(sid, conv, _card(), _messages(), _state())
    folder = memory.DATA_DIR.joinpath("rolecards", "chats", sid)
    assert sorted(p.name for p in folder.iterdir()) == [f"{conv}.json"]
    data = json.loads((folder / f"{conv}.json").read_text(encoding="utf-8"))
    assert data["version"] == store.RECORD_VERSION


def test_save_failure_returns_false(monkeypatch):
    sid, conv = "p39store09", store.new_id()

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(store.episode_store, "atomic_write", boom)
    assert store.save(sid, conv, _card(), _messages(), _state()) is False
    assert store.count(sid) == 0
