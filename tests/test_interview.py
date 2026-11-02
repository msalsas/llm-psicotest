import unittest

import _bootstrap
import fakes
import item_fixtures
from battery_layout import ORDER_A, ORDER_B, SLOT_BY_ID

from psicotest.checkers import check_turn
from psicotest.checkers.common import ANSWER_KINDS, CAPABILITY_FAMILIES
from psicotest.checkers.interview import (
    has_degenerate_sentence,
    has_repeated_ngram,
    split_sentences,
)
from psicotest.checkers.schema import invariant, validate
from psicotest.generators import SLOTS_V6, build_slot_item
from psicotest.generators.interview import PROMPT_POOL_S33, PROMPT_POOL_S34, gen_interview
from psicotest.rng import Rng
from psicotest.runner.report import CAPABILITY_MAX, CAPABILITY_SLOTS
from psicotest.spec import GenContext

GOOD = fakes.IV_ORACLE


def iv_item(floor=150):
    item = item_fixtures.make_item(
        "IV", {"word_floor": floor}, {"prompt_id": "iv_workspace", "realized": {"level": 0}}
    )
    return item


def check_iv_text(text, floor=150):
    turn = item_fixtures.turn_of(iv_item(floor))
    return check_turn(turn, text, "stop", None)


def block(text):
    return f"BEGIN\n{text}\nEND"


class TestInterviewRegistration(unittest.TestCase):
    def test_family_wiring(self):
        self.assertIn("IV", CAPABILITY_FAMILIES)
        self.assertEqual(ANSWER_KINDS["IV"], "block")
        self.assertEqual(CAPABILITY_MAX, 29)
        self.assertTrue({"S33", "S34"} <= CAPABILITY_SLOTS)
        self.assertEqual([s.slot for s in SLOTS_V6 if s.family == "IV"], ["S33", "S34"])

    def test_layout_places_iv_in_both_orders(self):
        for order in (ORDER_A, ORDER_B):
            at = {turn: slot for turn, _, slot in order}
            self.assertEqual((at[35], at[36]), ("S33", "S34"))


class TestInterviewGenerator(unittest.TestCase):
    def test_frozen_pools_per_slot(self):
        self.assertEqual([p[0] for p in PROMPT_POOL_S33], ["iv_workspace", "iv_learning"])
        self.assertEqual([p[0] for p in PROMPT_POOL_S34], ["iv_decisions", "iv_communication"])
        for _, text in (*PROMPT_POOL_S33, *PROMPT_POOL_S34):
            self.assertTrue(text.isascii())

    def test_slots_draw_from_their_own_pool(self):
        seen = {"S33": set(), "S34": set()}
        for seed in range(1, 41):
            for slot, pool in (("S33", PROMPT_POOL_S33), ("S34", PROMPT_POOL_S34)):
                item = build_slot_item(SLOT_BY_ID[slot], seed)
                validate(item, "IV")
                self.assertIsNone(invariant(item, "IV"))
                texts = dict(pool)
                self.assertIn(item.meta["prompt_id"], texts)
                self.assertTrue(item.prompt_en.startswith(texts[item.meta["prompt_id"]]))
                seen[slot].add(item.meta["prompt_id"])
                self.assertIn("Your response must be at least 150 words.", item.prompt_en)
                self.assertIn("BEGIN\n<your response here>\nEND", item.prompt_en)
                self.assertNotIn("ANSWER:", item.prompt_en)
                self.assertEqual(item.key, {"word_floor": 150})
        self.assertEqual(seen["S33"], {"iv_workspace", "iv_learning"})
        self.assertEqual(seen["S34"], {"iv_decisions", "iv_communication"})

    def test_variant_and_knob_validation(self):
        with self.assertRaises(ValueError):
            gen_interview(Rng(1), {"level": 0}, GenContext("relabel", None, Rng(1)))
        with self.assertRaises(ValueError):
            gen_interview(Rng(1), {"level": 0, "pool": 2}, GenContext("base", None, Rng(1)))


class TestInterviewMetrics(unittest.TestCase):
    def test_ngram(self):
        self.assertFalse(has_repeated_ngram(GOOD))
        words = "one two three four five six seven eight"
        self.assertTrue(has_repeated_ngram(f"{words} nine {words.upper()}"))
        self.assertFalse(has_repeated_ngram("one two three four five six seven eight nine ten"))

    def test_split_sentences_abbreviations(self):
        text = "Pick a simple tool, e.g. hammers. Then start working on it right away."
        self.assertEqual(len(split_sentences(text)), 2)
        self.assertFalse(has_degenerate_sentence(text))

    def test_split_requires_whitespace(self):
        self.assertEqual(len(split_sentences("Version 3.5 works fine for most of us.")), 1)

    def test_leading_fragment_merges_forward(self):
        text = "1. First I imagine a bright desk by the window. Then I begin."
        self.assertEqual(len(split_sentences(text)), 2)
        self.assertFalse(has_degenerate_sentence(text))

    def test_uppercase_fragment_not_merged(self):
        self.assertTrue(
            has_degenerate_sentence("This one is long enough. No. Another fine sentence.")
        )

    def test_degenerate_bounds(self):
        self.assertTrue(has_degenerate_sentence("Fine sentence number one here. Hi there."))
        self.assertTrue(has_degenerate_sentence(" ".join(["word"] * 46) + "."))
        self.assertFalse(has_degenerate_sentence(" ".join(["word"] * 45) + "."))
        self.assertFalse(has_degenerate_sentence("Three words here."))


class TestInterviewChecker(unittest.TestCase):
    def test_good_block_passes(self):
        result = check_iv_text(block(GOOD))
        self.assertEqual((result.outcome, result.flags, result.detail), ("OK", ("R2_OK",), ""))

    def test_extract_failure_is_fmt(self):
        for text in (GOOD, "BEGIN\n" + GOOD, "", None, "BEGIN\n\nEND"):
            result = check_iv_text(text)
            self.assertEqual(result.outcome, "NOANS", text)
            self.assertEqual(result.detail, "fmt")
            self.assertIn("FMT", result.flags)

    def test_leading_numbered_fragment_passes(self):
        result = check_iv_text(block("1. First I imagine a bright desk by the window. " + GOOD))
        self.assertEqual((result.outcome, result.detail), ("OK", ""))

    def test_too_short(self):
        short = " ".join(GOOD.split()[:100])
        result = check_iv_text(block(short + "."))
        self.assertEqual((result.outcome, result.detail), ("WRONG", "too_short"))

    def test_floor_boundary(self):
        words = GOOD.split()
        self.assertEqual(check_iv_text(block(GOOD), floor=len(words)).outcome, "OK")
        self.assertEqual(check_iv_text(block(GOOD), floor=len(words) + 1).detail, "too_short")

    def test_loop_ngram_isolated(self):
        looped = f"{GOOD} {GOOD.split('.')[0]}."
        result = check_iv_text(block(looped))
        self.assertEqual((result.outcome, result.detail), ("WRONG", "loop_ngram"))

    def test_degenerate_isolated(self):
        text = f"{GOOD} Yes."
        result = check_iv_text(block(text))
        self.assertEqual((result.outcome, result.detail), ("WRONG", "degenerate_sentence"))

    def test_long_sentence_degenerate(self):
        long_sentence = " ".join(f"w{i}" for i in range(50)) + "."
        result = check_iv_text(block(f"{GOOD} {long_sentence}"))
        self.assertEqual(result.detail, "degenerate_sentence")

    def test_no_partial_scores(self):
        self.assertEqual(check_iv_text(block(GOOD)).score, 1)
        self.assertEqual(check_iv_text(block(GOOD[:200])).score, 0)

    def test_preamble_allowed(self):
        result = check_iv_text("Sure thing.\n" + block(GOOD))
        self.assertEqual(result.outcome, "OK")

    def test_no_non_latin_metric_in_checker(self):
        result = check_iv_text(block(GOOD.replace("workspace", "workspace \u4f60\u597d", 1)))
        self.assertEqual(result.outcome, "OK")

    def test_generated_items_pass_oracle(self):
        for seed in range(1, 11):
            for slot in ("S33", "S34"):
                item = build_slot_item(SLOT_BY_ID[slot], seed)
                turn = item_fixtures.turn_of(item)
                result = check_turn(turn, block(GOOD), "stop", None)
                self.assertEqual(result.outcome, "OK", item.item_id)


if __name__ == "__main__":
    unittest.main()
