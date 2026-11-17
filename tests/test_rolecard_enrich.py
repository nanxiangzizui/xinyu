"""test_rolecard_enrich.py — P9f：建卡期检索补全（离线；联网只用假 transport）。"""
from __future__ import annotations

import json
import urllib.parse

import orchestrator
import rolecard
import rolecard_enrich
import web


def _known_card(**overrides) -> dict:
    card = {
        "origin": "known", "work": "某虚构作品", "name": "青砚",
        "identity": "来自过去的旅人", "setting": "",
        "voice": "说话轻，句子短", "address": "你",
        "examples": [("在吗", "在。"), ("今天有点累", "那就先歇一会儿。")],
        "taboos": [],
    }
    card.update(overrides)
    return card


def _items() -> dict:
    return {"items": [{"title": "资料页", "url": "https://example.com/a",
                       "snippet": "她是来自过去的旅人。"}]}


def test_build_queries_use_work_name_and_three_angles():
    """建卡检索三条：设定/经历/关系、官方介绍、米游社剧情；顺序固定。"""
    assert rolecard_enrich.build_queries(_known_card()) == [
        "某虚构作品 青砚 角色 设定 经历 人物关系 wiki 维基百科",
        "某虚构作品 青砚 官方 角色介绍",
        "某虚构作品 青砚 米游社 剧情 经历",
    ]


def test_build_queries_scrubs_and_caps():
    """手机号先脱敏，再按 80 字截断；用户设定不进检索词。"""
    queries = rolecard_enrich.build_queries(_known_card(name="13800138000"))
    assert all("[手机]" in query for query in queries)
    assert all("13800138000" not in query for query in queries)
    long_queries = rolecard_enrich.build_queries(_known_card(name="长" * 200))
    assert all(len(query) <= rolecard_enrich.ENRICH_QUERY_MAX for query in long_queries)


def test_build_queries_focus_only_two_angles():
    """盲点补全先查该人物自己的经历，再查与本卡角色的关系。"""
    queries = rolecard_enrich.build_queries(_known_card(), focus="白泽")
    assert queries == [
        "某虚构作品 白泽 经历 剧情 wiki",
        "某虚构作品 白泽 与 青砚 关系",
    ]


def test_parse_facts_whitelists_and_caps():
    """只收八个白名单字段，每段 ≤120 字；围栏 JSON 也能解析。"""
    raw = {"facts": [
        {"field": "identity", "text": "身份一"},
        {"field": "setting", "text": "设" * 130},
        {"field": "voice", "text": "轻"},
        {"field": "address", "text": "你"},
        {"field": "taboo", "text": "别催"},
        {"field": "story", "text": "她在雨城长大"},
        {"field": "world", "text": "雨城终年下雨"},
        {"field": "relationship", "text": "她认识一个邮差"},
        {"field": "plot", "text": "最终结局"},
        {"field": "setting", "text": ""},
    ]}
    facts = rolecard_enrich.parse_facts("```json\n" + json.dumps(raw) + "\n```")
    assert len(facts) == 8
    assert {fact["field"] for fact in facts} <= set(rolecard_enrich.FACT_FIELDS)
    assert all(len(fact["text"]) <= rolecard_enrich.FACT_MAX_CHARS for fact in facts)
    assert "最终结局" not in [fact["text"] for fact in facts]
    assert {"story", "world", "relationship"} <= {fact["field"] for fact in facts}


def test_parse_facts_caps_at_twelve():
    """最多 12 条，防止一次补全把卡塞爆。"""
    raw = {"facts": [{"field": "identity", "text": f"身份{idx}"} for idx in range(13)]}
    assert len(rolecard_enrich.parse_facts(json.dumps(raw))) == 12


def test_parse_facts_keeps_source_and_authority():
    """有来源编号时映射回 URL，并按域名标权威等级；编造编号不硬塞。"""
    rows = [{"url": "https://wiki.hoyolab.com/pc/x"},
            {"url": "https://www.17173.com/y"}]
    raw = {"facts": [
        {"field": "story", "text": "她守过一座桥", "source": 1},
        {"field": "relationship", "text": "她认识一个邮差", "source": 2},
        {"field": "world", "text": "雨城", "source": 9},
    ]}
    facts = rolecard_enrich.parse_facts(json.dumps(raw), rows)
    assert facts[0]["source"] == "https://wiki.hoyolab.com/pc/x"
    assert facts[0]["authority"] == "official"
    assert facts[1]["authority"] == "other"
    assert "source" not in facts[2] and "authority" not in facts[2]


def test_authority_for_tiers():
    """官方 > Wiki > 社区 > 其他；HoYoLAB 文章是社区，wiki 子域才是官方。"""
    assert rolecard_enrich.authority_for("https://wiki.hoyolab.com/pc/x") == "official"
    assert rolecard_enrich.authority_for("https://www.hoyolab.com/article/1") == "community"
    assert rolecard_enrich.authority_for("https://wiki.biligame.com/sr/x") == "wiki"
    assert rolecard_enrich.authority_for("https://www.miyoushe.com/sr/x") == "community"
    assert rolecard_enrich.authority_for("https://www.17173.com/x") == "other"
    assert rolecard_enrich.authority_for("not a url") == "unknown"


def test_auto_facts_only_authoritative():
    """自动盲点补全不吃社区/其他：宁可少写，也不把同人贴当原作。"""
    facts = [{"authority": "official"}, {"authority": "wiki"},
             {"authority": "community"}, {"authority": "other"}, {}]
    assert rolecard_enrich.auto_facts(facts) == facts[:2]


def test_parse_facts_bad_json_returns_empty():
    """坏 JSON 不抛异常，返回空列表。"""
    assert rolecard_enrich.parse_facts("这不是 JSON") == []


def test_parse_facts_drops_placeholder_meta():
    """摘要没给的信息不能当事实写进卡里；占位句直接丢掉。"""
    raw = {"facts": [
        {"field": "voice", "text": "摘要未提供明确的说话习惯"},
        {"field": "world", "text": "资料未提及"},
        {"field": "story", "text": "她曾守着旧书店"},
    ]}
    assert rolecard_enrich.parse_facts(json.dumps(raw)) == [
        {"field": "story", "text": "她曾守着旧书店"}]


def test_merge_fills_empty_and_keeps_filled_identity():
    """空字段补上；非权威来源不覆盖已填身份，只回一条冲突说明。"""
    card = _known_card()
    merged, conflicts = rolecard_enrich.merge(card, [
        {"field": "identity", "text": "另一个人"},
        {"field": "setting", "text": "一座会移动的城"},
    ])
    assert merged["identity"] == card["identity"]
    assert merged["setting"] == "一座会移动的城"
    assert "身份补充：另一个人" not in merged["lore"]
    assert conflicts and conflicts[0]["field"] == "身份"
    assert conflicts[0]["kind"] == "conflict"
    assert rolecard.validate(merged) == []


def test_merge_world_story_and_relationship_into_lore():
    """世界/经历/关系进角色认知；已填的语气不被覆盖，也不塞进认知。"""
    card = _known_card()
    merged, conflicts = rolecard_enrich.merge(card, [
        {"field": "story", "text": "她在雨城长大，后来守着旧书店。"},
        {"field": "world", "text": "雨城终年下雨，信靠摆渡人送。"},
        {"field": "relationship", "text": "她认识一个不常来的邮差。"},
        {"field": "voice", "text": "她说话慢，常用雨作比喻。"},
    ])
    assert merged["voice"] == card["voice"]
    assert len(merged["lore"]) == 3
    assert any(item.startswith("经历：") for item in merged["lore"])
    assert any(item.startswith("世界：") for item in merged["lore"])
    assert any(item.startswith("原作关系：") for item in merged["lore"])
    assert not any(item.startswith("语气：") for item in merged["lore"])
    assert conflicts and conflicts[0]["field"] == "说话风格"
    assert rolecard.validate(merged) == []


def test_merge_authoritative_identity_overrides():
    """Wiki/官方来源与已填身份冲突：以检索为主，并标成 override。"""
    card = _known_card()
    merged, conflicts = rolecard_enrich.merge(card, [
        {"field": "identity", "text": "另一个人", "authority": "wiki"},
    ])
    assert merged["identity"] == "另一个人"
    assert conflicts and conflicts[0]["kind"] == "override"
    assert rolecard.validate(merged) == []


def test_merge_voice_never_overrides_even_authoritative():
    """口吻/称呼是用户的表演层：权威来源也只提示，不改写。"""
    card = _known_card()
    merged, conflicts = rolecard_enrich.merge(card, [
        {"field": "voice", "text": "新的声音", "authority": "official"},
        {"field": "address", "text": "客人", "authority": "official"},
    ])
    assert merged["voice"] == card["voice"]
    assert merged["address"] == card["address"]
    assert [item["field"] for item in conflicts] == ["说话风格", "称呼"]


def test_merge_caps_taboos_at_three():
    """禁忌已满 3 条时不再追加，冲突里说明原因。"""
    card = _known_card(taboos=["嗯嗯", "啊啊", "哦哦"])
    merged, conflicts = rolecard_enrich.merge(card, [{"field": "taboo", "text": "别催"}])
    assert merged["taboos"] == card["taboos"]
    assert conflicts and conflicts[0]["reason"] == "taboo_full"


def test_merge_rejects_total_over_840():
    """补一条就会超过 840 字：不写，交回用户删减。"""
    card = _known_card(
        name="阿岚",
        identity="一" * 60, setting="", voice="三" * 160, address="四" * 16,
        examples=[("五" * 60, "六" * 100), ("七" * 60, "八" * 100)],
        taboos=["嗯" * 22, "啊" * 22],
    )
    assert rolecard.card_size(card) == 602
    merged, conflicts = rolecard_enrich.merge(card, [{"field": "setting", "text": "设" * 240}])
    assert merged["setting"] == ""
    assert conflicts and conflicts[0]["reason"] == "invalid"


def test_enrich_rejects_original_without_network(monkeypatch):
    """原创卡不联网：web.search 被换成炸弹也不会被调用。"""
    def _boom(*args, **kwargs):
        raise AssertionError("原创卡不许联网")

    monkeypatch.setattr(rolecard_enrich.web, "search", _boom)
    result = rolecard_enrich.enrich(rolecard.EXAMPLE_CARD)
    assert result["ok"] is False and result["error"] == "not_known"


def test_enrich_known_searches_three_angles_and_extracts(monkeypatch):
    """已知卡：三条检索 + 一次提取；事实来自白名单，来源与 rows 对齐。"""
    calls = {"search": 0, "llm": 0}
    queries = []

    def _fake_search(query, *, fetch=None):
        calls["search"] += 1
        queries.append(query)
        return _items(), ""

    def _fake_llm(messages, temperature=0.7):
        calls["llm"] += 1
        assert "网页摘要" in messages[-1]["content"]
        assert temperature == 0.0
        text = json.dumps({"facts": [{"field": "setting", "text": "会移动的城"},
                                     {"field": "story", "text": "她在城中长大"},
                                     {"field": "taboo", "text": "别催"}]})
        return {"text": text, "ok": True, "error": ""}

    monkeypatch.setattr(rolecard_enrich.web, "search", _fake_search)
    monkeypatch.setattr(rolecard_enrich.agent, "call_llm", _fake_llm)
    result = rolecard_enrich.enrich(_known_card())
    assert calls == {"search": 3, "llm": 1}
    assert queries == [
        "某虚构作品 青砚 角色 设定 经历 人物关系 wiki 维基百科",
        "某虚构作品 青砚 官方 角色介绍",
        "某虚构作品 青砚 米游社 剧情 经历",
    ]
    assert result["ok"] is True
    assert [fact["text"] for fact in result["facts"]] == ["会移动的城", "她在城中长大", "别催"]
    assert result["conflicts"] == []
    assert result["sources"] == [{"title": "资料页", "url": "https://example.com/a"}]


def test_enrich_uses_wiki_body_before_search(monkeypatch):
    """有 Wiki 正文时跳过搜索；事实 source 指回 Wiki 行，authority=wiki。"""
    wiki_row = {"title": "某虚构作品 Wiki · 青砚",
                "url": "https://wiki.biligame.com/sr/" + urllib.parse.quote("青砚"),
                "snippet": "她曾在雾港长大。" * 100}
    monkeypatch.setattr(rolecard_enrich.rolecard_wiki, "rows",
                        lambda card, *, focus="": [wiki_row])
    monkeypatch.setattr(rolecard_enrich.web, "search",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("有 Wiki 时不该搜索")))
    monkeypatch.setattr(rolecard_enrich.agent, "call_llm",
                        lambda *a, **k: {"ok": True, "error": "", "text": json.dumps(
                            {"facts": [{"field": "story", "text": "她曾在雾港长大",
                                        "source": 1}]})})
    result = rolecard_enrich.enrich(_known_card(work="某虚构作品"))
    assert result["ok"] is True
    assert result["facts"][0]["authority"] == "wiki"
    assert result["facts"][0]["source"] == wiki_row["url"]
    assert result["sources"] == [{"title": wiki_row["title"], "url": wiki_row["url"]}]



def test_extract_prompt_asks_for_concrete_events():
    """提取提示必须点名说话习惯、经历、世界，不能只让模型给身份/设定。"""
    for key in ("voice", "story", "world", "relationship"):
        assert key in rolecard_enrich.EXTRACT_SYS
    assert "至少提取 4 条" in rolecard_enrich.EXTRACT_SYS
    assert "不要只给身份和设定" in rolecard_enrich.EXTRACT_SYS
    assert "具体事件" in rolecard_enrich.EXTRACT_SYS
    assert "同人小说" in rolecard_enrich.EXTRACT_SYS
    assert "setting 只写世界" in rolecard_enrich.EXTRACT_SYS
    assert "命途/属性" in rolecard_enrich.EXTRACT_SYS


def test_enrich_web_error_skips_llm(monkeypatch):
    """检索失败就直接返回错误码，不再调模型。"""
    monkeypatch.setattr(rolecard_enrich.web, "search", lambda *a, **k: (None, "timeout"))
    monkeypatch.setattr(rolecard_enrich.agent, "call_llm",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("不该调模型")))
    result = rolecard_enrich.enrich(_known_card())
    assert result["ok"] is False and result["error"] == "timeout"


def test_enrich_focus_uses_two_queries_and_limits_fields(monkeypatch):
    """盲点补全只查两条、只收经历/世界/关系；返回 focus 供 UI 标注。"""
    calls = []

    def _fake_search(query, *, fetch=None):
        calls.append(query)
        return _items(), ""

    def _fake_llm(messages, temperature=0.7):
        assert "补全对象：白泽" in messages[-1]["content"]
        text = json.dumps({"facts": [
            {"field": "story", "text": "他曾在雪原上迷路"},
            {"field": "setting", "text": "这条应被丢"},
            {"field": "relationship", "text": "他们一起守过一座桥"},
        ]})
        return {"text": text, "ok": True, "error": ""}

    monkeypatch.setattr(rolecard_enrich.web, "search", _fake_search)
    monkeypatch.setattr(rolecard_enrich.agent, "call_llm", _fake_llm)
    result = rolecard_enrich.enrich(_known_card(), focus="白泽")
    assert len(calls) == 2
    assert all("白泽" in query for query in calls)
    assert result["ok"] is True and result["focus"] == "白泽"
    assert [fact["field"] for fact in result["facts"]] == ["story", "relationship"]


def test_enrich_bad_llm_json_returns_no_facts(monkeypatch):
    """模型没给出 JSON：按“没提取到”处理，不硬编事实。"""
    monkeypatch.setattr(rolecard_enrich.web, "search", lambda *a, **k: (_items(), ""))
    monkeypatch.setattr(rolecard_enrich.agent, "call_llm",
                        lambda *a, **k: {"text": "不是 JSON", "ok": True, "error": ""})
    result = rolecard_enrich.enrich(_known_card())
    assert result["ok"] is False and result["error"] == "no_facts"


def test_parse_facts_drops_pure_quoted_voice():
    """整句台词不是说话风格；描述性 voice 仍保留。"""
    facts = rolecard_enrich.parse_facts(json.dumps({"facts": [
        {"field": "voice", "text": "“记起我，忘记我。”"},
        {"field": "voice", "text": "说话慢，先接情绪。"}]}))
    assert [fact["text"] for fact in facts] == ["说话慢，先接情绪。"]


def test_orchestrator_b_generation_never_searches(monkeypatch):
    """B 生成路径零工具；盲点补全只发生在 UI 层，且可关。"""
    monkeypatch.setattr(web, "search",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("B 生成路径不许联网")))
    result = orchestrator.handle("今天有点累", "rc-enrich-runtime", [],
                                 _known_card(), {})
    assert result["reply"]
    assert result["level"] in ("L1", "L2")
