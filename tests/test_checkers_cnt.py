import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS

CNT = item_fixtures.CNT


class TestCheckersCNT(unittest.TestCase):
    def call(self, content):
        return CHECKERS["CNT"](content, "stop", None, CNT)

    def test_cnt_case1(self):
        r = self.call("RESPUESTA: 17 (contando la inicial)")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_cnt_case2(self):
        r = self.call("RESPUESTA: entre 16 y 17")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "multi_number")

    def test_cnt_case3(self):
        r = self.call("RESPUESTA: diecisiete")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))

    def test_cnt_wrong(self):
        r = self.call("RESPUESTA: 16")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("R2_OK",))


if __name__ == "__main__":
    unittest.main()
