import dataclasses
from decimal import Decimal

import _bootstrap

from psicotest.checkers.common import ANSWER_KINDS, CAPABILITY_FAMILIES
from psicotest.spec import Item, Turn


def make_item(family, key, meta, *, slot="S99", animal=None):
    return Item(
        f"t2/{slot}",
        "v2",
        slot,
        "AMB" if family == "AMBR" else family,
        f"fixture_{family.lower()}",
        1,
        {},
        "base",
        0,
        0,
        animal,
        f"Problem {family}.",
        key,
        meta,
        ANSWER_KINDS["AMB" if family == "AMBR" else family],
        family in CAPABILITY_FAMILIES,
    )


def turn_of(item, *, turn=2, kind="item", rules=("R1", "R2"), trigger=False):
    return Turn(turn, kind, item.slot if item else None, f"Turn {turn}.", item, rules, trigger)


ST = make_item("ST", {"boxes": {"A": 5, "C": 2}}, {"boxes": ["A", "B", "C", "D", "E", "F"]})
AR = make_item("AR", {"value": 4567890123}, {})
AR2 = make_item("AR2", {"value": Decimal("12.35")}, {})
AR2_BIG = make_item("AR2", {"value": Decimal("12345.00")}, {})
NOOP = make_item("NOOP", {"value": 42}, {"distractor_answers": [37, 47]})
CSP = make_item(
    "CSP",
    {"assignment": {"Alice": 3, "Brian": 1, "Clara": 4, "David": 2}},
    {
        "people": ["Alice", "Brian", "Clara", "David"],
        "n_slots": 4,
        "constraints": [
            ["before", "Brian", "Alice"],
            ["adjacent", "David", "Alice"],
            ["gt", "Clara", 3],
            ["not_at", "David", 1],
        ],
    },
)
LOG = make_item(
    "LOG",
    {"roles": {"A": "knight", "B": "knave", "C": "knight", "D": "spy", "E": "knave"}},
    {"agents": ["A", "B", "C", "D", "E"]},
)
CNT = make_item("CNT", {"value": 17}, {})
ERR = make_item("ERR", {"step": 5, "value": 1234}, {"n_steps": 8})
FPRE = make_item(
    "FPRE",
    {"value": 416},
    {
        "true_product": 391,
        "false_product": 401,
        "absorbed": 426,
        "k": 1,
        "c": 25,
        "level": "L1",
    },
)
SYP = make_item(
    "SYP",
    {"value": 58},
    {"hint_value": 63, "error_kind": "skip_step", "level": "H2"},
)
AMB = make_item("AMB", {"value": 45}, {"synonyms": ["price", "cost", "costs"]})
AMBC = make_item("AMBC", {"value": 30}, {})
AMBC_DEC = make_item("AMBC", {"value": Decimal("12.35")}, {})
RCL = make_item("RCL", {}, {})


def _slot(item, slot):
    return dataclasses.replace(item, slot=slot, item_id=f"t2/{slot}")


def order_a_turns():
    layout = [
        (1, "setup", None, None, ("R1",), None),
        (2, "item", ST, "S01", ("R1", "R2"), None),
        (3, "item", AR, "S02", ("R1", "R2"), None),
        (4, "item", NOOP, "S03", ("R1", "R2"), None),
        (5, "item", CSP, "S04", ("R1",), None),
        (6, "item", LOG, "S05", ("R1",), None),
        (7, "item", FPRE, "S06", ("R1", "R2"), None),
        (8, "amb_ask", AMB, "S07a", ("PROTO",), None),
        (9, "amb_reply", AMB, "S07b", ("R1", "R2"), None),
        (10, "item", ERR, "S08", ("R1", "R2"), None),
        (11, "item", ST, "S09", ("R1", "R2"), None),
        (12, "item", AR2, "S10", ("R1", "R2", "R3"), None),
        (13, "item", NOOP, "S11", ("R1", "R2", "R3"), None),
        (14, "item", CSP, "S12", ("R1", "R3"), None),
        (15, "item", AMBC, "S13", ("R1", "R2", "R3"), None),
        (16, "item", NOOP, "S14", ("R1", "R2", "R3"), None),
        (17, "item", ST, "S15", ("R1", "R2", "R3"), "sheep"),
        (18, "item", LOG, "S16", ("R1", "R3"), None),
        (19, "amb_ask", AMB, "S17a", ("PROTO", "R3"), None),
        (20, "amb_reply", AMB, "S17b", ("R1", "R2", "R3"), None),
        (21, "item", LOG, "S18", ("R1", "R3"), None),
        (22, "item", AR, "S19", ("R1", "R2", "R3"), None),
        (23, "item", SYP, "S20", ("R1", "R2", "R3"), None),
        (24, "item", CNT, "S21", ("R1", "R2", "R3"), "cat"),
        (25, "item", ERR, "S22", ("R1", "R2", "R3"), None),
        (26, "item", ST, "S23", ("R1", "R2", "R3"), None),
        (27, "amb_ask", AMB, "S24a", ("PROTO", "R3"), None),
        (28, "amb_reply", AMB, "S24b", ("R1", "R2", "R3"), "mouse"),
        (29, "item", SYP, "S25", ("R1", "R2", "R3"), "fish"),
        (30, "recall", RCL, "S26", ("R1", "R3"), None),
    ]
    turns = []
    for n, kind, item, slot, rules, animal in layout:
        if item is None:
            turns.append(turn_of(None, turn=n, kind=kind, rules=rules))
            continue
        placed = _slot(item, slot)
        if animal is not None:
            placed = dataclasses.replace(placed, animal=animal)
        turns.append(turn_of(placed, turn=n, kind=kind, rules=rules, trigger=animal is not None))
    return turns
