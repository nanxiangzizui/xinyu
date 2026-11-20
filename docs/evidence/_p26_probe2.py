"""P26 探针 2：L3 当轮按钮点击与 multiselect.select 的行为。"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from pipeline import Chat  # noqa: E402

chat = Chat()
print("reply:", chat.say("我不想活了")[:20])
at = chat.at
print("mode:", at.session_state["mode"])
print("buttons:", [(b.key, b.label, b.disabled) for b in at.button])
print("success:", [str(e.value) for e in at.success])
at.button("help_open_chat").click().run()
print("after click mode:", at.session_state["mode"], "page:", at.session_state.get("help_page"))
print("exception:", list(at.exception))
print("buttons2:", [(b.key, b.label) for b in at.button])
print("subheader:", [str(e.value) for e in at.subheader][:3])
