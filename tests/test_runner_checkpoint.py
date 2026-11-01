import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap
import fakes
from fake_transport import FakeServerTransport

from psicotest.generators import SLOTS_V5
from psicotest.runner import checkpoint, driver
from psicotest.runner.battery import battery_layout
from psicotest.runner.driver import run_battery

API_KEY = "fake-key-0123456789"


def sample_header():
    return {
        "type": "header",
        "schema": 1,
        "battery_version": "v2",
        "manifest_sha256": "ab" * 32,
        "psicotest_version": "dev",
        "python_version": "3.11.0",
        "platform": "linux",
        "base_url": "http://fake/v1",
        "model": "fake-model",
        "auth_scheme": "bearer",
        "key_env": "PSICOTEST_API_KEY",
        "seed": 7,
        "order": "A",
        "params": {"max_tokens": 6144, "temperature": 0.6, "top_p": 0.95},
        "started_at": "2026-01-01T00:00:00Z",
    }


def sample_turn(turn_no):
    return {
        "type": "turn",
        "turn": turn_no,
        "slot": f"S{turn_no:02d}",
        "kind": "item",
        "request": {
            "n_messages": 1,
            "messages_sha256": "x",
            "prompt_chars": 5,
            "params_sha256": "y",
        },
        "response": {
            "status": 200,
            "model": "fake-model",
            "content": f"ANSWER: {turn_no}",
            "reasoning_content": None,
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "reasoning_tokens": None,
            },
        },
        "timing": {"started_at": "2026-01-01T00:00:00Z", "wall_s": 0.5},
        "effective_tok_s": 10.0,
        "attempts": 1,
        "scoring": {"outcome": "OK", "score": 1, "value": "1", "flags": [], "detail": ""},
        "rules": {"R1": "R1_OK", "R2": "R2_OK", "R3": "NA", "R3_NOTE": ""},
        "telemetry": {"schema": 1},
    }


class TestCheckpoint(unittest.TestCase):
    def test_checkpoint_write_flush_fsync(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.jsonl"
            with mock.patch("os.fsync") as fsync:
                checkpoint.write_header(path, sample_header())
                checkpoint.write_turn(path, sample_turn(1))
                checkpoint.write_error(
                    path,
                    {
                        "type": "error",
                        "turn": 2,
                        "attempt": 1,
                        "kind": "connect",
                        "http_status": None,
                        "message": "boom",
                    },
                )
                checkpoint.write_footer(
                    path, {"type": "footer", "completed_at": "t", "n_turns": 30}
                )
            self.assertEqual(fsync.call_count, 4)
            lines = path.read_text("utf-8").splitlines()
            self.assertEqual(len(lines), 4)
            self.assertEqual(json.loads(lines[0])["type"], "header")
            self.assertEqual(json.loads(lines[-1])["type"], "footer")

    def test_checkpoint_read_truncated_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(sample_header()) + "\n")
                handle.write(json.dumps(sample_turn(1)) + "\n")
                handle.write('{"type": "turn", "turn": 2, "brok')
            header, turns, footer = checkpoint.load_checkpoint(path)
            self.assertIsNotNone(header)
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0]["turn"], 1)
            self.assertIsNone(footer)

    def test_resume_validates_header(self):
        current = {
            "manifest_sha256": "ab" * 32,
            "seed": 7,
            "order": "A",
            "model": "fake-model",
            "params": {"max_tokens": 6144, "temperature": 0.6, "top_p": 0.95},
        }
        self.assertIsNone(checkpoint.validate_resume(sample_header(), current))
        for field in ("manifest_sha256", "seed", "order", "model", "params"):
            bad = dict(current)
            bad[field] = "nope" if field != "seed" else 99
            problem = checkpoint.validate_resume(sample_header(), bad)
            self.assertIsNotNone(problem)
            self.assertIn(field, problem)
        self.assertIsNotNone(checkpoint.validate_resume(None, current))
        self.assertIsNotNone(checkpoint.validate_resume({}, current))

    def test_resume_validates_messages_sha256(self):
        import hashlib

        from psicotest.spec import canonical_json

        turns = battery_layout(3, "A")[:3]
        responses = [{"content": f"answer {t.turn}"} for t in turns]
        messages = checkpoint.rebuild_messages(turns, responses)
        manual = hashlib.sha256(canonical_json(messages)).hexdigest()
        self.assertEqual(checkpoint.canonical_hash(messages), manual)
        tampered = checkpoint.rebuild_messages(
            turns, [{"content": "answer " + str(t.turn) + " x"} for t in turns]
        )
        self.assertNotEqual(checkpoint.canonical_hash(tampered), manual)
        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[0]["content"], turns[0].prompt_en)
        with tempfile.TemporaryDirectory() as tmp:
            layout = battery_layout(7, "A")
            responses = [{"content": f"answer {t.turn}"} for t in layout[:2]]
            history = []
            records = []
            for turn, response in zip(layout[:2], responses, strict=False):
                history.append({"role": "user", "content": turn.prompt_en})
                record = sample_turn(turn.turn)
                record["request"]["n_messages"] = len(history)
                record["request"]["messages_sha256"] = checkpoint.canonical_hash(history)
                record["response"]["content"] = response["content"]
                records.append(record)
                history.append({"role": "assistant", "content": response["content"]})
            records[-1]["request"]["messages_sha256"] = "tampered"
            header = sample_header()
            header["manifest_sha256"] = checkpoint.canonical_hash(list(SLOTS_V5))
            path = Path(tmp) / "v5_7_A.jsonl"
            checkpoint.write_header(path, header)
            for record in records:
                checkpoint.write_turn(path, record)
            server = fakes.FakeServer("oracle", layout)
            transport = FakeServerTransport(server)
            code = run_battery(
                transport=transport,
                base_url="http://fake/v1",
                model="fake-model",
                api_key=API_KEY,
                seed=7,
                order="A",
                out_dir=tmp,
                resume=True,
            )
            self.assertEqual(code, driver.EXIT_INTERNAL)

    def test_resume_completed_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            turns = battery_layout(7, "A")
            server = fakes.FakeServer("oracle", turns)
            transport = FakeServerTransport(server)
            with mock.patch("psicotest.runner.client._wait", lambda delay: None):
                code = run_battery(
                    transport=transport,
                    base_url="http://fake/v1",
                    model="fake-model",
                    api_key=API_KEY,
                    seed=7,
                    order="A",
                    out_dir=tmp,
                )
            self.assertEqual(code, driver.EXIT_OK)
            path = Path(tmp) / "v5_7_A.jsonl"
            before = path.read_bytes()
            server2 = fakes.FakeServer("oracle", turns)
            transport2 = FakeServerTransport(server2)
            code = run_battery(
                transport=transport2,
                base_url="http://fake/v1",
                model="fake-model",
                api_key=API_KEY,
                seed=7,
                order="A",
                out_dir=tmp,
                resume=True,
            )
            self.assertEqual(code, driver.EXIT_OK)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
