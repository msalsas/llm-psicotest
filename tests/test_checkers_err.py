import unittest
from decimal import Decimal

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS

ERR = item_fixtures.ERR


class TestCheckersERR(unittest.TestCase):
    def call(self, content, item=ERR):
        return CHECKERS["ERR"](content, "stop", None, item)

    def test_err_case1(self):
        r = self.call("RESPUESTA: PASO 5 y 6")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "multi_step")

    def test_err_value_before_step(self):
        r = self.call("RESPUESTA: VALOR 1; PASO 5 y 6")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "multi_step")

    def test_err_case2(self):
        r = self.call("RESPUESTA: paso 5; valor: 1.234")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_FAIL",))
        self.assertEqual(r.detail, "value_ok")
        self.assertEqual(r.value, {"step": 5, "value": Decimal("1234"), "value_ok": True})

    def test_err_case3(self):
        r = self.call("El error está en el paso 5 y el valor correcto es 1234.")
        self.assertEqual(r.outcome, "NOANS")

    def test_err_value_secondary(self):
        r = self.call("RESPUESTA: PASO 5; VALOR 1235")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.detail, "value_wrong")
        r = self.call("RESPUESTA: PASO 4; VALOR 1234")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.detail, "value_ok")
        r = self.call("RESPUESTA: PASO 5")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "value_missing")

    def test_err_no_step(self):
        r = self.call("RESPUESTA: VALOR 1234")
        self.assertEqual(r.outcome, "NOANS")
        self.assertEqual(r.detail, "no_step")

    def test_err_gen_bug(self):
        item = item_fixtures.make_item("ERR", {"step": 9, "value": 1234}, {"n_steps": 8})
        r = self.call("RESPUESTA: PASO 9; VALOR 1234", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "step_out_of_range")


if __name__ == "__main__":
    unittest.main()
