"""memory_extract.py — P10 每 5 轮一次的记忆抽取（A 情景 / B 角色卡）。

只做三件事：判断该不该抽、调一次模型、把 JSON 校验后写进对应存储。
失败 fail-open：不阻塞回复，记 last_try_len 防每轮重试；MOCK 下整段跳过。
"""
from __future__ import annotations

import json
import logging
import os

import agent
import episode_store
import memory
import rolecard_memory

logger = logging.getLogger(__name__)

TURN_EVERY = 10          # 10 条消息 = 5 轮（user+assistant）
LINE_MAX = 60
MAX_ITEMS = 2

A_SYS = """你是记忆抽取器，只做一件事：从对话里挑出对方以后可能还会提到的事，写成转述。
只输出 JSON，不要解释，不要 markdown 围栏。
格式：{"episodes":[{"cue":"搬家","topic":"住处","event":"对方近期要换住处，这几天在整理行李","mood":"焦虑","importance":2}]}
规则：
1. 0-2 条；没有值得记的就输出 {"episodes":[]}。
2. cue 是 2-6 个汉字，必须原样出现在对方的话里；不用人名、地名、数字、空格，不用“今天/最近/什么”这类空词。
3. topic 只能是：学业、升学、人际、亲密关系、家庭、睡眠、求职、经济、住处、健康、约定、其他。
4. mood 只能是：平静、低落、焦虑、生气、开心、疲惫、其他。
5. importance：1=日常，2=对方在意或反复提，3=明确约定或重大变化。
6. event 4-50 字，必须完全换说法：不要保留对方原句里连续 6 个字以上的片段，更不要整句照搬；
   时间、地点、动作、感受都换词。
   例：原话“我下个月要搬家，最近一直在收拾东西” → “对方近期要换住处，这几天在整理行李”。
7. 不写姓名、学校、单位、住址、电话、邮箱、链接；不写病名、药物、医院、诊断、自伤细节。
8. 输出前逐条自检：把 event 与对方原话逐字比对；若有连续 8 个字相同，重写这条；宁可少写，也不要抄。"""

B_SYS = """你是角色扮演对话的记忆整理器。把最近几轮里“你们之间发生的事”整理成长期记忆。
只输出 JSON，不要解释，不要 markdown 围栏。
格式：{"summary":"...","state":{"scene":"...","mood":"...","relation":"..."},
"threads":[{"text":"...","status":"open"}],
"episodes":[{"cue":"看雪","topic":"约定","event":"你答应带对方去城外看雪","actors":["昔涟"],"importance":3}]}
规则：
1. summary 不超过 300 字，概括你们一起经历过的事；用“对方/你”，不写对方真名。
2. state 只写故事内的当前场景、角色情绪、关系，不写现实地名、学校、单位。
3. threads 只写还没兑现的约定或还没说完的事，最多 4 条；已经完成的把 status 写成 done。
4. episodes 0-2 条；cue 2-6 个汉字，必须原样出现在对方的话里；event 不超过 80 字，用转述。
5. actors 只能写角色卡或你上一轮回复里出现过的名字；对方消息里提到的名字不算。
6. 不写对方真名、学校、单位、住址、电话、邮箱、链接；不写病名、药物、医院、诊断、自伤细节。
7. 没有新内容就输出 {}。"""


def _is_mock() -> bool:
    return os.getenv("MOCK_LLM", "0").strip() == "1"


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _blobs(history: list[dict], text: str, reply: str) -> tuple[list[str], str, str]:
    """最近 5 轮 + 当前两条；每条 scrub 后截 60 字，另留完整（≤200）给闸门。"""
    tail = history[-(TURN_EVERY - 2):] if history else []
    msgs = [*tail, {"role": "user", "content": text},
            {"role": "assistant", "content": reply}]
    lines, user_parts, assistant_parts = [], [], []
    for msg in msgs:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        clean = memory.scrub(content.strip())
        is_user = msg.get("role") == "user"
        lines.append(f"{'对方' if is_user else '你'}：{clean[:LINE_MAX]}")
        (user_parts if is_user else assistant_parts).append(clean)
    return lines, "\n".join(user_parts), "\n".join(assistant_parts)


def parse_a(raw_text: str, user_blob: str) -> list[dict] | None:
    """A 的 JSON 校验；None=坏 JSON/坏结构，[]=合法但没有。"""
    data = agent.safe_json(raw_text)
    if not isinstance(data, dict):
        return None
    items = data.get("episodes")
    if not isinstance(items, list):
        return None
    names = episode_store.names_in(user_blob)
    out: list[dict] = []
    for item in items[:MAX_ITEMS]:
        ep = episode_store.clean_episode(item)
        if not ep:
            continue
        if ep["cue"] not in user_blob:
            continue
        if episode_store.quotes_source(ep["event"], [user_blob]):
            continue
        if any(name in ep["event"] for name in names):
            continue
        out.append(ep)
    return out


def parse_b(raw_text: str, card: dict, user_blob: str,
            assistant_blob: str) -> dict | None:
    """B 的 JSON 校验；None=坏 JSON/坏结构。"""
    data = agent.safe_json(raw_text)
    if not isinstance(data, dict):
        return None
    return rolecard_memory.clean_extraction(data, card, user_blob, assistant_blob)


def _extract_a(sid: str, lines: list[str], user_blob: str, current_len: int) -> None:
    out = agent.call_llm([{"role": "system", "content": A_SYS},
                          {"role": "user", "content": "\n".join(lines)}],
                         temperature=0.0)
    if not out.get("ok"):
        episode_store.mark_try(sid, current_len)
        logger.warning("memory_extract_failed mode=A error=%s", out.get("error"))
        return
    items = parse_a(str(out.get("text") or ""), user_blob)
    if items is None:
        episode_store.mark_try(sid, current_len)
        logger.warning("memory_extract_failed mode=A error=bad_json")
        return
    episode_store.append(sid, items, current_len)
    logger.info("memory_extract mode=A episodes=%d", len(items))


def _extract_b(card: dict, lines: list[str], user_blob: str,
               assistant_blob: str, current_len: int) -> None:
    old = rolecard_memory.snapshot(card)
    prompt = (f"角色：{card.get('name', '')}\n身份：{card.get('identity', '')}\n"
              f"设定：{card.get('setting', '')}\n"
              f"当前记忆：{json.dumps(old, ensure_ascii=False)}\n"
              f"最近对话：\n" + "\n".join(lines))
    out = agent.call_llm([{"role": "system", "content": B_SYS},
                          {"role": "user", "content": prompt}], temperature=0.0)
    if not out.get("ok"):
        rolecard_memory.mark_try(card, current_len)
        logger.warning("memory_extract_failed mode=B error=%s", out.get("error"))
        return
    clean = parse_b(str(out.get("text") or ""), card, user_blob, assistant_blob)
    if clean is None:
        rolecard_memory.mark_try(card, current_len)
        logger.warning("memory_extract_failed mode=B error=bad_json")
        return
    rolecard_memory.append_extraction(card, clean, current_len)
    logger.info("memory_extract mode=B episodes=%d", len(clean["episodes"]))


def maybe_run(is_rolecard: bool, card: dict | None, sid: str, facts: dict,
              history: list[dict], text: str, reply: str) -> None:
    """到点就抽一次；任何失败都不冒到界面，也不每轮重试。"""
    if _is_mock():
        return
    facts = facts or {}
    current_len = len(history or []) + 2
    last = max(_int(facts.get("_last_len")), _int(facts.get("_last_try_len")))
    if current_len < last:
        last = 0
    if current_len - last < TURN_EVERY:
        return
    lines, user_blob, assistant_blob = _blobs(history or [], text, reply)
    try:
        if is_rolecard and isinstance(card, dict):
            _extract_b(card, lines, user_blob, assistant_blob, current_len)
        elif not is_rolecard:
            _extract_a(sid, lines, user_blob, current_len)
    except Exception as exc:                     # 边界：抽取永不冒到界面
        logger.warning("memory_extract_error mode=%s error=%s",
                       "B" if is_rolecard else "A", type(exc).__name__)
        try:
            if is_rolecard and isinstance(card, dict):
                rolecard_memory.mark_try(card, current_len)
            elif not is_rolecard:
                episode_store.mark_try(sid, current_len)
        except Exception:
            pass
