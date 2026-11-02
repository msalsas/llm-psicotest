"""Free-form interview generator (family IV).

Elicits at least 150 words of opinion prose inside a BEGIN/END block, scored
only by structural metrics (no content judgment, no ANSWER line). The slot
selects its frozen prompt pool through the `pool` knob (0 = S33, 1 = S34).
"""

from collections.abc import Mapping

from psicotest.generators.core import check_variant, finish, resolve_knobs
from psicotest.rng import Rng
from psicotest.spec import GenContext

VARIANTS = ("base",)

LADDER = {0: {"word_floor": 150, "pool": 0}}
OVERRIDES: dict[str, tuple[int, int]] = {"pool": (0, 1)}

PROMPT_POOL_S33: tuple[tuple[str, str], ...] = (
    (
        "iv_workspace",
        "Describe your ideal workspace environment in detail. Explain which "
        "elements contribute most to focus and productivity, and discuss how "
        "the physical arrangement affects your work habits. Include at least "
        "three specific features and justify why each matters to you.",
    ),
    (
        "iv_learning",
        "Compare two different approaches to learning a new skill: self-study "
        "with online resources versus structured lessons with an instructor. "
        "Argue which approach you believe is more effective for most people, "
        "providing specific reasons and addressing potential counterarguments.",
    ),
)

PROMPT_POOL_S34: tuple[tuple[str, str], ...] = (
    (
        "iv_decisions",
        "Describe a situation where making a quick decision is better than "
        "waiting for complete information. Explain the factors that make speed "
        "valuable in such cases and discuss how someone can recognize when "
        "they are in this type of situation versus one requiring careful analysis.",
    ),
    (
        "iv_communication",
        "Compare written communication with spoken conversation for resolving "
        "disagreements. Argue which medium tends to produce better outcomes "
        "and explain why, while acknowledging situations where the other "
        "approach might be preferable.",
    ),
)

SLOT_POOLS = (PROMPT_POOL_S33, PROMPT_POOL_S34)


def gen_interview(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    word_floor = params["word_floor"]
    prompt_id, prompt_text = rng.choice(SLOT_POOLS[params["pool"]])
    paragraphs = [
        prompt_text,
        f"Your response must be at least {word_floor} words.",
        "Format your answer as a single block:\n"
        "BEGIN\n"
        "<your response here>\n"
        "END\n"
        "\n"
        "Do not include any text outside the BEGIN/END markers except optional brief preamble.",
    ]
    prompt, clause = finish(paragraphs, ctx)
    key = {"word_floor": word_floor}
    meta = {
        "instance": {"prompt_id": prompt_id},
        "realized": {"level": knobs["level"]},
        "prompt_id": prompt_id,
    }
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
