import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap
import fakes
from fake_transport import FakeServerTransport

from psicotest.generators import SLOTS_V5
from psicotest.runner import driver
from psicotest.runner.battery import battery_layout
from psicotest.runner.driver import run_battery

API_KEY = "fake-key-0123456789"
BASE_URL = "http://fake/v1"
MODEL = "fake-model"


def run(persona, out_dir, seed=7, order="A", resume=False):
    turns = battery_layout(seed, order)
    server = fakes.FakeServer(persona, turns)
    transport = FakeServerTransport(server)
    with mock.patch("psicotest.runner.client._wait", lambda delay: None):
        return run_battery(
            transport=transport,
            base_url=BASE_URL,
            model=MODEL,
            api_key=API_KEY,
            seed=seed,
            order=order,
            out_dir=out_dir,
            resume=resume,
        )


def records_of(path):
    return [json.loads(line) for line in Path(path).read_text("utf-8").splitlines()]


class TestIntegration(unittest.TestCase):
    def test_full_run_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = run("oracle", tmp)
            self.assertEqual(code, driver.EXIT_OK)
            checkpoint_path = Path(tmp) / "v5_7_A.jsonl"
            records = records_of(checkpoint_path)
            types = [r["type"] for r in records]
            self.assertEqual(types[0], "header")
            self.assertEqual(types[-1], "footer")
            self.assertEqual(types.count("turn"), 36)
            report = json.loads((Path(tmp) / "v5_7_A.report.json").read_text("utf-8"))
            self.assertEqual(report["capability"]["score"], 27)
            self.assertEqual(report["protocol"]["clar_ok"], 3)

    def test_full_run_crasher_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = run("crasher", tmp)
            self.assertEqual(code, driver.EXIT_TRANSPORT)
            checkpoint_path = Path(tmp) / "v5_7_A.jsonl"
            records = records_of(checkpoint_path)
            turn_records = [r for r in records if r["type"] == "turn"]
            self.assertEqual(len(turn_records), 11)
            error_records = [r for r in records if r["type"] == "error"]
            self.assertEqual(len(error_records), 4)
            for error in error_records:
                self.assertEqual(error["turn"], 12)
                self.assertEqual(error["kind"], "connect")
            self.assertEqual([error["attempt"] for error in error_records], [1, 2, 3, 4])
            self.assertNotIn("footer", [r["type"] for r in records])
            code = run("oracle", tmp, resume=True)
            self.assertEqual(code, driver.EXIT_OK)
            records = records_of(checkpoint_path)
            types = [r["type"] for r in records]
            self.assertEqual(types.count("turn"), 36)
            self.assertEqual(types[-1], "footer")
            report = json.loads((Path(tmp) / "v5_7_A.report.json").read_text("utf-8"))
            self.assertEqual(report["capability"]["score"], 27)
            self.assertEqual(report["protocol"]["clar_ok"], 3)
            with tempfile.TemporaryDirectory() as reference:
                run("oracle", reference)
                reference_records = records_of(Path(reference) / "v5_7_A.jsonl")
            resumed_hashes = [
                r["request"]["messages_sha256"] for r in records if r["type"] == "turn"
            ]
            reference_hashes = [
                r["request"]["messages_sha256"] for r in reference_records if r["type"] == "turn"
            ]
            self.assertEqual(resumed_hashes, reference_hashes)

    def test_full_run_auth_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = run("auth_reject", tmp)
            self.assertEqual(code, driver.EXIT_AUTH)
            records = records_of(Path(tmp) / "v5_7_A.jsonl")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["type"], "header")

    def test_full_run_ctx_shrink(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = run("ctx_shrink", tmp)
            self.assertEqual(code, driver.EXIT_PROTOCOL)
            records = records_of(Path(tmp) / "v5_7_A.jsonl")
            turn_records = [r for r in records if r["type"] == "turn"]
            self.assertEqual(len(turn_records), 5)
            self.assertNotIn("footer", [r["type"] for r in records])

    def test_checkpoint_report_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = run("oracle", tmp)
            self.assertEqual(code, driver.EXIT_OK)
            checkpoint_path = Path(tmp) / "v5_7_A.jsonl"
            report_path = Path(tmp) / "v5_7_A.report.json"
            records = records_of(checkpoint_path)
            turn_records = [r for r in records if r["type"] == "turn"]
            report_text = report_path.read_text("utf-8")
            report = json.loads(report_text)
            capability_slots = {s.slot for s in SLOTS_V5 if s.capability}
            capability_sum = sum(
                r["scoring"]["score"]
                for r in turn_records
                if r["kind"] == "item" and r["slot"] is not None and r["slot"] in capability_slots
            )
            self.assertEqual(report["capability"]["score"], capability_sum)
            self.assertEqual(capability_sum, 27)
            clar_ok = sum(1 for r in turn_records if r["scoring"]["outcome"] == "CLAR_OK")
            self.assertEqual(report["protocol"]["clar_ok"], clar_ok)
            self.assertEqual(clar_ok, 3)
            rcl_record = [r for r in turn_records if r["kind"] == "recall"]
            self.assertEqual(report["protocol"]["rcl_score"], rcl_record[0]["scoring"]["score"])
            self.assertEqual(
                report["tokens"]["prompt_total"],
                sum(r["response"]["usage"]["prompt_tokens"] for r in turn_records),
            )
            wall_values = [r["timing"]["wall_s"] for r in turn_records]
            self.assertAlmostEqual(report["timing"]["wall_s_total"], sum(wall_values))
            with tempfile.TemporaryDirectory() as second:
                code = run("oracle", second)
                self.assertEqual(code, driver.EXIT_OK)
                second_text = (Path(second) / "v5_7_A.report.json").read_text("utf-8")
            first_report = json.loads(report_text)
            second_report = json.loads(second_text)
            for volatile in ("started_at", "completed_at", "timing"):
                first_report.pop(volatile)
                second_report.pop(volatile)
            self.assertEqual(first_report, second_report)


if __name__ == "__main__":
    unittest.main()
