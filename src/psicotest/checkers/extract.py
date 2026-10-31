import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from psicotest.checkers.text import NUMBER_WORDS, fold

RESP_LINE_RE = re.compile(r"^\s*ANSWER\s*:\s*(.+?)\s*\.?\s*$", re.IGNORECASE)
CLAR_LINE_RE = re.compile(r"^\s*CLARIFICATION\s*:\s*(.*?)\s*$", re.IGNORECASE)
BOXED_RE = re.compile(r"\\boxed\{([^{}]*)\}")
NUM_TOKEN_RE = re.compile(r"(?<![\w.,])[+-]?\d(?:[\d.,]*\d)?(?!\w)")
NUM_ANY_RE = re.compile(r"\d(?:[\d.,]*\d)?")
NUM_BODY_RE = re.compile(r"([+-]?)(\d(?:[\d.,]*\d)?)")
PAREN_TAIL_RE = re.compile(r"\s*\(([^()]*)\)\s*$")
APPROX_RE = re.compile(r"^(?:\u2248|~|approx(?:\.|imately)?)\s*", re.IGNORECASE)
SCI_RE = re.compile(
    r"([+-]?\d(?:[\d.,]*\d)?)\s*[x\u00d7*\u00b7]\s*10\s*\^\s*([+-]?\d{1,3})",
    re.IGNORECASE,
)
LEAD_NUM_RE = re.compile(r"([\u20ac\u00a3]\s*)?([+-]?\d(?:[\d.,]*\d)?)\s*(.*)")
UNIT_TAIL_RE = re.compile(
    r"(?:[^\W\d_]+\.?|[\u20ac\u00a3%\u00b0\u00ba/])"
    r"(?:\s*(?:[^\W\d_]+\.?|[\u20ac\u00a3%\u00b0\u00ba/]))*"
)


def preclean(text: str | None) -> str:
    if text is None:
        return ""
    s = unicodedata.normalize("NFKC", text)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    for ch in ("\u00a0", "\u202f", "\u2007"):
        s = s.replace(ch, " ")
    prev = None
    while prev != s:
        prev = s
        s = BOXED_RE.sub(lambda m: m.group(1), s)
    return s.replace("**", "").replace("__", "").replace("`", "").replace("$", "")


@dataclass(frozen=True)
class Extraction:
    text: str
    lines: tuple[str, ...]
    values: tuple[str, ...]
    resp_lines: tuple[int, ...]
    value: str | None
    n_resp: int
    last_line_ok: bool
    multi: bool


def extract_answer(content: str | None) -> Extraction:
    if content is not None and not isinstance(content, str):
        raise TypeError("content must be str or None")
    text = preclean(content)
    lines = tuple(text.split("\n"))
    values = []
    resp_lines = []
    for i, line in enumerate(lines):
        m = RESP_LINE_RE.match(line)
        if m is not None:
            values.append(m.group(1))
            resp_lines.append(i)
    value = values[-1] if values else None
    n_resp = len(values)
    last_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() != "":
            last_idx = i
            break
    last_line_ok = n_resp >= 1 and resp_lines[-1] == last_idx
    multi = len({re.sub(r"\s+", "", fold(v)) for v in values}) > 1
    return Extraction(
        text, lines, tuple(values), tuple(resp_lines), value, n_resp, last_line_ok, multi
    )


def parse_number(s: str) -> tuple[Decimal | None, set[str]]:
    s = s.replace("\u2212", "-").strip()
    if s == "":
        return None, set()
    if fold(s) in NUMBER_WORDS:
        return Decimal(NUMBER_WORDS[fold(s)]), {"FMT"}
    m = NUM_BODY_RE.fullmatch(s)
    if m is None:
        return None, set()
    sign, body = m.groups()

    def dec_of(i: str, f: str) -> Decimal:
        return Decimal(sign + i + ("." + f if f else ""))

    def thousands(sep: str, x: str) -> bool:
        return re.fullmatch(r"\d{1,3}(?:" + re.escape(sep) + r"\d{3})+", x) is not None

    has_dot = "." in body
    has_comma = "," in body
    if has_dot and has_comma:
        if body.rfind(".") > body.rfind(","):
            dec, th = ".", ","
        else:
            dec, th = ",", "."
        i, f = body.rsplit(dec, 1)
        if th in f or not thousands(th, i):
            return None, set()
        return dec_of(i.replace(th, ""), f), {"R2_FAIL"}
    if has_dot:
        parts = body.split(".")
        if len(parts) == 2:
            return dec_of(parts[0], parts[1]), set()
        if thousands(".", body):
            return dec_of(body.replace(".", ""), ""), {"R2_FAIL"}
        return None, set()
    if has_comma:
        if thousands(",", body):
            return dec_of(body.replace(",", ""), ""), {"R2_FAIL"}
        parts = body.split(",")
        if len(parts) == 2:
            return dec_of(parts[0], parts[1]), {"R2_FAIL", "FMT"}
        return None, set()
    return dec_of(body, ""), set()


@dataclass(frozen=True)
class Scalar:
    status: str
    number: Decimal | None
    flags: frozenset[str]
    detail: str


def parse_scalar(text: str, allow_eq: bool = True) -> Scalar:
    flags: set[str] = set()
    details: list[str] = []
    s = text.replace("\u2212", "-").strip()
    while True:
        m = PAREN_TAIL_RE.search(s)
        if m is None:
            break
        if any(ch.isdigit() for ch in m.group(1)):
            return Scalar("ambig", None, frozenset(flags), ";".join([*details, "paren_number"]))
        s = s[: m.start()].rstrip()
    m = APPROX_RE.match(s)
    if m is not None:
        s = s[m.end() :]
        flags.add("FMT")
        details.append("approx")
    if allow_eq and "=" in s:
        s = s.rsplit("=", 1)[1].strip()
        flags.add("FMT")
        details.append("eq_tail")
    if s == "":
        return Scalar("none", None, frozenset(flags), ";".join([*details, "no_number"]))
    m = SCI_RE.fullmatch(s)
    if m is not None:
        n, nf = parse_number(m.group(1))
        if n is None:
            return Scalar("ambig", None, frozenset(flags), ";".join([*details, "badnum"]))
        t = n.as_tuple()
        num = Decimal((t.sign, t.digits, t.exponent + int(m.group(2))))
        flags |= nf
        flags.add("FMT")
        details.append("sci")
        return Scalar("ok", num, frozenset(flags), ";".join(details))
    m = LEAD_NUM_RE.fullmatch(s)
    if m is not None:
        cur, tok, rest = m.groups()
        if cur:
            flags.add("R2_FAIL")
            details.append("unit")
        if rest:
            if UNIT_TAIL_RE.fullmatch(rest) is not None:
                flags.add("R2_FAIL")
                if "unit" not in details:
                    details.append("unit")
            else:
                tail = "multi_number" if NUM_ANY_RE.search(rest) is not None else "trailing_text"
                return Scalar("ambig", None, frozenset(flags), ";".join([*details, tail]))
        n, nf = parse_number(tok)
        if n is None:
            return Scalar("ambig", None, frozenset(flags), ";".join([*details, "badnum"]))
        flags |= nf
        return Scalar("ok", n, frozenset(flags), ";".join(details))
    if not any(ch.isdigit() for ch in s):
        n, nf = parse_number(s)
        if n is not None:
            flags |= nf
            details.append("words")
            return Scalar("ok", n, frozenset(flags), ";".join(details))
        return Scalar("none", None, frozenset(flags), ";".join([*details, "no_number"]))
    tail = "multi_number" if len(NUM_ANY_RE.findall(s)) >= 2 else "lead_text"
    return Scalar("ambig", None, frozenset(flags), ";".join([*details, tail]))


def number_tokens(text: str) -> list[Decimal]:
    out = []
    for tok in NUM_TOKEN_RE.findall(text):
        n, _ = parse_number(tok)
        if n is not None:
            out.append(n)
    return out
