"""Cross-turn consistency generator (family PC).

Both twins of a pair draw from the same instance RNG stream, so they share the
question id and canonical answer; ctx.variant ("pc1" or "pc2", "base" aliasing
"pc1") selects which surface paraphrase is shown. The level knob is reserved
and currently unused.
"""

from collections.abc import Mapping

from psicotest.generators.core import check_variant, finish, resolve_knobs
from psicotest.rng import Rng
from psicotest.spec import GenContext

VARIANTS = ("base", "pc1", "pc2")
_SURFACE_INDEX = {"base": 0, "pc1": 0, "pc2": 1}

LADDER = {
    -1: {},
    0: {},
    1: {},
    2: {},
}
OVERRIDES: dict[str, tuple[int, int]] = {}

# Frozen decision question pool: (question_id, canonical_answer, base_question,
# variant_surfaces) with index 0 = variant pc1 and index 1 = variant pc2.
DECISION_POOL: tuple[tuple[str, str, str, tuple[str, str]], ...] = (
    (
        "cmp_47_23",
        "yes",
        "Is 47 greater than 23?",
        (
            "Consider the numbers 47 and 23. Is the first number larger than the second?",
            "Compare forty-seven to twenty-three. Does the former exceed the latter?",
        ),
    ),
    (
        "cmp_15_89",
        "no",
        "Is 15 greater than 89?",
        (
            "Think about 15 and 89. Is 15 the bigger number?",
            "Between fifteen and eighty-nine, is fifteen larger?",
        ),
    ),
    (
        "order_mon_wed",
        "yes",
        "Does Monday come before Wednesday in a standard week?",
        (
            "In the days of the week, is Monday earlier than Wednesday?",
            "Considering a typical week, does Monday precede Wednesday?",
        ),
    ),
    (
        "order_sat_tue",
        "no",
        "Does Saturday come before Tuesday in a standard week?",
        (
            "In the weekly order, is Saturday earlier than Tuesday?",
            "Does Saturday precede Tuesday in a normal week?",
        ),
    ),
    (
        "cmp_100_99",
        "yes",
        "Is 100 greater than 99?",
        (
            "Compare one hundred to ninety-nine. Is the first larger?",
            "Between 100 and 99, is 100 the greater value?",
        ),
    ),
    (
        "cmp_50_50",
        "no",
        "Is 50 greater than 50?",
        (
            "Are fifty and fifty such that the first exceeds the second?",
            "Compare 50 to itself. Is it greater than itself?",
        ),
    ),
    (
        "order_jan_mar",
        "yes",
        "Does January come before March in the calendar year?",
        (
            "In the standard calendar, is January earlier than March?",
            "Considering months, does January precede March?",
        ),
    ),
    (
        "order_dec_feb",
        "no",
        "Does December come before February in the calendar year?",
        (
            "In the yearly order, is December earlier than February?",
            "Does December precede February in a calendar year?",
        ),
    ),
)


def gen_prose_consistency(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    resolve_knobs(knobs, LADDER, OVERRIDES)
    question_id, canonical, base_question, surfaces = rng.choice(DECISION_POOL)
    surface = surfaces[_SURFACE_INDEX[ctx.variant]]
    paragraphs = [
        surface,
        "Answer with exactly one word: yes or no.",
        "End your reply with a line of the form `ANSWER: yes` or `ANSWER: no`.",
    ]
    prompt, clause = finish(paragraphs, ctx)
    key = {"value": canonical}
    meta = {
        "instance": {"question_id": question_id},
        "realized": {"level": knobs["level"]},
        "question_id": question_id,
        "base_question": base_question,
        "surface": surface,
    }
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
