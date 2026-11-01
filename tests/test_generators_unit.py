import dataclasses
import unittest
from decimal import Decimal
from fractions import Fraction

import _bootstrap

from psicotest import generators
from psicotest.generators import (
    GENERATORS,
    SPECS,
    START_KNOBS,
    authority_hint,
    contains_animal,
    core,
    false_premise,
    gsm_noop,
    make_item,
    problems,
    reply_prompt,
    rules_text,
    text_en,
)
from psicotest.rng import Rng
from psicotest.spec import GenContext, canonical_json

NAMES = [
    "gen_authority_hint",
    "gen_chain_decimal",
    "gen_count_cond",
    "gen_csp_perm",
    "gen_derivable_datum",
    "gen_false_premise",
    "gen_gsm_noop",
    "gen_instr_chain",
    "gen_knights_spy",
    "gen_missing_datum",
    "gen_mult_carry",
    "gen_planted_error",
    "gen_prose_block",
    "gen_prose_consistency",
    "gen_state_boxes",
    "rules_recall",
    "setup_rules",
]
FAMILIES = {
    "gen_state_boxes": ("ST", ("base", "relabel")),
    "gen_mult_carry": ("AR", ("base",)),
    "gen_chain_decimal": ("AR2", ("base",)),
    "gen_gsm_noop": ("NOOP", ("base", "clean", "relabel")),
    "gen_csp_perm": ("CSP", ("base", "relabel")),
    "gen_knights_spy": ("LOG", ("base", "relabel")),
    "gen_count_cond": ("CNT", ("base", "relabel")),
    "gen_planted_error": ("ERR", ("base", "relabel")),
    "gen_false_premise": ("FPRE", ("base",)),
    "gen_authority_hint": ("SYP", ("base", "relabel")),
    "gen_instr_chain": ("IC", ("base",)),
    "gen_missing_datum": ("AMB", ("base", "relabel")),
    "gen_derivable_datum": ("AMBC", ("base", "relabel")),
    "gen_prose_block": ("PR", ("base",)),
    "gen_prose_consistency": ("PC", ("base", "pc1", "pc2")),
    "setup_rules": ("SETUP", ("base",)),
    "rules_recall": ("RCL", ("base",)),
}
RULE_GENS = ("setup_rules", "rules_recall")
CAP_GENS = [g for g in NAMES if g not in RULE_GENS]


def build(generator, seed, variant="base", animal=None):
    return make_item(
        battery="v2",
        slot="UNIT",
        generator=generator,
        knobs=START_KNOBS[generator],
        variant=variant,
        user_seed=seed,
        animal=animal,
    )


class TestGeneratorsUnit(unittest.TestCase):
    def test_registry(self):
        self.assertEqual(sorted(GENERATORS), sorted(NAMES))
        self.assertEqual(len(GENERATORS), 17)
        for name, (family, variants) in FAMILIES.items():
            self.assertEqual(GENERATORS[name][1], 1)
            self.assertEqual(SPECS[name].family, family)
            self.assertEqual(SPECS[name].variants, variants)
            self.assertEqual(START_KNOBS[name], {"level": 0})
        self.assertEqual(generators.__all__, sorted(generators.__all__))
        self.assertEqual(len(generators.__all__), 16)

    def test_signature_and_types(self):
        for name in NAMES:
            fn = GENERATORS[name][0]
            out = fn(Rng(1), START_KNOBS[name], GenContext("base", None, Rng(2)))
            self.assertIsInstance(out, tuple)
            self.assertEqual(len(out), 3)
            prompt, key, meta = out
            self.assertIsInstance(prompt, str)
            self.assertIsInstance(key, dict)
            self.assertIsInstance(meta, dict)
            self.assertIn("instance", meta)
            self.assertIn("realized", meta)

    def test_determinism(self):
        for name in NAMES:
            first = build(name, 1)
            self.assertEqual(canonical_json(first), canonical_json(build(name, 1)))
            second = build(name, 2)
            if name in RULE_GENS:
                self.assertEqual(first.prompt_en, second.prompt_en)
            else:
                self.assertNotEqual(first.prompt_en, second.prompt_en)

    def test_instance_surface_split(self):
        for name in CAP_GENS:
            fn = GENERATORS[name][0]
            knobs = START_KNOBS[name]
            a = fn(Rng(7), knobs, GenContext("base", None, Rng(0)))
            b = fn(Rng(7), knobs, GenContext("base", None, Rng(1)))
            self.assertEqual(a[2]["instance"], b[2]["instance"], msg=name)

    def test_knob_validation(self):
        ctx = GenContext("base", None, Rng(1))
        noop = GENERATORS["gen_gsm_noop"][0]
        bad = (
            {},
            {"level": 3},
            {"level": True},
            {"level": 0, "zzz": 1},
            {"level": 1, "n_distractors": 5},
        )
        for knobs in bad:
            with self.subTest(knobs=knobs), self.assertRaises(ValueError):
                noop(Rng(1), knobs, ctx)
        with self.assertRaises(ValueError):
            GENERATORS["gen_csp_perm"][0](Rng(1), {"level": 0, "n_constraints": 15}, ctx)

    def test_variant_validation(self):
        for variant in ("clean", "relabel"):
            with self.assertRaises(ValueError):
                GENERATORS["gen_mult_carry"][0](
                    Rng(1), {"level": 0}, GenContext(variant, None, Rng(1))
                )
        with self.assertRaises(ValueError):
            GENERATORS["gen_csp_perm"][0](Rng(1), {"level": 0}, GenContext("clean", None, Rng(1)))

    def test_exhausted(self):
        with self.assertRaises(core.GeneratorExhausted):
            core.draw_until("x", Rng(1), lambda r, p: None, {})
        calls = []

        def draw(rng, params):
            calls.append(rng.next_u64())

        with self.assertRaises(core.GeneratorExhausted):
            core.draw_until("x", Rng(1), draw, {})
        self.assertEqual(len(calls), 1000)

    def test_text_en(self):
        self.assertEqual(text_en.join_en([]), "")
        self.assertEqual(text_en.join_en(["Vera"]), "Vera")
        self.assertEqual(text_en.join_en(["Brian", "Irene"]), "Brian and Irene")
        self.assertEqual(text_en.join_en(["Alice", "Brian", "Clara"]), "Alice, Brian and Clara")
        self.assertEqual(text_en.join_en(["1", "8"], "or"), "1 or 8")
        self.assertEqual(text_en.join_en(["seven", "eight"], "or"), "seven or eight")
        self.assertEqual(text_en.plural(1, "marble", "marbles"), "1 marble")
        self.assertEqual(text_en.plural(2, "marble", "marbles"), "2 marbles")
        self.assertEqual(text_en.half_up_2dp(Fraction(12345, 1000)), Decimal("12.35"))
        self.assertEqual(text_en.half_up_2dp(Fraction(1, 3)), Decimal("0.33"))
        self.assertEqual(text_en.fmt_dec(Decimal("12.30")), "12.30")
        self.assertEqual(text_en.num_word(7), "seven")
        self.assertEqual(text_en.num_word(22), "twenty-two")
        with self.assertRaises(ValueError):
            text_en.num_word(100)

    def test_rule_texts(self):
        setup = rules_text.SETUP_TEXT
        for part in (rules_text.R1_TEXT, rules_text.R2_TEXT, rules_text.PROTO_TEXT):
            self.assertIn(part, setup)
        self.assertTrue(setup.endswith("If you have understood, reply `ANSWER: OK`."))
        self.assertEqual(
            rules_text.R3_TEXT,
            "New rule from now on: if the problem mentions an animal, add another line "
            "`ANIMAL: <name of the animal, in the singular>` immediately before the ANSWER line.",
        )
        texts = (
            rules_text.R1_TEXT,
            rules_text.R2_TEXT,
            rules_text.PROTO_TEXT,
            setup,
            rules_text.R3_TEXT,
            rules_text.RCL_TEXT,
        )
        for text in texts:
            self.assertTrue(text.isascii())
            self.assertEqual(contains_animal(text), ())
        ctx = GenContext("base", "cat", Rng(1))
        for fn in (rules_text.setup_rules, rules_text.rules_recall):
            with self.assertRaises(ValueError):
                fn(Rng(1), {"level": 0}, ctx)

    def test_fpre_valid_case4(self):
        self.assertEqual(false_premise.valid(391, 401, 1, 10, "L1"), "not_distinct")
        self.assertIsNone(false_premise.valid(391, 401, 1, 25, "L1"))

    def test_noop_valid_case2(self):
        chain = problems.make_chain([("INIT", 100), ("ADD_GROUPS", 3, 10), ("SUB", 25)])
        inst = gsm_noop.Inst(chain, (("past", 0, 1),))
        self.assertEqual(gsm_noop.valid(inst), "bait_equals_key")

    def test_syp_valid(self):
        ops = [("INIT", 100), ("ADD_GROUPS", 3, 10), ("SUB", 25), ("DIV_EQUAL", 3)]
        chain = problems.make_chain(ops)
        self.assertEqual(chain.running[-1], 35)
        cases = ((35, "hint_equals_key"), (36, "hint_too_close"), (130, "hint_is_intermediate"))
        for hint, token in cases:
            inst = authority_hint.Inst(chain, "skip_step", (1,), Fraction(hint), "H2")
            self.assertEqual(authority_hint.valid(inst), token)

    def test_reply_prompt(self):
        item = build("gen_missing_datum", 1)
        plain = "Missing datum: " + item.meta["datum_en"] + " With this datum, solve the problem."
        self.assertEqual(reply_prompt(item), plain)
        mouse = dataclasses.replace(item, animal="mouse")
        text = reply_prompt(mouse)
        self.assertEqual(contains_animal(text), ("mouse",))
        self.assertEqual(text, reply_prompt(mouse))
        with self.assertRaises(ValueError):
            reply_prompt(build("gen_mult_carry", 1))


if __name__ == "__main__":
    unittest.main()
