import dataclasses
import math
from collections.abc import Mapping
from fractions import Fraction

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.text_en import fmt_int, half_up_2dp
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {"digits": 3, "extra_ops": 0},
    0: {"digits": 4, "extra_ops": 0},
    1: {"digits": 4, "extra_ops": 1},
    2: {"digits": 4, "extra_ops": 2},
}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base",)
DIVISORS = tuple(d for d in range(11, 100) if math.gcd(d, 10) == 1)


@dataclasses.dataclass(frozen=True)
class Inst:
    a: int
    b: int
    c: int
    e: int | None
    g: int | None
    d: int


def numerator(inst: Inst) -> int:
    return inst.a * inst.b - inst.c * (inst.e or 1) + (inst.g or 0)


def valid(inst: Inst) -> str | None:
    num = numerator(inst)
    if num <= 0:
        return "nonpositive"
    if (num * 100) % inst.d == 0:
        return "terminates"
    return None


def draw(rng: Rng, params: dict) -> Inst | None:
    lo = 10 ** (params["digits"] - 1)
    hi = 10 ** params["digits"] - 1
    a = rng.randint(lo, hi)
    b = rng.randint(lo, hi)
    c = rng.randint(100, 999)
    e = rng.randint(11, 99) if params["extra_ops"] >= 1 else None
    g = rng.randint(100, 999) if params["extra_ops"] >= 2 else None
    inst = Inst(a, b, c, e, g, rng.choice(DIVISORS))
    return inst if valid(inst) is None else None


def expression(inst: Inst) -> str:
    times = "\N{MULTIPLICATION SIGN}"
    text = f"{fmt_int(inst.a)} {times} {fmt_int(inst.b)} \N{MINUS SIGN} {fmt_int(inst.c)}"
    if inst.e is not None:
        text += f" {times} {fmt_int(inst.e)}"
    if inst.g is not None:
        text += f" + {fmt_int(inst.g)}"
    return text


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    exact = Fraction(numerator(inst), inst.d)
    paragraphs = [
        f"Compute ({expression(inst)}) \N{DIVISION SIGN} {fmt_int(inst.d)} "
        "and round the result to two decimal places."
    ]
    key = {"value": half_up_2dp(exact)}
    meta = {
        "instance": {
            "a": inst.a,
            "b": inst.b,
            "c": inst.c,
            "e": inst.e,
            "g": inst.g,
            "d": inst.d,
        },
        "exact": exact,
        "realized": {"digits": params["digits"], "extra_ops": params["extra_ops"]},
    }
    return paragraphs, key, meta


def gen_chain_decimal(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_chain_decimal", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
