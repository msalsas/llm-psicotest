import re
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction

from psicotest.checkers.common import (
    ANSWER_KINDS,
    CAPABILITY_FAMILIES,
    ItemSchemaError,
    make_result,
    prepare,
    trunc_flags,
)
from psicotest.checkers.text import fold, words
from psicotest.spec import Item

LABEL_RE = re.compile(r"^[A-Z][A-Z0-9]?$")
NAME_RE = re.compile(r"^[^\W\d_]+$")
GENERIC_ASK_WORDS = (
    "data",
    "datum",
    "how",
    "info",
    "information",
    "many",
    "missing",
    "much",
    "value",
    "what",
    "which",
)


def _family(family: str) -> str:
    return "AMB" if family == "AMBR" else family


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v: object) -> bool:
    return _is_int(v) or (isinstance(v, Decimal) and v.is_finite())


def _req(mapping: Mapping, name: str) -> object:
    if name not in mapping:
        raise ItemSchemaError(f"missing {name}")
    return mapping[name]


def _is_person(x: object, people: tuple) -> bool:
    return isinstance(x, str) and x in people


def _is_slot(x: object, n_slots: int) -> bool:
    return _is_int(x) and 1 <= x <= n_slots


def _check_constraint(c: object, people: tuple, n_slots: int) -> None:
    if not isinstance(c, (list, tuple)) or len(c) < 2:
        raise ItemSchemaError("bad constraint")
    op = c[0]
    if op in ("at", "not_at", "lt", "gt"):
        if len(c) != 3 or not _is_person(c[1], people) or not _is_slot(c[2], n_slots):
            raise ItemSchemaError("bad constraint")
    elif op in ("before", "adjacent", "not_adjacent"):
        if len(c) != 3 or not _is_person(c[1], people) or not _is_person(c[2], people):
            raise ItemSchemaError("bad constraint")
    elif op == "gap":
        if (
            len(c) != 4
            or not _is_person(c[1], people)
            or not _is_person(c[2], people)
            or not _is_int(c[3])
            or not 1 <= c[3] < n_slots
        ):
            raise ItemSchemaError("bad constraint")
    elif op == "offset":
        if (
            len(c) != 4
            or not _is_person(c[1], people)
            or not _is_person(c[2], people)
            or not _is_int(c[3])
            or not 1 <= abs(c[3]) < n_slots
        ):
            raise ItemSchemaError("bad constraint")
    elif op == "parity":
        if len(c) != 3 or not _is_person(c[1], people) or c[2] not in ("even", "odd"):
            raise ItemSchemaError("bad constraint")
    elif op == "in":
        if len(c) != 3 or not _is_person(c[1], people):
            raise ItemSchemaError("bad constraint")
        slots = c[2]
        if (
            not isinstance(slots, (list, tuple))
            or not slots
            or any(not _is_slot(x, n_slots) for x in slots)
            or len(set(slots)) != len(slots)
        ):
            raise ItemSchemaError("bad constraint")
    elif op == "between":
        if len(c) != 4 or not all(_is_person(x, people) for x in c[1:]):
            raise ItemSchemaError("bad constraint")
    else:
        raise ItemSchemaError("unknown op")


def validate(item: Item | None, family: str) -> None:
    if not isinstance(item, Item):
        if family == "SETUP" and item is None:
            return
        raise TypeError("item must be an Item")
    fam = _family(family)
    if item.family != fam:
        raise ItemSchemaError("family mismatch")
    if item.answer_kind != ANSWER_KINDS[fam]:
        raise ItemSchemaError("answer_kind mismatch")
    if item.capability != (family in CAPABILITY_FAMILIES):
        raise ItemSchemaError("capability mismatch")
    key = item.key
    meta = item.meta
    if not isinstance(key, Mapping) or not isinstance(meta, Mapping):
        raise ItemSchemaError("key and meta must be mappings")
    if fam == "ST":
        boxes = _req(key, "boxes")
        if not isinstance(boxes, Mapping) or not boxes:
            raise ItemSchemaError("bad boxes")
        for label, v in boxes.items():
            if (
                not isinstance(label, str)
                or LABEL_RE.fullmatch(label) is None
                or not _is_int(v)
                or v < 0
            ):
                raise ItemSchemaError("bad boxes")
        meta_boxes = _req(meta, "boxes")
        if (
            not isinstance(meta_boxes, (list, tuple))
            or not meta_boxes
            or any(not isinstance(b, str) or LABEL_RE.fullmatch(b) is None for b in meta_boxes)
            or len(set(meta_boxes)) != len(meta_boxes)
        ):
            raise ItemSchemaError("bad meta boxes")
    elif fam == "AR":
        v = _req(key, "value")
        if not _is_int(v) or v <= 0:
            raise ItemSchemaError("bad value")
    elif fam == "AR2":
        v = _req(key, "value")
        if not isinstance(v, Decimal) or not v.is_finite():
            raise ItemSchemaError("bad value")
    elif fam == "NOOP":
        if not _is_num(_req(key, "value")):
            raise ItemSchemaError("bad value")
        d = _req(meta, "distractor_answers")
        if not isinstance(d, (list, tuple)) or any(not _is_num(x) for x in d):
            raise ItemSchemaError("bad distractors")
    elif fam == "CSP":
        assignment = _req(key, "assignment")
        people = _req(meta, "people")
        n_slots = _req(meta, "n_slots")
        constraints = _req(meta, "constraints")
        if (
            not isinstance(assignment, Mapping)
            or not isinstance(people, (list, tuple))
            or not people
            or any(not isinstance(p, str) or NAME_RE.fullmatch(p) is None for p in people)
            or len(set(people)) != len(people)
            or not _is_int(n_slots)
            or n_slots < 2
            or n_slots != len(people)
        ):
            raise ItemSchemaError("bad csp item")
        people_t = tuple(people)
        for p, v in assignment.items():
            if not isinstance(p, str) or not _is_int(v):
                raise ItemSchemaError("bad assignment")
        if not isinstance(constraints, (list, tuple)):
            raise ItemSchemaError("bad constraints")
        for c in constraints:
            _check_constraint(c, people_t, n_slots)
    elif fam == "LOG":
        roles = _req(key, "roles")
        agents = _req(meta, "agents")
        if not isinstance(roles, Mapping) or not isinstance(agents, (list, tuple)) or not agents:
            raise ItemSchemaError("bad log item")
        if (
            any(not isinstance(a, str) or NAME_RE.fullmatch(a) is None for a in agents)
            or len(set(agents)) != len(agents)
            or any(r not in ("knight", "knave", "spy") for r in roles.values())
        ):
            raise ItemSchemaError("bad log item")
    elif fam == "CNT":
        v = _req(key, "value")
        if not _is_int(v) or v < 0:
            raise ItemSchemaError("bad value")
    elif fam == "ERR":
        step = _req(key, "step")
        if not _is_int(step) or not _is_num(_req(key, "value")):
            raise ItemSchemaError("bad key")
        n_steps = _req(meta, "n_steps")
        if not _is_int(n_steps) or n_steps < 2:
            raise ItemSchemaError("bad n_steps")
    elif fam == "FPRE":
        if not _is_int(_req(key, "value")):
            raise ItemSchemaError("bad value")
        for name in ("true_product", "false_product", "absorbed", "k", "c"):
            if not _is_int(_req(meta, name)):
                raise ItemSchemaError("bad meta")
        if _req(meta, "level") not in ("L0", "L1", "L2"):
            raise ItemSchemaError("bad level")
    elif fam == "SYP":
        if not _is_int(_req(key, "value")) or not _is_int(_req(meta, "hint_value")):
            raise ItemSchemaError("bad value")
        if _req(meta, "error_kind") not in ("skip_step", "swap_op", "off_by_one_count"):
            raise ItemSchemaError("bad error_kind")
        if _req(meta, "level") not in ("H1", "H2", "H3"):
            raise ItemSchemaError("bad level")
    elif fam == "AMB":
        if not _is_num(_req(key, "value")):
            raise ItemSchemaError("bad value")
        syns = _req(meta, "synonyms")
        if (
            not isinstance(syns, (list, tuple))
            or not syns
            or any(not isinstance(s, str) or s == "" or not words(s) for s in syns)
        ):
            raise ItemSchemaError("bad synonyms")
    elif fam == "AMBC":
        if not _is_num(_req(key, "value")):
            raise ItemSchemaError("bad value")
    elif fam in ("RCL", "SETUP"):
        pass
    else:
        raise ItemSchemaError("unknown family")


def constraint_holds(c: list | tuple, pos: Mapping) -> bool:
    op = c[0]
    if op == "at":
        return pos[c[1]] == c[2]
    if op == "not_at":
        return pos[c[1]] != c[2]
    if op == "before":
        return pos[c[1]] < pos[c[2]]
    if op == "adjacent":
        return abs(pos[c[1]] - pos[c[2]]) == 1
    if op == "not_adjacent":
        return abs(pos[c[1]] - pos[c[2]]) != 1
    if op == "gap":
        return abs(pos[c[1]] - pos[c[2]]) == c[3]
    if op == "offset":
        return pos[c[2]] - pos[c[1]] == c[3]
    if op == "lt":
        return pos[c[1]] < c[2]
    if op == "gt":
        return pos[c[1]] > c[2]
    if op == "parity":
        return pos[c[1]] % 2 == (0 if c[2] == "even" else 1)
    if op == "in":
        return pos[c[1]] in c[2]
    if op == "between":
        return min(pos[c[2]], pos[c[3]]) < pos[c[1]] < max(pos[c[2]], pos[c[3]])
    raise ItemSchemaError("unknown op")


def invariant(item: Item, family: str) -> str | None:
    if item is None:
        return None
    fam = _family(family)
    key = item.key
    meta = item.meta
    if fam == "ST":
        for label in key["boxes"]:
            if label not in meta["boxes"]:
                return "key_label_unknown"
    elif fam == "AR2":
        if key["value"].as_tuple().exponent != -2:
            return "key_not_2dp"
    elif fam == "NOOP":
        kv = key["value"]
        if any(Fraction(kv) == Fraction(d) for d in meta["distractor_answers"]):
            return "distractor_equals_key"
        if isinstance(kv, Decimal) and kv.as_tuple().exponent < -2:
            return "key_not_2dp"
    elif fam == "CSP":
        people = tuple(meta["people"])
        n_slots = meta["n_slots"]
        assignment = key["assignment"]
        if set(assignment) != set(people) or sorted(assignment.values()) != list(
            range(1, n_slots + 1)
        ):
            return "key_invalid"
        for i, c in enumerate(meta["constraints"]):
            if not constraint_holds(c, assignment):
                return f"key_violates:{i}"
    elif fam == "LOG":
        if set(key["roles"]) != set(meta["agents"]):
            return "key_invalid"
    elif fam == "ERR":
        if not 1 <= key["step"] <= meta["n_steps"]:
            return "step_out_of_range"
    elif fam == "FPRE":
        k = meta["k"]
        c = meta["c"]
        if (
            key["value"] != k * meta["true_product"] + c
            or meta["absorbed"] != k * meta["false_product"] + c
        ):
            return "inconsistent"
        if len({key["value"], meta["absorbed"], meta["true_product"], meta["false_product"]}) != 4:
            return "not_distinct"
        if abs(meta["absorbed"] - key["value"]) < 10:
            return "absorbed_too_close"
        if meta["false_product"] <= 0:
            return "false_product_nonpositive"
    elif fam == "SYP":
        hint = meta["hint_value"]
        if hint == key["value"]:
            return "hint_equals_key"
        if abs(hint - key["value"]) < 2:
            return "hint_too_close"
        if hint <= 0:
            return "hint_nonpositive"
    elif fam == "AMB":
        if isinstance(key["value"], Decimal) and key["value"].as_tuple().exponent < -2:
            return "key_not_2dp"
        if any(fold(s) in GENERIC_ASK_WORDS for s in meta["synonyms"]):
            return "generic_synonym"
    elif (
        fam == "AMBC"
        and isinstance(key["value"], Decimal)
        and key["value"].as_tuple().exponent < -2
    ):
        return "key_not_2dp"
    return None


def begin(content: str | None, finish_reason: str | None, reasoning: str | None, item, family: str):
    validate(item, family)
    token = invariant(item, family)
    if token is not None:
        return None, make_result("GEN_BUG", None, (), token)
    pre = prepare(content, finish_reason, reasoning)
    if pre.trunc:
        return None, make_result("TRUNC", None, trunc_flags(pre.flags), "")
    return pre, None
