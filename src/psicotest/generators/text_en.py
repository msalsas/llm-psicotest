from collections.abc import Sequence
from decimal import Decimal
from fractions import Fraction

from psicotest.checkers.text import NUMBER_WORDS


def plural(n: int, sg: str, pl: str) -> str:
    return f"{n} {sg}" if n == 1 else f"{n} {pl}"


def join_en(items: Sequence[str], conj: str = "and") -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" {conj} " + items[-1]


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def fmt_int(n: int) -> str:
    return str(n)


def fmt_dec(x: Decimal) -> str:
    return format(x, "f")


def half_up_2dp(fr: Fraction) -> Decimal:
    if fr < 0:
        raise ValueError("negative value")
    q = (fr.numerator * 200 + fr.denominator) // (2 * fr.denominator)
    return Decimal(f"{q // 100}.{q % 100:02d}")


def num_out(fr: Fraction) -> int | Decimal:
    if fr.denominator == 1:
        return int(fr)
    return half_up_2dp(fr)


def num_word(n: int) -> str:
    keys = [k for k, v in NUMBER_WORDS.items() if v == n]
    if len(keys) != 1:
        raise ValueError("no unique number word")
    return keys[0]
