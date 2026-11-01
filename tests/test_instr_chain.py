import unittest

import _bootstrap
import gen_corpus
import solvers

from psicotest.checkers import check_rules, check_turn
from psicotest.checkers.schema import invariant, validate
from psicotest.generators import make_item
from psicotest.generators.instr_chain import LADDER
from psicotest.spec import Turn, canonical_json


def build_item(level, seed):
    return make_item(
        battery="v4",
        slot="S27",
        generator="gen_instr_chain",
        knobs={"level": level},
        variant="base",
        user_seed=seed,
    )


class TestInstrChain(unittest.TestCase):
    def test_draw_all_levels_valid(self):
        for level in LADDER:
            item = build_item(level, 42)
            self.assertIn("position 1 is the first token", item.prompt_en)
            self.assertEqual(len(item.key["tokens"]), LADDER[level]["token_count"])
            validate(item, "IC")
            self.assertIsNone(invariant(item, "IC"))

    def test_determinism(self):
        for level in LADDER:
            first = canonical_json(build_item(level, 7))
            self.assertEqual(first, canonical_json(build_item(level, 7)))

    def test_solver_checked_10_seeds(self):
        for seed in range(1, 11):
            item = build_item(2, seed)
            instance = item.meta["instance"]
            self.assertEqual(
                solvers.ic_apply(instance["tokens"], instance["ops"]), item.key["tokens"]
            )
        for seed in range(1, 4):
            item = build_item(1, seed)
            instance = item.meta["instance"]
            self.assertEqual(
                solvers.ic_apply(instance["tokens"], instance["ops"]), item.key["tokens"]
            )

    def test_noop_replace_levels(self):
        for level in LADDER:
            for seed in range(1, 26):
                item = build_item(level, seed)
                instance = item.meta["instance"]
                running = list(instance["tokens"])
                n_noop = 0
                for op in instance["ops"]:
                    if op["kind"] == "replace" and op["old"] not in running:
                        n_noop += 1
                    running = solvers.ic_apply(running, [op])
                if level in (1, 2):
                    self.assertGreaterEqual(n_noop, 1)
                else:
                    self.assertEqual(n_noop, 0)

    def test_list_length_constant(self):
        for level in LADDER:
            for seed in range(1, 21):
                item = build_item(level, seed)
                tokens = item.key["tokens"]
                self.assertEqual(len(tokens), LADDER[level]["token_count"])
                for token in tokens:
                    self.assertNotIn(" ", token)
                    self.assertNotIn(",", token)

    def test_checker_roundtrip(self):
        item = build_item(2, 11)
        turn = Turn(12, "item", "S28", item.prompt_en, item, ("R1", "R2"), False)
        tokens = list(item.key["tokens"])
        oracle = "ANSWER: " + ", ".join(tokens)
        result = check_turn(turn, oracle, "stop", None)
        self.assertEqual(result.outcome, "OK")
        self.assertEqual(result.flags, ("R2_OK",))
        rules = check_rules(oracle, turn, "stop")
        self.assertEqual(rules["R1"], "R1_OK")
        self.assertEqual(rules["R2"], "R2_OK")
        swapped = list(tokens)
        swapped[0], swapped[1] = swapped[1], swapped[0]
        result = check_turn(turn, "ANSWER: " + ", ".join(swapped), "stop", None)
        self.assertEqual(result.outcome, "WRONG")
        half = tokens[: len(tokens) // 2]
        result = check_turn(turn, "ANSWER: " + ", ".join(half), "stop", None)
        self.assertNotEqual(result.outcome, "OK")
        result = check_turn(turn, "I cannot say.", "stop", None)
        self.assertEqual(result.outcome, "NOANS")

    def test_surface_hygiene(self):
        for level in LADDER:
            for seed in (1, 2, 3):
                item = build_item(level, seed)
                gen_corpus.check_surface(self, item.prompt_en, item.item_id)


if __name__ == "__main__":
    unittest.main()
