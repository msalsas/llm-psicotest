import http.client
import ssl
import urllib.error
import urllib.request
from typing import Protocol


class TransportError(Exception):
    pass


class AuthError(TransportError):
    pass


class ProtocolError(TransportError):
    pass


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: "float",
    ) -> tuple[int, dict[str, str], bytes]: ...


def _with_kind(exc: TransportError, kind: str) -> TransportError:
    exc.kind = kind
    return exc


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code in (301, 302, 303, 307, 308):
            raise ProtocolError(f"redirect {code} refused")
        return None


class HTTPTransport:
    def __init__(self, timeout: "float" = 120):
        self._timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect())
        urllib.request.install_opener(self._opener)

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: "float",
    ) -> tuple[int, dict[str, str], bytes]:
        request = urllib.request.Request(url, data=body, headers=dict(headers or {}), method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                try:
                    payload = response.read()
                except TimeoutError as exc:
                    raise _with_kind(TransportError(str(exc) or "timeout"), "timeout") from exc
                except (OSError, http.client.HTTPException) as exc:
                    raise _with_kind(TransportError(str(exc)), "read") from exc
                return response.status, dict(response.headers), payload
        except urllib.error.HTTPError as exc:
            try:
                payload = exc.read()
            except (OSError, http.client.HTTPException) as read_exc:
                raise _with_kind(TransportError(str(read_exc)), "connect") from read_exc
            return exc.code, dict(exc.headers or {}), payload
        except TimeoutError as exc:
            raise _with_kind(TransportError(str(exc) or "timeout"), "timeout") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise _with_kind(TransportError(str(exc.reason) or "timeout"), "timeout") from exc
            raise _with_kind(TransportError(str(exc)), "connect") from exc
        except ssl.SSLError as exc:
            raise _with_kind(TransportError(str(exc)), "connect") from exc
        except OSError as exc:
            raise _with_kind(TransportError(str(exc)), "connect") from exc
