import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS

AR = item_fixtures.AR


class TestCheckersAR(unittest.TestCase):
    def call(self, content, finish="stop", reasoning=None, item=AR):
        return CHECKERS["AR"](content, finish, reasoning, item)

    def test_ar_case1(self):
        r = self.call("RESPUESTA: 4.567.890.123")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_FAIL",))

    def test_ar_case2(self):
        r = self.call("RESPUESTA: \u2248 4,57\u00d710^9")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))

    def test_ar_case3(self):
        r = self.call("", "stop", "Calculo.\nRESPUESTA: 4567890123")
        self.assertEqual(r.outcome, "NOANS")
        self.assertEqual(r.flags, ("REASONING_ONLY",))

    def test_ar_non_integer(self):
        r = self.call("RESPUESTA: 4567890123,5")
        self.assertEqual(r.outcome, "WRONG")
        r = self.call("RESPUESTA: 4567890123,0")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))

    def test_ar_ambig(self):
        r = self.call("RESPUESTA: 4567890123 o 4567890124")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "multi_number")


if __name__ == "__main__":
    unittest.main()
