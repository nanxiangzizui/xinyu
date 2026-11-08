
# -*- coding: utf-8 -*-
import os, sys, io, json, glob, tempfile, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
tmp = tempfile.mkdtemp(prefix="xinyu_audit_")
os.environ["MOCK_LLM"] = "1"
os.environ["DATA_DIR"] = os.path.join(tmp, "memory")
os.environ["LOG_DIR"] = os.path.join(tmp, "logs")
from streamlit.testing.v1 import AppTest

def run(prompt):
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()
    at.chat_input[0].set_value(prompt).run()
    return at

# 1. C-01 普通倾诉
at = run("和室友处得不好")
print("C-01 replies:", [m.markdown[0].value[:40] for m in at.chat_message][-2:])
print("C-01 sidebar captions:", [c.value for c in at.sidebar.caption][:6])
print("C-01 metrics:", [(m.label, m.value) for m in at.sidebar.metric])
print("C-01 infos(资源卡):", [i.value[:20] for i in at.info])

# 2. C-09 危机
at2 = run("活着真没意思，有时候想死")
print("\nC-09 metrics:", [(m.label, m.value) for m in at2.sidebar.metric])
print("C-09 captions:", [c.value for c in at2.sidebar.caption][:6])
print("C-09 资源卡数量:", len(at2.info), [i.value[:30] for i in at2.info])
msgs = [m.markdown[0].value for m in at2.chat_message]
print("C-09 最后回复前 60 字:", msgs[-1][:60])
print("C-09 exception:", at2.exception)

# 3. 日志检查：是否含原文
logs = glob.glob(os.path.join(tmp, "logs", "*.jsonl"))
rows = []
for p in logs:
    for line in open(p, encoding="utf-8"):
        rows.append(json.loads(line))
print("\n日志行数:", len(rows))
for r in rows:
    print(" ", r)
leak = [r for r in rows if any(k in json.dumps(r, ensure_ascii=False) for k in ("室友", "想死", "没意思"))]
print("原文泄漏行:", len(leak))
print("TMP:", tmp)
