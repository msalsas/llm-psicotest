"""Checker for PR (prose_block) items.

Constraint failures are reported as detail tokens (word_count_low,
word_count_high, sentence_count, banned_letter, missing_phrase,
same_start_word, topic_lead); the framework flag vocabulary only carries
FMT/R2_* for format-level problems.
"""

import re

from psicotest.checkers import schema
from psicotest.checkers.common import make_result
from psicotest.checkers.extract import extract_block

SENTENCE_END_RE = re.compile(r"[.!?]+")


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_END_RE.split(text) if part.strip()]


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
    if len(sentences) != constraints["sentence_count"]:
        details.append("sentence_count")
    banned = constraints["banned_letter"].lower()
    if banned in block.lower():
        details.append("banned_letter")
    phrase = constraints["required_phrase"].lower()
    if phrase not in block.lower():
        details.append("missing_phrase")
    start_word = constraints.get("same_start_word")
    if start_word is not None and any(
        sentence.split()[0].lower() != start_word.lower() for sentence in sentences
    ):
        details.append("same_start_word")
    if constraints.get("topic_lead"):
        topic = constraints["topic"].lower()
        if not sentences or not sentences[0].lower().startswith(topic):
            details.append("topic_lead")
    outcome = "OK" if not details else "WRONG"
    return make_result(outcome, block, flags, ";".join(details))
