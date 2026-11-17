"""P9i：盲点识别的保守边界（不联网、不碰 Streamlit）。"""
from rolecard_gap import detect_focus, gap_lines, missing_hint, should_fill


def _card(**over):
    card = {
        "origin": "known", "work": "某作品", "name": "青砚",
        "identity": "来自过去的旅人", "setting": "", "voice": "说话轻，句子短",
        "address": "你", "user_role": "用户", "stage": "none",
        "examples": [("在吗", "在。")], "taboos": [], "lore": [],
    }
    card.update(over)
    return card


def test_detect_focus_only_on_explicit_question_shapes():
    """三种句式才认：知道/记得…吗、X 是谁/经历了什么、讲讲 X。"""
    assert detect_focus("你知道白泽经历了什么吗？", _card()) == "白泽"
    assert detect_focus("你记得白泽吗", _card()) == "白泽"
    assert detect_focus("白泽是谁", _card()) == "白泽"
    assert detect_focus("白泽的经历", _card()) == "白泽"
    assert detect_focus("讲讲白泽", _card()) == "白泽"


def test_detect_focus_skips_names_already_in_card():
    """卡里已有的名字不算盲点；否则每轮都会重复联网。"""
    card = _card(lore=["她认识一个叫白泽的人"])
    assert detect_focus("你知道白泽经历了什么吗", card) == ""


def test_detect_focus_skips_generic_words_and_bare_names():
    """普通词、代词、光秃秃的名字都不补，避免误联网。"""
    assert detect_focus("今天有点累", _card()) == ""
    assert detect_focus("白泽", _card()) == ""
    assert detect_focus("白泽和青砚", _card()) == ""
    assert detect_focus("你知道她经历了什么吗", _card()) == ""
    assert detect_focus("你知道这个经历了什么吗", _card()) == ""


def test_should_fill_gates():
    """自动补全的硬条件：已知卡、非 MOCK、非 L3、有专名、开关开。"""
    assert should_fill(_card(), "白泽")
    assert not should_fill(_card(), "白泽", auto=False)
    assert not should_fill(_card(), "白泽", mock=True)
    assert not should_fill(_card(), "白泽", level="L3")
    assert not should_fill(_card(), "")
    assert not should_fill(_card(origin="original"), "白泽")


def test_missing_hint_markers():
    """模型自己说“不认识”时才提示手动补全；普通回复不提示。"""
    assert missing_hint("这个我不太清楚。")
    assert missing_hint("没听说过。")
    assert missing_hint("说不准。")
    assert not missing_hint("我知道这件事。")


def test_gap_lines_keeps_story_world_relationship_and_caps():
    """临时资料只收经历/世界/关系，最多 4 条；身份不塞进来。"""
    facts = [
        {"field": "identity", "text": "身份"},
        {"field": "story", "text": "他在雪原上迷路"},
        {"field": "world", "text": "雪原"},
        {"field": "relationship", "text": "他与青砚守过桥"},
        {"field": "story", "text": "第二件事"},
        {"field": "story", "text": "第三件事"},
        {"field": "story", "text": "第四件事"},
    ]
    lines = gap_lines(facts, focus="白泽")
    assert lines[0] == "白泽的经历：他在雪原上迷路"
    assert "世界：雪原" in lines
    assert "原作关系：他与青砚守过桥" in lines
    assert len(lines) == 4
    assert all("身份" not in line for line in lines)
