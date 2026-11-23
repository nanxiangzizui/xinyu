# -*- coding: utf-8 -*-
"""构建 docs/02_项目方案.pptx（python-pptx，仅用于生成材料）。

17 页，口径与《01 项目文档》一致：普通大学生视角、少术语、重点写“怎么和 AI 一起做完”。
所有数字（828 条检查 / 8 个版本 / 32 个时刻 / 四指标）都能在 docs/evidence 下找到出处。
"""
import pathlib

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "02_项目方案.pptx"
SHOT = ROOT / "docs" / "evidence" / "P47-materials-2026-11-23"

BG = RGBColor(0xFF, 0xFD, 0xF9)
INK = RGBColor(0x3D, 0x32, 0x30)
MUTED = RGBColor(0x8A, 0x7F, 0x78)
ACC = RGBColor(0xFF, 0x9E, 0x6B)
ACC_D = RGBColor(0xB4, 0x55, 0x2A)
LINE = RGBColor(0xF0, 0xD8, 0xC8)
SOFT = RGBColor(0xFD, 0xF2, 0xEA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "微软雅黑"

BIG, MID, BODY = 40, 28, 20
LEFT = 0.85
WIDTH = 11.6
TOTAL = 17


def _font(run, size, color, bold=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT
    rpr = run._r.get_or_add_rPr()
    ea = rpr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}ea")
    if ea is None:
        ea = rpr.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}ea", {})
        rpr.append(ea)
    ea.set("typeface", FONT)


def textbox(slide, x, y, w, h, size=BODY, color=INK, bold=False,
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = ""
    _font(run, size, color, bold)
    return tf


def line(tf, text, size=BODY, color=INK, bold=False, align=PP_ALIGN.LEFT,
         space_before=0, space_after=6, first=False, spacing=1.15):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.line_spacing = spacing
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    run = p.add_run()
    run.text = text
    _font(run, size, color, bold)
    return p


def bullets(slide, x, y, w, h, items, size=BODY, gap=10, color=INK):
    tf = textbox(slide, x, y, w, h)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.3
        pPr = p._pPr if p._pPr is not None else p._p.get_or_add_pPr()
        pPr.set("marL", str(int(Inches(0.32))))
        pPr.set("indent", str(int(-Inches(0.32))))
        head = p.add_run()
        head.text = "· "
        _font(head, size, ACC_D, True)
        run = p.add_run()
        run.text = item
        _font(run, size, color)


def new_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = BG
    return slide


def head(slide, no, name, title):
    tf = textbox(slide, LEFT, 0.52, WIDTH, 0.4, 14, MUTED, True)
    line(tf, f"{no:02d} / {TOTAL} · {name}", 14, MUTED, True, first=True)
    tf = textbox(slide, LEFT, 0.95, WIDTH, 0.95, BIG, INK, True)
    line(tf, title, BIG, INK, True, first=True, spacing=1.05)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(LEFT), Inches(1.92),
                                 Inches(1.15), Inches(0.07))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACC
    bar.line.fill.background()
    foot = textbox(slide, LEFT, 6.92, WIDTH, 0.3, 11, MUTED)
    line(foot, "心屿 MindIsle · 赛题一（AI 辅助开发·创意产品原型）", 11, MUTED, first=True)
    page = textbox(slide, 11.4, 6.92, 1.1, 0.3, 11, MUTED, align=PP_ALIGN.RIGHT)
    line(page, f"{no:02d}", 11, MUTED, align=PP_ALIGN.RIGHT, first=True)


def pic(slide, path, x, y, w):
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w))


def table(slide, headers, rows, x, y, w, col_w, size=13, head_h=0.42, row_h=0.44):
    shape = slide.shapes.add_table(len(rows) + 1, len(headers),
                                   Inches(x), Inches(y), Inches(w), Inches(head_h + row_h * len(rows)))
    tbl = shape.table
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Inches(cw)
    tbl.rows[0].height = Inches(head_h)
    for i in range(1, len(rows) + 1):
        tbl.rows[i].height = Inches(row_h)
    for j, text in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = SOFT
        cell.margin_left = Inches(0.08)
        cell.margin_right = Inches(0.06)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf = cell.text_frame
        tf.word_wrap = True
        line(tf, text, size, ACC_D, True, first=True, space_after=0)
    for i, row in enumerate(rows, start=1):
        for j, text in enumerate(row):
            cell = tbl.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if i % 2 else BG
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.06)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            line(tf, text, size, INK, first=True, space_after=0, spacing=1.02)
    return shape


def quote(slide, x, y, w, h, text, size=16):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                                 Inches(w), Inches(h))
    box.fill.solid()
    box.fill.fore_color.rgb = SOFT
    box.line.color.rgb = LINE
    box.line.width = Pt(0.75)
    box.adjustments[0] = 0.06
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.3)
    tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.2)
    tf.margin_bottom = Inches(0.2)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, ln in enumerate(text.split("\n")):
        line(tf, ln, size, INK, first=(i == 0), spacing=1.3)
    return box


# ---------------------------------------------------------------- 17 页


def s01_cover(prs):
    slide = new_slide(prs)
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.22))
    band.fill.solid()
    band.fill.fore_color.rgb = ACC
    band.line.fill.background()

    tf = textbox(slide, 1.1, 1.45, 9.0, 0.4, 18, ACC_D, True)
    line(tf, "赛题一（AI 辅助开发·创意产品原型） · 杭电第二届 AIGC 应用创新大赛", 18, ACC_D, True, first=True)

    tf = textbox(slide, 1.05, 2.05, 10.6, 1.6, 66, INK, True)
    line(tf, "心屿 MindIsle", 66, INK, True, first=True, spacing=1.0)

    tf = textbox(slide, 1.1, 3.45, 10.0, 0.7, 32, INK)
    line(tf, "一个不会害人的情绪陪伴工具", 32, INK, first=True)

    tf = textbox(slide, 1.1, 4.25, 10.6, 0.9, 18, MUTED)
    line(tf, "我们想做的不是“更聪明的 AI”，而是一个知道什么时候该停下来的工具。", 18, MUTED, first=True)

    quote(slide, 1.1, 5.25, 10.9, 1.05,
          "6 人小队 · v3.2 · 2026-11-23 · 828 条自动检查 · 76 次提交 · 8 个版本", 17)


def s02_who(prs):
    slide = new_slide(prs)
    head(slide, 2, "我们是谁", "六个学生，和一句凌晨一点的话")
    bullets(slide, LEFT, 2.25, 6.4, 3.6, [
        "我们是六个本科生，专业不同：计算机、数字媒体、汉语言、心理学选修。",
        "我们不是心理专业，也不打算冒充。我们就是这个产品的用户。",
        "项目开始那天，群里聊的不是技术，是一句很普通的话。",
    ], size=BODY, gap=18)
    quote(slide, 7.5, 2.35, 4.95, 2.6,
          "“凌晨一点，通讯录翻到底，\n想找个人说话，\n又觉得这件事不值得打扰别人。”", 17)
    tf = textbox(slide, 7.5, 5.15, 4.95, 1.2, 15, MUTED)
    line(tf, "后来发现，这不是某一个人的夜晚：室友在打游戏，家里在另一个城市，心理中心要预约。",
         15, MUTED, first=True, spacing=1.3)


def s03_problem(prs):
    slide = new_slide(prs)
    head(slide, 3, "我们要解决的问题", "不是“心理问题”，是“今晚过不去”")
    tf = textbox(slide, LEFT, 2.2, WIDTH, 0.6, 22, ACC_D, True)
    line(tf, "卡住人的那句话，其实不是“我病了”，是“还没到要去那儿的程度，但今晚确实过不去”。",
         22, ACC_D, True, first=True)
    rows = [
        ["学校不缺资源", "有心理中心、有 24 小时热线、有辅导员", "但都要先“开口”"],
        ["普通 AI 助手", "会继续陪你聊，越聊越深", "但不会停下来给号码"],
        ["网上的自助内容", "道理都对", "但半夜看不进去，也不知道先做哪一条"],
    ]
    table(slide, ["现在的选择", "它给了什么", "缺了什么"], rows,
          LEFT, 3.22, 11.6, [3.0, 5.2, 3.4], size=15, head_h=0.45, row_h=0.7)
    tf = textbox(slide, LEFT, 5.95, WIDTH, 0.9, 17, MUTED)
    line(tf, "所以我们不做“测评”，也不做“AI 医生”：先让人找到一件现在就能做的事，出事的时候先给一个号码。",
         17, MUTED, first=True, spacing=1.3)


def s04_users(prs):
    slide = new_slide(prs)
    head(slide, 4, "用户与场景", "三种人，三个晚上")
    tf = textbox(slide, LEFT, 2.2, 5.4, 0.4, 16, ACC_D, True)
    line(tf, "三种人", 16, ACC_D, True, first=True)
    bullets(slide, LEFT, 2.62, 5.4, 3.4, [
        "说不出口的人：明明难受，觉得“这算什么大事”。",
        "想找个地方待着的人：不要建议，也不想被分析。",
        "担心朋友的人：想帮，怕说错，也怕担责任。",
    ], size=17, gap=16)
    tf = textbox(slide, 6.9, 2.2, 5.6, 0.4, 16, ACC_D, True)
    line(tf, "三个晚上（都来自我们自己的经历）", 16, ACC_D, True, first=True)
    bullets(slide, 6.9, 2.62, 5.6, 3.4, [
        "22:40 熄灯后，脑子停不下来。",
        "出成绩那天，一门课挂了，不想被安慰“没事”。",
        "朋友发来一句“我不想活了”，你手在抖。",
    ], size=17, gap=16)
    tf = textbox(slide, LEFT, 5.95, WIDTH, 0.8, 15, MUTED)
    line(tf, "这三件事都没严重到“去看病”，但都足够让人过不好这一晚。这就是心屿想接住的那一段。",
         15, MUTED, first=True)


def s05_needs(prs):
    slide = new_slide(prs)
    head(slide, 5, "需求证据", "从“情绪”到 32 个时刻，做成 26 个入口")
    tf = textbox(slide, LEFT, 2.2, WIDTH, 0.5, 16, MUTED)
    line(tf, "按情绪分类不好用：人不会说“我焦虑”，他说“我室友半夜打游戏”“我论文一个字没写”。",
         16, MUTED, first=True)
    rows = [
        ["今晚就要", "5", "我现在很难受；睡不着；失恋；今晚想找个人说话", "一个号码 + 一段能发出去的话"],
        ["这几天", "8", "考砸了；被挂网暴；和家里；钱；室友；毕业；拖延；社恐", "先接住，再给两三条今天能做的"],
        ["跟别人有关", "7", "朋友出事；陪人去医院；跟辅导员说；请假 / 缓考", "三档说法 + 什么时候必须找人"],
        ["不想说话", "4", "呼吸；接地；写下来；环境音 / 看看别处", "不用组织语言，跟着做"],
        ["关于", "2", "它是什么；我的数据怎么删", "说清边界，教人怎么删"],
    ]
    table(slide, ["分组", "入口", "几个例子", "给什么"], rows,
          LEFT, 2.78, 11.6, [2.3, 1.0, 5.6, 2.7], size=13, head_h=0.42, row_h=0.58)
    tf = textbox(slide, LEFT, 6.3, WIDTH, 0.5, 14, ACC_D, True)
    line(tf, "共 32 个时刻 → 26 个入口 → 每张页结构固定：先接住 / 可照抄 / 别做 / 硬线 / 60 秒出口",
         14, ACC_D, True, first=True)


def s06_home(prs):
    slide = new_slide(prs)
    head(slide, 6, "产品 · 第一屏", "五个按钮，不是一个空输入框")
    pic(slide, SHOT / "01-home.png", LEFT, 2.2, 6.0)
    bullets(slide, 7.15, 2.3, 5.2, 3.6, [
        "先问“想做什么”，而不是“想说什么”。",
        "四个板块、十七个入口。",
        "页尾三个号码不折叠，任何一页都能看到。",
    ], size=15, gap=14)
    tf = textbox(slide, 7.15, 5.65, 5.2, 0.9, 12, MUTED)
    line(tf, "2026-11-23 本地版本，离线演示模式截图；对话为自拟。", 12, MUTED, first=True)


def s07_index(prs):
    slide = new_slide(prs)
    head(slide, 7, "产品 · 索引", "26 个入口，接住 32 个时刻")
    pic(slide, SHOT / "02-index.png", LEFT, 2.2, 6.0)
    bullets(slide, 7.15, 2.3, 5.2, 3.6, [
        "用一句人真的会说出口的话当标题。",
        "每张页都有“可照抄”的句子和红框硬线。",
        "能搜词：室友、失眠、钱、挂科。",
    ], size=15, gap=14)
    tf = textbox(slide, 7.15, 5.65, 5.2, 0.9, 12, MUTED)
    line(tf, "页面不调用模型：断网也能看，也不会因为模型抽风给出奇怪的话。", 12, MUTED, first=True)


def s08_crisis(prs):
    slide = new_slide(prs)
    head(slide, 8, "产品 · 出事的时候", "先给一个号码，不给选择题")
    pic(slide, SHOT / "03-crisis.png", LEFT, 2.2, 6.0)
    bullets(slide, 8.75, 2.25, 3.7, 3.9, [
        "按时段只推一个号：深夜 12356，工作日校中心。",
        "给三句能直接发出去的话。",
        "这一段不经过模型：号码、地址都写死在代码里。",
    ], size=15, gap=14)
    tf = textbox(slide, 7.15, 5.75, 5.2, 0.8, 12, MUTED)
    line(tf, "我们试过让模型写这一段：它会漏号码、编地址、在不该多话的时候多话。", 12, MUTED, first=True)


def s09_safety(prs):
    slide = new_slide(prs)
    head(slide, 9, "安全", "三道关，和一条只能往上抬的线")
    steps = [("第一道 · 规则", "20 条写死的规则先跑；命中危险直接进危机页，连模型都不调用"),
             ("第二道 · 复核", "规则没命中时才问一次模型；超时就按原等级，绝不因为超时而降级"),
             ("第三道 · 拦截", "回复写出来后再检查：诊断、承诺保密、句数；不通过就改写或换固定话")]
    y = 2.2
    for name, desc in steps:
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(LEFT), Inches(y),
                                     Inches(7.2), Inches(1.15))
        box.fill.solid()
        box.fill.fore_color.rgb = SOFT
        box.line.color.rgb = LINE
        box.adjustments[0] = 0.08
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.25)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        line(tf, name, 18, ACC_D, True, first=True, space_after=2)
        line(tf, desc, 14, INK)
        y += 1.35
    quote(slide, 8.35, 2.2, 4.1, 3.85,
          "只升不降：\n任何一层出错\n（超时 / 乱码 / 断网），\n风险等级只能往上抬。\n\n判危险 → 可能是一个人的命；\n判安全 → 最多多问一句\n“你现在安全吗”。", 14)
    tf = textbox(slide, LEFT, 6.35, 11.6, 0.5, 14, MUTED)
    line(tf, "危机模板 126 个字，是写死的；我们改了十几版，最早那版会追问“发生了什么”，被删掉了。",
         14, MUTED, first=True)


def s10_collab(prs):
    slide = new_slide(prs)
    head(slide, 10, "怎么和 AI 一起做", "说清楚 → 让它做 → 自己验")
    tf = textbox(slide, LEFT, 2.2, 6.0, 0.4, 16, ACC_D, True)
    line(tf, "每天的三步", 16, ACC_D, True, first=True)
    bullets(slide, LEFT, 2.62, 6.0, 3.3, [
        "说清楚：背景、范围（只改哪几个文件）、验收标准。",
        "让它做：一次一件事；说三件，它会做一半、剩下一半自己发挥。",
        "自己验：跑检查、开页面、看截图、故意弄坏一次。",
    ], size=16, gap=16)
    tf = textbox(slide, 7.2, 2.2, 5.3, 0.4, 16, ACC_D, True)
    line(tf, "我们给它立的四条规矩", 16, ACC_D, True, first=True)
    bullets(slide, 7.2, 2.62, 5.3, 3.3, [
        "一个文件只干一件事，超长就拆。",
        "新功能加开关，出问题一键回旧行为。",
        "安全判断只许升，不许降。",
        "每次改完三条全绿才提交：检查、接口、页面。",
    ], size=16, gap=14)
    quote(slide, LEFT, 6.0, 11.6, 0.75,
          "“它说已完成”不等于完成：验收永远在我们这边。", 16)


def s11_prompts(prs):
    slide = new_slide(prs)
    head(slide, 11, "怎么和 AI 一起做", "我们真实说过的六句话")
    rows = [
        ["把 28 条规则用例编号写进测试，一条测试只断言一件事", "拆成一条一断言，编号对上文档", "坏一条能立刻定位"],
        ["有些页面内部还保留了“回首页”，已经多余了，删除类似的", "删四处，补五条检查", "出口只剩两个"],
        ["在左侧栏加一个“与心屿交流一下”的选项，不管在什么页面", "新增入口 + 十条检查", "任何页面一步回聊天"],
        ["每个界面都在这个位置加一个返回上一级的按键", "三轮改成页首按钮 + 页面栈", "七张截图验收"],
        ["用更强的提示词结构来弥补，你有什么建议吗", "给四条建议并排优先级", "先做前两条"],
        ["试一下第 4 条吧，设置好回滚", "做实验，诚实报告“更差”", "默认关掉，代码留着"],
    ]
    table(slide, ["我们说的话（原话）", "它做了什么", "结果"], rows,
          LEFT, 2.18, 11.6, [6.2, 3.2, 2.2], size=13, head_h=0.42, row_h=0.58)
    tf = textbox(slide, LEFT, 6.25, WIDTH, 0.5, 14, ACC_D, True)
    line(tf, "共同点：有具体动作、有范围、有验收标准；而不是“帮我优化一下”。", 14, ACC_D, True, first=True)


def s12_errors(prs):
    slide = new_slide(prs)
    head(slide, 12, "怎么和 AI 一起做", "它出错的六次，和留下的东西")
    rows = [
        ["30 条回复全部以“嗯”开头", "抽样盲评：10 条样本 10 个“嗯”", "删掉“开口先一个字”"],
        ["危机模板自称 108 字，实际 126 字", "按不计换行重数，改成 126", "加了字数与号码断言"],
        ["依赖清单里带中文注释，安装报错", "换一台电脑装了一遍", "改纯英文，写进红线"],
        ["写文件时目录创建放在异常保护外", "故意设成不可写", "只写一行日志，对话继续"],
        ["把“收拾房间”判成日常", "整理新一批测试句时发现全漏", "先填事实再下结论"],
        ["用命令行改中文源码，整份变乱码", "打开文件发现全是问号", "中文文件只用编辑器写"],
    ]
    table(slide, ["它写了什么", "我们怎么发现", "怎么改 / 留下了什么"], rows,
          LEFT, 2.18, 11.6, [4.9, 3.9, 2.8], size=13, head_h=0.42, row_h=0.58)
    tf = textbox(slide, LEFT, 6.25, WIDTH, 0.5, 14, MUTED)
    line(tf, "每一次都留下一个测试、一条规则或一个习惯——而不是只改一次。", 14, MUTED, first=True)


def s13_experiments(prs):
    slide = new_slide(prs)
    head(slide, 13, "怎么和 AI 一起做", "三个“AI 说不服我们”的实验")
    rows = [
        ["让三个模型投票", "12 组里只多捞回 1 条危险句，还多误判 1 条", "不做：安全不能被多数票推翻"],
        ["只抽事实、等级由代码算", "危险 10/12→9/12；日常 11/12→7/12", "关掉：更差。代码留下当零件"],
        ["教它“收尾”是什么", "危险 8/12→9/12，日常零新增误判", "采纳，但没达到我们定的 10/12"],
    ]
    table(slide, ["实验", "结果", "决定"], rows,
          LEFT, 2.3, 11.6, [3.6, 5.4, 2.6], size=15, head_h=0.45, row_h=0.95)
    quote(slide, LEFT, 5.78, 11.6, 1.1,
          "三个实验都提前写了回滚条件：两个被回滚，一个被采纳但没达到目标——材料里如实写 9，不写“基本达到”。", 15)


def s14_cut(prs):
    slide = new_slide(prs)
    head(slide, 14, "创新点", "我们没做什么")
    tf = textbox(slide, LEFT, 2.2, 5.6, 0.4, 16, ACC_D, True)
    line(tf, "删掉的", 16, ACC_D, True, first=True)
    bullets(slide, LEFT, 2.6, 5.6, 3.9, [
        "首页 18 张卡片 → 4 组 17 个入口。",
        "每页里面的“回首页” → 只留两个出口。",
        "表情和贴纸 → 真人反馈“像客服”。",
        "“识别所有危机”这种宣传语 → 改成写清漏报几条。",
    ], size=15, gap=12)
    tf = textbox(slide, 6.9, 2.2, 5.6, 0.4, 16, ACC_D, True)
    line(tf, "三个取舍", 16, ACC_D, True, first=True)
    rows = [
        ["判断写死在代码里", "让模型自己判断危险"],
        ["只记八个标签", "记住整段对话"],
        ["先给一个号码", "一次列五个资源"],
    ]
    table(slide, ["我们选了", "放弃了"], rows, 6.9, 2.6, 5.55, [3.15, 2.4],
          size=14, head_h=0.42, row_h=0.62)
    tf = textbox(slide, 6.9, 5.1, 5.55, 0.9, 13, MUTED)
    line(tf, "理由：这个产品的价值不在能做什么，而在该停的时候停得住。", 13, MUTED, first=True, spacing=1.3)


def s15_shots(prs):
    slide = new_slide(prs)
    head(slide, 15, "成果", "它现在长什么样")
    pic(slide, SHOT / "04-chat.png", LEFT, 2.2, 5.7)
    pic(slide, SHOT / "06-rolecard.png", 6.95, 2.2, 5.7)
    tf = textbox(slide, LEFT, 6.55, 5.7, 0.35, 12, MUTED)
    line(tf, "聊天：侧栏把风险等级、当前角色、记忆都摊开", 12, MUTED, first=True)
    tf = textbox(slide, 6.95, 6.55, 5.7, 0.35, 12, MUTED)
    line(tf, "角色卡：七条说明必须勾选才可开始", 12, MUTED, first=True)


def s16_data(prs):
    slide = new_slide(prs)
    head(slide, 16, "数据", "我们最信的那七十秒")
    nums = [("828", "条自动检查", "八组：规则与安全 163 / 对话 124 / 记忆 76 / 角色卡 125 / 页面 212 / 网络 43 / 测验 27 / 故障 58"),
            ("70 秒", "跑完全部检查", "每次改完都跑；任何一项退步就不提交"),
            ("8", "个版本", "v0.1 11-08 → v3.2 11-20 → 11-23 的 828；76 次提交"),
            ("4", "项指标全达标", "危险句接住 10/10；日常误报 0/20；角色判断 12/12；十轮连续 10/10")]
    y = 2.2
    for big, label, desc in nums:
        tf = textbox(slide, LEFT, y, 2.5, 0.75, 34, ACC_D, True)
        line(tf, big, 34, ACC_D, True, first=True, spacing=1.0)
        tf = textbox(slide, 3.5, y + 0.02, 1.9, 0.4, 15, INK, True)
        line(tf, label, 15, INK, True, first=True)
        tf = textbox(slide, 5.3, y + 0.02, 7.2, 0.6, 12, MUTED)
        line(tf, desc, 12, MUTED, first=True, spacing=1.25)
        y += 1.15


def s17_team(prs):
    slide = new_slide(prs)
    head(slide, 17, "团队与价值", "六个人，各管一件事的验收")
    rows = [
        ["需求与内容", "32 个时刻、26 张内容页", "写每页的“先接住 / 可照抄 / 别做 / 硬线 / 60 秒出口”"],
        ["安全与规则", "20 条规则、126 字危机模板", "造测试句、对着漏报一条条补"],
        ["对话与提示词", "三种身份、四次提示词实验", "定句数、跑对照、决定哪一版留下"],
        ["页面与交互", "首页、索引、返回键", "提需求、拍截图、验收每个入口"],
        ["记忆与数据", "八个标签、逐类删除", "定记什么、不记什么，写删除的检查"],
        ["材料与验收", "文档、PPT、录屏、证据", "每个数字追到证据文件，跑全套检查"],
    ]
    table(slide, ["角色", "管什么", "具体做了什么"], rows,
          LEFT, 2.15, 11.6, [2.6, 4.2, 4.8], size=13, head_h=0.42, row_h=0.55)
    tf = textbox(slide, LEFT, 6.2, WIDTH, 0.55, 13, MUTED)
    line(tf, "价值：在一个人还没准备找真人之前，先不让他一个人待着，并在危险的时候把人推向真人。",
         13, MUTED, first=True)


def main():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    for build in (s01_cover, s02_who, s03_problem, s04_users, s05_needs, s06_home,
                  s07_index, s08_crisis, s09_safety, s10_collab, s11_prompts,
                  s12_errors, s13_experiments, s14_cut, s15_shots, s16_data, s17_team):
        build(prs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print("saved", OUT, len(prs.slides._sldIdLst))


if __name__ == "__main__":
    main()

