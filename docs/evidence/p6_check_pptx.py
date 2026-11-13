# -*- coding: utf-8 -*-
"""P6 PPT 自检：页数、每页首行标题、关键数字是否出现（含表格）。"""
from pptx import Presentation

prs = Presentation("docs/02_项目方案.pptx")
print("SLIDES=%d" % len(prs.slides))
all_text = []
for i, slide in enumerate(prs.slides, 1):
    texts = []
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False) and shape.text.strip():
            texts.append(shape.text.strip().replace("\n", " / "))
        if getattr(shape, "has_table", False):
            for row in shape.table.rows:
                texts.append(" | ".join(c.text.strip() for c in row.cells))
    all_text.append("\n".join(texts))
    print("%02d  %s" % (i, texts[0][:70] if texts else "(no text)"))
joined = "\n".join(all_text)
for kw in ["176", "九步", "工具红线", "危机零工具", "11+5+20", "v2.0"]:
    print("HAS_%s=%s" % (kw, kw in joined))
