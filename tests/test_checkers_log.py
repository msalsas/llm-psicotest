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
        r = self.call("ANSWER: knights: A, C; knaves: B and E")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.detail, "complement")
        r = self.call("ANSWER: knights: A, C")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "underdetermined")

    def test_log_case2(self):
        r = self.call("ANSWER: all except B and D are knights")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "no_structure")

    def test_log_case3(self):
        r = self.call("ANSWER: knights: A, C; knaves: B, D; spy: E")
        self.assertEqual(r.outcome, "WRONG")

    def test_log_ok_full(self):
        r = self.call("ANSWER: Knights: A and C; Knaves: B, E; Spy: D")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(
            r.value,
            {"knave": ["B", "E"], "knight": ["A", "C"], "spy": ["D"]},
        )

    def test_log_conflict(self):
        r = self.call("ANSWER: knights: A, C; knaves: A, B, E; spy: D")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "conflict:A")

    def test_log_unknown_name_order(self):
        r = self.call("ANSWER: knights: A, C; knaves: A, B, E; spy: X")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "unknown_name:x")

    def test_log_uppercase_y(self):
        r = self.call("ANSWER: Knights: A AND C")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "underdetermined")
        r = self.call("ANSWER: Knights: A AND C; Knaves: B AND E; Spy: D")
        self.assertEqual(r.outcome, "OK")

    def test_log_unknown_role(self):
        r = self.call("ANSWER: wizards: A")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "unknown_role")

    def test_log_noans(self):
        r = self.call("ANSWER: I don't know")
        self.assertEqual(r.outcome, "NOANS")

    def test_log_gen_bug(self):
        item = item_fixtures.make_item(
            "LOG",
            {"roles": {"A": "knight", "B": "knave", "C": "knight", "D": "spy"}},
            {"agents": ["A", "B", "C", "D", "E"]},
        )
        r = self.call("ANSWER: knights: A, C; knaves: B; spy: D", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "key_invalid")

    def test_log_schema_list_agents(self):
        item = item_fixtures.make_item(
            "LOG",
            {"roles": {"A": "knight", "B": "knave", "C": "knight", "D": "spy", "E": "knave"}},
            {"agents": ["A", "B", ["C"], "D", "E"]},
        )
        with self.assertRaises(ItemSchemaError):
            self.call("ANSWER: knights: A, C", item)

    def test_log_role_words(self):
        from psicotest.checkers.logic import NONE_WORDS, ROLE_WORDS

        self.assertEqual(
            ROLE_WORDS,
            {
                "knight": "knight",
                "knights": "knight",
                "knave": "knave",
                "knaves": "knave",
                "spy": "spy",
                "spies": "spy",
            },
        )
        self.assertEqual(NONE_WORDS, ("none", "nobody", "no one"))
        self.assertEqual(self.call("ANSWER: knaves: B, and E; knights: A, C; spy: D").outcome, "OK")
        r = self.call("ANSWER: caball" + "eros: A, C; bribo" + "nes: B, E; esp" + "ia: D")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.detail, "unknown_role")


if __name__ == "__main__":
    unittest.main()
