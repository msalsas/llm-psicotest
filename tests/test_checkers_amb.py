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
        r = self.call("ACLARACION: asumo 3 \u20ac/u. RESPUESTA: 45")
        self.assertEqual(r.outcome, "CLAR_MISS")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "answered")
        self.assertEqual(r.score, 0)

    def test_amb_case2(self):
        r = self.call("ACLARACION: ¿Cuánto cuesta cada unidad?")
        self.assertEqual(r.outcome, "CLAR_OK")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "synonym:cuesta")
        self.assertEqual(r.score, 1)
        self.assertEqual(r.value, "¿Cuánto cuesta cada unidad?")

    def test_amb_case3(self):
        r = self.call("ACLARACION: ¿Cuántas unidades compra?")
        self.assertEqual(r.outcome, "CLAR_BAD")
        self.assertEqual(r.flags, ("REVIEW",))
        self.assertEqual(r.detail, "no_synonym")

    def test_amb_answered_lines(self):
        r = self.call("Supongo 3 \u20ac.\nRESPUESTA: 45")
        self.assertEqual(r.outcome, "CLAR_MISS")

    def test_amb_no_question(self):
        r = self.call("ACLARACION: falta el precio")
        self.assertEqual(r.outcome, "CLAR_BAD")
        self.assertEqual(r.flags, ("REVIEW",))
        self.assertEqual(r.detail, "no_question")

    def test_amb_no_prefix_hole(self):
        r = self.call("¿Cuál es el precio?")
        self.assertEqual(r.outcome, "CLAR_OK")
        self.assertEqual(r.flags, ("FMT",))
        self.assertEqual(r.detail, "no_prefix;synonym:precio")

    def test_amb_extra_line(self):
        r = self.call("ACLARACIÓN: ¿Cuál es el coste?\nGracias.")
        self.assertEqual(r.outcome, "CLAR_OK")
        self.assertEqual(r.flags, ("FMT",))

    def test_amb_all_asker(self):
        r = self.call("ACLARACION: ¿Qué dato falta?")
        self.assertEqual(r.outcome, "CLAR_BAD")
        self.assertEqual(r.flags, ("REVIEW",))

    def test_amb_empty_and_trunc(self):
        r = self.call("")
        self.assertEqual(r.outcome, "NOANS")
        r = self.call("ACLARACION: ¿precio?", finish="length")
        self.assertEqual(r.outcome, "TRUNC")

    def test_amb_gen_bug(self):
        item = item_fixtures.make_item("AMB", {"value": 45}, {"synonyms": ["dato"]})
        r = self.call("ACLARACION: ¿dato?", item=item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "generic_synonym")

    def test_amb_wordless_synonym(self):
        item = item_fixtures.make_item("AMB", {"value": 45}, {"synonyms": ["???"]})
        with self.assertRaises(ItemSchemaError):
            self.call("ACLARACION: ¿precio?", item=item)

    def test_ambr_numeric(self):
        r = self.call("RESPUESTA: 45", family="AMBR")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))
        r = self.call("RESPUESTA: 45 \u20ac", family="AMBR")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_FAIL",))
        r = self.call("ACLARACION: ¿precio?", family="AMBR")
        self.assertEqual(r.outcome, "NOANS")


if __name__ == "__main__":
    unittest.main()
