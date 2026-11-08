"""S18 探针：侧栏面板 8 字段 / 改偏好 / 导出 / 二次确认清空（MOCK，临时目录）。"""
import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
tmp = pathlib.Path(tempfile.mkdtemp(prefix="s18-"))
os.environ["MOCK_LLM"] = "1"
os.environ["DATA_DIR"] = str(tmp / "mem")
os.environ["LOG_DIR"] = str(tmp / "logs")

from streamlit.testing.v1 import AppTest  # noqa: E402
import memory  # noqa: E402
import panel  # noqa: E402

at = AppTest.from_file(str(ROOT / "app.py")).run()
assert not at.exception, at.exception
captions = [c.value for c in at.sidebar.caption]
labels = list(panel.LABELS.values())
assert all(label in captions for label in labels), captions
print("OK 8 labels in sidebar:", len(labels))

at.chat_input[0].set_value("最近考试压力大，我好累").run()
assert not at.exception, at.exception
mem_dir = pathlib.Path(os.environ["DATA_DIR"])
sid = next(mem_dir.glob("*.json")).stem
print("turn=1 sid:", sid, "mem:", json.dumps(memory.read_memory(sid), ensure_ascii=False))

at.sidebar.selectbox[0].select_index(1)          # neutral -> gentle
at.sidebar.text_input[0].set_value("听歌、散步")
at.run()
save = [b for b in at.sidebar.button if b.key and b.key.startswith("panel_save_")][0]
save.click().run()
assert not at.exception, at.exception
saved = memory.read_memory(sid)
assert saved["preferred_tone"] == "gentle", saved
assert saved["coping_preferences"] == ["听歌", "散步"], saved
print("OK save ->", saved["preferred_tone"], saved["coping_preferences"])

payload = panel.export_payload(memory.read_memory(sid))
blob = json.dumps(payload, ensure_ascii=False)
assert "考试压力大" not in blob and "我好累" not in blob
assert set(payload) == set(memory.ALLOWED)
print("OK export keys:", sorted(payload), "bytes:", len(blob))

confirm = [c for c in at.sidebar.checkbox if c.key and c.key.startswith("panel_confirm_")][0]
confirm.check().run()
clear = [b for b in at.sidebar.button if b.key and b.key.startswith("panel_clear_")][0]
clear.click().run()
assert not at.exception, at.exception
assert not (mem_dir / f"{sid}.json").exists()
remain = [p.stem for p in mem_dir.glob("*.json")]
assert remain and remain[0] != sid, remain
fresh = memory.read_memory(remain[0])
assert fresh["preferred_tone"] == "neutral" and fresh["emotion_tags"] == []
print("OK clear -> old gone, new sid:", remain[0], "defaults:", fresh["preferred_tone"])
print("exceptions:", len(at.exception))
