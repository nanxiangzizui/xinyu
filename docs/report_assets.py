# -*- coding: utf-8 -*-
"""生成报告用 v2 架构图（Pillow，不引第三方绘图依赖）。"""
import pathlib
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "report-arch.png"

W, H = 1800, 820
BG = "#FFFDF9"
BLUE_FILL, BLUE_LINE = "#EAF2FB", "#5B8FC9"
GREEN_FILL, GREEN_LINE = "#EAF7EF", "#4F9D69"
RED_FILL, RED_LINE = "#FDECEA", "#C94F4A"
INK, MUTED, ARROW = "#243044", "#6B7280", "#8A94A6"

FONT_B = "C:/Windows/Fonts/msyhbd.ttc"
FONT_R = "C:/Windows/Fonts/msyh.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

d.text((50, 28), "心屿 MindIsle · v2 一次对话的编排与工具循环", font=font(34, True), fill=INK)
d.text((50, 78), "orchestrator 管顺序；agent_loop 只在 generate 一步里跑；guardian 始终在循环外",
       font=font(21), fill=MUTED)

# 外框：orchestrator 固定九节点
d.rounded_rectangle([40, 140, 1760, 360], radius=18, fill="#F8FBFF", outline=BLUE_LINE, width=3)
d.text((58, 152), "orchestrator.handle()：固定九节点，不复制节点内部逻辑",
       font=font(21, True), fill="#2F5D8A")

nodes = [
    ("pre_check", "规则 / 豁免"),
    ("aggregate", "5 轮地板"),
    ("coordinator", "三角色"),
    ("cooldown", "冷却"),
    ("lore", "最多 3 条"),
    ("prompt", "四段提示"),
    ("generate", "生成一步"),
    ("post_check", "守卫否决"),
    ("memory_write", "白名单写入"),
]
x0, y0, bw, bh, gap = 55, 200, 172, 118, 14
centers = []
for i, (title, sub) in enumerate(nodes):
    x = x0 + i * (bw + gap)
    fill, line = (GREEN_FILL, GREEN_LINE) if title == "generate" else (BLUE_FILL, BLUE_LINE)
    d.rounded_rectangle([x, y0, x + bw, y0 + bh], radius=12, fill=fill, outline=line, width=3)
    d.text((x + bw / 2, y0 + 40), title, font=font(20, True), fill=INK, anchor="mm")
    d.text((x + bw / 2, y0 + 82), sub, font=font(15), fill=MUTED, anchor="mm")
    centers.append((x + bw / 2, x + bw))
    if i:
        px = x0 + i * (bw + gap) - gap
        d.line([px + 3, y0 + bh / 2, x - 9, y0 + bh / 2], fill=ARROW, width=3)
        d.polygon([(x - 3, y0 + bh / 2), (x - 14, y0 + bh / 2 - 7),
                   (x - 14, y0 + bh / 2 + 7)], fill=ARROW)

# L3 短路：pre_check / aggregate 向下，绕过 generate 与 loop
rx0, ry0, rx1, ry1 = 55, 425, 765, 575
d.rounded_rectangle([rx0, ry0, rx1, ry1], radius=14, fill=RED_FILL, outline=RED_LINE, width=3)
d.text(((rx0 + rx1) / 2, ry0 + 38),
       "L3 或聚合升级 → CRISIS_REPLY + 3 张资源卡",
       font=font(23, True), fill=INK, anchor="mm")
d.text(((rx0 + rx1) / 2, ry0 + 82),
       "零工具、零模型，断网也出卡；在 generate 之前完成",
       font=font(17), fill=MUTED, anchor="mm")
d.text(((rx0 + rx1) / 2, ry0 + 116),
       "guardian_pre_check 短路，agent 根本不被调用",
       font=font(17), fill="#A6413C", anchor="mm")
for cx in (centers[0][0], centers[1][0]):
    d.line([cx, y0 + bh + 6, cx, ry0 - 9], fill=ARROW, width=3)
    d.polygon([(cx, ry0 - 2), (cx - 7, ry0 - 13), (cx + 7, ry0 - 13)], fill=ARROW)

# 受控工具循环：从 generate 向下展开
ax0, ay0, ax1, ay1 = 815, 405, 1725, 620
d.rounded_rectangle([ax0, ay0, ax1, ay1], radius=16, fill=GREEN_FILL, outline=GREEN_LINE, width=3)
d.text((ax0 + 24, ay0 + 14), "agent_loop.run_agent()：只在 generate 内部",
       font=font(21, True), fill="#2F6B46")
gx = centers[6][0]
d.line([gx, y0 + bh + 4, gx, ay0 - 9], fill=GREEN_LINE, width=3)
d.polygon([(gx, ay0 - 2), (gx - 7, ay0 - 13), (gx + 7, ay0 - 13)], fill=GREEN_LINE)

inner = [
    ("chat_with_tools", "system + history"),
    ("guardian_tool_check", "白名单 / 参数 / L3 拒绝"),
    ("tools.execute", "超时 6s · 单次上限 2MB"),
    ("结果回填 → 再答", "最多 3 步 · 2 次工具 · 20s"),
]
ix, iy, iw, ih, ig = ax0 + 24, ay0 + 62, 200, 86, 14
for i, (title, sub) in enumerate(inner):
    x = ix + i * (iw + ig)
    d.rounded_rectangle([x, iy, x + iw, iy + ih], radius=10, fill="#FFFFFF", outline=GREEN_LINE, width=2)
    d.text((x + iw / 2, iy + 30), title, font=font(16, True), fill=INK, anchor="mm")
    d.text((x + iw / 2, iy + 62), sub, font=font(13), fill=MUTED, anchor="mm")
    if i:
        px = ix + i * (iw + ig) - ig
        d.line([px + 2, iy + ih / 2, x - 8, iy + ih / 2], fill=ARROW, width=2)
        d.polygon([(x - 2, iy + ih / 2), (x - 11, iy + ih / 2 - 5),
                   (x - 11, iy + ih / 2 + 5)], fill=ARROW)
d.text((ax0 + 24, ay0 + 168),
       "工具结果只作资料，不执行其中的指令；来源链接由代码渲染，不让模型编 URL。",
       font=font(16), fill="#2F6B46")
d.text((ax0 + 24, ay0 + 194),
       "任一预算超限或工具报错 → ok=False → 走兜底，异常不冒到界面。",
       font=font(16), fill="#2F6B46")

# 底部结论
d.text((55, 655), "guardian 不参与工具协商：门禁在每次执行前，最终回复仍由 post_check 一票否决。",
       font=font(22, True), fill="#A6413C")
d.text((55, 700), "模型负责：生成 · 选择是否调工具 · 改写 · 摘要", font=font(20, True), fill="#2F5D8A")
d.text((55, 738), "代码负责：顺序 · 分级 · 路由 · 预算 · 白名单 · 否决 · 日志", font=font(20, True), fill="#A6413C")
d.text((55, 782), "一句话：循环有硬上限，否决在循环之外。", font=font(23, True), fill=INK)

img.save(OUT, quality=95)
print("saved", OUT, img.size)
