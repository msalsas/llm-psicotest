import unittest

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS

FPRE = item_fixtures.FPRE


def fpre_item(key_value, true_product, false_product, absorbed, k, c):
    return item_fixtures.make_item(
        "FPRE",
        {"value": key_value},
        {
            "true_product": true_product,
            "false_product": false_product,
            "absorbed": absorbed,
            "k": k,
            "c": c,
            "level": "L1",
        },
    )


class TestCheckersFPRE(unittest.TestCase):
    def call(self, content, item=FPRE):
        return CHECKERS["FPRE"](content, "stop", None, item)

    def test_fpre_case1(self):
        r = self.call("RESPUESTA: 426")
        self.assertEqual(r.outcome, "PREMISE_ABSORBED")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_fpre_case2(self):
        r = self.call("17\u00d723 es 391, no 401.\nRESPUESTA: 416")
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("PREMISE_NOTED", "R2_OK"))

    def test_fpre_case3(self):
        r = self.call("RESPUESTA: 415")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_fpre_case4(self):
        item = fpre_item(401, 391, 401, 411, 1, 10)
        r = self.call("RESPUESTA: 401", item)
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "not_distinct")

    def test_fpre_noted_on_wrong(self):
        r = self.call("Es 391.\nRESPUESTA: 415")
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("PREMISE_NOTED", "R2_OK"))

    def test_fpre_invariants(self):
        r = self.call("RESPUESTA: 417", fpre_item(417, 391, 401, 426, 1, 25))
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "inconsistent")
        r = self.call("RESPUESTA: 416", fpre_item(416, 391, 400, 425, 1, 25))
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "absorbed_too_close")
        r = self.call("RESPUESTA: 416", fpre_item(416, 391, 0, 25, 1, 25))
        self.assertEqual(r.outcome, "GEN_BUG")
        self.assertEqual(r.detail, "false_product_nonpositive")


if __name__ == "__main__":
    unittest.main()
