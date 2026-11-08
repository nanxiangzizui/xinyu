# -*- coding: utf-8 -*-
"""S26：17 页项目方案 PPT 生成器（python-pptx）。

用法（bundled python 才有 python-pptx）：
    python docs/slides_build.py
输出 docs/02_项目方案.pptx，16:9，17 页，字号只用 40 / 28 / 20 三级。
"""

from __future__ import annotations

import pathlib

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "02_项目方案.pptx"
SHOTS = ROOT / "docs" / "evidence" / "s21"

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
N_SLIDES = 17


# ---------- 基础排版 ----------

def _font(run, size, color, bold=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = FONT
    run.font.color.rgb = color
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {})
            rpr.append(el)
        el.set("typeface", FONT)


def textbox(slide, x, y, w, h, size=BODY, color=INK, bold=False,
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.paragraphs[0].alignment = align
    return tf


def line(tf, text, size=BODY, color=INK, bold=False, align=PP_ALIGN.LEFT,
         space_before=0, space_after=0, first=False, spacing=1.2):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.line_spacing = spacing
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    r = p.add_run()
    r.text = text
    _font(r, size, color, bold)
    return p


def bullets(slide, x, y, w, h, items, size=BODY, gap=10):
    """每条前面加一个强调色圆点，悬挂缩进 0.32 英寸。"""
    tf = textbox(slide, x, y, w, h)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 1.22
        p.space_after = Pt(gap)
        ppr = p._pPr if p._pPr is not None else p._p.get_or_add_pPr()
        ppr.set("marL", str(Emu(Inches(0.32))))
        ppr.set("indent", str(-Emu(Inches(0.32))))
        dot = p.add_run()
        dot.text = "·  "
        _font(dot, size, ACC_D, True)
        run = p.add_run()
        run.text = item
        _font(run, size, INK)
    return tf


def head(slide, no, name, title, total=N_SLIDES):
    """页眉：编号 + 板块名（20pt）、标题（40pt）、强调短线、页码。"""
    tf = textbox(slide, LEFT, 0.42, WIDTH, 0.4)
    line(tf, "%02d / %d · %s" % (no, total, name), size=BODY, color=ACC_D, first=True)
    tf2 = textbox(slide, LEFT, 0.78, WIDTH, 0.9)
    line(tf2, title, size=BIG, color=INK, bold=True, first=True, spacing=1.05)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(LEFT + 0.02), Inches(1.62),
                                 Inches(0.9), Inches(0.075))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACC
    bar.line.fill.background()
    bar.shadow.inherit = False
    num = textbox(slide, LEFT + WIDTH - 1.6, 6.95, 1.6, 0.4, align=PP_ALIGN.RIGHT)
    line(num, "%d / %d" % (no, total), size=BODY, color=MUTED, first=True)


def new_slide(prs):
    """新建空白页并铺产品底色（sakura 系 #FFFDF9）。"""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    return s


def pic(slide, path, x, y, w=None, h=None):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)


def table(slide, headers, rows, x, y, w, col_w, row_h=0.5, head_h=0.52):
    shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(x), Inches(y),
                                   Inches(w), Inches(head_h + row_h * len(rows)))
    tbl = shape.table
    tbl_pr = shape._element.graphic.graphicData.tbl.tblPr
    tbl_pr.set("firstRow", "0")
    tbl_pr.set("bandRow", "0")
    for el in tbl_pr.findall(qn("a:tableStyleId")):
        tbl_pr.remove(el)
    sid = tbl_pr.makeelement(qn("a:tableStyleId"), {})
    sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"  # No Style, No Grid
    tbl_pr.append(sid)

    tbl.rows[0].height = Inches(head_h)
    for i in range(1, len(rows) + 1):
        tbl.rows[i].height = Inches(row_h)
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = Inches(cw)

    for j, text in enumerate(headers):
        _fill_cell(tbl.cell(0, j), text, SOFT, INK, True)
    for i, row in enumerate(rows, 1):
        bg = WHITE if i % 2 else SOFT
        for j, text in enumerate(row):
            _fill_cell(tbl.cell(i, j), text, bg, INK, False)
    return shape


def _fill_cell(cell, text, fill, color, bold):
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    cell.margin_left = Inches(0.12)
    cell.margin_right = Inches(0.08)
    cell.margin_top = Inches(0.05)
    cell.margin_bottom = Inches(0.05)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf = cell.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.line_spacing = 1.0
    r = p.add_run()
    r.text = text
    _font(r, BODY, color, bold)
    _borders(cell)


def _borders(cell):
    tc_pr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnB", "a:lnT", "a:lnR", "a:lnL"):
        for el in tc_pr.findall(qn(tag)):
            tc_pr.remove(el)
        ln = tc_pr.makeelement(qn(tag), {"w": "9525", "cap": "flat", "cmpd": "sng", "algn": "ctr"})
        fill = ln.makeelement(qn("a:solidFill"), {})
        clr = fill.makeelement(qn("a:srgbClr"), {"val": "F0D8C8"})
        fill.append(clr)
        ln.append(fill)
        tc_pr.insert(0, ln)


# ---------- 17 页 ----------

def slide_cover(prs, no):
    s = new_slide(prs)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.22))
    band.fill.solid()
    band.fill.fore_color.rgb = ACC
    band.line.fill.background()
    band.shadow.inherit = False

    block = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(LEFT), Inches(1.05),
                               Inches(6.0), Inches(5.2))
    block.fill.solid()
    block.fill.fore_color.rgb = SOFT
    block.line.color.rgb = LINE
    block.shadow.inherit = False

    tf = textbox(s, LEFT + 0.6, 1.55, 8.0, 0.4)
    line(tf, "参赛赛题：赛题一（AI 辅助开发·创意产品原型）", size=BODY, color=ACC_D, bold=True, first=True)
    t2 = textbox(s, LEFT + 0.6, 2.15, 9.0, 1.0)
    line(t2, "心屿 MindIsle", size=BIG, color=INK, bold=True, first=True)
    t3 = textbox(s, LEFT + 0.6, 3.05, 8.0, 0.6)
    line(t3, "一个不会害人的情绪陪伴工具", size=MID, color=INK, first=True)
    t4 = textbox(s, LEFT + 0.6, 3.75, 8.4, 1.4)
    line(t4, "三段职责隔离 + 一票否决的安全审查层", size=BODY, color=MUTED, first=True)
    line(t4, "杭州电子科技大学 · 第二届 AIGC 应用创新大赛", size=BODY, color=MUTED, space_before=10)
    t5 = textbox(s, LEFT + 0.6, 5.45, 8.4, 0.4)
    line(t5, "6 人小队 · 项目方案 · v1.0 · 2026 年 11 月", size=BODY, color=MUTED, first=True)
    n = textbox(s, 9.3, 6.8, 3.2, 0.4, align=PP_ALIGN.RIGHT)
    line(n, "01 / %d" % N_SLIDES, size=BODY, color=MUTED, first=True)
    return s


def slide_idea(prs):
    s = new_slide(prs)
    head(s, 2, "创作理念", "陪伴 > 建议，边界 > 能力")
    tf = textbox(s, LEFT, 2.0, WIDTH, 0.6)
    line(tf, "它不假装懂你，但它不会害你。", size=MID, color=ACC_D, bold=True, first=True)
    bullets(s, LEFT, 2.75, WIDTH, 4.0, [
        "陪伴优先：第一轮不解决问题，只让人敢继续说下去",
        "边界优先：模型说错一句就可能伤人，所以否决权不交给模型",
        "可验证优先：报告里每个数字都有分子分母，能逐条复现",
        "诚实优先：测试集自拟、没有真人测试，这两条写在报告第 7 章",
    ])


def slide_user(prs):
    s = new_slide(prs)
    head(s, 3, "目标用户", "杭电在校生，三个真实的时刻")
    tf = textbox(s, LEFT, 2.0, WIDTH, 0.6)
    line(tf, "凌晨一点，通讯录翻到底。", size=MID, color=ACC_D, bold=True, first=True)
    bullets(s, LEFT, 2.75, WIDTH, 3.4, [
        "深夜宿舍：熄灯后想说话，又怕吵醒室友",
        "考前一周：连续失眠、什么都不想做，还怕被人说“矫情”",
        "宿舍矛盾：气得说不出话，需要一个不站队的耳朵",
    ])
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(LEFT), Inches(5.55),
                             Inches(WIDTH), Inches(1.05))
    box.fill.solid()
    box.fill.fore_color.rgb = SOFT
    box.line.color.rgb = LINE
    box.shadow.inherit = False
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.25)
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "他们不是“病人”，是暂时没人可说的普通学生：不做筛查，不做诊断。"
    _font(r, BODY, INK)


def slide_problem(prs):
    s = new_slide(prs)
    head(s, 4, "核心问题", "三种出口，三处不足")
    table(s, ["现有出口", "学生的顾虑", "结果"],
          [["室友、朋友", "怕打扰、怕被记住", "话咽了回去"],
           ["辅导员、心理中心", "怕留痕、要预约", "三天后才有人"],
           ["通用 AI 聊天", "怕说错、怕被下诊断", "最需要的时候不敢用"]],
          LEFT, 2.0, WIDTH, [3.4, 4.0, 4.2], row_h=0.72, head_h=0.56)
    tf = textbox(s, LEFT, 5.5, WIDTH, 1.2)
    line(tf, "缺的是一个随时在、不评判、不出事的出口。", size=MID, color=ACC_D, bold=True, first=True)


def slide_evidence(prs):
    s = new_slide(prs)
    head(s, 5, "需求证据", "我们只有场景共识，没有问卷")
    tf = textbox(s, LEFT, 2.0, WIDTH, 0.6)
    line(tf, "所以这一页没有一个百分比。", size=MID, color=ACC_D, bold=True, first=True)
    bullets(s, LEFT, 2.75, WIDTH, 4.1, [
        "需求来自 6 名队员和身边同学的共同场景，不是抽样调查",
        "能拿出的证据是“失败模式”：三种出口各自在哪一步断掉（上一页）",
        "校园资源可达性已核实：12356 24 小时，校心理中心工作日 0571-87713518",
        "局限写在明面上：没有真人用户测试，没有问卷样本，报告 §7 同样写明",
    ])


def slide_solution(prs):
    s = new_slide(prs)
    head(s, 6, "解决方案总览", "三种状态，一条安全线")
    pic(s, ROOT / "docs" / "report-arch.png", LEFT, 1.9, w=11.2)
    tf = textbox(s, LEFT, 6.86, WIDTH, 0.4)
    line(tf, "三条铁律：只升不降 · 否决权唯一 · 责任不越界。", size=BODY, color=ACC_D, bold=True, first=True)


def slide_stack(prs):
    s = new_slide(prs)
    head(s, 7, "技术路径", "20 天能做完的技术，才是好技术")
    table(s, ["层", "选型", "为什么是它"],
          [["界面", "Streamlit 单页", "一门语言做完，不写前端"],
           ["模型", "DeepSeek（OpenAI 兼容）", "便宜、够用、可替换"],
           ["存储", "本地 JSON，一人一文件", "可读、可删、可审计"],
           ["测试", "pytest 132 条", "纯函数优先，不测网络"],
           ["边界", "11 个函数签名契约", "改签名 = 全组返工"]],
          LEFT, 2.0, WIDTH, [1.7, 4.6, 5.3], row_h=0.66, head_h=0.52)
    tf = textbox(s, LEFT, 6.55, WIDTH, 0.4)
    line(tf, "不引入 LangChain / 向量库 / FastAPI / React / 数据库。", size=BODY, color=MUTED, first=True)


def slide_flow(prs):
    s = new_slide(prs)
    head(s, 8, "工作流", "谁决定说什么，谁决定能不能说")
    steps = [
        "1  输入：一句话，允许情绪化、允许不说完整",
        "2  规则层：20 条规则、按小句切分、四类豁免先跑",
        "3  聚合：最近 5 轮窗口，出现 L2 就抬 L2，只升不降",
        "4  角色状态机：listener / guide / crisis，只改语气",
        "5  生成：DeepSeek，温度 0.7，人设只管措辞",
        "6  守卫：四类硬违规直接重写，其余交模型复核（0.2）",
        "7  输出：回复 + 资源卡 + 一行结构化日志（不写原文）",
    ]
    tf = textbox(s, LEFT, 1.98, WIDTH, 4.2)
    for i, text in enumerate(steps):
        line(tf, text, size=BODY, color=INK, first=(i == 0), space_after=9, spacing=1.15)
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(LEFT), Inches(5.92),
                             Inches(WIDTH), Inches(0.95))
    box.fill.solid()
    box.fill.fore_color.rgb = SOFT
    box.line.color.rgb = LINE
    box.shadow.inherit = False
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.25)
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "L3 或聚合升级 → 固定模板 + 3 张资源卡，不调用模型。"
    _font(r, MID, ACC_D, True)


def slide_scope(prs):
    s = new_slide(prs)
    head(s, 9, "设计过程①", "五份计划书，砍成一份执行书")
    tf = textbox(s, LEFT, 2.0, WIDTH, 0.6)
    line(tf, "我们删掉了大约 60% 的想法。", size=MID, color=ACC_D, bold=True, first=True)
    bullets(s, LEFT, 2.75, WIDTH, 4.1, [
        "5 份计划书 → 1 份执行书：3 角色 / 3 决策层 / 20 条规则 / 11 个契约",
        "拆成 26 个可单独验证、可单独回滚的步骤，每步都有可勾选的出口",
        "六级砍单表：主题 → lorebook → 角色 → 打卡 → 面板 → 聚合，按顺序砍",
        "砍单只砍体验：guardian、20 条规则、测试、免责声明、资源卡不许砍",
    ])


def slide_tradeoff(prs):
    s = new_slide(prs)
    head(s, 10, "设计过程②", "每个“不用”都有判据")
    table(s, ["取舍", "判据", "结果"],
          [["不做多角色协商", "角色只改语气，不改决策", "是路由，不是协商，责任可指"],
           ["不用向量库", "8 字段 + 8 条 lore 够用", "少 3 天，也不会检索出原文"],
           ["危机不走模型", "模型最不可靠时恰是最危险时", "固定模板，断网可用"]],
          LEFT, 2.0, WIDTH, [3.0, 4.5, 4.1], row_h=0.86, head_h=0.52)
    tf = textbox(s, LEFT, 5.55, WIDTH, 0.6)
    line(tf, "判据只有一个：它是否改变下游行为。", size=MID, color=ACC_D, bold=True, first=True)


def slide_matrix(prs):
    s = new_slide(prs)
    head(s, 11, "考虑过但没用", "不是不会，是不划算")
    table(s, ["候选方案", "新手可维护", "4 周可交付", "安全可验证", "结论"],
          [["DeepSeek 单模型 + 多角色 prompt + 规则否决", "✅", "✅", "✅ 可逐条回归", "采用"],
           ["5 个 Agent 串行协作（LangGraph）", "❌", "❌", "⚠️ 责任难界", "否：约 12.5s，且没人负责"],
           ["微调专属模型", "❌", "❌", "❌", "否：无数据、无算力"],
           ["向量库长记忆（ChromaDB）", "⚠️", "⚠️", "⚠️", "否：检索到原文就违规"],
           ["纯规则（不用 LLM）", "✅", "✅", "✅", "否：回复像测试用例"]],
          LEFT, 2.0, WIDTH, [3.9, 1.7, 1.7, 2.2, 2.1], row_h=0.74, head_h=0.56)
    tf = textbox(s, LEFT, 6.62, WIDTH, 0.4)
    line(tf, "一页里同时出现“选了什么”和“为什么不选”，就是选择能力。", size=BODY, color=MUTED, first=True)


def slide_shots(prs):
    s = new_slide(prs)
    head(s, 12, "核心功能演示", "三个状态，四种证据")
    items = [
        ("02-tired.png", "陪伴 · 倾听者", "L1 · 先接住情绪，不给建议"),
        ("03-advice.png", "切换 · 引导者", "L1 · 问的是方法，角色由规则切"),
        ("05-crisis.png", "危机 · 危机支持", "L3 · 3 张资源卡 12356 / 110·120 / 校心理中心"),
        ("12-offline-crisis.png", "断网 · 模型不可用", "照样出卡：危机回复不经过模型"),
    ]
    cw, gap = 5.75, 0.55
    for i, (fname, cap, note) in enumerate(items):
        x = LEFT + (i % 2) * (cw + gap)
        y = 1.95 + (i // 2) * 2.55
        pic(s, SHOTS / fname, x, y, w=3.3)
        tf = textbox(s, x + 3.45, y + 0.1, 2.3, 2.2)
        line(tf, cap, size=BODY, color=ACC_D, bold=True, first=True, spacing=1.1)
        line(tf, note, size=BODY, color=INK, space_before=8, spacing=1.1)


def slide_safety(prs):
    s = new_slide(prs)
    head(s, 13, "安全机制", "模型没有否决权")
    items = [
        "规则层：20 条规则（X 5 / H 10 / W 5），小句切分，四类豁免先跑",
        "聚合：5 轮窗口，窗口内出现 L2 就抬 L2，三次 L2 升 L3",
        "短路：判为 L3 立即返回固定模板 + 资源卡，不调用模型",
        "守卫：四类硬违规直接重写，其余交模型复核（温度 0.2）",
        "复检：重写后再过同一套检查，仍不过就换安全兜底句",
    ]
    bullets(s, LEFT, 1.95, WIDTH, 4.2, items, gap=12)
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(LEFT), Inches(5.95),
                             Inches(WIDTH), Inches(0.9))
    box.fill.solid()
    box.fill.fore_color.rgb = SOFT
    box.line.color.rgb = LINE
    box.shadow.inherit = False
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.25)
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "一票否决：guardian 不通过，这句就不发。"
    _font(r, MID, ACC_D, True)


def slide_memory(prs):
    s = new_slide(prs)
    head(s, 14, "记忆设计", "记住标签，不记原话")
    pic(s, SHOTS / "08-refresh-memory.png", LEFT, 1.95, w=4.4)
    bullets(s, LEFT + 4.75, 1.95, 6.85, 3.6, [
        "8 个白名单字段 + 1 个摘要位置，其余一律不落盘",
        "写入前 scrub 手机 / 证件 / 邮箱 / 链接 / 学校名，再截断",
        "每 5 轮或超 200 字，压成 120 字第三人称摘要，禁止人名",
        "面板可读、可改两项偏好、可导出、可一键真删（含备份）",
    ], gap=9)
    tf = textbox(s, LEFT + 4.75, 5.75, 6.85, 1.1)
    line(tf, "云端容器磁盘是临时的：演示时同一会话连续操作，不承诺长期存储。",
         size=BODY, color=MUTED, first=True, spacing=1.15)


def slide_data(prs):
    s = new_slide(prs)
    head(s, 15, "测试与数据", "每个数字都有分子分母")
    table(s, ["指标", "结果", "目标"],
          [["高危召回（10 条）", "10/10 = 100%", "≥ 90%"],
           ["日常误拦（20 条）", "0/20 = 0%", "≤ 15%"],
           ["角色准确率（12 条）", "12/12 = 100%", "≥ 75%"],
           ["连续 10 轮稳定", "10/10", "10/10"],
           ["自动化测试", "132 条，全部本地可跑", "考核口径 48"]],
          LEFT, 1.95, WIDTH, [4.3, 4.6, 2.7], row_h=0.55, head_h=0.5)
    tf = textbox(s, LEFT, 5.35, WIDTH, 0.9)
    line(tf, "三句局限：样本自拟、高危样本只有 10 条、12 条角色用例里 9 条是 listener。",
         size=BODY, color=ACC_D, bold=True, first=True, spacing=1.2)


def slide_team(prs):
    s = new_slide(prs)
    head(s, 16, "团队协作", "每个人都能被追问")
    table(s, ["成员", "主责", "备份"],
          [["P1 队长", "memory.py、契约、整合、进度", "P2"],
           ["P2", "agent.py、人设 prompt", "P1"],
           ["P3", "guardian.py、RULES 20 条", "P4"],
           ["P4", "coordinator.py、会话聚合", "P3"],
           ["P5", "app.py、resources.py、主题", "P6"],
           ["P6", "测试、部署、文档、录屏", "P5"]],
          LEFT, 1.95, WIDTH, [2.1, 7.0, 2.5], row_h=0.56, head_h=0.5)
    tf = textbox(s, LEFT, 6.2, WIDTH, 0.6)
    line(tf, "26 个可回滚步骤 · 34 次提交 · 4 个版本节点（v0.1 / v0.2 / v0.3 / v1.0）· 结对互看",
         size=BODY, color=MUTED, first=True)


def slide_value(prs):
    s = new_slide(prs)
    head(s, 17, "价值与展望", "它不治病，它只保证不添乱")
    bullets(s, LEFT, 1.95, WIDTH, 3.6, [
        "价值：给“还没到看病的程度、但今晚很难”的人一个不添乱的出口",
        "价值：把安全做成可审计的结构，而不是一句“我们会注意”",
        "限制：不是治疗、不做筛查、没有真人转介闭环、没有真人用户测试",
        "下一步：校园资源打通（预约 / 转介）、真人危机联动、扩大误拦评估样本",
    ], gap=11)
    tf = textbox(s, LEFT, 5.75, WIDTH, 0.6)
    line(tf, "不诊断，不承诺保密，不替代真人。", size=MID, color=ACC_D, bold=True, first=True)


def main():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    builders = [
        slide_cover, slide_idea, slide_user, slide_problem, slide_evidence,
        slide_solution, slide_stack, slide_flow, slide_scope, slide_tradeoff,
        slide_matrix, slide_shots, slide_safety, slide_memory, slide_data,
        slide_team, slide_value,
    ]
    for i, fn in enumerate(builders, 1):
        if fn is slide_cover:
            fn(prs, i)
        else:
            fn(prs)

    prs.save(OUT)
    print("saved", OUT)
    print("slides", len(prs.slides._sldIdLst))


if __name__ == "__main__":
    main()
