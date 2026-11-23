"""test_risk_review.py — P32：规则没命中时才问模型，且只升不降。"""
from __future__ import annotations

import pytest

import agent
import guardian
import orchestrator
import risk_review
import second_opinion


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """P35：两道补看一律桩成「没答」，测试绝不联网；要测的用例再单独覆盖。"""
    monkeypatch.setattr(second_opinion, "audit", lambda text: {})
    monkeypatch.setattr(second_opinion, "cross", lambda text: {})


@pytest.fixture(autouse=True)
def _prompt_path(monkeypatch):
    """P38：这一组测的是回滚路径（模型直接判级）；抽事实那条见 test_risk_facts.py。"""
    monkeypatch.setattr(risk_review, "DERIVE", False)


def _stub(level: str, why: str = "", ok: bool = True, calls: list | None = None,
          signal: str = "中"):
    def judge(text: str) -> dict:
        if calls is not None:
            calls.append(text)
        return {"level": level, "signal": signal, "why": why, "ok": ok}
    return judge


def _live(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_LLM", "0")


def test_rule_hit_never_calls_model(monkeypatch):
    _live(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(risk_review, "judge", _stub("L3", calls=calls))
    out = risk_review.check("我不想活了")
    assert (out["level"], bool(out["rule_ids"])) == ("L3", True)
    assert calls == []


def test_exempted_rule_also_skips_model(monkeypatch):
    _live(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(risk_review, "judge", _stub("L3", calls=calls))
    out = risk_review.check("我不想死，我只是想停下来")
    assert out["level"] == "L1"
    assert calls == []


def test_rule_l2_skips_model(monkeypatch):
    _live(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(risk_review, "judge", _stub("L3", calls=calls))
    out = risk_review.check("我真的没用")
    assert out["level"] == "L2"
    assert calls == []


def test_ambiguous_text_asks_model_and_raises(monkeypatch):
    _live(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(risk_review, "judge", _stub("L2", "无望", calls=calls))
    out = risk_review.check("最近什么都提不起劲，也不知道跟谁说")
    assert calls and out["level"] == "L2"
    assert out["rule_ids"] == ["LLM_REVIEW"]
    assert "模型复核" in out["reason"]
    assert out["llm_review"] == {"level": "L2", "why": "无望"}


def test_model_failure_keeps_rule_level(monkeypatch):
    _live(monkeypatch)
    monkeypatch.setattr(risk_review, "judge", _stub("L1", ok=False))
    out = risk_review.check("今天食堂的菜有点咸")
    assert out["level"] == "L1"
    assert out["rule_ids"] == []


def test_mock_mode_skips_model(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    calls: list[str] = []
    monkeypatch.setattr(risk_review, "judge", _stub("L3", calls=calls))
    out = risk_review.check("今天食堂的菜有点咸")
    assert (out["level"], calls) == ("L1", [])


def test_switch_off_skips_model(monkeypatch):
    _live(monkeypatch)
    monkeypatch.setattr(risk_review, "ENABLED", False)
    calls: list[str] = []
    monkeypatch.setattr(risk_review, "judge", _stub("L3", calls=calls))
    out = risk_review.check("最近什么都提不起劲")
    assert (out["level"], calls) == ("L1", [])


def test_judge_parses_three_levels(monkeypatch):
    monkeypatch.setattr(agent, "call_llm",
                        lambda messages, temperature=0.0: {"ok": True,
                                                           "text": '{"level":"L2","signal":"中","why":"无望"}'})
    assert risk_review.judge("随便一句") == {"level": "L2", "signal": "中", "why": "无望",
                                            "ok": True, "flag": "LLM_REVIEW"}


def test_judge_falls_back_to_no_signal(monkeypatch):
    """模型漏写 signal 或写了不认识的值时回落「无」：不猜，也不因此抬级。"""
    monkeypatch.setattr(agent, "call_llm",
                        lambda messages, temperature=0.0: {"ok": True,
                                                           "text": '{"level":"L2","signal":"很危险"}'})
    assert risk_review.judge("随便一句")["signal"] == "无"


def test_judge_rejects_bad_level(monkeypatch):
    monkeypatch.setattr(agent, "call_llm",
                        lambda messages, temperature=0.0: {"ok": True, "text": '{"level":"L4"}'})
    assert risk_review.judge("随便一句")["ok"] is False


def test_judge_rejects_garbage(monkeypatch):
    monkeypatch.setattr(agent, "call_llm",
                        lambda messages, temperature=0.0: {"ok": True, "text": "我觉得没事"})
    assert risk_review.judge("随便一句")["ok"] is False


def test_judge_rejects_call_failure(monkeypatch):
    monkeypatch.setattr(agent, "call_llm",
                        lambda messages, temperature=0.0: {"ok": False, "text": ""})
    assert risk_review.judge("随便一句")["ok"] is False


# [SAFE] P36：判 L1 必须引得出原文、说得出动机。拿不出来的 L1 一律按 L2——
# 判高只是多问一句，判低可能让这个人把话咽回去。
def _reply(text: str):
    return lambda messages, temperature=0.0: {"ok": True, "text": text}


def test_l1_without_quote_is_lifted_to_l2(monkeypatch):
    monkeypatch.setattr(agent, "call_llm",
                        _reply('{"level":"L1","signal":"无","motive":"只是还钱"}'))
    out = risk_review.judge("我把欠的钱都还清了")
    assert (out["level"], out["flag"]) == ("L2", "LLM_REVIEW_WEAK")
    assert "quote" in out["why"]


def test_quote_must_come_from_the_original_text(monkeypatch):
    """模型自己编一句"原话"不算：摘不出来说明它没在这句话里找到东西。"""
    monkeypatch.setattr(agent, "call_llm", _reply(
        '{"level":"L1","quote":"我只是随便还还","motive":"只是还钱"}'))
    assert risk_review.judge("我把欠的钱都还清了")["level"] == "L2"


def test_motive_must_not_be_an_excuse(monkeypatch):
    monkeypatch.setattr(agent, "call_llm", _reply(
        '{"level":"L1","quote":"我把欠的钱都还清了","motive":"无自伤指向"}'))
    out = risk_review.judge("我把欠的钱都还清了")
    assert (out["level"], "空话" in out["why"]) == ("L2", True)


def test_after_irreversible_contradicts_l1(monkeypatch):
    """它自己写了「不可逆」还判 L1，是自相矛盾，代码不接受。"""
    monkeypatch.setattr(agent, "call_llm", _reply('{"level":"L1","after":"不可逆","quote":"我把欠的钱都还清了","motive":"想清账"}'))
    out = risk_review.judge("我把欠的钱都还清了")
    assert (out["level"], "不可逆" in out["why"]) == ("L2", True)


def test_supported_l1_stays_l1(monkeypatch):
    monkeypatch.setattr(agent, "call_llm", _reply(
        '{"level":"L1","after":"可逆","quote":"菜有点咸","motive":"在说食堂的菜"}'))
    out = risk_review.judge("今天食堂的菜有点咸")
    assert (out["level"], out["flag"]) == ("L1", "LLM_REVIEW")


def test_orchestrator_uses_risk_review(monkeypatch):
    calls: list[str] = []

    def fake(text: str, state=None) -> dict:
        calls.append(text)
        return guardian.guardian_pre_check(text)

    monkeypatch.setattr(orchestrator.risk_review, "check", fake)
    orchestrator.handle("今天食堂的菜有点咸", "p32", [], "sister_heart", {})
    assert calls == ["今天食堂的菜有点咸"]


# [SAFE] P34：累积只抬到 L2，永远不判 L3。连续几天说「累」在人群里太常见，
# 堆到阈值就送进危机页，判错的代价是这个人下次不敢再说真话。
def test_signal_accumulates_into_l2_but_never_l3(monkeypatch):
    _live(monkeypatch)
    monkeypatch.setattr(risk_review, "judge", _stub("L1", signal="中"))
    state: dict = {}
    levels = [risk_review.check("今天食堂的菜有点咸", state)["level"] for _ in range(6)]
    assert levels[:2] == ["L1", "L2"]
    assert set(levels[1:]) == {"L2"}
    assert state["risk_signals"] == ["中"] * risk_review.WINDOW


def test_accum_window_slides(monkeypatch):
    """窗口只留最近 5 轮：旧的滑出去，不会一直记着三天前那句话。"""
    _live(monkeypatch)
    monkeypatch.setattr(risk_review, "judge", _stub("L1", signal="弱"))
    state: dict = {"risk_signals": ["中", "中"]}
    out = risk_review.check("今天食堂的菜有点咸", state)
    assert (out["accum"], out["level"]) == (5, "L2")
    for _ in range(4):
        risk_review.check("今天食堂的菜有点咸", state)
    assert state["risk_signals"] == ["弱"] * risk_review.WINDOW
    assert risk_review.score(state["risk_signals"]) == 5


def test_rule_hits_still_feed_the_window(monkeypatch):
    """规则命中的那几轮也要给信号，否则窗口开天窗、累积看着像突然归零。"""
    _live(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(risk_review, "judge", _stub("L1", calls=calls))
    state: dict = {}
    risk_review.check("我真的没用", state)      # 规则 L2
    risk_review.check("我不想活了", state)      # 规则 L3
    assert (state["risk_signals"], calls) == (["中", "强"], [])


def test_worry_note_gated_by_accum():
    """不到阈值一个字都不给；到了才给指令，而且明说别泄漏「我注意到」。"""
    assert risk_review.worry_note({"accum": 2}) == ""
    note = risk_review.worry_note({"accum": 3})
    assert "担心" in note
    assert "我注意到" in note and "根据记录" in note
    assert "[" in note.splitlines()[0]      # 带段头，才能拼在最后一段


def test_worry_reaches_the_prompt(monkeypatch):
    """P34：累积到阈值时，那段指令要真的走到 build_system_prompt 里。"""
    monkeypatch.setenv("MOCK_LLM", "1")
    seen: dict = {}
    real = agent.build_system_prompt

    def spy(pid, memory, lore):
        seen.update(memory)
        return real(pid, memory, lore)

    monkeypatch.setattr(orchestrator.agent, "build_system_prompt", spy)
    state: dict = {"risk_signals": ["中", "中", "弱"]}
    orchestrator.handle("今天食堂的菜有点咸", "p34", [], "sister_heart", state)
    assert "担心" in str(seen.get("_worry") or "")


# [SAFE] P35：规则没命中、模型也判 L1 之后的两道补看。都只抬到 L2，都不判 L3。
def test_action_gate_is_keywords_not_a_verdict():
    """闸门只看「有没有做完了的事」，用来省调用，不是判据。"""
    assert second_opinion.looks_like_action("我把东西都寄回家了")
    assert not second_opinion.looks_like_action("今天食堂的菜有点咸")


def test_audit_lifts_completed_action_to_l2(monkeypatch):
    _live(monkeypatch)
    monkeypatch.setattr(risk_review, "judge", _stub("L1", "寄行李"))
    monkeypatch.setattr(second_opinion, "audit", lambda text: {"hit": True, "what": "寄行李"})
    out = risk_review.check("我把东西都寄回家了")
    assert (out["level"], out["second"]) == ("L2", "SECOND_AUDIT")
    assert out["rule_ids"] == ["SECOND_AUDIT"]
    assert "补看" in out["reason"]


def test_audit_skipped_when_nothing_completed(monkeypatch):
    """句子里没有「做完了的事」，不花这次调用。"""
    _live(monkeypatch)
    monkeypatch.setattr(risk_review, "judge", _stub("L1", signal="无"))
    calls: list[str] = []
    monkeypatch.setattr(second_opinion, "audit",
                        lambda text: calls.append(text) or {"hit": True})
    out = risk_review.check("今天食堂的菜有点咸")
    assert (calls, out["level"]) == ([], "L1")


def test_cross_runs_only_when_model_admits_it_is_close(monkeypatch):
    """模型自己说「中/强」却仍判 L1——分歧最大的那批才值得换模型再看。"""
    _live(monkeypatch)
    seen: list[str] = []
    monkeypatch.setattr(second_opinion, "cross",
                        lambda text: seen.append(text) or {"hit": True, "what": "像是在收尾"})
    monkeypatch.setattr(risk_review, "judge", _stub("L1", signal="无"))
    risk_review.check("今天食堂的菜有点咸")
    assert seen == []           # 信号「无」，不给第二道

    monkeypatch.setattr(risk_review, "judge", _stub("L1", signal="中"))
    out = risk_review.check("今天食堂的菜有点咸")
    assert (out["level"], out["second"]) == ("L2", "SECOND_CROSS")


def test_second_opinion_never_returns_l3(monkeypatch):
    """两道都说「像」也只到 L2：判 L3 要能指认动作 / 时间 / 手段 / 告别。"""
    _live(monkeypatch)
    monkeypatch.setattr(risk_review, "judge", _stub("L1", signal="强"))
    monkeypatch.setattr(second_opinion, "audit", lambda text: {"hit": True, "what": "x"})
    monkeypatch.setattr(second_opinion, "cross", lambda text: {"hit": True, "what": "y"})
    out = risk_review.check("我把东西都寄回家了")
    assert out["level"] == "L2"
    assert len(out["rule_ids"]) == 1 and out["rule_ids"][0].startswith("SECOND_")


def test_gate_also_fires_on_model_own_signal(monkeypatch):
    """模型说「中/强」却仍判 L1 时也给一次机会——这时句子里没有动作词。"""
    assert second_opinion.worth_a_look("今天食堂的菜有点咸", "中")
    assert not second_opinion.worth_a_look("今天食堂的菜有点咸", "无")


def test_second_look_runs_both_only_when_there_is_an_action(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(second_opinion, "audit",
                        lambda text: calls.append("audit") or {"hit": False})
    monkeypatch.setattr(second_opinion, "cross",
                        lambda text: calls.append("cross") or {"hit": True, "what": "z"})
    got = second_opinion.second_look("今天食堂的菜有点咸", "中")
    assert sorted(calls) == ["cross"] and got["flag"] == "SECOND_CROSS"

    calls.clear()
    second_opinion.second_look("我把东西都寄回家了", "无")
    assert sorted(calls) == ["audit", "cross"]      # 有动作迹象，两道都问


def test_worry_note_prefers_the_second_opinion():
    """补看命中时要说的是「就着动作问一句」，不是「这几轮」那句。"""
    assert risk_review.worry_note({"second": "SECOND_AUDIT", "accum": 9}) == second_opinion.NOTE
    assert "结束自己的生命" in second_opinion.NOTE


def test_mock_mode_makes_no_second_opinion_call(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    assert second_opinion._ask([{"role": "user", "content": "x"}], 0.5) == ""
