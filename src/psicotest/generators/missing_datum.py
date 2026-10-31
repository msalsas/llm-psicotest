import dataclasses
from collections.abc import Mapping

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.lexicon import animal_clause
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
from psicotest.generators.text_en import fmt_int
from psicotest.rng import Rng, derive_seed
from psicotest.spec import GenContext, Item

LADDER = {0: {}}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base", "relabel")
ALLOWED = (ADD_GROUPS, ADD, SUB)
DATUM_KINDS = ("per_container", "n_containers")
HIDDEN_ARG = {"per_container": 2, "n_containers": 1}
FORMS = {"per_container": "no_c", "n_containers": "no_b"}


@dataclasses.dataclass(frozen=True)
class Inst:
    chain: Chain
    datum_kind: str
    distractors: tuple


def datum_value(inst: Inst) -> int:
    return inst.chain.ops[first_groups(inst.chain)][HIDDEN_ARG[inst.datum_kind]]


def shown_numbers(inst: Inst) -> set[int]:
    shown = shown_args(inst.chain, first_groups(inst.chain), HIDDEN_ARG[inst.datum_kind])
    return shown | {x for kind, x, _ in inst.distractors if kind != "quantifier"}


def valid(inst: Inst) -> str | None:
    if inst.chain.running[-1] in shown_numbers(inst):
        return "key_in_prompt"
    if 1 <= datum_value(inst) <= 5:
        return "guessable"
    return None


def draw(rng: Rng, params: dict) -> Inst | None:
    chain = draw_chain(rng, 4, ALLOWED, final_div=True)
    if chain is None:
        return None
    datum_kind = rng.choice(DATUM_KINDS)
    distractors = draw_distractors(rng, chain, op_numbers(chain) | {chain.running[-1]}, 0, 2, 0)
    if distractors is None:
        return None
    inst = Inst(chain, datum_kind, distractors)
    return inst if valid(inst) is None else None


def synonyms(inst: Inst, unit_pl: str, cont_sg: str, cont_pl: str) -> list[str]:
    if inst.datum_kind == "per_container":
        return [
            f"number of {unit_pl} per {cont_sg}",
            f"per {cont_sg}",
            f"each {cont_sg}",
            f"in a {cont_sg}",
            f"{unit_pl} are in",
            f"{unit_pl} come in",
            "contains",
            "contain",
            "holds",
            "hold",
        ]
    return [
        f"number of {cont_pl}",
        f"how many {cont_pl}",
        f"count of {cont_pl}",
        f"quantity of {cont_pl}",
        f"{cont_pl} arrive",
        f"{cont_pl} are received",
        f"{cont_pl} there are",
    ]


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    gi = first_groups(inst.chain)
    forms = {gi: (FORMS[inst.datum_kind],)}
    story, _, sc = render_story(ctx.surface_rng, inst.chain, inst.distractors, False, forms)
    value = fmt_int(datum_value(inst))
    if inst.datum_kind == "per_container":
        datum_en = f"Each {sc.cont_sg} holds {value} {sc.unit_pl}."
    else:
        datum_en = f"It receives {value} {sc.cont_pl}."
    key = {"value": inst.chain.running[-1]}
    meta = {
        "datum_kind": inst.datum_kind,
        "datum_value": datum_value(inst),
        "datum_en": datum_en,
        "synonyms": synonyms(inst, sc.unit_pl, sc.cont_sg, sc.cont_pl),
        "instance": {
            "ops": [list(op) for op in inst.chain.ops],
            "distractors": [list(d) for d in inst.distractors],
            "datum_kind": inst.datum_kind,
        },
        "realized": {"level": 0},
    }
    return [story, question(inst.chain, sc)], key, meta


def gen_missing_datum(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_missing_datum", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta


def reply_prompt(item: Item) -> str:
    if item.family != "AMB":
        raise ValueError("not an AMB item")
    parts = ["Missing datum: " + item.meta["datum_en"]]
    if item.animal is not None:
        seed = derive_seed(item.surface_seed, "reply_animal")
        parts.append(animal_clause(item.animal, Rng(seed)))
    parts.append("With this datum, solve the problem.")
    return " ".join(parts)
