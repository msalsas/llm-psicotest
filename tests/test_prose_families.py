import dataclasses
import unittest

import _bootstrap
import item_fixtures
from battery_layout import SLOT_BY_ID

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
    START_WORD_POOL_L1,
    START_WORD_POOL_L2,
    TOPIC_POOL,
    TOPIC_POOL_L2,
    gen_prose_block,
)
from psicotest.generators.prose_consistency import DECISION_POOL, gen_prose_consistency
from psicotest.rng import Rng
from psicotest.spec import GenContext

LEVEL_BANNED = {-1: BANNED_POOL_L0, 0: BANNED_POOL_L0, 1: BANNED_POOL_L1, 2: BANNED_POOL_L2}
LEVEL_PHRASES = {-1: PHRASE_POOL_L0, 0: PHRASE_POOL_L0, 1: PHRASE_POOL_L1, 2: PHRASE_POOL_L2}
LEVEL_STARTS = {-1: (), 0: (), 1: START_WORD_POOL_L1, 2: START_WORD_POOL_L2}
LEVEL_TOPICS = {-1: TOPIC_POOL, 0: TOPIC_POOL, 1: TOPIC_POOL, 2: TOPIC_POOL_L2}

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
            START_WORD_POOL_L1,
            START_WORD_POOL_L2,
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


if __name__ == "__main__":
    unittest.main()
