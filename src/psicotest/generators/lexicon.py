from psicotest.checkers.rules import singular_candidates
from psicotest.checkers.text import (
    ANIMAL_STOP_WORDS,
    ANIMAL_WORDS,
    NAME_POOL,
    fold,
    has_phrase,
    words,
)
from psicotest.checkers.text import CNT_WORDS as CNT_WORDS
from psicotest.checkers.text import LABEL_POOL as LABEL_POOL
from psicotest.rng import Rng, derive_seed

TRIGGER_ANIMALS = (("sheep", "a"), ("cat", "a"), ("mouse", "a"), ("fish", "a"))
ANIMAL_CLAUSES = (
    "Someone has drawn {art} {noun} on the blackboard.",
    "A picture of {art} {noun} hangs on the wall.",
    "The cover of the notebook shows {art} {noun}.",
    "On the table there is a mug with {art} {noun} painted on it.",
)
STOP_PHRASES = (
    "big fish",
    "black sheep",
    "cat burglar",
    "computer mouse",
    "fat cat",
    "mister fox",
    "mr fox",
    "sea lion",
)

_ANIMALS = frozenset(ANIMAL_WORDS)
_STOPS = frozenset(ANIMAL_STOP_WORDS)
_ARTICLES = dict(TRIGGER_ANIMALS)


def _hits(token: str, table: frozenset[str]) -> bool:
    return any(c in table for c in singular_candidates(token))


def contains_animal(text: str) -> tuple[str, ...]:
    toks = words(text)
    animals = tuple(t for t in toks if _hits(t, _ANIMALS))
    stops = tuple(f"stop:{t}" for t in toks if _hits(t, _STOPS) and not _hits(t, _ANIMALS))
    phrases = tuple(f"phrase:{p}" for p in STOP_PHRASES if has_phrase(toks, tuple(p.split())))
    return animals + stops + phrases


def animal_clause(noun: str, rng: Rng) -> str:
    if noun not in _ARTICLES:
        raise ValueError("not a trigger animal")
    return ANIMAL_CLAUSES[rng.below(len(ANIMAL_CLAUSES))].format(art=_ARTICLES[noun], noun=noun)


def trigger_animal(battery: str, user_seed: int, order: str, turn: int) -> str:
    seed = derive_seed("psicotest", battery, user_seed, order, turn, "animal")
    return TRIGGER_ANIMALS[seed % len(TRIGGER_ANIMALS)][0]


def pick_names(rng: Rng, k: int) -> list[str]:
    if k > 20:
        raise ValueError("too many names")
    groups: dict[str, list[str]] = {}
    for name in NAME_POOL:
        groups.setdefault(fold(name)[0], []).append(name)
    keys = list(groups)
    return [rng.choice(groups[i]) for i in rng.sample(keys, k)]
