"""test_relax_media.py — P17c：呼吸/环境音/计时器的 HTML 约束。"""
from __future__ import annotations

import relax_media


def test_breath_is_paused_until_clicked():
    html = relax_media.breath_html()
    assert "animation-play-state: paused" in html
    assert "prefers-reduced-motion" in html
    assert "吸气 4 秒" in html and "呼气 6 秒" in html
    assert "5 轮" in html


def test_sound_uses_remote_audio_without_autoplay():
    html = relax_media.sound_html()
    assert html.count("<audio") == 3
    assert "preload=\"none\"" in html
    assert "autoplay" not in html.lower()
    assert relax_media.RAIN_URL in html
    assert relax_media.WIND_URL in html
    assert relax_media.WAVES_URL in html
    assert "Wikimedia Commons" in html


def test_sound_has_fade_volume_and_timer_controls():
    html = relax_media.sound_html()
    assert "fadeTo" in html
    assert "type=\"range\"" in html
    assert "300" in html and "600" in html and "900" in html
    assert "没加载出来" in html


def test_timer_does_not_start_by_itself():
    html = relax_media.timer_html(30, "微休息")
    assert "开始 30 秒" in html
    assert "微休息" in html
    assert "setInterval" in html                 # 只在点击回调里创建
    assert "setInterval(() =>" in html
    # 页面加载时不直接调用 start；按钮文案仍是“开始”。
    assert "startBtn.click()" not in html
