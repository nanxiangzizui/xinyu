"""P26 探针 3：multiselect(format_func) 在 AppTest 里 select/set_value 的差异。"""
import pathlib
import tempfile

from streamlit.testing.v1 import AppTest

CODE = """
import streamlit as st
opts = ["记忆（概况）", "情景（说过的事）", "测验（分数）"]
picks = st.multiselect("勾选", list(range(3)), format_func=lambda i: opts[i], key="picks")
st.write(picks)
"""

tmp = pathlib.Path(tempfile.mkdtemp()) / "app.py"
tmp.write_text(CODE, encoding="utf-8")


def _run():
    return AppTest.from_file(str(tmp), default_timeout=30).run()


at = _run()
ms = at.multiselect("picks")
print("value:", ms.value, "indices:", ms.indices, "values:", ms.values, "options:", ms.options)
for how in ("select_index", "set_indices", "select_label"):
    at2 = _run()
    m2 = at2.multiselect("picks")
    try:
        if how == "select_index":
            m2.select(0).run()
        elif how == "set_indices":
            m2.set_value([0]).run()
        else:
            m2.select("记忆（概况）").run()
        print(how, "->", at2.multiselect("picks").value, "exc:", list(at2.exception))
    except Exception as exc:  # noqa: BLE001
        print(how, "-> ERROR", type(exc).__name__, exc)
