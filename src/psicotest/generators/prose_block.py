"""Constrained prose block generator (family PR).

Pool invariant (T5D D7): no topic, required phrase, or start word contains a
letter banned at the level where it is drawn (e, a, t), and every level has one
fixed proof instance (T5D D9) that satisfies every draw at that level.

Pool invariant (T5D D8): the frozen pools and proofs contain no abbreviations
or decimals, so sentence counting by splitting on [.!?]+ and word counting by
whitespace splitting inside the BEGIN block are exact.
"""

from collections.abc import Mapping

from psicotest.generators.core import check_variant, finish, resolve_knobs
from psicotest.rng import Rng
from psicotest.spec import GenContext

VARIANTS = ("base",)

# Topics avoid e, a and t entirely, so any topic is safe at levels -1, 0 and 1
# where the banned letter is drawn from {e, a} or {e, t}.
TOPIC_POOL: tuple[str, ...] = (
    "crisp morning",
    "dim room",
    "cold wind",
    "high cliff",
    "mild sun",
    "gold ring",
    "loud horn",
    "long film",
    "big hill",
    "old mill",
    "moss rock",
    "dry wood",
)

# Level 2 requires the first sentence to start with the topic words, and every
# sentence must start with the level start word, so the level-2 topic is fixed
# to the proof's opening words ("snowy" carries no e; the level only bans e).
TOPIC_POOL_L2: tuple[str, ...] = ("snowy mountains",)

# Every phrase in a level pool appears verbatim in that level's proof, and no
# phrase contains a letter banned at that level.
PHRASE_POOL_L0: tuple[str, ...] = ("for now", "in short", "in truth", "with skill", "in full")
PHRASE_POOL_L1: tuple[str, ...] = ("all in all", "by far", "on hand", "in full")
PHRASE_POOL_L2: tuple[str, ...] = ("in summary", "by all accounts", "in truth")

BANNED_POOL_L0: tuple[str, ...] = ("e", "a")
BANNED_POOL_L1: tuple[str, ...] = ("e", "t")
BANNED_POOL_L2: tuple[str, ...] = ("e",)

START_WORD_POOL_L1: tuple[str, ...] = ("all",)
START_WORD_POOL_L2: tuple[str, ...] = ("snowy",)

# One fixed proof instance per level (T5D D9). Each proof satisfies every draw
# at its level: word count inside the level window, exact sentence count, free
# of every letter banned at that level, containing every level phrase, and (for
# levels 1 and 2) starting every sentence with the level start word. Level 2's
# proof opens with the fixed level-2 topic words.
_PROOFS: dict[int, str] = {
    -1: (
        "Cool wind blows on dry wood by old mill rooms for now too. "
        "Long film nights bring soft joy in full. "
        "Mild sun lifts crisp morning fog in short cold bursts. "
        "Bold cooks grill corn with skill on cold iron. "
        "Dim rooms hold soft light in truth plus full hush."
    ),
    0: (
        "Cool wind blows on dry wood by old mill rooms for now too. "
        "Long film nights bring soft joy in full. "
        "Mild sun lifts crisp morning fog in short cold bursts. "
        "Bold cooks grill corn with skill on cold iron. "
        "Dim rooms hold soft light in truth plus full hush."
    ),
    1: (
        "All dull mornings dawn gray and cold. "
        "All our walks bring calm joy by far. "
        "All good music can calm any busy mind all in all. "
        "All bold cooks honor old family soup bowls on hand. "
        "All long songs bring crisp focus and calm. "
        "All dim days call for warm soup in full."
    ),
    2: (
        "snowy mountains stand high in summary. "
        "snowy roofs glow bright all day. "
        "snowy paths grow calm by all accounts. "
        "snowy winds bring bright joy in truth. "
        "snowy hills hold soft light and calm."
    ),
}

LADDER = {
    -1: {"word_count_min": 50, "word_count_max": 80, "sentence_count": 5},
    0: {"word_count_min": 50, "word_count_max": 80, "sentence_count": 5},
    1: {"word_count_min": 40, "word_count_max": 60, "sentence_count": 6},
    2: {"word_count_min": 30, "word_count_max": 45, "sentence_count": 5},
}
OVERRIDES: dict[str, tuple[int, int]] = {}

_PHRASE_POOL_OF_LEVEL = {
    -1: PHRASE_POOL_L0,
    0: PHRASE_POOL_L0,
    1: PHRASE_POOL_L1,
    2: PHRASE_POOL_L2,
}
_BANNED_POOL_OF_LEVEL = {
    -1: BANNED_POOL_L0,
    0: BANNED_POOL_L0,
    1: BANNED_POOL_L1,
    2: BANNED_POOL_L2,
}
_START_POOL_OF_LEVEL = {1: START_WORD_POOL_L1, 2: START_WORD_POOL_L2}


def _draw(rng: Rng, level: int) -> dict:
    params = LADDER[level]
    topics = TOPIC_POOL_L2 if level == 2 else TOPIC_POOL
    start_pool = _START_POOL_OF_LEVEL.get(level)
    constraints = {
        "topic": rng.choice(topics),
        "word_count_min": params["word_count_min"],
        "word_count_max": params["word_count_max"],
        "sentence_count": params["sentence_count"],
        "banned_letter": rng.choice(_BANNED_POOL_OF_LEVEL[level]),
        "required_phrase": rng.choice(_PHRASE_POOL_OF_LEVEL[level]),
        "same_start_word": rng.choice(start_pool) if start_pool else None,
        "topic_lead": level == 2,
    }
    return constraints


def _paragraphs(constraints: dict) -> list[str]:
    lines = [
        f"- Word count: between {constraints['word_count_min']} and "
        f"{constraints['word_count_max']} words (inclusive)",
        (
            f"- Exactly {constraints['sentence_count']} sentences "
            "(each ends with a period or question mark)"
        ),
        f"- Do not use the letter '{constraints['banned_letter']}' anywhere (case-insensitive)",
        f'- Include the phrase "{constraints["required_phrase"]}" verbatim',
    ]
    if constraints["same_start_word"] is not None:
        lines.append(
            f'- Every sentence must start with the word "{constraints["same_start_word"]}"'
        )
    if constraints["topic_lead"]:
        lines.append(f'- Your first sentence must start with the words "{constraints["topic"]}"')
    return [
        f"Write a short paragraph about {constraints['topic']}.",
        "Your response must satisfy all of the following constraints:\n" + "\n".join(lines),
        "Format your answer as a single block:\n"
        "BEGIN\n"
        "<your paragraph here>\n"
        "END\n"
        "\n"
        "Do not include any text outside the BEGIN/END markers except optional brief preamble.",
    ]


def gen_prose_block(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    resolve_knobs(knobs, LADDER, OVERRIDES)
    level = knobs["level"]
    constraints = _draw(rng, level)
    prompt, clause = finish(_paragraphs(constraints), ctx)
    key = {"constraints": constraints}
    meta = {
        "instance": {
            name: constraints[name] for name in ("topic", "banned_letter", "required_phrase")
        },
        "realized": {"level": level},
        "level": level,
        "proof": _PROOFS[level],
    }
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
