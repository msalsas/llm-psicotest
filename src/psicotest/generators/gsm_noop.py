import dataclasses
from collections.abc import Mapping

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.problems import (
    ADD,
    ADD_GROUPS,
    REMOVE_GROUPS,
    SAME_KINDS,
    SUB,
    Chain,
    bait_values,
    draw_chain,
    draw_distractors,
    op_numbers,
    question,
    render_story,
)
from psicotest.generators.text_en import num_out
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {"n_steps": 5, "n_distractors": 2, "quantifier": 0, "n_same_unit": 2},
    0: {"n_steps": 5, "n_distractors": None, "quantifier": 0, "n_same_unit": None},
    1: {"n_steps": 6, "n_distractors": 7, "quantifier": 1, "n_same_unit": 4},
    2: {"n_steps": 9, "n_distractors": 10, "quantifier": 1, "n_same_unit": 6},
}
OVERRIDES = {"n_distractors": (5, 8)}
VARIANTS = ("base", "clean", "relabel")
ALLOWED = (ADD_GROUPS, REMOVE_GROUPS, ADD, SUB)
MIN_SAME_UNIT = 2


@dataclasses.dataclass(frozen=True)
class Inst:
    chain: Chain
    distractors: tuple


def shown_numbers(inst: Inst) -> set[int]:
    return op_numbers(inst.chain) | {x for kind, x, _ in inst.distractors if kind != "quantifier"}


def valid(inst: Inst) -> str | None:
    key = inst.chain.running[-1]
    for bait in bait_values(inst.chain, inst.distractors):
        if bait == key:
            return "bait_equals_key"
        if bait <= 0:
            return "bait_nonpositive"
    if key in shown_numbers(inst):
        return "key_in_prompt"
    if sum(1 for kind, _, _ in inst.distractors if kind in SAME_KINDS) < MIN_SAME_UNIT:
        return "too_few_same_unit"
    return None


def draw(rng: Rng, params: dict) -> Inst | None:
    chain = draw_chain(rng, params["n_steps"], ALLOWED, final_div=True)
    if chain is None:
        return None
    n = params["n_distractors"]
    if n is None:
        n = rng.randint(*OVERRIDES["n_distractors"])
    same = params["n_same_unit"]
    if same is None:
        same = max(2, n // 2)
    distractors = draw_distractors(
        rng, chain, op_numbers(chain) | {chain.running[-1]}, same, n - same, params["quantifier"]
    )
    if distractors is None:
        return None
    inst = Inst(chain, distractors)
    return inst if valid(inst) is None else None


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    story, sentences, sc = render_story(
        ctx.surface_rng, inst.chain, inst.distractors, ctx.variant == "clean"
    )
    paragraphs = [story, question(inst.chain, sc)]
    key = {"value": inst.chain.running[-1]}
    n_same = sum(1 for kind, _, _ in inst.distractors if kind in SAME_KINDS)
    n_quantifier = sum(1 for kind, _, _ in inst.distractors if kind == "quantifier")
    meta = {
        "distractor_answers": [num_out(b) for b in bait_values(inst.chain, inst.distractors)],
        "distractor_sentences": sentences,
        "instance": {
            "ops": [list(op) for op in inst.chain.ops],
            "distractors": [list(d) for d in inst.distractors],
        },
        "realized": {
            "n_steps": params["n_steps"],
            "n_distractors": len(inst.distractors) - n_quantifier,
            "n_same_unit": n_same,
            "quantifier": n_quantifier,
        },
    }
    return paragraphs, key, meta


def gen_gsm_noop(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_gsm_noop", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
