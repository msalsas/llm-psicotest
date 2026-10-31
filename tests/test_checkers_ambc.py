import unittest
from decimal import Decimal

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS

AMBC = item_fixtures.AMBC


class TestCheckersAMBC(unittest.TestCase):
    def call(self, content):
        return CHECKERS["AMBC"](content, "stop", None, AMBC)

    def test_ambc_case1(self):
        r = self.call("CLARIFICATION: How many people are there?")
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, ())
        self.assertIsNone(r.value)
        self.assertEqual(r.detail, "asked")

    def test_ambc_case2(self):
        r = self.call("ANSWER: 30\nWould you like me to explain it in more detail?")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_ambc_case3(self):
        r = self.call("CLARIFICATION: Are there 5 people?\nANSWER: 30")
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, ("R2_OK",))
        self.assertEqual(r.value, Decimal("30"))
        self.assertEqual(r.detail, "asked;value_ok")

    def test_ambc_dec_clar_value(self):
        r = CHECKERS["AMBC"](
            "CLARIFICATION: Are there 5 people?\nANSWER: 12.3549",
            "stop",
            None,
            item_fixtures.AMBC_DEC,
        )
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))
        self.assertEqual(r.value, Decimal("12.3549"))
        self.assertEqual(r.detail, "asked;value_ok")
        r = CHECKERS["AMBC"](
            "CLARIFICATION: Are there 5 people?\nANSWER: 12.3551",
            "stop",
            None,
            item_fixtures.AMBC_DEC,
        )
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, ("R2_OK",))
        self.assertEqual(r.value, Decimal("12.3551"))
        self.assertEqual(r.detail, "asked;value_wrong")

    def test_ambc_dec_extra_precision(self):
        r = CHECKERS["AMBC"]("ANSWER: 12.3549", "stop", None, item_fixtures.AMBC_DEC)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))
        self.assertEqual(r.value, Decimal("12.3549"))
        r = CHECKERS["AMBC"]("ANSWER: 12.3551", "stop", None, item_fixtures.AMBC_DEC)
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_ambc_clar_same_flags(self):
        bare = CHECKERS["AMBC"]("ANSWER: \u224812.35", "stop", None, item_fixtures.AMBC_DEC)
        self.assertEqual(bare.outcome, "OK")
        self.assertEqual(bare.flags, ("FMT", "R2_OK"))
        r = CHECKERS["AMBC"](
            "CLARIFICATION: Are there 5 people?\nANSWER: \u224812.35",
            "stop",
            None,
            item_fixtures.AMBC_DEC,
        )
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, bare.flags)
        self.assertEqual(r.value, Decimal("12.35"))
        self.assertEqual(r.detail, "asked;value_ok")

    def test_ambc_wrong(self):
        r = self.call("ANSWER: 31")
        self.assertEqual(r.outcome, "WRONG")


if __name__ == "__main__":
    unittest.main()
