"""Cross-turn consistency generator (family PC).

Both twins of a pair draw from the same instance RNG stream, so they share the
question id and canonical answer; ctx.variant ("pc1" or "pc2", "base" aliasing
"pc1") selects which surface paraphrase is shown. Levels -1..1 draw one-hop
DECISION_POOL questions; level 2 (hops=2) draws a TWO_HOP_POOL chain whose
premises are carried inside both surfaces.
"""

from collections.abc import Mapping

from psicotest.generators.core import check_variant, finish, resolve_knobs
from psicotest.rng import Rng
from psicotest.spec import GenContext

VARIANTS = ("base", "pc1", "pc2")
_SURFACE_INDEX = {"base": 0, "pc1": 0, "pc2": 1}

LADDER = {
    -1: {"hops": 1},
    0: {"hops": 1},
    1: {"hops": 1},
    2: {"hops": 2},
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

# Two-hop pool: (question_id, canonical_answer, premises, base_question,
# variant_surfaces). The answer chains the first two premises; the third is a
# true distractor that the answer never uses.
TWO_HOP_POOL: tuple[tuple[str, str, tuple[str, str, str], str, tuple[str, str]], ...] = (
    (
        "chain_height_1",
        "yes",
        (
            "Alice is taller than Bob.",
            "Bob is taller than Carol.",
            "Diana is shorter than Carol.",
        ),
        "Is Alice taller than Carol?",
        (
            "Given these facts about height: (1) Alice is taller than Bob, (2) Bob is taller "
            "than Carol, (3) Diana is shorter than Carol. Determine: Is Alice taller than Carol?",
            "Consider three height comparisons: Alice exceeds Bob in height, Bob exceeds Carol "
            "in height, and Diana is shorter than Carol. Does Alice exceed Carol in height?",
        ),
    ),
    (
        "chain_height_2",
        "no",
        (
            "Eve is shorter than Frank.",
            "Frank is shorter than Grace.",
            "Henry is taller than Grace.",
        ),
        "Is Eve taller than Grace?",
        (
            "Height facts: Eve is shorter than Frank, Frank is shorter than Grace, Henry is "
            "taller than Grace. Is Eve taller than Grace?",
            "Given that Eve < Frank in height and Frank < Grace in height (with Henry taller "
            "than Grace), is Eve taller than Grace?",
        ),
    ),
    (
        "chain_age_1",
        "yes",
        (
            "The red book was published before the blue book.",
            "The blue book was published before the green book.",
            "The yellow book was published after the green book.",
        ),
        "Was the red book published before the green book?",
        (
            "Publication order: red before blue, blue before green, yellow after green. Did the "
            "red book come out before the green book?",
            "Consider: red book -> blue book -> green book -> yellow book in "
            "publication order (arrows mean 'before'). Was red published before green?",
        ),
    ),
    (
        "chain_age_2",
        "no",
        (
            "Project Alpha started after Project Beta.",
            "Project Beta started after Project Gamma.",
            "Project Delta started before Project Gamma.",
        ),
        "Did Project Alpha start before Project Gamma?",
        (
            "Timeline: Alpha after Beta, Beta after Gamma, Delta before Gamma. Did Alpha start "
            "before Gamma?",
            "Project order facts: Gamma -> Beta -> Alpha (arrows mean 'started before'), "
            "with Delta before Gamma. Did Alpha begin before Gamma?",
        ),
    ),
)


def gen_prose_consistency(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    hops = resolve_knobs(knobs, LADDER, OVERRIDES)["hops"]
    premises: tuple[str, ...] = ()
    if hops == 2:
        question_id, canonical, premises, base_question, surfaces = rng.choice(TWO_HOP_POOL)
    else:
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
    if hops == 2:
        meta["hops"] = 2
        meta["premises"] = list(premises)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
