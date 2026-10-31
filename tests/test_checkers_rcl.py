import unittest

import _bootstrap
import fakes
import item_fixtures

from psicotest.checkers import CHECKERS

RCL = item_fixtures.RCL


class TestCheckersRCL(unittest.TestCase):
    def call(self, content):
        return CHECKERS["RCL"](content, "stop", None, RCL)

    def test_rcl_case1(self):
        r = self.call("- be concise\n- the last line is ANSWER: value\nANSWER: 2")
        self.assertEqual(r.outcome, "RCL")
        self.assertEqual(r.score, 1)
        self.assertEqual(r.value, {"PROTO": False, "R1": True, "R2": False, "R3": False})
        self.assertEqual(r.detail, "")

    def test_rcl_case2(self):
        r = self.call("- use a decimal point\nANSWER: 1")
        self.assertEqual(r.value["R2"], True)
        self.assertEqual(r.score, 1)

    def test_rcl_case3(self):
        r = self.call("Mention the animal if one appears.\n- use a decimal point\nANSWER: 1")
        self.assertEqual(r.value["R3"], False)
        self.assertEqual(r.score, 1)

    def test_rcl_oracle_full(self):
        r = self.call(fakes.RCL_ORACLE)
        self.assertEqual(r.score, 3)
        self.assertEqual(r.detail, "bonus")
        self.assertEqual(r.value, {"PROTO": True, "R1": True, "R2": True, "R3": True})

    def test_rcl_numbered(self):
        r = self.call("1. answer at the end\n2) no units\nANSWER: 2")
        self.assertEqual(r.value["R1"], True)
        self.assertEqual(r.value["R2"], True)
        self.assertEqual(r.score, 2)

    def test_rcl_empty(self):
        r = self.call("")
        self.assertEqual(r.outcome, "NOANS")

    def test_rcl_keywords_english(self):
        from psicotest.checkers.protocol import RCL_KEYWORDS

        self.assertEqual(
            RCL_KEYWORDS,
            {
                "R1": (("answer",), ("last", "line")),
                "R2": (("decimal",), ("decimals",), ("thousands",), ("units",)),
                "R3": (("animal",), ("animals",)),
                "PROTO": (("clarification",), ("datum",), ("data",)),
            },
        )
        self.assertEqual(self.call("- espera y usa coma\nANSWER: 0").score, 0)


if __name__ == "__main__":
    unittest.main()
