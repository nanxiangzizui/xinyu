"""test_memory.py — S03 的 9 条离线测试：不联网、不 sleep、不碰真实 data/memory。"""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import memory

    monkeypatch.setattr(memory, "DATA_DIR", tmp_path)
    return memory


def test_read_missing_creates_default(mem):
    """1. 读不存在的 id：返回默认值，且补充落盘一份。"""
    got = mem.read_memory("new_user")
    assert (mem.DATA_DIR / "new_user.json").exists()
    assert set(got) == mem.ALLOWED
    assert got["current_role"] == "listener"
    assert got["summary_at_turn"] == 0
    assert got["last_updated"]
    got["emotion_tags"].append("学业")
    assert mem.DEFAULT_MEMORY["emotion_tags"] == []      # 返回值不能污染默认值


def test_write_read_roundtrip(mem):
    """2. 写→读往返：值一致，last_updated 非空。"""
    mem.write_memory("u1", {
        "preferred_tone": "gentle",
        "current_role": "guide",
        "emotion_tags": ["学业"],
        "summary_at_turn": 3,
    })
    got = mem.read_memory("u1")
    assert got["preferred_tone"] == "gentle"
    assert got["current_role"] == "guide"
    assert got["emotion_tags"] == ["学业"]
    assert got["summary_at_turn"] == 3
    assert got["last_updated"]


def test_whitelist_drops_unknown_keys(mem):
    """3. 白名单：多余键丢弃，盘上也不留。"""
    mem.write_memory("u2", {"name": "张三", "preferred_tone": "gentle"})
    got = mem.read_memory("u2")
    assert "name" not in got
    raw = (mem.DATA_DIR / "u2.json").read_text(encoding="utf-8")
    assert "张三" not in raw


def test_atomic_write_keeps_valid_json_and_backup(mem):
    """4. 连写两次：文件仍是合法 JSON，.bak 存在，.tmp 不残留。"""
    mem.write_memory("u3", {"preferred_tone": "gentle"})
    mem.write_memory("u3", {"preferred_tone": "direct"})
    path = mem.DATA_DIR / "u3.json"
    assert json.loads(path.read_text(encoding="utf-8"))["preferred_tone"] == "direct"
    assert (mem.DATA_DIR / "u3.json.bak").exists()
    assert not (mem.DATA_DIR / "u3.json.tmp").exists()


def test_corrupt_main_recovers_from_backup(mem):
    """5. 正文坏、备份好：读回备份内容，不抛异常。"""
    mem.write_memory("u4", {"preferred_tone": "gentle"})
    mem.write_memory("u4", {"preferred_tone": "direct"})
    (mem.DATA_DIR / "u4.json").write_text("{broken", encoding="utf-8")
    assert mem.read_memory("u4")["preferred_tone"] == "gentle"


def test_both_corrupt_resets_and_rewrites(mem):
    """6. 正文与备份都坏：回默认值，并把合法文件重新落盘。"""
    mem.write_memory("u5", {"preferred_tone": "gentle"})
    mem.write_memory("u5", {"preferred_tone": "direct"})
    (mem.DATA_DIR / "u5.json").write_text("{broken", encoding="utf-8")
    (mem.DATA_DIR / "u5.json.bak").write_text("{broken", encoding="utf-8")
    got = mem.read_memory("u5")
    assert got["preferred_tone"] == "neutral"
    again = json.loads((mem.DATA_DIR / "u5.json").read_text(encoding="utf-8"))
    assert again["current_role"] == "listener"


def test_scrub_phone_number(mem):
    """7. 脱敏：手机号落盘前变成占位符。"""
    mem.write_memory("u6", {"preferred_tone": "13800138000"})
    got = mem.read_memory("u6")
    assert "[手机]" in got["preferred_tone"]
    assert "13800138000" not in json.dumps(got, ensure_ascii=False)


def test_clear_removes_all_three_files(mem):
    """8. 清空：正文、.bak、.tmp 都删，返回 True。"""
    mem.write_memory("u7", {"preferred_tone": "gentle"})
    mem.write_memory("u7", {"preferred_tone": "direct"})
    (mem.DATA_DIR / "u7.json.tmp").write_text("{}", encoding="utf-8")
    assert mem.clear_memory("u7") is True
    for name in ("u7.json", "u7.json.bak", "u7.json.tmp"):
        assert not (mem.DATA_DIR / name).exists()


def test_invalid_session_id_rejected(mem):
    """9. 非法 id（路径穿越）：抛 ValueError，不落到磁盘。"""
    with pytest.raises(ValueError):
        mem.clear_memory("../evil")
    with pytest.raises(ValueError):
        mem.read_memory("../evil")
