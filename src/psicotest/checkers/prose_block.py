"""Checker for PR (prose_block) items.

Constraint failures are reported as detail tokens (word_count_low,
word_count_high, sentence_count, banned_letter, missing_phrase,
same_start_word, topic_lead, and for level 3 start_words, distinct_starts); the
framework flag vocabulary only carries FMT/R2_* for format-level problems.
"""

import re

from psicotest.checkers import schema
from psicotest.checkers.common import make_result
from psicotest.checkers.extract import extract_block

SENTENCE_END_RE = re.compile(r"[.!?]+")


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_END_RE.split(text) if part.strip()]


def _initial(sentence: str) -> str:
    return next((ch.casefold() for ch in sentence if ch.isalpha()), "")


_LEADING_PUNCT = "\"'\u201c\u201d\u2018\u2019\u00ab\u00bb([{<"


def _first_word(sentence: str) -> str:
    words = sentence.lstrip(_LEADING_PUNCT).split()
    return words[0] if words else ""


def check_pr(content, finish_reason, reasoning, item):
    pre, early = schema.begin(content, finish_reason, reasoning, item, "PR")
    if early is not None:
        return early
    block, extract_flags = extract_block(pre.ext.text)
    if extract_flags:
        if reasoning is not None and reasoning.strip():
            return make_result("NOANS", None, ("REASONING_ONLY",), "no_block")
        return make_result("NOANS", None, ("FMT",), "no_block")
    flags = set(pre.flags)
    flags.add("R2_OK")
    constraints = item.key["constraints"]
    details = []
    word_count = len(block.split())
    if word_count < constraints["word_count_min"]:
        details.append("word_count_low")
    if word_count > constraints["word_count_max"]:
        details.append("word_count_high")
    sentences = _sentences(block)
    count_max = constraints.get("sentence_count_max", constraints["sentence_count"])
    if not constraints["sentence_count"] <= len(sentences) <= count_max:
        details.append("sentence_count")
    banned = constraints["banned_letter"].lower()
    if banned in block.lower():
        details.append("banned_letter")
    phrases = constraints.get("required_phrases", [constraints["required_phrase"]])
    if any(phrase.lower() not in block.lower() for phrase in phrases):
        details.append("missing_phrase")
    start_word = constraints.get("same_start_word")
    if start_word is not None and any(
        _first_word(sentence).lower() != start_word.lower() for sentence in sentences
    ):
        details.append("same_start_word")
    if constraints.get("topic_lead"):
        topic = constraints["topic"].lower()
        if not sentences or not sentences[0].lower().startswith(topic):
            details.append("topic_lead")
    start_words = constraints.get("start_words")
    if start_words is not None:
        firsts = [_first_word(sentence).casefold().strip(",;:") for sentence in sentences]
        if any(firsts.count(word.casefold()) != 1 for word in start_words):
            details.append("start_words")
    if constraints.get("distinct_starts"):
        initials = [_initial(sentence) for sentence in sentences]
        if len(initials) != len(set(initials)):
            details.append("distinct_starts")
    outcome = "OK" if not details else "WRONG"
    return make_result(outcome, block, flags, ";".join(details))
