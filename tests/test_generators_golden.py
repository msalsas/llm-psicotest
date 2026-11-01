import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import _bootstrap

from psicotest.generators import GENERATORS, golden_items
from psicotest.spec import canonical_json

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "tests" / "golden" / "items_v3.json"
STALE = "v3 golden stale: regenerate with tools/gen_golden.py in the version-bump commit"
CODE = (
    "import hashlib, json\n"
    "from psicotest.generators import golden_items\n"
    "from psicotest.spec import canonical_json\n"
    "items = golden_items()\n"
    "print(json.dumps({k: hashlib.sha256(canonical_json(items[k])).hexdigest() "
    "for k in sorted(items)}))\n"
)

_spec = importlib.util.spec_from_file_location("gen_golden", ROOT / "tools" / "gen_golden.py")
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)


def load_golden():
    return json.loads(GOLDEN_PATH.read_text("utf-8"))


def hashes_under(hash_seed):
    env = dict(os.environ, PYTHONHASHSEED=hash_seed, PYTHONPATH=str(ROOT / "src"))
    done = subprocess.run(
        [sys.executable, "-B", "-c", CODE], env=env, capture_output=True, text=True, check=True
    )
    return json.loads(done.stdout)


class TestGeneratorsGolden(unittest.TestCase):
    def test_items_golden(self):
        golden = load_golden()
        for key, item in golden_items().items():
            self.assertEqual(golden[key], hashlib.sha256(canonical_json(item)).hexdigest(), key)

    def test_golden_key_set(self):
        golden = load_golden()
        self.assertEqual(sorted(golden_items()), sorted(golden))
        self.assertEqual(len(golden), 132)

    def test_version_bump_required(self):
        for key in load_golden():
            name, version = key.split("/")[0].split("@")
            self.assertEqual(int(version), GENERATORS[name][1], STALE)
        old = {"gen_x@1/1/base": "aa", "gen_x@1/2/base": "bb"}
        with self.assertRaises(ValueError):
            tool.merge_items(old, {"gen_x@1/1/base": "cc", "gen_x@1/2/base": "bb"})
        bumped = {"gen_x@2/1/base": "cc", "gen_x@2/2/base": "bb"}
        self.assertEqual(tool.merge_items(old, bumped), bumped)
        with self.assertRaises(ValueError):
            tool.merge_items({"gen_a@1/0/base": "x"}, {})
        bumped_a = {"gen_a@2/0/base": "y"}
        self.assertEqual(tool.merge_items({"gen_a@1/0/base": "x"}, bumped_a), bumped_a)

    def test_golden_hashseed_independent(self):
        self.assertEqual(hashes_under("0"), hashes_under("1"))


if __name__ == "__main__":
    unittest.main()
