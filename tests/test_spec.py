import dataclasses
import enum
import unittest
from decimal import Decimal
from fractions import Fraction

import _bootstrap

from psicotest.rng import Rng, derive_seed
from psicotest.spec import (
    CheckResult,
    GenContext,
    GeneratorSpec,
    Item,
    Turn,
    canonical_json,
    item_key,
)

ITEM = Item(
    "v2/S01/10001",
    "v2",
    "S01",
    "ST",
    "gen_state_boxes",
    1,
    {"ops": 30, "boxes": 6},
    "base",
    5,
    7,
    None,
    "Problem A.",
    {"A": 5},
    {},
    "keys",
    True,
)

ITEM_BYTES = (
    b'{"animal":null,"answer_kind":"keys","battery_version":"v2","capability":true,"family":"ST",'
    b'"generator":"gen_state_boxes","generator_version":1,"instance_seed":5,'
    b'"item_id":"v2/S01/10001","key":{"A":5},"knobs":{"boxes":6,"ops":30},'
    b'"meta":{},"prompt_en":"Problem A.","slot":"S01","surface_seed":7,"variant":"base"}'
)


class TestSpec(unittest.TestCase):
    def test_canonical_json_bytes(self):
        obj = {
            "b": [1, Decimal("1.50"), Fraction(-3, 4)],
            "a": "\u00f1",
            "c": None,
            "d": True,
            "e": (2, 3),
            "f": 2**64,
        }
        expected = (
            '{"a":"\u00f1","b":[1,"1.50","-3/4"],"c":null,"d":true,"e":[2,3],'
            '"f":18446744073709551616}'
        ).encode()
        self.assertEqual(canonical_json(obj), expected)

    def test_canonical_json_key_order_unicode(self):
        obj = {"\u00e9": 1, "z": 2, "Z": 3, "n": {"y": 1, "x": 2}}
        expected = '{"Z":3,"n":{"x":2,"y":1},"z":2,"\u00e9":1}'.encode()
        self.assertEqual(canonical_json(obj), expected)

    def test_decimal_fraction_serialization(self):
        obj = [
            Decimal("1.50"),
            Decimal("1E+2"),
            Decimal("-0.00"),
            Fraction(4, 2),
            Fraction(-3, 4),
            Fraction(3),
        ]
        self.assertEqual(canonical_json(obj), b'["1.50","1E+2","-0.00","2/1","-3/4","3/1"]')

    def test_canonical_json_rejects(self):
        for bad in (1.5, {1, 2}, frozenset(), {1: "a"}, b"x", Rng(1)):
            with self.assertRaises(TypeError):
                canonical_json(bad)
        with self.assertRaises(TypeError):
            canonical_json(GenContext("base", None, Rng(1)))
        for bad in (Decimal("NaN"), Decimal("Infinity")):
            with self.assertRaises(ValueError):
                canonical_json(bad)

    def test_dataclass_serialization(self):
        self.assertEqual(
            canonical_json(CheckResult("OK", 1, Decimal("12.35"), ("R1_OK", "R2_OK"), "")),
            b'{"detail":"","flags":["R1_OK","R2_OK"],"outcome":"OK","score":1,"value":"12.35"}',
        )
        self.assertEqual(
            canonical_json(Turn(2, "item", "S01", "x", None, ("R1", "R2"), False)),
            b'{"item":null,"kind":"item","prompt_en":"x","r3_trigger":false,'
            b'"rules_active":["R1","R2"],"slot":"S01","turn":2}',
        )
        self.assertEqual(canonical_json(ITEM), ITEM_BYTES)

    def test_dataclasses_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ITEM.slot = "S02"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            GeneratorSpec("gen_x", 1, "ST").version = 2

    def test_item_key_format(self):
        self.assertEqual(item_key("gen_state_boxes", 1, 42, "base"), "gen_state_boxes@1/42/base")
        self.assertEqual(item_key("gen_gsm_noop", 3, 0, "clean"), "gen_gsm_noop@3/0/clean")
        self.assertEqual(
            item_key("gen_state_boxes", 1, 42, "base", "sheep"),
            "gen_state_boxes@1/42/base/animal=sheep",
        )

    def test_item_key_rejects(self):
        cases = [
            ("Gen", 1, 1, "base"),
            ("gen_x", 0, 1, "base"),
            ("gen_x", True, 1, "base"),
            ("gen_x", 1, -1, "base"),
            ("gen_x", 1, True, "base"),
            ("gen_x", 1, 1, "mirror"),
            ("gen_x", 1, 1, "base", "Sheep"),
            ("gen_x", 1, 1, "base", ""),
        ]
        for case in cases:
            with self.assertRaises(ValueError):
                item_key(*case)

    def test_generator_spec_validation(self):
        spec = GeneratorSpec("gen_gsm_noop", 1, "NOOP", ("base", "clean"))
        self.assertEqual(spec.variants, ("base", "clean"))
        self.assertEqual(GeneratorSpec("gen_gsm_noop", 1, "NOOP").variants, ("base",))
        bad = [
            ("GenX", 1, "ST"),
            ("gen_x", 0, "ST"),
            ("gen_x", True, "ST"),
            ("gen_x", 1, "st"),
            ("gen_x", 1, "ST", ()),
            ("gen_x", 1, "ST", ("clean", "base")),
            ("gen_x", 1, "ST", ("base", "base")),
            ("gen_x", 1, "ST", ("base", "mirror")),
            ("gen_x", 1, "ST", ["base"]),
        ]
        for args in bad:
            with self.assertRaises(ValueError):
                GeneratorSpec(*args)

    def test_generator_spec_key(self):
        spec = GeneratorSpec("gen_gsm_noop", 2, "NOOP", ("base", "clean"))
        self.assertEqual(spec.key(5, "clean"), "gen_gsm_noop@2/5/clean")
        self.assertEqual(spec.key(5, animal="sheep"), "gen_gsm_noop@2/5/base/animal=sheep")
        with self.assertRaises(ValueError):
            spec.key(5, "relabel")

    def test_derive_seed_subclass_intenum(self):
        class Weird(int):
            def __repr__(self):
                return "WEIRD"

        class Slot(enum.IntEnum):
            ONE = 1

        self.assertEqual(derive_seed(Weird(5)), derive_seed(5))
        self.assertEqual(derive_seed(Slot.ONE), derive_seed(1))


if __name__ == "__main__":
    unittest.main()
