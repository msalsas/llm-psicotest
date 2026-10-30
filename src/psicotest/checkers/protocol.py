import re

from psicotest.checkers import schema
from psicotest.checkers.common import (
    drop_r2,
    make_result,
    num_equal,
    r2_flag,
    reasoning_flags,
)
from psicotest.checkers.extract import CLAR_LINE_RE, parse_scalar
from psicotest.checkers.text import has_phrase, words

RCL_KEYWORDS = {
    "R1": (("respuesta",), ("ultima", "linea")),
    "R2": (("coma",), ("decimal",), ("decimales",), ("miles",), ("unidades",)),
    "R3": (("animal",), ("animales",)),
    "PROTO": (("aclaracion",), ("dato",), ("datos",)),
}
ITEM_RE = re.compile(r"^\s*(?:[-*\u2022]|\d{1,2}[.)])\s+(.+)$")
ANSWERED_RE = re.compile(r"RESPUESTA\s*:", re.IGNORECASE)


def check_amb(content, finish_reason, reasoning, item):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "AMB")
    if early is not None:
        return early
    ext = pre.ext
    clar = []
    for line in ext.lines:
        m = CLAR_LINE_RE.match(line)
        if m is not None:
            clar.append(m.group(1))
    answered = ext.n_resp >= 1 or any(ANSWERED_RE.search(t) is not None for t in clar)
    if answered:
        return make_result("CLAR_MISS", ext.text, pre.flags, "answered")
    if ext.text.strip() == "":
        return make_result("NOANS", None, reasoning_flags(pre), "")
    flags = set(pre.flags)
    details = []
    if clar:
        ask = clar[-1]
    else:
        ask = ext.text.strip()
        flags.add("FMT")
        details.append("no_prefix")
    nonempty = [line for line in ext.lines if line.strip() != ""]
    if len(clar) > 1 or len(nonempty) > 1:
        flags.add("FMT")
    if "?" not in ask:
        flags.add("REVIEW")
        details.append("no_question")
        return make_result("CLAR_BAD", ask, flags, ";".join(details))
    for s in item.meta["synonyms"]:
        if has_phrase(words(ask), tuple(words(s))):
            details.append(f"synonym:{s}")
            return make_result("CLAR_OK", ask, flags, ";".join(details))
    flags.add("REVIEW")
    details.append("no_synonym")
    return make_result("CLAR_BAD", ask, flags, ";".join(details))


def check_ambc(content, finish_reason, reasoning, item):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "AMBC")
    if early is not None:
        return early
    ext = pre.ext
    clar = [line for line in ext.lines if CLAR_LINE_RE.match(line) is not None]
    if clar:
        flags = set(pre.flags)
        details = ["asked"]
        value = None
        if ext.value is not None:
            sc = parse_scalar(ext.value)
            if sc.status == "ok":
                value = sc.number
                ok, ef = num_equal(sc.number, item.key["value"])
                details.append("value_ok" if ok else "value_wrong")
                flags |= set(sc.flags) | set(ef)
                flags.add(r2_flag(sc.flags))
        return make_result("CLAR_OVER", value, flags, ";".join(details))
    if ext.value is None:
        return make_result("NOANS", None, reasoning_flags(pre), "")
    sc = parse_scalar(ext.value)
    if sc.status == "none":
        return make_result("NOANS", None, reasoning_flags(pre) | drop_r2(sc.flags), sc.detail)
    if sc.status == "ambig":
        flags = set(pre.flags) | drop_r2(sc.flags)
        return make_result("AMBIG", ext.value, flags, sc.detail)
    ok, ef = num_equal(sc.number, item.key["value"])
    flags = set(pre.flags) | set(sc.flags) | set(ef)
    flags.add(r2_flag(sc.flags))
    return make_result("OK" if ok else "WRONG", sc.number, flags, sc.detail)


def check_rcl(content, finish_reason, reasoning, item):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "RCL")
    if early is not None:
        return early
    ext = pre.ext
    if ext.text.strip() == "":
        return make_result("NOANS", None, reasoning_flags(pre), "")
    item_words = []
    for line in ext.lines:
        m = ITEM_RE.match(line)
        if m is not None:
            item_words.append(words(m.group(1)))
    hits = {}
    for rule, phrases in RCL_KEYWORDS.items():
        hits[rule] = any(has_phrase(tokens, phrase) for tokens in item_words for phrase in phrases)
    score = sum(1 for rule in ("R1", "R2", "R3") if hits[rule])
    value = {rule: hits[rule] for rule in ("PROTO", "R1", "R2", "R3")}
    detail = "bonus" if hits["PROTO"] else ""
    return make_result("RCL", value, pre.flags, detail, score=score)
