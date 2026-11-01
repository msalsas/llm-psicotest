import dataclasses
from collections.abc import Mapping

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.text_en import plural
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {
        "token_count": 6,
        "op_count": 4,
        "has_rotate": False,
        "has_move": False,
        "noop_replaces": False,
    },
    0: {
        "token_count": 7,
        "op_count": 4,
        "has_rotate": True,
        "has_move": True,
        "noop_replaces": False,
    },
    1: {
        "token_count": 8,
        "op_count": 5,
        "has_rotate": True,
        "has_move": True,
        "noop_replaces": True,
    },
    2: {
        "token_count": 9,
        "op_count": 6,
        "has_rotate": True,
        "has_move": True,
        "noop_replaces": True,
    },
}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base",)
TOKEN_POOL = (
    "apple",
    "bronze",
    "candle",
    "delta",
    "ember",
    "frost",
    "grain",
    "harbor",
    "index",
    "jasper",
    "kindle",
    "lemon",
    "marble",
    "noble",
    "orbit",
    "prism",
    "quartz",
    "riddle",
    "spark",
    "timber",
    "umbra",
    "velvet",
    "willow",
    "xenon",
    "yellow",
    "zephyr",
)


@dataclasses.dataclass(frozen=True)
class Inst:
    tokens: tuple[str, ...]
    ops: tuple[dict, ...]


def apply_ops(tokens: tuple[str, ...], ops: tuple[dict, ...]) -> list[str]:
    out = list(tokens)
    for op in ops:
        kind = op["kind"]
        if kind == "reverse":
            out.reverse()
        elif kind == "rotate":
            k = op["k"] % len(out)
            out = out[-k:] + out[:-k]
        elif kind == "replace":
            out = [op["new"] if t == op["old"] else t for t in out]
        elif kind == "swap":
            i, j = op["i"] - 1, op["j"] - 1
            out[i], out[j] = out[j], out[i]
        else:
            out.append(out.pop(op["i"] - 1))
    return out


def valid(inst: Inst) -> str | None:
    n = len(inst.tokens)
    if len(set(inst.tokens)) != n:
        return "dup_tokens"
    for tok in inst.tokens:
        if tok not in TOKEN_POOL:
            return "token_out_of_pool"
    for op in inst.ops:
        kind = op["kind"]
        if kind == "rotate" and not 1 <= op["k"] <= n - 1:
            return "bad_rotate"
        if kind == "swap" and not 1 <= op["i"] < op["j"] <= n:
            return "bad_swap"
        if kind == "move" and not 1 <= op["i"] <= n:
            return "bad_move"
        if kind == "replace" and (op["old"] not in TOKEN_POOL or op["new"] not in TOKEN_POOL):
            return "bad_replace"
    return None


def draw(rng: Rng, params: dict) -> Inst | None:
    n = params["token_count"]
    tokens = tuple(rng.sample(TOKEN_POOL, n))
    kinds = ["reverse", "replace", "swap"]
    if params["has_rotate"]:
        kinds.append("rotate")
    if params["has_move"]:
        kinds.append("move")
    chosen = rng.sample(kinds, min(len(kinds), params["op_count"]))
    while len(chosen) < params["op_count"]:
        chosen.append(rng.choice(kinds))
    rng.shuffle(chosen)
    ops: list[dict] = []
    noop_left = params["noop_replaces"]
    running = list(tokens)
    for kind in chosen:
        if kind == "reverse":
            ops.append({"kind": "reverse"})
            running.reverse()
        elif kind == "rotate":
            k = rng.randint(1, n - 1)
            ops.append({"kind": "rotate", "k": k})
            running = running[-k:] + running[:-k]
        elif kind == "replace":
            if noop_left:
                noop_left = False
                absent = [t for t in TOKEN_POOL if t not in running]
                old = rng.choice(absent)
            else:
                old = rng.choice(running)
            new = rng.choice([t for t in TOKEN_POOL if t != old])
            ops.append({"kind": "replace", "old": old, "new": new})
            running = [new if t == old else t for t in running]
        elif kind == "swap":
            i, j = sorted(rng.sample(range(1, n + 1), 2))
            ops.append({"kind": "swap", "i": i, "j": j})
            running[i - 1], running[j - 1] = running[j - 1], running[i - 1]
        else:
            i = rng.randint(1, n)
            ops.append({"kind": "move", "i": i})
            running.append(running.pop(i - 1))
    inst = Inst(tokens, tuple(ops))
    return inst if valid(inst) is None else None


def op_text(op: dict) -> str:
    kind = op["kind"]
    if kind == "reverse":
        return "Reverse the entire list."
    if kind == "rotate":
        return f"Rotate the list right by {plural(op['k'], 'position', 'positions')}."
    if kind == "replace":
        return f'Replace the token "{op["old"]}" with "{op["new"]}".'
    if kind == "swap":
        return f"Swap the tokens at positions {op['i']} and {op['j']}."
    return f"Move the token at position {op['i']} to the end of the list."


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    listed = ", ".join(inst.tokens)
    lines = [f"{i}. {op_text(op)}" for i, op in enumerate(inst.ops, 1)]
    paragraphs = [
        f"You have the following list of tokens:\n[{listed}]",
        "Apply these operations in order. Positions are counted from 1: "
        "position 1 is the first token of the list.\n" + "\n".join(lines),
        "What is the final list? Provide your answer as a comma-separated list of tokens "
        "in their final order on the ANSWER: line.",
    ]
    key = {"tokens": apply_ops(inst.tokens, inst.ops)}
    meta = {
        "instance": {"tokens": list(inst.tokens), "ops": [dict(op) for op in inst.ops]},
        "realized": {"token_count": params["token_count"], "op_count": params["op_count"]},
    }
    return paragraphs, key, meta


def gen_instr_chain(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_instr_chain", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
