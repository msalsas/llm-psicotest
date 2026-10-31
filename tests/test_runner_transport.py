import json
import unittest
import urllib.error
from unittest import mock

import _bootstrap

from psicotest.runner.client import Client
from psicotest.runner.transport import (
    AuthError,
    HTTPTransport,
    ProtocolError,
    Transport,
    TransportError,
)


class FakeResponse:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _usage_body(model="fake-model"):
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "ANSWER: 1"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
        },
    }


class TestTransport(unittest.TestCase):
    def test_transport_protocol_signature(self):
        self.assertTrue(hasattr(Transport, "request"))
        signature = Transport.request
        self.assertEqual(signature.__name__, "request")
        transport = HTTPTransport(timeout=5)
        self.assertEqual(transport._timeout, 5)

    def test_http_transport_builds_request(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(200, {"content-type": "application/json"}, b"{}")

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            transport = HTTPTransport()
            result = transport.request(
                "POST",
                "http://localhost:9/v1/chat/completions",
                {"Authorization": "Bearer key"},
                b"{}",
                25,
            )
        self.assertEqual(result[0], 200)
        request = captured["request"]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, "http://localhost:9/v1/chat/completions")
        self.assertEqual(request.data, b"{}")
        self.assertEqual(request.headers["Authorization"], "Bearer key")
        self.assertEqual(captured["timeout"], 25)

    def test_http_transport_parses_response(self):
        body = b'{"ok": true}'

        def fake_urlopen(request, timeout):
            return FakeResponse(200, {"content-type": "application/json"}, body)

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            transport = HTTPTransport()
            status, headers, payload = transport.request(
                "GET", "http://localhost:9/v1/models", {}, None, 10
            )
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(payload, body)

    def test_http_transport_timeout_handling(self):
        def timeout_urlopen(request, timeout):
            raise TimeoutError("timed out")

        with mock.patch("urllib.request.urlopen", timeout_urlopen):
            transport = HTTPTransport()
            with self.assertRaises(TransportError) as caught:
                transport.request("POST", "http://x/", {}, b"", 1)
        self.assertEqual(caught.exception.kind, "timeout")

        def urlerror_urlopen(request, timeout):
            raise urllib.error.URLError(TimeoutError("slow"))

        with mock.patch("urllib.request.urlopen", urlerror_urlopen):
            transport = HTTPTransport()
            with self.assertRaises(TransportError) as caught:
                transport.request("POST", "http://x/", {}, b"", 1)
        self.assertEqual(caught.exception.kind, "timeout")

        def read_timeout_urlopen(request, timeout):
            class ReadTimeoutResponse:
                def read(self):
                    raise TimeoutError("timed out")

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

            return ReadTimeoutResponse()

        with mock.patch("urllib.request.urlopen", read_timeout_urlopen):
            transport = HTTPTransport()
            with self.assertRaises(TransportError) as caught:
                transport.request("POST", "http://x/", {}, b"", 1)
        self.assertEqual(caught.exception.kind, "timeout")

        def refused_urlopen(request, timeout):
            raise urllib.error.URLError("connection refused")

        with mock.patch("urllib.request.urlopen", refused_urlopen):
            transport = HTTPTransport()
            with self.assertRaises(TransportError) as caught:
                transport.request("POST", "http://x/", {}, b"", 1)
        self.assertEqual(caught.exception.kind, "connect")

    def test_transport_error_types(self):
        self.assertTrue(issubclass(AuthError, TransportError))
        self.assertTrue(issubclass(ProtocolError, TransportError))
        self.assertFalse(issubclass(AuthError, ProtocolError))
        self.assertFalse(issubclass(ProtocolError, AuthError))
        self.assertTrue(isinstance(AuthError("x"), Exception))
        self.assertTrue(isinstance(ProtocolError("x"), Exception))

    def test_auth_header_schemes(self):
        class Recorder:
            def __init__(self):
                self.headers = []

            def request(self, method, url, headers, body, timeout):
                self.headers.append(headers)
                return (
                    200,
                    {"content-type": "application/json"},
                    json.dumps(_usage_body()).encode("utf-8"),
                )

        recorder = Recorder()
        client = Client(recorder, "http://fake/v1", "fake-model", "secret-key")
        client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(recorder.headers[-1]["Authorization"], "Bearer secret-key")

        client = Client(
            recorder,
            "http://fake/v1",
            "fake-model",
            "secret-key",
            auth_scheme="x-api-key",
        )
        client.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(recorder.headers[-1]["x-api-key"], "secret-key")
        self.assertNotIn("Authorization", recorder.headers[-1])


if __name__ == "__main__":
    unittest.main()
