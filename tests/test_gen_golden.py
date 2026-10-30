import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap

from psicotest.rng import Rng

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("gen_golden", ROOT / "tools/gen_golden.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class TestGenGolden(unittest.TestCase):
    def test_golden_file_matches_tool(self):
        self.assertEqual(
            mod.render(mod.build_rng_golden()),
            (ROOT / "tests/golden/rng.json").read_bytes(),
        )

    def test_golden_file_layout(self):
        raw = (ROOT / "tests/golden/rng.json").read_bytes()
        data = json.loads(raw)
        self.assertEqual(
            sorted(data),
            [
                "below7_seed42",
                "chi2_below7_seed7_n70000",
                "counts_below7_seed7_n70000",
                "derive_seed",
                "fork_surface_seed42",
                "next_u64",
                "sample100_5_seed42",
                "schema",
                "shuffle10_seed42",
            ],
        )
        self.assertEqual(data["schema"], 1)
        self.assertEqual(len(data["below7_seed42"]), 16)
        self.assertEqual(len(data["counts_below7_seed7_n70000"]), 7)
        self.assertEqual(len(data["derive_seed"]), 7)
        self.assertEqual(len(data["fork_surface_seed42"]), 4)
        self.assertEqual(len(data["sample100_5_seed42"]), 5)
        self.assertEqual(len(data["shuffle10_seed42"]), 10)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(b"\r", raw)

    def test_check_and_write_modes(self):
        self.assertEqual(mod.main(["--check"]), 0)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "rng.json"
            self.assertEqual(mod.main(["--check", "--path", str(p)]), 1)
            self.assertEqual(mod.main(["--write", "--path", str(p)]), 0)
            self.assertEqual(p.read_bytes(), mod.render(mod.build_rng_golden()))
            self.assertEqual(mod.main(["--write", "--path", str(p)]), 0)
            p.write_bytes(b"{}\n")
            self.assertEqual(mod.main(["--path", str(p)]), 1)
            self.assertEqual(mod.main(["--write", "--path", str(p)]), 1)
            self.assertEqual(p.read_bytes(), b"{}\n")
            self.assertEqual(mod.main(["--write", "--force", "--path", str(p)]), 0)
            self.assertEqual(p.read_bytes(), mod.render(mod.build_rng_golden()))


if __name__ == "__main__":
    unittest.main()
