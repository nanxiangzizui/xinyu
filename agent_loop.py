"""agent_loop.py — 受控工具循环：最多 AGENT_MAX_STEPS 次模型往返、AGENT_MAX_TOOL_CALLS 次工具执行。

[SAFE] 预算判断全部在动作之前；异常/超限一律返回 ok=False + 兜底文本，绝不把异常冒到界面。
工具返回加 RESULT_NOTE 前缀回填：它只是资料，不是指令。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import agent
import tools

AGENT_MAX_STEPS = 3
AGENT_MAX_TOOL_CALLS = 2
AGENT_TOTAL_TIMEOUT_S = 20
HISTORY_WINDOW = 10


@dataclass
class AgentResult:
    """一轮生成的最终结果；text 为空时由 orchestrator 用 FALLBACK_LINE 兜底。"""
    text: str = ""
    tool_calls: int = 0
    trace: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    ok: bool = False
    error: str = ""


def _wire_call(call: dict, index: int) -> dict:
    """assistant 消息里的 tool_call：arguments 必须还原成 JSON 字符串。"""
    args = call.get("arguments")
    return {"id": call.get("id") or f"call_{index}", "type": "function", "function": {
        "name": call.get("name", ""),
        "arguments": args if isinstance(args, str) else json.dumps(args or {}, ensure_ascii=False)}}


def _assistant_msg(text: str, calls: list[dict]) -> dict:
    return {"role": "assistant", "content": text or "",
            "tool_calls": [_wire_call(c, i) for i, c in enumerate(calls)]}


def _tool_msg(call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _payload(res: tools.ToolResult) -> str:
    if not res.ok:
        return f"工具调用失败：{res.error or 'unknown'}。请换一种方式或直接回答。"
    return f"{tools.RESULT_NOTE}\n{json.dumps(res.data, ensure_ascii=False, default=str)}"


def _run_calls(calls: list[dict], msgs: list[dict], result: AgentResult, gate) -> int:
    """执行一轮里的工具调用；预算/门禁在每次 execute 之前判。返回实际执行数。"""
    done = 0
    for call in calls:
        cid = call.get("id") or f"call_{done}"
        if result.tool_calls >= AGENT_MAX_TOOL_CALLS:
            msgs.append(_tool_msg(cid, "工具调用预算已用完，本轮请直接回答。"))
            continue
        name, args = call.get("name", ""), call.get("arguments") or {}
        if gate is not None:
            try:
                verdict = gate(name, args)
            except Exception:                      # [SAFE] 门禁自身出错 = 拒绝，不放行
                verdict = {"allow": False, "reason": "gate_error"}
            if not verdict.get("allow", False):
                msgs.append(_tool_msg(cid, "该工具本轮不可用，请直接回答。"))
                continue
        res = tools.execute(name, args)
        result.tool_calls += 1
        done += 1
        msgs.append(_tool_msg(cid, _payload(res)))
    return done


def _fail(result: AgentResult, error: str) -> AgentResult:
    """统一失败出口：ok=False + 错误码；text 保留兜底文本。"""
    result.ok, result.error = False, error
    return result


def run_agent(system_prompt: str, history: list[dict], tool_list: list[dict],
              max_steps: int = AGENT_MAX_STEPS, *, chat=None, gate=None,
              fallback_text: str = "",
              deadline_s: float = AGENT_TOTAL_TIMEOUT_S) -> AgentResult:
    """受控循环：模型答 → 有 tool_calls 就执行并回填 → 再问，直到答或预算用尽。"""
    chat = chat or agent.chat_with_tools
    msgs = [{"role": "system", "content": system_prompt}, *history[-HISTORY_WINDOW:]]
    result = AgentResult(text=fallback_text)
    started = time.perf_counter()
    for step in range(max_steps):
        if time.perf_counter() - started > deadline_s:
            return _fail(result, "deadline")
        try:
            out = chat(msgs, tool_list)
        except Exception as exc:                   # 边界：模型层异常由这里兜
            return _fail(result, type(exc).__name__)
        if not out.get("ok", True):
            return _fail(result, out.get("error") or "llm_error")
        text, calls = (out.get("text") or "").strip(), out.get("tool_calls") or []
        if not calls:
            result.text, result.ok = text or fallback_text, True
            result.trace.append({"step": step + 1, "action": "answer", "tools": 0})
            return result
        result.usage = out.get("usage") or result.usage
        msgs.append(_assistant_msg(text, calls))
        done = _run_calls(calls, msgs, result, gate)
        result.trace.append({"step": step + 1, "action": "tools", "tools": done})
    return _fail(result, "max_steps")
