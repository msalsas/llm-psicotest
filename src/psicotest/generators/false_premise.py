import dataclasses
from collections.abc import Mapping

from psicotest.generators.core import check_variant, draw_until, finish, resolve_knobs
from psicotest.generators.text_en import fmt_int
from psicotest.rng import Rng
from psicotest.spec import GenContext

LADDER = {
    -1: {"digits_a": 2, "digits_b": 2, "k": 1, "plausibility": "L0", "story": 0},
    0: {"digits_a": 3, "digits_b": 2, "k": None, "plausibility": "L1", "story": 0},
    1: {"digits_a": 3, "digits_b": 3, "k": None, "plausibility": "L2", "story": 0},
    2: {"digits_a": 3, "digits_b": 3, "k": None, "plausibility": "L2", "story": 1},
}
OVERRIDES: dict[str, tuple[int, int]] = {}
VARIANTS = ("base",)
STORY = (
    "A workshop makes {a} parts a day for {b} days. As we already know, "
    "{a} \N{MULTIPLICATION SIGN} {b} = {f}. The next month it makes {k} times that amount and, "
    "on top of that, {c} loose parts for a special order. "
    "How many parts does it make the next month?"
)


@dataclasses.dataclass(frozen=True)
class Inst:
    a: int
    b: int
    k: int
    c: int
    false_product: int
    level: str


def valid(true_product: int, false_product: int, k: int, c: int, level: str) -> str | None:
    d = false_product - true_product
    if d == 0:
        return "d_zero"
    if false_product <= 0:
        return "F_nonpositive"
    t_digits = str(true_product)
    f_digits = str(false_product)
    if len(f_digits) != len(t_digits):
        return "length_changed"
    differing = sum(1 for x, y in zip(t_digits, f_digits, strict=True) if x != y)
    if level == "L0" and differing != 1:
        return "level_violation"
    if level == "L1" and t_digits[-1] != f_digits[-1]:
        return "level_violation"
    if level == "L2" and (d % 9 != 0 or t_digits[-1] != f_digits[-1]):
        return "level_violation"
    key = k * true_product + c
    absorbed = k * false_product + c
    if len({key, absorbed, true_product, false_product}) != 4:
        return "not_distinct"
    if abs(absorbed - key) < 10:
        return "absorbed_too_close"
    return None


def _change(rng: Rng, digits: list[int], level: str) -> list[int] | None:
    out = list(digits)
    last = len(digits) - 1
    if level in ("L0", "L1"):
        p = rng.below(last + 1 if level == "L0" else last)
        out[p] = rng.choice([x for x in range(10) if x != digits[p]])
        return out
    if rng.choice(("nine", "pair")) == "nine":
        spots = [p for p in range(last) if digits[p] in (0, 9)]
        if not spots:
            return None
        p = rng.choice(spots)
        out[p] = 9 - digits[p]
        return out
    p, q = rng.sample(range(last), 2)
    delta = rng.randint(1, 8)
    out[p] += delta
    out[q] -= delta
    if not 0 <= out[p] <= 9 or not 0 <= out[q] <= 9:
        return None
    return out


def draw(rng: Rng, params: dict) -> Inst | None:
    a = rng.randint(10 ** (params["digits_a"] - 1), 10 ** params["digits_a"] - 1)
    b = rng.randint(10 ** (params["digits_b"] - 1), 10 ** params["digits_b"] - 1)
    k = params["k"] if params["k"] is not None else rng.choice((2, 3))
    c = rng.randint(11, 99)
    level = params["plausibility"]
    changed = _change(rng, [int(ch) for ch in str(a * b)], level)
    if changed is None:
        return None
    false_product = int("".join(str(x) for x in changed))
    if valid(a * b, false_product, k, c, level) is not None:
        return None
    return Inst(a, b, k, c, false_product, level)


def render(inst: Inst, params: dict, ctx: GenContext) -> tuple[list[str], dict, dict]:
    a = fmt_int(inst.a)
    b = fmt_int(inst.b)
    f = fmt_int(inst.false_product)
    if params["story"]:
        text = STORY.format(a=a, b=b, f=f, k=fmt_int(inst.k), c=fmt_int(inst.c))
    else:
        times = "\N{MULTIPLICATION SIGN}"
        if inst.k == 1:
            expr = f"{a} {times} {b} + {fmt_int(inst.c)}"
        else:
            expr = f"{fmt_int(inst.k)} {times} ({a} {times} {b}) + {fmt_int(inst.c)}"
        text = f"As we already know, {a} {times} {b} = {f}. Compute {expr}."
    true_product = inst.a * inst.b
    key = {"value": inst.k * true_product + inst.c}
    meta = {
        "true_product": true_product,
        "false_product": inst.false_product,
        "absorbed": inst.k * inst.false_product + inst.c,
        "k": inst.k,
        "c": inst.c,
        "level": inst.level,
        "instance": {
            "a": inst.a,
            "b": inst.b,
            "k": inst.k,
            "c": inst.c,
            "false_product": inst.false_product,
        },
        "realized": {
            "digits_a": params["digits_a"],
            "digits_b": params["digits_b"],
            "k": inst.k,
            "plausibility": params["plausibility"],
            "story": params["story"],
        },
    }
    return [text], key, meta


def gen_false_premise(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    params = resolve_knobs(knobs, LADDER, OVERRIDES)
    inst = draw_until("gen_false_premise", rng, draw, params)
    paragraphs, key, meta = render(inst, params, ctx)
    prompt, clause = finish(paragraphs, ctx)
    if clause is not None:
        meta["animal_clause"] = clause
    return prompt, key, meta
