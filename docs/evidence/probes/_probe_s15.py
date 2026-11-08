# -*- coding: utf-8 -*-
"""S15 证据探针：说教句 → 重写（日志 rule_ids 含 SAYING、rewrite=1）；干净句原样通过。"""
import io, json, os, sys, tempfile, pathlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
os.environ["MOCK_LLM"] = "1"
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

tmp = pathlib.Path(tempfile.mkdtemp())
import memory, logger, agent
memory.DATA_DIR = tmp / "mem"
logger.LOG_DIR = tmp / "logs"


def dispatcher(gen_text, review_json, rewrite_text):
    calls = []

    def fake(messages, temperature=0.7):
        head = messages[0]["content"]
        kind = ("review" if head == agent.REVIEW_SYS
                else "rewrite" if head == agent.REWRITE_SYS else "gen")
        calls.append((kind, temperature))
        text = {"gen": gen_text, "review": review_json, "rewrite": rewrite_text}[kind]
        return {"text": text, "ok": True, "error": "", "latency_ms": 0}

    return fake, calls


def run_once(text, fake):
    agent.call_llm = fake
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.chat_input[0].set_value(text).run()
    rows = [json.loads(l) for f in (tmp / "logs").glob("*.jsonl")
            for l in f.read_text(encoding="utf-8").splitlines()]
    return at, rows[-1] if rows else {}


# ① 说教句：pre_check 无命中，但 SAYING 命中 → 只重写，不升级、不兜底
fake, calls = dispatcher("你应该早点睡。", '{"pass": true}', "听着挺累的，先歇会儿吧。")
at, row = run_once("我好累", fake)
sent = at.session_state["messages"][-1]["content"]
print("① exceptions:", len(at.exception))
print("① calls:", calls)                      # 期望只有 gen + rewrite，没有 review
print("① 发出的句子:", repr(sent))
print("① 日志:", row)
print("① level / action / rewrite:", row.get("level"), row.get("action"), row.get("rewrite"))
print("① rule_ids 含 SAYING:", "SAYING" in row.get("rule_ids", []))
print("① 说教句是否发出:", "你应该" in sent)
print("① 原文泄漏:", "我好累" in json.dumps(row, ensure_ascii=False))

# ② 干净回复：复核 pass → 原样通过，不重写
fake2, calls2 = dispatcher("听起来今天挺耗人的。", '{"pass": true, "reason": ""}', "不该用到")
at2, row2 = run_once("今天有点累", fake2)
print("② exceptions:", len(at2.exception))
print("② calls:", calls2)
print("② 日志:", row2)
print("② rule_ids:", row2.get("rule_ids"))

# ③ 五卡 taboos 注入（体验层）
print("③ taboos:", {pid: card["taboos"] for pid, card in agent.PERSONAS.items()})
print("③ 学长卡提示词片段:", [ln for ln in
      agent.build_system_prompt("warm_senpai", {}, []).splitlines() if "不要这样说" in ln])
