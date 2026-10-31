import dataclasses

import _bootstrap

from psicotest.generators import (
    R3_TEXT,
    RCL_TEXT,
    SETUP_TEXT,
    SLOTS_V2,
    build_slot_item,
    reply_prompt,
    trigger_animal,
)
from psicotest.spec import Turn

SLOT_BY_ID = {s.slot: s for s in SLOTS_V2}
ORDER_A = (
    (1, "setup", None),
    (2, "item", "S01"),
    (3, "item", "S02"),
    (4, "item", "S03"),
    (5, "item", "S04"),
    (6, "item", "S05"),
    (7, "item", "S06"),
    (8, "amb_ask", "S07"),
    (9, "amb_reply", "S07"),
    (10, "item", "S08"),
    (11, "item", "S09"),
    (12, "item", "S10"),
    (13, "item", "S11"),
    (14, "item", "S12"),
    (15, "item", "S13"),
    (16, "item", "S14"),
    (17, "item", "S15"),
    (18, "item", "S16"),
    (19, "amb_ask", "S17"),
    (20, "amb_reply", "S17"),
    (21, "item", "S18"),
    (22, "item", "S19"),
    (23, "item", "S20"),
    (24, "item", "S21"),
    (25, "item", "S22"),
    (26, "item", "S23"),
    (27, "amb_ask", "S24"),
    (28, "amb_reply", "S24"),
    (29, "item", "S25"),
    (30, "recall", "S26"),
)
P = [2, 3, 4, 5, 6, 7, 10, 11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 26, 29]
_A_AT = {turn: (kind, slot) for turn, kind, slot in ORDER_A}
_B_AT = {P[i]: _A_AT[P[21 - i]] for i in range(22)}
ORDER_B = tuple((turn, *(_B_AT[turn] if turn in _B_AT else _A_AT[turn])) for turn, _, _ in ORDER_A)
TRIGGERS = (17, 24, 28, 29)
SLOT_SUFFIX = {"item": "", "recall": "", "amb_ask": "a", "amb_reply": "b"}


def rules_for(kind, family, turn):
    if kind == "setup":
        return ("R1",)
    r3 = ("R3",) if turn >= 12 else ()
    if kind == "amb_ask":
        return ("PROTO", *r3)
    if kind == "recall":
        return ("R1", *r3)
    if family in ("CSP", "LOG"):
        return ("R1", *r3)
    return ("R1", "R2", *r3)


def build_turns(seed, order):
    layout = ORDER_A if order == "A" else ORDER_B
    turns = []
    for turn, kind, slot_id in layout:
        if kind == "setup":
            rules = rules_for(kind, None, turn)
            turns.append(Turn(turn, kind, None, SETUP_TEXT, None, rules, False))
            continue
        spec = SLOT_BY_ID[slot_id]
        trigger = turn in TRIGGERS
        noun = trigger_animal("v2", seed, order, turn) if trigger else None
        if kind == "amb_reply":
            item = dataclasses.replace(build_slot_item(spec, seed), animal=noun)
            prompt = reply_prompt(item)
        elif kind == "recall":
            item = build_slot_item(spec, seed)
            prompt = RCL_TEXT
        else:
            item = build_slot_item(spec, seed, animal=noun)
            prompt = item.prompt_en
        if turn == 11:
            prompt = R3_TEXT + "\n\n" + prompt
        turns.append(
            Turn(
                turn,
                kind,
                slot_id + SLOT_SUFFIX[kind],
                prompt,
                item,
                rules_for(kind, item.family, turn),
                trigger,
            )
        )
    return turns
