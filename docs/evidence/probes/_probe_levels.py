# -*- coding: utf-8 -*-
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from guardian import guardian_pre_check
for s in ("没意思", "今天吃什么", "我好累", "没意思，什么都不想干", "最近什么都提不起劲"):
    print(ascii(s), guardian_pre_check(s))
