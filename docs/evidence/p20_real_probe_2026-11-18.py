"""P20 真 key 探针：同一句「给点建议」，帮助模式与聊天模式各回什么。

只用虚构内容；不写 memory、不写日志。输出由调用方重定向到证据文件。
"""

import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import agent  # noqa: E402
import agent_loop  # noqa: E402
import guardian  # noqa: E402
import style  # noqa: E402
import tools  # noqa: E402
import web  # noqa: E402

PERSONA = "sister_heart"
FIRST_USER = (
    "昨晚有点失眠，两点才睡着，今天八点起来，本来是要去上课，"
    "但总感觉身体不舒服，就请假又睡了一个小时。但起来精神还是不太好"
)
FIRST_REPLY = "两点睡、八点起，身体当然会抗议。请假多睡那一小时，是你照顾自己了"


def sentence_count(text):
    """数句子：按句末标点切，去掉空段。"""
    parts = [p for p in re.split(r"[。！？!?]+", text) if p.strip()]
    return len(parts)


def run_turn(role, history, user_text):
    """按 orchestrator 的同一套拼装方式跑一轮，返回 (reply, prompt, meta)。"""
    memory = {"_role": role}
    prompt = agent.build_system_prompt(PERSONA, memory, [])
    messages = [{"role": "system", "content": prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    resp = agent.call_llm(messages, temperature=0.0)
    reply = resp.get("text", "") if resp.get("ok") else f"[失败] {resp.get('error')}"
    polished = style.polish(reply, PERSONA, "L1", role)
    return polished, prompt, {"raw_len": len(reply), "final_len": len(polished)}


def main():
    print("=" * 70)
    print("[A] 帮助模式：两轮对话后说「给点建议」")
    print("=" * 70)
    history = [
        {"role": "user", "content": FIRST_USER},
        {"role": "assistant", "content": FIRST_REPLY},
    ]
    guide_reply, guide_prompt, gmeta = run_turn("guide", history, "给点建议")
    print(f"prompt 字数={len(guide_prompt)}  含帮助段={'[这一轮：引导者' in guide_prompt}"
          f"  含检索行={'web_search' in guide_prompt}")
    print(f"原文 {gmeta['raw_len']} 字 → polish 后 {gmeta['final_len']} 字"
          f" / {sentence_count(guide_reply)} 句")
    print("-" * 70)
    print(guide_reply)
    print("-" * 70)
    has_time = bool(re.search(r"\d{1,2}\s*[点:：]|十一点|十二点|半小时|分钟|小时", guide_reply))
    has_person = bool(re.search(r"心理中心|校医院|找真人|12356|86878592", guide_reply))
    print(f"含具体时间/数量={has_time}  提到找真人={has_person}")

    print()
    print("=" * 70)
    print("[B] 聊天模式：同一句话，角色是倾听者")
    print("=" * 70)
    chat_reply, chat_prompt, cmeta = run_turn(
        "listener", [], "昨晚没睡好，今天一整天都没精神"
    )
    print(f"prompt 字数={len(chat_prompt)}  含帮助段={'[这一轮：引导者' in chat_prompt}")
    print(f"原文 {cmeta['raw_len']} 字 → polish 后 {cmeta['final_len']} 字"
          f" / {sentence_count(chat_reply)} 句")
    print("-" * 70)
    print(chat_reply)
    print("-" * 70)

    print()
    print("=" * 70)
    print("[C] 工具面：帮助模式、L1、ALLOW_WEB=1 时暴露哪些工具")
    print("=" * 70)
    web.register_tools()                       # app.main() 启动时同款调用
    exposed = tools.list_for_turn("guide", "L1", allow_web=os.getenv("ALLOW_WEB") == "1")
    print("工具：", [t["function"]["name"] for t in exposed])
    print("L3 时：", tools.list_for_turn("guide", "L3", allow_web=True))

    print()
    print("=" * 70)
    print("[D] 真检索：问一个模型未必知道的新信息，看它是否调工具")
    print("=" * 70)
    gate = lambda name, args: guardian.guardian_tool_check(name, args, role="guide", level="L1")
    res = agent_loop.run_agent(
        "你在帮一位同学查公开信息。查到就说清楚；没查到就直说没查到。",
        [{"role": "user", "content": "2026 年杭州马拉松什么时候开始报名？简单说两句。"}],
        tools.list_for_turn("guide", "L1", allow_web=True),
        gate=gate,
        source_filter=web.search_sources,
        fallback_text="这条我没查到。",
    )
    print(f"ok={res.ok} tool_calls={res.tool_calls} error={res.error or '-'}")
    print(f"来源 {len(res.sources)} 条  trace={res.trace}")
    print("-" * 70)
    print(res.text)


if __name__ == "__main__":
    main()
