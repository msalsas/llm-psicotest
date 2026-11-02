"""Checker for IV (interview) items.

Structural metrics only (T5E D8): M2 repeated 8-gram (loop_ngram), M3
degenerate sentence length (degenerate_sentence), M4 word floor (too_short).
Non-Latin leakage (M1) is not checked here: the driver leak hook zeroes every
capability item containing CJK. An extraction failure or empty block is `fmt`.
"""

import re

from psicotest.checkers import schema
from psicotest.checkers.common import make_result
from psicotest.checkers.extract import extract_block, fold

NGRAM = 8
MIN_SENTENCE_WORDS = 3
MAX_SENTENCE_WORDS = 45
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_TRAILING_PUNCT_RE = re.compile(r"[.!?]+$")


def has_repeated_ngram(text: str, n: int = NGRAM) -> bool:
    # fold() keeps punctuation attached, so n-gram tokens include punctuation by design.
    words = fold(text).split()
    seen = set()
    for i in range(len(words) - n + 1):
        gram = tuple(words[i : i + n])
        if gram in seen:
            return True
        seen.add(gram)
    return False


def split_sentences(text: str) -> list[str]:
    # Split only where [.!?]+ is followed by whitespace; a fragment under three
    # words that does not start uppercase (e.g. "g. a tool") belongs to the
    # previous sentence (a leading one merges forward into the next).
    sentences: list[str] = []
    carry = ""
    for part in _SENTENCE_SPLIT_RE.split(text.strip()):
        part = part.strip()
        if not part:
            continue
        if carry:
            part = f"{carry} {part}"
            carry = ""
        is_fragment = len(part.split()) < MIN_SENTENCE_WORDS and not part[0].isupper()
        if is_fragment and sentences:
            sentences[-1] = f"{sentences[-1]} {part}"
        elif is_fragment:
            carry = part
        else:
            sentences.append(part)
    if carry:
        sentences.append(carry)
    return [_TRAILING_PUNCT_RE.sub("", s) for s in sentences]


def has_degenerate_sentence(text: str) -> bool:
    return any(
        not MIN_SENTENCE_WORDS <= len(s.split()) <= MAX_SENTENCE_WORDS
        for s in split_sentences(text)
    )


def check_iv(content, finish_reason, reasoning, item):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "IV")
    if early is not None:
        return early
    block, extract_flags = extract_block(pre.ext.text)
    if extract_flags or not block:
        if reasoning is not None and reasoning.strip():
            return make_result("NOANS", None, ("REASONING_ONLY",), "fmt")
        return make_result("NOANS", None, ("FMT",), "fmt")
    flags = set(pre.flags)
    flags.add("R2_OK")
    details = []
    if has_repeated_ngram(block):
        details.append("loop_ngram")
    if has_degenerate_sentence(block):
        details.append("degenerate_sentence")
    if len(block.split()) < item.key["word_floor"]:
        details.append("too_short")
    outcome = "OK" if not details else "WRONG"
    return make_result(outcome, block, flags, ";".join(details))
