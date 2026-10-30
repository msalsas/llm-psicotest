import re
import unicodedata
from collections.abc import Sequence

ARTICLES = ("el", "la", "los", "las", "un", "una", "unos", "unas")
WORD_RE = re.compile(r"[a-z0-9]+")

SMALL = {
    "cero": 0,
    "uno": 1,
    "un": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciseis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
    "veintiuno": 21,
    "veintiun": 21,
    "veintiuna": 21,
    "veintidos": 22,
    "veintitres": 23,
    "veinticuatro": 24,
    "veinticinco": 25,
    "veintiseis": 26,
    "veintisiete": 27,
    "veintiocho": 28,
    "veintinueve": 29,
    "cien": 100,
}

TENS = {
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
    "sesenta": 60,
    "setenta": 70,
    "ochenta": 80,
    "noventa": 90,
}

NUMBER_WORDS = dict(SMALL)
NUMBER_WORDS.update(TENS)
for _tens_word in TENS:
    for _unit_word in (
        "uno",
        "un",
        "una",
        "dos",
        "tres",
        "cuatro",
        "cinco",
        "seis",
        "siete",
        "ocho",
        "nueve",
    ):
        NUMBER_WORDS[f"{_tens_word} y {_unit_word}"] = TENS[_tens_word] + SMALL[_unit_word]


def fold(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


def words(s: str) -> list[str]:
    return WORD_RE.findall(fold(s))


def has_phrase(tokens: Sequence[str], phrase: tuple[str, ...]) -> bool:
    n = len(phrase)
    return any(tuple(tokens[i : i + n]) == phrase for i in range(len(tokens) - n + 1))
