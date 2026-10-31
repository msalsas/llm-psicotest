import dataclasses
import itertools
from collections.abc import Mapping, Sequence

from psicotest.checkers.text import fold
from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.lexicon import pick_names
from psicotest.generators.text_en import cap, join_en, num_word, plural
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {"n": 5, "count": (8, 10), "min_hop2": 2},
    0: {"n": 6, "count": (12, 14), "min_hop2": 3},
    1: {"n": 6, "count": (10, 10), "min_hop2": 3},
    2: {"n": 7, "count": (13, 15), "min_hop2": 3},
}
OVERRIDES = {"n_constraints": (12, 14)}
VARIANTS = ("base", "relabel")
OPS = (
    "not_at",
    "before",
    "adjacent",
    "not_adjacent",
    "gap",
    "offset",
    "lt",
    "gt",
    "parity",
    "in",
    "between",
)
PERSON_COUNT = {
    "not_at": 1,
    "before": 2,
    "adjacent": 2,
    "not_adjacent": 2,
    "gap": 2,
    "offset": 2,
    "lt": 1,
    "gt": 1,
    "parity": 1,
    "in": 1,
    "between": 3,
}
CANDIDATES = 400


@dataclasses.dataclass(frozen=True)
class Inst:
    perm: tuple[int, ...]
    constraints: tuple[tuple, ...]
    count_range: tuple[int, int]
    min_hop2: int


def mentioned(c: tuple) -> tuple[int, ...]:
    return c[1 : 1 + PERSON_COUNT[c[0]]]


def holds(c: tuple, pos: Sequence[int] | Mapping[int, int]) -> bool:
    op = c[0]
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
    return min(pos[c[2]], pos[c[3]]) < pos[c[1]] < max(pos[c[2]], pos[c[3]])


def pins_cell(c: tuple, n: int) -> bool:
    people = mentioned(c)
    slots: dict[int, set[int]] = {p: set() for p in people}
    for assignment in itertools.permutations(range(1, n + 1), len(people)):
        pos = dict(zip(people, assignment, strict=True))
        if holds(c, pos):
            for p, slot in pos.items():
                slots[p].add(slot)
    return any(len(slots[p]) <= 1 for p in people)


def hop2(perm: tuple[int, ...], constraints: Sequence[tuple]) -> int:
    n = len(perm)
    prefix = list(itertools.permutations(range(1, n + 1)))
    necessary = 0
    for i, c in enumerate(constraints):
        rest = constraints[i + 1 :]
        if len(mentioned(c)) >= 2 and any(
            s != perm and all(holds(r, s) for r in rest) for s in prefix
        ):
            necessary += 1
        prefix = [s for s in prefix if holds(c, s)]
    return necessary


def valid(inst: Inst) -> str | None:
    n = len(inst.perm)
    remaining = list(itertools.permutations(range(1, n + 1)))
    for c in inst.constraints:
        remaining = [s for s in remaining if holds(c, s)]
    if remaining != [inst.perm]:
        return "not_unique"
    if any(pins_cell(c, n) for c in inst.constraints):
        return "pins_cell"
    if hop2(inst.perm, inst.constraints) < inst.min_hop2:
        return "hop2_low"
    lo, hi = inst.count_range
    if not lo <= len(inst.constraints) <= hi:
        return "count_out_of_range"
    return None


def _candidate(rng: Rng, n: int) -> tuple:
    op = rng.choice(OPS)
    if op == "not_at":
        return (op, rng.below(n), rng.randint(1, n))
    if op in ("before", "adjacent", "not_adjacent"):
        p, q = rng.sample(range(n), 2)
        return (op, p, q)
    if op == "gap":
        p, q = rng.sample(range(n), 2)
        return (op, p, q, rng.randint(2, n - 1))
    if op == "offset":
        p, q = rng.sample(range(n), 2)
        return (op, p, q, rng.randint(1, n - 1) * rng.choice((-1, 1)))
    if op in ("lt", "gt"):
        return (op, rng.below(n), rng.randint(1, n))
    if op == "parity":
        return (op, rng.below(n), rng.choice(("even", "odd")))
    if op == "in":
        p = rng.below(n)
        return (op, p, tuple(sorted(rng.sample(range(1, n + 1), rng.randint(2, 3)))))
    p, q, r = rng.sample(range(n), 3)
    return (op, p, q, r)


def draw(rng: Rng, params: dict) -> Inst | None:
    n = params["n"]
    if "n_constraints" in params:
        lo = hi = params["n_constraints"]
    else:
        lo, hi = params["count"]
    target = rng.randint(lo, hi)
    perm = list(range(1, n + 1))
    rng.shuffle(perm)
    perm_t = tuple(perm)
    remaining = list(itertools.permutations(range(1, n + 1)))
    pinned: dict[tuple, bool] = {}
    kept: list[tuple] = []

    def usable(c: tuple) -> bool:
        if not holds(c, perm_t):
            return False
        key = (c[0], *c[1 + PERSON_COUNT[c[0]] :])
        if key not in pinned:
            pinned[key] = pins_cell(c, n)
        return not pinned[key]

    for _ in range(CANDIDATES):
        if len(remaining) == 1:
            break
        c = _candidate(rng, n)
        if not usable(c):
            continue
        narrowed = [s for s in remaining if holds(c, s)]
        if len(narrowed) < len(remaining):
            kept.append(c)
            remaining = narrowed
    if len(remaining) != 1 or len(kept) > hi:
        return None
    for _ in range(CANDIDATES):
        if len(kept) >= target:
            break
        c = _candidate(rng, n)
        if c not in kept and usable(c):
            kept.append(c)
    inst = Inst(perm_t, tuple(kept), (lo, hi), params["min_hop2"])
    return inst if valid(inst) is None else None


def constraint_text(c: list) -> str:
    op = c[0]
    p = c[1]
    if op == "not_at":
        return f"{p} does not sit in seat {c[2]}."
    if op == "before":
        return f"{p} sits to the left of {c[2]}, though not necessarily next to them."
    if op == "adjacent":
        return f"{p} and {c[2]} sit next to each other."
    if op == "not_adjacent":
        return f"{p} and {c[2]} do not sit next to each other."
    if op == "gap":
        verb = "is" if c[3] - 1 == 1 else "are"
        return f"There {verb} exactly {plural(c[3] - 1, 'seat', 'seats')} between {p} and {c[2]}."
    if op == "offset":
        q = c[2]
        if c[3] == 1:
            return f"{q} sits immediately to the right of {p}."
        if c[3] == -1:
            return f"{q} sits immediately to the left of {p}."
        side = "right" if c[3] > 0 else "left"
        return f"{q} sits {abs(c[3])} seats to the {side} of {p}."
    if op == "lt":
        return f"{p} sits in a seat with a number lower than {c[2]}."
    if op == "gt":
        return f"{p} sits in a seat with a number higher than {c[2]}."
    if op == "parity":
        return f"{p} sits in an {c[2]}-numbered seat."
    if op == "in":
        return f"{p} sits in seat {join_en([str(k) for k in c[2]], 'or')}."
    return f"{p} sits somewhere between {c[2]} and {c[3]}."


def named(c: tuple, names: list[str]) -> list:
    m = PERSON_COUNT[c[0]]
    tail = [list(x) if isinstance(x, tuple) else x for x in c[1 + m :]]
    return [c[0], *[names[i] for i in c[1 : 1 + m]], *tail]


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    n = len(inst.perm)
    names = pick_names(ctx.surface_rng, n)
    people = sorted(names, key=fold)
    order = list(range(len(inst.constraints)))
    ctx.surface_rng.shuffle(order)
    shown = [named(inst.constraints[i], names) for i in order]
    lines = [f"- {constraint_text(c)}" for c in shown]
    paragraphs = [
        f"{cap(num_word(n))} people, {join_en(people)}, sit in a row of {num_word(n)} seats "
        f"numbered 1 to {n} from left to right. Each seat is taken by exactly one person.",
        "We know that:\n" + "\n".join(lines),
        "Which seat does each person sit in? Give each person's seat in the format "
        "Name=<number>, separating the pairs with semicolons.",
    ]
    key = {"assignment": {names[i]: inst.perm[i] for i in range(n)}}
    meta = {
        "people": people,
        "n_slots": n,
        "constraints": shown,
        "instance": {
            "perm": list(inst.perm),
            "constraints_idx": [
                [list(x) if isinstance(x, tuple) else x for x in c] for c in inst.constraints
            ],
        },
        "realized": {
            "n": n,
            "n_constraints": len(inst.constraints),
            "hop2": hop2(inst.perm, inst.constraints),
        },
    }
    return paragraphs, key, meta


def gen_csp_perm(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_csp_perm", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
