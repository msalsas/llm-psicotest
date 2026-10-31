import hashlib
import json
import unittest
from fractions import Fraction
from pathlib import Path

import _bootstrap

from psicotest.rng import MASK64, Rng, derive_item_seed, derive_seed, splitmix64

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "tests/golden/rng.json").read_text("utf-8"))
RNG_JSON_SHA256 = "bdbffbc8a18000126af26594309e91a8aaa32ca73719f8041c5f7cfbcfc391f0"

PIN_SEED1_FIRST = 0x910A2DEC89025CC1
PIN_SEEDMAX_FIRST = 0xE4D971771B652C20
PIN_BELOW7 = [5, 5, 0, 2, 6, 4, 2, 6, 6, 5, 5, 6, 1, 4, 0, 5]
PIN_SHUFFLE10 = [0, 9, 5, 8, 6, 4, 7, 2, 1, 3]
PIN_SAMPLE5 = [13, 83, 86, 9, 2]
PIN_FORK4 = [17187392296015359549, 15975406728688652968, 15124960599191300858, 1446099805371588969]
PIN_COUNTS7 = [9989, 10068, 9957, 9955, 9948, 9901, 10182]
PIN_CHI2 = 5.424800


class TestRng(unittest.TestCase):
    def test_splitmix64_function(self):
        self.assertEqual(splitmix64(0), (0x9E3779B97F4A7C15, 0xE220A8397B1DCDAF))
        state = 0
        outputs = []
        for _ in range(4):
            state, out = splitmix64(state)
            outputs.append(out)
        self.assertEqual(
            outputs,
            [
                0xE220A8397B1DCDAF,
                0x6E789E6AA1B965F4,
                0x06C45D188009454F,
                0xF88BB8A8724C81EC,
            ],
        )
        with self.assertRaises(ValueError):
            splitmix64(-1)
        with self.assertRaises(ValueError):
            splitmix64(2**64)
        with self.assertRaises(TypeError):
            splitmix64(True)

    def test_splitmix64_golden(self):
        self.assertEqual(set(GOLDEN["next_u64"]), {"0", "1", "18446744073709551615"})
        for key in ("0", "1", "18446744073709551615"):
            rng = Rng(int(key))
            outs = [rng.next_u64() for _ in range(16)]
            self.assertEqual(outs, GOLDEN["next_u64"][key])
            self.assertEqual(len(GOLDEN["next_u64"][key]), 16)
        self.assertEqual(
            GOLDEN["next_u64"]["0"][:4],
            [
                0xE220A8397B1DCDAF,
                0x6E789E6AA1B965F4,
                0x06C45D188009454F,
                0xF88BB8A8724C81EC,
            ],
        )
        self.assertEqual(GOLDEN["next_u64"]["1"][0], PIN_SEED1_FIRST)
        self.assertEqual(
            GOLDEN["next_u64"]["18446744073709551615"][0],
            PIN_SEEDMAX_FIRST,
        )

    def test_seed_normalization(self):
        a = Rng(2**64)
        b = Rng(0)
        self.assertEqual(
            [a.next_u64() for _ in range(3)],
            [b.next_u64() for _ in range(3)],
        )
        a = Rng(-1)
        b = Rng(2**64 - 1)
        self.assertEqual(
            [a.next_u64() for _ in range(3)],
            [b.next_u64() for _ in range(3)],
        )
        with self.assertRaises(TypeError):
            Rng(True)
        with self.assertRaises(TypeError):
            Rng("1")

    def test_below_rejection_unbiased(self):
        rng = Rng(7)
        counts = [0] * 7
        for _ in range(70000):
            counts[rng.below(7)] += 1
        self.assertEqual(counts, GOLDEN["counts_below7_seed7_n70000"])
        self.assertEqual(counts, PIN_COUNTS7)
        self.assertEqual(sum(counts), 70000)
        for c in counts:
            self.assertTrue(9500 <= c <= 10500)
        chi2 = Fraction(sum((c - 10000) ** 2 for c in counts), 10000)
        self.assertEqual(
            f"{chi2.numerator}/{chi2.denominator}",
            GOLDEN["chi2_below7_seed7_n70000"],
        )
        self.assertLess(chi2, Fraction(22458, 1000))
        self.assertAlmostEqual(chi2.numerator / chi2.denominator, PIN_CHI2, places=6)

    def test_below_rejection_path(self):
        class Scripted(Rng):
            def __init__(self, script):
                super().__init__(0)
                self.script = list(script)

            def next_u64(self):
                return self.script.pop(0)

        for bad in (True, 1.0, "5"):
            with self.assertRaises(TypeError):
                Rng(1).below(bad)
        for bad in (0, 2**64 + 1, 10**30):
            with self.assertRaises(ValueError):
                Rng(1).below(bad)

        s = Scripted([MASK64, 5])
        self.assertEqual(s.below(3), 2)
        self.assertEqual(s.script, [])

        s = Scripted([2**64 - 2, 2**64 - 1, 13])
        self.assertEqual(s.below(7), 6)
        self.assertEqual(s.script, [])

        s = Scripted([MASK64])
        self.assertEqual(s.below(8), 7)
        self.assertEqual(s.script, [])

        s = Scripted([13])
        self.assertEqual(s.below(2**64), 13)
        self.assertEqual(s.script, [])

    def test_below_rejects_zero(self):
        with self.assertRaises(ValueError):
            Rng(1).below(0)
        with self.assertRaises(ValueError):
            Rng(1).below(-1)

    def test_below_n1_consumes_one_draw(self):
        rng = Rng(42)
        self.assertEqual(rng.below(1), 0)
        fresh = Rng(42)
        fresh.next_u64()
        golden_second_42 = fresh.next_u64()
        self.assertEqual(rng.next_u64(), golden_second_42)

    def test_below_golden(self):
        rng = Rng(42)
        vals = [rng.below(7) for _ in range(16)]
        self.assertEqual(vals, GOLDEN["below7_seed42"])
        self.assertEqual(vals, PIN_BELOW7)
        for v in vals:
            self.assertIn(v, range(7))

    def test_shuffle_golden(self):
        lst = list(range(10))
        Rng(42).shuffle(lst)
        self.assertEqual(lst, GOLDEN["shuffle10_seed42"])
        self.assertEqual(lst, PIN_SHUFFLE10)
        self.assertEqual(sorted(lst), list(range(10)))
        rng = Rng(42)
        rng.shuffle([])
        rng.shuffle([9])
        self.assertEqual(rng.next_u64(), Rng(42).next_u64())

    def test_sample_golden(self):
        out = Rng(42).sample(range(100), 5)
        self.assertEqual(out, GOLDEN["sample100_5_seed42"])
        self.assertEqual(out, PIN_SAMPLE5)
        self.assertEqual(len(set(out)), 5)
        for v in out:
            self.assertIn(v, range(100))
        rng = Rng(42)
        self.assertEqual(rng.sample(range(5), 0), [])
        self.assertEqual(rng.next_u64(), Rng(42).next_u64())
        seq = [1, 2, 3]
        Rng(42).sample(seq, 2)
        self.assertEqual(seq, [1, 2, 3])
        with self.assertRaises(ValueError):
            Rng(1).sample([1, 2], 3)
        with self.assertRaises(ValueError):
            Rng(1).sample([1, 2], -1)

    def test_randint_and_choice(self):
        self.assertEqual(Rng(42).randint(5, 11), 5 + Rng(42).below(7))
        self.assertEqual(Rng(1).randint(3, 3), 3)
        with self.assertRaises(ValueError):
            Rng(1).randint(4, 3)
        self.assertEqual(
            Rng(42).choice(["a", "b", "c"]),
            ["a", "b", "c"][Rng(42).below(3)],
        )
        with self.assertRaises(ValueError):
            Rng(1).choice([])

    def test_fork_independent(self):
        fresh = Rng(42)
        first = fresh.next_u64()
        second = fresh.next_u64()
        p = Rng(42)
        c = p.fork("surface")
        self.assertEqual(c.next_u64(), Rng(derive_seed(first, "surface")).next_u64())
        self.assertEqual(p.next_u64(), second)
        fresh_fork = Rng(42).fork("surface")
        fork4 = [fresh_fork.next_u64() for _ in range(4)]
        self.assertEqual(fork4, GOLDEN["fork_surface_seed42"])
        self.assertEqual(fork4, PIN_FORK4)
        self.assertNotEqual(Rng(42).fork("a").next_u64(), Rng(42).fork("b").next_u64())
        p2 = Rng(42)
        c2 = p2.fork("surface")
        child_vals = {c2.next_u64() for _ in range(16)}
        parent_vals = {p2.next_u64() for _ in range(16)}
        self.assertEqual(child_vals & parent_vals, set())
        with self.assertRaises(TypeError):
            Rng(1).fork(1)

    def test_derive_seed_golden(self):
        self.assertEqual(derive_seed(""), 0xE3B0C44298FC1C14)
        self.assertEqual(derive_seed("abc"), 0xBA7816BF8F01CFEA)
        self.assertEqual(derive_seed("a"), 0xCA978112CA1BBDCA)
        self.assertEqual(
            derive_seed("psicotest", "v1", "S01", "gen_state_boxes", 1, 10001, "instance"),
            int.from_bytes(
                hashlib.sha256(
                    b"psicotest\x1fv1\x1fS01\x1fgen_state_boxes\x1f1\x1f10001\x1finstance"
                ).digest()[:8],
                "big",
            ),
        )
        self.assertEqual(
            derive_seed("\u00f1and\u00fa", 0),
            int.from_bytes(
                hashlib.sha256("\u00f1and\u00fa\x1f0".encode()).digest()[:8],
                "big",
            ),
        )
        for entry in GOLDEN["derive_seed"]:
            self.assertEqual(derive_seed(*entry["parts"]), entry["value"])
        self.assertEqual(
            [entry["parts"] for entry in GOLDEN["derive_seed"]],
            [
                ["psicotest", "v1", "S01", "gen_state_boxes", 1, 10001, "instance"],
                ["psicotest", "v1", "S01", "gen_state_boxes", 1, 10001, "surface"],
                ["psicotest", "v1", 10001, "A", 17, "animal"],
                ["req", "v1", 10001, "A", 2],
                ["\u00f1and\u00fa", 0],
                [""],
                ["abc"],
            ],
        )
        self.assertEqual(derive_seed(1, 2), derive_seed("1", "2"))
        for entry in GOLDEN["derive_seed"]:
            self.assertLess(entry["value"], 2**64)

    def test_derive_seed_rejects(self):
        with self.assertRaises(ValueError):
            derive_seed()
        with self.assertRaises(ValueError):
            derive_seed("a\x1fb")
        with self.assertRaises(TypeError):
            derive_seed(True)
        with self.assertRaises(TypeError):
            derive_seed(1.0)
        with self.assertRaises(TypeError):
            derive_seed(None)

    def test_derive_item_seed(self):
        self.assertEqual(
            derive_item_seed("v1", "S01", "gen_state_boxes", 1, 10001, "instance"),
            GOLDEN["derive_seed"][0]["value"],
        )
        self.assertEqual(
            derive_item_seed("v1", "S01", "gen_state_boxes", 1, 10001, "surface"),
            GOLDEN["derive_seed"][1]["value"],
        )
        self.assertNotEqual(
            GOLDEN["derive_seed"][0]["value"],
            GOLDEN["derive_seed"][1]["value"],
        )
        with self.assertRaises(ValueError):
            derive_item_seed("v1", "S01", "gen_state_boxes", 1, 10001, "animal")

    def test_rng_golden_file_frozen(self):
        self.assertEqual(
            hashlib.sha256((ROOT / "tests/golden/rng.json").read_bytes()).hexdigest(),
            RNG_JSON_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
