"""P10：B 角色卡记忆按卡存、来源门、清空与 60 条上限。"""
import episode_store
import memory
import rolecard_memory

CARD = {"name": "昔涟", "work": "星穹铁道", "lore": ["贝洛伯格"]}


def _clean():
    return {
        "summary": "你们一起看过雪",
        "state": {"scene": "雪原", "mood": "平静", "relation": "同行者"},
        "threads_open": ["答应去城外看雪"], "threads_done": [],
        "episodes": [{"cue": "看雪", "topic": "约定",
                      "event": "你答应带对方去城外看雪",
                      "actors": ["昔涟"], "importance": 3}],
    }


def test_card_key_stable_and_work_scoped():
    a = rolecard_memory.card_key(CARD)
    b = rolecard_memory.card_key({**CARD, "setting": "换个设定"})
    c = rolecard_memory.card_key({**CARD, "work": "原神"})
    assert a == b and a != c


def test_append_and_read_block():
    assert rolecard_memory.append_extraction(CARD, _clean(), 10) is True
    block = rolecard_memory.read(CARD, "还记得看雪吗")["_block"]
    assert "摘要：" in block and "当前：" in block and "还没说完：" in block
    assert "- 你答应带对方去城外看雪" in block
    assert len(block) <= rolecard_memory.BLOCK_MAX


def test_recall_only_when_cue_hits():
    rolecard_memory.append_extraction(CARD, _clean(), 10)
    no_hit = rolecard_memory.read(CARD, "今天有点累")["_block"]
    assert "你答应带对方去城外看雪" not in no_hit


def test_refresh_same_card_keeps_memory():
    rolecard_memory.append_extraction(CARD, _clean(), 10)
    assert rolecard_memory.stats(CARD)[0] == 1
    assert rolecard_memory.stats(CARD)[0] == 1   # 新 rc_sid / 刷新后仍是同一张卡


def test_clear():
    rolecard_memory.append_extraction(CARD, _clean(), 10)
    assert rolecard_memory.clear(CARD) is True
    assert rolecard_memory.stats(CARD) == (0, 0)
    assert rolecard_memory.read(CARD)["_block"] == ""


def test_actors_must_come_from_card_or_assistant():
    data = {"summary": "你们约好一起看雪",
            "episodes": [{"cue": "看雪", "event": "你答应带对方去城外看雪",
                          "actors": ["昔涟", "张三"], "importance": 3}]}
    clean = rolecard_memory.clean_extraction(
        data, CARD, "还记得看雪吗", "当然记得，昔涟答应过你。")
    assert clean["episodes"][0]["actors"] == ["昔涟"]


def test_user_real_name_not_stored():
    user_blob = "我叫张三，我们一起看雪"
    data = {"summary": "张三和昔涟一起看雪",
            "threads": [{"text": "张三说要一起看雪", "status": "open"}],
            "episodes": [{"cue": "看雪", "event": "张三答应一起看雪",
                          "importance": 3}]}
    clean = rolecard_memory.clean_extraction(data, CARD, user_blob, "")
    assert clean["summary"] == "" and clean["threads_open"] == []
    rolecard_memory.append_extraction(CARD, clean, 10)
    path = memory.DATA_DIR / "rolecards" / f"{rolecard_memory.card_key(CARD)}.json"
    assert "张三" not in path.read_text(encoding="utf-8")


def test_virtual_place_allowed():
    data = {"summary": "你们在贝洛伯格看雪",
            "state": {"scene": "贝洛伯格"},
            "episodes": [{"cue": "看雪", "event": "你们在贝洛伯格的雪原看雪",
                          "actors": ["昔涟"], "importance": 2}]}
    clean = rolecard_memory.clean_extraction(data, CARD, "看雪", "")
    assert clean["state"]["scene"] == "贝洛伯格"
    rolecard_memory.append_extraction(CARD, clean, 10)
    assert "贝洛伯格" in rolecard_memory.read(CARD)["_block"]


def test_cap_60_keeps_high_importance():
    first = "词" + chr(0x4E00)
    episodes = [{"cue": "词" + chr(0x4E00 + i), "event": f"事件记录{i}",
                 "importance": 1, "seq": i} for i in range(60)]
    episodes.append({"cue": "重要", "event": "很重要的事",
                     "importance": 3, "seq": 99})
    path = memory.DATA_DIR / "rolecards" / f"{rolecard_memory.card_key(CARD)}.json"
    episode_store.atomic_write(path, {"summary": "", "state": {}, "threads": [],
                                      "episodes": episodes, "seq": 99})
    assert rolecard_memory.stats(CARD)[0] == 60
    block = rolecard_memory.read(CARD, "重要")["_block"]
    assert "很重要的事" in block and first not in block


def test_thread_done_removed():
    rolecard_memory.append_extraction(CARD, _clean(), 10)
    second = {"summary": "", "state": {}, "threads_open": ["寄一封信"],
              "threads_done": ["答应去城外看雪"], "episodes": []}
    rolecard_memory.append_extraction(CARD, second, 12)
    block = rolecard_memory.read(CARD)["_block"]
    assert "寄一封信" in block and "答应去城外看雪" not in block


def test_block_header_and_cap():
    rolecard_memory.append_extraction(CARD, _clean(), 10)
    block = rolecard_memory.read(CARD, "看雪")["_block"]
    assert block.startswith("（这是你和对方一起经历过的")
    assert len(block) <= rolecard_memory.BLOCK_MAX


def test_key_memory_always_visible_and_survives_cap():
    """重点记忆不吃 cue、不被 60 条上限淘汰，且排在摘要前。"""
    rolecard_memory.mark_crisis(CARD)
    rolecard_memory.mark_resumed(CARD)
    assert rolecard_memory.key_count(CARD) == 2

    path = memory.DATA_DIR / "rolecards" / f"{rolecard_memory.card_key(CARD)}.json"
    store = episode_store.read_json(path)
    store["summary"] = "你们一起看过雪"
    store["episodes"] = [{"cue": "词" + chr(0x4E00 + i), "event": f"事件记录{i}",
                          "importance": 1, "seq": i} for i in range(60)]
    episode_store.atomic_write(path, store)

    block = rolecard_memory.read(CARD, "今天有点累")["_block"]
    assert rolecard_memory.KEY_CRISIS in block
    assert rolecard_memory.KEY_RESUMED in block
    assert block.index("重点：") < block.index("摘要：")
    assert len(block) <= rolecard_memory.BLOCK_MAX


def test_key_memory_dedupes_and_clear_removes_it():
    rolecard_memory.mark_crisis(CARD)
    rolecard_memory.mark_crisis(CARD)
    assert rolecard_memory.key_count(CARD) == 1
    assert rolecard_memory.clear(CARD) is True
    assert rolecard_memory.key_count(CARD) == 0
    assert rolecard_memory.read(CARD)["_block"] == ""


def test_key_memory_rejects_sensitive_import():
    store = rolecard_memory.clean_store(
        {"key_events": ["对方说自己想自杀", rolecard_memory.KEY_CRISIS]})
    assert store["key_events"] == [rolecard_memory.KEY_CRISIS]


def test_key_memory_does_not_change_stats_shape():
    rolecard_memory.mark_crisis(CARD)
    assert rolecard_memory.stats(CARD) == (0, 0)
