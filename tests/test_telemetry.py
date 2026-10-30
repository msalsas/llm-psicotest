import unittest

import _bootstrap

from psicotest.checkers.cjk import cjk_class, count_cjk
from psicotest.checkers.telemetry import has_loop, measure, selfcorr_counts
from psicotest.spec import canonical_json


class TestTelemetry(unittest.TestCase):
    def test_loop_detect(self):
        b = ("0123456789" * 7)[:64]
        self.assertIs(has_loop(b * 5), True)
        self.assertIs(has_loop(b * 4), False)
        self.assertIs(has_loop("a" * 319), False)
        self.assertIs(has_loop("a" * 320), True)
        self.assertIs(has_loop(""), False)
        self.assertIs(has_loop(None), False)
        self.assertEqual(measure(b * 5, "x")["loop"], {"content": True, "reasoning": False})

    def test_leak_split(self):
        m = measure("\u4e2d\u6587\u304b\u306a\u30ab\u30ca\ud55c\uad6d\uff0c\u3002", "\u601d\u8003")
        self.assertEqual(
            m["leak"]["content"],
            {"han": 2, "kana": 4, "hangul": 2, "bopomofo": 0, "total": 8},
        )
        self.assertEqual(m["cjk_punct"], {"content": 2, "reasoning": 0})
        self.assertEqual(m["leak"]["reasoning"]["total"], 2)
        self.assertEqual(m["chars"], {"content": 10, "reasoning": 2})

    def test_leak_astral_and_raw(self):
        c = count_cjk("\U00020000\uf900\uff76")
        self.assertEqual(c["han"], 2)
        self.assertEqual(c["kana"], 1)
        self.assertEqual(count_cjk("\ud840")["leak_total"], 0)

    def test_cjk_boundaries(self):
        rows = [
            (0x10FF, None),
            (0x1100, "hangul"),
            (0x2FFF, None),
            (0x3000, "punct"),
            (0x303F, "punct"),
            (0x3040, "kana"),
            (0x309F, "kana"),
            (0x30A0, "kana"),
            (0x30FF, "kana"),
            (0x3100, "bopomofo"),
            (0x318F, "hangul"),
            (0x33FF, "punct"),
            (0x3400, "han"),
            (0x4DC0, "han"),
            (0x9FFF, "han"),
            (0xA000, None),
            (0xAC00, "hangul"),
            (0xD7AF, "hangul"),
            (0xD7B0, "hangul"),
            (0xD7FF, "hangul"),
            (0xE000, None),
            (0xF8FF, None),
            (0xF900, "han"),
            (0xFAFF, "han"),
            (0xFB00, None),
            (0xFF01, "punct"),
            (0xFF65, "punct"),
            (0xFF66, "kana"),
            (0xFFDC, "hangul"),
            (0xFFDD, None),
            (0x1B000, "kana"),
            (0x1FFFF, None),
            (0x20000, "han"),
            (0x2EBF0, "han"),
            (0x31350, "han"),
            (0x3FFFF, "han"),
            (0x40000, None),
            ("ñ", None),
            ("¿", None),
            ("\u20ac", None),
            ("\u00d7", None),
        ]
        for cp, expected in rows:
            with self.subTest(cp=cp):
                self.assertEqual(cjk_class(chr(cp) if isinstance(cp, int) else cp), expected)
        with self.assertRaises(TypeError):
            cjk_class("ab")

    def test_selfcorr_markers(self):
        counts = selfcorr_counts(
            "Espera, en realidad me equivoqué. Wait. corrijo: error mío. esperanza esperar espera."
        )
        self.assertEqual(
            counts,
            {
                "espera": 2,
                "wait": 1,
                "corrijo": 1,
                "en_realidad": 1,
                "me_equivoque": 1,
                "error_mio": 1,
                "total": 7,
            },
        )
        m = measure("espera", "wait wait")
        self.assertEqual(m["selfcorr"]["content"]["total"], 1)
        self.assertEqual(m["selfcorr"]["reasoning"]["wait"], 2)

    def test_measure_schema(self):
        m = measure(None, None)
        self.assertEqual(sorted(m), ["chars", "cjk_punct", "leak", "loop", "schema", "selfcorr"])
        self.assertEqual(m["chars"], {"content": 0, "reasoning": 0})
        self.assertEqual(m["cjk_punct"], {"content": 0, "reasoning": 0})
        self.assertEqual(m["loop"], {"content": False, "reasoning": False})
        self.assertEqual(m["leak"]["content"]["total"], 0)
        self.assertEqual(m["selfcorr"]["content"]["total"], 0)
        canonical_json(measure("a", "b"))


if __name__ == "__main__":
    unittest.main()
