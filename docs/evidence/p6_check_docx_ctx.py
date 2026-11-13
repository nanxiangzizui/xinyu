# -*- coding: utf-8 -*-
from docx import Document
doc = Document("docs/01_项目文档.docx")
for ti, t in enumerate(doc.tables):
    for ri, row in enumerate(t.rows):
        cells = [c.text.strip().replace("\n", " / ") for c in row.cells]
        if any("132" in c for c in cells):
            print("table=%d row=%d" % (ti, ri))
            for c in cells:
                print("  | " + c)
