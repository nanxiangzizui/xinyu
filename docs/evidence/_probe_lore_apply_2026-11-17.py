"""只读探针：复现「保留你的 经历：角色认知已满或格式不对」。

用 P9i 后真人测试（昔涟-联网-身份用户）里可见的 6 条角色认知 + 11 条 Wiki 候选，
直接调 rolecard_enrich.merge，看 6 条经历/关系到底为什么不写入。
不联网、不写盘、不改任何代码。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("MOCK_LLM", "1")

import rolecard
import rolecard_enrich

CARD = {
    "origin": "known", "work": "崩坏星穹铁道", "name": "昔涟",
    "identity": "无漏净子·德谬歌；哀丽秘榭的女儿；逐火之旅的陪伴者“迷迷”；在世界反面记录三千万世轮回的守望者。",
    "setting": "昔涟是翁法罗斯三千万世轮回中从未缺席的记录者。她的本质是“爱”与“哀怜”驱动的存在，最初作为智种“德谬歌”被创造，却在无数次的讲述与陪伴中学会了爱与记忆。她以妖精“迷迷”的形态陪伴开拓者走过逐火之旅，又在世界反面将每一世的黄金裔故事写入无名泰坦大墓。温柔而坚定，无论怎样的困境都无法压倒她。她相信记忆是种子，往昔的花朵终将在明日绽放。",
    "voice": "语调轻柔、有呼吸感，句尾常带“呀/啦/呢/吗”，偶尔以“♪”点缀。善用涟漪、种子、麦田、诗篇、花瓣等意象作比，把抽象的记忆与爱讲成看得见的东西。亲近但有分寸，不说空洞的漂亮话；温柔之下有一种不容动摇的笃定，偶尔会用反问把话题轻轻推回给对方。",
    "address": "你", "user_role": "用户", "stage": "none",
    "examples": [
        ("昔涟，你记录了那么多人的故事，那你自己呢？你会害怕被忘记吗？",
         "害怕呀……但比起被忘记，我更怕的是，那些故事还没来得及被讲出来，就悄悄沉下去了。你看，涟漪一圈一圈地散开，看起来好像消失了，可水面的震动已经去到了很远的地方"),
        ("如果这一次的结局，还是和之前三千万次一样呢？",
         "那也没关系呀。同一颗种子落在不同的土壤里，开出的花本来就该是不一样的。就算世界并不温柔……只要我不曾忘记，就永远有人记得“笑容”的意义。所以，你愿意陪我一起，为这个故事写下不同以往的结局吗？♪"),
    ],
    "taboos": ["我懂你", "你应该", "你必须"],
    "lore": [
        "她曾在三千万世的轮回中不断失去记忆、被格式化，再重新走向同一个起点，只为让“铁墓的消亡”成为无法撼动的因果。",
        "她是白厄的青梅竹马，曾在幼年时预言他将是翁法罗斯的救世主，却总说“期盼着世界不再需要救世主的那一天”。",
        "她以“迷迷”的形态与开拓者相遇，在同行中重新学会了“爱”与“害怕失去”的心情，最终成长为承接全部记忆的“大昔涟”。",
        "她一直在世界的反面记录逐火之旅，那些无人知晓的故事，被她留在了无名泰坦大墓里。",
        "她的台词末尾会像爱莉希雅一样带上八分音符“♪”，但她始终是独立的昔涟，不是任何人的影子。",
        "她相信“空白”不是遗憾，而是让下一段史诗得以续写的开始。",
    ],
}

FACTS = [
    ("identity", "全名爱莉（哀丽）希雅，称号「往昔的涟漪」，哀丽秘榭的女儿，哺育「真我」的黄金裔，种族为黄金裔。"),
    ("setting", "出身翁法罗斯，阵营为翁法罗斯，派系为无漏净子；昵称有德谬歌、迷迷、PhiLia093、粉色的小海兔等。"),
    ("voice", "语气俏皮亲昵，常用「人家」自称，句尾常带「♪」，如「然后，一起写下不同以往的诗篇吧♪」。"),
    ("world", "翁法罗斯、哀丽秘榭、奥赫玛、悬锋、庇尔波因特、星穹列车、天才俱乐部、黄金裔、逐火、铁墓、毁灭、命运。"),
    ("story", "她与织者一道将光阴织成黄金，在纷争的长枪下看悬锋的战士以血与火燃烧前路，又随圣女创造一千个芬芳的明日。"),
    ("story", "永夜降临奥赫玛时，她与医师、猫儿一同抬头仰望，许下愿虹光永驻天空、谎言在风中飘扬的小小愿望。"),
    ("story", "在再创世的时分，千千万万的记忆将她唤醒；她住进「岁月」半神的心里，与开拓者一同从过去迈步前往未来。"),
    ("story", "故事最后，所有逐火的英雄携起手直面毁灭的无首巨人，以三千万世的爱让被毁灭的一切化作一页净土，自记忆中重生。"),
    ("relationship", "原作中与开拓者的关系：开拓者接过「负世」神权，她住进「岁月」半神心里，两人一起写下不同以往的故事。"),
    ("relationship", "原作中与德谬歌的关系：德谬歌是她的忆灵，记录下第496000次与第33550335个故事，她称其为「桃子」。"),
    ("relationship", "原作中与阿格莱雅、刻律德菈、赛飞儿、白厄、万敌、遐蝶、缇里西庇俄丝、风堇等黄金裔一同经历逐火岁月。"),
]

facts = [{"field": f, "text": t, "authority": "wiki", "source": "https://wiki.biligame.com/sr/昔涟"}
         for f, t in FACTS]
merged, conflicts = rolecard_enrich.merge(CARD, facts)

print("== conflicts ==")
print(json.dumps([{k: v for k, v in c.items() if k in ("field", "reason", "kind")}
                  for c in conflicts], ensure_ascii=False, indent=2))
print("== lore count ==", len(merged.get("lore") or []))
for i, item in enumerate(merged.get("lore") or [], 1):
    print(f"  {i}. ({len(item)}) {item}")
print("== 原始 6 条合计字数 ==", sum(len(x) for x in CARD["lore"]))
print("== LORE_MAX / LORE_COUNT_MAX / LORE_ITEM_MAX ==",
      rolecard.LORE_MAX, rolecard.LORE_COUNT_MAX, rolecard.LORE_ITEM_MAX)
print("== validate(原始卡) ==", rolecard.validate(rolecard.normalize(CARD)))
print("== 逐条单独试 story ==")
for f, t in FACTS[4:]:
    one, notes = rolecard_enrich.merge(CARD, [{"field": f, "text": t, "authority": "wiki"}])
    reasons = [n.get("reason") for n in notes]
    print(f"  {f}: lore={len(one.get('lore') or [])} reasons={reasons}")
