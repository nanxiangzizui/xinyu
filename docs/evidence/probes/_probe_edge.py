
# -*- coding: utf-8 -*-
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from guardian import guardian_pre_check as g, CRISIS_REPLY
long = "我" + "今天天气不错" * 500
t0=time.perf_counter(); r=g(long); dt=(time.perf_counter()-t0)*1000
print("D-26 长文本:", len(long), "字 ->", r["level"], r["rule_ids"], f"{dt:.1f}ms")
for kw in ("12356","110","120","0571-87713518"):
    print(kw, kw in CRISIS_REPLY)
print("CRISIS_REPLY 字数:", len(CRISIS_REPLY))
# 空输入 / 纯标点 / 英文
for s in ["", "。。。", "hello", " ", "啊"*2000]:
    rr = g(s)
    print(repr(s[:8]), "->", rr["level"], rr["rule_ids"])
