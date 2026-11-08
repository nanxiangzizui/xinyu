# -*- coding: utf-8 -*-
"""生成报告用架构图（Pillow，不引第三方绘图依赖）。"""
import pathlib
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "report-arch.png"

W, H = 1800, 780
BG = "#FFFDF9"
BLUE_FILL, BLUE_LINE = "#EAF2FB", "#5B8FC9"
RED_FILL, RED_LINE = "#FDECEA", "#C94F4A"
INK, MUTED, ARROW = "#243044", "#6B7280", "#8A94A6"

FONT_B = "C:/Windows/Fonts/msyhbd.ttc"
FONT_R = "C:/Windows/Fonts/msyh.ttc"

def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

d.text((60, 36), "心屿 MindIsle · 一次对话的数据流与否决回路", font=font(34, True), fill=INK)
d.text((60, 88), "每个方框是一个函数边界；红色支路意味着模型被完全绕过", font=font(21), fill=MUTED)

boxes = [
    ("用户输入", "一句话，允许情绪化"),
    ("规则层", "20 条规则 + 小句豁免"),
    ("聚合与分级", "窗口 5 轮 / 只升不降"),
    ("角色状态机", "listener / guide / crisis"),
    ("生成", "DeepSeek，温度 0.7"),
    ("守卫", "复核 0.2 / 重写 0.5 / 兜底"),
    ("输出", "回复 + 资源卡 + 日志"),
]
x0, y0, bw, bh, gap = 50, 200, 215, 118, 33
centers = []
for i, (title, sub) in enumerate(boxes):
    x = x0 + i * (bw + gap)
    d.rounded_rectangle([x, y0, x + bw, y0 + bh], radius=14, fill=BLUE_FILL, outline=BLUE_LINE, width=3)
    d.text((x + bw / 2, y0 + 30), title, font=font(25, True), fill=INK, anchor="mm")
    d.text((x + bw / 2, y0 + 76), sub, font=font(17), fill=MUTED, anchor="mm")
    centers.append((x + bw / 2, x + bw))
    if i:
        px = x0 + i * (bw + gap) - gap
        d.line([px + 4, y0 + bh / 2, x - 10, y0 + bh / 2], fill=ARROW, width=3)
        d.polygon([(x - 4, y0 + bh / 2), (x - 16, y0 + bh / 2 - 8), (x - 16, y0 + bh / 2 + 8)], fill=ARROW)

# 红色支路：L3 / 聚合升级 -> 固定模板 + 资源卡（跳过模型）
rx0, ry0, rx1, ry1 = 298, 430, 1505, 552
d.rounded_rectangle([rx0, ry0, rx1, ry1], radius=14, fill=RED_FILL, outline=RED_LINE, width=3)
d.text(((rx0 + rx1) / 2, ry0 + 38), "L3 或聚合升级 → CRISIS_REPLY（125 字）+ 3 张资源卡：不调用模型，断网可用",
       font=font(24, True), fill=INK, anchor="mm")
d.text(((rx0 + rx1) / 2, ry0 + 84), "短路由 app.py 在生成之前完成；同一条路径也承担风险地板与冷却",
       font=font(19), fill=MUTED, anchor="mm")
# 从规则层、聚合分级向下进入红框
for cx in (centers[1][0], centers[2][0]):
    d.line([cx, y0 + bh + 6, cx, ry0 - 10], fill=ARROW, width=3)
    d.polygon([(cx, ry0 - 2), (cx - 8, ry0 - 15), (cx + 8, ry0 - 15)], fill=ARROW)
# 红框向右再向上进入输出
d.line([rx1 + 6, ry0 + 61, 1645, ry0 + 61], fill=ARROW, width=3)
d.line([1645, ry0 + 61, 1645, y0 + bh + 8], fill=ARROW, width=3)
d.polygon([(1645, y0 + bh + 2), (1637, y0 + bh + 16), (1653, y0 + bh + 16)], fill=ARROW)

d.text((60, 640), "模型负责：生成 · 判别（只给意见）· 改写 · 压缩摘要", font=font(22, True), fill="#2F5D8A")
d.text((60, 682), "代码负责：规则 · 豁免 · 分级 · 路由 · 否决 · 日志", font=font(22, True), fill="#A6413C")
d.text((60, 730), "一句话：模型负责说人话，代码负责守边界。", font=font(24, True), fill=INK)

img.save(OUT, quality=95)
print("saved", OUT, img.size)
