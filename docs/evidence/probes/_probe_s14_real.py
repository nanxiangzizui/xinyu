# -*- coding: utf-8 -*-
"""S14 真实模型耗时：一次复核 + 一次重写，验证总耗时 < 6 秒。"""
import io, os, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
os.environ.pop("MOCK_LLM", None)
sys.path.insert(0, __import__("pathlib").Path(__file__).resolve().parents[3].as_posix())

import guardian

t0 = time.monotonic()
rv = guardian.llm_review("今天有点累，什么都不想做。", "听起来今天挺耗人的。", "L1")
t1 = time.monotonic()
print("复核:", rv, "%.2fs" % (t1 - t0))

t2 = time.monotonic()
rw = guardian.llm_rewrite("今天有点累，什么都不想做。", "你应该振作起来，多运动就好了。",
                          ["说教"], "listener")
t3 = time.monotonic()
print("重写:", repr(rw), "%.2fs" % (t3 - t2))
print("合计: %.2fs" % (t3 - t0))
