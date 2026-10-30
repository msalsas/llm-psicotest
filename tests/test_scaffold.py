import unittest

import _bootstrap

import psicotest.cli


class TestScaffold(unittest.TestCase):
    def test_main_exits_zero(self):
        self.assertEqual(psicotest.cli.main([]), 0)


if __name__ == "__main__":
    unittest.main()
