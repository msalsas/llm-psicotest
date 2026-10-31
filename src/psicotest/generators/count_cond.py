import dataclasses
from collections.abc import Mapping

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.lexicon import CNT_WORDS
from psicotest.generators.text_en import join_en
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {"n_words": 40, "n_conds": 1},
    0: {"n_words": 40, "n_conds": 2},
    1: {"n_words": 60, "n_conds": 2},
    2: {"n_words": 60, "n_conds": 3},
}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base", "relabel")
LETTERS = "abcdeilmnoprst"
VOWELS = "aeiou"
OPS = ("start", "end", "contains", "not_contains", "len_eq", "len_ge", "vowels_eq")
LETTER_OPS = ("start", "end", "contains", "not_contains")
CONTAINS_OPS = ("contains", "not_contains")
MIN_RATE = 15
MAX_RATE = 60
KEY_RANGE = (8, 20)
MIN_MARGIN = 3


@dataclasses.dataclass(frozen=True)
class Inst:
    word_idx: tuple[int, ...]
    conditions: tuple[tuple, ...]


def holds(word: str, cond: tuple) -> bool:
    op, arg = cond
    if op == "start":
        return word[0] == arg
    if op == "end":
        return word[-1] == arg
    if op == "contains":
        return arg in word
    if op == "not_contains":
        return arg not in word
    if op == "len_eq":
        return len(word) == arg
    if op == "len_ge":
        return len(word) >= arg
    return sum(1 for ch in word if ch in VOWELS) == arg


def count(words: list[str], conditions: tuple) -> int:
    return sum(1 for w in words if all(holds(w, c) for c in conditions))


def valid(inst: Inst) -> str | None:
    words = [CNT_WORDS[i] for i in inst.word_idx]
    key = count(words, inst.conditions)
    if not KEY_RANGE[0] <= key <= KEY_RANGE[1]:
        return "key_range"
    if len(inst.conditions) >= 2 and any(
        count(words, (c,)) < key + MIN_MARGIN for c in inst.conditions
    ):
        return "cond_redundant"
    return None


def _draw_condition(rng: Rng, op: str) -> tuple:
    if op in LETTER_OPS:
        return (op, rng.choice(LETTERS))
    if op == "len_eq":
        return (op, rng.randint(4, 8))
    if op == "len_ge":
        return (op, rng.randint(5, 8))
    return (op, rng.randint(2, 4))


def draw(rng: Rng, params: dict) -> Inst | None:
    conditions: list[tuple] = []
    for _ in range(params["n_conds"]):
        used = [c[0] for c in conditions]
        pool = [
            op
            for op in OPS
            if op not in used and not (op in CONTAINS_OPS and any(u in CONTAINS_OPS for u in used))
        ]
        conditions.append(_draw_condition(rng, rng.choice(pool)))
    matches = count(list(CNT_WORDS), tuple(conditions))
    if matches * 100 < MIN_RATE * len(CNT_WORDS) or matches * 100 > MAX_RATE * len(CNT_WORDS):
        return None
    chosen = rng.sample(range(len(CNT_WORDS)), params["n_words"])
    inst = Inst(tuple(sorted(chosen)), tuple(conditions))
    return inst if valid(inst) is None else None


def condition_text(cond: tuple) -> str:
    op, arg = cond
    if op == "start":
        return f"start with the letter {arg}"
    if op == "end":
        return f"end with the letter {arg}"
    if op == "contains":
        return f"contain the letter {arg}"
    if op == "not_contains":
        return f"do not contain the letter {arg}"
    if op == "len_eq":
        return f"have exactly {arg} letters"
    if op == "len_ge":
        return f"have {arg} or more letters"
    return f"have exactly {arg} vowels"


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    words = [CNT_WORDS[i] for i in inst.word_idx]
    shown = list(words)
    ctx.surface_rng.shuffle(shown)
    texts = [condition_text(c) for c in inst.conditions]
    paragraphs = [
        "Look at this list of words:",
        ", ".join(shown) + ".",
        f"How many words in the list {join_en(texts)}?",
    ]
    key = {"value": count(words, inst.conditions)}
    meta = {
        "words": shown,
        "conditions": [list(c) for c in inst.conditions],
        "single_counts": [count(words, (c,)) for c in inst.conditions],
        "instance": {
            "word_idx": list(inst.word_idx),
            "conditions": [list(c) for c in inst.conditions],
        },
        "realized": {"n_words": params["n_words"], "n_conds": params["n_conds"]},
    }
    return paragraphs, key, meta


def gen_count_cond(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_count_cond", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
