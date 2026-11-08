"""contract_check.py — 11 个签名 + 5 个常量，一次校验。"""
from __future__ import annotations
import importlib
import inspect
import sys

import roles

EMPTY = inspect.Parameter.empty
SPEC = {
    "memory.read_memory": [("session_id", EMPTY)],
    "memory.write_memory": [("session_id", EMPTY), ("data", EMPTY)],
    "memory.update_memory": [("session_id", EMPTY), ("user_text", EMPTY), ("reply", EMPTY)],
    "memory.clear_memory": [("session_id", EMPTY)],
    "memory.match_lore": [("user_text", EMPTY), ("session_id", "")],
    "agent.call_llm": [("messages", EMPTY), ("temperature", 0.7)],
    "agent.build_system_prompt": [("persona_id", EMPTY), ("memory", EMPTY), ("lore", EMPTY)],
    "coordinator.coordinator_decide": [("memory", EMPTY), ("user_text", EMPTY), ("level", EMPTY)],
    "guardian.guardian_pre_check": [("user_text", EMPTY)],
    "guardian.guardian_post_check": [("user_text", EMPTY), ("reply", EMPTY),
                                     ("level", EMPTY), ("role", EMPTY), ("rewriter", None)],
    "resources.pick_resources": [("level", EMPTY), ("emotion_tags", EMPTY)],
}
CONSTS = {"TIMEOUT": 15, "N_WINDOW": 5, "COOLDOWN": 3, "SUMMARY_MAX": 200, "SUMMARY_EVERY": 5}


def check_one(name: str, expect: list) -> str | None:
    """通过返回 None；不通过返回一句人话。只比参数名/顺序/默认值，不比注解。"""
    mod_name, fn_name = name.split(".")
    try:
        fn = getattr(importlib.import_module(mod_name), fn_name)
    except Exception as exc:                       # 边界：模块或函数缺失
        return f"取不到函数（{exc.__class__.__name__}）"
    params = list(inspect.signature(fn).parameters.values())
    if len(params) != len(expect):
        return f"参数个数 {len(params)} != {len(expect)}"
    for got, (want_name, want_default) in zip(params, expect):
        if got.name != want_name:
            return f"参数名 {got.name} != {want_name}"
        if (got.default is EMPTY) != (want_default is EMPTY):
            return f"{want_name} 有没有默认值不一致"
        if want_default is not EMPTY and got.default != want_default:
            return f"{want_name} 默认值 {got.default!r} != {want_default!r}"
    return None


def main() -> int:
    bad = 0
    for name, expect in SPEC.items():
        err = check_one(name, expect)
        if err:
            bad += 1
            print(f"FAIL {name}: {err}")
    print(f"{len(SPEC) - bad}/{len(SPEC)} signatures OK")

    const_bad = [k for k, v in CONSTS.items() if getattr(roles, k, object()) != v]
    for k in const_bad:
        print(f"FAIL roles.{k}: 期望 {CONSTS[k]} 实际 {getattr(roles, k, '缺失')!r}")
    print(f"{len(CONSTS) - len(const_bad)}/{len(CONSTS)} constants OK")

    rule_errors = roles.validate_rules()
    if rule_errors:
        print("RULES FAIL:")
        for err in rule_errors:
            print(" -", err)
    else:
        print(f"{len(roles.RULES)}/{roles.N_RULES} rules OK")
    return 1 if bad or const_bad or rule_errors else 0


if __name__ == "__main__":
    sys.exit(main())
