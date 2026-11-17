"""test_orchestrator.py — P1：编排顺序 / 兜底 / trace 不含原文 / state 跨轮。

不走 AppTest：orchestrator 不依赖 streamlit，传普通 dict 就能测。
"""
from __future__ import annotations

import json

import agent
import episode_store
import guardian
import memory_extract
import orchestrator
import pipeline
from roles import COOLDOWN

MARK = "ZzqMarker9"          # 特征串：日志与 trace 里都不许出现


def test_l3_short_circuits_before_agent(monkeypatch):
    """L3 不进生成：把 call_llm 换成炸弹，跑通即证明没调。"""
    def boom(*args, **kwargs):
        raise AssertionError("L3 不许调模型")

    monkeypatch.setattr(agent, "call_llm", boom)
    monkeypatch.setattr(agent, "chat_with_tools", boom)
    res = orchestrator.handle("我不想活了", "t1", [], "sister_heart", {})
    assert (res["level"], res["role"], res["short_circuit"]) == ("L3", "crisis", True)
    assert res["reply"] == guardian.CRISIS_REPLY


def test_node_order_is_unchanged():
    """顺序即契约：少一步/多一步都算改了行为。"""
    res = orchestrator.handle("你好", "t2", [], "sister_heart", {})
    assert [s["node"] for s in res["trace"]] == [
        "pre_check", "aggregate", "coordinator", "cooldown",
        "lore", "prompt", "generate", "post_check", "memory_write"]


def test_exception_becomes_fallback_and_logged(monkeypatch):
    """生成抛异常 → 一句人话 + L2 + PIPELINE_FAILED；开关两条分支都走同一兜底。"""
    def boom(*args, **kwargs):
        raise TimeoutError()

    monkeypatch.setattr(agent, "chat_with_tools", boom)
    monkeypatch.setattr(agent, "call_llm", boom)
    # 兜底只在 safe_run（handle 按 §5.1 让异常上抛，节点层不许吞）。
    res = orchestrator.safe_run("今天很累", "t3", [], "sister_heart", {})
    assert res["reply"] == orchestrator.FALLBACK_LINE
    assert (res["level"], res["role"], res["degraded"]) == ("L2", "listener", True)
    row = pipeline.reply_rows("t3")[-1]
    assert (row["level"], row["action"], row["rule_ids"]) == (
        "L2", "template_fallback", ["PIPELINE_FAILED"])

    # AGENT_LOOP=0 是回退开关：行为必须与 v1 管线一致（同样是兜底 + 留痕）。
    monkeypatch.setattr(orchestrator, "AGENT_LOOP", False)
    old = orchestrator.safe_run("今天很累", "t3v1", [], "sister_heart", {})
    assert (old["reply"], old["level"], old["role"], old["degraded"]) == (
        orchestrator.FALLBACK_LINE, "L2", "listener", True)
    row = pipeline.reply_rows("t3v1")[-1]
    assert (row["action"], row["rule_ids"]) == ("template_fallback", ["PIPELINE_FAILED"])


def test_trace_and_log_carry_no_user_text():
    """同一条特征串：trace 没有，JSONL 也没有。"""
    res = orchestrator.handle(f"{MARK} 今天有点累", "t4", [], "sister_heart", {})
    assert MARK not in json.dumps(res["trace"], ensure_ascii=False)
    blob = json.dumps(pipeline.rows("t4"), ensure_ascii=False)
    assert MARK not in blob


def test_state_threads_cooldown_across_turns():
    """同一个 state 连跑两轮：冷却真的留下来了（漏传 state 会这里红）。"""
    state: dict = {}
    orchestrator.handle("我不想活了", "t5", [], "sister_heart", state)
    assert (state["cooldown"], state["ever_crisis"]) == (COOLDOWN - 1, True)
    res = orchestrator.handle("我该怎么办", "t5", [], "sister_heart", state)
    assert (res["role"], res["reason"]) == ("listener", "after_crisis")


def test_extract_runs_without_extra_trace_node(monkeypatch):
    """P10：抽取发生在 memory_write 之后，但 trace 仍是 9 节点。"""
    calls = []
    monkeypatch.setattr(memory_extract, "maybe_run",
                        lambda *args: calls.append(args))
    res = orchestrator.handle("今天有点累", "t6", [], "sister_heart", {})
    assert calls and calls[0][0] is False
    assert len(res["trace"]) == 9


def test_l3_does_not_extract(monkeypatch):
    """L3 在抽取之前短路：断网/坏模型都不影响危机卡。"""
    def boom(*args):
        raise AssertionError("L3 不许抽取")

    monkeypatch.setattr(memory_extract, "maybe_run", boom)
    res = orchestrator.handle("我不想活了", "t7", [], "sister_heart", {})
    assert res["short_circuit"] is True


def test_episode_block_reaches_a_prompt(monkeypatch):
    """A 的确定性召回结果必须真的进 system prompt。"""
    seen = {}

    def fake_recall(sid, text):
        return {"_episode_text": "（下面有对方以前提过的事）\n- 对方下个月要搬家",
                "_last_len": 0, "_last_try_len": 0}

    def fake_llm(messages, **kwargs):
        seen["system"] = messages[0]["content"]
        return {"ok": True, "text": "那搬家那天记得留点力气。"}

    monkeypatch.setattr(orchestrator, "AGENT_LOOP", False)
    monkeypatch.setattr(episode_store, "read_with_recall", fake_recall)
    monkeypatch.setattr(agent, "call_llm", fake_llm)
    orchestrator.handle("我下周要搬家", "t8", [], "sister_heart", {})
    assert "对方下个月要搬家" in seen["system"]
