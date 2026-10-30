import re
from fractions import Fraction

from psicotest.checkers import schema
from psicotest.checkers.common import make_result, r2_flag, reasoning_flags, resolve
from psicotest.checkers.extract import parse_scalar
from psicotest.checkers.text import fold

PAIR_RE = re.compile(r"^(?:caja\s+)?([^\W_]\w*)\s*[=:]\s*(.+?)$", re.IGNORECASE)
SPLIT_RE = re.compile(r"[;,]")


def _segments(value):
    return [seg.strip() for seg in SPLIT_RE.split(value) if seg.strip() != ""]


def _pairs(value):
    pairs = []
    strays = 0
    for seg in _segments(value):
        m = PAIR_RE.match(seg)
        if m is None:
            strays += 1
        else:
            pairs.append((m.group(1), m.group(2)))
    return pairs, strays


def check_st(content, finish_reason, reasoning, item):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "ST")
    if early is not None:
        return early
    if pre.ext.value is None:
        return make_result("NOANS", None, reasoning_flags(pre), "")
    key = item.key["boxes"]
    pairs, strays = _pairs(pre.ext.value)
    flags = set(pre.flags)
    details = []
    if strays:
        flags.add("FMT")
        details.append("stray")
    if not pairs:
        return make_result("NOANS", None, flags, "no_pairs")
    parsed = []
    for raw_label, raw_value in pairs:
        parsed.append((raw_label.upper(), parse_scalar(raw_value, allow_eq=False)))
    key_parsed = [(label, sc) for label, sc in parsed if label in key]
    for label, _sc in key_parsed:
        same = [sc2 for label2, sc2 in key_parsed if label2 == label]
        if len(same) > 1:
            first = same[0]
            if any(s.status != first.status or s.number != first.number for s in same[1:]):
                details.append(f"conflict:{label}")
                return make_result("AMBIG", pre.ext.value, flags, ";".join(details))
    for label, sc in key_parsed:
        if sc.status != "ok":
            details.append(f"bad_value:{label}")
            return make_result("AMBIG", pre.ext.value, flags, ";".join(details))
    found = {label: sc.number for label, sc in key_parsed}
    union = set()
    parsed_ok = False
    for _label, sc in key_parsed:
        union |= set(sc.flags)
        if sc.status == "ok":
            parsed_ok = True
    flags |= union
    if parsed_ok:
        flags.add(r2_flag(union))
    missing = sorted(label for label in key if label not in found)
    if missing:
        details.append("missing:" + ",".join(missing))
        return make_result("WRONG", found, flags, ";".join(details))
    bad = sorted(label for label in key if Fraction(found[label]) != Fraction(key[label]))
    if bad:
        details.append("mismatch:" + ",".join(bad))
        return make_result("WRONG", found, flags, ";".join(details))
    return make_result("OK", found, flags, ";".join(details))


def check_csp(content, finish_reason, reasoning, item):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "CSP")
    if early is not None:
        return early
    if pre.ext.value is None:
        return make_result("NOANS", None, reasoning_flags(pre), "")
    meta = item.meta
    people = tuple(meta["people"])
    n_slots = meta["n_slots"]
    key = item.key["assignment"]
    pairs, strays = _pairs(pre.ext.value)
    flags = set(pre.flags)
    details = []
    if strays:
        flags.add("FMT")
        details.append("stray")
    if not pairs:
        return make_result("NOANS", None, flags, "no_pairs")
    bound = []
    for raw_name, raw_value in pairs:
        person = resolve(raw_name, people)
        bound.append((raw_name, person, parse_scalar(raw_value, allow_eq=False)))
    for raw_name, person, _sc in bound:
        if person is None:
            details.append(f"unknown_name:{fold(raw_name)}")
            return make_result("AMBIG", pre.ext.value, flags, ";".join(details))
    values = {}
    order = []
    for _raw_name, person, sc in bound:
        if person in values:
            old = values[person]
            new_ok = sc.status == "ok" and sc.number is not None
            old_ok = old.status == "ok" and old.number is not None
            if (
                old.status != sc.status
                or not (new_ok and old_ok)
                or Fraction(old.number) != Fraction(sc.number)
            ):
                details.append(f"conflict:{person}")
                return make_result("AMBIG", pre.ext.value, flags, ";".join(details))
        else:
            values[person] = sc
            order.append(person)
    for person in order:
        sc = values[person]
        if sc.status != "ok" or sc.number is None or Fraction(sc.number).denominator != 1:
            details.append(f"bad_value:{person}")
            return make_result("AMBIG", pre.ext.value, flags, ";".join(details))
    assignment = {person: int(values[person].number) for person in order}
    if any(person not in assignment for person in people):
        details.append("incomplete")
        return make_result("WRONG", assignment, flags, ";".join(details))
    if sorted(assignment.values()) != list(range(1, n_slots + 1)):
        details.append("invalid_perm")
        return make_result("WRONG", assignment, flags, ";".join(details))
    violated = [
        i for i, c in enumerate(meta["constraints"]) if not schema.constraint_holds(c, assignment)
    ]
    if violated:
        details.append("violated:" + ",".join(str(i) for i in violated))
        return make_result("WRONG", assignment, flags, ";".join(details))
    if assignment == key:
        return make_result("OK", assignment, flags, ";".join(details))
    details.append("alt_solution")
    return make_result("GEN_BUG", assignment, flags, ";".join(details))
