"""test_examples.py — P23 ①：情境示例只示范「怎么开口」，不替规则做判断。"""
from __future__ import annotations

import agent
import examples
import orchestrator
from roles import PERSONAS

# 与 test_speech 同一条红线：建议句、诊断词都不许进示例。
BANNED = ("你可以试试", "建议你", "试试看", "应该", "必须",
          "你得了", "倾向", "抑郁", "焦虑症")


def test_tag_of_prefers_specific_over_generic():
    """1. 具体情境优先：坐一天眼睛酸算 body，不算泛泛的 tired。"""
    assert examples.tag_of("眼睛很酸，坐了一整天") == "body"
    assert examples.tag_of("今天有点累，什么都不想干") == "tired"
    assert examples.tag_of("我妈又打电话来了，问我什么时候回家") == "family"


def test_tag_of_returns_empty_for_smalltalk():
    """2. 认不出来就返回空串，不猜（猜错比不给更糟）。"""
    assert examples.tag_of("今天天气不错") == ""
    assert examples.tag_of("") == ""
    # 单字线索会误伤：「积累经验」不是累，「心慌」才收。
    assert examples.tag_of("最近在积累经验") == ""
    assert examples.tag_of("我在看一本讲秩序的书") == ""


def test_every_situation_covers_all_personas():
    """3. 12 个情境 × 5 人设齐全；缺一个，那个人设这一轮就白给。"""
    assert len(examples.SITUATIONS) == 12
    for tag, item in examples.SITUATIONS.items():
        assert set(item["replies"]) == set(PERSONAS), tag


def test_situational_replies_are_distinct_and_short():
    """4. 同一情境下五人设说法不同，且都在 40 字以内。"""
    for tag, item in examples.SITUATIONS.items():
        replies = item["replies"].values()
        assert len(set(replies)) == 5, tag
        for reply in replies:
            assert len(reply) <= 40, (tag, reply)


def test_situational_examples_keep_red_lines():
    """5. 示例里不许出现建议句与诊断词——示例比规则更会带节奏。"""
    for item in examples.SITUATIONS.values():
        for reply in item["replies"].values():
            for word in BANNED:
                assert word not in reply, (word, reply)


def test_situational_block_only_when_hit():
    """6. 命中才拼 [同类情境]；没标签 / 没这个人设就整段不出现。"""
    assert examples.situational("sister_heart", "") == ""
    assert examples.situational("no_such_person", "tired") == ""
    assert examples.situational("quiet_hollow", "tired").startswith("[同类情境]")


def _capture(monkeypatch, text):
    """走 A 管线截下 system prompt；AGENT_LOOP=0 让调用点唯一。"""
    seen = {}

    def fake_llm(messages, **kwargs):
        seen["system"] = messages[0]["content"]
        return {"ok": True, "text": "嗯。"}

    monkeypatch.setattr(orchestrator, "AGENT_LOOP", False)
    monkeypatch.setattr(agent, "call_llm", fake_llm)
    orchestrator.handle(text, "ex-" + str(abs(hash(text)) % 10**6), [], "sister_heart", {})
    return seen["system"]


def test_pipeline_adds_the_matching_situation(monkeypatch):
    """7. A 管线按本轮原话选情境，只给「对方上一句 + 该做什么」，不给成品句。"""
    system = _capture(monkeypatch, "躺了一个小时了，还是睡不着")
    assert "[同类情境]" in system
    assert "对方上一句：躺了一个小时了，还是睡不着" in system
    assert "躺了一个小时，脑子还转着吧。" not in system   # 成品句会让五个人设照抄


def test_pipeline_omits_the_block_when_no_tag(monkeypatch):
    """8. 认不出来的话不加任何示例——不留空标题，也不退回通用版。"""
    system = _capture(monkeypatch, "今天天气不错")
    assert "[同类情境]" not in system


def test_card_candidates_parse_and_filter(monkeypatch):
    """9. 解析数组、丢掉越界/建议句/禁忌句/重复。"""
    import json

    card = {"identity": "守夜人", "taboos": ["我懂你"]}
    payload = json.dumps([
        {"user": "你好", "role": "嗯，来了。"},
        {"user": "你好", "role": "重复的不要。"},
        {"user": "", "role": "空的不要。"},
        {"user": "我累了", "role": "你应该早点睡。"},
        {"user": "我累了", "role": "我懂你。"},
        {"user": "太" * 61, "role": "太长。"},
    ])
    monkeypatch.setattr(agent, "call_llm",
                        lambda *a, **k: {"ok": True, "text": "好的：\n" + payload})
    assert examples.card_candidates(card) == [("你好", "嗯，来了。")]


def test_card_candidates_fail_closed(monkeypatch):
    """10. 卡上没内容 / 模型失败 / 输出没有 JSON，一律返回空列表。"""
    def boom(*args, **kwargs):
        raise AssertionError("卡上没内容时不该调模型")

    monkeypatch.setattr(agent, "call_llm", boom)
    assert examples.card_candidates({"identity": ""}) == []
    monkeypatch.setattr(agent, "call_llm", lambda *a, **k: {"ok": False, "text": ""})
    assert examples.card_candidates({"identity": "守夜人"}) == []
    monkeypatch.setattr(agent, "call_llm", lambda *a, **k: {"ok": True, "text": "没有数组"})
    assert examples.card_candidates({"identity": "守夜人"}) == []


def test_card_candidates_offline_returns_empty():
    """11. 演示模式不编造示例：宁可空着，也不给假对话。"""
    assert examples.card_candidates({"identity": "守夜人"}) == []


def _open_form(at) -> None:
    """从 A 点进 B，并勾上免责声明，停在建卡表单。"""
    [b for b in at.button if b.key == "rc_to_rolecard"][0].click().run()
    [c for c in at.checkbox if c.key == "rc_consent_box"][0].check().run()


def test_form_has_generate_button_and_fills_the_slot():
    """12. 表单有生成按钮；候选就位后「填到示例 1」写进对应控件。"""
    from pipeline import Chat

    at = Chat().at
    _open_form(at)
    assert [b.key for b in at.button if b.key == "rc_gen_examples"] == ["rc_gen_examples"]
    at.session_state["rc_example_candidates"] = [("你好", "嗯，来了。")]
    at.run()
    [b for b in at.button if b.key == "rc_fill_ex1"][0].click().run()
    assert at.session_state["rc_ex1_user"] == "你好"
    assert at.session_state["rc_ex1_role"] == "嗯，来了。"
