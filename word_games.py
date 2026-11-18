"""word_games.py — P17 三个文字小游戏：脑筋急转弯 / 猜谜语 / 成语接龙。

全部本地词库、确定性逻辑：不调用 LLM、不联网、不计时、不排名、不打分。
用户输入只进 st.session_state，不写盘、不进日志、不进 messages / trace。
"""
from __future__ import annotations

import random
import re

import streamlit as st

# (题目, 答案)；答案是固定的，点“看答案”才显示。
BRAIN_TEASERS = (
    ("什么东西越洗越脏？", "水。"),
    ("什么布剪不断？", "瀑布。"),
    ("什么帽不能戴？", "螺帽。"),
    ("什么书在书店买不到？", "秘书。"),
    ("什么河没有水？", "银河。"),
    ("什么马不会跑？", "木马。"),
    ("什么牛不会吃草？", "蜗牛。"),
    ("什么虎不吃人？", "壁虎。"),
    ("什么鱼不能游泳？", "木鱼。"),
    ("什么鸟不会飞？", "鸵鸟。"),
    ("什么花不能摸？", "火花。"),
    ("什么门永远关不上？", "球门。"),
    ("什么球不能踢？", "眼球。"),
    ("什么蛋不能吃？", "脸蛋。"),
    ("什么瓜不能吃？", "傻瓜。"),
    ("什么床不能睡？", "河床。"),
    ("什么路不能走？", "电路。"),
    ("什么线不能缝？", "光线。"),
    ("什么伞不能挡雨？", "降落伞。"),
    ("什么车不能开？", "风车。"),
    ("什么海没有水？", "辞海。"),
    ("什么报不能订？", "海报。"),
    ("什么网不能上网？", "蜘蛛网。"),
    ("什么桥不能过？", "鹊桥。"),
    ("什么东西有五个头，人不觉得奇怪？", "手，五个指头。"),
    ("什么东西明明是你的，别人却用得比你多？", "名字。"),
    ("什么东西天气越热，爬得越高？", "温度计。"),
    ("什么东西打破了才能吃？", "鸡蛋。"),
    ("什么东西越分享越多？", "快乐。"),
    ("什么东西越擦越小？", "橡皮。"),
)

# (谜面, 谜底, 提示)
RIDDLES = (
    ("有头无颈，有眼无眉，有尾无毛。", "鱼。", "它生活在水里。"),
    ("有面没有口，有脚没有手，虽有四条腿，自己不会走。", "桌子。", "你写字时常用。"),
    ("有嘴没有牙，有脚没有手，天天站在桌上。", "茶壶。", "它装水。"),
    ("白天挂在天上，晚上不见。", "太阳。", "它带来光和热。"),
    ("有时像圆镜，有时像镰刀，晚上才出来。", "月亮。", "它会变圆变弯。"),
    ("千条线万条线，掉到水里看不见。", "雨。", "出门要带伞。"),
    ("白色花，无人栽，一夜北风遍地开。", "雪花。", "冬天才有。"),
    ("看不见，摸不着，没有颜色没味道，人人离不开。", "空气。", "你正在呼吸。"),
    ("越洗越脏的东西是什么？", "水。", "洗东西时用到它。"),
    ("有眼睛没有眉毛，有尾巴没有毛。", "鱼。", "和第一条有点像。"),
    ("一个娃娃，有嘴不说话，有脚不走路。", "布娃娃。", "它是玩具。"),
    ("圆圆一座房，里面住着白姑娘，打开房门看一看，白姑娘不见了。", "鸡蛋。", "早餐常见。"),
    ("身穿绿衣裳，肚里水汪汪，生的籽儿多，个个黑脸膛。", "西瓜。", "夏天解渴。"),
    ("弯弯像小船，黄黄像月牙，剥开白皮衣，露出黄娃娃。", "香蕉。", "猴子爱吃。"),
    ("红口袋，绿口袋，有人怕，有人爱。", "辣椒。", "味道很冲。"),
    ("一个东西，有头有尾，有脚有手，却不能走。", "床。", "你每天在上面睡觉。"),
    ("一物生来真奇怪，身穿三百多件衣，每天脱一件，年底剩张皮。", "日历。", "挂在墙上。"),
    ("小小一间房，只有一扇窗，唱歌又演戏，天天换花样。", "电视机。", "客厅里常见。"),
    ("有风不动无风动，不动无风动有风。", "扇子。", "夏天用它。"),
    ("一个老头，不跑不走，请他睡觉，他就摇头。", "不倒翁。", "推它也不倒。"),
    ("上不怕水，下不怕火，家家厨房，都有一个。", "锅。", "做饭用。"),
    ("两个小口袋，天天随身带，要是少一只，就把人笑坏。", "袜子。", "穿在脚上。"),
    ("看看没有，摸摸倒有，像冰不化，像水不流。", "玻璃。", "窗户上有。"),
    ("一物三个口，你有我也有，有口不会说，有脚不会走。", "裤子。", "穿在身上。"),
    ("一位老公公，面孔红彤彤，晴天早早起，按时来上工。", "太阳。", "和第四条的谜底一样。"),
    ("有时落在山腰，有时挂在树梢，有时像面圆镜，有时像把镰刀。", "月亮。", "和第五条是同一个。"),
    ("生在山里，死在锅里，藏在瓶里，活在杯里。", "茶叶。", "泡水喝。"),
    ("一物生得巧，地位比人高，戴上它，看得远。", "帽子。", "头上戴的。"),
    ("有脚不会走，有嘴不会叫，有眼不会看，有耳不会听。", "茶壶。", "和第三条同一个。"),
    ("一个东西，白天工作，晚上休息，你走它也走，你停它也停。", "影子。", "有光才有。"),
)

_IDIOM_TEXTS = (
    "一心一意\n画蛇添足\n守株待兔\n亡羊补牢\n井底之蛙\n狐假虎威\n"
    "对牛弹琴\n自相矛盾\n三人成虎\n四海为家\n五湖四海\n六神无主\n"
    "七上八下\n八仙过海\n九牛一毛\n十全十美\n百发百中\n千军万马\n"
    "万紫千红\n安居乐业\n春暖花开\n鸟语花香\n山清水秀\n风和日丽\n"
    "心平气和\n笑口常开\n一帆风顺\n万事如意\n心想事成\n前程似锦\n"
    "步步高升\n马到成功\n水到渠成\n顺其自然\n随遇而安\n知足常乐\n"
    "助人为乐\n与人为善\n诚实守信\n言而有信\n一诺千金\n精打细算\n"
    "勤俭持家\n井井有条\n有条不紊\n一丝不苟\n全神贯注\n专心致志\n"
    "聚精会神\n心无旁骛\n脚踏实地\n实事求是\n持之以恒\n坚持不懈\n"
    "锲而不舍\n水滴石穿\n铁杵成针\n熟能生巧\n温故知新\n学而不厌\n"
    "不耻下问\n举一反三\n触类旁通\n融会贯通\n博览群书\n学以致用\n"
    "知行合一\n明辨是非\n三思而行\n从容不迫\n不慌不忙\n镇定自若\n"
    "泰然处之\n随机应变\n通情达理\n善解人意\n将心比心\n推己及人\n"
    "宽以待人\n海纳百川\n有容乃大\n虚怀若谷\n谦虚谨慎\n不骄不躁\n"
    "戒骄戒躁\n见贤思齐\n知错能改\n改过自新\n迷途知返\n未雨绸缪\n"
    "防患未然\n有备无患\n居安思危\n饮水思源\n知恩图报\n雪中送炭\n"
    "锦上添花\n乐于助人\n成人之美\n拾金不昧\n见义勇为\n尊老爱幼\n"
    "和睦相处\n团结友爱\n同心协力\n齐心协力\n众志成城\n同舟共济\n"
    "风雨同舟\n守望相助\n相敬如宾\n举案齐眉\n白头偕老\n天长地久\n"
    "花好月圆\n喜气洋洋\n欢天喜地\n兴高采烈\n眉开眼笑\n心花怒放"
).split()

# 只收首字/尾字；声调不计，ü 写 v。多音字按成语里的读法。
_PINYIN_PAIRS = """
一:yi 七:qi 万:wan 三:san 下:xia 不:bu 与:yu 专:zhuan 业:ye 中:zhong
为:wei 主:zhu 丽:li 举:ju 久:jiu 之:zhi 乐:le 九:jiu 书:shu 五:wu
井:jing 亡:wang 人:ren 从:cong 众:zhong 信:xin 兔:tu 全:quan 八:ba
六:liu 兴:xing 前:qian 力:li 功:gong 助:zhu 勤:qin 十:shi 千:qian
升:sheng 博:bo 危:wei 厌:yan 变:bian 吉:ji 同:tong 和:he 善:shan
喜:xi 四:si 团:tuan 圆:yuan 地:di 坚:jian 城:cheng 处:chu 大:da
天:tian 威:wei 学:xue 守:shou 安:an 实:shi 家:jia 宽:kuan 宾:bin
对:dui 将:jiang 尊:zun 居:ju 山:shan 岁:sui 川:chuan 巧:qiao 平:ping
幼:you 开:kai 归:gui 得:de 心:xin 志:zhi 忙:mang 恒:heng 悠:you
患:huan 意:yi 慎:shen 懈:xie 成:cheng 戒:jie 报:bao 拾:shi 持:chi
推:tui 改:gai 放:fang 新:xin 明:ming 春:chun 昧:mei 是:shi 有:you
未:wei 条:tiao 欢:huan 步:bu 毛:mao 水:shui 注:zhu 泰:tai 洋:yang
济:ji 海:hai 温:wen 源:yuan 满:man 炭:tan 烈:lie 然:ran 熟:shu
爱:ai 牢:lao 狐:hu 理:li 琴:qin 用:yong 画:hua 白:bai 百:bai 皆:jie
相:xiang 盾:dun 眉:mei 知:zhi 神:shen 秀:xiu 穿:chuan 笑:xiao 算:suan
精:jing 紊:wen 红:hong 缪:mou 美:mei 老:lao 聚:ju 脚:jiao 自:zi
舍:she 舟:zhou 花:hua 苟:gou 若:ruo 虎:hu 虚:xu 蛙:wa 融:rong
行:xing 见:jian 触:chu 言:yan 诚:cheng 谦:qian 谷:gu 足:zu 躁:zao
返:fan 迫:po 迷:mi 通:tong 金:jin 针:zhen 铁:tie 锦:jin 锲:qie
镇:zhen 问:wen 防:fang 随:sui 雪:xue 非:fei 顺:shun 风:feng 饮:yin
香:xiang 马:ma 骛:wu 鸟:niao 齐:qi
"""
CHAR_PINYIN = dict(pair.split(":", 1) for pair in _PINYIN_PAIRS.split())
IDIOMS = tuple((text, CHAR_PINYIN[text[0]], CHAR_PINYIN[text[-1]])
               for text in _IDIOM_TEXTS)
BY_TEXT = {text: (text, first, last) for text, first, last in IDIOMS}
STARTS: dict[str, list[tuple[str, str, str]]] = {}
for _item in IDIOMS:
    STARTS.setdefault(_item[1], []).append(_item)

_IDIOM_RE = re.compile(r"^[\u4e00-\u9fff]{4}$")


def _clean_idiom(text: str) -> str:
    """只留四个汉字；长度不对或含标点都不算。"""
    text = "".join(text.split())
    return text if _IDIOM_RE.fullmatch(text) else ""


def _next_idiom(current: tuple[str, str, str]) -> tuple[str, str, str] | None:
    """按上一个成语的尾音找候选；找不到就返回 None，由页面提示换开头。"""
    options = [item for item in STARTS.get(current[2], []) if item[0] != current[0]]
    return random.choice(options) if options else None


def _random_idiom() -> tuple[str, str, str]:
    return random.choice(IDIOMS)


def _render_reveal(items: tuple, prefix: str, hint: bool = False) -> None:
    """看答案 / 换一题；no input, no score。"""
    idx = st.session_state.setdefault(f"{prefix}_idx", 0)
    item = items[idx % len(items)]
    st.markdown(f"**{item[0]}**")
    if hint and st.button("看提示", key=f"{prefix}_hint"):
        st.session_state[f"{prefix}_hint_on"] = True
    if hint and st.session_state.get(f"{prefix}_hint_on"):
        st.caption(f"提示：{item[2]}")
    if st.button("看答案", key=f"{prefix}_show"):
        st.session_state[f"{prefix}_answer"] = True
    if st.session_state.get(f"{prefix}_answer"):
        st.success(f"答案：{item[1]}")
    if st.button("换一题", key=f"{prefix}_next"):
        st.session_state[f"{prefix}_idx"] = (idx + 1) % len(items)
        for key in (f"{prefix}_answer", f"{prefix}_hint_on"):
            st.session_state.pop(key, None)
        st.rerun()
    st.caption("不用答，看看就好。")


def _render_idiom() -> None:
    """按读音接龙：同字或同音都行，只收词库里的四字成语。"""
    current = st.session_state.get("idiom_current")
    if not isinstance(current, tuple) or len(current) != 3:
        current = _random_idiom()
        st.session_state["idiom_current"] = current
    st.markdown(f"### {current[0]}")
    st.caption(f"尾字读音：{current[2]}；接一个首字同音或同字的四字成语。")
    with st.form("idiom_form", clear_on_submit=True):
        text = st.text_input("接一个", key="idiom_input", max_chars=8,
                             placeholder="输入四个汉字")
        submitted = st.form_submit_button("接上")
    if submitted:
        cleaned = _clean_idiom(text)
        if not cleaned:
            st.session_state["idiom_msg"] = "要四个汉字，不要标点或空格。"
        elif cleaned not in BY_TEXT:
            st.session_state["idiom_msg"] = "这个词库里还没有；换一个试试。"
        elif BY_TEXT[cleaned][1] != current[2]:
            st.session_state["idiom_msg"] = (
                f"读音没接上：上一个尾字读 {current[2]}，"
                f"「{cleaned[0]}」读 {BY_TEXT[cleaned][1]}。")
        else:
            st.session_state["idiom_current"] = BY_TEXT[cleaned]
            st.session_state["idiom_msg"] = "接上了。"
            st.session_state["idiom_history"] = (
                (st.session_state.get("idiom_history") or []) + [current[0]])[-5:]
            st.rerun()
    if st.session_state.get("idiom_msg"):
        st.info(st.session_state["idiom_msg"])
    cols = st.columns(2)
    if cols[0].button("帮我接一个", key="idiom_help"):
        nxt = _next_idiom(st.session_state["idiom_current"])
        if nxt:
            st.session_state["idiom_current"] = nxt
            st.session_state["idiom_msg"] = f"接「{nxt[0]}」，可以继续。"
        else:
            st.session_state["idiom_msg"] = "这条路有点窄，换一个开头吧。"
        st.rerun()
    if cols[1].button("换一个开头", key="idiom_restart"):
        st.session_state["idiom_current"] = _random_idiom()
        st.session_state["idiom_msg"] = "换了一个开头。"
        st.rerun()
    history = st.session_state.get("idiom_history") or []
    if history:
        st.caption("刚才接过的：" + " → ".join(history))


def render(page: str) -> None:
    """三页共用入口；未知页不画东西。"""
    if page == "brain":
        st.subheader("脑筋急转弯")
        _render_reveal(BRAIN_TEASERS, "brain")
    elif page == "riddle":
        st.subheader("猜谜语")
        _render_reveal(RIDDLES, "riddle", hint=True)
    elif page == "idiom":
        st.subheader("成语接龙")
        _render_idiom()
