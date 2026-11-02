import json
import unittest
from pathlib import Path

import _bootstrap

from psicotest.checkers.budget import (
    BUDGET_BAND,
    BUDGET_MARGIN,
    BUDGET_MARKER,
    BUDGET_MIN_CLUSTER,
    BUDGET_MIN_GAP,
    budget_flags,
    has_budget_marker,
    infer_budget_cap,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "budget_golden.json"

RUNS = {
    "strata-v6-seed7",
    "strata-v6-seed11",
    "strata-iq2xs-seed7",
    "strata-iq2xs-seed11",
}


def load_rows():
    return json.loads(FIXTURE.read_text("utf-8"))


def by_run():
    grouped = {}
    for row in load_rows():
        grouped.setdefault(row["run"], []).append(row)
    for run_rows in grouped.values():
        run_rows.sort(key=lambda row: row["turn"])
    return grouped


def flagged_pairs():
    pairs = set()
    for run, run_rows in by_run().items():
        flags = budget_flags([row["ct"] for row in run_rows])
        for row, flag in zip(run_rows, flags, strict=True):
            if flag:
                pairs.add((run, row["turn"]))
    return pairs


class TestBudgetFixture(unittest.TestCase):
    def test_fixture_shape(self):
        rows = load_rows()
        self.assertEqual(len(rows), 152)
        for row in rows:
            self.assertEqual(set(row), {"run", "turn", "kind", "slot", "ct", "fr", "phrase"})
            self.assertEqual(row["fr"], "stop")
        runs = by_run()
        self.assertEqual(set(runs), RUNS)
        for run_rows in runs.values():
            self.assertEqual([row["turn"] for row in run_rows], list(range(1, 39)))

    def test_flagged_set_is_the_34(self):
        flagged = flagged_pairs()
        phrase = {(row["run"], row["turn"]) for row in load_rows() if row["phrase"]}
        self.assertEqual(flagged, phrase)
        self.assertEqual(len(flagged), 34)

    def test_token_rule_agrees_with_phrase_on_all_rows(self):
        for run, run_rows in by_run().items():
            flags = budget_flags([row["ct"] for row in run_rows])
            for row, flag in zip(run_rows, flags, strict=True):
                with self.subTest(run=run, turn=row["turn"]):
                    self.assertEqual(flag, row["phrase"])

    def test_per_run_caps_and_counts(self):
        runs = by_run()
        self.assertEqual(
            {run: infer_budget_cap([row["ct"] for row in rows]) for run, rows in runs.items()},
            {
                "strata-v6-seed7": 4638,
                "strata-v6-seed11": 4638,
                "strata-iq2xs-seed7": 4638,
                "strata-iq2xs-seed11": 4631,
            },
        )
        self.assertEqual(
            {run: sum(budget_flags([row["ct"] for row in rows])) for run, rows in runs.items()},
            {
                "strata-v6-seed7": 8,
                "strata-v6-seed11": 6,
                "strata-iq2xs-seed7": 8,
                "strata-iq2xs-seed11": 12,
            },
        )
        kinds = set()
        for rows in runs.values():
            flags = budget_flags([row["ct"] for row in rows])
            for row, flag in zip(rows, flags, strict=True):
                if flag:
                    kinds.add(row["kind"])
        self.assertEqual(kinds, {"item", "recall"})

    def test_gap_and_margin_window(self):
        runs = by_run()
        rows = [row for run_rows in runs.values() for row in run_rows]
        flagged = flagged_pairs()
        caps = {
            run: infer_budget_cap([row["ct"] for row in run_rows]) for run, run_rows in runs.items()
        }
        unflagged_ct = [row["ct"] for row in rows if (row["run"], row["turn"]) not in flagged]
        flagged_ct = [row["ct"] for row in rows if (row["run"], row["turn"]) in flagged]
        self.assertEqual(max(unflagged_ct), 4110)
        self.assertEqual(min(flagged_ct), 4631)
        self.assertEqual(min(flagged_ct) - max(unflagged_ct), 521)
        self.assertEqual(
            max(max(row["ct"] for row in runs[run]) - caps[run] for run in runs),
            268,
        )
        self.assertEqual(
            min(
                max(row["ct"] for row in runs[run])
                - max(row["ct"] for row in runs[run] if (run, row["turn"]) not in flagged)
                for run in runs
            ),
            628,
        )
        self.assertTrue(268 <= BUDGET_MARGIN < 628)


class TestBudgetInference(unittest.TestCase):
    def test_boundary_4110_vs_4631(self):
        cts = [41, 300, 4110, 4631, 4636, 4638, 4652]
        self.assertEqual(infer_budget_cap(cts), 4631)
        self.assertEqual(budget_flags(cts), [False, False, False, True, True, True, True])

    def test_boundary_tail_within_margin(self):
        cts = [41, 300, 4110, 4631, 4636, 4638, 4652, 4899]
        self.assertEqual(infer_budget_cap(cts), 4631)
        self.assertEqual(budget_flags(cts), [False, False, False, True, True, True, True, True])

    def test_no_cap_run_max_1200(self):
        cts = [58, 1200, 651, 397, 833, 152, 673, 213, 558, 858, 353, 1139, 216, 96]
        self.assertIsNone(infer_budget_cap(cts))
        self.assertEqual(budget_flags(cts), [False] * len(cts))

    def test_lone_max_not_flagged(self):
        self.assertIsNone(infer_budget_cap([41, 300, 1200, 4899]))

    def test_dense_top_without_gap_not_flagged(self):
        self.assertIsNone(infer_budget_cap([1200, 1190, 1180, 1170, 1100, 900, 300]))

    def test_gap_below_min_gap_not_flagged(self):
        self.assertIsNone(infer_budget_cap([41, 300, 4400, 4631, 4636, 4638, 4652]))

    def test_all_equal_run_not_flagged(self):
        cts = [41] * 38
        self.assertIsNone(infer_budget_cap(cts))
        self.assertEqual(budget_flags(cts), [False] * 38)

    def test_empty_and_short(self):
        self.assertIsNone(infer_budget_cap([]))
        self.assertEqual(budget_flags([]), [])
        self.assertIsNone(infer_budget_cap([4638, 4638, 4638]))

    def test_constants_pinned(self):
        self.assertEqual(BUDGET_MARGIN, 448)
        self.assertEqual(BUDGET_BAND, 32)
        self.assertEqual(BUDGET_MIN_CLUSTER, 4)
        self.assertEqual(BUDGET_MIN_GAP, 256)

    def test_marker_constant(self):
        self.assertEqual(
            BUDGET_MARKER, "I have thought about this long enough; time to give my answer"
        )
        self.assertFalse(has_budget_marker(None))
        self.assertTrue(has_budget_marker("x " + BUDGET_MARKER + "."))
        self.assertFalse(has_budget_marker(BUDGET_MARKER[:-1]))

    def test_marker_defined_once(self):
        root = Path(__file__).resolve().parent.parent / "src" / "psicotest"
        matches = []
        for path in sorted(root.rglob("*.py")):
            if BUDGET_MARKER in path.read_text("utf-8"):
                matches.append(path.name)
        self.assertEqual(matches, ["budget.py"])


if __name__ == "__main__":
    unittest.main()
