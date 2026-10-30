import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS
from psicotest.checkers.common import ItemSchemaError

LOG = item_fixtures.LOG


class TestCheckersLOG(unittest.TestCase):
    def call(self, content, item=LOG):
        return CHECKERS["LOG"](content, "stop", None, item)

    def test_log_case1(self):
        r = self.call("RESPUESTA: caballeros: A, C; bribones: B y E")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.detail, "complement")
        r = self.call("RESPUESTA: caballeros: A, C")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "underdetermined")

    def test_log_case2(self):
        r = self.call("RESPUESTA: todos menos B y D son caballeros")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "no_structure")

    def test_log_case3(self):
        r = self.call("RESPUESTA: caballeros: A, C; bribones: B, D; espía: E")
        self.assertEqual(r.outcome, "WRONG")

    def test_log_ok_full(self):
        r = self.call("RESPUESTA: Caballeros: A y C; Bribones: B, E; Espía: D")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(
            r.value,
            {"knave": ["B", "E"], "knight": ["A", "C"], "spy": ["D"]},
        )

    def test_log_conflict(self):
        r = self.call("RESPUESTA: caballeros: A, C; bribones: A, B, E; espía: D")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "conflict:A")

    def test_log_unknown_name_order(self):
        r = self.call("RESPUESTA: caballeros: A, C; bribones: A, B, E; espía: X")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "unknown_name:x")

    def test_log_uppercase_y(self):
        r = self.call("RESPUESTA: Caballeros: A Y C")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "underdetermined")
        r = self.call("RESPUESTA: Caballeros: A Y C; Bribones: B Y E; Espía: D")
        self.assertEqual(r.outcome, "OK")

    def test_log_unknown_role(self):
        r = self.call("RESPUESTA: magos: A")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "unknown_role")

    def test_log_noans(self):
        r = self.call("RESPUESTA: no lo sé")
        self.assertEqual(r.outcome, "NOANS")

    def test_log_gen_bug(self):
        item = item_fixtures.make_item(
            "LOG",
            {"roles": {"A": "knight", "B": "knave", "C": "knight", "D": "spy"}},
            {"agents": ["A", "B", "C", "D", "E"]},
        )
        r = self.call("RESPUESTA: caballeros: A, C; bribones: B; espía: D", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "key_invalid")

    def test_log_schema_list_agents(self):
        item = item_fixtures.make_item(
            "LOG",
            {"roles": {"A": "knight", "B": "knave", "C": "knight", "D": "spy", "E": "knave"}},
            {"agents": ["A", "B", ["C"], "D", "E"]},
        )
        with self.assertRaises(ItemSchemaError):
            self.call("RESPUESTA: caballeros: A, C", item)


if __name__ == "__main__":
    unittest.main()
