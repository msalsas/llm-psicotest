import unittest
from decimal import Decimal

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS

NOOP = item_fixtures.NOOP


class TestCheckersNOOP(unittest.TestCase):
    def call(self, content, item=NOOP):
        return CHECKERS["NOOP"](content, "stop", None, item)

    def test_noop_case1(self):
        r = self.call("ANSWER: 42 apples.")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_FAIL",))

    def test_noop_case2(self):
        item = item_fixtures.make_item("NOOP", {"value": 42}, {"distractor_answers": [42]})
        r = self.call("ANSWER: 42", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "distractor_equals_key")

    def test_noop_case3(self):
        r = self.call("ANSWER: 42 - 5 = 37")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))

    def test_noop_decimal_key(self):
        item = item_fixtures.make_item(
            "NOOP", {"value": Decimal("3.50")}, {"distractor_answers": []}
        )
        r = self.call("ANSWER: 3.5", item)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_noop_superset_rejected(self):
        r = self.call("ANSWER: 37, 42")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "multi_number")


if __name__ == "__main__":
    unittest.main()
