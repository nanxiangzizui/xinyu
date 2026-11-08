"""agent.py — LLM 调用与系统提示词拼接（MOCK / 超时 / 失败兜底）。"""
from __future__ import annotations

from roles import TIMEOUT


def call_llm(messages: list[dict], temperature: float = 0.7) -> dict:
    """S02 空壳：返回固定文本。S04 实现真实调用与 MOCK。"""
    return {"text": "（骨架）我在这里。", "ok": False, "error": "not_implemented", "latency_ms": 0}


def build_system_prompt(persona_id: str, memory: dict, lore: list[str]) -> str:
    """S02 空壳：一句占位。S07 实现分区拼接。"""
    return "你是一个倾听者。"
