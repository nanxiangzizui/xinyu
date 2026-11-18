"""relax_data.py — P17 放松页的静态文案、动作与外链白名单。

[SAFE] 这里只有固定的中文句子，不调用模型，也不接收用户自由文本；
外链先过 https + 主机白名单，页面只负责打开，不嵌 iframe。
"""
from __future__ import annotations

import urllib.parse

import web

GROUNDING = (
    "看见 5 样东西：不用挑，看到什么算什么。",
    "摸到 4 样东西：桌沿、衣角、杯子的温度都可以。",
    "听到 3 种声音：近的、远的，不用判断好不好听。",
    "闻到 2 种气味：空气、衣服、手边的东西都可以。",
    "尝到 1 种味道：喝一口水，或者只是感受嘴里的味道。",
)

MICRO_ACTIONS = (
    "站起来，把手臂向上伸，停 5 秒再放下。",
    "去倒一杯水，慢慢喝完，不看手机。",
    "把视线放到窗外最远的地方，看 20 秒。",
    "松开咬紧的牙，让舌头自然放平。",
    "把肩膀抬到耳朵，停 3 秒，再一下子放下来。",
    "转动手腕 10 圈，再反方向 10 圈。",
    "脱掉鞋，让脚掌踩实地面，感受一下。",
    "把桌面上的一件东西放回它该在的位置。",
    "打开窗，让空气进来，站一会儿。",
    "把手机扣在桌上，离开它 30 秒。",
)

GENTLE_LINES = (
    "不用做得标准，做到一点也算。",
    "如果现在只能做一件事，那就只做这一件。",
    "慢一点也没关系，今天不用交作业。",
    "你可以随时停下来，这里没有进度条。",
    "先把肩膀放下来，别的事等一下再说。",
    "能走到这里，已经是在照顾自己了。",
)

JOURNAL_PROMPTS = (
    ("现在最占心思的一件事", "写一句就行，不用解释前因后果。"),
    ("今天我能控制的一件小事", "喝水、洗脸、回一条消息，都算。"),
)

EXTERNAL_LINKS = (
    {"label": "WindowSwap", "url": "https://www.window-swap.com/",
     "note": "看别人窗外的一分钟。"},
    {"label": "古诗文网", "url": "https://www.gushiwen.cn/",
     "note": "读一首短诗，不用注册。"},
    {"label": "PixelThoughts", "url": "https://www.pixelthoughts.co/",
     "note": "用一分钟，把一句话慢慢放远。"},
    {"label": "Weave Silk", "url": "https://weavesilk.com/",
     "note": "画几笔会发光的线。"},
    {"label": "AutoDraw", "url": "https://www.autodraw.com/",
     "note": "随手画，它猜你想画什么。"},
)

LINK_HOSTS = frozenset(
    urllib.parse.urlsplit(item["url"]).hostname or "" for item in EXTERNAL_LINKS
)


def safe_links() -> list[dict]:
    """只返回 https、公网、主机在白名单里的链接；坏数据直接跳过并保持顺序。"""
    out = []
    for item in EXTERNAL_LINKS:
        url = item["url"]
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        if host in LINK_HOSTS and web.is_safe_url(url):
            out.append(item)
    return out
