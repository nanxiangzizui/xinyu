"""relax_media.py — 呼吸、环境音与 30 秒计时器的自包含 HTML。

全部走 streamlit.components.v1.html：不新增依赖、不写音频文件、不自动播放。
环境音用 Wikimedia Commons 的公开音频 URL，由浏览器在用户点击后才加载；
服务端不替用户取音频，也不把 URL 交给模型。
"""
from __future__ import annotations

import streamlit.components.v1 as components

RAIN_URL = "https://upload.wikimedia.org/wikipedia/commons/0/0e/Rain_%281%29.ogg"
WIND_URL = ("https://upload.wikimedia.org/wikipedia/commons/1/1d/"
            "Strong_winds_before_the_Rain.ogg")
WAVES_URL = ("https://upload.wikimedia.org/wikipedia/commons/7/73/"
             "On_a_pebble_beach.ogg")

BREATH_HTML = """
<div class="wrap">
  <div id="circle"></div>
  <div id="phase">准备好就开始</div>
  <div id="count">5 轮，随时可以停</div>
  <button id="toggle">开始</button>
  <p class="hint">吸气 4 秒，呼气 6 秒；不用屏息，跟不上就按自己的节奏。</p>
</div>
<style>
  .wrap { font-family: system-ui, sans-serif; text-align: center; padding: 8px; }
  #circle { width: 96px; height: 96px; margin: 8px auto; border-radius: 50%;
            background: #b7d6c4; animation: breathe 10s ease-in-out infinite;
            animation-play-state: paused; }
  @keyframes breathe { 0%,100% { transform: scale(.72); } 40% { transform: scale(1.12); }
                       100% { transform: scale(.72); } }
  #phase { font-size: 1.05rem; color: #315347; margin-top: 4px; }
  #count { font-size: .85rem; color: #6b7f76; margin: 4px 0 10px; }
  button { border: 1px solid #7da994; background: #eef7f2; color: #24463a;
           border-radius: 999px; padding: 7px 22px; cursor: pointer; }
  .hint { font-size: .8rem; color: #6b7f76; margin: 10px 0 0; line-height: 1.5; }
</style>
<script>
  const circle = document.getElementById("circle");
  const phase = document.getElementById("phase");
  const count = document.getElementById("count");
  const toggle = document.getElementById("toggle");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let running = false, rounds = 0;
  if (reduce) { circle.style.animation = "none"; phase.textContent = "按自己的节奏呼吸"; }
  circle.addEventListener("animationiteration", () => {
    rounds += 1;
    count.textContent = rounds >= 5 ? "5 轮到了，可以停，也可以再来" : `第 ${rounds} / 5 轮`;
    if (rounds >= 5) { stop(); }
  });
  function stop() {
    running = false;
    circle.style.animationPlayState = "paused";
    toggle.textContent = "继续";
    phase.textContent = "停一下也没关系";
  }
  toggle.addEventListener("click", () => {
    if (running) { stop(); return; }
    if (rounds >= 5) { rounds = 0; count.textContent = "5 轮，随时可以停"; }
    running = true;
    circle.style.animationPlayState = "running";
    toggle.textContent = "暂停";
    phase.textContent = "吸气 4 秒 · 呼气 6 秒";
  });
</script>
"""

SOUND_HTML = """
<div class="wrap">
  <div class="row">
    <button data-a="rain">雨</button>
    <button data-a="wind">风</button>
    <button data-a="waves">海浪</button>
    <button id="stop">停止</button>
  </div>
  <label>音量 <input id="vol" type="range" min="0" max="100" value="35"></label>
  <label>定时
    <select id="timer">
      <option value="0">不限</option>
      <option value="300">5 分钟</option>
      <option value="600">10 分钟</option>
      <option value="900">15 分钟</option>
    </select>
  </label>
  <div id="msg">默认是静的，点一个声音才会开始。</div>
  <div class="credit">雨 / 海浪：Public domain；风：CC BY-SA 4.0；来源 Wikimedia Commons。</div>
</div>
<audio id="rain" src="__RAIN__" loop preload="none"></audio>
<audio id="wind" src="__WIND__" loop preload="none"></audio>
<audio id="waves" src="__WAVES__" loop preload="none"></audio>
<style>
  .wrap { font-family: system-ui, sans-serif; color: #315347; padding: 6px; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
  button { border: 1px solid #7da994; background: #eef7f2; color: #24463a;
           border-radius: 999px; padding: 6px 18px; cursor: pointer; }
  label { font-size: .85rem; margin-right: 14px; }
  input[type=range] { vertical-align: middle; width: 110px; }
  #msg { font-size: .82rem; color: #6b7f76; margin-top: 8px; min-height: 20px; }
  .credit { font-size: .72rem; color: #8a9a92; margin-top: 6px; }
</style>
<script>
  const audios = { rain: document.getElementById("rain"),
                   wind: document.getElementById("wind"),
                   waves: document.getElementById("waves") };
  const vol = document.getElementById("vol");
  const msg = document.getElementById("msg");
  const timer = document.getElementById("timer");
  let current = null, fade = null, stopTimer = null;
  function fadeTo(a, target) {
    clearInterval(fade);
    fade = setInterval(() => {
      const step = target > a.volume ? 0.05 : -0.05;
      a.volume = Math.max(0, Math.min(1, a.volume + step));
      if (Math.abs(a.volume - target) < 0.06) { a.volume = target; clearInterval(fade); }
    }, 80);
  }
  function stopAll() {
    Object.values(audios).forEach(a => { a.pause(); a.currentTime = 0; });
    clearInterval(fade);
    clearTimeout(stopTimer);
    current = null;
    msg.textContent = "已经停了。";
  }
  document.querySelectorAll("button[data-a]").forEach(btn => {
    btn.addEventListener("click", () => {
      const a = audios[btn.dataset.a];
      Object.values(audios).forEach(x => { x.pause(); x.currentTime = 0; });
      clearTimeout(stopTimer);
      current = a;
      a.volume = 0;
      a.play().then(() => {
        fadeTo(a, Number(vol.value) / 100);
        msg.textContent = "正在播放，可以随时停。";
        const sec = Number(timer.value);
        if (sec) stopTimer = setTimeout(() => {
          a.pause(); msg.textContent = "时间到了，声音已经停了。";
        }, sec * 1000);
      }).catch(() => {
        msg.textContent = "这段声音没加载出来，换一个试试，或者先听身边的声音。";
      });
    });
  });
  vol.addEventListener("input", () => {
    if (current) current.volume = Number(vol.value) / 100;
  });
  document.getElementById("stop").addEventListener("click", stopAll);
</script>
"""

TIMER_HTML = """
<div class="wrap">
  <div id="clock">__SECONDS__</div>
  <div class="label">__LABEL__</div>
  <button id="start">开始 __SECONDS__ 秒</button>
  <button id="reset">重置</button>
  <p class="hint">不是任务，时间到了就停；想继续也可以再按一次。</p>
</div>
<style>
  .wrap { font-family: system-ui, sans-serif; text-align: center; padding: 8px; }
  #clock { font-size: 2.6rem; color: #315347; line-height: 1.1; }
  .label { color: #6b7f76; margin: 2px 0 10px; }
  button { border: 1px solid #7da994; background: #eef7f2; color: #24463a;
           border-radius: 999px; padding: 7px 16px; margin: 0 4px; cursor: pointer; }
  .hint { font-size: .8rem; color: #6b7f76; margin-top: 10px; }
</style>
<script>
  const clock = document.getElementById("clock");
  const total = __SECONDS__, startBtn = document.getElementById("start");
  let left = total, tick = null;
  function paint() { clock.textContent = left; }
  function stop() { clearInterval(tick); tick = null; startBtn.textContent = "继续"; }
  startBtn.addEventListener("click", () => {
    if (tick) { stop(); return; }
    if (left <= 0) left = total;
    startBtn.textContent = "暂停";
    tick = setInterval(() => {
      left -= 1; paint();
      if (left <= 0) { stop(); clock.textContent = "到"; }
    }, 1000);
  });
  document.getElementById("reset").addEventListener("click", () => {
    stop(); left = total; paint(); startBtn.textContent = "开始 __SECONDS__ 秒";
  });
</script>
"""


def breath_html() -> str:
    """4 秒吸 / 6 秒呼的呼吸圈；默认暂停，用户点开始才动。"""
    return BREATH_HTML


def sound_html() -> str:
    """雨 / 风 / 海浪三段环境音；默认静音，点击才加载、才播放。"""
    return (SOUND_HTML.replace("__RAIN__", RAIN_URL)
            .replace("__WIND__", WIND_URL)
            .replace("__WAVES__", WAVES_URL))


def timer_html(seconds: int = 30, label: str = "微休息") -> str:
    """不自动开始的倒计时；只用于 30 秒微休息。"""
    return (TIMER_HTML.replace("__SECONDS__", str(seconds))
            .replace("__LABEL__", label))


def render_breath(height: int = 280) -> None:
    """在页面里放呼吸组件；调用方负责标题与退出按钮。"""
    components.html(breath_html(), height=height)


def render_sound(height: int = 250) -> None:
    """在页面里放环境音组件。"""
    components.html(sound_html(), height=height)


def render_timer(seconds: int = 30, label: str = "微休息") -> None:
    """在页面里放倒计时组件。"""
    components.html(timer_html(seconds, label), height=210)
