import dataclasses
from collections.abc import Mapping, Sequence
from fractions import Fraction

from psicotest.generators.lexicon import pick_names
from psicotest.generators.text_en import cap, fmt_int
from psicotest.rng import Rng

INIT = "INIT"
ADD_GROUPS = "ADD_GROUPS"
REMOVE_GROUPS = "REMOVE_GROUPS"
ADD = "ADD"
SUB = "SUB"
DIV_EQUAL = "DIV_EQUAL"
GROUPS = (ADD_GROUPS, REMOVE_GROUPS)
LINES = {ADD_GROUPS: 2, REMOVE_GROUPS: 2, ADD: 1, SUB: 1}
CONNECTORS = (
    "First",
    "Then",
    "Later",
    "Next",
    "After that",
    "A while later",
    "In the afternoon",
    "Before closing",
)
CONNECTED = (ADD_GROUPS, REMOVE_GROUPS, ADD, SUB, "no_c", "no_b", "derive")
NAMED = (ADD, SUB, "other_place", "minutes", "derive")
SAME_KINDS = ("other_place", "past", "label")
OTHER_KINDS = ("hour", "minutes", "price")
HOURS = (8, 9, 10)
NUMBERS = tuple(range(11, 100))


@dataclasses.dataclass(frozen=True)
class Scenario:
    place: str
    unit_sg: str
    unit_pl: str
    cont_sg: str
    cont_pl: str
    group_sg: str
    group_pl: str


SCENARIOS = (
    Scenario("the stationery shop", "notebook", "notebooks", "box", "boxes", "class", "classes"),
    Scenario("the library", "book", "books", "box", "boxes", "shelf", "shelves"),
    Scenario(
        "the plant nursery", "flowerpot", "flowerpots", "tray", "trays", "terrace", "terraces"
    ),
    Scenario("the bakery", "muffin", "muffins", "tray", "trays", "table", "tables"),
    Scenario("the warehouse", "screw", "screws", "bag", "bags", "workshop", "workshops"),
    Scenario("the fruit shop", "orange", "oranges", "box", "boxes", "stall", "stalls"),
)


@dataclasses.dataclass(frozen=True)
class Chain:
    ops: tuple
    running: tuple
    products: tuple


def apply(op: tuple, v: Fraction) -> Fraction:
    kind = op[0]
    if kind == INIT:
        return Fraction(op[1])
    if kind == ADD_GROUPS:
        return v + op[1] * op[2]
    if kind == REMOVE_GROUPS:
        return v - op[1] * op[2]
    if kind == ADD:
        return v + op[1]
    if kind == SUB:
        return v - op[1]
    return v / op[1]


def evaluate(ops: Sequence[tuple]) -> Fraction:
    v = Fraction(0)
    for op in ops:
        v = apply(op, v)
    return v


def make_chain(ops: Sequence[tuple]) -> Chain | None:
    if not any(op[0] in GROUPS for op in ops):
        return None
    v = Fraction(0)
    running = []
    products = []
    for op in ops:
        if op[0] in GROUPS:
            products.append(op[1] * op[2])
        v = apply(op, v)
        if v.denominator != 1 or not 1 <= v <= 9999:
            return None
        running.append(int(v))
    return Chain(tuple(ops), tuple(running), tuple(products))


def _draw_op(rng: Rng, kind: str) -> tuple:
    if kind == ADD_GROUPS:
        return (kind, rng.randint(3, 9), rng.randint(6, 24))
    if kind == REMOVE_GROUPS:
        return (kind, rng.randint(2, 6), rng.randint(6, 24))
    return (kind, rng.randint(11, 99))


def draw_chain(
    rng: Rng,
    size: int,
    allowed: Sequence[str],
    final_div: bool = False,
    by_lines: bool = False,
) -> Chain | None:
    ops = [(INIT, rng.randint(120, 480))]
    target = size - (1 if final_div else 0)
    used = 0
    prev = None
    while used < target:
        kind = rng.choice([k for k in allowed if k != prev])
        ops.append(_draw_op(rng, kind))
        used += LINES[kind] if by_lines else 1
        prev = kind
    if used != target:
        return None
    if final_div:
        v = evaluate(ops)
        divisors = [f for f in range(3, 10) if v % f == 0]
        if not divisors:
            return None
        ops.append((DIV_EQUAL, rng.choice(divisors)))
    return make_chain(ops)


def op_numbers(chain: Chain) -> set[int]:
    return {x for op in chain.ops for x in op[1:]}


def first_groups(chain: Chain) -> int:
    return next(i for i, op in enumerate(chain.ops) if op[0] == ADD_GROUPS)


def shown_args(chain: Chain, hidden_op: int, hidden_arg: int) -> set[int]:
    return {
        x
        for i, op in enumerate(chain.ops)
        for j, x in enumerate(op[1:], 1)
        if (i, j) != (hidden_op, hidden_arg)
    }


def draw_distractors(
    rng: Rng, chain: Chain, taken: set[int], same: int, other: int, quantifier: int
) -> tuple | None:
    m = len(chain.ops) - 1
    kinds = rng.sample(SAME_KINDS, same) + rng.sample(OTHER_KINDS, other)
    used = set(taken)
    out = []
    for kind in kinds:
        pool = [x for x in (HOURS if kind == "hour" else NUMBERS) if x not in used]
        if not pool:
            return None
        x = rng.choice(pool)
        used.add(x)
        out.append((kind, x, rng.randint(1, m)))
    if quantifier:
        pos = rng.randint(1, m)
        dens = [d for d in (2, 3) if chain.running[pos - 1] % d == 0]
        if not dens:
            return None
        out.append(("quantifier", rng.choice(dens), pos))
    return tuple(sorted(out, key=lambda d: d[2]))


def bait_values(chain: Chain, distractors: Sequence[tuple]) -> list[Fraction]:
    out = []
    for kind, x, pos in distractors:
        if kind not in SAME_KINDS and kind != "quantifier":
            continue
        v = Fraction(chain.running[pos - 1])
        if kind == "label":
            v -= x
        elif kind == "quantifier":
            v /= x
        else:
            v += x
        for op in chain.ops[pos:]:
            v = apply(op, v)
        out.append(v)
    return out


def sentence(tag: str, args: tuple, sc: Scenario, conn: str, name: str) -> str:
    n = [fmt_int(x) for x in args]
    if tag == INIT:
        return f"{cap(sc.place)} has {n[0]} {sc.unit_pl}."
    if tag == ADD_GROUPS:
        return f"{conn}, it receives {n[0]} {sc.cont_pl} of {n[1]} {sc.unit_pl}."
    if tag == REMOVE_GROUPS:
        return (
            f"{conn}, it takes {n[0]} {sc.cont_pl} of {n[1]} {sc.unit_pl} out for the shop window."
        )
    if tag == ADD:
        return f"{conn}, {name} brings {n[0]} more {sc.unit_pl}."
    if tag == SUB:
        return f"{conn}, {name} takes away {n[0]} {sc.unit_pl}."
    if tag == DIV_EQUAL:
        return f"Finally, all the {sc.unit_pl} are shared out equally among {n[0]} {sc.group_pl}."
    if tag == "no_c":
        return f"{conn}, it receives {n[0]} {sc.cont_pl} full of {sc.unit_pl}."
    if tag == "no_b":
        return f"{conn}, it receives several {sc.cont_pl} of {n[1]} {sc.unit_pl}."
    if tag == "derive":
        return (
            f"{conn}, it receives {n[0]} identical {sc.cont_pl}; {name} counts what is in "
            f"{n[2]} of them and gets {fmt_int(args[1] * args[2])} {sc.unit_pl}."
        )
    if tag == "other_place":
        return f"{name} mentions that the shop across the street has {n[0]} {sc.unit_pl}."
    if tag == "past":
        return f"Last year, at this time, {sc.place} had {n[0]} {sc.unit_pl}."
    if tag == "label":
        return (
            f"{n[0]} of the {sc.unit_pl} have a slightly crooked label, "
            "but they are sold all the same."
        )
    if tag == "hour":
        return f"{cap(sc.place)} opens at {n[0]} in the morning."
    if tag == "minutes":
        return f"{name} takes {n[0]} minutes to get there."
    if tag == "price":
        return f"Each {sc.unit_sg} costs {n[0]} dollars."
    return f"{'Half' if args[0] == 2 else 'A third'} of the {sc.unit_pl} are blue."


def render_story(
    rng: Rng,
    chain: Chain,
    distractors: Sequence[tuple],
    clean: bool,
    forms: Mapping[int, tuple] | None = None,
) -> tuple[str, list[str], Scenario]:
    forms = forms or {}
    sc = rng.choice(SCENARIOS)
    entries = []
    for i, op in enumerate(chain.ops):
        entries.extend((True, d[0], (d[1],)) for d in distractors if d[2] == i)
        if i in forms:
            entries.append((False, forms[i][0], op[1:] + forms[i][1:]))
        else:
            entries.append((False, op[0], op[1:]))
    names = iter(pick_names(rng, sum(1 for _, tag, _ in entries if tag in NAMED)))
    texts = []
    n_conn = 0
    for is_distractor, tag, args in entries:
        conn = CONNECTORS[n_conn % len(CONNECTORS)]
        name = next(names) if tag in NAMED else ""
        texts.append((is_distractor, sentence(tag, args, sc, conn, name)))
        if tag in CONNECTED:
            n_conn += 1
    story = " ".join(t for is_distractor, t in texts if not (is_distractor and clean))
    return story, [t for is_distractor, t in texts if is_distractor], sc


def question(chain: Chain, sc: Scenario) -> str:
    if chain.ops[-1][0] == DIV_EQUAL:
        return f"How many {sc.unit_pl} does each {sc.group_sg} get?"
    return f"How many {sc.unit_pl} does {sc.place} have at the end?"
