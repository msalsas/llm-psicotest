import unittest
from decimal import Decimal
from fractions import Fraction

import _bootstrap
import item_fixtures

from psicotest.checkers import CHECKERS, rules
from psicotest.checkers.extract import (
    APPROX_RE,
    CLAR_LINE_RE,
    RESP_LINE_RE,
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
            CHECKERS["AR"]("", "stop", "ANSWER: 4567890123", AR),
            R("NOANS", 0, None, ("REASONING_ONLY",), ""),
        )
        self.assertEqual(
            CHECKERS["AR"]("I don't know.", "stop", "ANSWER: 4567890123", AR).flags,
            (),
        )
        self.assertEqual(CHECKERS["AR"](None, None, None, AR).outcome, "NOANS")
        with self.assertRaises(TypeError):
            CHECKERS["AR"](b"x", "stop", None, AR)

    def test_preclean_markup(self):
        self.assertEqual(preclean("**ANSWER:** `42`"), "ANSWER: 42")
        self.assertEqual(preclean("__x__ $5$"), "x 5")

    def test_preclean_boxed(self):
        self.assertEqual(preclean("\\boxed{\\boxed{7}}"), "7")
        self.assertEqual(extract_answer("ANSWER: \\boxed{12.35}").value, "12.35")

    def test_preclean_nbsp_nfkc(self):
        self.assertEqual(
            preclean("\uff21\uff2e\uff33\uff37\uff25\uff32\uff1a\u00a042"),
            "ANSWER: 42",
        )
        self.assertEqual(preclean("a\r\nb\rc"), "a\nb\nc")

    def test_extraction_last_match(self):
        ext = extract_answer("ANSWER: 1\nANSWER: 2")
        self.assertEqual(ext.value, "2")
        self.assertEqual(ext.values, ("1", "2"))
        self.assertEqual(ext.n_resp, 2)
        self.assertIs(ext.multi, True)
        self.assertIs(ext.last_line_ok, True)
        self.assertEqual(ext.resp_lines, (0, 1))

    def test_extraction_case_and_period(self):
        self.assertEqual(extract_answer("answer :  42 .").value, "42")
        self.assertEqual(extract_answer("  Answer: 12.35.").value, "12.35")
        self.assertIsNone(extract_answer("The ANSWER: 5").value)

    def test_multiplicity_same_value(self):
        ext = extract_answer("ANSWER: 42\nANSWER:  42")
        self.assertEqual(ext.n_resp, 2)
        self.assertIs(ext.multi, False)

    def test_last_line_flag(self):
        self.assertIs(extract_answer("ANSWER: 42\nThanks.").last_line_ok, False)
        self.assertIs(extract_answer("ANSWER: 42\n\n  \n").last_line_ok, True)

    def test_truncation_overrides(self):
        self.assertEqual(
            CHECKERS["AR"]("ANSWER: 4567890123", "length", None, AR),
            R("TRUNC", 0, None, (), ""),
        )

    def test_cjk_leak_content(self):
        r = CHECKERS["AR"]("\u8ba1\u7b97\u5b8c\u6210\nANSWER: 4567890123", "stop", None, AR)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("LEAK", "R2_OK"))
        r = CHECKERS["AR"]("ANSWER: 4567890123", "stop", "\u601d\u8003", AR)
        self.assertEqual(r.flags, ("R2_OK",))

    def test_cjk_leak_in_value(self):
        r = CHECKERS["AR"]("ANSWER: 4567890123 \u4e2a", "stop", None, AR)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("LEAK", "FMT", "R2_FAIL"))

    def test_number_both_separators(self):
        self.assertEqual(parse_number("1.234,5"), (Decimal("1234.5"), {"R2_FAIL"}))
        self.assertEqual(parse_number("1,234.5"), (Decimal("1234.5"), {"R2_FAIL"}))
        self.assertEqual(parse_number("1,234,567.89"), (Decimal("1234567.89"), {"R2_FAIL"}))
        self.assertEqual(parse_number("12,34.5"), (None, set()))
        self.assertEqual(parse_number("1.234,5.6"), (None, set()))

    def test_number_comma_only(self):
        self.assertEqual(parse_number("12,35"), (Decimal("12.35"), {"R2_FAIL", "FMT"}))
        self.assertEqual(parse_number("12,345"), (Decimal("12345"), {"R2_FAIL"}))
        self.assertEqual(parse_number("0,5"), (Decimal("0.5"), {"R2_FAIL", "FMT"}))
        self.assertEqual(parse_number("1,234"), (Decimal("1234"), {"R2_FAIL"}))

    def test_number_comma_multi(self):
        self.assertEqual(parse_number("4,567,890,123"), (Decimal("4567890123"), {"R2_FAIL"}))
        self.assertEqual(parse_number("1,2,3"), (None, set()))
        self.assertEqual(parse_number("1,23,4"), (None, set()))

    def test_number_dot_thousands(self):
        self.assertEqual(parse_number("4.567.890.123"), (Decimal("4567890123"), {"R2_FAIL"}))
        self.assertEqual(parse_number("1.23.4"), (None, set()))

    def test_number_dot_decimal(self):
        self.assertEqual(parse_number("12.35"), (Decimal("12.35"), set()))
        self.assertEqual(parse_number("12.345"), (Decimal("12.345"), set()))
        self.assertEqual(parse_number("1.234"), (Decimal("1.234"), set()))
        self.assertEqual(parse_number("1.2.3"), (None, set()))
        self.assertEqual(parse_number("1.2345"), (Decimal("1.2345"), set()))
        self.assertEqual(parse_number("0.5"), (Decimal("0.5"), set()))

    def test_number_words(self):
        self.assertEqual(parse_number("seventeen"), (Decimal(17), {"FMT"}))
        self.assertEqual(parse_number("Twenty-Three"), (Decimal(23), {"FMT"}))
        self.assertEqual(parse_number("thirty-two"), (Decimal(32), {"FMT"}))
        self.assertEqual(parse_number("one hundred"), (Decimal(100), {"FMT"}))
        self.assertEqual(parse_number("zero"), (Decimal(0), {"FMT"}))
        self.assertEqual(len(NUMBER_WORDS), 102)

    def test_number_plain_and_sign(self):
        self.assertEqual(parse_number("42"), (Decimal("42"), set()))
        self.assertEqual(parse_number("-7"), (Decimal("-7"), set()))
        self.assertEqual(parse_number("+7"), (Decimal("7"), set()))
        self.assertEqual(parse_number("\u22127"), (Decimal("-7"), set()))
        self.assertEqual(parse_number("one hundred one"), (None, set()))
        self.assertEqual(parse_number("two thousand"), (None, set()))
        self.assertEqual(parse_number(""), (None, set()))
        self.assertEqual(parse_number("abc"), (None, set()))
        self.assertEqual(parse_number("4 2"), (None, set()))

    def test_scalar_ladder(self):
        cases = [
            ("17 (counting the first one)", ("ok", 17, [], "")),
            ("17 (or 18)", ("ambig", None, [], "paren_number")),
            ("\u2248 4.57\u00d710^9", ("ok", 4570000000, ["FMT"], "approx;sci")),
            ("42 - 5 = 37", ("ok", 37, ["FMT"], "eq_tail")),
            ("42 - 5", ("ambig", None, [], "multi_number")),
            ("between 16 and 17", ("ambig", None, [], "multi_number")),
            ("roughly 42", ("ambig", None, [], "lead_text")),
            ("see table above", ("none", None, [], "no_number")),
            ("1.2.3", ("ambig", None, [], "badnum")),
            ("five", ("ok", 5, ["FMT"], "words")),
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
            parse_scalar("42 apples"),
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
        r = CHECKERS["AR"]("ANSWER: 4,567,890,123", "stop", None, AR)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("R2_FAIL",))
        r = CHECKERS["AR"]("ANSWER: 4567890124", "stop", None, AR)
        self.assertEqual(r.outcome, "WRONG")
        self.assertEqual(r.flags, ("R2_OK",))

    def test_value_vs_format_single_r2(self):
        r = CHECKERS["AR"]("ANSWER: 4,567,890,123", "stop", None, AR)
        self.assertEqual([f for f in r.flags if f.startswith("R2_")], ["R2_FAIL"])

    def test_ambig_unit_no_r2(self):
        r = CHECKERS["AR"]("ANSWER: \u20ac45 or 46", "stop", None, AR)
        self.assertEqual(r.outcome, "AMBIG")
        self.assertNotIn("R2_FAIL", r.flags)
        self.assertNotIn("R2_OK", r.flags)
        r = CHECKERS["AR"]("ANSWER: 1.2.3 \u20ac", "stop", None, AR)
        self.assertEqual(r.outcome, "AMBIG")
        self.assertNotIn("R2_FAIL", r.flags)
        self.assertNotIn("R2_OK", r.flags)

    def test_loop_flag(self):
        block = ("x" * 63 + "\n") * 5
        r = CHECKERS["AR"](block + "ANSWER: 4567890123", "stop", None, AR)
        self.assertEqual(r.outcome, "OK")
        self.assertEqual(r.flags, ("LOOP", "R2_OK"))
        r = CHECKERS["AR"]("ANSWER: 4567890123", "stop", ("y" * 63 + "\n") * 5, AR)
        self.assertEqual(r.flags, ("LOOP", "R2_OK"))
        r = CHECKERS["AR"]("ANSWER: 4567890123", "stop", ("y" * 63 + "\n") * 4, AR)
        self.assertEqual(r.flags, ("R2_OK",))

    def test_number_tokens(self):
        self.assertEqual(
            number_tokens("17\u00d723 is 391, not 401."),
            [Decimal("17"), Decimal("23"), Decimal("391"), Decimal("401")],
        )

    def test_markers_english(self):
        self.assertEqual(RESP_LINE_RE.pattern, r"^\s*ANSWER\s*:\s*(.+?)\s*\.?\s*$")
        self.assertEqual(CLAR_LINE_RE.pattern, r"^\s*CLARIFICATION\s*:\s*(.*?)\s*$")
        self.assertEqual(rules.ANIMAL_LINE_RE.pattern, r"^\s*ANIMAL\s*:\s*(.*?)\s*\.?\s*$")
        self.assertIsNone(extract_answer("RESP" + "UESTA: 42").value)
        self.assertEqual(extract_answer("Answer: 42").value, "42")
        self.assertEqual(
            CHECKERS["AR"]("RESP" + "UESTA: 4567890123", "stop", None, AR).outcome,
            "NOANS",
        )

    def test_number_words_no_false_composites(self):
        forbidden = (
            "onety",
            "tenty",
            "eleventy",
            "twenty-zero",
            "twenty-ten",
            "ten-one",
            "nineteen-one",
            "fourty",
            "twenty two",
            "hundred",
            "a",
            "one hundred one",
            "one hundred and one",
            "two thousand",
            "twelve point three five",
            "minus five",
        )
        for value in forbidden:
            self.assertNotIn(value, NUMBER_WORDS)
            self.assertEqual(parse_number(value), (None, set()))
        self.assertEqual(sorted(set(NUMBER_WORDS.values())), list(range(101)))
        self.assertEqual(NUMBER_WORDS["ninety-nine"], 99)
        self.assertEqual(NUMBER_WORDS["a hundred"], 100)

    def test_approx_english(self):
        expected = Scalar("ok", Decimal("42"), frozenset({"FMT"}), "approx")
        for value in ("approximately 42", "approx. 42", "Approx 42"):
            self.assertEqual(parse_scalar(value), expected)
        for value in ("aprox 42", "aproximadamente 42"):
            self.assertEqual(
                (parse_scalar(value).status, parse_scalar(value).detail),
                ("ambig", "lead_text"),
            )


if __name__ == "__main__":
    unittest.main()
