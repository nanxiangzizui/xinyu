"""test_risk_facts.py — P38：模型只抽事实，等级由代码表拼，模型没有地方写结论。"""
from __future__ import annotations

import pytest

import risk_facts
import risk_review
import second_opinion


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """两道补看一律桩成「没答」，测试绝不联网。"""
    monkeypatch.setattr(second_opinion, "audit", lambda text: {})
    monkeypatch.setattr(second_opinion, "cross", lambda text: {})


def _facts(who: str = "他自己", did: str = "收拾东西", after: str = "不可逆",
           motive: str = "没有交代去向", frame: str = "像收尾",
           harm: str = "读不出") -> dict:
    return {"who": who, "did": did, "after": after, "motive": motive,
            "frame": frame, "harm": harm, "why": "准备"}


def test_l3_needs_action_and_closing_frame():
    assert risk_facts.from_facts(_facts())[0] == "L3"


@pytest.mark.parametrize("key,value", [("who", "别人"), ("did", "无"),
                                       ("frame", "像日常")])
def test_any_missing_fact_cannot_reach_l3(key, value):
    """少一条都到不了 L3——这就是「无自伤指向」再也写不出来的原因。"""
    assert risk_facts.from_facts(_facts(**{key: value}))[0] != "L3"


@pytest.mark.parametrize("who,did,after,motive,frame,harm,level,sig", [
    ("他自己", "无", "看不出", "看不出", "看不出", "读不出", "L1", "无"),
    ("他自己", "无", "看不出", "看不出", "看不出", "只是难受", "L1", "弱"),
    ("他自己", "收拾", "可逆", "没有交代去向", "像日常", "读不出", "L2", "中"),
    ("他自己", "收拾", "可逆", "有正常去向", "像收尾", "读不出", "L2", "中"),
    ("他自己", "收拾", "可逆", "有正常去向", "像日常", "读不出", "L1", "无"),
    ("别人", "买了药", "不可逆", "没有交代去向", "像收尾", "他会伤到自己", "L2", "中"),
    ("虚构", "跳下去", "不可逆", "没有交代去向", "像收尾", "他会没命", "L1", "无"),
])
def test_table(who, did, after, motive, frame, harm, level, sig):
    got = risk_facts.from_facts(_facts(who=who, did=did, after=after, motive=motive,
                                       frame=frame, harm=harm))
    assert got[:2] == (level, sig)


def test_non_dict_is_not_a_guess():
    assert risk_facts.from_facts(None) is None


def test_facts_prompt_has_no_level_field():
    """提示词里不能出现 level / signal：有字段就有地方写结论。"""
    assert '"level"' not in risk_facts.DERIVE_SYS
    assert '"signal"' not in risk_facts.DERIVE_SYS
    for token in ("who", "did", "after", "motive", "frame", "harm"):
        assert f'"{token}"' in risk_facts.DERIVE_SYS


def test_derive_turns_facts_into_level(monkeypatch):
    payload = ('{"who":"他自己","did":"把书还了","after":"不可逆",'
               '"motive":"没有交代去向","frame":"像收尾","harm":"读不出","why":"还清"}')
    monkeypatch.setattr(risk_review, "_bounded", lambda messages: {"ok": True, "text": payload})
    got = risk_review.derive("我把借的书都还了，一本没留")
    assert (got["level"], got["signal"], got["flag"], got["ok"]) == ("L3", "强", "LLM_DERIVE", True)


def test_derive_failure_keeps_rule_level(monkeypatch):
    monkeypatch.setattr(risk_review, "_bounded", lambda messages: None)
    assert risk_review.derive("随便一句")["ok"] is False


def test_derive_unparsable_is_not_a_guess(monkeypatch):
    monkeypatch.setattr(risk_review, "_bounded",
                        lambda messages: {"ok": True, "text": "我觉得没事"})
    assert risk_review.derive("随便一句")["ok"] is False


def test_check_uses_facts_when_enabled(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.setattr(risk_review, "DERIVE", True)
    monkeypatch.setattr(risk_review, "judge", lambda text: pytest.fail("不该走直接判级"))
    monkeypatch.setattr(risk_review, "derive", lambda text: {
        "level": "L2", "signal": "中", "why": "动作", "ok": True, "flag": "LLM_DERIVE"})
    out = risk_review.check("今天食堂的菜有点咸", {})
    assert (out["level"], out["rule_ids"][-1]) == ("L2", "LLM_DERIVE")


def test_check_rolls_back_to_prompt_when_disabled(monkeypatch):
    """回滚开关：RISK_DERIVE=0 时仍走「模型直接判级」那条老路。"""
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.setattr(risk_review, "DERIVE", False)
    monkeypatch.setattr(risk_review, "derive", lambda text: pytest.fail("回滚后不该走抽事实"))
    monkeypatch.setattr(risk_review, "judge", lambda text: {
        "level": "L2", "signal": "中", "why": "无望", "ok": True, "flag": "LLM_REVIEW"})
    out = risk_review.check("今天食堂的菜有点咸", {})
    assert (out["level"], out["rule_ids"][-1]) == ("L2", "LLM_REVIEW")
