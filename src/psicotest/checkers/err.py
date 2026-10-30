import re

from psicotest.checkers import schema
from psicotest.checkers.common import make_result, r2_flag, reasoning_flags
from psicotest.checkers.extract import parse_number

STEP_RE = re.compile(r"PASO\s*[:=]?\s*(\d+)", re.IGNORECASE)
VALUE_RE = re.compile(r"VALOR\s*[:=]?\s*([+-]?\d(?:[\d.,]*\d)?)", re.IGNORECASE)


def check_err(content, finish_reason, reasoning, item):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "ERR")
    if early is not None:
        return early
    if pre.ext.value is None:
        return make_result("NOANS", None, reasoning_flags(pre), "")
    value = pre.ext.value
    steps = list(STEP_RE.finditer(value))
    if not steps:
        return make_result("NOANS", None, reasoning_flags(pre), "no_step")
    first = steps[0]
    vmatch = VALUE_RE.search(value, first.end())
    if len(steps) >= 2:
        return make_result("AMBIG", value, pre.flags, "multi_step")
    end = vmatch.start() if vmatch is not None else len(value)
    if any(ch.isdigit() for ch in value[first.end() : end]):
        return make_result("AMBIG", value, pre.flags, "multi_step")
    step = int(first.group(1))
    flags = set(pre.flags)
    parsed = None
    value_ok = None
    if vmatch is None:
        detail = "value_missing"
    else:
        parsed, pflags = parse_number(vmatch.group(1))
        if parsed is None:
            detail = "value_ambig"
        else:
            value_ok = parsed == item.key["value"]
            detail = "value_ok" if value_ok else "value_wrong"
            flags.add(r2_flag(pflags))
    result_value = {"step": step, "value": parsed, "value_ok": value_ok}
    outcome = "OK" if step == item.key["step"] else "WRONG"
    return make_result(outcome, result_value, flags, detail)
