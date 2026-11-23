# -*- coding: utf-8 -*-
"""生成报告用的“一次对话里发生了什么”示意图（Pillow，纯画图，不引第三方依赖）。

口径：给普通读者看，不用英文节点名、不解释代码结构；只说清“谁先谁后、哪一步会跳走”。
画布按竖版设计（1200×1200），放进 A4 正文约 14.5cm 宽时字号仍有 9–11pt。
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "report-arch.png"

W, H = 1200, 1230
BG = "#FFFDF9"
STEP_FILL, STEP_LINE = "#F4F8FD", "#9DBAD9"
GEN_FILL, GEN_LINE = "#EAF7EF", "#4F9D69"
RED_FILL, RED_LINE = "#FDECEA", "#C94F4A"
GREEN_FILL, GREEN_LINE = "#EAF7EF", "#4F9D69"
INK, MUTED, ACC = "#243044", "#6B7280", "#B4552A"

FONT_B = "C:/Windows/Fonts/msyhbd.ttc"
FONT_R = "C:/Windows/Fonts/msyh.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


def row(d, y, no, title, desc, fill, line, h=96):
    d.rounded_rectangle([50, y, W - 50, y + h], radius=12, fill=fill, outline=line, width=3)
    d.ellipse([72, y + 24, 118, y + 70], fill=BG, outline=line, width=3)
    d.text((95, y + 48), str(no), font=font(26, True), fill=line, anchor="mm")
    d.text((140, y + 12), title, font=font(31, True), fill=INK)
    d.text((140, y + 56), desc, font=font(22), fill=MUTED)
    return y + h + 12


def callout(d, y, text1, text2, fill, line, h=84):
    d.rounded_rectangle([50, y, W - 50, y + h], radius=12, fill=fill, outline=line, width=3)
    d.text((78, y + 12), text1, font=font(25, True), fill=INK)
    d.text((78, y + 50), text2, font=font(21), fill=line if line == RED_LINE else "#2F6B46")
    return y + h + 12


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

d.text((50, 34), "心屿 MindIsle · 一次对话里发生了什么", font=font(40, True), fill=INK)
d.text((50, 92), "顺序是写死的：先看危险，再定身份，最后才让模型写。", font=font(24), fill=MUTED)

y = 150
y = row(d, y, 1, "先找危险", "20 条规则，在本地先跑一遍", STEP_FILL, STEP_LINE)
y = row(d, y, 2, "看最近五轮", "攒起来只抬一级，不判危险", STEP_FILL, STEP_LINE)
y = callout(d, y, "判成危险 → 直接跳走，不进入模型",
            "固定的一段话（126 字）+ 三个号码；不调用模型，断网也给得出", RED_FILL, RED_LINE)
y = row(d, y, 3, "定身份", "倾听 / 帮手，由代码定，危机优先", STEP_FILL, STEP_LINE)
y = row(d, y, 4, "拼说明书", "它是谁、这一轮该做什么、不许说什么", STEP_FILL, STEP_LINE)
y = row(d, y, 5, "让模型写", "唯一可能用到模型和网络的一步", GEN_FILL, GEN_LINE)
y = callout(d, y, "要查资料时：最多 3 步、2 次工具、每次 6 秒",
            "查回来的只当资料；出错就用一句固定的话顶上", GREEN_FILL, GREEN_LINE)
y = row(d, y, 6, "发之前再查", "诊断、承诺保密、句数，不通过就改写", STEP_FILL, STEP_LINE)
y = row(d, y, 7, "只记一点点", "八个标签 + 一句摘要，原文不存", STEP_FILL, STEP_LINE)

d.text((50, y + 6), "模型只做一件事：把这一句话写出来。", font=font(28, True), fill=INK)
d.text((50, y + 48), "其余全是代码：判断 · 顺序 · 字数 · 白名单 · 否决 · 记录", font=font(23, True), fill=ACC)

img.save(OUT, quality=95)
print("saved", OUT, img.size)

