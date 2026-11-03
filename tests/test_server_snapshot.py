import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap
import fakes
from fake_transport import FakeServerTransport

from psicotest.runner import driver
from psicotest.runner.battery import battery_layout
from psicotest.runner.client import Client, null_server_snapshot
from psicotest.runner.transport import TransportError

API_KEY = "fake-key-0123456789"

STRATA = {
    "object": "list",
    "data": [
        {
            "id": "iq3_s",
            "owned_by": "strata",
            "meta": {
                "instanceId": "inst-1",
                "gpus": [0],
                "label": "Qwen3.8-Flash-Next IQ3_S",
                "aliases": ["iq3_s"],
            },
        }
    ],
}


def ok_body(model, content="ANSWER: 1"):
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


class ScriptTransport:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def request(self, method, url, headers, body, timeout):
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "body": body, "timeout": timeout}
        )
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        status, payload = item
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        return status, {"content-type": "application/json"}, data


class Intercept:
    def __init__(self, inner, on_get):
        self.inner = inner
        self.on_get = on_get
        self.n_gets = 0

    def request(self, method, url, headers, body, timeout):
        if method == "GET" and url.endswith("/models"):
            self.n_gets += 1
            return self.on_get()
        return self.inner.request(method, url, headers, body, timeout)


def load_records(path):
    records = []
    for line in Path(path).read_text("utf-8").splitlines():
        records.append(json.loads(line))
    return records


def drive_snapshot(persona, out_dir, on_get=None, resume=False):
    turns = battery_layout(7, "A")
    server = fakes.FakeServer(persona, turns)
    inner = FakeServerTransport(server)
    transport = Intercept(inner, on_get) if on_get is not None else inner
    with mock.patch("psicotest.runner.client._wait", lambda delay: None):
        code = driver.run_battery(
            transport=transport,
            base_url="http://fake/v1",
            model="fake-model",
            api_key=API_KEY,
            seed=7,
            order="A",
            out_dir=out_dir,
            resume=resume,
        )
    return code, transport


class TestClientSnapshot(unittest.TestCase):
    def test_snapshot_ok_strata_payload(self):
        transport = ScriptTransport([(200, STRATA)])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key")
        self.assertEqual(
            client.server_snapshot(),
            {
                "status": "ok",
                "http_status": 200,
                "model_id": "iq3_s",
                "owned_by": "strata",
                "label": "Qwen3.8-Flash-Next IQ3_S",
                "instance_id": "inst-1",
                "gpus": [0],
                "aliases": ["iq3_s"],
            },
        )
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["url"], "http://fake/v1/models")
        self.assertIsNone(call["body"])
        self.assertEqual(call["timeout"], 30)
        self.assertEqual(call["headers"]["Authorization"], "Bearer secret-key")

    def test_snapshot_alias_match(self):
        data = [{"id": "other"}, {"id": "q-int", "meta": {"aliases": ["iq3_s"]}}]
        transport = ScriptTransport([(200, {"object": "list", "data": data})])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key")
        snapshot = client.server_snapshot()
        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["model_id"], "q-int")
        self.assertEqual(snapshot["aliases"], ["iq3_s"])

    def test_snapshot_model_not_listed(self):
        transport = ScriptTransport([(200, {"object": "list", "data": [{"id": "other"}]})])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key")
        self.assertEqual(client.server_snapshot(), null_server_snapshot("model_not_listed", 200))

    def test_snapshot_http_404(self):
        transport = ScriptTransport([(404, {"error": "not found"})])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key")
        self.assertEqual(client.server_snapshot(), null_server_snapshot("http_error", 404))

    def test_snapshot_transport_error(self):
        transport = ScriptTransport([TransportError("x")])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key")
        self.assertEqual(client.server_snapshot(), null_server_snapshot("transport_error"))

    def test_snapshot_bad_payload(self):
        transport = ScriptTransport([(200, b"not json")])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key")
        self.assertEqual(client.server_snapshot(), null_server_snapshot("bad_payload", 200))
        transport = ScriptTransport([(200, {"data": "x"})])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key")
        self.assertEqual(client.server_snapshot(), null_server_snapshot("bad_payload", 200))

    def test_snapshot_bad_types(self):
        data = [{"id": "iq3_s", "meta": {"gpus": ["0"], "aliases": [1], "label": 5}}]
        transport = ScriptTransport([(200, {"object": "list", "data": data})])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key")
        snapshot = client.server_snapshot()
        self.assertEqual(snapshot["status"], "ok")
        for key in ("gpus", "aliases", "label", "instance_id", "owned_by"):
            self.assertIsNone(snapshot[key])

    def test_snapshot_leaves_chat_state(self):
        transport = ScriptTransport([(200, STRATA), (200, ok_body("iq3_s"))])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key")
        client.server_snapshot()
        self.assertEqual(client._last_errors, [])
        self.assertIsNone(client._last_prompt_tokens)
        self.assertEqual(client._last_attempts, 0)
        response = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(response.content, "ANSWER: 1")
        call = transport.calls[1]
        self.assertTrue(call["url"].endswith("/chat/completions"))
        self.assertEqual(
            set(json.loads(call["body"])),
            {"model", "messages", "max_tokens", "temperature", "top_p"},
        )

    def test_snapshot_x_api_key_scheme(self):
        transport = ScriptTransport([(200, STRATA)])
        client = Client(transport, "http://fake/v1", "iq3_s", "secret-key", auth_scheme="x-api-key")
        client.server_snapshot()
        call = transport.calls[0]
        self.assertEqual(call["headers"]["x-api-key"], "secret-key")
        self.assertNotIn("Authorization", call["headers"])


class TestDriverSnapshot(unittest.TestCase):
    def test_header_snapshot_populated(self):
        payload = {
            "object": "list",
            "data": [
                {
                    "id": "fake-model",
                    "owned_by": "strata",
                    "meta": {
                        "instanceId": "inst-1",
                        "gpus": [0],
                        "label": "Qwen3.8-Flash-Next IQ3_S",
                        "aliases": ["fake-model"],
                    },
                }
            ],
        }

        def on_get():
            return 200, {"content-type": "application/json"}, json.dumps(payload).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            code, _transport = drive_snapshot("oracle", tmp, on_get=on_get)
            self.assertEqual(code, driver.EXIT_OK)
            records = load_records(Path(tmp) / "v6_7_A.jsonl")
            self.assertEqual(records[0]["schema"], 2)
            self.assertEqual(
                records[0]["server"],
                {
                    "status": "ok",
                    "http_status": 200,
                    "model_id": "fake-model",
                    "owned_by": "strata",
                    "label": "Qwen3.8-Flash-Next IQ3_S",
                    "instance_id": "inst-1",
                    "gpus": [0],
                    "aliases": ["fake-model"],
                },
            )
            turn_records = [record for record in records if record["type"] == "turn"]
            self.assertEqual(len(turn_records), 38)
            report = json.loads((Path(tmp) / "v6_7_A.report.json").read_text("utf-8"))
            self.assertEqual(report["server"], records[0]["server"])
            self.assertEqual(report["capability"]["score"], 29)
            self.assertEqual(list(records[0])[-1], "server")

    def test_header_snapshot_failure_nulls_run_continues(self):
        def on_get():
            raise TransportError("x")

        with tempfile.TemporaryDirectory() as tmp:
            code, _transport = drive_snapshot("oracle", tmp, on_get=on_get)
            self.assertEqual(code, driver.EXIT_OK)
            records = load_records(Path(tmp) / "v6_7_A.jsonl")
            self.assertEqual(records[0]["server"], null_server_snapshot("transport_error"))
            turn_records = [record for record in records if record["type"] == "turn"]
            self.assertEqual(len(turn_records), 38)
            self.assertEqual(records[-1]["type"], "footer")
            report = json.loads((Path(tmp) / "v6_7_A.report.json").read_text("utf-8"))
            self.assertEqual(report["capability"]["score"], 29)

    def test_header_snapshot_default_fake_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _transport = drive_snapshot("oracle", tmp)
            self.assertEqual(code, driver.EXIT_OK)
            records = load_records(Path(tmp) / "v6_7_A.jsonl")
            server = records[0]["server"]
            self.assertEqual(server["status"], "ok")
            self.assertEqual(server["model_id"], "fake-model")
            for key in ("owned_by", "label", "instance_id", "gpus", "aliases"):
                self.assertIsNone(server[key])

    def test_resume_does_not_refetch(self):
        def on_get():
            raise AssertionError("unexpected GET /models during resume")

        with tempfile.TemporaryDirectory() as tmp:
            code, _transport = drive_snapshot("crasher", tmp)
            self.assertEqual(code, driver.EXIT_TRANSPORT)
            checkpoint_path = Path(tmp) / "v6_7_A.jsonl"
            before = load_records(checkpoint_path)
            code, transport = drive_snapshot("oracle", tmp, on_get=on_get, resume=True)
            self.assertEqual(code, driver.EXIT_OK)
            self.assertEqual(transport.n_gets, 0)
            after = load_records(checkpoint_path)
            self.assertEqual(after[0], before[0])

    def test_snapshot_redacted_if_key_echoed(self):
        payload = {
            "object": "list",
            "data": [
                {
                    "id": "fake-model",
                    "owned_by": "strata",
                    "meta": {
                        "instanceId": "inst-1",
                        "gpus": [0],
                        "label": "served by " + API_KEY,
                        "aliases": ["fake-model"],
                    },
                }
            ],
        }

        def on_get():
            return 200, {"content-type": "application/json"}, json.dumps(payload).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            code, _transport = drive_snapshot("oracle", tmp, on_get=on_get)
            self.assertEqual(code, driver.EXIT_OK)
            records = load_records(Path(tmp) / "v6_7_A.jsonl")
            self.assertEqual(records[0]["server"], null_server_snapshot("redacted", 200))


if __name__ == "__main__":
    unittest.main()
