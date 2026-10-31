import unittest
from decimal import Decimal

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS
from psicotest.checkers.err import STEP_RE, VALUE_RE

ERR = item_fixtures.ERR


class TestCheckersERR(unittest.TestCase):
    def call(self, content, item=ERR):
        return CHECKERS["ERR"](content, "stop", None, item)

    def test_err_case1(self):
        r = self.call("ANSWER: STEP 5 and 6")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "multi_step")

    def test_err_value_before_step(self):
        r = self.call("ANSWER: VALUE 1; STEP 5 and 6")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "multi_step")

    def test_err_case2(self):
        r = self.call("ANSWER: step 5; value: 1,234")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_FAIL",))
        self.assertEqual(r.detail, "value_ok")
        self.assertEqual(r.value, {"step": 5, "value": Decimal("1234"), "value_ok": True})

    def test_err_case3(self):
        r = self.call("The error is in step 5 and the correct value is 1234.")
        self.assertEqual(r.outcome, "NOANS")

    def test_err_value_secondary(self):
        r = self.call("ANSWER: STEP 5; VALUE 1235")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.detail, "value_wrong")
        r = self.call("ANSWER: STEP 4; VALUE 1234")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.detail, "value_ok")
        r = self.call("ANSWER: STEP 5")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "value_missing")

    def test_err_no_step(self):
        r = self.call("ANSWER: VALUE 1234")
        self.assertEqual(r.outcome, "NOANS")
        self.assertEqual(r.detail, "no_step")

    def test_err_gen_bug(self):
        item = item_fixtures.make_item("ERR", {"step": 9, "value": 1234}, {"n_steps": 8})
        r = self.call("ANSWER: STEP 9; VALUE 1234", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "step_out_of_range")

    def test_err_markers_english(self):
        self.assertEqual(STEP_RE.pattern, r"STEP\s*[:=]?\s*(\d+)")
        self.assertEqual(VALUE_RE.pattern, r"VALUE\s*[:=]?\s*([+-]?\d(?:[\d.,]*\d)?)")
        r = self.call("ANSWER: PA" + "SO 5; VA" + "LOR 1234")
        self.assertEqual(r.outcome, "NOANS")
        self.assertEqual(r.detail, "no_step")


if __name__ == "__main__":
    unittest.main()
