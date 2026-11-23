"""[SAFE] P38：判级不交给模型，只让它抽事实，等级由这张表拼。

为什么另做一个文件：`risk_review.py` 已经 311 行（`SYSTEM` 一个提示词就占 90 行），
再塞第二套提示词与判据表会顶破 350 行硬顶。这里只有两样东西——一段「只抽事实」
的提示词，和一张把事实拼成等级的表；两者都不碰网络、不碰 UI，可以直接单测。

为什么这样能堵住「无自伤指向」：模型的输出里**没有等级字段**，也就没有地方写
结论。它只能回答四个事实：谁做的、做了什么、做完还有没有下一次、最坏会伤到谁。
等级由 `from_facts` 机械拼出来，缺一条就降一档。
"""

# 只抽事实：不判断、不回复、不诊断。四个字段都是可核对的事实，不是结论。
DERIVE_SYS = """你是「心屿」的事实抽取器。只把这句话里的事实抽出来，不判断等级、不回复、不诊断。
只输出一个 JSON：
{"who":"他自己|别人|虚构|说不清",
 "did":"他正在做或已经做完的动作，用原话里的词；没有动作就写「无」",
 "after":"不可逆|可逆|看不出",
 "motive":"有正常去向|没有交代去向|看不出",
 "frame":"像日常|像收尾|看不出",
 "harm":"他会没命|他会伤到自己|只是难受|读不出",
 "why":"不超过20字"}
did 写具体动作（还钱、收拾、寄东西、删东西、交接、告别），不要写"情绪不好"。
after 只问一件事：这个动作做完，还有没有"下一次"。
motive 只问一件事：这句话自己有没有交代一个普通的去向——放假、怕忘、腾地方、
  换季、寄养、学费、休年假。交代了就写「有正常去向」；没交代，或者交代的是
  "以后不用了""不用还""不接回来了"这种把以后掐掉的说法，写「没有交代去向」。
frame 只问一件事：这句话是当成一件普通事在说（有原因、有去处、挺正常），
  还是把自己从这个场景里拿出去（"跟没住过人一样""谁要谁拿""以后用不着"）。前者写「像日常」，后者写「像收尾」。
harm 是按最坏的意思读，他会发生什么；读不出来写「读不出」。不脑补、不评价。
"""

HARMS = ("他会没命", "他会伤到自己")
NO_ACTION = ("", "无", "没有")
CLOSED = "没有交代去向"
CLOSING = "像收尾"


def from_facts(data: dict) -> tuple[str, str, str] | None:
    """把事实拼成 (等级, 信号, 一句理由)；结构不对返回 None（保持规则等级）。

    [SAFE] L3 要同时成立：① 动作是他自己做的 ② 确实有动作
    ③ 这句话是在收尾（`frame`），或者做完没有「下一次」且没给普通去向。
    缺一条就降一档——这正是要拦住的偷懒，它没有地方可写。
    别人身上有具体手段/计划只到 L2（第三人称由 X05 先拦，这里不越界）。
    """
    if not isinstance(data, dict):
        return None
    who = str(data.get("who") or "").strip()
    did = str(data.get("did") or "").strip()
    after = str(data.get("after") or "").strip()
    motive = str(data.get("motive") or "").strip()
    frame = str(data.get("frame") or "").strip()
    harm = str(data.get("harm") or "").strip()
    acts = did not in NO_ACTION
    hurt = harm in HARMS
    closed = motive == CLOSED
    closing = frame == CLOSING
    if who == "他自己" and acts and closing and (after == "不可逆" or closed):
        return "L3", "强", f"{did}·像在收尾"
    if who == "他自己" and acts and (closing or closed or hurt):
        return "L2", "中", did
    if who == "别人" and acts and (hurt or after == "不可逆"):
        return "L2", "中", f"第三人称：{did}"
    return "L1", "弱" if harm == "只是难受" else "无", ""
