"""orchestrator.py — 固定九节点管线；顺序在本文件是唯一事实来源。

[SAFE] 不 import streamlit；节点逻辑留在各自模块。P9 起 A/B 只差记忆/工具/风格分支。
"""
from __future__ import annotations

import functools
import logging
import os
import time

import agent
import agent_loop
import coordinator
import episode_store, memory_extract, quiz_store, rolecard_memory
import guardian
import knowledge
import memory
import rolecard
import style
import tools as tools_mod
import web
from logger import log_turn, session_hash

logger = logging.getLogger(__name__)

FALLBACK_LINE = "我这边刚刚卡了一下，但我在。你可以再说一句吗？"

AGENT_LOOP = os.environ.get("AGENT_LOOP", "1") == "1"   # 出问题一键关回 v1
ALLOW_WEB = os.environ.get("ALLOW_WEB", "0") == "1"     # P3 起才可能为真


def _ms(t0: float) -> int:
    """毫秒耗时；trace 只记整数，不记浮点尾巴。"""
    return int((time.perf_counter() - t0) * 1000)


def _node(trace: list[dict], node: str, status: str, ms: int, detail: str = "") -> None:
    """记一步编排；detail 只准放等级/角色/状态，不放原句、不放 prompt、不放回复。"""
    trace.append({"node": node, "status": status, "latency_ms": ms, "detail": detail})


def _detail(out: object) -> str:
    """从节点返回值里挑一句可公开的说明；挑不出就返回空串。"""
    if not isinstance(out, dict):
        return ""
    parts = [str(out[key]) for key in ("level", "role") if out.get(key)]
    if "ok" in out:
        parts.append("ok" if out["ok"] else str(out.get("error") or "fail"))
    return " ".join(parts)


def _timed(trace: list[dict], node: str, fn, *args, **kwargs):
    """跑一个节点并记 trace；异常照常上抛（兜底只在 safe_run，节点层不许吞）。"""
    t0 = time.perf_counter()
    try:
        out = fn(*args, **kwargs)
    except Exception:
        _node(trace, node, "error", _ms(t0))
        raise
    _node(trace, node, "ok", _ms(t0), _detail(out))
    return out


def _generate(prompt: str, history: list[dict], role: str, level: str,
              trace: list[dict], allow_tools: bool = True) -> dict:
    """生成一步：AGENT_LOOP=0 走 v1 call_llm；=1 进受控工具循环。

    B 模式传 allow_tools=False：运行时零工具、零联网，直接单次调用。
    """
    t0 = time.perf_counter()
    if not AGENT_LOOP or not allow_tools:
        out = agent.call_llm([{"role": "system", "content": prompt},
                              *history[-10:]])
        _node(trace, "generate", "ok", _ms(t0), "pipeline")
        return out
    tool_list = tools_mod.list_for_turn(role, level, allow_web=ALLOW_WEB)
    # [SAFE] 门禁由 orchestrator 注入：guardian 只看工具名/参数，工具结果说服不了它。
    gate = functools.partial(guardian.guardian_tool_check, role=role, level=level)
    res = agent_loop.run_agent(prompt, history[-10:], tool_list, gate=gate,
                               source_filter=web.search_sources,
                               fallback_text=FALLBACK_LINE)
    _node(trace, "generate", "ok" if res.ok else "error", _ms(t0),
          f"tools={res.tool_calls}")
    if not res.ok:
        # [SAFE] 循环失败不许当正常回复往下发：交给 safe_run 统一走 L2 + 兜底。
        raise RuntimeError(f"agent_loop:{res.error}")
    # 形状对齐 call_llm；sources 只由 web.search_sources 的代码过滤结果提供。
    return {"text": res.text, "ok": True, "sources": res.sources}

def _log_turn(sid: str, level: str, role: str, rule_ids: list[str],
              action: str, rewrite: int, t0: float, state: dict) -> None:
    """结构化日志唯一出口：只过白名单，不带任何原文。"""
    log_turn(session_hash=session_hash(sid),
             turn=state.get("turn", 0),
             level=level, role=role, rule_ids=rule_ids,
             action=action, rewrite=rewrite,
             latency_ms=int((time.perf_counter() - t0) * 1000))

def _no_lore(text: str, sid: str) -> list[str]:
    """B 模式不读知识库：角色卡已在建卡期补全，运行时零检索、零工具。"""
    return []

def _no_memory_write(sid: str, user_text: str, reply: str) -> None:
    """B 模式不写 memory.json：角色卡会话不进入陪伴记忆，刷新即清空。"""
    return None


def _maybe_compress(sid: str, level: str, role: str,
                    history: list[dict], t0: float, state: dict) -> None:
    """摘要节流：满 5 轮 / 超 200 字 / 首次 L3 压一次；L3 只写标记不调模型。"""
    mem = memory.read_memory(sid)
    turn = state.get("turn", 0)
    if not memory.should_compress(turn, len(mem["rolling_summary"]),
                                  mem["summary_at_turn"], level):
        return
    if level == "L3":
        memory.mark_crisis_summary(sid, turn)
        _log_turn(sid, level, role, ["SUMMARY_CRISIS"], "summary_compress", 0, t0, state)
        return
    new_summary = memory.compress_summary(mem["rolling_summary"],
                                          memory.recent_lines(history))
    if not new_summary:
        # 没压成就不写盘：旧摘要比空摘要有用，也不许把“没压成”记成压过了。
        _log_turn(sid, level, role, ["SUMMARY_FAILED"], "summary_compress", 0, t0, state)
        return
    mem["rolling_summary"] = new_summary
    mem["summary_at_turn"] = turn
    memory.write_memory(sid, mem)
    _log_turn(sid, level, role, [], "summary_compress", 0, t0, state)


def _crisis_result(sid: str, pre: dict, escalated: bool, t0: float,
                   state: dict, trace: list[dict], compress: bool = True) -> dict:
    """L3 短路：固定模板 + 资源卡，不调 LLM、不加载人设、不写记忆。"""
    coordinator.mark_crisis(state)
    # 聚合升级与原始 L3 用不同 action，报告里才能分清“自己说出来的”和“被窗口推上来的”。
    action = "aggregate_escalate" if escalated else "short_circuit"
    _log_turn(sid, "L3", "crisis", pre["rule_ids"], action, 0, t0, state)
    if compress:  # B 不碰 memory：连 L3 的结构化摘要标记也不写。
        _maybe_compress(sid, "L3", "crisis", [], t0, state)
    return {"reply": guardian.CRISIS_REPLY, "level": "L3", "role": "crisis",
            "reason": "crisis_shortcircuit",
            "degraded": False, "short_circuit": True, "template_fallback": False,
            "trace": trace}


def _log_and_result(sid: str, pre: dict, dec: dict, eff_level: str, escalated: bool,
                    post: dict, resp: dict, reply: str, t0: float,
                    state: dict, trace: list[dict]) -> dict:
    """审后收尾：action 只取执行书四值，日志单行，等级原样往下传。"""
    if escalated:
        # 本轮等级被聚合抬高：优先记这件事，短路/重写原因由 rule_ids 与 rewrite 保留。
        action = "aggregate_escalate"
    elif post.get("template_fallback"):
        action = "template_fallback"
    else:
        action = "rewrite" if post.get("rewrite") else "pass"
    logged_ids = list(pre["rule_ids"])
    if "preachy" in (post.get("reason") or ""):
        # [SAFE] 执行书 §5.3.1：说教词不进 RULES，但日志要能和 H / W 组区分开。
        logged_ids.append("SAYING")
    _log_turn(sid, eff_level, dec["role"], logged_ids,
              action, post.get("rewrite", 0), t0, state)
    return {
        "reply": reply,
        "level": eff_level,
        "role": dec["role"],
        "reason": dec["reason"],
        # 只看字符串会把“模型失败、guardian 换成安全兜底”误判成正常回复（S13 起会发生）。
        "degraded": (not resp.get("ok", False)) or reply == FALLBACK_LINE,
        # P14：模板兜底整条不拆；标记由这一层给出，UI 不猜 reply 的来历。
        "template_fallback": bool(post.get("template_fallback")),
        "sources": resp.get("sources") or [],
        "trace": trace,
    }


def handle(text: str, sid: str, history: list[dict], persona_id: str,
           state: dict | None = None) -> dict:
    """九节点固定管线；A/B 只差记忆/工具/风格分支，顺序与等级逻辑一致。"""
    state = {} if state is None else state
    is_rolecard = isinstance(persona_id, dict)
    t0, trace = time.perf_counter(), []
    # [SAFE] A 读情景记忆；B 读按卡存的记忆。两者都不写 memory.json 的白名单字段。
    facts = (rolecard_memory.read(persona_id, text) if is_rolecard
             else episode_store.read_with_recall(sid, text))
    # 趣味测试记录是单独一区：只有对方自己提起时才拼进来，平时模型看不见。B 不读。
    quiz_text = "" if is_rolecard else quiz_store.recall(sid, text)
    if quiz_text:
        facts["_quiz_text"] = quiz_text
    pre = _timed(trace, "pre_check", guardian.guardian_pre_check, text)   # 1 判危
    eff_level, escalated = _timed(trace, "aggregate",               # 1.5 会话聚合
                                  coordinator.effective_level, pre["level"], state)
    if eff_level == "L3":
        # [SAFE] L3 一律短路，这一轮到此为止；B 也不写摘要标记。
        _node(trace, "short_circuit", "ok", _ms(t0), "L3")
        return _crisis_result(sid, pre, escalated, t0, state, trace, compress=not is_rolecard)
    dec = _timed(trace, "coordinator", coordinator.decide_with_choice,   # 2 定角色
                 facts, text, eff_level, state.get("role_choice", ""))
    # [SAFE] 冷却/历史危机只降 guide，不碰 crisis；L3 已在上面短路，等级不会被这里下调。
    dec = _timed(trace, "cooldown", coordinator.enforce_cooldown, dec,
                 state.get("cooldown", 0), state.get("ever_crisis", False))
    state["cooldown"] = max(0, state.get("cooldown", 0) - 1)
    if not is_rolecard:  # P16（m00002）：A 只有 listener 收窄问句；guide / crisis 不受影响
        facts["_role"] = dec["role"]
        facts["_listener_hint"] = style.listener_hint(history)
    lore_fn = _no_lore if is_rolecard else knowledge.facts_for
    lore = _timed(trace, "lore", lore_fn, text, sid)               # 3 找事实
    prompt = _timed(trace, "prompt", agent.build_system_prompt, persona_id, facts, lore)
    resp = _generate(prompt, history, dec["role"], eff_level, trace, allow_tools=not is_rolecard)
    post = _timed(trace, "post_check", guardian.guardian_post_check,   # 6 审
                  text, resp.get("text", ""), eff_level, dec["role"])
    reply = post.get("fixed_reply") or resp.get("text") or FALLBACK_LINE
    if is_rolecard and (post.get("template_fallback") or reply == FALLBACK_LINE):
        reply = rolecard.SAFE_FALLBACK   # [SAFE] B 的兜底也留在角色里
    # [SAFE] 只润色复核通过的模型输出；模板兜底、L3、兜底句逐字不动。
    if (not is_rolecard and post["pass"] and not post.get("template_fallback")
            and eff_level != "L3" and reply != FALLBACK_LINE):
        reply = style.polish(reply, persona_id, eff_level, dec["role"])
    write_fn = _no_memory_write if is_rolecard else memory.update_memory
    _timed(trace, "memory_write", write_fn, sid, text, reply)      # 7 记
    if not is_rolecard:
        _maybe_compress(sid, eff_level, dec["role"], history, t0, state)
    # 每 5 轮抽一次；失败只漏记，不新增 trace 节点，也不阻塞本轮回复。
    memory_extract.maybe_run(is_rolecard, persona_id, sid, facts, history, text, reply)
    return _log_and_result(sid, pre, dec, eff_level, escalated, post, resp, reply, t0, state, trace)


def safe_run(text: str, sid: str, history: list[dict], persona_id: str,
             state: dict | None = None) -> dict:
    """任何异常都变成一句人话；日志只记类型名，不记原文与堆栈。"""
    state = {} if state is None else state
    t0 = time.perf_counter()
    try:
        return handle(text, sid, history, persona_id, state)
    except Exception as exc:                       # 边界：界面永不显示 traceback
        logger.warning("pipeline_failed session=%s error=%s",
                       sid[:6], type(exc).__name__)
        # 判危失败按中风险记，绝不按 L1 当“没事”；崩掉的这一轮也要留结构化日志，
        # 否则“日志行数 = 用户轮次”对不上。异常类型名只进 WARN，字段只放 PIPELINE_FAILED。
        try:
            _log_turn(sid, "L2", "listener", ["PIPELINE_FAILED"],
                      "template_fallback", 0, t0, state)
        except Exception:                          # 边界：日志本身失败也不许抛回界面
            pass
        fallback = rolecard.SAFE_FALLBACK if isinstance(persona_id, dict) else FALLBACK_LINE
        return {"reply": fallback, "level": "L2", "role": "listener",
                "reason": "default", "degraded": True, "template_fallback": True,
                "trace": []}
