import dataclasses
from collections.abc import Mapping
from fractions import Fraction

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.text_en import fmt_int
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {"digits_a": 5, "digits_b": 3},
    0: {"digits_a": 6, "digits_b": 4},
    1: {"digits_a": 6, "digits_b": 5},
    2: {"digits_a": 7, "digits_b": 5},
}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base",)
MIN_DENSITY = Fraction(3, 5)


@dataclasses.dataclass(frozen=True)
class Inst:
    a: int
    b: int


def carry_density(a: int, b: int) -> Fraction:
    parts = [(j, a * int(d)) for j, d in enumerate(reversed(str(b)))]
    width = max(j + len(str(p)) for j, p in parts)
    carry = 0
    columns = 0
    carried = 0
    for i in range(width):
        total = carry
        digits = 0
        for j, p in parts:
            if j <= i < j + len(str(p)):
                total += p // 10 ** (i - j) % 10
                digits += 1
        carry = total // 10
        if digits >= 2:
            columns += 1
            if carry >= 1:
                carried += 1
    return Fraction(carried, columns)


def _number(rng: Rng, digits: int) -> int:
    n = 0
    for _ in range(digits):
        n = n * 10 + rng.randint(2, 9)
    return n


def valid(inst: Inst) -> str | None:
    if carry_density(inst.a, inst.b) < MIN_DENSITY:
        return "carry_density"
    return None


def draw(rng: Rng, params: dict) -> Inst | None:
    a = _number(rng, params["digits_a"])
    b = _number(rng, params["digits_b"])
    inst = Inst(a, b)
    return inst if valid(inst) is None else None


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    a = fmt_int(inst.a)
    b = fmt_int(inst.b)
    paragraphs = [f"Compute {a} \N{MULTIPLICATION SIGN} {b}. Give the exact result."]
    key = {"value": inst.a * inst.b}
    meta = {
        "instance": {"a": inst.a, "b": inst.b},
        "carry_density": carry_density(inst.a, inst.b),
        "realized": {"digits_a": params["digits_a"], "digits_b": params["digits_b"]},
    }
    return paragraphs, key, meta


def gen_mult_carry(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_mult_carry", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
