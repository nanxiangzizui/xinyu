# -*- coding: utf-8 -*-
"""P6 破坏性验证：临时改坏一处，跑指定测试确认会红，再原样还原。"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "evidence" / "p6_destructive_2026-11-13.txt"


def run_case(name, rel, old, new, tests):
    path = ROOT / rel
    raw = path.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    assert text.count(old) == 1, "target not unique: " + name
    lines = [name, "file=" + rel, "tests=" + " ".join(tests)]
    try:
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"] + tests,
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        lines.append("returncode=" + str(proc.returncode))
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        lines.extend(tail[-8:])
    finally:
        path.write_bytes(raw)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    lines.append("restored=" + str(before == after))
    lines.append("")
    print("\n".join(lines))
    return "\n".join(lines)


cases = [
    ("#1 L3 短路被注释", "orchestrator.py",
     'if eff_level == "L3":', 'if False and eff_level == "L3":',
     ["tests/test_orchestrator.py::test_l3_short_circuits_before_agent",
      "tests/test_agent_loop.py::test_l3_never_calls_agent"]),
    ("#2 步数预算被改大", "agent_loop.py",
     "AGENT_MAX_STEPS = 3", "AGENT_MAX_STEPS = 99",
     ["tests/test_agent_loop.py::test_default_step_budget_is_three"]),
    ("#3 工具门禁被绕过", "agent_loop.py",
     "if gate is not None:", "if False and gate is not None:",
     ["tests/test_tool_gate.py::test_denied_tool_is_not_executed",
      "tests/test_tool_gate.py::test_gate_error_fails_closed"]),
]

blocks = [run_case(*c) for c in cases]
OUT.write_text("\n".join(blocks), encoding="utf-8")
print("WROTE", OUT)
