"""agent.py — LLM 调用与系统提示词拼接（MOCK / 超时 / 失败兜底）。"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from roles import BOUNDARIES_COMMON, PERSONAS, SAFETY_BLOCK, TIMEOUT

# 入口只加载一次；默认不覆盖已有环境变量，否则 monkeypatch 与环境隔离都会失效。
load_dotenv()

logger = logging.getLogger(__name__)

FENCE = chr(96) * 3          # 三个反引号，避免源码里出现 markdown 围栏
MOCK_LINES = (
    "我在。你慢慢说，不着急。",
    "听起来这件事让你挺不好受的，我先陪你待一会儿。",
    "嗯，我听到了。你现在最想说的是哪一部分？",
)

# [SAFE] S14 复核/重写 prompt 放这里：guardian 通过 agent.REVIEW_SYS 引用同一常量，
# MOCK 才能按 system 原文精确分派剧本，两处各写一份 prompt 迟早漂。
# 复核只看这一句回复是否越界：不给记忆、不给会话历史，隐私不随复核外溢。
REVIEW_SYS = ("你是内容安全审核员。只输出 JSON：{\"pass\": true 或 false, "
              "\"reason\": \"简短中文原因\"}。"
              "判定为 false 的情形：下诊断、推荐药物、承诺保密、追问自杀细节、说教、超过 4 句。")
# 重写必须写明"改哪些、为什么"，否则模型只会换同义词。
REWRITE_SYS = ("你在改写一段心理支持回复。保持原意，只改被标出的问题。"
               "要求：3 句以内、不说教、不诊断、不追问危机细节；危机场景必须包含 12356。"
               "只输出改写后的正文。")

# [SAFE] S17 摘要 prompt：只写概括，禁原句 / 人名 / 地点；放这里同样是为了 MOCK 能按原文分派。
SUMMARY_SYS = ("把下面这段对话概括成不超过 120 字的第三人称摘要。"
               "只写：情绪趋势、反复出现的话题、对方接受或拒绝的安抚方式。"
               "禁止出现：原句引用、人名、地名、机构名、具体事件细节。"
               "只输出摘要正文，不要标题。")

# MOCK 剧本：命中这些标记就当"复核不通过"，让离线演示也能演一次重写。
MOCK_REVIEW_BAD = ("你应该振作", "没什么大不了", "__unsafe__")
MOCK_REWRITE_LINE = "我在。你不用急着好起来，我们先慢慢说。"
# 摘要剧本不含任何用户原话，跑 AppTest 时能直接断言“摘要里没有原文”。
MOCK_SUMMARY_LINE = "对方近期在学业与人际上都有压力，情绪偏紧；喜欢简短、不说教的回应；想被听见。"

_client: OpenAI | None = None


def _is_mock() -> bool:
    """每次现读环境变量：模块级读会让 monkeypatch 失效。"""
    return os.getenv("MOCK_LLM", "0").strip() == "1"


def _ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def _last_user(messages: list[dict]) -> str:
    """取最后一条用户消息；MOCK 的几条剧本都只看它。"""
    last = next((m.get("content") or "" for m in reversed(messages)
                 if m.get("role") == "user"), "")
    return last if isinstance(last, str) else ""


def _mock(messages: list[dict]) -> dict:
    """确定性 MOCK：同一输入永远同一输出。

    用 md5 而不是内置 hash——后者受 PYTHONHASHSEED 影响，跨进程每次不同，
    测试与演示都断言不了。
    """
    last = _last_user(messages)
    joined = "\n".join(str(m.get("content") or "") for m in messages)
    head = str(messages[0].get("content") or "") if messages else ""
    if "__fail__" in joined:
        return {"text": "", "ok": False, "error": "MockFailure", "latency_ms": 0}
    if head == REVIEW_SYS:
        bad = any(mark in joined for mark in MOCK_REVIEW_BAD)
        text = '{"pass": false, "reason": "说教"}' if bad else '{"pass": true, "reason": ""}'
        return {"text": text, "ok": True, "error": "", "latency_ms": 0}
    if head == REWRITE_SYS:
        return {"text": MOCK_REWRITE_LINE, "ok": True, "error": "", "latency_ms": 0}
    if head == SUMMARY_SYS:
        return {"text": MOCK_SUMMARY_LINE, "ok": True, "error": "", "latency_ms": 0}
    if "__unsafe__" in last:
        return {"text": "这没什么大不了的，你应该振作起来。",
                "ok": True, "error": "", "latency_ms": 0}
    idx = int(hashlib.md5(last.encode("utf-8")).hexdigest(), 16) % len(MOCK_LINES)
    return {"text": MOCK_LINES[idx], "ok": True, "error": "", "latency_ms": 0}


def _get_client() -> OpenAI:
    """懒加载：import 时不建客户端，没 Key 的机器也能跑 contract_check。

    timeout / max_retries 放在客户端：openai 1.x 的 create() 不接受 max_retries，
    传进去会抛 TypeError 并被 except 吞成 ok=False，真实调用看起来像网络故障。
    """
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            timeout=TIMEOUT,
            max_retries=1,
        )
    return _client


def call_llm(messages: list[dict], temperature: float = 0.7) -> dict:
    """调模型。永不抛异常（缺 Key 除外，那是配置错误，必须当场报）。"""
    if _is_mock():
        return _mock(messages)
    if not os.getenv("LLM_API_KEY"):
        # 在 try 之前抛：只兜边界异常，不吞配置错误，也不悄悄转 MOCK。
        raise RuntimeError("缺少 LLM_API_KEY：请在 .env 填 Key，或设 MOCK_LLM=1 离线运行")

    t0 = time.time()
    try:
        resp = _get_client().chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            messages=messages,
            temperature=temperature,
        )
        text = (resp.choices[0].message.content or "").strip()
        logger.debug("agent.call ok text_len=%s latency_ms=%s", len(text), _ms(t0))
        return {"text": text, "ok": bool(text), "error": "", "latency_ms": _ms(t0)}
    except Exception as exc:                      # 边界 1/4：LLM 调用
        # error 只放类型名：异常内容可能带 Key 或用户原文，落日志就等于泄露。
        logger.warning("agent.call_failed error=%s latency_ms=%s",
                       type(exc).__name__, _ms(t0))
        return {"text": "", "ok": False, "error": type(exc).__name__, "latency_ms": _ms(t0)}


def safe_json(text: str) -> dict | None:
    """剥掉 markdown 围栏后解析。失败返回 None（调用方按中风险处理，不许当无事）。"""
    if not text:
        return None
    s = text.strip()
    if s.startswith(FENCE):
        s = s.split(FENCE)[1]
        s = s[4:] if s.lower().startswith("json") else s
    try:
        data = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _flat(value) -> str:
    """记忆字段可能是列表也可能是字符串，统一成一行。"""
    if isinstance(value, (list, tuple)):
        return "、".join(str(v).strip() for v in value if str(v).strip())
    return str(value or "").strip()


def _facts_block(memory: dict, lore: list[str]) -> str:
    """只放 5 个字段 + lore；不放历史对话，否则 prompt 会越聊越长。"""
    rows: list[str] = []
    for key, label in (("preferred_tone", "对方喜欢的语气"),
                       ("coping_preferences", "对方愿意试的办法"),
                       ("emotion_tags", "最近的情绪"),
                       ("unresolved_issues", "还没放下的事"),
                       ("rolling_summary", "之前的谈话概况")):
        text = _flat(memory.get(key))
        if text:
            rows.append(f"{label}：{text}")
    for item in lore or []:
        text = _flat(item)
        if text:
            # [SAFE] lore 只是背景常识：允许自然带一句，但禁止整段复述成公告。
            rows.append(f"背景（和对方的话相关时用一句话带出，不要整段念）：{text}")
    return "\n".join(rows)


def _style_block(p: dict) -> str:
    """风格区只改四样：称呼 / 语气 / 句长 / emoji，外加 taboos 与示例。"""
    lines = [
        f"你是「{p['name']}」，称呼对方为「{p['address']}」。",
        f"语气：{p['tone']}。每条回复约 {p['sentence_len']} 字以内。",
        f"表情：{p['emoji']}。",
        "不要这样说：" + "；".join(p["taboos"]) + "。",
        "示例只示范语气与句长，不要复用其中任何句子；每次用你自己的话说。",
    ]
    for user_text, bot_text in p["mes_example"]:
        lines.append(f"用户：{user_text}\n你：{bot_text}")
    return "\n".join(lines)


def build_system_prompt(persona_id: str, memory: dict, lore: list[str]) -> str:
    """顺序固定：安全区 → 风格区 → 事实区 → PHI。

    安全区在最前（模型对开头最敏感），PHI 在最后（紧贴用户输入）。
    事实区是唯一可能为空的一段：空了整段省略，不留空标题。
    """
    p = PERSONAS.get(persona_id) or PERSONAS["sister_heart"]
    parts = [
        "[安全守则]\n" + SAFETY_BLOCK + "\n[说话边界]\n" + BOUNDARIES_COMMON,
        "[你的说话方式]\n" + _style_block(p),
    ]
    facts = _facts_block(memory if isinstance(memory, dict) else {}, lore or [])
    if facts:
        parts.append("[你记得的事]\n" + facts)
    parts.append("[最后提醒]\n" + p["post_history_instructions"])
    return "\n\n".join(parts)
