"""P25：B 模式发送前护栏——没到 L3 就留在角色里，不主动提热线（m01351）。"""
import agent
import guardian
import orchestrator
import rolecard
import rolecard_guard
from rolecard import EXAMPLE_CARD

# 用户 2026-11-20 的两张截图里的原话，原样留作回归用例。
OOC_REPLY = "看起来你有些疑惑，我可能没理解清楚你的意思。我们可以慢慢聊，你想说什么都可以。"
PLAY_ACTING = ("好的，我继续扮演。你刚才说的“111”和“堵你的那个”我没太明白，"
               "能直接说说你想表达什么吗？")


def rolecard_guard_reply(reply: str, level: str = "L1", fallback: bool = False) -> str:
    """直接调护栏；默认 L1，免得每个用例都写一遍等级。"""
    return rolecard_guard.final_reply(reply, level, fallback)


def _run(text: str, sid: str) -> dict:
    """走真实管线（B 分支），只把模型那一步换掉。"""
    return orchestrator.handle(text, sid, [], EXAMPLE_CARD, {})


def test_prompt_tells_model_not_to_offer_hotline_and_how_to_answer_question_mark():
    prompt = rolecard.build_prompt(EXAMPLE_CARD, {}, [])
    assert "危机交给系统，不主动提热线" in prompt
    assert "对方只发“？”或空白时，直接用角色回一句" in prompt


def test_screenshot_apology_line_becomes_in_character_fallback():
    assert rolecard_guard_reply(OOC_REPLY) == rolecard.SAFE_FALLBACK


def test_screenshot_acting_line_becomes_in_character_fallback():
    assert rolecard_guard_reply(PLAY_ACTING) == rolecard.SAFE_FALLBACK


def test_hotline_before_l3_is_stripped_but_other_sentences_stay():
    reply = "嗯。如果你现在感到很难受或有危险，请拨打12356寻求帮助。"
    assert rolecard_guard_reply(reply) == "嗯。"


def test_l3_may_still_carry_resources():
    reply = "我在这儿。你可以打 12356。"
    assert rolecard_guard_reply(reply, level="L3") == reply


def test_in_character_reply_is_untouched():
    reply = "嗯。你堵这儿半天就为了问这个？"
    assert rolecard_guard_reply(reply) == reply


def test_empty_or_fallback_maps_to_safe_fallback():
    assert rolecard_guard_reply("") == rolecard.SAFE_FALLBACK
    assert rolecard_guard_reply("我这边刚刚卡了一下。", fallback=True) == rolecard.SAFE_FALLBACK


def test_pipeline_hides_out_of_character_reply(monkeypatch):
    monkeypatch.setattr(agent, "call_llm",
                        lambda messages, temperature=0.7: {"ok": True, "text": OOC_REPLY})
    res = _run("？", "rc-guard-1")
    assert res["reply"] == rolecard.SAFE_FALLBACK
    assert "慢慢聊" not in res["reply"]


def test_pipeline_still_short_circuits_l3_with_resources(monkeypatch):
    monkeypatch.setattr(agent, "call_llm",
                        lambda messages, temperature=0.7: {"ok": True, "text": "不该被调用"})
    res = _run("我不想活了", "rc-guard-2")
    assert res["level"] == "L3"
    assert res["reply"] == guardian.CRISIS_REPLY
    assert "12356" in res["reply"]
