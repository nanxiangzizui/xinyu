# -*- coding: utf-8 -*-
"""构建 docs/P26-P30_对话工作记录_2026-11-20.docx（python-docx，仅生成用）。"""
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
import p26_p30_log_content as C  # noqa: E402

OUT = ROOT / "docs" / "P26-P30_对话工作记录_2026-11-20.docx"
INK = RGBColor(0x24, 0x30, 0x44)
MUTED = RGBColor(0x6B, 0x72, 0x80)
BODY_FONT = "宋体"
HEAD_FONT = "黑体"
CODE_FONT = "Consolas"
TEXT_W = 16.8


def _east(style, name):
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(attr)) is not None:
            del rfonts.attrib[qn(attr)]
    for attr in ("w:eastAsia", "w:ascii", "w:hAnsi"):
        rfonts.set(qn(attr), name)


def setup(doc):
    for cs in doc.settings.element.findall(qn("w:compat")):
        for s in cs.findall(qn("w:compatSetting")):
            if s.get(qn("w:name")) == "compatibilityMode":
                s.set(qn("w:val"), "15")
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.0)
    sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)

    st = doc.styles["Normal"]
    st.font.name = BODY_FONT
    st.font.size = Pt(11)
    st.font.color.rgb = INK
    _east(st, BODY_FONT)
    st.paragraph_format.line_spacing = 1.32
    st.paragraph_format.space_after = Pt(3)

    for name, size in (("Heading 1", 17), ("Heading 2", 13.5), ("Heading 3", 12)):
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
    run = footer.add_run("心屿 MindIsle · P26–P30 工作记录 · 2026-11-20 · 第 ")
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
    tail = footer.add_run(" 页")
    tail.font.size = Pt(8.5)
    tail.font.color.rgb = MUTED


def shade(cell, color):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcpr.append(shd)


def table(doc, spec):
    headers, rows = spec["headers"], spec["rows"]
    widths = spec["widths"]
    size = spec.get("size", 9.2)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    t._tbl.tblPr.append(layout)
    total = sum(widths)
    if total > TEXT_W:
        widths = [w * TEXT_W / total for w in widths]
    for i, w in enumerate(widths):
        t.columns[i].width = Cm(w)
    hdr = t.rows[0]
    trpr = hdr._tr.get_or_add_trPr()
    trpr.append(OxmlElement("w:tblHeader"))
    for i, text in enumerate(headers):
        cell = hdr.cells[i]
        cell.text = ""
        par = cell.paragraphs[0]
        run = par.add_run(text)
        run.bold = True
        run.font.size = Pt(size)
        par.paragraph_format.space_after = Pt(1)
        par.paragraph_format.line_spacing = 1.05
        shade(cell, "EDF1F7")
    for row in rows:
        cells = t.add_row().cells
        for i, text in enumerate(row):
            cells[i].text = ""
            par = cells[i].paragraphs[0]
            run = par.add_run(str(text))
            run.font.size = Pt(size)
            run.bold = spec.get("first_col_bold") and i == 0
            par.paragraph_format.space_after = Pt(1)
            par.paragraph_format.line_spacing = 1.05
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    if spec.get("caption"):
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = par.add_run(spec["caption"])
        run.font.size = Pt(9)
        run.font.color.rgb = MUTED
        par.paragraph_format.space_after = Pt(10)


def p(doc, text, indent=True):
    par = doc.add_paragraph()
    run = par.add_run(text)
    if indent:
        par.paragraph_format.first_line_indent = Pt(22)
    par.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return par


def bullets(doc, items):
    for it in items:
        par = doc.add_paragraph(style="List Bullet")
        par.paragraph_format.line_spacing = 1.3
        par.paragraph_format.space_after = Pt(2)
        if isinstance(it, tuple):
            lead, rest = it
            run = par.add_run(lead)
            run.bold = True
            par.add_run(rest)
        else:
            par.add_run(it)


def numbered(doc, items):
    for i, it in enumerate(items, 1):
        par = doc.add_paragraph()
        par.paragraph_format.left_indent = Cm(0.85)
        par.paragraph_format.first_line_indent = Cm(-0.85)
        par.paragraph_format.line_spacing = 1.3
        par.paragraph_format.space_after = Pt(2)
        par.add_run(f"{i}.  ")
        par.add_run(it)


def code_block(doc, text):
    par = doc.add_paragraph()
    par.paragraph_format.left_indent = Cm(0.4)
    par.paragraph_format.line_spacing = 1.15
    par.paragraph_format.space_before = Pt(4)
    par.paragraph_format.space_after = Pt(6)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F4F6FA")
    par._p.get_or_add_pPr().append(shd)
    run = par.add_run()
    run.font.name = CODE_FONT
    run.font.size = Pt(9)
    run.text = text


def _run_font(run, name, size, bold=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    rpr = run._r.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:eastAsia", "w:ascii", "w:hAnsi"):
        rfonts.set(qn(attr), name)


def figure(doc, filename, width_cm, caption, num):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before = Pt(6)
    par.paragraph_format.space_after = Pt(2)
    run = par.add_run()
    run.add_picture(str(ROOT / "docs" / "evidence" / "shots-P31" / filename), width=Cm(width_cm))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(10)
    r = cap.add_run(f"图 {num}　{caption}")
    r.font.size = Pt(9)
    r.font.color.rgb = MUTED


def render(doc, blocks):
    fig = 0
    for b in blocks:
        kind = b[0]
        if kind == "h1":
            doc.add_heading(b[1], level=1)
        elif kind == "h2":
            doc.add_heading(b[1], level=2)
        elif kind == "h3":
            doc.add_heading(b[1], level=3)
        elif kind == "p":
            p(doc, b[1])
        elif kind == "b":
            bullets(doc, b[1])
        elif kind == "n":
            numbered(doc, b[1])
        elif kind == "t":
            table(doc, b[1])
        elif kind == "code":
            code_block(doc, b[1])
        elif kind == "img":
            fig += 1
            figure(doc, b[1], b[2], b[3], fig)
        elif kind == "pb":
            doc.add_page_break()


def title_page(doc):
    for _ in range(3):
        doc.add_paragraph()
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("内部工作记录 · 不进入提交材料")
    run.font.size = Pt(10)
    run.font.color.rgb = MUTED

    doc.add_paragraph()
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("心屿 MindIsle")
    _run_font(run, HEAD_FONT, 38, bold=True)

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("P26–P30 工作记录")
    _run_font(run, HEAD_FONT, 22, bold=True)

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("从「这一刻我想说话」到「开不了口」与「说完之后」")
    _run_font(run, BODY_FONT, 12.5)
    run.font.color.rgb = MUTED

    for _ in range(5):
        doc.add_paragraph()
    rows = [
        ("覆盖范围", "2026-11-20 20:14–21:18 这一次对话区内的 P26–P30"),
        ("起点基线", "536 passed（P25 后）"),
        ("终点基线", "618 passed，契约 11/11 + 5/5 + 20/20"),
        ("产物", "三个新页面层文件、六个测试文件、五份证据文档"),
    ]
    t = doc.add_table(rows=0, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for k, v in rows:
        cells = t.add_row().cells
        cells[0].width, cells[1].width = Cm(3.6), Cm(10.4)
        r0 = cells[0].paragraphs[0].add_run(k)
        r0.bold = True
        r0.font.size = Pt(10.5)
        cells[1].paragraphs[0].add_run(v).font.size = Pt(10.5)

    for _ in range(6):
        doc.add_paragraph()
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run("本文只覆盖这一个对话区；P0–P25 与材料侧（docx / PPT / 视频）不在范围内。"
                      "文中用户对话与测试用例均为项目自拟，不含任何真人倾诉。")
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED


def guide_page(doc):
    doc.add_page_break()
    doc.add_heading("本文导览", level=1)
    p(doc, "这份文档把对话区里发生的事按「问题 → 做法 → 验证 → 证据」整理成五轮，"
           "并在最后两节给出可复用的工程结论与文件索引。所有数字都来自本对话的实跑输出。")
    table(doc, {
        "headers": ["章节", "内容", "对应阶段"],
        "rows": [
            ["一", "评分口径变化、问题地图、七项清单", "起点"],
            ["二", "五轮迭代总览与测试数变化", "P26–P30"],
            ["三", "危机下一步、朋友页、数据可见", "P26"],
            ["四", "首屏四选一分诊", "P27"],
            ["五", "对抗性测试集与 RULES 补丁", "P28 / P28b"],
            ["六", "写下来接一句、咨询前后两张卡", "P29"],
            ["七", "辅导员 / 请假 / 陪同三页", "P30"],
            ["八", "五轮里反复出现的工程结论", "横切"],
            ["九", "新增 / 修改文件、证据索引、已知限制", "收尾"],
            ["附录 A / B", "验收命令与原始输出；一页速查", "—"],
        ],
        "widths": [2.2, 11.0, 3.6],
        "size": 9.5,
        "caption": "表 0　本文结构",
        "first_col_bold": True,
    })
    p(doc, "阅读建议：如果只关心「解决了什么现实问题」，看第二、九章与附录 B；"
           "如果关心「怎么验证的」，看每一轮的验证小节与附录 A。")


def main():
    doc = Document()
    setup(doc)
    title_page(doc)
    guide_page(doc)
    render(doc, C.BLOCKS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print("saved", OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
