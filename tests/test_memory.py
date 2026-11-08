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
    """5. 正文坏、备份好：读回备份内容、修好主文件，且**再来一轮写入**也不许把坏文件写进备份。

    回归点（2026-11-08）：修好主文件后，下一轮 write_memory 会执行 copy2(主文件, .bak)；
    如果当时没修主文件，坏内容会盖掉唯一的好备份，用户记忆两份全废。
    """
    mem.write_memory("u4", {"preferred_tone": "gentle"})
    mem.write_memory("u4", {"preferred_tone": "direct"})
    (mem.DATA_DIR / "u4.json").write_text("{broken", encoding="utf-8")

    recovered = mem.read_memory("u4")
    assert recovered["preferred_tone"] == "gentle"
    repaired = json.loads((mem.DATA_DIR / "u4.json").read_text(encoding="utf-8"))
    assert repaired == recovered                           # 主文件已自愈
    bak = json.loads((mem.DATA_DIR / "u4.json.bak").read_text(encoding="utf-8"))
    assert bak["preferred_tone"] == "gentle"               # 好备份没被坏文件覆盖

    mem.write_memory("u4", recovered)                      # 模拟下一轮对话落盘
    bak2 = json.loads((mem.DATA_DIR / "u4.json.bak").read_text(encoding="utf-8"))
    assert bak2 == repaired                                # 备份是合法旧版，不是 "{broken"
    now = json.loads((mem.DATA_DIR / "u4.json").read_text(encoding="utf-8"))
    assert now["preferred_tone"] == "gentle"


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


# --- S17 摘要节流：三个触发条件 + 两道隐私闸门 ---

def test_should_compress_after_five_turns(mem):
    """10. turn=6 / 上次压缩在 1 → 满 5 轮，触发。"""
    assert mem.should_compress(6, 0, 1, "L1") is True


def test_should_compress_when_summary_too_long(mem):
    """11. 摘要 210 字 → 超长触发（与轮次无关）。"""
    assert mem.should_compress(1, mem.SUMMARY_MAX + 10, 1, "L2") is True


def test_should_compress_not_yet(mem):
    """12. 才过 2 轮且摘要不长 → 不压，避免每轮都烧一次调用。"""
    assert mem.should_compress(3, 50, 1, "L1") is False


def test_first_crisis_compresses_once(mem):
    """13. 首次 L3 立即压一次；已压过（summary_at_turn>0）就不再压。"""
    assert mem.should_compress(1, 0, 0, "L3") is True
    assert mem.should_compress(2, 0, 1, "L3") is False


def test_compress_failure_keeps_old_summary(mem, monkeypatch):
    """14. 模型失败 → 返回 None；调用方保留旧摘要，绝不写空。"""
    monkeypatch.setattr(mem, "call_llm", lambda *a, **k: {"ok": False, "text": ""})
    assert mem.compress_summary("旧摘要还在", ["最近考试压力大"]) is None


def test_compress_truncates_to_max(mem, monkeypatch):
    """15. 模型话痨 → 硬截断到 200 字。"""
    monkeypatch.setattr(mem, "call_llm",
                        lambda *a, **k: {"ok": True, "text": "啊" * 300})
    got = mem.compress_summary("", ["最近考试压力大"])
    assert got is not None and len(got) == mem.SUMMARY_MAX


def test_compress_blocks_verbatim_quote(mem, monkeypatch):
    """16. 摘要里出现 8 字以上原句 → 整次作废，宁可摘要不更新。"""
    monkeypatch.setattr(mem, "call_llm",
                        lambda *a, **k: {"ok": True, "text": "他说我今天被老师批评了很难受"})
    assert mem.compress_summary("", ["我今天被老师批评了很难受"]) is None


def test_compress_empty_history_returns_none(mem, monkeypatch):
    """17. 没有新对话就不要拿旧摘要自压（会越压越空）。"""
    called = []
    monkeypatch.setattr(mem, "call_llm", lambda *a, **k: called.append(1) or {"ok": True, "text": "x"})
    assert mem.compress_summary("旧摘要", []) is None
    assert called == []


def test_recent_lines_scrubs_and_caps(mem):
    """18. 送进模型的短句已脱敏、且每条 ≤40 字。"""
    lines = mem.recent_lines([{"role": "user", "content": "我手机13800138000，最近考试压力大"}])
    assert len(lines) == 1 and "[手机]" in lines[0]
    assert "13800138000" not in lines[0] and len(lines[0]) <= mem.LINE_MAX


def test_mark_crisis_summary_writes_note(mem):
    """19. 首次 L3 留档：不调模型也写摘要与 summary_at_turn。"""
    mem.write_memory("u8", {"rolling_summary": "之前聊过学业"})
    got = mem.mark_crisis_summary("u8", 4)
    assert mem.CRISIS_NOTE in got and got.startswith("之前聊过学业")
    mem2 = mem.read_memory("u8")
    assert mem2["summary_at_turn"] == 4
    assert mem.CRISIS_NOTE in mem2["rolling_summary"]


def test_mock_summary_has_no_user_text(mem, monkeypatch):
    """20. MOCK 剧本：摘要走固定文本，AppTest 能据此断言“摘要里没有原文”。"""
    monkeypatch.setenv("MOCK_LLM", "1")
    got = mem.compress_summary("", ["我室友最近不理我，我很难受"])
    assert got and "室友" not in got and "难受" not in got


# --- S18 记忆面板：展示脱敏 + 清空后无残留 ---

def test_panel_view_scrubs_contact_markers(mem):
    """21. 面板展示前过 scrub：手机 / 邮箱不出现在侧栏数据里，8 个中文标签顺序不变。"""
    import panel

    view = panel.panel_view({
        "preferred_tone": "gentle",
        "emotion_tags": ["a@b.com"],
        "rolling_summary": "他电话 13800138000",
    })
    text = json.dumps(view, ensure_ascii=False)
    assert "13800138000" not in text and "a@b.com" not in text
    assert "[手机]" in text and "[邮箱]" in text
    assert list(view) == list(panel.LABELS.values())
    assert "last_updated" not in text                      # 面板不展示时间戳
    assert panel.export_payload({"rolling_summary": "电话 13800138000"})[
        "rolling_summary"] == "电话 [手机]"                 # 导出同样过 scrub


def test_clear_then_read_returns_defaults(mem):
    """22. 清空后读回：8 字段全默认、无残留（面板不会显示旧内容）。"""
    mem.write_memory("u10", {
        "preferred_tone": "direct",
        "emotion_tags": ["学业"],
        "rolling_summary": "考试压力",
        "summary_at_turn": 3,
    })
    assert mem.clear_memory("u10") is True
    got = mem.read_memory("u10")
    assert set(got) == mem.ALLOWED
    assert got["preferred_tone"] == "neutral"
    assert got["current_role"] == "listener"
    assert got["role_switch_reason"] == "default"
    assert got["emotion_tags"] == [] and got["unresolved_issues"] == []
    assert got["coping_preferences"] == []
    assert got["rolling_summary"] == "" and got["summary_at_turn"] == 0

# --- S20 迷你 Lorebook：命中受控、注入受控、种子受审 ---

def test_lore_hits_exam_keyword(mem):
    """23. "快考试了" 命中补考/重修常识，且只给一条。"""
    got = mem.match_lore("快考试了，有点慌", "u_lore_1")
    assert len(got) == 1 and "补考或重修" in got[0]


def test_lore_stops_after_three_injections(mem):
    """24. 同一会话注入 3 次后不再注入（防复读）；换会话重新计数。"""
    sid = "u_lore_2"
    for _ in range(mem.LORE_USED_MAX):
        assert mem.match_lore("快考试了", sid)
    assert mem.match_lore("快考试了", sid) == []
    assert mem.match_lore("快考试了", "u_lore_2b")          # 换会话重新计数
    assert mem.match_lore("快考试了", "")                  # 不传 sid 退化为不计次


def test_lore_caps_items_and_length(mem):
    """25. 一句命中 5 条种子：最多 2 条、单轮总长 ≤100 字。"""
    got = mem.match_lore("考试 保研 宿舍 心理咨询 失眠", "u_lore_3")
    assert len(got) <= mem.LORE_MAX_ITEMS
    assert sum(len(t) for t in got) <= mem.LORE_INJECT_MAX


def test_lore_seed_shape(mem):
    """26. 8 条种子、每条 ≤25 字、不出现诊断/政策结论类表述。"""
    assert len(mem.LORE_SEED) == 8
    for entry in mem.LORE_SEED:
        assert entry["keys"] and entry["text"]
        assert len(entry["text"]) <= 25, entry["text"]
        assert all(w not in entry["text"] for w in ("抑郁症", "焦虑症", "一定", "必须"))

