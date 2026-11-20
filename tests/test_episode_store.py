"""P10：情景记忆的存储、召回、淘汰、清空（A 模式）。"""
import json

import episode_store
import memory


def _item(cue="搬家", event="对方提过下个月要搬家", importance=2):
    return {"cue": cue, "topic": "住处", "event": event,
            "mood": "焦虑", "importance": importance}


def test_missing_store_is_empty():
    store = episode_store.read_store("s1")
    assert store == {"seq": 0, "last_len": 0, "last_try_len": 0, "episodes": []}


def test_append_and_read_roundtrip():
    assert episode_store.append("s1", [_item()], 10) is True
    store = episode_store.read_store("s1")
    assert (store["seq"], store["last_len"]) == (1, 10)
    ep = store["episodes"][0]
    assert (ep["cue"], ep["seq"], ep["recalls"]) == ("搬家", 1, 0)


def test_append_advances_even_with_no_items():
    assert episode_store.append("s1", [], 10) is True
    store = episode_store.read_store("s1")
    assert (store["seq"], store["last_len"], store["episodes"]) == (1, 10, [])


def test_recall_requires_cue():
    episode_store.append("s1", [_item()], 10)
    hit = episode_store.read_with_recall("s1", "我下周要搬家")
    assert len(hit["_episodes"]) == 1
    assert "搬家" in hit["_episode_text"]
    assert hit["_episodes"][0]["recalls"] == 1
    miss = episode_store.read_with_recall("s1", "今天天气不错")
    assert miss["_episodes"] == [] and miss["_episode_text"] == ""


def test_recall_cooldown():
    episode_store.append("s1", [_item()], 10)
    assert len(episode_store.read_with_recall("s1", "要搬家")["_episodes"]) == 1
    assert episode_store.read_with_recall("s1", "要搬家")["_episodes"] == []
    episode_store.append("s1", [], 12)
    assert len(episode_store.read_with_recall("s1", "要搬家")["_episodes"]) == 1


def test_cap_keeps_high_importance():
    first, last = "词" + chr(0x4E00), "词" + chr(0x4E00 + 28)
    episodes = [_item("词" + chr(0x4E00 + i), f"事件记录{i}", 1) for i in range(29)]
    episodes.append(_item("重要", "很重要的事", 3))
    episode_store.write_store("s1", {"seq": 99, "last_len": 10,
                                     "last_try_len": 0, "episodes": episodes})
    store = episode_store.read_store("s1")
    cues = {ep["cue"] for ep in store["episodes"]}
    assert len(store["episodes"]) == 24
    assert "重要" in cues and first not in cues and last in cues


def test_clear_removes_three_files():
    episode_store.append("s1", [_item()], 10)
    path = memory.DATA_DIR / "episodes" / "s1.json"
    path.with_suffix(".json.tmp").write_text("{}", encoding="utf-8")
    assert episode_store.clear("s1") is True
    for cand in (path, path.with_suffix(".json.bak"), path.with_suffix(".json.tmp")):
        assert not cand.exists()


def test_corrupt_main_recovers_bak():
    episode_store.append("s1", [_item()], 10)
    episode_store.append("s1", [_item("考试", "对方下周有一场考试")], 12)
    path = memory.DATA_DIR / "episodes" / "s1.json"
    path.write_text("{bad", encoding="utf-8")
    store = episode_store.read_store("s1")
    assert store["episodes"][0]["cue"] == "搬家"
    json.loads(path.read_text(encoding="utf-8"))   # 主文件已从 .bak 修好


def test_block_has_header_and_cap():
    block = episode_store.render_block([_item(event="事" * 50),
                                        _item("考试", "考" * 50)])
    # P24 ②：首句必须让模型"先说出记得的那个细节"，这是实测 0/5 → 5/5 的那一句。
    assert block.startswith("（对方以前提过的事")
    assert "说出你记得的那个细节" in block and "不要装作第一次听说" in block
    assert len(block) <= episode_store.BLOCK_MAX


def test_clean_episode_rejects_sensitive():
    assert episode_store.clean_episode({"cue": "吃药", "event": "对方在吃药"}) is None
    assert episode_store.clean_episode({"cue": "搬家", "event": "对方确诊抑郁症"}) is None


def test_clean_episode_requires_clean_cue():
    assert episode_store.clean_episode({"cue": "今天", "event": "对方今天很累"}) is None
    assert episode_store.clean_episode({"cue": "搬 家", "event": "对方要搬家"}) is None
    assert episode_store.clean_episode({"cue": "5点", "event": "对方五点下班"}) is None
