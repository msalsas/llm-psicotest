import dataclasses
import json
import time

from psicotest.runner.transport import (
    AuthError,
    ProtocolError,
    Transport,
    TransportError,
)

RETRY_DELAYS = (10, 30, 90)
MAX_ATTEMPTS = 4
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
DEFAULT_MAX_TOKENS = 6144
DEFAULT_TIMEOUT = 240
DEFAULT_TEMPERATURE = 6 / 10
DEFAULT_TOP_P = 95 / 100


def _wait(delay):
    time.sleep(delay)


def _fail(exc, kind, http_status=None, attempts=None):
    exc.kind = kind
    exc.http_status = http_status
    exc.attempts = attempts
    return exc


def build_request_body(
    model: str,
    messages: list[dict],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: "float" = DEFAULT_TEMPERATURE,
    top_p: "float" = DEFAULT_TOP_P,
    seed: int | None = None,
) -> dict:
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }
    if seed is not None:
        body["seed"] = seed
    return body


@dataclasses.dataclass(frozen=True)
class Response:
    status: int
    model: str
    content: str
    reasoning_content: str | None
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int | None
    raw: dict


class Client:
    def __init__(
        self,
        transport: Transport,
        base_url: str,
        model: str,
        api_key: str,
        auth_scheme: str = "bearer",
        timeout: "float" = DEFAULT_TIMEOUT,
    ):
        if auth_scheme not in ("bearer", "x-api-key"):
            raise ValueError("unknown auth scheme")
        self._transport = transport
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        if auth_scheme == "bearer":
            self._headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        else:
            self._headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json",
            }
        self._last_prompt_tokens = None
        self._last_attempts = 0
        self._last_errors = []

    def _observe_prompt_tokens(self, value: int) -> None:
        self._last_prompt_tokens = value

    def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: "float" = DEFAULT_TEMPERATURE,
        top_p: "float" = DEFAULT_TOP_P,
        seed: int | None = None,
    ) -> Response:
        body = build_request_body(
            self._model,
            list(messages),
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
        )
        payload = json.dumps(body).encode("utf-8")
        url = self._base_url + "/chat/completions"
        self._last_errors = []
        attempt = 0
        while True:
            attempt += 1
            try:
                status, _headers, rbody = self._transport.request(
                    "POST", url, self._headers, payload, self._timeout
                )
            except TransportError as exc:
                kind = getattr(exc, "kind", "connect")
                self._last_errors.append(
                    {
                        "attempt": attempt,
                        "kind": kind,
                        "http_status": getattr(exc, "http_status", None),
                        "message": str(exc),
                    }
                )
                if attempt < MAX_ATTEMPTS:
                    _wait(RETRY_DELAYS[attempt - 1])
                    continue
                raise _fail(exc, kind, getattr(exc, "http_status", None), attempt) from exc
            if status in RETRYABLE_STATUSES:
                kind = "http_429" if status == 429 else "http_5xx"
                self._last_errors.append(
                    {
                        "attempt": attempt,
                        "kind": kind,
                        "http_status": status,
                        "message": f"http status {status}",
                    }
                )
                if attempt < MAX_ATTEMPTS:
                    _wait(RETRY_DELAYS[attempt - 1])
                    continue
                raise _fail(TransportError(f"http status {status}"), kind, status, attempt)
            if status in (401, 403):
                raise _fail(AuthError(f"http status {status}"), "http_4xx", status, attempt)
            if status == 400:
                raise _fail(ProtocolError("http status 400"), "http_4xx", status, attempt)
            if status != 200:
                raise _fail(TransportError(f"http status {status}"), "http_4xx", status, attempt)
            try:
                data = json.loads(rbody)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise _fail(
                    ProtocolError("non-JSON response body"), "protocol", None, attempt
                ) from exc
            if not isinstance(data, dict) or not data.get("choices"):
                raise _fail(ProtocolError("missing choices"), "protocol", None, attempt)
            if data.get("model") != self._model:
                raise _fail(ProtocolError("response model mismatch"), "protocol", None, attempt)
            choice = data["choices"][0]
            if not isinstance(choice, dict):
                raise _fail(ProtocolError("bad choice payload"), "protocol", None, attempt)
            message = choice.get("message") or {}
            usage = data.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens") or 0
            completion_tokens = usage.get("completion_tokens") or 0
            details = usage.get("completion_tokens_details") or {}
            reasoning_tokens = details.get("reasoning_tokens")
            if self._last_prompt_tokens is not None and prompt_tokens < self._last_prompt_tokens:
                raise _fail(ProtocolError("prompt tokens decreased"), "protocol", None, attempt)
            content = message.get("content")
            if content is None:
                content = ""
            finish_reason = choice.get("finish_reason")
            if finish_reason is None:
                raise _fail(ProtocolError("missing finish_reason"), "protocol", None, attempt)
            self._last_prompt_tokens = prompt_tokens
            self._last_attempts = attempt
            return Response(
                status=status,
                model=data.get("model"),
                content=content,
                reasoning_content=message.get("reasoning_content"),
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                raw=data,
            )
