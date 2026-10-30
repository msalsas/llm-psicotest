import dataclasses
import unittest
from decimal import Decimal
from fractions import Fraction

import _bootstrap
import fakes
import item_fixtures
import test_fakes_smoke

from psicotest.checkers import CHECKERS, check_turn, dispatch_key
from psicotest.checkers.common import ItemSchemaError, make_result, num_equal
from psicotest.spec import CheckResult, canonical_json


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
                "LOG",
                "NOOP",
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
            CHECKERS["AR"]("RESPUESTA: 1", "stop", None, item_fixtures.make_item("AR", {}, {}))
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"](
                "RESPUESTA: 1", "stop", None, item_fixtures.make_item("AR", {"value": True}, {})
            )
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"](
                "RESPUESTA: 1",
                "stop",
                None,
                item_fixtures.make_item("AR", {"value": Decimal("NaN")}, {}),
            )
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"](
                "RESPUESTA: 1",
                "stop",
                None,
                item_fixtures.make_item("AR", {"value": Fraction(1, 2)}, {}),
            )
        with self.assertRaises(ItemSchemaError):
            CHECKERS["CNT"]("RESPUESTA: 17", "stop", None, ar)
        bad_kind = dataclasses.replace(ar, answer_kind="num")
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"]("RESPUESTA: 1", "stop", None, bad_kind)
        bad_cap = dataclasses.replace(ar, capability=False)
        with self.assertRaises(ItemSchemaError):
            CHECKERS["AR"]("RESPUESTA: 1", "stop", None, bad_cap)
        with self.assertRaises(TypeError):
            CHECKERS["AR"]("RESPUESTA: 1", "stop", None, "x")
        self.assertEqual(CHECKERS["SETUP"]("RESPUESTA: OK", "stop", None, None).outcome, "OK")

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
        item = item_fixtures.make_item("AMB", {"value": 45}, {"synonyms": ["valor"]})
        r = CHECKERS["AMB"]("ACLARACION: ¿valor?", "stop", None, item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "generic_synonym")

    def test_setup_ack(self):
        self.assertEqual(CHECKERS["SETUP"]("RESPUESTA: OK", "stop", None, None).outcome, "OK")
        self.assertEqual(CHECKERS["SETUP"]("RESPUESTA: ok.", "stop", None, None).outcome, "OK")
        self.assertEqual(CHECKERS["SETUP"]("RESPUESTA: vale", "stop", None, None).outcome, "WRONG")
        self.assertEqual(CHECKERS["SETUP"]("", "stop", None, None).outcome, "NOANS")
        self.assertNotIn("R2_OK", CHECKERS["SETUP"]("RESPUESTA: OK", "stop", None, None).flags)
        self.assertNotIn("R2_FAIL", CHECKERS["SETUP"]("RESPUESTA: OK", "stop", None, None).flags)

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


if __name__ == "__main__":
    unittest.main()
