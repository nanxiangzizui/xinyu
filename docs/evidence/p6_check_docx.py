# -*- coding: utf-8 -*-
"""P6 文档自检：抽取 docx 全文，打印禁词与旧数字上下文。"""
from docx import Document

PATH = "docs/01_项目文档.docx"
BLOCKS = ["多智能体", "多模态", "有效缓解焦虑", "AI 心理医生", "心理医生",
          "你得了", "倾向", "你可能是抑郁", "132", "1,962", "12 个 Python",
          "七步", "v1.0"]


def all_text(doc):
    for p in doc.paragraphs:
        if p.text.strip():
            yield p.text.strip()
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if p.text.strip():
                        yield p.text.strip()


doc = Document(PATH)
texts = list(all_text(doc))
print("paragraphs=%d tables=%d text_blocks=%d" % (len(doc.paragraphs), len(doc.tables), len(texts)))
for kw in BLOCKS:
    hits = [t for t in texts if kw in t]
    print("\n[%s] hits=%d" % (kw, len(hits)))
    for t in hits[:8]:
        print("  ..." + t[:160].replace("\n", " ") + "...")
