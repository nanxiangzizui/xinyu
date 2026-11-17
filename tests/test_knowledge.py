"""test_knowledge.py — P8：专名卡命中 / 卡优先 / 预算 / L3 不读卡 / trace 不记名字。

运行时卡表是空的：测试角色不许写进代码，否则测出来的是「模型认识它」而不是
「卡生效」（2026-11-17 清空，见 CLAUDE.md §4）。机制用 monkeypatch 注入虚构卡来测。
"""
from __future__ import annotations

import json

import agent
import knowledge
import memory
import orchestrator
import pipeline
from roles import PERSONAS

FAKE_CARD = {
    "keys": ("青砚", "青硯", "Qingyan"),
    "text": "青砚是《某虚构作品》里的角色。先确认是不是他；别背设定，别拿「虚构」纠正对方。",
}


def _inject(monkeypatch) -> None:
    """只在当前用例内注入虚构卡，用例结束自动还原空表。"""
    monkeypatch.setattr(knowledge, "CARDS", (FAKE_CARD,))


def test_card_matches_name(monkeypatch):
    """1. 提到专名就拿到唯一一张卡，卡里带作品名。"""
    _inject(monkeypatch)
    hits = knowledge.match("你知道青砚吗")
    assert len(hits) == 1
    assert "某虚构作品" in hits[0]


def test_card_matches_traditional_and_english(monkeypatch):
    """2. 繁体与英文名同卡，别名表不写死在 if 分支里。"""
    _inject(monkeypatch)
    expected = knowledge.match("青砚")
    assert knowledge.match("青硯是谁") == expected
    assert knowledge.match("Qingyan 是谁") == expected


def test_unrelated_text_does_not_hit(monkeypatch):
    """3. 没提专名就不劫持；「她」这种代词也不该触发卡。空表时任何输入都是空。"""
    _inject(monkeypatch)
    assert knowledge.match("这电影没意义") == []
    assert knowledge.match("我不可能遇到她") == []
    assert knowledge.match("") == []
    monkeypatch.setattr(knowledge, "CARDS", ())
    assert knowledge.match("你知道青砚吗") == []


def test_cards_table_stays_empty():
    """4. 卡表必须为空：测试用的对照角色不许留在运行时表里（清空后的回归闸门）。"""
    assert knowledge.CARDS == ()


def test_card_replaces_campus_lore(monkeypatch):
    """5. 卡与校园 lore 同时命中时只给卡：两条事实会挤爆 prompt。"""
    _inject(monkeypatch)
    sid = "know_card"
    memory._lore_used.pop(sid, None)
    facts = knowledge.facts_for("青砚 快考试了", sid)
    assert len(facts) == 1 and "某虚构作品" in facts[0]
    assert "补考" not in facts[0]


def test_without_card_campus_lore_still_works():
    """6. 没命中卡时仍走原来的校园 lore，不许把老功能一起改掉。"""
    sid = "know_lore"
    memory._lore_used.pop(sid, None)
    facts = knowledge.facts_for("快考试了", sid)
    assert facts and "补考" in facts[0]


def test_l3_never_reads_card(monkeypatch):
    """7. L3 在 lore 节点之前短路；把 facts_for 换成炸弹，跑通即证明没读卡。"""
    def boom(*args, **kwargs):
        raise AssertionError("L3 不许读专名卡")

    monkeypatch.setattr(knowledge, "facts_for", boom)
    res = orchestrator.handle("我不想活了", "know_l3", [], "sister_heart", {})
    assert (res["level"], res["role"]) == ("L3", "crisis")


def test_card_not_in_trace_or_log(monkeypatch):
    """8. 卡进了 prompt，但不许进 trace 与 JSONL：日志只留结构化字段。"""
    _inject(monkeypatch)
    res = orchestrator.handle("你知道青砚吗", "know_trace", [], "sister_heart", {})
    assert "青砚" not in json.dumps(res["trace"], ensure_ascii=False)
    assert "青砚" not in json.dumps(pipeline.rows("know_trace"), ensure_ascii=False)


def test_prompt_budget_with_card():
    """9. 卡是最坏情况：五套人设加卡后仍 ≤1400 字；卡本身也守 45 字上限。"""
    card = FAKE_CARD["text"]
    assert len(card) <= knowledge.CARD_MAX_CHARS
    mem = {"preferred_tone": "温和", "emotion_tags": ["学业", "失眠"],
           "unresolved_issues": ["期末"], "rolling_summary": "在聊考试压力" * 5,
           "_episode_text": "对方以前提过：" + "下个月要搬家，" * 10 + "（当时焦虑）"}
    for pid in PERSONAS:
        prompt = agent.build_system_prompt(pid, mem, [card])
        assert len(prompt) <= 1400, (pid, len(prompt))
