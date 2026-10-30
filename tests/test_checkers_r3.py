import dataclasses
import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import check_rules
from psicotest.checkers.rules import singular_candidates


class TestCheckersR3(unittest.TestCase):
    def setUp(self):
        self.t17 = item_fixtures.turn_of(
            dataclasses.replace(item_fixtures.ST, animal="oveja"),
            turn=17,
            rules=("R1", "R2", "R3"),
            trigger=True,
        )
        self.t18 = dataclasses.replace(
            self.t17,
            turn=18,
            r3_trigger=False,
            item=dataclasses.replace(self.t17.item, animal=None),
        )

    def test_r3_case1(self):
        out = check_rules("ANIMAL: ovejas\nRESPUESTA: A=5; C=2", self.t17)
        self.assertEqual(out, {"R1": "R1_OK", "R2": "R2_OK", "R3": "R3_HIT", "R3_NOTE": "FMT"})

    def test_r3_case2(self):
        out = check_rules("RESPUESTA: A=5; C=2\nANIMAL: oveja", self.t17)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "NOT_ADJACENT")
        self.assertEqual(out["R1"], "R1_FAIL")

    def test_r3_case3(self):
        out = check_rules("ANIMAL: oveja\nRESPUESTA: A=5; C=2", self.t18)
        self.assertEqual(out["R3"], "R3_FALSE")

    def test_r3_clean_and_miss(self):
        out = check_rules("RESPUESTA: A=5; C=2", self.t18)
        self.assertEqual(out["R3"], "R3_CLEAN")
        self.assertEqual(check_rules("RESPUESTA: A=5; C=2", self.t17)["R3"], "R3_MISS")
        out = check_rules("ANIMAL: vaca\nRESPUESTA: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_MISS")
        self.assertEqual(out["R3_NOTE"], "WRONG_NOUN")
        out = check_rules("ANIMAL: dos ovejas\nRESPUESTA: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_MISS")
        self.assertEqual(out["R3_NOTE"], "BAD_VALUE")

    def test_r3_article_multi(self):
        out = check_rules("ANIMAL: gato\nANIMAL: la oveja\nRESPUESTA: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT;MULTI_ANIMAL")

    def test_r3_plural_article_note(self):
        out = check_rules("ANIMAL: las ovejas\nRESPUESTA: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT")

    def test_r3_multi_miss(self):
        out = check_rules("ANIMAL: vaca\nANIMAL: otra\nRESPUESTA: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_MISS")
        self.assertEqual(out["R3_NOTE"], "MULTI_ANIMAL;WRONG_NOUN")

    def test_singular_candidates(self):
        self.assertIn("oveja", singular_candidates("Ovejas"))
        self.assertIn("pez", singular_candidates("peces"))
        self.assertIn("leon", singular_candidates("leones"))
        self.assertIn("buey", singular_candidates("bueyes"))
        self.assertIn("nandu", singular_candidates("ñandúes"))
        self.assertNotIn("oso", singular_candidates("osas"))
        turn = item_fixtures.turn_of(
            dataclasses.replace(item_fixtures.ST, animal="ratón"),
            turn=17,
            rules=("R1", "R2", "R3"),
            trigger=True,
        )
        out = check_rules("ANIMAL: ratones\nRESPUESTA: A=5; C=2", turn)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT")

    def test_r3_validation(self):
        no_r3 = item_fixtures.turn_of(
            dataclasses.replace(item_fixtures.ST, animal="oveja"),
            turn=17,
            rules=("R1", "R2"),
            trigger=True,
        )
        with self.assertRaises(ValueError):
            check_rules("ANIMAL: oveja\nRESPUESTA: A=5; C=2", no_r3)
        no_animal = item_fixtures.turn_of(
            item_fixtures.ST, turn=17, rules=("R1", "R2", "R3"), trigger=True
        )
        with self.assertRaises(ValueError):
            check_rules("ANIMAL: oveja\nRESPUESTA: A=5; C=2", no_animal)
        with self.assertRaises(TypeError):
            check_rules("x", None)


if __name__ == "__main__":
    unittest.main()
