import unittest
from decimal import Decimal

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS


class TestCheckersAR2(unittest.TestCase):
    def call(self, content, item=item_fixtures.AR2):
        return CHECKERS["AR2"](content, "stop", None, item)

    def test_ar2_case1(self):
        r = self.call("ANSWER: 12,35")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("FMT", "R2_FAIL"))

    def test_ar2_case2(self):
        r = self.call("ANSWER: 12.345", item_fixtures.AR2_BIG)
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.value, Decimal("12.345"))

    def test_ar2_case3(self):
        r = self.call("ANSWER: 12.350")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_ar2_boundary_hole(self):
        r = self.call("ANSWER: 12.345")
        self.assertEqual(r.outcome, "WRONG")

    def test_ar2_extra_precision(self):
        r = self.call("ANSWER: 12.3549")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))
        r = self.call("ANSWER: 12.3551")
        self.assertEqual(r.outcome, "WRONG")

    def test_ar2_gen_bug(self):
        item = item_fixtures.make_item("AR2", {"value": Decimal("12.3")}, {})
        r = self.call("ANSWER: 12.3", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "key_not_2dp")


if __name__ == "__main__":
    unittest.main()
