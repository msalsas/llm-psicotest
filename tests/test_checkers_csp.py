import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS
from psicotest.checkers.common import ItemSchemaError

CSP = item_fixtures.CSP
PEOPLE = ["Alice", "Brian", "Clara", "David"]


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
        r = self.call("ANSWER: A=3; B=3; C=4; D=2")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "invalid_perm")

    def test_csp_case2(self):
        r = self.call("ANSWER: see table above")
        self.assertEqual(r.outcome, "NOANS")
        self.assertEqual(r.detail, "no_pairs")

    def test_csp_case3(self):
        r = self.call("ANSWER: Alice=2; Brian=1; Clara=4; David=3")
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "alt_solution")

    def test_csp_ok_forms(self):
        r = self.call("ANSWER: A=3; B=1; C=4; D=2")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ())
        r = self.call("ANSWER: alice: 3, BRIAN: 1, Clara=4; david=2")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ())

    def test_csp_violation(self):
        r = self.call("ANSWER: Alice=1; Brian=2; Clara=4; David=3")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.detail, "violated:0,1")

    def test_csp_incomplete(self):
        r = self.call("ANSWER: A=3; B=1")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.detail, "incomplete")

    def test_csp_unknown_name(self):
        r = self.call("ANSWER: Zoe=1; B=1")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "unknown_name:zoe")

    def test_csp_key_invalid(self):
        item = csp_item(
            {"Alice": 2, "Brian": 3, "Clara": 4, "David": 1},
            [
                ["at", "Alice", 2],
                ["gt", "Clara", 3],
                ["before", "Brian", "Clara"],
                ["not_at", "David", 1],
            ],
        )
        r = self.call("ANSWER: Alice=2; Brian=3; Clara=4; David=1", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "key_violates:3")

    def test_csp_schema(self):
        with self.assertRaises(ItemSchemaError):
            self.call(
                "ANSWER: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["near", "Alice", 1]]),
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "ANSWER: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["before", "Alice"]]),
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "ANSWER: A=3; B=1; C=4; D=2", csp_item(CSP.key["assignment"], [["gt", "Alice", 9]])
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "ANSWER: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["gap", "Alice", "Brian", -2]]),
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "ANSWER: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["in", "Alice", [[1], 2]]]),
            )
        with self.assertRaises(ItemSchemaError):
            self.call(
                "ANSWER: A=3; B=1; C=4; D=2",
                csp_item(CSP.key["assignment"], [["in", "Alice", [1, "x"]]]),
            )
        bad_people = item_fixtures.make_item(
            "CSP",
            {"assignment": CSP.key["assignment"]},
            {
                "people": ["Alice", ["Brian"], "Clara", "David"],
                "n_slots": 4,
                "constraints": [],
            },
        )
        with self.assertRaises(ItemSchemaError):
            self.call("ANSWER: A=3; B=1; C=4; D=2", bad_people)
        bad_name = item_fixtures.make_item(
            "CSP",
            {"assignment": CSP.key["assignment"]},
            {"people": ["A\n", "Brian", "Clara", "David"], "n_slots": 4, "constraints": []},
        )
        with self.assertRaises(ItemSchemaError):
            self.call("ANSWER: A=3; B=1; C=4; D=2", bad_name)
        bad_slots = item_fixtures.make_item(
            "CSP",
            {"assignment": CSP.key["assignment"]},
            {"people": PEOPLE, "n_slots": 5, "constraints": []},
        )
        with self.assertRaises(ItemSchemaError):
            self.call("ANSWER: A=3; B=1; C=4; D=2", bad_slots)

    def test_csp_dsl_table(self):
        ops = [
            (
                ["at", "Alice", 3],
                {"Alice": 3, "Brian": 1, "Clara": 4, "David": 2},
                {"Alice": 1, "Brian": 2, "Clara": 4, "David": 3},
            ),
            (
                ["not_at", "Alice", 3],
                {"Alice": 2, "Brian": 1, "Clara": 4, "David": 3},
                {"Alice": 3, "Brian": 1, "Clara": 4, "David": 2},
            ),
            (
                ["before", "Brian", "Alice"],
                {"Alice": 3, "Brian": 1, "Clara": 4, "David": 2},
                {"Alice": 1, "Brian": 2, "Clara": 4, "David": 3},
            ),
            (
                ["adjacent", "David", "Alice"],
                {"Alice": 3, "Brian": 1, "Clara": 4, "David": 2},
                {"Alice": 1, "Brian": 2, "Clara": 4, "David": 3},
            ),
            (
                ["not_adjacent", "David", "Alice"],
                {"Alice": 1, "Brian": 2, "Clara": 4, "David": 3},
                {"Alice": 2, "Brian": 1, "Clara": 4, "David": 3},
            ),
            (
                ["gap", "David", "Alice", 2],
                {"Alice": 1, "Brian": 2, "Clara": 4, "David": 3},
                {"Alice": 1, "Brian": 3, "Clara": 4, "David": 2},
            ),
            (
                ["offset", "David", "Alice", 1],
                {"Alice": 3, "Brian": 1, "Clara": 4, "David": 2},
                {"Alice": 2, "Brian": 1, "Clara": 4, "David": 3},
            ),
            (
                ["lt", "Alice", 3],
                {"Alice": 2, "Brian": 1, "Clara": 4, "David": 3},
                {"Alice": 3, "Brian": 1, "Clara": 4, "David": 2},
            ),
            (
                ["gt", "Alice", 2],
                {"Alice": 3, "Brian": 1, "Clara": 4, "David": 2},
                {"Alice": 2, "Brian": 1, "Clara": 4, "David": 3},
            ),
            (
                ["parity", "Alice", "even"],
                {"Alice": 2, "Brian": 1, "Clara": 4, "David": 3},
                {"Alice": 1, "Brian": 2, "Clara": 4, "David": 3},
            ),
            (
                ["in", "Alice", [1, 3]],
                {"Alice": 3, "Brian": 1, "Clara": 4, "David": 2},
                {"Alice": 2, "Brian": 1, "Clara": 4, "David": 3},
            ),
            (
                ["between", "Brian", "Alice", "Clara"],
                {"Alice": 1, "Brian": 2, "Clara": 4, "David": 3},
                {"Alice": 1, "Brian": 4, "Clara": 2, "David": 3},
            ),
        ]
        for constraint, key, wrong in ops:
            with self.subTest(op=constraint[0]):
                item = csp_item(key, [constraint])
                parts = "; ".join(f"{p}={v}" for p, v in key.items())
                r = self.call(f"ANSWER: {parts}", item)
                self.assertEqual(r.outcome, "OK")
                parts = "; ".join(f"{p}={v}" for p, v in wrong.items())
                r = self.call(f"ANSWER: {parts}", item)
                self.assertEqual(r.outcome, "WRONG")
                self.assertEqual(r.detail, "violated:0")


if __name__ == "__main__":
    unittest.main()
