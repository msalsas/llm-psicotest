import json
import urllib.parse

import _bootstrap
import fakes

from psicotest.runner.transport import TransportError


class FakeServerTransport:
    def __init__(self, server: fakes.FakeServer):
        self.server = server

    def request(self, method, url, headers, body, timeout):
        path = urllib.parse.urlparse(url).path
        payload = json.loads(body) if body else None
        try:
            status, response = self.server.handle(method, path, headers, payload)
        except fakes.FakeDisconnect as exc:
            error = TransportError("fake disconnect")
            error.kind = "connect"
            raise error from exc
        return status, {"content-type": "application/json"}, json.dumps(response).encode("utf-8")
