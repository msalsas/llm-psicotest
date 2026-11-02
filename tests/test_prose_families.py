import dataclasses
import hashlib
import itertools
import re
import unittest
from typing import ClassVar

import _bootstrap
import item_fixtures
from battery_layout import ORDER_A, ORDER_B, SLOT_BY_ID
from solvers import TWO_HOP_PREMISE, TWO_HOP_QUESTION, solve_two_hop

from psicotest.checkers import check_turn
from psicotest.checkers.extract import extract_block
from psicotest.checkers.prose_consistency import _parse_yes_no, check_pc
from psicotest.checkers.schema import invariant, validate
from psicotest.generators import build_slot_item, prose_block
from psicotest.generators.prose_block import (
    _PROOFS,
    BANNED_POOL_L0,
    BANNED_POOL_L1,
    BANNED_POOL_L2,
    PHRASE_POOL_L0,
    PHRASE_POOL_L1,
    PHRASE_POOL_L2,
    PHRASE_POOL_L3,
    START_WORD_POOL_L1,
    START_WORD_POOL_L2,
    START_WORD_POOL_L3,
    TOPIC_POOL,
    TOPIC_POOL_L2,
    TOPIC_POOL_L3,
    gen_prose_block,
)
from psicotest.generators.prose_consistency import (
    DECISION_POOL,
    TWO_HOP_POOL,
    gen_prose_consistency,
)
from psicotest.rng import Rng
from psicotest.spec import GenContext, canonical_json

LEVEL_BANNED = {
    -1: BANNED_POOL_L0,
    0: BANNED_POOL_L0,
    1: BANNED_POOL_L1,
    2: BANNED_POOL_L2,
    3: BANNED_POOL_L1,
}
LEVEL_PHRASES = {
    -1: PHRASE_POOL_L0,
    0: PHRASE_POOL_L0,
    1: PHRASE_POOL_L1,
    2: PHRASE_POOL_L2,
    3: PHRASE_POOL_L3,
}
LEVEL_STARTS = {-1: (), 0: (), 1: START_WORD_POOL_L1, 2: START_WORD_POOL_L2, 3: START_WORD_POOL_L3}
LEVEL_TOPICS = {-1: TOPIC_POOL, 0: TOPIC_POOL, 1: TOPIC_POOL, 2: TOPIC_POOL_L2, 3: TOPIC_POOL_L3}
L3_BANNED_ALL = ("e", "a", "t")
SENTENCE_SPLIT = re.compile(r"[.!?]+")

L1_CONSTRAINTS = {
    "topic": "cold wind",
    "word_count_min": 40,
    "word_count_max": 60,
    "sentence_count": 6,
    "banned_letter": "e",
    "required_phrase": "by far",
    "same_start_word": "all",
    "topic_lead": False,
}
L2_CONSTRAINTS = {
    "topic": "snowy mountains",
    "word_count_min": 30,
    "word_count_max": 45,
    "sentence_count": 5,
    "banned_letter": "e",
    "required_phrase": "in summary",
    "same_start_word": "snowy",
    "topic_lead": True,
}
VALID_L1 = (
    "all dull mornings dawn gray and cold. "
    "all dull mornings dawn gray and cold. "
    "all dull mornings dawn gray and cold. "
    "all dull mornings dawn gray and cold. "
    "all dull mornings dawn gray and cold. "
    "all our walks bring calm joy by far."
)
VALID_L2 = _PROOFS[2]
FILLER = "all dull mornings dawn gray and cold."
FILLER_WORDY = (
    "all dull mornings dawn gray and cold and calm and dim and soft and still "
    "and bland and dry and plain and dark and low and slow."
)


def pr_item(constraints, level=1):
    return item_fixtures.make_item(
        "PR", {"constraints": dict(constraints)}, {"level": level, "proof": "x"}
    )


def pc_item(canonical="yes", variant="base"):
    item = item_fixtures.make_item(
        "PC",
        {"value": canonical},
        {"question_id": "cmp_47_23", "surface": "Is 47 greater than 23?"},
    )
    meta = {**item.meta, "twin_slot": "S31"} if variant == "pc2" else item.meta
    return dataclasses.replace(item, variant=variant, meta=meta)


def check_pr_text(constraints, text, level=1):
    turn = item_fixtures.turn_of(pr_item(constraints, level))
    return check_turn(turn, text, "stop", None)


_GENERIC_WORDS = {"book", "project"}
_HIGH_LEFT = ("taller", "exceed", ">", "after")
_LOW_LEFT = ("shorter", "<", "before", "->")
_RELATION_RE = re.compile("|".join(re.escape(w) for w in (*_HIGH_LEFT, *_LOW_LEFT)), re.I)


def _short(name):
    words = [w for w in name.split() if w.lower() not in _GENERIC_WORDS]
    return words[0].lower()


def _premise_edges(premises):
    edges = []
    for premise in premises:
        m = TWO_HOP_PREMISE.match(premise)
        if m["rel"] is not None:
            low, high = (m["b"], m["a"]) if m["rel"] == "taller" else (m["a"], m["b"])
        else:
            low, high = (m["c"], m["d"]) if m["dir"] == "before" else (m["d"], m["c"])
        edges.append((_short(low), _short(high)))
    return edges


def _short_names(premises):
    return {name for edge in _premise_edges(premises) for name in edge}


def _surface_edges(text, names):
    # Directed (low, high) edges between consecutive entity mentions within a clause.
    mention = re.compile(r"\b(" + "|".join(sorted(names)) + r")\b", re.I)
    edges = []
    for clause in re.split(r"[.,;:?()]", text):
        found = list(mention.finditer(clause))
        for left, right in itertools.pairwise(found):
            rel = _RELATION_RE.search(clause[left.end() : right.start()])
            if rel is None or left.group().lower() == right.group().lower():
                continue
            pair = (left.group().lower(), right.group().lower())
            high_left = rel.group().lower() in _HIGH_LEFT
            edges.append(pair[::-1] if high_left else pair)
    return edges


def _derives(premises, question, canonical):
    try:
        return solve_two_hop(premises, question) == canonical
    except ValueError:
        return False


class TestBlockExtractor(unittest.TestCase):
    def test_block_simple(self):
        self.assertEqual(extract_block("BEGIN\nHello\nEND"), ("Hello", []))

    def test_block_multiline(self):
        self.assertEqual(extract_block("BEGIN\nLine1\nLine2\nEND"), ("Line1\nLine2", []))

    def test_block_with_preamble(self):
        self.assertEqual(extract_block("Sure, here you go.\nBEGIN\nText\nEND"), ("Text", []))

    def test_block_no_begin(self):
        self.assertEqual(extract_block("Text\nEND"), (None, ["no_block"]))

    def test_block_no_end(self):
        self.assertEqual(extract_block("BEGIN\nText"), (None, ["no_block"]))

    def test_block_none(self):
        self.assertEqual(extract_block(None), (None, ["no_block"]))

    def test_block_nested_takes_first_pair(self):
        self.assertEqual(extract_block("BEGIN\nBEGIN\nInner\nEND\nEND"), ("BEGIN\nInner", []))

    def test_block_trailing_ws_after_begin(self):
        self.assertEqual(extract_block("BEGIN  \nHello\nEND"), ("Hello", []))

    def test_block_leading_ws_before_end(self):
        self.assertEqual(extract_block("BEGIN\nHello\n  END"), ("Hello", []))


class TestProsePoolInvariants(unittest.TestCase):
    def test_no_pool_word_contains_level_banned_letter(self):
        for level, banned_pool in LEVEL_BANNED.items():
            pools = (LEVEL_TOPICS[level], LEVEL_PHRASES[level], LEVEL_STARTS[level])
            for banned in banned_pool:
                for pool in pools:
                    for word in pool:
                        self.assertNotIn(banned, word.lower(), (level, banned, word))

    def test_pools_ascii_and_nonempty(self):
        pools = (
            TOPIC_POOL,
            TOPIC_POOL_L2,
            PHRASE_POOL_L0,
            PHRASE_POOL_L1,
            PHRASE_POOL_L2,
            PHRASE_POOL_L3,
            TOPIC_POOL_L3,
            START_WORD_POOL_L1,
            START_WORD_POOL_L2,
            START_WORD_POOL_L3,
        )
        for pool in pools:
            self.assertTrue(pool)
            for word in pool:
                self.assertTrue(word.isascii(), word)
                self.assertNotIn("  ", word)

    def test_level2_topic_matches_start_word(self):
        for topic in TOPIC_POOL_L2:
            first = topic.split()[0]
            self.assertIn(first, START_WORD_POOL_L2)

    def test_proof_present_for_every_ladder_level(self):
        for level in prose_block.LADDER:
            self.assertIn(level, _PROOFS)
            self.assertTrue(_PROOFS[level].isascii())


class TestProofInstances(unittest.TestCase):
    def test_proof_satisfies_every_level_draw(self):
        for level in _PROOFS:
            if level == 3:
                continue
            proof = _PROOFS[level]
            for banned in LEVEL_BANNED[level]:
                for phrase in LEVEL_PHRASES[level]:
                    topics = LEVEL_TOPICS[level]
                    starts = LEVEL_STARTS[level] or (None,)
                    for start in starts:
                        for topic in topics:
                            probe = {
                                "topic": topic,
                                "word_count_min": prose_block.LADDER[level]["word_count_min"],
                                "word_count_max": prose_block.LADDER[level]["word_count_max"],
                                "sentence_count": prose_block.LADDER[level]["sentence_count"],
                                "banned_letter": banned,
                                "required_phrase": phrase,
                                "same_start_word": start,
                                "topic_lead": level == 2,
                            }
                            result = check_pr_text(probe, f"BEGIN\n{proof}\nEND", level)
                            self.assertEqual(
                                (result.outcome, result.flags, result.detail),
                                ("OK", ("R2_OK",), ""),
                                (level, banned, phrase, start, topic, result.detail),
                            )

    def test_level3_pools_avoid_e_a_t(self):
        for pool in (PHRASE_POOL_L3, START_WORD_POOL_L3, TOPIC_POOL_L3):
            for entry in pool:
                for banned in L3_BANNED_ALL:
                    self.assertNotIn(banned, entry.lower(), entry)

    def test_level3_proof_satisfies_every_draw(self):
        proof = _PROOFS[3]
        ladder = prose_block.LADDER[3]
        words = proof.split()
        self.assertTrue(ladder["word_count_min"] <= len(words) <= ladder["word_count_max"])
        sentences = [part.strip() for part in SENTENCE_SPLIT.split(proof) if part.strip()]
        self.assertTrue(ladder["sentence_count"] <= len(sentences) <= ladder["sentence_count_max"])
        for banned in LEVEL_BANNED[3]:
            self.assertNotIn(banned, proof.lower())
        for phrase in PHRASE_POOL_L3:
            self.assertIn(phrase, proof.lower())
        firsts = [sentence.split()[0].lower() for sentence in sentences]
        for word in START_WORD_POOL_L3:
            self.assertEqual(firsts.count(word), 1, word)
        initials = [sentence[0].casefold() for sentence in sentences]
        self.assertEqual(len(initials), len(set(initials)))
        self.assertEqual(len(sentences), 7)
        self.assertEqual(len(words), 85)

    def test_level3_proof_passes_every_phrase_pair_and_banned_letter(self):
        for banned in LEVEL_BANNED[3]:
            for i, first in enumerate(PHRASE_POOL_L3):
                for second in PHRASE_POOL_L3[i + 1 :]:
                    constraints = {
                        "topic": "crisp morning",
                        "word_count_min": 80,
                        "word_count_max": 120,
                        "sentence_count": 6,
                        "sentence_count_max": 8,
                        "banned_letter": banned,
                        "required_phrase": first,
                        "required_phrases": [first, second],
                        "same_start_word": None,
                        "topic_lead": False,
                        "start_words": list(START_WORD_POOL_L3),
                        "distinct_starts": True,
                    }
                    result = check_pr_text(constraints, f"BEGIN\n{_PROOFS[3]}\nEND", 3)
                    self.assertEqual(
                        (result.outcome, result.flags, result.detail),
                        ("OK", ("R2_OK",), ""),
                        (banned, first, second),
                    )

    def test_level3_generated_constraints(self):
        for seed in range(1, 41):
            item = build_slot_item(SLOT_BY_ID["S30"], seed)
            constraints = item.key["constraints"]
            phrases = constraints["required_phrases"]
            self.assertEqual(len(set(phrases)), 2)
            self.assertTrue(set(phrases) <= set(PHRASE_POOL_L3))
            self.assertEqual(constraints["start_words"], list(START_WORD_POOL_L3))
            self.assertIn(constraints["banned_letter"], BANNED_POOL_L1)
            self.assertEqual(constraints["required_phrase"], phrases[0])
            for phrase in phrases:
                self.assertIn(f'"{phrase}"', item.prompt_en)

    def test_proof_passes_generated_slot_items(self):
        for seed in range(1, 21):
            for slot in ("S29", "S30"):
                item = build_slot_item(SLOT_BY_ID[slot], seed)
                validate(item, "PR")
                self.assertIsNone(invariant(item, "PR"))
                turn = item_fixtures.turn_of(item)
                result = check_turn(turn, f"BEGIN\n{item.meta['proof']}\nEND", "stop", None)
                self.assertEqual(result.outcome, "OK", item.item_id)
                self.assertEqual(result.flags, ("R2_OK",), item.item_id)
                self.assertEqual(result.detail, "", item.item_id)

    def test_proofs_do_not_trip_loop_or_leak(self):
        from psicotest.checkers.cjk import has_leak
        from psicotest.checkers.telemetry import has_loop

        for proof in _PROOFS.values():
            self.assertFalse(has_loop(proof))
            self.assertFalse(has_leak(proof))


class TestProseBlockCheckerIsolation(unittest.TestCase):
    def test_valid_block_passes(self):
        result = check_pr_text(L1_CONSTRAINTS, f"BEGIN\n{VALID_L1}\nEND")
        self.assertEqual((result.outcome, result.flags, result.detail), ("OK", ("R2_OK",), ""))

    def test_no_block(self):
        result = check_pr_text(L1_CONSTRAINTS, "Just some prose, no markers.")
        self.assertEqual(result.outcome, "NOANS")
        self.assertEqual(result.detail, "no_block")
        self.assertEqual(set(result.flags), {"FMT"})

    def test_word_count_low(self):
        block = " ".join(["all dim days call for soup."] * 5 + ["all dim days call by far."])
        result = check_pr_text(L1_CONSTRAINTS, f"BEGIN\n{block}\nEND")
        self.assertEqual((result.outcome, result.detail), ("WRONG", "word_count_low"))

    def test_word_count_high(self):
        block = VALID_L1.replace(FILLER, FILLER_WORDY, 1)
        result = check_pr_text(L1_CONSTRAINTS, f"BEGIN\n{block}\nEND")
        self.assertEqual((result.outcome, result.detail), ("WRONG", "word_count_high"))

    def test_sentence_count(self):
        block = f"{FILLER} {VALID_L1}"
        result = check_pr_text(L1_CONSTRAINTS, f"BEGIN\n{block}\nEND")
        self.assertEqual((result.outcome, result.detail), ("WRONG", "sentence_count"))

    def test_banned_letter(self):
        block = VALID_L1.replace("all dull mornings", "all mellow mornings", 1)
        result = check_pr_text(L1_CONSTRAINTS, f"BEGIN\n{block}\nEND")
        self.assertEqual((result.outcome, result.detail), ("WRONG", "banned_letter"))

    def test_missing_phrase(self):
        block = VALID_L1.replace(
            "all our walks bring calm joy by far.", "all our walks bring calm joy all day."
        )
        result = check_pr_text(L1_CONSTRAINTS, f"BEGIN\n{block}\nEND")
        self.assertEqual((result.outcome, result.detail), ("WRONG", "missing_phrase"))

    def test_same_start_word(self):
        block = VALID_L1.replace(
            "all our walks bring calm joy by far.", "our walks bring calm joy by far."
        )
        result = check_pr_text(L1_CONSTRAINTS, f"BEGIN\n{block}\nEND")
        self.assertEqual((result.outcome, result.detail), ("WRONG", "same_start_word"))

    def test_same_start_word_with_leading_quote(self):
        block = VALID_L1.replace("all dull mornings", '"all dull mornings', 1)
        result = check_pr_text(L1_CONSTRAINTS, f"BEGIN\n{block}\nEND")
        self.assertEqual((result.outcome, result.detail), ("OK", ""))

    def test_topic_lead(self):
        block = VALID_L2.replace(
            "snowy mountains stand high in summary.",
            "snowy hills stand high in summary.",
            1,
        )
        result = check_pr_text(L2_CONSTRAINTS, f"BEGIN\n{block}\nEND", level=2)
        self.assertEqual((result.outcome, result.detail), ("WRONG", "topic_lead"))

    def test_isolation_each_single_token(self):
        cases = (
            ("word_count_low", VALID_L1.replace(FILLER, "all dull mornings.", 1)),
            ("sentence_count", f"{FILLER} {VALID_L1}"),
            ("banned_letter", VALID_L1.replace("gray", "mellow", 1)),
            ("missing_phrase", VALID_L1.replace(" by far.", " all day.")),
            ("same_start_word", VALID_L1.replace("all our walks", "our walks", 1)),
        )
        for token, block in cases:
            with self.subTest(token=token):
                result = check_pr_text(L1_CONSTRAINTS, f"BEGIN\n{block}\nEND")
                self.assertEqual(result.detail, token)
        result = check_pr_text(
            L2_CONSTRAINTS,
            "BEGIN\n" + VALID_L2.replace("snowy mountains", "snowy hills", 1) + "\nEND",
            level=2,
        )
        self.assertEqual(result.detail, "topic_lead")


class TestLevel3CheckerIsolation(unittest.TestCase):
    CONSTRAINTS: ClassVar[dict] = {
        "topic": "crisp morning",
        "word_count_min": 80,
        "word_count_max": 120,
        "sentence_count": 6,
        "sentence_count_max": 8,
        "banned_letter": "e",
        "required_phrase": "in full",
        "required_phrases": ["in full", "much joy"],
        "same_start_word": None,
        "topic_lead": False,
        "start_words": ["cold", "bold"],
        "distinct_starts": True,
    }

    def detail(self, block):
        return check_pr_text(self.CONSTRAINTS, f"BEGIN\n{block}\nEND", 3).detail

    def test_proof_ok(self):
        self.assertEqual(self.detail(_PROOFS[3]), "")

    def test_second_phrase_missing(self):
        self.assertEqual(self.detail(_PROOFS[3].replace("much joy", "much fun")), "missing_phrase")

    def test_first_phrase_missing(self):
        self.assertEqual(self.detail(_PROOFS[3].replace("in full", "in all")), "missing_phrase")

    def test_start_word_missing(self):
        block = _PROOFS[3].replace("Bold cooks", "Brisk cooks")
        self.assertEqual(self.detail(block), "start_words")

    def test_start_word_duplicated(self):
        block = _PROOFS[3].replace("Dry wood", "Cold wood")
        self.assertEqual(self.detail(block), "start_words;distinct_starts")

    def test_distinct_starts_fail_alone(self):
        block = _PROOFS[3].replace("Mild sun", "Long sun")
        self.assertEqual(self.detail(block), "distinct_starts")

    def test_distinct_starts_casefold(self):
        block = _PROOFS[3].replace("Mild sun", "long sun")
        self.assertEqual(self.detail(block), "distinct_starts")

    def test_sentence_count_range(self):
        sentences = [
            part.strip() + "." for part in SENTENCE_SPLIT.split(_PROOFS[3]) if part.strip()
        ]
        self.assertEqual(self.detail(" ".join(sentences[:5])), "word_count_low;sentence_count")
        eight = " ".join([*sentences, "Zinc pans glow."])
        self.assertEqual(self.detail(eight), "")
        nine = " ".join([*sentences, "Zinc pans glow.", "Yarn rolls up."])
        self.assertEqual(self.detail(nine), "sentence_count")

    def test_word_count_bounds(self):
        short = " ".join(_PROOFS[3].split()[:60]) + "."
        self.assertIn("word_count_low", self.detail(short))

    def test_banned_letter(self):
        self.assertEqual(self.detail(_PROOFS[3].replace("kilns", "ovens")), "banned_letter")


class TestProseConsistencyChecker(unittest.TestCase):
    def test_parse_yes_no(self):
        self.assertEqual(_parse_yes_no("Yes"), "yes")
        self.assertEqual(_parse_yes_no("YES "), "yes")
        self.assertEqual(_parse_yes_no(" NO"), "no")
        self.assertIsNone(_parse_yes_no("ANSWER: NO"))
        self.assertIsNone(_parse_yes_no("yes, no"))
        self.assertIsNone(_parse_yes_no("no maybe"))
        self.assertIsNone(_parse_yes_no("maybe"))
        self.assertIsNone(_parse_yes_no(None))

    def test_variant1_correctness_only(self):
        item = pc_item("yes", "pc1")
        result = check_pc("ANSWER: yes", "stop", None, item, prior=None)
        self.assertEqual((result.outcome, result.flags, result.detail), ("OK", ("R2_OK",), ""))
        result = check_pc("ANSWER: no", "stop", None, item, prior=None)
        self.assertEqual((result.outcome, result.detail), ("WRONG", "incorrect"))
        result = check_pc("ANSWER: no", "stop", None, item, prior={"S32": "ANSWER: yes"})
        self.assertEqual(result.detail, "incorrect", "pc1 ignores twin context")

    def test_unparseable(self):
        item = pc_item("yes", "pc1")
        result = check_pc("ANSWER: maybe", "stop", None, item)
        self.assertEqual((result.outcome, result.detail), ("WRONG", "unparseable"))
        self.assertIn("FMT", result.flags)
        self.assertIn("R2_FAIL", result.flags)

    def test_no_answer_line(self):
        item = pc_item("yes", "pc1")
        result = check_pc("I cannot decide.", "stop", None, item)
        self.assertEqual(result.outcome, "NOANS")

    def test_variant2_consistent(self):
        item = pc_item("yes", "pc2")
        result = check_pc("ANSWER: yes", "stop", None, item, prior={"S31": "ANSWER: yes"})
        self.assertEqual((result.outcome, result.detail), ("OK", ""))

    def test_variant2_inconsistent(self):
        item = pc_item("yes", "pc2")
        result = check_pc("ANSWER: yes", "stop", None, item, prior={"S31": "ANSWER: no"})
        self.assertEqual((result.outcome, result.detail), ("WRONG", "inconsistent"))

    def test_variant2_only_looks_at_twin_slot(self):
        item = pc_item("yes", "pc2")
        other = {"S09": "ANSWER: no"}
        result = check_pc("ANSWER: yes", "stop", None, item, prior=other)
        self.assertEqual((result.outcome, result.detail), ("OK", "missing_twin_context"))
        result = check_pc(
            "ANSWER: yes", "stop", None, item, prior={"S09": "ANSWER: no", "S31": "ANSWER: yes"}
        )
        self.assertEqual((result.outcome, result.detail), ("OK", ""))
        result = check_pc(
            "ANSWER: yes", "stop", None, item, prior={"S09": "ANSWER: yes", "S31": "ANSWER: no"}
        )
        self.assertEqual((result.outcome, result.detail), ("WRONG", "inconsistent"))

    def test_generated_pc2_carries_twin_slot(self):
        self.assertEqual(build_slot_item(SLOT_BY_ID["S32"], 7).meta["twin_slot"], "S31")

    def test_variant2_missing_twin_context_not_failure(self):
        item = pc_item("yes", "pc2")
        result = check_pc("ANSWER: yes", "stop", None, item, prior=None)
        self.assertEqual((result.outcome, result.detail), ("OK", "missing_twin_context"))
        result = check_pc("ANSWER: yes", "stop", None, item, prior={"S01": "ANSWER: 42"})
        self.assertEqual((result.outcome, result.detail), ("OK", "missing_twin_context"))

    def test_d5_twin_wrong_but_parseable_same_word(self):
        # Twin parseable and wrong (says "no" for a "yes" question); variant-2
        # repeats the twin word, so only "incorrect" fires, never "inconsistent".
        item = pc_item("yes", "pc2")
        result = check_pc("ANSWER: no", "stop", None, item, prior={"S31": "ANSWER: no"})
        self.assertEqual((result.outcome, result.detail), ("WRONG", "incorrect"))

    def test_schema_validation(self):
        item = build_slot_item(SLOT_BY_ID["S31"], 7)
        validate(item, "PC")
        self.assertIsNone(invariant(item, "PC"))


class TestProseTwins(unittest.TestCase):
    def test_twins_share_question_and_answer(self):
        for seed in (0, 1, 7, 11, 42, 123):
            first = build_slot_item(SLOT_BY_ID["S31"], seed)
            second = build_slot_item(SLOT_BY_ID["S32"], seed)
            self.assertEqual(first.meta["question_id"], second.meta["question_id"])
            self.assertEqual(first.key, second.key)
            self.assertEqual(first.variant, "pc1")
            self.assertEqual(second.variant, "pc2")
            self.assertNotEqual(first.surface_seed, second.surface_seed)
            self.assertNotEqual(first.meta["surface"], second.meta["surface"])

    def test_decision_pool_shape(self):
        self.assertEqual(len(DECISION_POOL), 8)
        for question_id, canonical, base, surfaces in DECISION_POOL:
            self.assertTrue(question_id)
            self.assertIn(canonical, ("yes", "no"))
            self.assertTrue(base.endswith("?"))
            self.assertEqual(len(surfaces), 2)
            self.assertNotEqual(surfaces[0], surfaces[1])

    def test_two_hop_pool_shape(self):
        self.assertEqual(len(TWO_HOP_POOL), 4)
        for question_id, canonical, premises, question, surfaces in TWO_HOP_POOL:
            self.assertTrue(question_id)
            self.assertIn(canonical, ("yes", "no"))
            self.assertEqual(len(premises), 3)
            self.assertTrue(question.endswith("?"))
            self.assertEqual(len(surfaces), 2)
            self.assertNotEqual(surfaces[0], surfaces[1])
            self.assertEqual(solve_two_hop(premises, question), canonical, question_id)

    def test_two_hop_pool_is_sound(self):
        flip = {"yes": "no", "no": "yes"}
        for question_id, canonical, premises, question, surfaces in TWO_HOP_POOL:
            with self.subTest(question_id=question_id):
                chains = [
                    pair
                    for pair in itertools.combinations(premises, 2)
                    if _derives(pair, question, canonical)
                ]
                self.assertTrue(chains, "no 2-premise chain derives the canonical answer")
                for premise in premises:
                    with self.assertRaises(ValueError):
                        solve_two_hop((premise,), question)
                m = TWO_HOP_QUESTION.match(question)
                reverse = (
                    question.replace(m["a"], "\0").replace(m["b"], m["a"]).replace("\0", m["b"])
                )
                self.assertEqual(solve_two_hop(premises, reverse), flip[canonical])
                want = _surface_edges(question, _short_names(premises))
                for surface in surfaces:
                    edges = _surface_edges(surface, _short_names(premises))
                    self.assertEqual(edges[-1], want[0], surface)
                    self.assertEqual(sorted(edges[:-1]), sorted(_premise_edges(premises)), surface)

    def test_solver_unit(self):
        premises = TWO_HOP_POOL[0][2]
        self.assertEqual(solve_two_hop(premises, "Is Alice taller than Carol?"), "yes")
        self.assertEqual(solve_two_hop(premises, "Is Diana taller than Alice?"), "no")
        with self.assertRaises(ValueError):
            solve_two_hop(premises, "Is Alice taller than Zed?")

    def test_two_hop_twins_share_entry_and_carry_premises(self):
        entries = {entry[0]: entry for entry in TWO_HOP_POOL}
        seen = set()
        for seed in range(1, 60):
            first = build_slot_item(SLOT_BY_ID["S31"], seed)
            second = build_slot_item(SLOT_BY_ID["S32"], seed)
            validate(first, "PC")
            validate(second, "PC")
            self.assertIsNone(invariant(second, "PC"))
            question_id = first.meta["question_id"]
            seen.add(question_id)
            self.assertEqual(question_id, second.meta["question_id"])
            _, canonical, premises, _, surfaces = entries[question_id]
            self.assertEqual(first.key, {"value": canonical})
            self.assertEqual(first.key, second.key)
            self.assertEqual(first.meta["surface"], surfaces[0])
            self.assertEqual(second.meta["surface"], surfaces[1])
            self.assertEqual(first.meta["premises"], list(premises))
            self.assertEqual(second.meta["premises"], list(premises))
            self.assertEqual(second.meta["twin_slot"], "S31")
            self.assertEqual(first.meta["hops"], 2)
            self.assertIn(surfaces[0], first.prompt_en)
            self.assertIn(surfaces[1], second.prompt_en)
        self.assertEqual(seen, set(entries))

    def test_level_zero_stays_one_hop(self):
        item = build_slot_item(SLOT_BY_ID["S31"], 7)
        self.assertEqual(item.knobs, {"level": 2})
        base = gen_prose_consistency(Rng(7), {"level": 0}, GenContext("pc1", None, Rng(1)))
        self.assertNotIn("premises", base[2])
        self.assertIn(base[2]["question_id"], {entry[0] for entry in DECISION_POOL})

    def test_generator_variants(self):
        rng = Rng(7)
        knobs = {"level": 0}
        base = gen_prose_consistency(rng, knobs, GenContext("base", None, Rng(1)))
        self.assertEqual(base[1]["value"] in ("yes", "no"), True)
        self.assertIn("ANSWER", base[0])
        with self.assertRaises(ValueError):
            gen_prose_consistency(Rng(1), knobs, GenContext("relabel", None, Rng(1)))
        with self.assertRaises(ValueError):
            gen_prose_block(Rng(1), {"level": 0}, GenContext("relabel", None, Rng(1)))


class TestTwinLookupInFrozenLayout(unittest.TestCase):
    def turn_of(self, order, slot):
        return next(turn for turn, _, s in order if s == slot)

    def test_twin_gap_in_both_orders(self):
        for order in (ORDER_A, ORDER_B):
            first = self.turn_of(order, "S31")
            second = self.turn_of(order, "S32")
            self.assertEqual((first, second), (31, 38))
            self.assertGreaterEqual(second - first, 5)
            between = [s for turn, _, s in order if first < turn < second]
            self.assertEqual(between, ["S28", "S29", "S30", "S33", "S34", "S27"])

    def test_unrelated_yes_no_prior_cannot_flip_twin_pair(self):
        for seed in range(1, 30):
            first = build_slot_item(SLOT_BY_ID["S31"], seed)
            second = build_slot_item(SLOT_BY_ID["S32"], seed)
            answer = f"ANSWER: {first.key['value']}"
            noise = {
                "S27": "ANSWER: yes",
                "S28": "ANSWER: no",
                "S29": "BEGIN\nyes no yes no\nEND",
                "S30": "ANSWER: no",
                "S33": "BEGIN\nyes, I agree. no, I do not.\nEND",
                "S34": "ANSWER: yes",
            }
            prior = {**noise, "S31": answer}
            result = check_pc(answer, "stop", None, second, prior=prior)
            self.assertEqual((result.outcome, result.detail), ("OK", ""), seed)
            without = check_pc(answer, "stop", None, second, prior=noise)
            self.assertEqual((without.outcome, without.detail), ("OK", "missing_twin_context"))


# Frozen v6 paths: sha256 of canonical_json({"prompt", "key", "meta"}). Regenerate only on a
# deliberate battery version bump: build_slot_item(SLOT_BY_ID[slot], seed), hash as below.
GOLDEN_V6 = {
    ("S30", 1): "2cab26712a207da4d1cefe4abda149dc91f20aaa50daefa17a2aec3a1b0d3884",
    ("S30", 2): "89b0477c29ee14b86a428db4a08c45c35046f729de1095df89c5fc9ac41b161d",
    ("S30", 3): "56ed086d835e0641a78d81c20d20e89262641cd60ea8eb69a00fabd84e5afd0d",
    ("S30", 42): "56ed086d835e0641a78d81c20d20e89262641cd60ea8eb69a00fabd84e5afd0d",
    ("S30", 1000): "39d43f233205ec555729acc20fcb80f05d068eb0d61882440ba084d89b87fc14",
    ("S31", 1): "3a7fe7235196060ff19b8dca6424905df40bb1c4f7605644b59325e838a4ed3f",
    ("S31", 2): "c97254c58dd75d8aeca2f7286c3d08ac6dcc5e9abab0154567dc9c94664b9f25",
    ("S31", 3): "3a7fe7235196060ff19b8dca6424905df40bb1c4f7605644b59325e838a4ed3f",
    ("S31", 42): "c97254c58dd75d8aeca2f7286c3d08ac6dcc5e9abab0154567dc9c94664b9f25",
    ("S31", 1000): "c97254c58dd75d8aeca2f7286c3d08ac6dcc5e9abab0154567dc9c94664b9f25",
    ("S32", 1): "c58fdd6beab3d0761400fa454cf285ca7a87e97a174ad996a2869e7091c12923",
    ("S32", 2): "f68140a4bdc9948ae0b445d0a1860e9a54e2348cc78e26018cf8f9816d412bef",
    ("S32", 3): "c58fdd6beab3d0761400fa454cf285ca7a87e97a174ad996a2869e7091c12923",
    ("S32", 42): "f68140a4bdc9948ae0b445d0a1860e9a54e2348cc78e26018cf8f9816d412bef",
    ("S32", 1000): "f68140a4bdc9948ae0b445d0a1860e9a54e2348cc78e26018cf8f9816d412bef",
    ("S34", 1): "5a178405b5b918ccbcfb91679a74d72c829e05b6991a888e8d7d501b61a5d4a8",
    ("S34", 2): "09a655e02d009420681824633121f75b82401e05b7946d5cf7375f9a9017a650",
    ("S34", 3): "5a178405b5b918ccbcfb91679a74d72c829e05b6991a888e8d7d501b61a5d4a8",
    ("S34", 42): "09a655e02d009420681824633121f75b82401e05b7946d5cf7375f9a9017a650",
    ("S34", 1000): "09a655e02d009420681824633121f75b82401e05b7946d5cf7375f9a9017a650",
}


class TestFrozenV6GoldenPins(unittest.TestCase):
    def test_item_hashes(self):
        for (slot, seed), expected in GOLDEN_V6.items():
            with self.subTest(slot=slot, seed=seed):
                item = build_slot_item(SLOT_BY_ID[slot], seed)
                payload = {"prompt": item.prompt_en, "key": item.key, "meta": item.meta}
                self.assertEqual(hashlib.sha256(canonical_json(payload)).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
