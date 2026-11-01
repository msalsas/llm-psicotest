import dataclasses
import itertools
from collections.abc import Mapping

from psicotest.checkers.text import fold
from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.lexicon import pick_names
from psicotest.generators.text_en import join_en, num_word, plural
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {"n_agents": 4, "n_nested": 1},
    0: {"n_agents": 5, "n_nested": 1},
    1: {"n_agents": 7, "n_nested": 2},
    2: {"n_agents": 8, "n_nested": 2},
}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base", "relabel")
ROLE_NAMES = ("knight", "knave", "spy")
PLAIN_KINDS = ("role", "same", "diff", "count")
SPY_KINDS = ("role", "same", "diff")
INNER_KINDS = ("role", "same", "diff")
ROLE_PHRASE = {"knight": "a knight", "knave": "a knave", "spy": "the spy"}
TRIES = 50


@dataclasses.dataclass(frozen=True)
class Inst:
    roles: tuple[str, ...]
    statements: tuple[tuple, ...]


def truth(stmt: tuple, roles: tuple[str, ...]) -> bool:
    op = stmt[0]
    if op == "role":
        return roles[stmt[1]] == stmt[2]
    if op == "same":
        return roles[stmt[1]] == roles[stmt[2]]
    if op == "diff":
        return roles[stmt[1]] != roles[stmt[2]]
    if op == "count":
        return sum(1 for r in roles if r == "knight") == stmt[2]
    asked_role = roles[stmt[1]]
    if asked_role == "spy":
        return True
    return truth(stmt[2], roles) == (asked_role == "knight")


def speaker_ok(roles: tuple[str, ...], speaker: int, stmt: tuple) -> bool:
    role = roles[speaker]
    return role == "spy" or truth(stmt, roles) == (role == "knight")


def assignments(n: int) -> list[tuple[str, ...]]:
    out = []
    for spy in range(n):
        for others in itertools.product(("knight", "knave"), repeat=n - 1):
            out.append((*others[:spy], "spy", *others[spy:]))
    return out


def solutions(statements: tuple[tuple, ...]) -> list[tuple[str, ...]]:
    return [
        roles
        for roles in assignments(len(statements))
        if all(speaker_ok(roles, i, s) for i, s in enumerate(statements))
    ]


def valid(inst: Inst) -> str | None:
    if "knight" not in inst.roles or "knave" not in inst.roles:
        return "degenerate_roles"
    spy_says_count = any(
        s[0] == "count" and r == "spy" for r, s in zip(inst.roles, inst.statements, strict=True)
    )
    if spy_says_count:
        return "spy_count"
    if len(solutions(inst.statements)) != 1:
        return "not_unique"
    return None


def _inner(rng: Rng, others: list[int]) -> tuple:
    kind = rng.choice(INNER_KINDS)
    if kind == "role":
        return (kind, rng.choice(others), rng.choice(ROLE_NAMES))
    x, y = rng.sample(others, 2)
    return (kind, x, y)


def _statement(rng: Rng, n: int, speaker: int, role: str, nested: bool) -> tuple:
    if nested:
        x = rng.choice([a for a in range(n) if a != speaker])
        return ("says", x, _inner(rng, [a for a in range(n) if a not in (speaker, x)]))
    kind = rng.choice(SPY_KINDS if role == "spy" else PLAIN_KINDS)
    if kind == "role":
        return (kind, rng.below(n), rng.choice(ROLE_NAMES))
    if kind == "count":
        return (kind, "knight", rng.randint(1, n - 1))
    x, y = rng.sample(range(n), 2)
    return (kind, x, y)


def draw(rng: Rng, params: dict) -> Inst | None:
    n = params["n_agents"]
    spy = rng.below(n)
    roles = tuple("spy" if i == spy else ("knight", "knave")[rng.below(2)] for i in range(n))
    if "knight" not in roles or "knave" not in roles:
        return None
    nested = rng.sample(range(n), params["n_nested"])
    remaining = assignments(n)
    statements = []
    for speaker in range(n):
        best = None
        for _ in range(TRIES):
            stmt = _statement(rng, n, speaker, roles[speaker], speaker in nested)
            if not speaker_ok(roles, speaker, stmt):
                continue
            left = [r for r in remaining if speaker_ok(r, speaker, stmt)]
            if best is None or len(left) < len(best[1]):
                best = (stmt, left)
        if best is None:
            return None
        statements.append(best[0])
        remaining = best[1]
    inst = Inst(roles, tuple(statements))
    return inst if valid(inst) is None else None


def named(stmt: tuple, names: list[str]) -> list:
    op = stmt[0]
    if op == "role":
        return [op, names[stmt[1]], stmt[2]]
    if op in ("same", "diff"):
        return [op, names[stmt[1]], names[stmt[2]]]
    if op == "count":
        return [op, stmt[1], stmt[2]]
    return [op, names[stmt[1]], named(stmt[2], names)]


def statement_text(stmt: list, speaker: str) -> str:
    op = stmt[0]
    if op == "role":
        who = "I am" if stmt[1] == speaker else f"{stmt[1]} is"
        return f"{who} {ROLE_PHRASE[stmt[2]]}."
    if op == "same":
        return f"{stmt[1]} and {stmt[2]} are of the same type."
    if op == "diff":
        return f"{stmt[1]} and {stmt[2]} are of different types."
    if op == "count":
        verb = "is" if stmt[2] == 1 else "are"
        return f"Among all of us there {verb} exactly {plural(stmt[2], 'knight', 'knights')}."
    inner = statement_text(stmt[2], speaker)[:-1]
    return f"If you asked {stmt[1]}, they would say that {inner}."


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    n = params["n_agents"]
    names = pick_names(ctx.surface_rng, n)
    agents = sorted(names, key=fold)
    order = [names.index(a) for a in agents]
    statements = [[agents[k], named(inst.statements[i], names)] for k, i in enumerate(order)]
    lines = [f'- {speaker}: "{statement_text(s, speaker)}"' for speaker, s in statements]
    paragraphs = [
        "On an island live knights, who always tell the truth, and knaves, who always lie. "
        "Today there is also a spy among them, who may tell the truth or lie. "
        f"These {num_word(n)} people are {join_en(agents)}, and exactly one of them is the spy.",
        "Each one makes a statement:\n" + "\n".join(lines),
        "What is each person? Give the answer in the format "
        "knights: <names>; knaves: <names>; spy: <name>.",
    ]
    key = {"roles": {names[i]: inst.roles[i] for i in range(n)}}
    meta = {
        "agents": agents,
        "statements": statements,
        "instance": {
            "roles_idx": list(inst.roles),
            "statements_idx": [list(s) for s in inst.statements],
        },
        "realized": {"n_agents": n, "n_nested": params["n_nested"]},
    }
    return paragraphs, key, meta


def gen_knights_spy(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_knights_spy", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
