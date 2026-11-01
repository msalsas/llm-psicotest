import dataclasses
import re
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import _bootstrap
import fakes
import item_fixtures
import test_fakes_smoke

from psicotest.checkers import CHECKERS, check_turn, dispatch_key
from psicotest.checkers.common import ItemSchemaError, make_result, num_equal
from psicotest.checkers.logic import ROLE_WORDS
from psicotest.checkers.rules import singular_candidates
from psicotest.checkers.text import (
    ANIMAL_STOP_WORDS,
    ANIMAL_WORDS,
    CNT_WORDS,
    LABEL_POOL,
    NAME_POOL,
    NUMBER_WORDS,
    fold,
)
from psicotest.spec import CheckResult, Item, Turn, canonical_json


class TestCheckersCommon(unittest.TestCase):
    def test_registry_keys(self):
        self.assertEqual(
            sorted(CHECKERS),
            [
                "AMB",
                "AMBC",
                "AMBR",
                "AR",
                "AR2",
                "CNT",
                "CSP",
                "ERR",
                "FPRE",
                "IC",
                "LOG",
                "NOOP",
                "PC",
                "PR",
                "RCL",
                "SETUP",
                "ST",
                "SYP",
            ],
        )

    def test_dispatch_key(self):
        turns = item_fixtures.order_a_turns()
        self.assertEqual(dispatch_key(turns[0]), "SETUP")
        self.assertEqual(dispatch_key(turns[7]), "AMB")
        self.assertEqual(dispatch_key(turns[8]), "AMBR")
        self.assertEqual(dispatch_key(turns[29]), "RCL")
        self.assertEqual(dispatch_key(turns[1]), "ST")
        self.assertEqual(dispatch_key(turns[14]), "AMBC")
        bad_kind = dataclasses.replace(turns[1], kind="x")
        with self.assertRaises(ValueError):
            dispatch_key(bad_kind)
        no_item = item_fixtures.turn_of(None, turn=2, kind="item")
        with self.assertRaises(ValueError):
            dispatch_key(no_item)
        no_item_reply = item_fixtures.turn_of(None, turn=9, kind="amb_reply")
        with self.assertRaises(ValueError):
            dispatch_key(no_item_reply)
        no_item_recall = item_fixtures.turn_of(None, turn=30, kind="recall", rules=("R1", "R3"))
        with self.assertRaises(ValueError):
            dispatch_key(no_item_recall)
        rcl_item = item_fixtures.turn_of(item_fixtures.RCL, turn=2, kind="item")
        with self.assertRaises(ValueError):
            dispatch_key(rcl_item)

    def test_check_turn_matches_checker(self):
        turns = item_fixtures.order_a_turns()
        for t in turns:
            ans = fakes.oracle_answer(t)
            a = check_turn(t, ans.content, ans.finish_reason, ans.reasoning_content)
            b = CHECKERS[dispatch_key(t)](
                ans.content, ans.finish_reason, ans.reasoning_content, t.item
            )
            self.assertEqual(a, b)

    def test_schema_errors(self):
        ar = item_fixtures.AR
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"]("ANSWER: 1", "stop", None, item_fixtures.make_item("AR", {}, {}))
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"](
                "ANSWER: 1", "stop", None, item_fixtures.make_item("AR", {"value": True}, {})
            )
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"](
                "ANSWER: 1",
                "stop",
                None,
                item_fixtures.make_item("AR", {"value": Decimal("NaN")}, {}),
            )
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"](
                "ANSWER: 1",
                "stop",
                None,
                item_fixtures.make_item("AR", {"value": Fraction(1, 2)}, {}),
            )
        with self.assertRaises(ItemSchemaError):
            CHECKERS["CNT"]("ANSWER: 17", "stop", None, ar)
        bad_kind = dataclasses.replace(ar, answer_kind="num")
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"]("ANSWER: 1", "stop", None, bad_kind)
        bad_cap = dataclasses.replace(ar, capability=False)
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"]("ANSWER: 1", "stop", None, bad_cap)
        with self.assertRaises(TypeError):
            CHECKERS["AR"]("ANSWER: 1", "stop", None, "x")
        self.assertEqual(CHECKERS["SETUP"]("ANSWER: OK", "stop", None, None).outcome, "OK")

    def test_make_result(self):
        r = make_result("OK", 1, {"R2_OK", "MULTI", "LEAK"}, "")
        self.assertEqual(r.flags, ("MULTI", "LEAK", "R2_OK"))
        self.assertEqual(make_result("CLAR_OK", None, (), "").score, 1)
        self.assertEqual(make_result("WRONG", None, (), "").score, 0)
        self.assertEqual(make_result("RCL", {}, (), "", score=2).score, 2)
        with self.assertRaises(ValueError):
            make_result("FOO", None, (), "")
        with self.assertRaises(ValueError):
            make_result("OK", None, {"X"}, "")
        with self.assertRaises(ValueError):
            make_result("RCL", {}, (), "")
        with self.assertRaises(ValueError):
            make_result("OK", None, (), "", score=1)

    def test_generic_synonym_valor(self):
        item = item_fixtures.make_item("AMB", {"value": 45}, {"synonyms": ["value"]})
        r = CHECKERS["AMB"]("CLARIFICATION: value?", "stop", None, item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "generic_synonym")

    def test_setup_ack(self):
        self.assertEqual(CHECKERS["SETUP"]("ANSWER: OK", "stop", None, None).outcome, "OK")
        self.assertEqual(CHECKERS["SETUP"]("ANSWER: ok.", "stop", None, None).outcome, "OK")
        self.assertEqual(
            CHECKERS["SETUP"]("ANSWER: understood", "stop", None, None).outcome,
            "WRONG",
        )
        self.assertEqual(CHECKERS["SETUP"]("", "stop", None, None).outcome, "NOANS")
        self.assertNotIn("R2_OK", CHECKERS["SETUP"]("ANSWER: OK", "stop", None, None).flags)
        self.assertNotIn("R2_FAIL", CHECKERS["SETUP"]("ANSWER: OK", "stop", None, None).flags)

    def test_num_equal(self):
        self.assertEqual(num_equal(Decimal("42.0"), 42), (True, frozenset({"FMT"})))
        self.assertEqual(num_equal(Decimal("12.350"), Decimal("12.35")), (True, frozenset()))
        self.assertEqual(num_equal(Decimal("12.345"), Decimal("12.35")), (False, frozenset()))

    def test_results_serializable(self):
        turns = item_fixtures.order_a_turns()
        for persona in fakes.PERSONAS:
            if persona == "auth_reject":
                continue
            server = fakes.FakeServer(persona, turns)
            upto = 11 if persona == "crasher" else 30
            for turn, status, resp in test_fakes_smoke.drive(server, turns, upto=upto):
                self.assertEqual(status, 200)
                result, rules = test_fakes_smoke.score(turn, resp)
                canonical_json(result)
                canonical_json(rules)

    def test_lexicon_tables(self):
        self.assertEqual(
            (
                len(NAME_POOL),
                len(LABEL_POOL),
                len(ANIMAL_WORDS),
                len(ANIMAL_STOP_WORDS),
                len(CNT_WORDS),
            ),
            (40, 16, 84, 20, 320),
        )
        self.assertEqual(len(set(CNT_WORDS)), 320)
        self.assertTrue(all(re.fullmatch(r"[A-Z][a-z]{2,7}", name) for name in NAME_POOL))
        self.assertTrue(all(re.fullmatch(r"[A-Z][A-Z0-9]?", label) for label in LABEL_POOL))
        self.assertTrue(
            all(re.fullmatch(r"[a-z]+", animal) for animal in ANIMAL_WORDS + ANIMAL_STOP_WORDS)
        )
        self.assertTrue(all(re.fullmatch(r"[a-z]{3,10}", word) for word in CNT_WORDS))
        self.assertEqual(tuple(sorted(NAME_POOL)), NAME_POOL)
        self.assertEqual(tuple(sorted(ANIMAL_WORDS)), ANIMAL_WORDS)
        self.assertEqual(tuple(sorted(ANIMAL_STOP_WORDS)), ANIMAL_STOP_WORDS)
        self.assertEqual({name[0] for name in NAME_POOL}, set("ABCDEFGHIJKLMNOPRSTV"))
        self.assertTrue(
            all(
                sum(name.startswith(initial) for name in NAME_POOL) == 2
                for initial in "ABCDEFGHIJKLMNOPRSTV"
            )
        )
        tables = [
            {fold(value) for value in NAME_POOL},
            {fold(value) for value in ANIMAL_WORDS},
            {fold(value) for value in ANIMAL_STOP_WORDS},
            {fold(value) for value in CNT_WORDS},
            {fold(value) for value in NUMBER_WORDS},
            {fold(value) for value in ROLE_WORDS},
        ]
        self.assertTrue(
            all(not (tables[i] & tables[j]) for i in range(len(tables)) for j in range(i))
        )
        self.assertTrue(
            all(
                not (set(singular_candidates(word)) & (set(ANIMAL_WORDS) | set(ANIMAL_STOP_WORDS)))
                for word in CNT_WORDS + NAME_POOL
            )
        )
        self.assertTrue({"sheep", "cat", "mouse", "fish", "goat"} <= set(ANIMAL_WORDS))

    def test_sources_ascii_only(self):
        root = Path(__file__).resolve().parents[1]
        paths = sorted((root / "src/psicotest").rglob("*.py")) + sorted(
            (root / "tests").rglob("*.py")
        )
        for path in paths:
            self.assertLess(max(path.read_bytes(), default=0), 0x80, path)

    def test_no_v1_surface_tokens(self):
        root = Path(__file__).resolve().parents[1]
        rx = re.compile(
            r"(?i)\b(?:respuesta|aclaraci|prompt_es|format_es|caballer|bribon|espia|"
            r"oveja|raton|enunciado|corrijo|turno\b|caja\b|paso\b|valor\b|gato\b|pez\b)"
        )
        paths = sorted((root / "src/psicotest").rglob("*.py")) + sorted(
            (root / "tests").rglob("*.py")
        )
        for path in paths:
            if path.name != "test_checkers_common.py":
                self.assertIsNone(rx.search(path.read_text("ascii")), path)

    def test_battery_version_v2(self):
        self.assertEqual(item_fixtures.make_item("AR", {"value": 1}, {}).battery_version, "v2")
        root = Path(__file__).resolve().parents[1]
        for path in (root / "src/psicotest").rglob("*.py"):
            self.assertNotIn(b'"v1"', path.read_bytes())
            self.assertNotIn(b"'v1'", path.read_bytes())

    def test_prompt_field_renamed(self):
        self.assertEqual([f.name for f in dataclasses.fields(Item)].index("prompt_en"), 11)
        self.assertEqual([f.name for f in dataclasses.fields(Turn)].index("prompt_en"), 3)
        self.assertNotIn("prompt_es", [f.name for f in dataclasses.fields(Item)])
        self.assertNotIn("prompt_es", [f.name for f in dataclasses.fields(Turn)])


if __name__ == "__main__":
    unittest.main()
