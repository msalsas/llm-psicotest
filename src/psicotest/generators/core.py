from collections.abc import Callable, Mapping

from psicotest.generators.lexicon import animal_clause
from psicotest.rng import Rng
from psicotest.spec import GenContext

MAX_ATTEMPTS = 1000
LEVELS = (-1, 0, 1, 2)


class GeneratorExhausted(RuntimeError):
    pass


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def resolve_knobs(
    knobs: Mapping,
    ladder: Mapping[int, Mapping[str, object]],
    overrides: Mapping[str, tuple[int, int]],
) -> dict:
    if "level" not in knobs:
        raise ValueError("missing level")
    level = knobs["level"]
    if not _is_int(level) or level not in ladder:
        raise ValueError("bad level")
    given = {}
    for k, v in knobs.items():
        if k == "level":
            continue
        if k not in overrides:
            raise ValueError(f"unknown knob {k}")
        lo, hi = overrides[k]
        if not _is_int(v) or not lo <= v <= hi:
            raise ValueError(f"knob {k} out of range")
        if level != 0:
            raise ValueError(f"knob {k} needs level 0")
        given[k] = v
    return dict(ladder[level]) | given


def draw_until(
    name: str, rng: Rng, draw: Callable[[Rng, dict], object | None], params: dict
) -> object:
    for _ in range(MAX_ATTEMPTS):
        inst = draw(rng, params)
        if inst is not None:
            return inst
    raise GeneratorExhausted(f"{name}: no instance after {MAX_ATTEMPTS} attempts")


def finish(paragraphs: list[str], ctx: GenContext, slot_par: int = 0) -> tuple[str, str | None]:
    clause = None
    if ctx.animal is not None:
        clause = animal_clause(ctx.animal, ctx.surface_rng)
        paragraphs[slot_par] += " " + clause
    return "\n\n".join(paragraphs), clause


def check_variant(ctx: GenContext, supported: tuple[str, ...]) -> None:
    if ctx.variant not in supported:
        raise ValueError(f"unsupported variant {ctx.variant}")
