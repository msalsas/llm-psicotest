import ast
import unittest
from pathlib import Path

import _bootstrap

from psicotest.rng import Rng

ROOT = Path(__file__).resolve().parents[1]

BANNED_MODULES = ("random", "uuid", "secrets")
BANNED_FROM_IMPORTS = {
    ("time", "time"),
    ("time", "time_ns"),
    ("os", "urandom"),
    ("os", "getrandom"),
}
BANNED_ATTRIBUTES = {
    ("time", "time"),
    ("time", "time_ns"),
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("date", "today"),
    ("os", "urandom"),
    ("os", "getrandom"),
}
BANNED_NAMES = {"hash", "id", "float"}


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        parts.reverse()
        return parts
    return None


def _is_banned_module(name):
    return any(name == m or name.startswith(m + ".") for m in BANNED_MODULES)


def _is_set_iteration(node):
    if isinstance(node, (ast.Set, ast.SetComp)):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("set", "frozenset")
    )


def find_violations(source, filename="<s>"):
    tree = ast.parse(source)
    violations = []

    def add(node, reason):
        violations.append(f"{filename}:{node.lineno}: {reason}")

    def check_iter(node):
        if _is_set_iteration(node):
            add(node, "unsorted set iteration")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_banned_module(alias.name):
                    add(node, f"banned import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module is not None:
                if _is_banned_module(node.module):
                    add(node, f"banned import {node.module}")
                for alias in node.names:
                    if (node.module, alias.name) in BANNED_FROM_IMPORTS:
                        add(node, f"banned from-import {node.module}.{alias.name}")
        elif isinstance(node, ast.Attribute):
            parts = _dotted(node)
            if (
                parts is not None
                and len(parts) >= 2
                and (parts[-2], parts[-1]) in BANNED_ATTRIBUTES
            ):
                add(node, f"banned attribute {'.'.join(parts)}")
        elif isinstance(node, ast.Name):
            if node.id in BANNED_NAMES:
                add(node, f"banned name {node.id}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, (float, complex)):
            add(node, "float literal")
        if isinstance(node, ast.For):
            check_iter(node.iter)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            for comp in node.generators:
                check_iter(comp.iter)
    return sorted(violations)


def _scan_paths():
    paths = []
    for name in ("rng.py", "spec.py", "interview.py"):
        p = ROOT / "src" / "psicotest" / name
        if p.exists():
            paths.append(p)
    for sub in ("generators", "checkers"):
        d = ROOT / "src" / "psicotest" / sub
        if d.exists():
            paths.extend(sorted(d.rglob("*.py")))
    return sorted(paths)


class TestBannedConstructs(unittest.TestCase):
    def test_no_banned_constructs(self):
        paths = _scan_paths()
        self.assertIn(ROOT / "src" / "psicotest" / "rng.py", paths)
        self.assertIn(ROOT / "src" / "psicotest" / "spec.py", paths)
        self.assertIn(ROOT / "src" / "psicotest" / "checkers" / "extract.py", paths)
        self.assertIn(ROOT / "src" / "psicotest" / "checkers" / "rules.py", paths)
        self.assertIn(ROOT / "src" / "psicotest" / "generators" / "core.py", paths)
        self.assertIn(ROOT / "src" / "psicotest" / "generators" / "csp_perm.py", paths)
        all_violations = []
        for p in paths:
            all_violations.extend(find_violations(p.read_text("utf-8"), str(p)))
        self.assertEqual(all_violations, [])

    def test_detector_flags_samples(self):
        samples = [
            "import random",
            "from random import choice",
            "import uuid",
            "import secrets",
            "x = hash('a')",
            "y = id(x)",
            "z = float('1')",
            "w = 1.5",
            "import time\nt = time.time()",
            "from time import time",
            "import datetime\nd = datetime.datetime.now()",
            "import os\nb = os.urandom(8)",
            "for x in {1, 2}:\n    pass",
            "a = [x for x in set(b)]",
            "for x in frozenset(b):\n    pass",
        ]
        for s in samples:
            with self.subTest(s=s):
                self.assertEqual(len(find_violations(s)), 1)

    def test_detector_allows_clean_sample(self):
        source = (
            "from fractions import Fraction\n"
            "for k in sorted(set(d)):\n"
            "    q = Fraction(1, 3)\n"
            "n = int('5')"
        )
        self.assertEqual(find_violations(source), [])


if __name__ == "__main__":
    unittest.main()
