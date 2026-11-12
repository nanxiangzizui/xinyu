"""orchestrator.py — 固定七步管线：判危 → 聚合 → 路由 → 冷却 → 事实 → prompt → 生成 → 审 → 记 → 摘要 → 日志。

[SAFE] 本模块不 import streamlit：会话状态由调用方以 mapping 传入
（app 传 st.session_state，测试传普通 dict）。顺序在本文件里是唯一事实来源；
节点内部逻辑仍留在各自模块，本文件不复制任何业务判断。

P1 只做搬家：逻辑、顺序、日志字段、文案与 app.py 原实现逐行一致。
"""
from __future__ import annotations

import logging
import os
import time

import agent
import agent_loop
import coordinator
import guardian
import memory
import tools as tools_mod
from logger import log_turn, session_hash
from roles import COOLDOWN, N_WINDOW

logger = logging.getLogger(__name__)

FALLBACK_LINE = "我这边刚刚卡了一下，但我在。你可以再说一句吗？"

AGENT_LOOP = os.environ.get("AGENT_LOOP", "0") == "1"   # 出问题一键关回 v1
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
              trace: list[dict]) -> dict:
    """生成一步：AGENT_LOOP=0 走 v1 的 call_llm；=1 进受控工具循环。"""
    t0 = time.perf_counter()
    if not AGENT_LOOP:
        out = agent.call_llm([{"role": "system", "content": prompt},
                              *history[-10:]])
        _node(trace, "generate", "ok", _ms(t0), "pipeline")
        return out
    tool_list = tools_mod.list_for_turn(role, level, allow_web=ALLOW_WEB)
    res = agent_loop.run_agent(prompt, history[-10:], tool_list,
                               fallback_text=FALLBACK_LINE)
    _node(trace, "generate", "ok" if res.ok else "error", _ms(t0),
          f"tools={res.tool_calls}")
    # [SAFE] 形状对齐 call_llm：下游 guardian / 日志 / 兜底一行都不用改。
    return {"text": res.text, "ok": res.ok, "error": res.error,
            "tool_calls": res.tool_calls}


def _mark_crisis(state: dict) -> None:
    """L3 当轮置冷却与永久标记。

    先置 COOLDOWN 再减 1：L3 这一轮本身已短路，不计入余量，
    之后还有 COOLDOWN-1 轮处于冷却（S11 §5.4）。
    """
    state["cooldown"] = COOLDOWN
    state["ever_crisis"] = True
    state["cooldown"] = max(0, state["cooldown"] - 1)


def _log_turn(sid: str, level: str, role: str, rule_ids: list[str],
              action: str, rewrite: int, t0: float, state: dict) -> None:
    """结构化日志唯一出口：只过白名单，不带任何原文。"""
    log_turn(session_hash=session_hash(sid),
             turn=state.get("turn", 0),
             level=level, role=role, rule_ids=rule_ids,
             action=action, rewrite=rewrite,
             latency_ms=int((time.perf_counter() - t0) * 1000))


def _effective_level(raw: str, state: dict) -> tuple[str, bool]:
    """[SAFE] 会话聚合只升不降：窗口内真实 L2+ ≥3 次升 L3，出现过 L2+ 则地板 L2。

    窗口只存 pre 的原始等级，不存聚合后的 eff，否则地板抬上来的 L2 会自己凑数升级。
    """
    levels = list(state.get("levels", []))
    eff = coordinator.aggregate_level(levels, raw)
    # 只有升到 L3 的那轮存 eff：存地板抬上来的 L2 会让平静轮自己凑成“3 次 L2”。
    state["levels"] = (levels + [eff if eff == "L3" else raw])[-N_WINDOW:]
    return eff, eff != raw


def _maybe_compress(sid: str, level: str, role: str,
                    history: list[dict], t0: float, state: dict) -> None:
    """摘要节流：满 5 轮 / 超 200 字 / 首次 L3 压一次；失败保留旧摘要。

    [SAFE] L3 分支不调模型：危机回复必须断网可用，这里只写结构化标记留档。
    """
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
                   state: dict, trace: list[dict]) -> dict:
    """L3 短路：固定模板 + 资源卡，不调 LLM、不加载人设、不写记忆。"""
    _mark_crisis(state)
    # 聚合升级与原始 L3 用不同 action，报告里才能分清“自己说出来的”和“被窗口推上来的”。
    action = "aggregate_escalate" if escalated else "short_circuit"
    _log_turn(sid, "L3", "crisis", pre["rule_ids"], action, 0, t0, state)
    _maybe_compress(sid, "L3", "crisis", [], t0, state)
    return {"reply": guardian.CRISIS_REPLY, "level": "L3", "role": "crisis",
            "reason": "crisis_shortcircuit",
            "degraded": False, "short_circuit": True, "trace": trace}


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
        "trace": trace,
    }


def handle(text: str, sid: str, history: list[dict], persona_id: str,
           state: dict | None = None) -> dict:
    """七步固定管线；异常交给 safe_run，不在这里吞。"""
    state = {} if state is None else state
    t0, trace = time.perf_counter(), []
    facts = memory.read_memory(sid)                                # 前置：读记忆
    pre = _timed(trace, "pre_check", guardian.guardian_pre_check, text)   # 1 判危
    eff_level, escalated = _timed(trace, "aggregate",               # 1.5 会话聚合
                                  _effective_level, pre["level"], state)
    if eff_level == "L3":
        # [SAFE] L3 一律短路，这一轮到此为止；等级不许被后续步骤下调。
        _node(trace, "short_circuit", "ok", _ms(t0), "L3")
        return _crisis_result(sid, pre, escalated, t0, state, trace)
    dec = _timed(trace, "coordinator", coordinator.coordinator_decide,  # 2 定角色
                 facts, text, eff_level)
    # [SAFE] 冷却/历史危机只降 guide，不碰 crisis；L3 已在上面短路，等级不会被这里下调。
    dec = _timed(trace, "cooldown", coordinator.enforce_cooldown, dec,
                 state.get("cooldown", 0), state.get("ever_crisis", False))
    state["cooldown"] = max(0, state.get("cooldown", 0) - 1)
    lore = _timed(trace, "lore", memory.match_lore, text, sid)     # 3 找事实（sid 用于同会话限次）
    prompt = _timed(trace, "prompt", agent.build_system_prompt,    # 4 拼 prompt
                    persona_id, facts, lore)
    resp = _generate(prompt, history, dec["role"], eff_level, trace)   # 5 生成
    post = _timed(trace, "post_check", guardian.guardian_post_check,   # 6 审
                  text, resp.get("text", ""), eff_level, dec["role"])
    reply = post.get("fixed_reply") or resp.get("text") or FALLBACK_LINE
    _timed(trace, "memory_write", memory.update_memory, sid, text, reply)  # 7 记
    _maybe_compress(sid, eff_level, dec["role"], history, t0, state)   # 7.5 摘要节流
    return _log_and_result(sid, pre, dec, eff_level, escalated,
                           post, resp, reply, t0, state, trace)


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
        # 判危失败时风险未知，按中风险记录；绝不按 L1 当“没事”。
        # [SAFE] S23 F-01：崩掉的这一轮也要留一行结构化日志，否则“日志行数 = 用户轮次”
        # 在故障时就对不上。异常类型名只进上面的 WARN，结构字段里只放 PIPELINE_FAILED 标记。
        try:
            _log_turn(sid, "L2", "listener", ["PIPELINE_FAILED"],
                      "template_fallback", 0, t0, state)
        except Exception:                          # 边界：日志本身失败也不许抛回界面
            pass
        return {"reply": FALLBACK_LINE, "level": "L2", "role": "listener",
                "reason": "default", "degraded": True, "trace": []}
