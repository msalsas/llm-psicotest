import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS
from psicotest.checkers.common import ItemSchemaError

CSP = item_fixtures.CSP
PEOPLE = ["Ana", "Bruno", "Carla", "Dario"]


def csp_item(key, constraints):
    return item_fixtures.make_item(
        "CSP",
        {"assignment": key},
        {"people": PEOPLE, "n_slots": 4, "constraints": constraints},
    )


class TestCheckersCSP(unittest.TestCase):
    def call(self, content, item=CSP):
        return CHECKERS["CSP"](content, "stop", None, item)

    def test_csp_case1(self):
        r = self.call("RESPUESTA: A=3; B=3; C=4; D=2")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "invalid_perm")

    def test_csp_case2(self):
        r = self.call("RESPUESTA: ver tabla arriba")
        self.assertEqual(r.outcome, "NOANS")
        self.assertEqual(r.detail, "no_pairs")

    def test_csp_case3(self):
        r = self.call("RESPUESTA: Ana=2; Bruno=1; Carla=4; Dario=3")
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "alt_solution")

    def test_csp_ok_forms(self):
        r = self.call("RESPUESTA: A=3; B=1; C=4; D=2")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ())
        r = self.call("RESPUESTA: ana: 3, BRUNO: 1, Carla=4; Darío=2")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ())

    def test_csp_violation(self):
        r = self.call("RESPUESTA: Ana=1; Bruno=2; Carla=4; Dario=3")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.detail, "violated:0,1")

    def test_csp_incomplete(self):
        r = self.call("RESPUESTA: A=3; B=1")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.detail, "incomplete")

    def test_csp_unknown_name(self):
        r = self.call("RESPUESTA: Zoe=1; B=1")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "unknown_name:zoe")

    def test_csp_key_invalid(self):
        item = csp_item(
            {"Ana": 2, "Bruno": 3, "Carla": 4, "Dario": 1},
            [
                ["at", "Ana", 2],
                ["gt", "Carla", 3],
                ["before", "Bruno", "Carla"],
                ["not_at", "Dario", 1],
            ],
        )
        r = self.call("RESPUESTA: Ana=2; Bruno=3; Carla=4; Dario=1", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "key_violates:3")

    def test_csp_schema(self):
        with self.assertRaises(ItemSchemaError):
            self.call(
                "RESPUESTA: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["near", "Ana", 1]]),
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "RESPUESTA: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["before", "Ana"]]),
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "RESPUESTA: A=3; B=1; C=4; D=2", csp_item(CSP.key["assignment"], [["gt", "Ana", 9]])
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "RESPUESTA: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["gap", "Ana", "Bruno", -2]]),
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "RESPUESTA: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["in", "Ana", [[1], 2]]]),
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "RESPUESTA: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["in", "Ana", [1, "x"]]]),
            )
        bad_people = item_fixtures.make_item(
            "CSP",
            {"assignment": CSP.key["assignment"]},
            {
                "people": ["Ana", ["Bruno"], "Carla", "Dario"],
                "n_slots": 4,
                "constraints": [],
            },
        )
        with self.assertRaises(ItemSchemaError):
            self.call("RESPUESTA: A=3; B=1; C=4; D=2", bad_people)
        bad_name = item_fixtures.make_item(
            "CSP",
            {"assignment": CSP.key["assignment"]},
            {"people": ["A\n", "Bruno", "Carla", "Dario"], "n_slots": 4, "constraints": []},
        )
        with self.assertRaises(ItemSchemaError):
            self.call("RESPUESTA: A=3; B=1; C=4; D=2", bad_name)
        bad_slots = item_fixtures.make_item(
            "CSP",
            {"assignment": CSP.key["assignment"]},
            {"people": PEOPLE, "n_slots": 5, "constraints": []},
        )
        with self.assertRaises(ItemSchemaError):
            self.call("RESPUESTA: A=3; B=1; C=4; D=2", bad_slots)

    def test_csp_dsl_table(self):
        ops = [
            (
                ["at", "Ana", 3],
                {"Ana": 3, "Bruno": 1, "Carla": 4, "Dario": 2},
                {"Ana": 1, "Bruno": 2, "Carla": 4, "Dario": 3},
            ),
            (
                ["not_at", "Ana", 3],
                {"Ana": 2, "Bruno": 1, "Carla": 4, "Dario": 3},
                {"Ana": 3, "Bruno": 1, "Carla": 4, "Dario": 2},
            ),
            (
                ["before", "Bruno", "Ana"],
                {"Ana": 3, "Bruno": 1, "Carla": 4, "Dario": 2},
                {"Ana": 1, "Bruno": 2, "Carla": 4, "Dario": 3},
            ),
            (
                ["adjacent", "Dario", "Ana"],
                {"Ana": 3, "Bruno": 1, "Carla": 4, "Dario": 2},
                {"Ana": 1, "Bruno": 2, "Carla": 4, "Dario": 3},
            ),
            (
                ["not_adjacent", "Dario", "Ana"],
                {"Ana": 1, "Bruno": 2, "Carla": 4, "Dario": 3},
                {"Ana": 2, "Bruno": 1, "Carla": 4, "Dario": 3},
            ),
            (
                ["gap", "Dario", "Ana", 2],
                {"Ana": 1, "Bruno": 2, "Carla": 4, "Dario": 3},
                {"Ana": 1, "Bruno": 3, "Carla": 4, "Dario": 2},
            ),
            (
                ["offset", "Dario", "Ana", 1],
                {"Ana": 3, "Bruno": 1, "Carla": 4, "Dario": 2},
                {"Ana": 2, "Bruno": 1, "Carla": 4, "Dario": 3},
            ),
            (
                ["lt", "Ana", 3],
                {"Ana": 2, "Bruno": 1, "Carla": 4, "Dario": 3},
                {"Ana": 3, "Bruno": 1, "Carla": 4, "Dario": 2},
            ),
            (
                ["gt", "Ana", 2],
                {"Ana": 3, "Bruno": 1, "Carla": 4, "Dario": 2},
                {"Ana": 2, "Bruno": 1, "Carla": 4, "Dario": 3},
            ),
            (
                ["parity", "Ana", "even"],
                {"Ana": 2, "Bruno": 1, "Carla": 4, "Dario": 3},
                {"Ana": 1, "Bruno": 2, "Carla": 4, "Dario": 3},
            ),
            (
                ["in", "Ana", [1, 3]],
                {"Ana": 3, "Bruno": 1, "Carla": 4, "Dario": 2},
                {"Ana": 2, "Bruno": 1, "Carla": 4, "Dario": 3},
            ),
            (
                ["between", "Bruno", "Ana", "Carla"],
                {"Ana": 1, "Bruno": 2, "Carla": 4, "Dario": 3},
                {"Ana": 1, "Bruno": 4, "Carla": 2, "Dario": 3},
            ),
        ]
        for constraint, key, wrong in ops:
            with self.subTest(op=constraint[0]):
                item = csp_item(key, [constraint])
                parts = "; ".join(f"{p}={v}" for p, v in key.items())
                r = self.call(f"RESPUESTA: {parts}", item)
                self.assertEqual(r.outcome, "OK")
                parts = "; ".join(f"{p}={v}" for p, v in wrong.items())
                r = self.call(f"RESPUESTA: {parts}", item)
                self.assertEqual(r.outcome, "WRONG")
                self.assertEqual(r.detail, "violated:0")


if __name__ == "__main__":
    unittest.main()
