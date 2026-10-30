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
        r = self.call("ACLARACION: ¿Cuántas personas hay?")
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, ())
        self.assertIsNone(r.value)
        self.assertEqual(r.detail, "asked")

    def test_ambc_case2(self):
        r = self.call("RESPUESTA: 30\n¿Quieres que lo explique con más detalle?")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_ambc_case3(self):
        r = self.call("ACLARACION: ¿Son 5 personas?\nRESPUESTA: 30")
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, ("R2_OK",))
        self.assertEqual(r.value, Decimal("30"))
        self.assertEqual(r.detail, "asked;value_ok")

    def test_ambc_dec_clar_value(self):
        r = CHECKERS["AMBC"](
            "ACLARACION: ¿Son 5 personas?\nRESPUESTA: 12,3549", "stop", None, item_fixtures.AMBC_DEC
        )
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))
        self.assertEqual(r.value, Decimal("12.3549"))
        self.assertEqual(r.detail, "asked;value_ok")
        r = CHECKERS["AMBC"](
            "ACLARACION: ¿Son 5 personas?\nRESPUESTA: 12,3551", "stop", None, item_fixtures.AMBC_DEC
        )
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, ("R2_OK",))
        self.assertEqual(r.value, Decimal("12.3551"))
        self.assertEqual(r.detail, "asked;value_wrong")

    def test_ambc_dec_extra_precision(self):
        r = CHECKERS["AMBC"]("RESPUESTA: 12,3549", "stop", None, item_fixtures.AMBC_DEC)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))
        self.assertEqual(r.value, Decimal("12.3549"))
        r = CHECKERS["AMBC"]("RESPUESTA: 12,3551", "stop", None, item_fixtures.AMBC_DEC)
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_ambc_clar_same_flags(self):
        bare = CHECKERS["AMBC"]("RESPUESTA: \u224812,35", "stop", None, item_fixtures.AMBC_DEC)
        self.assertEqual(bare.outcome, "OK")
        self.assertEqual(bare.flags, ("FMT", "R2_OK"))
        r = CHECKERS["AMBC"](
            "ACLARACION: \u00bfSon 5 personas?\nRESPUESTA: \u224812,35",
            "stop",
            None,
            item_fixtures.AMBC_DEC,
        )
        self.assertEqual(r.outcome, "CLAR_OVER")
        self.assertEqual(r.flags, bare.flags)
        self.assertEqual(r.value, Decimal("12.35"))
        self.assertEqual(r.detail, "asked;value_ok")

    def test_ambc_wrong(self):
        r = self.call("RESPUESTA: 31")
        self.assertEqual(r.outcome, "WRONG")


if __name__ == "__main__":
    unittest.main()
