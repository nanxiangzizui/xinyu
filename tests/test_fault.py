"""test_fault.py — S23：8 条故障注入（F-01 ~ F-08，step/S23 §5.3）。

每条把某个外部边界弄坏，断言系统"不崩且更严"：不抛异常、不把坏内容发出去、
等级不降、日志留痕。只替换边界（call_llm / 磁盘路径 / 环境变量），不改被测逻辑。
"""
from __future__ import annotations

import json
import time

import dotenv
from streamlit.testing.v1 import AppTest

import agent
import memory
import pipeline
from guardian import SAFE_FALLBACK, guardian_post_check
from pipeline import Chat, FALLBACK_LINE, memory_of, memory_path, reply_rows


def test_f01_timeout_becomes_human_line_and_logged(monkeypatch):
    """F-01：生成抛超时 → 一句人话、等级按 L2 记、这一轮在日志里留痕。"""
    assert FALLBACK_LINE in pipeline.app_source()      # 兜底文案与 app.py 同步

    def boom(*args, **kwargs):
        raise TimeoutError()

    monkeypatch.setattr(agent, "call_llm", boom)
    chat = Chat()
    reply = chat.say("我今天很累")
    assert reply == FALLBACK_LINE
    assert chat.state("last_level") == "L2"            # 不按 L1 当“没事”
    assert chat.state("degraded") is True
    row = reply_rows(chat.sid)[-1]
    assert (row["level"], row["action"]) == ("L2", "template_fallback")
    assert row["rule_ids"] == ["PIPELINE_FAILED"]


def test_f02_non_json_reply_is_rechecked_not_crashed(monkeypatch):
    """F-02：模型回的不是 JSON → 复核按失败处理 → 重写一次；全程不崩。"""
    assert agent.safe_json("这不是 JSON") is None

    def plain(messages, temperature=0.7):
        if messages[0]["content"] == agent.REVIEW_SYS:
            return {"text": "我觉得还行", "ok": True, "latency_ms": 1}
        return {"text": "我在听。", "ok": True, "latency_ms": 1}

    monkeypatch.setattr(agent, "call_llm", plain)
    chat = Chat()
    reply = chat.say("今天有点累")
    assert reply == "我在听。"
    row = reply_rows(chat.sid)[-1]
    assert (row["action"], row["rewrite"]) == ("rewrite", 1)


def test_f03_corrupt_memory_self_heals():
    """F-03：主文件写成 {{{ → 从 .bak 救回 / 回默认值，并把主文件补成完整结构。"""
    chat = Chat()
    chat.say("最近考试太多了")
    sid, path = chat.sid, memory_path(chat.sid)
    assert json.loads(path.read_text(encoding="utf-8"))["emotion_tags"] == ["学业"]

    path.write_text("{{{", encoding="utf-8")
    healed = memory.read_memory(sid)
    assert healed["emotion_tags"] == []                    # 坏文件不许原样读回
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert set(on_disk) == set(memory.ALLOWED)             # 主文件已自愈补写
    chat.say("今天天气不错")                               # 之后照常走
    assert memory_of(sid)["emotion_tags"] == []


def test_f04_unwritable_memory_dir_keeps_chat_alive(monkeypatch, tmp_path):
    """F-04：记忆目录建不出来 → 写失败只警告，对话照常完成。"""
    blocked = tmp_path / "blocked"
    blocked.write_text("not a dir", encoding="utf-8")
    monkeypatch.setattr(memory, "DATA_DIR", blocked / "memory")

    chat = Chat()
    reply = chat.say("今天有点累")
    assert reply and reply != FALLBACK_LINE
    assert not (blocked / "memory").exists()
    assert reply_rows(chat.sid)[-1]["action"] == "pass"


def test_f05_unwritable_log_dir_only_warns(monkeypatch, tmp_path, capsys):
    """F-05：日志目录是文件 → 只打一行 WARN，对话照常完成。"""
    fake = tmp_path / "logs-is-a-file"
    fake.write_text("x", encoding="utf-8")
    monkeypatch.setattr(pipeline.logmod, "LOG_DIR", str(fake))

    chat = Chat()
    reply = chat.say("今天有点累")
    assert reply and reply != FALLBACK_LINE
    assert "日志写入失败" in capsys.readouterr().out


def test_f06_missing_key_reports_human_error_not_mock(monkeypatch):
    """F-06：缺 Key 且 MOCK=0 → 启动即报人话并停住，不静默转 mock。"""
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("MOCK_LLM", "0")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    at = AppTest.from_file(pipeline.APP, default_timeout=30)
    at.run()
    assert not list(at.exception)
    assert len(at.chat_input) == 0                        # 输入框都不给
    errors = [el.value for el in at.error]
    assert any("未配置 LLM_API_KEY" in text for text in errors), errors


def test_f07_diagnosis_is_blocked_before_model_review(monkeypatch):
    """F-07：规则先命中就直接重写，不许拿模型的 pass=true 来放行诊断句。"""
    calls = []

    def fake(messages, temperature=0.7):
        head = messages[0]["content"]
        calls.append(head)
        if head == agent.REVIEW_SYS:
            return {"text": '{"pass": true}', "ok": True, "latency_ms": 1}
        return {"text": "我在。慢慢说。", "ok": True, "latency_ms": 1}

    monkeypatch.setattr(agent, "call_llm", fake)
    bad = "你这是抑郁症，建议服药。"
    out = guardian_post_check("我很累", bad, "L1", "listener")
    assert agent.REVIEW_SYS not in calls          # 规则优先：根本没问模型“这句行不行”
    assert out["rewrite"] == 1
    assert "抑郁症" not in (out["fixed_reply"] or "")

    def echo(user_text, reply, reasons, role):
        return bad                     # 重写又被送回诊断句：复检仍要拦

    out2 = guardian_post_check("我很累", bad, "L1", "listener", rewriter=echo)
    assert out2["pass"] is False
    assert out2["template_fallback"] is True
    assert out2["fixed_reply"] == SAFE_FALLBACK["listener"]


def test_f08_5000_chars_does_not_crash_or_hang():
    """F-08：5000 字输入正常处理，不崩不超时。"""
    chat = Chat()
    t0 = time.perf_counter()
    reply = chat.say("啊" * 5000)
    elapsed = time.perf_counter() - t0
    assert reply
    assert reply_rows(chat.sid)[-1]["level"] == "L1"
    assert elapsed < 10
