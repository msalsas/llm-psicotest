from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from psicotest.checkers.cjk import has_leak
from psicotest.checkers.extract import (
    CLAR_LINE_RE,
    RESP_LINE_RE,
    Extraction,
    extract_answer,
    fold,
    preclean,
)
from psicotest.checkers.telemetry import has_loop
from psicotest.spec import CheckResult

CAPABILITY_FAMILIES = ("ST", "AR", "AR2", "NOOP", "CSP", "LOG", "CNT", "ERR", "FPRE", "SYP", "IC")
PROTOCOL_FAMILIES = ("AMB", "AMBC", "RCL")
R2_FAMILIES = ("ST", "AR", "AR2", "NOOP", "CNT", "ERR", "FPRE", "SYP", "AMBR", "AMBC")
OUTCOMES = (
    "OK",
    "WRONG",
    "PREMISE_ABSORBED",
    "FLIPPED",
    "WRONG_OTHER",
    "NOANS",
    "AMBIG",
    "TRUNC",
    "CLAR_OK",
    "CLAR_MISS",
    "CLAR_OVER",
    "CLAR_BAD",
    "GEN_BUG",
    "RCL",
)
FLAG_ORDER = (
    "MULTI",
    "LEAK",
    "FMT",
    "REASONING_ONLY",
    "LOOP",
    "PREMISE_NOTED",
    "REVIEW",
    "R2_OK",
    "R2_FAIL",
)
ANSWER_KINDS = {
    "ST": "keys",
    "AR": "int",
    "AR2": "dec2",
    "NOOP": "num",
    "CSP": "assignment",
    "LOG": "roles",
    "CNT": "int",
    "ERR": "step_value",
    "FPRE": "int",
    "SYP": "int",
    "IC": "list",
    "AMB": "clar",
    "AMBC": "num",
    "RCL": "recall",
    "SETUP": "ack",
}
HALF_CENT = Fraction(1, 200)

_TRUNC_FLAGS = frozenset(("LEAK", "LOOP"))
_R2_FLAGS = frozenset(("R2_OK", "R2_FAIL"))


class ItemSchemaError(ValueError):
    pass


def make_result(
    outcome: str,
    value: object,
    flags: Iterable[str],
    detail: str,
    score: int | None = None,
) -> CheckResult:
    if outcome not in OUTCOMES:
        raise ValueError("unknown outcome")
    fs = frozenset(flags)
    if any(f not in FLAG_ORDER for f in fs):
        raise ValueError("unknown flag")
    if score is not None and outcome != "RCL":
        raise ValueError("score only allowed for RCL")
    if outcome == "RCL":
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 3:
            raise ValueError("RCL needs an int score in 0..3")
    elif score is None:
        score = 1 if outcome in ("OK", "CLAR_OK") else 0
    return CheckResult(outcome, score, value, tuple(f for f in FLAG_ORDER if f in fs), detail)


@dataclass(frozen=True)
class Prepared:
    ext: Extraction
    flags: frozenset[str]
    trunc: bool
    reasoning_only: bool


def prepare(content: str | None, finish_reason: str | None, reasoning: str | None) -> Prepared:
    if content is not None and not isinstance(content, str):
        raise TypeError("content must be str or None")
    if reasoning is not None and not isinstance(reasoning, str):
        raise TypeError("reasoning must be str or None")
    ext = extract_answer(content)
    trunc = finish_reason == "length"
    flags = set()
    if has_leak(content):
        flags.add("LEAK")
    if has_loop(content) or has_loop(reasoning):
        flags.add("LOOP")
    if not trunc:
        if ext.multi:
            flags.add("MULTI")
        if ext.value is not None and has_leak(ext.value):
            flags.add("FMT")
    reasoning_only = ext.text.strip() == "" and any(
        RESP_LINE_RE.match(line) is not None or CLAR_LINE_RE.match(line) is not None
        for line in preclean(reasoning).split("\n")
    )
    return Prepared(ext, frozenset(flags), trunc, reasoning_only)


def r2_flag(flags: Iterable[str]) -> str:
    return "R2_FAIL" if "R2_FAIL" in flags else "R2_OK"


def drop_r2(flags: Iterable[str]) -> frozenset[str]:
    return frozenset(flags) - _R2_FLAGS


def resolve(token, people):
    folded = fold(token)
    for person in people:
        if fold(person) == folded:
            return person
    if len(folded) == 1:
        matches = [person for person in people if fold(person).startswith(folded)]
        if len(matches) == 1:
            return matches[0]
    return None


def num_equal(x: Decimal, key: int | Decimal) -> tuple[bool, frozenset[str]]:
    fx = Fraction(x)
    fk = Fraction(key)
    if isinstance(key, int):
        ok = fx == fk
        if ok and x.as_tuple().exponent < 0:
            return True, frozenset({"FMT"})
        return ok, frozenset()
    if x.as_tuple().exponent >= -2 or (fx * 100).denominator == 1:
        return fx == fk, frozenset()
    ok = abs(fx - fk) < HALF_CENT
    return ok, frozenset({"FMT"}) if ok else frozenset()


def trunc_flags(flags: Iterable[str]) -> frozenset[str]:
    return frozenset(flags) & _TRUNC_FLAGS


def reasoning_flags(pre: Prepared) -> set[str]:
    flags = set(pre.flags)
    if pre.reasoning_only:
        flags.add("REASONING_ONLY")
    return flags
