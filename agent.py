"""agent.py — LLM 调用与系统提示词拼接（MOCK / 超时 / 失败兜底）。"""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from openai import OpenAI

import examples
import rolecard
import style
from roles import BOUNDARIES_COMMON, PERSONAS, SAFETY_BLOCK, TIMEOUT

# 入口只加载一次；默认不覆盖已有环境变量，否则 monkeypatch 与环境隔离都会失效。
load_dotenv()

logger = logging.getLogger(__name__)

FENCE = chr(96) * 3          # 三个反引号，避免源码里出现 markdown 围栏
# P24 ①：固定 UTC+8。Streamlit Cloud 跑 UTC，直接 now() 会在晚八点告诉模型"中午"。
CN_TZ = timezone(timedelta(hours=8))
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
              "判定为 false 的情形：下诊断、推荐药物、承诺保密、追问自杀细节、说教、超过本轮句数上限。")
# 重写必须写明"改哪些、为什么"，否则模型只会换同义词。
# P20：上限不再写死 3 句——帮助模式下 6 句的结构化建议是正常长度，
# 继续按 3 句重写等于把刚放开的上限又收回去。
REWRITE_SYS = ("你在改写一段心理支持回复。保持原意，只改被标出的问题。"
               "要求：不超过原文句数，最多 8 句；不说教、不诊断、不追问危机细节；"
               "危机场景必须包含 12356。只输出改写后的正文。")

# [SAFE] S17 摘要 prompt：只写概括，禁原句 / 人名 / 地点；放这里同样是为了 MOCK 能按原文分派。
SUMMARY_SYS = ("把下面这段对话概括成不超过 120 字的第三人称摘要。"
               "只写：情绪趋势、反复出现的话题、对方接受或拒绝的安抚方式。"
               "禁止出现：原句引用、人名、地名、机构名、具体事件细节。"
               "只输出摘要正文，不要标题。")

# [SAFE] P13 趣味测试报告：只总结这次答题，不引导、不下判断；放这里让 MOCK 能分派。
QUIZ_REPORT_SYS = ("你刚陪对方做完一个趣味小游戏，现在写一小段结果总结。"
                   "只写 2-4 句、90 字以内；只说这次答题的结果和分数，"
                   "不引导、不追问、不给建议、不下判断、不承诺疗效，"
                   "不出现心理疾病名，不说「你就是这样的人」「你应该」。"
                   "语气自然，像随口说两句；只输出正文。")

# MOCK 剧本：命中这些标记就当"复核不通过"，让离线演示也能演一次重写。
MOCK_REVIEW_BAD = ("你应该振作", "没什么大不了", "__unsafe__")
MOCK_REWRITE_LINE = "我在。你不用急着好起来，我们先慢慢说。"
# 摘要剧本不含任何用户原话，跑 AppTest 时能直接断言“摘要里没有原文”。
MOCK_SUMMARY_LINE = "对方近期在学业与人际上都有压力，情绪偏紧；喜欢简短、不说教的回应；想被听见。"
# 报告剧本同样只谈结果，不点评人；离线演示与测试都断言这句在。
MOCK_QUIZ_REPORT = ("这一局你的选择挺集中的：遇事先动，再回头想，不太拖。"
                    "分数偏向一边，说明你这次选得挺干脆。"
                    "这只是个小游戏，当个参照就好。")

_client: OpenAI | None = None

# 会话级 Key：app 每轮 rerun 写一次。用 ContextVar 而不是模块变量，
# 两个浏览器会话各跑各的线程，模块变量会互相覆盖（把 A 的 Key 用去发 B 的话）。
_SESSION_KEY: contextvars.ContextVar[str] = contextvars.ContextVar("xinyu_key", default="")
_DEMO_MODE: contextvars.ContextVar[bool] = contextvars.ContextVar("xinyu_demo", default=False)


def set_session_key(key: str) -> None:
    """访客自带的 Key 只活在这一轮的执行上下文里；不落盘、不进日志。"""
    _SESSION_KEY.set((key or "").strip())


def set_demo_mode(on: bool) -> None:
    """没有站点 Key 时的显式演示模式；每轮由 app 重设，避免线程复用留下旧值。"""
    _DEMO_MODE.set(bool(on))


def _api_key() -> str:
    """会话 Key 优先，其次站点 Key；都没有返回空串。"""
    return _SESSION_KEY.get() or (os.getenv("LLM_API_KEY") or "")


def _is_mock() -> bool:
    """每次现读：环境变量给测试与离线演示，显式演示模式给没有 Key 的公开实例。"""
    if _DEMO_MODE.get():
        return True
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
    if head == QUIZ_REPORT_SYS:
        return {"text": MOCK_QUIZ_REPORT, "ok": True, "error": "", "latency_ms": 0}
    if "__unsafe__" in last:
        return {"text": "这没什么大不了的，你应该振作起来。",
                "ok": True, "error": "", "latency_ms": 0}
    idx = int(hashlib.md5(last.encode("utf-8")).hexdigest(), 16) % len(MOCK_LINES)
    return {"text": MOCK_LINES[idx], "ok": True, "error": "", "latency_ms": 0}


def _get_client(key: str) -> OpenAI:
    """懒加载：import 时不建客户端，没 Key 的机器也能跑 contract_check。

    站点 Key 复用同一个客户端；访客自带的 Key 每次新建、不缓存——
    缓存就等于把别人的 Key 留在进程里，还可能让两个会话串用连接。

    timeout / max_retries 放在客户端：openai 1.x 的 create() 不接受 max_retries，
    传进去会抛 TypeError 并被 except 吞成 ok=False，真实调用看起来像网络故障。
    """
    global _client
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    if key != (os.getenv("LLM_API_KEY") or ""):
        return OpenAI(api_key=key, base_url=base_url,
                      timeout=TIMEOUT, max_retries=1)
    if _client is None:
        _client = OpenAI(api_key=key, base_url=base_url,
                         timeout=TIMEOUT, max_retries=1)
    return _client


def call_llm(messages: list[dict], temperature: float = 0.7) -> dict:
    """调模型。永不抛异常（缺 Key 除外，那是配置错误，必须当场报）。"""
    if _is_mock():
        return _mock(messages)
    key = _api_key()
    if not key:
        # 在 try 之前抛：只兜边界异常，不吞配置错误，也不悄悄转 MOCK。
        # 公开实例的空 Key 由 app 层先切成显式演示模式，走不到这里。
        raise RuntimeError("缺少 LLM_API_KEY：请在 .env 填 Key，或设 MOCK_LLM=1 离线运行")

    t0 = time.time()
    try:
        resp = _get_client(key).chat.completions.create(
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


def chat_with_tools(messages: list[dict], tools: list[dict],
                    temperature: float = 0.7) -> dict:
    """带工具的调用；返回 {"text","tool_calls","ok","error","usage"}，异常不外抛。"""
    if _is_mock():
        return {"text": _mock(messages)["text"], "tool_calls": [], "ok": True,
                "error": "", "usage": {}}
    t0 = time.time()
    try:
        resp = _get_client(_api_key()).chat.completions.create(
            model=os.getenv("LLM_MODEL", "deepseek-chat"), messages=messages, tools=tools,
            tool_choice="auto" if tools else "none", temperature=temperature)
    except Exception as exc:                       # 边界 1/4：LLM 调用，一次失败交回 loop 兜底
        logger.warning("agent.tools_failed error=%s latency_ms=%s",
                       type(exc).__name__, _ms(t0))
        return {"text": "", "tool_calls": [], "ok": False,
                "error": type(exc).__name__, "usage": {}}
    msg = resp.choices[0].message
    calls = []
    for call in msg.tool_calls or []:
        try:
            args = json.loads(call.function.arguments or "{}")
        except (ValueError, TypeError):            # 边界：坏 JSON 当坏参数，交给 execute 拒
            args = {}
        calls.append({"id": call.id, "name": call.function.name, "arguments": args})
    usage = getattr(resp, "usage", None)
    return {"text": msg.content or "", "tool_calls": calls, "ok": True, "error": "",
            "usage": {"prompt_tokens": getattr(usage, "prompt_tokens", 0),
                      "completion_tokens": getattr(usage, "completion_tokens", 0)}}


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
    """4 个字段 + 本轮情景块 + lore；不放历史对话，prompt 才不会越聊越长。

    语气偏好不在这里：它是枚举码（gentle/direct），模型看不懂；
    由 _style_block 翻成一句中文指令，两处不能各写一份。
    """
    rows: list[str] = []
    for key, label in (("coping_preferences", "对方愿意试的办法"),
                       ("emotion_tags", "最近的情绪"),
                       ("unresolved_issues", "还没放下的事"),
                       ("rolling_summary", "之前的谈话概况")):
        text = _flat(memory.get(key))
        if text:
            rows.append(f"{label}：{text}")
    # P24 ②：情景块不放这里——实测放事实区 0–2/5 说出细节，挪到 [最后提醒] 之后才 5/5。
    # 趣味测试记录只在用户自己提起时才由 quiz_store 送进来；平时没有这个键。
    quiz_text = _flat(memory.get("_quiz_text"))
    if quiz_text:
        rows.append(quiz_text)
    for item in lore or []:
        text = _flat(item)
        if text:
            # [SAFE] lore 只是背景常识：允许自然带一句，但禁止整段复述成公告。
            rows.append(f"背景（相关时一句）：{text}")
    return "\n".join(rows)


def now_line() -> str:
    """P24 ①：给模型一个真实的钟点，否则它只能说"早点睡"这类放之四海的话。"""
    t = datetime.now(CN_TZ)
    return f"现在是 {t:%Y-%m-%d} 周{'一二三四五六日'[t.weekday()]} {t:%H:%M}（北京时间）。"


def web_ready() -> bool:
    """帮助模式要不要写"先查一次"：开关开，且至少有一家 provider 的 key。"""
    if os.getenv("ALLOW_WEB", "0").strip() != "1":
        return False
    return bool(os.getenv("BOCHA_API_KEY") or os.getenv("TAVILY_API_KEY"))


def _style_block(p: dict, persona_id: str, tone_code: str = "",
                 role: str = "", situation: str = "") -> str:
    """风格区只改四样：称呼 / 语气 / 句长 / emoji，外加 taboos、示例与开场偏好。"""
    lines = [f"你是「{p['name']}」，称呼对方为「{p['address']}」。",
             # P24 ③：「每条回复约 N 字」会被读成每句都这么长（指纹 sent_cv 0.02），改成总长 + 错开。
             f"语气：{p['tone']}。整条回复约 {p['sentence_len']} 字以内，句子长短错开，别每句都差不多长。"]
    # 开场偏好（温柔/轻松/直接）与 persona 语气不冲突：一个管底子，一个管这一轮。
    tone = style.tone_line(tone_code)
    if tone:
        lines.append(tone)
    lines += [
        f"表情：{p['emoji']}。",
        "不要这样说：" + "；".join(p["taboos"]) + "。",
        "示例只示范语气与句长，不要复用其中任何句子；每次用你自己的话说。",
    ]
    for user_text, bot_text in p["mes_example"]:
        lines.append(f"用户：{user_text}\n你：{bot_text}")
    speech = style.speech_block(persona_id)
    if speech:
        lines.append(speech)
    # P23 ①：这一轮像哪种情境，就给一条同情境的开口；命中不了整段省略，不猜。
    same = examples.situational(persona_id, situation)
    if same:
        lines.append(same)
    hint = style.tone_hint(persona_id)
    if hint:
        lines.append(hint)
    # P16（m00002）：放在 tone_hint 之后，让“这一轮用陈述句”成为离用户最近的一句。
    # 只收窄 listener；guide 求助时仍可问清一件事，crisis 走模板。
    if role == "listener":
        lines.append(style.listener_block())
    return "\n".join(lines)


def build_system_prompt(persona_id: str, memory: dict, lore: list[str]) -> str:
    """顺序固定：安全区 → 风格区 → 事实区 → PHI。

    安全区在最前（模型对开头最敏感），PHI 在最后（紧贴用户输入）。
    事实区是唯一可能为空的一段：空了整段省略，不留空标题。
    P9b：首参传 dict 即角色卡模式（B），只拼角色卡 prompt；A 的签名与行为不变。
    """
    if isinstance(persona_id, dict):
        return rolecard.build_prompt(persona_id, memory, lore)
    persona_key = persona_id if persona_id in PERSONAS else "sister_heart"
    p = PERSONAS[persona_key]
    memory = memory if isinstance(memory, dict) else {}
    parts = [
        "[安全守则]\n" + SAFETY_BLOCK + "\n[说话边界]\n" + BOUNDARIES_COMMON,
        "[你的说话方式]\n" + _style_block(
            p, persona_key, memory.get("preferred_tone", ""),
            str(memory.get("_role") or ""), str(memory.get("_situation") or "")),
    ]
    facts = _facts_block(memory, lore or [])
    if facts:
        parts.append("[你记得的事]\n" + facts)
    # P24 ①：钟点贴着 [最后提醒]；附一句"以它为准、别自己编"（实测模型会自己编"快一点了"）。
    parts.append("[现在]\n" + now_line() + "\n提到时间以这一行为准，不要自己编钟点；对方没问时不必报具体时间。")
    parts.append("[最后提醒]\n" + p["post_history_instructions"])
    # P20：帮助段放最后一段。人设的 post_history 常写着"不要急着给办法"，
    # 只有排在它后面，"这一轮可以给步骤"才压得住；位置本身是设计的一部分。
    role = str(memory.get("_role") or "")
    if role == "guide":
        parts.append(style.guide_block(web_ready()))
    elif role == "listener":
        # P23（m00039）：轮次议程同样要压在 [最后提醒] 之后，否则只是废纸。
        todo = style.listener_todo(str(memory.get("_listener_hint") or ""))
        if todo:  # P24 ③：开口规则也只有在最后一段才生效（放规则区实测 sent_cv 0.09，这里 0.43）
            parts.append(todo + "\n（后面那句用上对方刚说的那个词，十来字；跟上一句别一样长。）")
    episode = _flat(memory.get("_episode_text"))
    if episode:  # P24 ②：排在最末，才压得住 [最后提醒] 的「不要急着给办法」
        parts.append("[这轮记得]\n" + episode)
    return "\n\n".join(parts)
