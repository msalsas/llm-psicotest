"""Checker for PC (prose_consistency) items.

Scoring rule (T5D D5): unparseable, incorrect and inconsistent are failures;
missing_twin_context is not a failure by itself, so variant pc2 passes when it
is correct and does not contradict a parseable twin answer. Variant pc1 is
scored on correctness only. The twin answer is found by scanning the prior
slot->content mapping for exactly the sibling slot id carried in item.meta["twin_slot"].
"""

from psicotest.checkers import schema
from psicotest.checkers.common import make_result, reasoning_flags
from psicotest.checkers.extract import extract_answer


def _parse_yes_no(text: str | None) -> str | None:
    if text is None:
        return None
    word = text.strip().casefold()
    return word if word in ("yes", "no") else None


def _twin_answer(item, prior: dict[str, str] | None) -> str | None:
    twin_slot = item.meta.get("twin_slot")
    if not prior or twin_slot is None or twin_slot not in prior:
        return None
    return _parse_yes_no(extract_answer(prior[twin_slot]).value)


def check_pc(content, finish_reason, reasoning, item, prior=None):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "PC")
    if early is not None:
        return early
    if pre.ext.value is None:
        return make_result("NOANS", None, reasoning_flags(pre), "")
    answer = _parse_yes_no(pre.ext.value)
    if answer is None:
        return make_result(
            "WRONG", pre.ext.value, reasoning_flags(pre) | {"FMT", "R2_FAIL"}, "unparseable"
        )
    flags = set(pre.flags)
    flags.add("R2_OK")
    details = []
    if answer != item.key["value"].lower():
        details.append("incorrect")
    if item.variant == "pc2":
        twin = _twin_answer(item, prior)
        if twin is None:
            details.append("missing_twin_context")
        elif twin != answer:
            details.append("inconsistent")
    failed = {"incorrect", "inconsistent"} & set(details)
    outcome = "OK" if not failed else "WRONG"
    return make_result(outcome, answer, flags, ";".join(details))
