"""P24 ① 时间感：模型得知道现在几点，否则只会说"早点睡"。"""
import re
from datetime import datetime, timedelta, timezone

import agent
from roles import PERSONAS


def test_now_line_shape():
    """一句话、带星期与分钟、写明北京时间。"""
    line = agent.now_line()
    assert re.match(r"^现在是 \d{4}-\d{2}-\d{2} 周[一二三四五六日] \d{2}:\d{2}（北京时间）。$", line)


def test_now_line_is_utc8_not_local_utc():
    """云上跑 UTC：若直接用 now()，晚上八点会被说成中午。"""
    want = datetime.now(timezone.utc) + timedelta(hours=8)
    # 只比到分钟，避免跨秒时偶尔差 1 分钟；正负 2 分钟都算过。
    m = re.match(r"^现在是 (\d{4}-\d{2}-\d{2}) 周. (\d{2}:\d{2})", agent.now_line())
    got = datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M")
    assert abs((want.replace(second=0, microsecond=0, tzinfo=None) - got).total_seconds()) <= 120


def test_prompt_puts_clock_before_last_reminder():
    """钟点要贴着 [最后提醒]，且五个人设都带。"""
    for pid in PERSONAS:
        prompt = agent.build_system_prompt(pid, {}, [])
        assert "[现在]" in prompt
        assert prompt.index("[现在]") < prompt.index("[最后提醒]")
