import dataclasses
import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import check_rules
from psicotest.checkers.rules import PLURAL_EXCEPTIONS, singular_candidates


class TestCheckersR3(unittest.TestCase):
    def setUp(self):
        self.t17 = item_fixtures.turn_of(
            dataclasses.replace(item_fixtures.ST, animal="goat"),
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
        out = check_rules("ANIMAL: goats\nANSWER: A=5; C=2", self.t17)
        self.assertEqual(out, {"R1": "R1_OK", "R2": "R2_OK", "R3": "R3_HIT", "R3_NOTE": "FMT"})

    def test_r3_case2(self):
        out = check_rules("ANSWER: A=5; C=2\nANIMAL: goat", self.t17)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "NOT_ADJACENT")
        self.assertEqual(out["R1"], "R1_FAIL")

    def test_r3_case3(self):
        out = check_rules("ANIMAL: goat\nANSWER: A=5; C=2", self.t18)
        self.assertEqual(out["R3"], "R3_FALSE")

    def test_r3_clean_and_miss(self):
        out = check_rules("ANSWER: A=5; C=2", self.t18)
        self.assertEqual(out["R3"], "R3_CLEAN")
        self.assertEqual(check_rules("ANSWER: A=5; C=2", self.t17)["R3"], "R3_MISS")
        out = check_rules("ANIMAL: cow\nANSWER: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_MISS")
        self.assertEqual(out["R3_NOTE"], "WRONG_NOUN")
        out = check_rules("ANIMAL: two goats\nANSWER: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_MISS")
        self.assertEqual(out["R3_NOTE"], "BAD_VALUE")

    def test_r3_article_multi(self):
        out = check_rules("ANIMAL: cat\nANIMAL: the goat\nANSWER: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT;MULTI_ANIMAL")

    def test_r3_plural_article_note(self):
        out = check_rules("ANIMAL: the goats\nANSWER: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT")

    def test_r3_multi_miss(self):
        out = check_rules("ANIMAL: cow\nANIMAL: other\nANSWER: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_MISS")
        self.assertEqual(out["R3_NOTE"], "MULTI_ANIMAL;WRONG_NOUN")

    def test_singular_candidates(self):
        self.assertIn("goat", singular_candidates("Goats"))
        self.assertIn("fox", singular_candidates("foxes"))
        self.assertIn("pony", singular_candidates("ponies"))
        self.assertIn("wolf", singular_candidates("wolves"))
        self.assertIn("knife", singular_candidates("knives"))
        self.assertNotIn("fox", singular_candidates("foxen"))
        turn = item_fixtures.turn_of(
            dataclasses.replace(item_fixtures.ST, animal="mouse"),
            turn=17,
            rules=("R1", "R2", "R3"),
            trigger=True,
        )
        out = check_rules("ANIMAL: mice\nANSWER: A=5; C=2", turn)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT")

    def test_r3_validation(self):
        no_r3 = item_fixtures.turn_of(
            dataclasses.replace(item_fixtures.ST, animal="goat"),
            turn=17,
            rules=("R1", "R2"),
            trigger=True,
        )
        with self.assertRaises(ValueError):
            check_rules("ANIMAL: goat\nANSWER: A=5; C=2", no_r3)
        no_animal = item_fixtures.turn_of(
            item_fixtures.ST, turn=17, rules=("R1", "R2", "R3"), trigger=True
        )
        with self.assertRaises(ValueError):
            check_rules("ANIMAL: goat\nANSWER: A=5; C=2", no_animal)
        with self.assertRaises(TypeError):
            check_rules("x", None)

    def test_r3_plural_exceptions(self):
        self.assertEqual(
            PLURAL_EXCEPTIONS,
            {
                "bison": "bison",
                "deer": "deer",
                "feet": "foot",
                "fish": "fish",
                "geese": "goose",
                "lice": "louse",
                "mice": "mouse",
                "moose": "moose",
                "octopi": "octopus",
                "oxen": "ox",
                "salmon": "salmon",
                "sheep": "sheep",
                "teeth": "tooth",
            },
        )
        self.assertEqual(singular_candidates("sheep"), ("sheep",))
        self.assertEqual(singular_candidates("mice"), ("mice", "mouse"))
        self.assertEqual(
            singular_candidates("wolves"),
            ("wolves", "wolve", "wolv", "wolf", "wolfe"),
        )
        self.assertEqual(singular_candidates("ponies"), ("ponies", "ponie", "poni", "pony"))
        sheep = dataclasses.replace(
            self.t17,
            item=dataclasses.replace(self.t17.item, animal="sheep"),
        )
        fish = dataclasses.replace(self.t17, item=dataclasses.replace(self.t17.item, animal="fish"))
        mouse = dataclasses.replace(
            self.t17,
            item=dataclasses.replace(self.t17.item, animal="mouse"),
        )
        out = check_rules("ANIMAL: sheep\nANSWER: A=5; C=2", sheep)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "")
        out = check_rules("ANIMAL: sheeps\nANSWER: A=5; C=2", sheep)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT")
        out = check_rules("ANIMAL: fish\nANSWER: A=5; C=2", fish)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "")
        out = check_rules("ANIMAL: fishes\nANSWER: A=5; C=2", fish)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT")
        out = check_rules("ANIMAL: Mice\nANSWER: A=5; C=2", mouse)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT")

    def test_r3_articles_english(self):
        from psicotest.checkers.text import ARTICLES

        self.assertEqual(ARTICLES, ("the", "a", "an"))
        out = check_rules("ANIMAL: a goat\nANSWER: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT")
        out = check_rules("ANIMAL: an goat\nANSWER: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_HIT")
        self.assertEqual(out["R3_NOTE"], "FMT")
        out = check_rules("ANIMAL: la goat\nANSWER: A=5; C=2", self.t17)
        self.assertEqual(out["R3"], "R3_MISS")
        self.assertEqual(out["R3_NOTE"], "BAD_VALUE")


if __name__ == "__main__":
    unittest.main()
