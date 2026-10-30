import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import check_rules


class TestRules(unittest.TestCase):
    def test_r1_ok(self):
        turn = item_fixtures.turn_of(item_fixtures.ST, turn=2)
        out = check_rules("Calculo.\nRESPUESTA: A=5; C=2\n", turn)
        self.assertEqual(out["R1"], "R1_OK")
        self.assertEqual(out["R3"], "NA")

    def test_r1_fail_cases(self):
        turn = item_fixtures.turn_of(item_fixtures.ST, turn=2)
        self.assertEqual(
            check_rules("RESPUESTA: A=5; C=2\nRESPUESTA: A=5; C=2", turn)["R1"], "R1_FAIL"
        )
        self.assertEqual(check_rules("RESPUESTA: A=5; C=2\nGracias.", turn)["R1"], "R1_FAIL")
        self.assertEqual(check_rules("Sin respuesta.", turn)["R1"], "R1_FAIL")

    def test_r1_not_active(self):
        turns = item_fixtures.order_a_turns()
        out = check_rules("ACLARACION: ¿Cuál es el dato de precio?", turns[7])
        self.assertEqual(out["R1"], "NA")
        self.assertEqual(out["R2"], "NA")

    def test_trunc_all_na(self):
        turns = item_fixtures.order_a_turns()
        out = check_rules("RESPUESTA: 42", turns[12], "length")
        self.assertEqual(out, {"R1": "NA", "R2": "NA", "R3": "NA", "R3_NOTE": ""})

    def test_r2_from_checker(self):
        turn = item_fixtures.turn_of(item_fixtures.AR, turn=3)
        self.assertEqual(check_rules("RESPUESTA: 4.567.890.123", turn)["R2"], "R2_FAIL")
        self.assertEqual(check_rules("RESPUESTA: 4567890123", turn)["R2"], "R2_OK")
        self.assertEqual(check_rules("nada", turn)["R2"], "NA")
        turns = item_fixtures.order_a_turns()
        self.assertEqual(
            check_rules("RESPUESTA: Ana=3; Bruno=1; Carla=4; Dario=2", turns[4])["R2"], "NA"
        )

    def test_r2_gen_bug_na(self):
        item = item_fixtures.make_item("NOOP", {"value": 42}, {"distractor_answers": [42]})
        turn = item_fixtures.turn_of(item, turn=13, rules=("R1", "R2", "R3"))
        self.assertEqual(check_rules("RESPUESTA: 42", turn)["R2"], "NA")


if __name__ == "__main__":
    unittest.main()
