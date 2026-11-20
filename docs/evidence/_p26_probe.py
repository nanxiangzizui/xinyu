"""P26 探针：两页求助 + about 页在 AppTest 里能取到哪些元素。"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from pipeline import Chat  # noqa: E402


def show(name, at):
    print(f"--- {name} mode={at.session_state.get('mode')} page={at.session_state.get('help_page')}")
    for kind in ("subheader", "markdown", "info", "caption", "code", "success", "error", "text"):
        els = getattr(at, kind, None)
        if els is None:
            print(f"  {kind}: <none>")
            continue
        for el in list(els)[:4]:
            print(f"  {kind}: {str(getattr(el, 'value', ''))[:70]!r}")
    print("  buttons:", [b.key for b in at.button])
    print("  chat_input:", len(at.chat_input))


at = Chat(enter=False).at
print("home buttons:", [b.key for b in at.button])
show("home", at)
at.button("home_help_self").click().run()
show("help_self", at)
at.button("help_home").click().run()
at.button("home_help_friend").click().run()
show("help_friend", at)
at.button("help_home").click().run()
at.button("home_about").click().run()
show("about", at)
print("multiselect:", [(m.key, list(m.options)) for m in at.multiselect])
print("checkbox:", [(c.key, c.value) for c in at.checkbox])
print("buttons:", [(b.key, b.label) for b in at.button])
