import unittest
from decimal import Decimal
from fractions import Fraction

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS
from psicotest.checkers.extract import (
    Scalar,
    extract_answer,
    number_tokens,
    parse_number,
    parse_scalar,
    preclean,
)
from psicotest.checkers.text import NUMBER_WORDS
from psicotest.spec import CheckResult as R

AR = item_fixtures.AR


class TestExtract(unittest.TestCase):
    def test_source_content_only(self):
        self.assertEqual(
            CHECKERS["AR"]("", "stop", "RESPUESTA: 4567890123", AR),
            R("NOANS", 0, None, ("REASONING_ONLY",), ""),
        )
        self.assertEqual(CHECKERS["AR"]("No sé.", "stop", "RESPUESTA: 4567890123", AR).flags, ())
        self.assertEqual(CHECKERS["AR"](None, None, None, AR).outcome, "NOANS")
        with self.assertRaises(TypeError):
            CHECKERS["AR"](b"x", "stop", None, AR)

    def test_preclean_markup(self):
        self.assertEqual(preclean("**RESPUESTA:** `42`"), "RESPUESTA: 42")
        self.assertEqual(preclean("__x__ $5$"), "x 5")

    def test_preclean_boxed(self):
        self.assertEqual(preclean("\\boxed{\\boxed{7}}"), "7")
        self.assertEqual(extract_answer("RESPUESTA: \\boxed{12,35}").value, "12,35")

    def test_preclean_nbsp_nfkc(self):
        self.assertEqual(
            preclean("\uff32\uff25\uff33\uff30\uff35\uff25\uff33\uff34\uff21\uff1a\u00a042"),
            "RESPUESTA: 42",
        )
        self.assertEqual(preclean("a\r\nb\rc"), "a\nb\nc")

    def test_extraction_last_match(self):
        ext = extract_answer("RESPUESTA: 1\nRESPUESTA: 2")
        self.assertEqual(ext.value, "2")
        self.assertEqual(ext.values, ("1", "2"))
        self.assertEqual(ext.n_resp, 2)
        self.assertIs(ext.multi, True)
        self.assertIs(ext.last_line_ok, True)
        self.assertEqual(ext.resp_lines, (0, 1))

    def test_extraction_case_and_period(self):
        self.assertEqual(extract_answer("respuesta :  42 .").value, "42")
        self.assertEqual(extract_answer("  Respuesta: 12,35.").value, "12,35")
        self.assertIsNone(extract_answer("La RESPUESTA: 5").value)

    def test_multiplicity_same_value(self):
        ext = extract_answer("RESPUESTA: 42\nRESPUESTA:  42")
        self.assertEqual(ext.n_resp, 2)
        self.assertIs(ext.multi, False)

    def test_last_line_flag(self):
        self.assertIs(extract_answer("RESPUESTA: 42\nGracias.").last_line_ok, False)
        self.assertIs(extract_answer("RESPUESTA: 42\n\n  \n").last_line_ok, True)

    def test_truncation_overrides(self):
        self.assertEqual(
            CHECKERS["AR"]("RESPUESTA: 4567890123", "length", None, AR),
            R("TRUNC", 0, None, (), ""),
        )

    def test_cjk_leak_content(self):
        r = CHECKERS["AR"]("\u8ba1\u7b97\u5b8c\u6210\nRESPUESTA: 4567890123", "stop", None, AR)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("LEAK", "R2_OK"))
        r = CHECKERS["AR"]("RESPUESTA: 4567890123", "stop", "\u601d\u8003", AR)
        self.assertEqual(r.flags, ("R2_OK",))

    def test_cjk_leak_in_value(self):
        r = CHECKERS["AR"]("RESPUESTA: 4567890123 \u4e2a", "stop", None, AR)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("LEAK", "FMT", "R2_FAIL"))

    def test_number_both_separators(self):
        self.assertEqual(parse_number("1.234,5"), (Decimal("1234.5"), {"R2_FAIL"}))
        self.assertEqual(parse_number("1,234.5"), (Decimal("1234.5"), {"R2_FAIL"}))
        self.assertEqual(parse_number("1.234.567,89"), (Decimal("1234567.89"), {"R2_FAIL"}))
        self.assertEqual(parse_number("12.34,5"), (None, set()))
        self.assertEqual(parse_number("1,234.5,6"), (None, set()))

    def test_number_comma_only(self):
        self.assertEqual(parse_number("12,35"), (Decimal("12.35"), set()))
        self.assertEqual(parse_number("12,345"), (Decimal("12.345"), set()))
        self.assertEqual(parse_number("0,5"), (Decimal("0.5"), set()))

    def test_number_comma_multi(self):
        self.assertEqual(parse_number("4,567,890,123"), (Decimal("4567890123"), {"R2_FAIL"}))
        self.assertEqual(parse_number("1,23,4"), (None, set()))

    def test_number_dot_thousands(self):
        self.assertEqual(parse_number("4.567.890.123"), (Decimal("4567890123"), {"R2_FAIL"}))
        self.assertEqual(parse_number("1.234"), (Decimal("1234"), {"R2_FAIL"}))

    def test_number_dot_decimal(self):
        self.assertEqual(parse_number("12.35"), (Decimal("12.35"), {"R2_FAIL", "FMT"}))
        self.assertEqual(parse_number("1.2.3"), (None, set()))
        self.assertEqual(parse_number("1.2345"), (Decimal("1.2345"), {"R2_FAIL", "FMT"}))

    def test_number_words(self):
        self.assertEqual(parse_number("diecisiete"), (Decimal(17), {"FMT"}))
        self.assertEqual(parse_number("Veintitrés"), (Decimal(23), {"FMT"}))
        self.assertEqual(parse_number("treinta y dos"), (Decimal(32), {"FMT"}))
        self.assertEqual(parse_number("cien"), (Decimal(100), {"FMT"}))
        self.assertEqual(parse_number("cero"), (Decimal(0), {"FMT"}))
        self.assertEqual(parse_number("ciento"), (None, set()))
        self.assertEqual(len(NUMBER_WORDS), 119)

    def test_number_plain_and_sign(self):
        self.assertEqual(parse_number("42"), (Decimal("42"), set()))
        self.assertEqual(parse_number("-7"), (Decimal("-7"), set()))
        self.assertEqual(parse_number("+7"), (Decimal("7"), set()))
        self.assertEqual(parse_number("\u22127"), (Decimal("-7"), set()))
        self.assertEqual(parse_number("ciento uno"), (None, set()))
        self.assertEqual(parse_number("dos mil"), (None, set()))
        self.assertEqual(parse_number(""), (None, set()))
        self.assertEqual(parse_number("abc"), (None, set()))
        self.assertEqual(parse_number("4 2"), (None, set()))

    def test_scalar_ladder(self):
        cases = [
            ("17 (contando la inicial)", ("ok", 17, [], "")),
            ("17 (o 18)", ("ambig", None, [], "paren_number")),
            ("\u2248 4,57\u00d710^9", ("ok", 4570000000, ["FMT"], "approx;sci")),
            ("42 - 5 = 37", ("ok", 37, ["FMT"], "eq_tail")),
            ("42 - 5", ("ambig", None, [], "multi_number")),
            ("entre 16 y 17", ("ambig", None, [], "multi_number")),
            ("unos 42", ("ambig", None, [], "lead_text")),
            ("ver tabla arriba", ("none", None, [], "no_number")),
            ("1.2.3", ("ambig", None, [], "badnum")),
            ("cinco", ("ok", 5, ["FMT"], "words")),
            ("=", ("none", None, ["FMT"], "eq_tail;no_number")),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                sc = parse_scalar(text)
                got = (
                    sc.status,
                    Fraction(sc.number) if sc.number is not None else None,
                    sorted(sc.flags),
                    sc.detail,
                )
                self.assertEqual(got, expected)

    def test_units_stripped(self):
        self.assertEqual(
            parse_scalar("42 manzanas"),
            Scalar("ok", Decimal("42"), frozenset({"R2_FAIL"}), "unit"),
        )
        for text in ("45 \u20ac", "\u20ac45", "3 km/h"):
            with self.subTest(text=text):
                sc = parse_scalar(text)
                self.assertEqual(sc.status, "ok")
                self.assertEqual(sc.flags, frozenset({"R2_FAIL"}))
        sc = parse_scalar("42 m2")
        self.assertEqual(sc.status, "ambig")
        self.assertEqual(sc.detail, "multi_number")

    def test_value_vs_format(self):
        r = CHECKERS["AR"]("RESPUESTA: 4.567.890.123", "stop", None, AR)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_FAIL",))
        r = CHECKERS["AR"]("RESPUESTA: 4567890124", "stop", None, AR)
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_value_vs_format_single_r2(self):
        r = CHECKERS["AR"]("RESPUESTA: 4.567.890.123", "stop", None, AR)
        self.assertEqual([f for f in r.flags if f.startswith("R2_")], ["R2_FAIL"])

    def test_ambig_unit_no_r2(self):
        r = CHECKERS["AR"]("RESPUESTA: \u20ac45 o 46", "stop", None, AR)
        self.assertEqual(r.outcome, "AMBIG")
        self.assertNotIn("R2_FAIL", r.flags)
        self.assertNotIn("R2_OK", r.flags)
        r = CHECKERS["AR"]("RESPUESTA: 1.2.3 \u20ac", "stop", None, AR)
        self.assertEqual(r.outcome, "AMBIG")
        self.assertNotIn("R2_FAIL", r.flags)
        self.assertNotIn("R2_OK", r.flags)

    def test_loop_flag(self):
        block = ("x" * 63 + "\n") * 5
        r = CHECKERS["AR"](block + "RESPUESTA: 4567890123", "stop", None, AR)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("LOOP", "R2_OK"))
        r = CHECKERS["AR"]("RESPUESTA: 4567890123", "stop", ("y" * 63 + "\n") * 5, AR)
        self.assertEqual(r.flags, ("LOOP", "R2_OK"))
        r = CHECKERS["AR"]("RESPUESTA: 4567890123", "stop", ("y" * 63 + "\n") * 4, AR)
        self.assertEqual(r.flags, ("R2_OK",))

    def test_number_tokens(self):
        self.assertEqual(
            number_tokens("17\u00d723 es 391, no 401."),
            [Decimal("17"), Decimal("23"), Decimal("391"), Decimal("401")],
        )


if __name__ == "__main__":
    unittest.main()
