import unittest
from decimal import Decimal

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS
from psicotest.checkers.common import ItemSchemaError
from psicotest.checkers.keyed import PAIR_RE


class TestCheckersST(unittest.TestCase):
    def call(self, content, item=item_fixtures.ST):
        return CHECKERS["ST"](content, "stop", None, item)

    def test_st_case1(self):
        r = self.call("ANSWER: C=5; A=2")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("R2_OK",))
        self.assertEqual(r.detail, "mismatch:A,C")

    def test_st_case2(self):
        r = self.call("ANSWER: A=4; C=2\nChecking box A.\nANSWER: A=5; C=2")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("MULTI", "R2_OK"))

    def test_st_case3(self):
        r = self.call("ANSWER: A = five; C = two")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))
        self.assertEqual(r.value, {"A": Decimal("5"), "C": Decimal("2")})

    def test_st_extra_and_prefix(self):
        r = self.call("ANSWER: box a = 5, B=9; Box C: 2")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_st_missing(self):
        r = self.call("ANSWER: A=5")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.detail, "missing:C")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_st_stray(self):
        r = self.call("ANSWER: A=5; xyz; C=2")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("FMT", "R2_OK"))
        self.assertEqual(r.detail, "stray")

    def test_st_conflict(self):
        r = self.call("ANSWER: A=5; A=6; C=2")
        self.assertEqual(r.outcome, "AMBIG")
        self.assertEqual(r.flags, ())
        self.assertEqual(r.detail, "conflict:A")

    def test_st_no_pairs(self):
        r = self.call("ANSWER: 5 and 2")
        self.assertEqual(r.outcome, "NOANS")
        self.assertEqual(r.detail, "no_pairs")

    def test_st_gen_bug(self):
        item = item_fixtures.make_item(
            "ST", {"boxes": {"G": 1}}, {"boxes": ["A", "B", "C", "D", "E", "F"]}
        )
        r = self.call("ANSWER: G=1", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "key_label_unknown")

    def test_st_no_key_label_no_r2(self):
        r = self.call("ANSWER: B=9")
        self.assertEqual(r.outcome, "WRONG")
        self.assertTrue(r.detail.startswith("missing:"))
        self.assertEqual(r.flags, ())

    def test_st_schema(self):
        bad_key = item_fixtures.make_item(
            "ST", {"boxes": {}}, {"boxes": ["A", "B", "C", "D", "E", "F"]}
        )
        with self.assertRaises(ItemSchemaError):
            self.call("ANSWER: A=5", bad_key)
        bool_value = item_fixtures.make_item(
            "ST", {"boxes": {"A": True}}, {"boxes": ["A", "B", "C", "D", "E", "F"]}
        )
        with self.assertRaises(ItemSchemaError):
            self.call("ANSWER: A=5", bool_value)
        no_meta = item_fixtures.make_item("ST", {"boxes": {"A": 5, "C": 2}}, {})
        with self.assertRaises(ItemSchemaError):
            self.call("ANSWER: A=5", no_meta)
        list_boxes = item_fixtures.make_item(
            "ST", {"boxes": {"A": 5, "C": 2}}, {"boxes": ["A", "B", ["C"], "D", "E", "F"]}
        )
        with self.assertRaises(ItemSchemaError):
            self.call("ANSWER: A=5; C=2", list_boxes)

    def test_st_box_prefix(self):
        self.assertEqual(PAIR_RE.pattern, r"^(?:box\s+)?([^\W_]\w*)\s*[=:]\s*(.+?)$")
        r = self.call("ANSWER: Box A = 5; box C = 2")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_OK",))


if __name__ == "__main__":
    unittest.main()
