import dataclasses
from collections.abc import Mapping

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.lexicon import LABEL_POOL
from psicotest.generators.text_en import join_en, num_word, plural
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {"n_ops": 20, "n_boxes": 6},
    0: {"n_ops": 30, "n_boxes": 6},
    1: {"n_ops": 60, "n_boxes": 7},
    2: {"n_ops": 150, "n_boxes": 9},
}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base", "relabel")
KINDS = ("add", "remove", "transfer", "swap")
MAX_BOX = 99
REDRAWS = 50


@dataclasses.dataclass(frozen=True)
class Inst:
    initial: tuple[int, ...]
    ops: tuple[tuple, ...]
    query: tuple[int, int]


def n_conditionals(n_ops: int) -> int:
    return (n_ops + 4) // 5


def step(state: list[int], op: tuple) -> tuple[list[int], bool | None] | None:
    out = list(state)
    kind = op[0]
    branch = None
    if kind == "add":
        out[op[1]] += op[2]
    elif kind == "remove":
        out[op[1]] -= op[2]
    elif kind == "transfer":
        out[op[1]] -= op[3]
        out[op[2]] += op[3]
    elif kind == "swap":
        out[op[1]], out[op[2]] = out[op[2]], out[op[1]]
    else:
        x = state[op[1]]
        y = state[op[2]]
        if x == y:
            return None
        branch = x > y
        if branch:
            out[op[1]] -= op[3]
            out[op[2]] += op[3]
    if min(out) < 0 or max(out) > MAX_BOX:
        return None
    return out, branch


def replay(inst: Inst) -> tuple[list[int], list[bool]] | None:
    state = list(inst.initial)
    branches = []
    for op in inst.ops:
        result = step(state, op)
        if result is None:
            return None
        state = result[0]
        if result[1] is not None:
            branches.append(result[1])
    return state, branches


def boxes_of(op: tuple) -> tuple[int, ...]:
    return op[1:2] if op[0] in ("add", "remove") else op[1:3]


def valid(inst: Inst) -> str | None:
    replayed = replay(inst)
    if replayed is None:
        return "bad_op"
    final, branches = replayed
    i, j = inst.query
    if final[i] == final[j]:
        return "query_equal"
    if final[i] == inst.initial[i] or final[j] == inst.initial[j]:
        return "query_unchanged"
    need = len(inst.ops) // 5
    if any(sum(1 for op in inst.ops if box in boxes_of(op)) < need for box in inst.query):
        return "query_untouched"
    if True not in branches or False not in branches:
        return "cond_one_branch"
    return None


def _draw_op(rng: Rng, n_boxes: int, conditional: bool) -> tuple:
    if conditional:
        a, b = rng.sample(range(n_boxes), 2)
        return ("cond", a, b, rng.randint(1, 9))
    kind = rng.choice(KINDS)
    if kind in ("add", "remove"):
        return (kind, rng.below(n_boxes), rng.randint(1, 9))
    a, b = rng.sample(range(n_boxes), 2)
    if kind == "swap":
        return (kind, a, b)
    return (kind, a, b, rng.randint(1, 9))


def draw(rng: Rng, params: dict) -> Inst | None:
    n_ops = params["n_ops"]
    n_boxes = params["n_boxes"]
    initial = tuple(rng.randint(3, 15) for _ in range(n_boxes))
    conditional = rng.sample(range(n_ops), n_conditionals(n_ops))
    state = list(initial)
    ops = []
    for i in range(n_ops):
        for _ in range(REDRAWS):
            op = _draw_op(rng, n_boxes, i in conditional)
            result = step(state, op)
            if result is not None:
                break
        else:
            return None
        state = result[0]
        ops.append(op)
    query = rng.sample(range(n_boxes), 2)
    inst = Inst(initial, tuple(ops), (query[0], query[1]))
    return inst if valid(inst) is None else None


def marbles(k: int) -> str:
    return plural(k, "marble", "marbles")


def op_text(op: tuple, labels: list[str]) -> str:
    kind = op[0]
    a = labels[op[1]]
    if kind == "add":
        return f"Add {marbles(op[2])} to box {a}."
    if kind == "remove":
        return f"Take {marbles(op[2])} out of box {a}."
    b = labels[op[2]]
    if kind == "transfer":
        return f"Move {marbles(op[3])} from box {a} to box {b}."
    if kind == "swap":
        return f"Swap the entire contents of boxes {a} and {b}."
    return (
        f"If box {a} holds more marbles than box {b}, "
        f"move {marbles(op[3])} from box {a} to box {b}; otherwise do nothing."
    )


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    labels = sorted(ctx.surface_rng.sample(LABEL_POOL, params["n_boxes"]))
    final, _ = replay(inst)
    holds = [
        f"box {label} holds {marbles(v)}" for label, v in zip(labels, inst.initial, strict=True)
    ]
    (lx, vx), (ly, vy) = sorted((labels[i], final[i]) for i in inst.query)
    lines = [f"{i}. {op_text(op, labels)}" for i, op in enumerate(inst.ops, 1)]
    paragraphs = [
        f"On a table there are {num_word(params['n_boxes'])} boxes, labelled with the letters "
        f"{join_en(labels)}. At the start, {join_en(holds)}.",
        "Carry out these operations in order:\n" + "\n".join(lines),
        f"How many marbles are in box {lx} and in box {ly} at the end? "
        f"Give the result in the format {lx}=<number>; {ly}=<number>.",
    ]
    key = {"boxes": {lx: vx, ly: vy}}
    meta = {
        "boxes": labels,
        "instance": {
            "initial": list(inst.initial),
            "ops": [list(op) for op in inst.ops],
            "query": list(inst.query),
        },
        "realized": {
            "n_ops": params["n_ops"],
            "n_boxes": params["n_boxes"],
            "n_cond": sum(1 for op in inst.ops if op[0] == "cond"),
        },
    }
    return paragraphs, key, meta


def gen_state_boxes(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_state_boxes", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
