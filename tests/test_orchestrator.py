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
import style
from roles import COOLDOWN

MARK = "ZzqMarker9"          # 特征串：日志与 trace 里都不许出现


def _capture_prompt(monkeypatch, text, sid, history=None):
    """走 A 管线并截下 system prompt；AGENT_LOOP=0 让调用点唯一。"""
    seen = {}

    def fake_llm(messages, **kwargs):
        seen["system"] = messages[0]["content"]
        return {"ok": True, "text": "我在。"}

    monkeypatch.setattr(orchestrator, "AGENT_LOOP", False)
    monkeypatch.setattr(agent, "call_llm", fake_llm)
    orchestrator.handle(text, sid, history or [], "sister_heart", {})
    return seen["system"]


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


def test_listener_prompt_carries_statement_rule(monkeypatch):
    """m00002：默认的 listener 必须收到“非必要不反问”。"""
    system = _capture_prompt(monkeypatch, "今天有点累", "t9")
    assert style.LISTENER_HEAD in system
    assert "非必要不反问" in system


def test_guide_prompt_does_not_carry_listener_rule(monkeypatch):
    """“怎么办”会切 guide：求助场景仍可问清一件事，不被 listener 规则误伤。"""
    system = _capture_prompt(monkeypatch, "我该怎么办", "t10")
    assert style.LISTENER_HEAD not in system
    assert "非必要不反问" not in system


def test_question_ending_triggers_listener_repeat(monkeypatch):
    """上一轮以问号收尾时，下一轮 prompt 追加“用陈述句”。"""
    history = [{"role": "user", "content": "你好"},
               {"role": "assistant", "content": "今天怎么样？"}]
    system = _capture_prompt(monkeypatch, "就那样", "t11", history)
    assert style.LISTENER_REPEAT in system


def test_listener_reply_loses_trailing_question(monkeypatch):
    """m00331：prompt 之外再加代码兜底，listener 的收尾问句不落地。"""
    def fake_llm(messages, *args, **kwargs):
        return {"ok": True,
                "text": "这个我没法从测试里推出来。你遇到难处时，一般会先自己扛着吗？"}

    monkeypatch.setattr(orchestrator, "AGENT_LOOP", False)
    monkeypatch.setattr(agent, "call_llm", fake_llm)
    res = orchestrator.handle("你觉得我遇到困难会怎么做", "t12", [], "sister_heart", {})
    assert res["role"] == "listener"
    assert res["reply"] == "这个我没法从测试里推出来"


def test_guide_reply_keeps_trailing_question(monkeypatch):
    """guide 的问句不被 listener 的代码兜底削掉。"""
    reply = "这个我没法从测试里推出来。你遇到难处时，一般会先自己扛着吗？"

    def fake_llm(messages, *args, **kwargs):
        return {"ok": True, "text": reply}

    monkeypatch.setattr(orchestrator, "AGENT_LOOP", False)
    monkeypatch.setattr(agent, "call_llm", fake_llm)
    res = orchestrator.handle("我该怎么办", "t13", [], "sister_heart", {})
    assert res["role"] == "guide"
    assert res["reply"] == reply


# ── P20：帮助模式真的能给出步骤 ──
HELP_REPLY = (
    "你现在最该做的是把今晚的入睡时间往前挪，而不是白天硬补。"
    "今晚十一点半躺下，手机放到桌子另一头，闹钟固定七点半，别在床上刷手机。"
    "明天早上醒了先拉开窗帘，去楼下走十分钟，让身体先见到光，别一睁眼就躺着。"
    "中午最多补二十分钟，超过这个长度晚上更难睡着，下午三点以后不喝咖啡和浓茶。"
    "晚饭别吃太饱，睡前两小时不要剧烈运动，房间里尽量暗一点、凉一点。"
    "如果白天还是困，午睡前先定二十分钟的闹钟，别一躺就是一下午。"
    "如果连续两周还是这样、白天也提不起精神，去校心理中心聊聊，工作日可以预约。")


def test_guide_prompt_carries_help_block(monkeypatch):
    """「给点建议」这一轮必须收到帮助段，且它在 [最后提醒] 之后。"""
    system = _capture_prompt(monkeypatch, "给点建议", "t14")
    assert style.GUIDE_HEAD in system
    assert system.index(style.GUIDE_HEAD) > system.index("[最后提醒]")
    assert "最多 8 句" in system


def test_guide_reply_is_not_clipped_to_chat_limit(monkeypatch):
    """P20 回归点：截图里“给点建议”只回一句；6 句建议不许被 220 字截掉。"""
    def fake_llm(messages, *args, **kwargs):
        return {"ok": True, "text": HELP_REPLY}

    monkeypatch.setattr(orchestrator, "AGENT_LOOP", False)
    monkeypatch.setattr(agent, "call_llm", fake_llm)
    res = orchestrator.handle("给点建议", "t15", [], "sister_heart", {})
    assert res["role"] == "guide"
    assert len(HELP_REPLY) > style.MAX_CHARS
    assert len(res["reply"]) > style.MAX_CHARS
    assert len(res["reply"]) <= style.HELP_MAX_CHARS
    assert "校心理中心" in res["reply"]


def test_listener_reply_still_clipped_to_chat_limit(monkeypatch):
    """放松只给 guide：闲聊仍 220 字，别把 listener 也改成长篇。"""
    def fake_llm(messages, *args, **kwargs):
        return {"ok": True, "text": HELP_REPLY}

    monkeypatch.setattr(orchestrator, "AGENT_LOOP", False)
    monkeypatch.setattr(agent, "call_llm", fake_llm)
    res = orchestrator.handle("今天有点累", "t16", [], "sister_heart", {})
    assert res["role"] == "listener"
    assert len(res["reply"]) <= style.MAX_CHARS
