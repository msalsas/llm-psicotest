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
    "tokens",
    "timing",
    "telemetry",
    "errors",
]


def oracle_run(tmp, seed=7, order="A"):
    turns = battery_layout(seed, order)
    server = fakes.FakeServer("oracle", turns)
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
    return Path(tmp) / f"v5_{seed}_{order}.jsonl"


def load_report(tmp, seed=7, order="A"):
    path = Path(tmp) / f"v5_{seed}_{order}.report.json"
    return path, json.loads(path.read_text("utf-8"))


class TestReport(unittest.TestCase):
    def test_report_deterministic_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = oracle_run(tmp)
            report_path = Path(tmp) / "v5_7_A.report.json"
            write_report(checkpoint_path, report_path)
            first = report_path.read_bytes()
            write_report(checkpoint_path, report_path)
            second = report_path.read_bytes()
            self.assertEqual(first, second)

    def test_report_from_oracle_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            oracle_run(tmp)
            _path, report = load_report(tmp)
            self.assertEqual(report["schema"], 1)
            self.assertEqual(report["battery_version"], "v5")
            self.assertEqual(report["seed"], 7)
            self.assertEqual(report["order"], "A")
            self.assertEqual(report["capability"]["score"], 27)
            self.assertEqual(report["capability"]["max"], 27)
            by_family = report["capability"]["by_family"]
            self.assertEqual(sum(f["score"] for f in by_family.values()), 27)
            self.assertEqual(sum(f["max"] for f in by_family.values()), 27)
            self.assertEqual(
                {name: f["max"] for name, f in by_family.items()},
                {
                    "ST": 4,
                    "AR": 2,
                    "AR2": 1,
                    "NOOP": 3,
                    "CSP": 2,
                    "LOG": 3,
                    "CNT": 1,
                    "ERR": 2,
                    "FPRE": 1,
                    "SYP": 2,
                    "IC": 2,
                    "PR": 2,
                    "PC": 2,
                },
            )
            self.assertTrue(report["protocol"]["setup_ok"])
            self.assertEqual(report["protocol"]["rcl_score"], 3)
            self.assertEqual(report["errors"], [])

    def test_report_key_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            oracle_run(tmp)
            path, _report = load_report(tmp)
            text = path.read_text("utf-8")
            ordered = json.loads(text)
            self.assertEqual(list(ordered), TOP_KEYS)
            self.assertEqual(list(ordered["capability"]), ["score", "max", "by_family"])
            self.assertEqual(
                list(ordered["protocol"]),
                ["setup_ok", "clar_ok", "clar_miss", "clar_over", "clar_bad", "rcl_score"],
            )
            self.assertEqual(list(ordered["rules"]), ["R1", "R2", "R3"])
            self.assertEqual(list(ordered["rules"]["R1"]), ["ok", "fail", "na"])
            self.assertEqual(list(ordered["rules"]["R3"]), ["hit", "miss", "false", "clean", "na"])
            self.assertEqual(
                list(ordered["tokens"]),
                ["prompt_total", "completion_total", "reasoning_total"],
            )
            self.assertEqual(list(ordered["timing"]), ["wall_s_total", "wall_s_mean"])
            self.assertEqual(
                list(ordered["telemetry"]),
                ["leak_chars", "loop_count", "selfcorr_total"],
            )

    def test_report_aggregation_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint_path = oracle_run(tmp)
            _path, report = load_report(tmp)
            self.assertEqual(report["rules"]["R1"], {"ok": 33, "fail": 0, "na": 3})
            self.assertEqual(report["rules"]["R2"], {"ok": 26, "fail": 0, "na": 10})
            self.assertEqual(
                report["rules"]["R3"],
                {"hit": 4, "miss": 0, "false": 0, "clean": 21, "na": 11},
            )
            lines = checkpoint_path.read_text("utf-8").splitlines()
            turns = [json.loads(line) for line in lines if json.loads(line)["type"] == "turn"]
            prompt_total = sum(t["response"]["usage"]["prompt_tokens"] for t in turns)
            completion_total = sum(t["response"]["usage"]["completion_tokens"] for t in turns)
            reasoning_total = sum(t["response"]["usage"]["reasoning_tokens"] or 0 for t in turns)
            self.assertEqual(report["tokens"]["prompt_total"], prompt_total)
            self.assertEqual(report["tokens"]["completion_total"], completion_total)
            self.assertEqual(report["tokens"]["reasoning_total"], reasoning_total)
            self.assertEqual(report["trunc_count"], 0)
            self.assertEqual(report["telemetry"]["leak_chars"], 0)
            self.assertEqual(report["telemetry"]["loop_count"], 0)
            self.assertEqual(report["telemetry"]["selfcorr_total"], 0)


if __name__ == "__main__":
    unittest.main()
