import dataclasses
from collections.abc import Mapping

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.problems import (
    ADD,
    ADD_GROUPS,
    SUB,
    Chain,
    draw_chain,
    draw_distractors,
    first_groups,
    op_numbers,
    question,
    render_story,
    shown_args,
)
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {0: {}}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base", "relabel")
ALLOWED = (ADD_GROUPS, ADD, SUB)


@dataclasses.dataclass(frozen=True)
class Inst:
    chain: Chain
    m: int
    distractors: tuple


def derived(inst: Inst) -> tuple[int, int]:
    c = inst.chain.ops[first_groups(inst.chain)][2]
    return c, inst.m * c


def valid(inst: Inst) -> str | None:
    _, mc = derived(inst)
    shown = shown_args(inst.chain, first_groups(inst.chain), 2) | {inst.m}
    shown |= {x for kind, x, _ in inst.distractors if kind != "quantifier"}
    if mc in shown:
        return "derived_clash"
    if inst.chain.running[-1] in shown | {mc}:
        return "key_in_prompt"
    return None


def draw(rng: Rng, params: dict) -> Inst | None:
    chain = draw_chain(rng, 4, ALLOWED, final_div=True)
    if chain is None:
        return None
    _, b, c = chain.ops[first_groups(chain)]
    m = rng.randint(2, b - 1)
    taken = op_numbers(chain) | {chain.running[-1], m, m * c}
    distractors = draw_distractors(rng, chain, taken, 0, 2, 0)
    if distractors is None:
        return None
    inst = Inst(chain, m, distractors)
    return inst if valid(inst) is None else None


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    forms = {first_groups(inst.chain): ("derive", inst.m)}
    story, _, sc = render_story(ctx.surface_rng, inst.chain, inst.distractors, False, forms)
    c, mc = derived(inst)
    key = {"value": inst.chain.running[-1]}
    meta = {
        "derivation": {"m": inst.m, "mc": mc, "c": c},
        "instance": {
            "ops": [list(op) for op in inst.chain.ops],
            "distractors": [list(d) for d in inst.distractors],
            "m": inst.m,
        },
        "realized": {"level": 0},
    }
    return [story, question(inst.chain, sc)], key, meta


def gen_derivable_datum(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_derivable_datum", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
