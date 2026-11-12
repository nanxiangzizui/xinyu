"""P0 能力探测：DeepSeek（OpenAI 兼容接口）是否支持 tools / tool_calls。

- 只发两条最小请求，不含任何用户数据，不写文件。
- 用法：.\.venv\Scripts\python.exe docs\evidence\probe_tools_2026-11-12.py
- 结论手工回填到同目录 P0-tools-probe.md（本脚本只打印结构）。

判定口径：
  1. 请求是否成功（200）；
  2. finish_reason 是否为 tool_calls；
  3. tool_calls[0].function.arguments 是否为合法 JSON。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from openai import OpenAI  # noqa: E402

TIMEOUT = 15
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")

ECHO_TOOL = {
    "type": "function",
    "function": {
        "name": "echo",
        "description": "回显一段文本，仅用于连通性探测，无副作用。",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "要回显的文本"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
}

PLAIN_MSG = "用一句话回答：今天适合散步吗？"
TOOL_MSG = "请调用 echo 工具回显 hello，不要直接回答。"


def _client() -> OpenAI | None:
    key = os.getenv("LLM_API_KEY", "").strip()
    if not key:
        print("[FAIL] LLM_API_KEY 为空，检查 .env")
        return None
    return OpenAI(api_key=key, base_url=BASE_URL, timeout=TIMEOUT, max_retries=0)


def _call(client: OpenAI, messages: list[dict], tools: list[dict] | None) -> dict:
    """发一条请求，返回结构化的观测结果（异常不外抛，记录类型名）。"""
    t0 = time.perf_counter()
    try:
        kwargs = {"model": MODEL, "messages": messages, "timeout": TIMEOUT}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:  # 边界：探测脚本要区分“网络/key 问题”和“不支持 tools”
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    msg = resp.choices[0].message
    calls = getattr(msg, "tool_calls", None) or []
    parsed, parse_error = [], ""
    for call in calls:
        raw = call.function.arguments
        try:
            json.loads(raw)
            parsed.append(True)
        except Exception:
            parsed.append(False)
            parse_error = "arguments 不是合法 JSON"
    return {
        "ok": True,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "finish_reason": resp.choices[0].finish_reason,
        "has_tool_calls": bool(calls),
        "n_tool_calls": len(calls),
        "tool_names": [c.function.name for c in calls],
        "args_json_ok": parsed,
        "parse_error": parse_error,
        "content": (msg.content or "")[:120],
    }


def _roundtrip(client: OpenAI) -> dict:
    """第三关：拿到 tool_call 后回填结果再问一次，看能否收敛成正常回答。

    这一步模拟 agent_loop 的两步：assistant 消息必须原样带回 tool_calls 与 id，
    否则第二步会 400——这也是 P2 最容易写错的地方。
    """
    t0 = time.perf_counter()
    try:
        first = client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": TOOL_MSG}],
            tools=[ECHO_TOOL], tool_choice="auto", timeout=TIMEOUT,
        )
        msg = first.choices[0].message
        calls = getattr(msg, "tool_calls", None) or []
        if not calls:
            return {"ok": False, "error": "step1 未返回 tool_calls，无法回填",
                    "latency_ms": int((time.perf_counter() - t0) * 1000)}
        call = calls[0]
        args = json.loads(call.function.arguments)
        messages = [
            {"role": "user", "content": TOOL_MSG},
            {"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in calls]},
            {"role": "tool", "tool_call_id": call.id,
             "content": json.dumps({"echo": args.get("text", "")}, ensure_ascii=False)},
        ]
        second = client.chat.completions.create(
            model=MODEL, messages=messages, tools=[ECHO_TOOL], timeout=TIMEOUT,
        )
        choice = second.choices[0]
        return {
            "ok": True,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "finish_reason": choice.finish_reason,
            "has_tool_calls": bool(getattr(choice.message, "tool_calls", None)),
            "content": (choice.message.content or "")[:120],
        }
    except Exception as exc:  # 边界：探测脚本要能区分协议问题和网络问题
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "latency_ms": int((time.perf_counter() - t0) * 1000)}


def _show(title: str, result: dict) -> None:
    print(f"\n=== {title} ===")
    for k, v in result.items():
        print(f"{k}: {v}")


def main() -> int:
    print(f"model={MODEL} base_url={BASE_URL}")
    client = _client()
    if client is None:
        return 2

    plain = _call(client, [{"role": "user", "content": PLAIN_MSG}], None)
    _show("case 1: 普通请求（不带 tools）", plain)

    tool = _call(client, [{"role": "user", "content": TOOL_MSG}], [ECHO_TOOL])
    _show("case 2: 请求携带 1 个 echo 工具", tool)

    trip = _roundtrip(client)
    _show("case 3: 回填 tool 结果再问一次（两跳闭环）", trip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
