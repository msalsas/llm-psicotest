import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap
import fakes
from fake_transport import FakeServerTransport

from psicotest.runner.battery import battery_layout
from psicotest.runner.driver import run_battery
from psicotest.runner.report import write_report

API_KEY = "fake-key-0123456789"

TOP_KEYS = [
    "schema",
    "battery_version",
    "manifest_sha256",
    "base_url",
    "model",
    "seed",
    "order",
    "started_at",
    "completed_at",
    "capability",
    "protocol",
    "rules",
    "trunc_count",
    "budget",
    "tokens",
    "timing",
    "telemetry",
    "server",
    "errors",
]


def oracle_run(tmp, persona="oracle", seed=7, order="A"):
    turns = battery_layout(seed, order)
    server = fakes.FakeServer(persona, turns)
    transport = FakeServerTransport(server)
    with mock.patch("psicotest.runner.client._wait", lambda delay: None):
        code = run_battery(
            transport=transport,
            base_url="http://fake/v1",
            model="fake-model",
            api_key=API_KEY,
            seed=seed,
            order=order,
            out_dir=tmp,
        )
    assert code == 0
    return Path(tmp) / f"v6_{seed}_{order}.jsonl"


def rewrite(path, fn):
    lines = Path(path).read_text("utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    text = "".join(json.dumps(fn(record), ensure_ascii=False) + "\n" for record in records)
    Path(path).write_text(text, encoding="utf-8")


def downgrade(record):
    if record["type"] == "header":
        record["schema"] = 1
        record.pop("server", None)
    if record["type"] == "turn":
        record["telemetry"]["schema"] = 1
        record["telemetry"].pop("budget", None)
    return record


def set_tokens(mapping):
    def fn(record):
        if record["type"] == "turn":
            record["response"]["usage"]["completion_tokens"] = mapping.get(
                record["turn"], 50 * record["turn"]
            )
        return record

    return fn


def mark_reasoning(turns):
    def fn(record):
        if record["type"] == "turn" and record["turn"] in turns:
            record["telemetry"]["budget"]["marker"]["reasoning"] = True
        return record

    return fn


def turn_records(path):
    return [
        json.loads(line)
        for line in Path(path).read_text("utf-8").splitlines()
        if json.loads(line)["type"] == "turn"
    ]


class TestReportBudget(unittest.TestCase):
    def test_schema1_archive_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = oracle_run(tmp)
            rewrite(checkpoint_path, downgrade)
            rewrite(checkpoint_path, set_tokens({}))
            report_path = Path(tmp) / "v6_7_A.report.json"
            write_report(checkpoint_path, report_path)
            report = json.loads(report_path.read_text("utf-8"))
            self.assertEqual(
                report["budget"],
                {
                    "cap": None,
                    "budget_hits": 0,
                    "hit_turns": [],
                    "marker_hits": None,
                    "marker_crosscheck": None,
                    "marker_disagree_turns": None,
                },
            )
            self.assertIsNone(report["server"])
            self.assertEqual(report["schema"], 2)
            self.assertEqual(report["trunc_count"], 0)
            self.assertEqual(report["capability"]["score"], 29)

    def test_schema1_archive_token_rule_still_applies(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = oracle_run(tmp)
            rewrite(checkpoint_path, downgrade)
            rewrite(checkpoint_path, set_tokens({6: 4638, 11: 4639, 18: 4652, 21: 4652}))
            report_path = Path(tmp) / "v6_7_A.report.json"
            write_report(checkpoint_path, report_path)
            report = json.loads(report_path.read_text("utf-8"))
            self.assertEqual(report["budget"]["cap"], 4638)
            self.assertEqual(report["budget"]["budget_hits"], 4)
            self.assertEqual(report["budget"]["hit_turns"], [6, 11, 18, 21])
            self.assertIsNone(report["budget"]["marker_hits"])
            self.assertIsNone(report["budget"]["marker_crosscheck"])
            self.assertIsNone(report["budget"]["marker_disagree_turns"])

    def test_schema2_crosscheck_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = oracle_run(tmp)
            rewrite(
                checkpoint_path,
                set_tokens({6: 4638, 11: 4639, 18: 4652, 21: 4652, 30: 4794}),
            )
            rewrite(checkpoint_path, mark_reasoning({6, 11, 18, 21}))
            report_path = Path(tmp) / "v6_7_A.report.json"
            write_report(checkpoint_path, report_path)
            report = json.loads(report_path.read_text("utf-8"))
            self.assertEqual(
                report["budget"],
                {
                    "cap": 4638,
                    "budget_hits": 5,
                    "hit_turns": [6, 11, 18, 21, 30],
                    "marker_hits": 4,
                    "marker_crosscheck": 37,
                    "marker_disagree_turns": [30],
                },
            )

    def test_budget_does_not_touch_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = oracle_run(tmp)
            base_report_path = Path(tmp) / "base.report.json"
            write_report(checkpoint_path, base_report_path)
            base_turns = turn_records(checkpoint_path)
            rewrite(
                checkpoint_path,
                set_tokens({6: 4638, 11: 4639, 18: 4652, 21: 4652, 30: 4794}),
            )
            rewrite(checkpoint_path, mark_reasoning({6, 11, 18, 21}))
            mod_report_path = Path(tmp) / "mod.report.json"
            write_report(checkpoint_path, mod_report_path)
            mod_turns = turn_records(checkpoint_path)
            base = json.loads(base_report_path.read_text("utf-8"))
            mod = json.loads(mod_report_path.read_text("utf-8"))
            for key in ("capability", "protocol", "rules", "trunc_count"):
                self.assertEqual(base[key], mod[key])
            for base_record, mod_record in zip(base_turns, mod_turns, strict=True):
                self.assertEqual(base_record["scoring"], mod_record["scoring"])
                self.assertEqual(base_record["rules"], mod_record["rules"])

    def test_budget_key_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = oracle_run(tmp)
            report_path = Path(tmp) / "v6_7_A.report.json"
            write_report(checkpoint_path, report_path)
            report = json.loads(report_path.read_text("utf-8"))
            self.assertEqual(
                list(report["budget"]),
                [
                    "cap",
                    "budget_hits",
                    "hit_turns",
                    "marker_hits",
                    "marker_crosscheck",
                    "marker_disagree_turns",
                ],
            )
            self.assertEqual(list(report), TOP_KEYS)

    def test_trunc_count_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = oracle_run(tmp, persona="truncator")
            report_path = Path(tmp) / "v6_7_A.report.json"
            write_report(checkpoint_path, report_path)
            report = json.loads(report_path.read_text("utf-8"))
            self.assertEqual(report["trunc_count"], 38)
            self.assertEqual(report["budget"]["marker_hits"], 0)
            self.assertIn("budget", report)
            self.assertIn("trunc_count", report)


if __name__ == "__main__":
    unittest.main()
