import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap
import fakes
from fake_transport import FakeServerTransport

from psicotest.runner import client as client_module
from psicotest.runner import driver
from psicotest.runner.battery import battery_layout
from psicotest.runner.driver import run_battery

API_KEY = "fake-key-0123456789"


def drive(persona, out_dir, seed=7, order="A", resume=False):
    turns = battery_layout(seed, order)
    server = fakes.FakeServer(persona, turns)
    transport = FakeServerTransport(server)
    with mock.patch.object(client_module, "_wait", lambda delay: None):
        code = run_battery(
            transport=transport,
            base_url="http://fake/v1",
            model="fake-model",
            api_key=API_KEY,
            seed=seed,
            order=order,
            out_dir=out_dir,
            resume=resume,
        )
    return code


def load_records(path):
    records = []
    for line in Path(path).read_text("utf-8").splitlines():
        records.append(json.loads(line))
    return records


class TestDriver(unittest.TestCase):
    def test_driver_oracle_full_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = drive("oracle", tmp)
            self.assertEqual(code, driver.EXIT_OK)
            checkpoint_path = Path(tmp) / "v5_7_A.jsonl"
            records = load_records(checkpoint_path)
            self.assertEqual(records[0]["type"], "header")
            turn_records = [r for r in records if r["type"] == "turn"]
            self.assertEqual(len(turn_records), 36)
            self.assertEqual(records[-1]["type"], "footer")
            self.assertEqual(records[-1]["n_turns"], 36)
            report_path = Path(tmp) / "v5_7_A.report.json"
            report = json.loads(report_path.read_text("utf-8"))
            self.assertEqual(report["capability"]["score"], 27)
            self.assertEqual(report["capability"]["max"], 27)
            self.assertEqual(report["protocol"]["clar_ok"], 3)
            self.assertEqual(report["protocol"]["rcl_score"], 3)
            self.assertEqual(report["rules"]["R3"]["hit"], 4)
            self.assertEqual(report["trunc_count"], 0)
            self.assertEqual(report["errors"], [])

    def test_driver_scores_each_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = drive("oracle", tmp)
            self.assertEqual(code, driver.EXIT_OK)
            records = load_records(Path(tmp) / "v5_7_A.jsonl")
            turn_records = [r for r in records if r["type"] == "turn"]
            self.assertEqual(len(turn_records), 36)
            for record in turn_records:
                scoring = record["scoring"]
                self.assertEqual(sorted(scoring), ["detail", "flags", "outcome", "score", "value"])
                self.assertEqual(sorted(record["rules"]), ["R1", "R2", "R3", "R3_NOTE"])
                self.assertEqual(record["telemetry"]["schema"], 1)
                self.assertIsInstance(record["attempts"], int)
            outcomes = {record["turn"]: record["scoring"]["outcome"] for record in turn_records}
            for turn in range(2, 37):
                if turn in (8, 19, 27):
                    self.assertEqual(outcomes[turn], "CLAR_OK")
                elif turn == 30:
                    self.assertEqual(outcomes[turn], "RCL")
                else:
                    self.assertEqual(outcomes[turn], "OK")

    def test_driver_handles_trunc(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = drive("truncator", tmp)
            self.assertEqual(code, driver.EXIT_OK)
            records = load_records(Path(tmp) / "v5_7_A.jsonl")
            turn_records = [r for r in records if r["type"] == "turn"]
            self.assertEqual(len(turn_records), 36)
            for record in turn_records:
                self.assertEqual(record["scoring"]["outcome"], "TRUNC")
                self.assertEqual(
                    record["rules"],
                    {"R1": "NA", "R2": "NA", "R3": "NA", "R3_NOTE": ""},
                )
            report = json.loads((Path(tmp) / "v5_7_A.report.json").read_text("utf-8"))
            self.assertEqual(report["trunc_count"], 36)
            self.assertEqual(report["capability"]["score"], 0)
            self.assertFalse(report["protocol"]["setup_ok"])

    def test_driver_r3_triggers(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = drive("oracle", tmp)
            self.assertEqual(code, driver.EXIT_OK)
            records = load_records(Path(tmp) / "v5_7_A.jsonl")
            by_turn = {r["turn"]: r for r in records if r["type"] == "turn"}
            for turn_no in (17, 24, 28, 29):
                record = by_turn[turn_no]
                self.assertEqual(record["rules"]["R3"], "R3_HIT")
                self.assertIn("ANIMAL:", record["response"]["content"])
            report = json.loads((Path(tmp) / "v5_7_A.report.json").read_text("utf-8"))
            self.assertEqual(report["rules"]["R3"]["hit"], 4)
            self.assertEqual(report["rules"]["R3"]["miss"], 0)
            self.assertEqual(report["rules"]["R3"]["false"], 0)
            # R3 is active on turns 12-36 (25 turns); the 4 trigger hits leave 21 clean.
            self.assertEqual(report["rules"]["R3"]["clean"], 21)

    def test_driver_amb_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = drive("oracle", tmp)
            self.assertEqual(code, driver.EXIT_OK)
            records = load_records(Path(tmp) / "v5_7_A.jsonl")
            by_turn = {r["turn"]: r for r in records if r["type"] == "turn"}
            for turn_no in (8, 19, 27):
                self.assertEqual(by_turn[turn_no]["kind"], "amb_ask")
                self.assertEqual(by_turn[turn_no]["scoring"]["outcome"], "CLAR_OK")
            for turn_no in (9, 20, 28):
                self.assertEqual(by_turn[turn_no]["kind"], "amb_reply")
                self.assertEqual(by_turn[turn_no]["scoring"]["outcome"], "OK")
            report = json.loads((Path(tmp) / "v5_7_A.report.json").read_text("utf-8"))
            self.assertEqual(report["protocol"]["clar_ok"], 3)
            self.assertEqual(report["protocol"]["clar_miss"], 0)
            self.assertEqual(report["protocol"]["clar_over"], 0)
            self.assertEqual(report["protocol"]["clar_bad"], 0)

    def test_driver_history_excludes_reasoning(self):
        class Recorder:
            def __init__(self, inner):
                self.inner = inner
                self.bodies = []

            def request(self, method, url, headers, body, timeout):
                self.bodies.append(json.loads(body))
                return self.inner.request(method, url, headers, body, timeout)

        with tempfile.TemporaryDirectory() as tmp:
            turns = battery_layout(7, "A")
            server = fakes.FakeServer("oracle", turns)
            recorder = Recorder(FakeServerTransport(server))
            code = run_battery(
                transport=recorder,
                base_url="http://fake/v1",
                model="fake-model",
                api_key=API_KEY,
                seed=7,
                order="A",
                out_dir=tmp,
            )
            self.assertEqual(code, driver.EXIT_OK)
            self.assertEqual(len(recorder.bodies), 36)
            expected_prompts = {t.turn: t.prompt_en for t in turns}
            for index, body in enumerate(recorder.bodies, start=1):
                messages = body["messages"]
                self.assertEqual(len(messages), 2 * index - 1)
                for position, message in enumerate(messages):
                    self.assertNotIn("reasoning_content", message)
                    self.assertEqual(message["role"], "user" if position % 2 == 0 else "assistant")
                self.assertEqual(messages[-1]["content"], expected_prompts[index])


if __name__ == "__main__":
    unittest.main()
