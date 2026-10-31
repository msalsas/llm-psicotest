import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS
from psicotest.checkers.common import ItemSchemaError

AMB = item_fixtures.AMB


class TestCheckersAMB(unittest.TestCase):
    def call(self, content, family="AMB", item=AMB, finish="stop", reasoning=None):
        return CHECKERS[family](content, finish, reasoning, item)

    def test_amb_case1(self):
        r = self.call("CLARIFICATION: I assume $3 each. ANSWER: 45")
        self.assertEqual(r.outcome, "CLAR_MISS")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "answered")
        self.assertEqual(r.score, 0)

    def test_amb_case2(self):
        r = self.call("CLARIFICATION: How much does each unit cost?")
        self.assertEqual(r.outcome, "CLAR_OK")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "synonym:cost")
        self.assertEqual(r.score, 1)
        self.assertEqual(r.value, "How much does each unit cost?")

    def test_amb_case3(self):
        r = self.call("CLARIFICATION: How many units does she buy?")
        self.assertEqual(r.outcome, "CLAR_BAD")
        self.assertEqual(r.flags, ("REVIEW",))
        self.assertEqual(r.detail, "no_synonym")

    def test_amb_answered_lines(self):
        r = self.call("I assume $3.\nANSWER: 45")
        self.assertEqual(r.outcome, "CLAR_MISS")

    def test_amb_no_question(self):
        r = self.call("CLARIFICATION: the price is missing")
        self.assertEqual(r.outcome, "CLAR_BAD")
        self.assertEqual(r.flags, ("REVIEW",))
        self.assertEqual(r.detail, "no_question")

    def test_amb_no_prefix_hole(self):
        r = self.call("What is the price?")
        self.assertEqual(r.outcome, "CLAR_OK")
        self.assertEqual(r.flags, ("FMT",))
        self.assertEqual(r.detail, "no_prefix;synonym:price")

    def test_amb_extra_line(self):
        r = self.call("Clarification: What is the cost?\nThanks.")
        self.assertEqual(r.outcome, "CLAR_OK")
        self.assertEqual(r.flags, ("FMT",))

    def test_amb_all_asker(self):
        r = self.call("CLARIFICATION: Which datum is missing?")
        self.assertEqual(r.outcome, "CLAR_BAD")
        self.assertEqual(r.flags, ("REVIEW",))

    def test_amb_empty_and_trunc(self):
        r = self.call("")
        self.assertEqual(r.outcome, "NOANS")
        r = self.call("CLARIFICATION: price?", finish="length")
        self.assertEqual(r.outcome, "TRUNC")

    def test_amb_gen_bug(self):
        item = item_fixtures.make_item("AMB", {"value": 45}, {"synonyms": ["datum"]})
        r = self.call("CLARIFICATION: datum?", item=item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "generic_synonym")

    def test_amb_wordless_synonym(self):
        item = item_fixtures.make_item("AMB", {"value": 45}, {"synonyms": ["???"]})
        with self.assertRaises(ItemSchemaError):
            self.call("CLARIFICATION: price?", item=item)

    def test_ambr_numeric(self):
        r = self.call("ANSWER: 45", family="AMBR")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))
        r = self.call("ANSWER: 45 dollars", family="AMBR")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_FAIL",))
        r = self.call("CLARIFICATION: price?", family="AMBR")
        self.assertEqual(r.outcome, "NOANS")

    def test_amb_marker_english(self):
        from psicotest.checkers.schema import GENERIC_ASK_WORDS

        self.assertEqual(
            GENERIC_ASK_WORDS,
            (
                "data",
                "datum",
                "how",
                "info",
                "information",
                "many",
                "missing",
                "much",
                "value",
                "what",
                "which",
            ),
        )
        r = self.call("ACLAR" + "ACION: What is the price?")
        self.assertEqual(r.outcome, "CLAR_OK")
        self.assertEqual(r.flags, ("FMT",))
        self.assertEqual(r.detail, "no_prefix;synonym:price")


if __name__ == "__main__":
    unittest.main()
