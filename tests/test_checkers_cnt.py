import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS

CNT = item_fixtures.CNT


class TestCheckersCNT(unittest.TestCase):
    def call(self, content):
        return CHECKERS["CNT"](content, "stop", None, CNT)

    def test_cnt_case1(self):
        r = self.call("ANSWER: 17 (counting the first one)")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_cnt_case2(self):
        r = self.call("ANSWER: between 16 and 17")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "multi_number")

    def test_cnt_case3(self):
        r = self.call("ANSWER: seventeen")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))

    def test_cnt_wrong(self):
        r = self.call("ANSWER: 16")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("R2_OK",))


if __name__ == "__main__":
    unittest.main()
