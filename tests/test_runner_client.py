import json
import unittest
from unittest import mock

import _bootstrap

from psicotest.runner import client as client_module
from psicotest.runner.client import Client
from psicotest.runner.transport import AuthError, ProtocolError, TransportError


def ok_body(
    model="fake-model",
    content="ANSWER: 1",
    prompt_tokens=10,
    completion_tokens=5,
    reasoning_tokens=None,
    reasoning_content=None,
):
    message = {"role": "assistant", "content": content}
    if reasoning_content is not None:
        message["reasoning_content"] = reasoning_content
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    if reasoning_tokens is not None:
        usage["completion_tokens_details"] = {"reasoning_tokens": reasoning_tokens}
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": usage,
    }


class FakeTransport:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def request(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        status, payload = item
        return status, {"content-type": "application/json"}, json.dumps(payload).encode("utf-8")


def make_client(script, **kwargs):
    transport = FakeTransport(script)
    client = Client(transport, "http://fake/v1", "fake-model", "secret-key", **kwargs)
    return client, transport


class TestClient(unittest.TestCase):
    def test_client_with_fake_transport(self):
        client, transport = make_client([(200, ok_body(content="ANSWER: 7"))])
        response = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(response.status, 200)
        self.assertEqual(response.model, "fake-model")
        self.assertEqual(response.content, "ANSWER: 7")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.prompt_tokens, 10)
        self.assertEqual(response.completion_tokens, 5)
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], "http://fake/v1/chat/completions")
        body = json.loads(call["body"])
        self.assertEqual(body["model"], "fake-model")
        self.assertEqual(body["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(body["max_tokens"], 6144)
        self.assertEqual(body["temperature"], 0.6)
        self.assertEqual(body["top_p"], 0.95)
        self.assertNotIn("seed", body)

    def test_client_retries_on_5xx(self):
        client, transport = make_client([(503, {}), (500, {}), (502, {}), (504, {})])
        delays = []
        with (
            mock.patch.object(client_module, "_wait", delays.append),
            self.assertRaises(TransportError) as caught,
        ):
            client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(delays, [10, 30, 90])
        self.assertEqual(len(transport.calls), 4)
        self.assertEqual(caught.exception.kind, "http_5xx")
        self.assertEqual(caught.exception.http_status, 504)
        self.assertEqual(caught.exception.attempts, 4)
        self.assertEqual(len(client._last_errors), 4)

    def test_client_retries_on_429(self):
        client, transport = make_client([(429, {}), (200, ok_body())])
        delays = []
        with mock.patch.object(client_module, "_wait", delays.append):
            response = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(delays, [10])
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(response.status, 200)
        self.assertEqual(client._last_errors[0]["kind"], "http_429")
        self.assertEqual(client._last_attempts, 2)

    def test_client_no_retry_on_401(self):
        client, transport = make_client([(401, {"error": "unauthorized"})])
        delays = []
        with mock.patch.object(client_module, "_wait", delays.append), self.assertRaises(AuthError):
            client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(delays, [])
        self.assertEqual(len(transport.calls), 1)

    def test_client_no_retry_on_400(self):
        client, transport = make_client([(400, {"error": "bad request"})])
        delays = []
        with (
            mock.patch.object(client_module, "_wait", delays.append),
            self.assertRaises(ProtocolError),
        ):
            client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(delays, [])
        self.assertEqual(len(transport.calls), 1)

    def test_client_prompt_tokens_monotonic(self):
        client, _transport = make_client(
            [(200, ok_body(prompt_tokens=100)), (200, ok_body(prompt_tokens=50))]
        )
        client.chat([{"role": "user", "content": "one"}])
        with self.assertRaises(ProtocolError):
            client.chat(
                [
                    {"role": "user", "content": "one"},
                    {"role": "assistant", "content": "ANSWER: 1"},
                    {"role": "user", "content": "two"},
                ]
            )
        client, _transport = make_client(
            [(200, ok_body(prompt_tokens=100)), (200, ok_body(prompt_tokens=120))]
        )
        client.chat([{"role": "user", "content": "one"}])
        response = client.chat(
            [
                {"role": "user", "content": "one"},
                {"role": "assistant", "content": "ANSWER: 1"},
                {"role": "user", "content": "two"},
            ]
        )
        self.assertEqual(response.prompt_tokens, 120)

    def test_client_model_mismatch_error(self):
        client, _transport = make_client([(200, ok_body(model="other-model"))])
        with self.assertRaises(ProtocolError):
            client.chat([{"role": "user", "content": "hi"}])

    def test_client_extracts_reasoning_content(self):
        client, _transport = make_client(
            [
                (
                    200,
                    ok_body(
                        reasoning_content="thinking",
                        reasoning_tokens=7,
                    ),
                )
            ]
        )
        response = client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(response.reasoning_content, "thinking")
        self.assertEqual(response.reasoning_tokens, 7)
        client, _transport = make_client([(200, ok_body())])
        response = client.chat([{"role": "user", "content": "hi"}])
        self.assertIsNone(response.reasoning_content)
        self.assertIsNone(response.reasoning_tokens)


if __name__ == "__main__":
    unittest.main()
