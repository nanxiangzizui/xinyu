# -*- coding: utf-8 -*-
"""构建 docs/01_项目文档.docx（python-docx，仅用于生成，不进入运行时依赖）。"""
import json
import pathlib
import sys
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs"))

import report_content_a as A
import report_content_b as B

OUT = ROOT / "docs" / "01_项目文档.docx"
INK = RGBColor(0x24, 0x30, 0x44)
MUTED = RGBColor(0x6B, 0x72, 0x80)
BODY_FONT = "宋体"
HEAD_FONT = "黑体"
BODY_PT = 12
LINE = 1.3
TEXT_W = 16.4  # 正文可用宽度（21cm - 左右各 2.2cm，留 0.2 余量）


def _east(style, name):
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(attr)) is not None:
            del rfonts.attrib[qn(attr)]
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)


def setup(doc):
    for cs in doc.settings.element.findall(qn("w:compat")):
        for s in cs.findall(qn("w:compatSetting")):
            if s.get(qn("w:name")) == "compatibilityMode":
                s.set(qn("w:val"), "15")
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Cm(2.2))
    sec.top_margin, sec.bottom_margin = Cm(2.4), Cm(2.2)

    st = doc.styles["Normal"]
    st.font.name = BODY_FONT
    st.font.size = Pt(BODY_PT)
    st.font.color.rgb = INK
    _east(st, BODY_FONT)
    pf = st.paragraph_format
    pf.line_spacing = LINE
    pf.space_after = Pt(4)

    for name, size in (("Heading 1", 17), ("Heading 2", 14), ("Heading 3", 12.5)):
        h = doc.styles[name]
        h.font.name = HEAD_FONT
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = INK
        _east(h, HEAD_FONT)
        h.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 10)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.line_spacing = 1.2

    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("心屿 MindIsle · 参赛赛题：赛题一（AI 辅助开发·创意产品原型） · ")
    run.font.size = Pt(8.5)
    run.font.color.rgb = MUTED
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    fld.append(r)
    footer._p.append(fld)


def h(doc, level, text):
    return doc.add_heading(text, level=level)


def p(doc, text, indent=True, size=None, bold=False, align=None, space_after=None):
    par = doc.add_paragraph()
    run = par.add_run(text)
    run.bold = bold
    if size:
        run.font.size = Pt(size)
    if indent:
        par.paragraph_format.first_line_indent = Pt(BODY_PT * 2)
    par.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if align is None else align
    if space_after is not None:
        par.paragraph_format.space_after = Pt(space_after)
    return par


def bullets(doc, items):
    for it in items:
        par = doc.add_paragraph(style="List Bullet")
        par.paragraph_format.line_spacing = LINE
        par.paragraph_format.space_after = Pt(2)
        if isinstance(it, tuple):
            lead, rest = it
            r = par.add_run(lead)
            r.bold = True
            par.add_run(rest)
        else:
            par.add_run(it)


def numbered(doc, items):
    # 手写序号：Word 的 List Number 是全局续编（第二章从 11 开始），这里每条列表都从 1 起
    for i, it in enumerate(items, 1):
        par = doc.add_paragraph()
        par.paragraph_format.left_indent = Cm(0.85)
        par.paragraph_format.first_line_indent = Cm(-0.85)
        par.paragraph_format.line_spacing = LINE
        par.paragraph_format.space_after = Pt(2)
        par.add_run(f"{i}.  ")
        par.add_run(it)


def quote(doc, text):
    par = doc.add_paragraph()
    par.paragraph_format.left_indent = Cm(0.6)
    par.paragraph_format.line_spacing = 1.25
    run = par.add_run(text)
    run.font.name = "楷体"
    run.font.size = Pt(10.5)
    _east_par(par, "楷体")
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F4F6FA")
    par._p.get_or_add_pPr().append(shd)
    return par


def _east_par(par, name):
    for run in par.runs:
        rpr = run._r.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        rfonts.set(qn("w:eastAsia"), name)


def caption(doc, text):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run(text)
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED
    par.paragraph_format.space_after = Pt(10)


def shade(cell, color):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcpr.append(shd)


def table(doc, headers, rows, widths=None, size=9.5, caption_text=None, first_col_bold=False):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    hdr = t.rows[0]
    trpr = hdr._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    trpr.append(th)
    for i, text in enumerate(headers):
        cell = hdr.cells[i]
        cell.text = ""
        par = cell.paragraphs[0]
        run = par.add_run(text)
        run.bold = True
        run.font.size = Pt(size)
        par.paragraph_format.space_after = Pt(1)
        par.paragraph_format.line_spacing = 1.0
        shade(cell, "EDF1F7")
    for row in rows:
        cells = t.add_row().cells
        for i, text in enumerate(row):
            cells[i].text = ""
            par = cells[i].paragraphs[0]
            run = par.add_run(str(text))
            run.font.size = Pt(size)
            run.bold = first_col_bold and i == 0
            par.paragraph_format.space_after = Pt(1)
            par.paragraph_format.line_spacing = 1.0
    if widths:
        total = sum(widths)
        if total > TEXT_W:
            widths = [w * TEXT_W / total for w in widths]
        for i, w in enumerate(widths):
            t.columns[i].width = Cm(w)
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    if caption_text:
        caption(doc, caption_text)
    return t


def figure(doc, path, width_cm, cap):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before = Pt(6)
    par.add_run().add_picture(str(ROOT / path), width=Cm(width_cm))
    caption(doc, cap)


def render(doc, blocks):
    for b in blocks:
        kind = b[0]
        if kind == "h1":
            page_break(doc)
            h(doc, 1, b[1])
        elif kind == "h2":
            h(doc, 2, b[1])
        elif kind == "h3":
            h(doc, 3, b[1])
        elif kind == "p":
            p(doc, b[1])
        elif kind == "b":
            bullets(doc, b[1])
        elif kind == "n":
            numbered(doc, b[1])
        elif kind == "q":
            quote(doc, b[1])
        elif kind == "t":
            spec = b[1]
            table(doc, spec["headers"], spec["rows"], spec.get("widths"),
                  spec.get("size", 9.5), spec.get("caption"), spec.get("first_col_bold", False))
        elif kind == "fig":
            figure(doc, b[1], b[2], b[3])
        elif kind == "cap":
            caption(doc, b[1])
        elif kind == "pb":
            page_break(doc)


def page_break(doc):
    doc.add_page_break()


def title_page(doc):
    for _ in range(3):
        doc.add_paragraph()
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("参赛赛题：赛题一（AI 辅助开发·创意产品原型）")
    run.bold = True
    run.font.size = Pt(13)
    doc.add_paragraph()
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("心屿 MindIsle")
    run.bold = True
    run.font.size = Pt(40)
    run.font.name = HEAD_FONT
    _east_par(par, HEAD_FONT)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("一个不会害人的情绪陪伴工具")
    run.font.size = Pt(17)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("项目文档 · 杭电第二届 AIGC 应用创新大赛")
    run.font.size = Pt(12)
    run.font.color.rgb = MUTED
    for _ in range(7):
        doc.add_paragraph()
    rows = [
        ("队伍", "6 人小队（分工见第 8 章）"),
        ("产物", "Streamlit 单页应用 + 规则安全层 + 本地记忆"),
        ("代码规模", "12 个 Python 模块（2067 行），132 条自动化测试"),
        ("版本 / 日期", "v1.0 / 2026-11-08"),
    ]
    t = doc.add_table(rows=0, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for k, v in rows:
        cells = t.add_row().cells
        cells[0].width, cells[1].width = Cm(4), Cm(10)
        r0 = cells[0].paragraphs[0].add_run(k)
        r0.bold = True
        r0.font.size = Pt(11)
        cells[1].paragraphs[0].add_run(v).font.size = Pt(11)
    doc.add_paragraph()
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("本材料中的用户对话、测试用例全部为自拟虚构，不含任何真人倾诉。")
    run.font.size = Pt(9.5)
    run.font.color.rgb = MUTED


def toc(doc):
    doc.add_page_break()
    h(doc, 1, "目录")
    pages = {}
    map_path = ROOT / "docs" / "report_toc.json"
    if map_path.exists():
        pages = json.loads(map_path.read_text(encoding="utf-8"))
    idx = [str(i) for i in range(1, 10)] + ["A", "B", "C", "D"]
    items = [
        ("1 项目背景与问题", "1"),
        ("2 目标用户与需求分析", "3"),
        ("3 解决方案：三角色与一条安全线", "4"),
        ("4 技术实现路径", "6"),
        ("5 安全与记忆机制", "9"),
        ("6 测试与评估", "12"),
        ("7 创新点与价值：我们没做什么", "14"),
        ("8 团队分工与协作过程", "16"),
        ("9 总结与展望", "17"),
        ("附录 A　AI 工具使用说明", "A-1"),
        ("附录 B　28 条规则用例逐条结果", "B-1"),
        ("附录 C　12 条对话与 8 条故障注入", "C-1"),
        ("附录 D　仓库、运行说明与证据索引", "D-1"),
    ]
    items = [(name, pages.get(key, default)) for (name, default), key in zip(items, idx)]
    for name, page in items:
        par = doc.add_paragraph()
        par.paragraph_format.line_spacing = 1.6
        par.add_run(name)
        par.add_run(" " * 6)
        run = par.add_run(page)
        run.font.color.rgb = MUTED


def main():
    doc = Document()
    setup(doc)
    title_page(doc)
    toc(doc)
    render(doc, A.BLOCKS)
    render(doc, B.BLOCKS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print("saved", OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
