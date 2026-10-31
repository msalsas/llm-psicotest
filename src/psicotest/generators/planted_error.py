import dataclasses
from collections.abc import Mapping

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.problems import (
    ADD,
    ADD_GROUPS,
    GROUPS,
    REMOVE_GROUPS,
    SUB,
    Chain,
    draw_chain,
    question,
    render_story,
)
from psicotest.generators.text_en import fmt_int
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {"n_steps": 8, "first": (2, 3), "n_errors": 1},
    0: {"n_steps": 8, "first": (4, 7), "n_errors": 1},
    1: {"n_steps": 10, "first": (5, 9), "n_errors": 1},
    2: {"n_steps": 10, "first": (4, 7), "n_errors": 2},
}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base", "relabel")
ALLOWED = (ADD_GROUPS, REMOVE_GROUPS, ADD, SUB)
DELTAS = (-100, -10, -2, -1, 1, 2, 10, 100)
LAST_ERROR_STEP = 10
ONE_ERROR = (
    "One of the steps contains a calculation error; the following steps carry that error "
    "forward, but their operations are done correctly. Give the number of the step with the "
    "error and the correct final result, in the format STEP <number>; VALUE <number>."
)
TWO_ERRORS = (
    "The solution contains calculation errors; every step after an error carries that error "
    "forward, but its operation is done correctly. Give the number of the first step with an "
    "error and the correct final result, in the format STEP <number>; VALUE <number>."
)


@dataclasses.dataclass(frozen=True)
class Inst:
    chain: Chain
    errors: tuple[tuple[int, int], ...]


def solution_lines(inst: Inst) -> list[tuple[int, str, int, int, int]]:
    deltas = dict(inst.errors)
    lines = []
    v = inst.chain.ops[0][1]
    step = 0
    for op in inst.chain.ops[1:]:
        if op[0] in GROUPS:
            step += 1
            exact = op[1] * op[2]
            y = exact + deltas.get(step, 0)
            lines.append((op[1], "\N{MULTIPLICATION SIGN}", op[2], exact, y))
        else:
            y = op[1]
        step += 1
        sym = "+" if op[0] in (ADD_GROUPS, ADD) else "-"
        exact = v + y if sym == "+" else v - y
        z = exact + deltas.get(step, 0)
        lines.append((v, sym, y, exact, z))
        v = z
    return lines


def valid(inst: Inst) -> str | None:
    lines = solution_lines(inst)
    if any(min(x, y, z) <= 0 for x, _, y, _, z in lines):
        return "slip_nonpositive"
    if any(abs(delta) >= lines[step - 1][3] for step, delta in inst.errors):
        return "slip_nonpositive"
    if lines[-1][4] == inst.chain.running[-1]:
        return "no_effect"
    if sum(1 for _, _, _, exact, z in lines if exact != z) != len(inst.errors):
        return "detectability"
    return None


def draw(rng: Rng, params: dict) -> Inst | None:
    chain = draw_chain(rng, params["n_steps"], ALLOWED, by_lines=True)
    if chain is None:
        return None
    lo, hi = params["first"]
    steps = [rng.randint(lo, hi)]
    if params["n_errors"] == 2:
        steps.append(rng.randint(steps[0] + 2, LAST_ERROR_STEP))
    inst = Inst(chain, tuple((s, rng.choice(DELTAS)) for s in steps))
    return inst if valid(inst) is None else None


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    story, _, sc = render_story(ctx.surface_rng, inst.chain, (), False)
    lines = solution_lines(inst)
    shown = [
        f"Step {i}: {fmt_int(x)} {sym} {fmt_int(y)} = {fmt_int(z)}."
        for i, (x, sym, y, _, z) in enumerate(lines, 1)
    ]
    paragraphs = [
        "Problem: " + story + " " + question(inst.chain, sc),
        "Proposed solution:\n" + "\n".join(shown),
        ONE_ERROR if params["n_errors"] == 1 else TWO_ERRORS,
    ]
    key = {"step": inst.errors[0][0], "value": inst.chain.running[-1]}
    meta = {
        "n_steps": len(lines),
        "planted_steps": [step for step, _ in inst.errors],
        "wrong_final": lines[-1][4],
        "instance": {
            "ops": [list(op) for op in inst.chain.ops],
            "errors": [list(e) for e in inst.errors],
        },
        "realized": {"n_steps": params["n_steps"], "n_errors": params["n_errors"]},
    }
    return paragraphs, key, meta


def gen_planted_error(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_planted_error", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
