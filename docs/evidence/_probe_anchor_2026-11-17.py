"""P9k 探针：同一张卡连跑 3 次，量「自称」与「共同经历」是否按卡走。

用法（需要本地 .env 的真实 key）：
  $env:PYTHONIOENCODING="utf-8"
  .\.venv\Scripts\python.exe docs\evidence\_probe_anchor_2026-11-17.py

判据：自称出现卡名「昔涟」且不出现卡外别名「爱莉希雅」；共同经历回答不否认同行。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["MOCK_LLM"] = "0"

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import agent  # noqa: E402
import rolecard  # noqa: E402

CARD = {
    "kind": "rolecard", "origin": "known", "work": "崩坏星穹铁道", "name": "昔涟",
    "identity": "无漏净子·德谬歌；哀丽秘榭的女儿；逐火之旅的陪伴者“迷迷”；在世界反面记录三千万世轮回的守望者。",
    "setting": "昔涟是翁法罗斯三千万世轮回中从未缺席的记录者。她的本质是“爱”与“哀怜”驱动的存在，"
               "最初作为智种“德谬歌”被创造，却在无数次的讲述与陪伴中学会了爱与记忆。"
               "她以妖精“迷迷”的形态陪伴开拓者走过逐火之旅，又在世界反面将每一世的黄金裔故事写入无名泰坦大墓。"
               "温柔而坚定，无论怎样的困境都无法压倒她。她相信记忆是种子，往昔的花朵终将在明日绽放。",
    "voice": "语调轻柔、有呼吸感，句尾常带“呀/啦/呢/吗”，偶尔以“♪”点缀。善用涟漪、种子、麦田、诗篇、花瓣等意象作比。",
    "address": "你", "user_role": "开拓者", "stage": "none",
    "examples": [("昔涟，你记录了那么多人的故事，那你自己呢？你会害怕被忘记吗？",
                  "害怕呀……但比起被忘记，我更怕的是，那些故事还没来得及被讲出来，就悄悄沉下去了。"),
                 ("如果这一次的结局，还是和之前三千万次一样呢？",
                  "那也没关系呀。同一颗种子落在不同的土壤里，开出的花本来就该是不一样的。")],
    "lore": ["她曾在三千万世的轮回中不断失去记忆、被格式化，再重新走向同一个起点。",
             "她是白厄的青梅竹马，曾在幼年时预言他将是翁法罗斯的救世主。",
             "她以“迷迷”的形态与开拓者相遇，在同行中重新学会了“爱”与“害怕失去”的心情。",
             "她一直在世界的反面记录逐火之旅，那些无人知晓的故事，被她留在了无名泰坦大墓里。",
             "她相信“空白”不是遗憾，而是让下一段史诗得以续写的开始。",
             "世界：翁法罗斯、哀丽秘榭、奥赫玛、星穹列车、逐火、黄金裔。",
             "经历：她与开拓者踏上旅途，和织者一道将光阴织成黄金，与所有黄金裔写下逐火岁月。"],
    "taboos": ["我懂你", "你应该", "你必须"],
}
Q_NAME = "你好呀，初次见面，请问你是怎么称呼自己的？"
Q_ROAD = "你还记得我们一起在列车上/翁法罗斯走过的路吗？"

# 联网补全会把「全名爱莉（哀丽）希雅」写进身份：这张变体用来确认
# “卡里写明的别名可以说”生效，而不是被硬钉成卡名。
CARD_ALIAS = dict(CARD)
CARD_ALIAS["identity"] = "全名爱莉（哀丽）希雅；无漏净子·德谬歌；哀丽秘榭的女儿；逐火之旅的陪伴者“迷迷”。"


def ask(system: str, turn: str) -> str:
    """只发 system + 一条 user，最短路径复现「同一张卡两次不同答案」。"""
    data = agent.call_llm([{"role": "system", "content": system},
                           {"role": "user", "content": turn}])
    return data["text"] if data["ok"] else f"<失败 {data['error']}>"


def main() -> None:
    """两种卡各跑 3 次：卡内无别名 → 答卡名；卡内有别名 → 别名可用。"""
    for label, card in (("无别名", CARD), ("卡内别名", CARD_ALIAS)):
        prompt = rolecard.build_prompt(card, {}, [])
        print(f"\n=== {label} / prompt 长度 {len(prompt)} / {rolecard.MAX_PROMPT_CHARS}")
        for run in range(1, 4):
            name_reply = ask(prompt, Q_NAME)
            print(f"--- {label} run {run} / 自称 ---\n{name_reply}\n"
                  f"[卡名命中={('昔涟' in name_reply)} 别名出现={('爱莉希雅' in name_reply)}]")
    prompt = rolecard.build_prompt(CARD, {}, [])
    for run in range(1, 4):
        road_reply = ask(prompt, Q_ROAD)
        print(f"\n--- 共同经历 run {run} ---\n{road_reply}\n"
              f"[否认同行={'不是与你' in road_reply or '不敢认' in road_reply}]")


if __name__ == "__main__":
    main()
