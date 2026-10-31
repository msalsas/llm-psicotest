# T4 implementation contract: `runner/` package, CLI `run` subcommand, session report

This contract covers T4 from DESIGN v2 §14. DESIGN.md is the source of truth. This document makes exact: the OpenAI-compatible HTTP client, the conversation driver, per-turn scoring via existing checkers, the session report schema, the CLI `run` subcommand, injectable transports for testing, retry policy and exit codes. Lines marked `HOLE:` are places where DESIGN does not fix the behaviour. Each one states the default this contract pins and the decision the owner needs to confirm.

---

## 0. Global rules (non-negotiable)

- Python ≥ 3.11. **Runtime code uses stdlib only.** No new dependencies. Allowed modules in `runner/`: `urllib.request`, `urllib.error`, `urllib.parse`, `ssl`, `socket`, `http.client`, `json`, `dataclasses`, `hashlib`, `time`, `os`, `sys`, `typing`, `collections.abc`, `contextlib`, `pathlib`.
- **Zero comments**: no `#` lines and no docstrings in any T4 file under `src/psicotest/runner/`. No docstrings in `cli.py` additions.
- `unittest` only. Every test module starts with the T1 import layout (`import unittest`, blank line, `import _bootstrap`, blank line, first-party imports).
- Every file under `src/psicotest/runner/` must pass `tests/test_banned_constructs.py`. That rules out `random`, `hash`, `id`, float literals in non-report paths, time-dependent tests and socket-opening tests.
- **Pure ASCII source.** Every byte of every T4 `*.py` file under `src/` is `< 0x80`.
- **Lint.** Use ruff 0.17.1 from repo root. `ruff check .` and `ruff format --check .` must be clean.
- Floats are allowed only in timing fields (`wall_s`, `effective_tok_s`) and the session report's `telemetry` section. All other numerics use `int`, `Decimal` or `Fraction`.
- The battery for a run is exactly the 26 slots of `SLOTS_V2` in slot order, materialized through `generators.build_slot_item`, candidate surface in English v2.
- Transport is injectable (a one-method protocol class) so unit tests drive fake transports; unit and property tests never open a network socket.
- Live-server behavior is exercised only by `tools/run_live.py`, excluded from CI.
- Telemetry: reuse `checkers.telemetry.measure` as-is; do not redesign it.

---

## 1. Files and public API

### 1.1 Files

| Action | Path |
|---|---|
| create | `src/psicotest/runner/__init__.py` |
| create | `src/psicotest/runner/transport.py` (Transport protocol, HTTPTransport, errors) |
| create | `src/psicotest/runner/client.py` (Client class) |
| create | `src/psicotest/runner/driver.py` (conversation driver) |
| create | `src/psicotest/runner/checkpoint.py` (JSONL writer, reader, resume logic) |
| create | `src/psicotest/runner/report.py` (session report writer) |
| create | `src/psicotest/runner/battery.py` (battery_layout, turn builder) |
| modify | `src/psicotest/cli.py` (add `run` subcommand) |
| create | `tools/run_live.py` (opt-in live script) |
| create | `tests/test_runner_transport.py` |
| create | `tests/test_runner_client.py` |
| create | `tests/test_runner_driver.py` |
| create | `tests/test_runner_checkpoint.py` |
| create | `tests/test_runner_report.py` |
| create | `tests/test_runner_battery.py` |
| create | `tests/test_runner_integration.py` |
| create | `tests/test_cli_run.py` |
| modify | `tests/test_banned_constructs.py`: add `runner/` modules to scan set |

That is 7 created source files, 8 test files and 2 modified files.

Do not touch `rng.py`, `spec.py`, `checkers/`, `generators/` (except imports), the CI workflow or `batteries/`.

### 1.2 Import DAG

```
transport   <- (stdlib only)
client      <- transport, spec
checkpoint  <- spec, client
battery     <- generators.slots, generators.factory, generators.rules_text,
               generators.missing_datum, generators.lexicon, spec, rng
driver      <- spec, client, checkpoint, battery, checkers.registry,
               checkers.rules, checkers.telemetry
report      <- spec, checkpoint, driver
__init__    <- transport, client, driver, checkpoint, report, battery
cli         <- runner (all exports)
```

### 1.3 `runner/__init__.py`

Contains only re-exports and a sorted `__all__`:

```python
__all__ = [
    "AuthError",
    "Client",
    "HTTPTransport",
    "ProtocolError",
    "Transport",
    "TransportError",
    "battery_layout",
    "build_turns",
    "load_checkpoint",
    "run_battery",
    "write_report",
]
```

---

## 2. Pinned constants and tables

### 2.1 Exit codes (DESIGN §2.4)

```python
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_TRANSPORT = 4
EXIT_PREFLIGHT = 5
EXIT_RESUME_MISMATCH = 6
EXIT_PROTOCOL = 7
EXIT_SELFTEST = 8
EXIT_INCOMPATIBLE = 9
```

This contract uses only `EXIT_OK`, `EXIT_AUTH`, `EXIT_TRANSPORT`, `EXIT_PROTOCOL` and `EXIT_INTERNAL`. The others are defined for forward compatibility.

### 2.2 Retry policy (DESIGN §12.4)

```python
RETRY_DELAYS = (10, 30, 90)  # seconds
MAX_ATTEMPTS = 4  # 1 initial + 3 retries
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
```

- Connect error, timeout, HTTP 5xx, 429 → retry after delays[attempt], then exit 4.
- HTTP 401/403 → no retry, exit 3.
- HTTP 400, non-JSON body, missing `choices`, response `model` != configured → no retry, exit 7.
- `prompt_tokens` < previous turn's → exit 7 (silent context truncation).
- Timeout uses `time.monotonic()` for the interval; scored paths never depend on wall clock.

### 2.3 Request payload builder

```python
def build_request_body(
    model: str,
    messages: list[dict],
    *,
    max_tokens: int = 6144,
    temperature: float = 0.6,
    top_p: float = 0.95,
    seed: int | None = None,
) -> dict:
```

Returns:
```python
{
    "model": model,
    "messages": messages,
    "max_tokens": max_tokens,
    "temperature": temperature,
    "top_p": top_p,
    **({"seed": seed} if seed is not None else {}),
}
```

Optional fields (`reasoning_effort`, `top_k`, `min_p`) are not sent unless explicitly passed. The client adds them only when the caller provides them.

### 2.4 Session report schema (§6)

```python
REPORT_SCHEMA_VERSION = 1
```

The report is a JSON object with deterministic key order (explicit ordering, not `sort_keys`). Schema in §6.

---

## 3. Conversation protocol

### 3.1 Turn sequence

The battery has 30 turns, built from `SLOTS_V2` (26 slots) plus the SETUP turn and the AMB-reply scaffolding. The exact sequence per order is defined by `battery_layout(seed, order)` which reuses T3's `tests/battery_layout.py` structure.

| Turn range | Description |
|---|---|
| T1 | SETUP: rules R1, R2, PROTO. User message = `SETUP_TEXT`. Expected reply: `ANSWER: OK` |
| T2-T7 | Capability items (S01-S06) |
| T8 | AMB ask (S07). Expected: `CLARIFICATION: ...` |
| T9 | AMB reply (S07b). User provides datum. Expected: `ANSWER: <value>` |
| T10 | ERR item (S08) |
| T11 | ST item (S09) with R3 rule prepended. User message = `R3_TEXT + "\n\n" + item.prompt_en` |
| T12-T30 | Remaining items per order layout, with R3 active |

### 3.2 R3 trigger turns

Order A: T17, T24, T28, T29.
Order B: T17, T24, T28, T29 (same turn positions, different slots).

On a trigger turn:
1. The item is regenerated with `animal = trigger_animal(battery, seed, order, turn)`.
2. T28 is the AMB-reply trigger: the item is `dataclasses.replace(ask_item, animal=noun)` and the prompt uses `reply_prompt(item)`.

### 3.3 Markers

Per DESIGN §6.1:
- `ANSWER: <value>` — expected on scored turns except AMB asks and TRUNC.
- `CLARIFICATION: <question>` — expected on AMB ask turns.
- `ANIMAL: <name>` — expected on R3+ trigger turns, immediately before ANSWER.

### 3.4 Message history

Each request includes all prior turns' user and assistant `content`. Reasoning content (`reasoning_content`) is never sent back to the model (DESIGN §10.2).

### 3.5 Clarification loop

There is no clarification loop. AMB ask turns expect exactly one `CLARIFICATION:` response. If the model answers instead, the outcome is `CLAR_MISS` and the conversation continues. The AMB reply turn is always sent with the static datum prompt.

---

## 4. Scoring aggregation

### 4.1 Per-turn scoring

Each assistant response is scored using `checkers.check_turn(turn, content, finish_reason, reasoning)` and `checkers.check_rules(content, turn, finish_reason)`.

Telemetry is measured via `checkers.telemetry.measure(content, reasoning)`.

### 4.2 Verdict fields

Per turn, record:
- `outcome`: from `CheckResult.outcome`
- `score`: from `CheckResult.score` (0 or 1 for capability, 0-3 for RCL)
- `value`: from `CheckResult.value`
- `flags`: from `CheckResult.flags`
- `detail`: from `CheckResult.detail`
- `rules`: from `check_rules` dict (`R1`, `R2`, `R3`, `R3_NOTE`)
- `telemetry`: from `measure`

### 4.3 Unscored turns

SETUP (T1) is scored but not included in capability aggregation. AMB ask turns are scored for protocol only. TRUNC turns are scored with `outcome=TRUNC` and excluded from R1/R2 denominators.

### 4.4 Aggregation

For the session report:
- `capability_score`: sum of scores for the 21 capability slots, max 21.
- `family_scores`: per-family breakdown.
- `protocol`: CLAR_OK/CLAR_MISS/CLAR_OVER/CLAR_BAD counts, RCL score.
- `rule_compliance`: R1_OK/R1_FAIL counts, R2_OK/R2_FAIL counts, R3_HIT/R3_MISS/R3_FALSE/R3_CLEAN counts.
- `trunc_count`: number of TRUNC outcomes.

---

## 5. CLI surface

### 5.1 `run` subcommand

```
psicotest run --base-url URL --model NAME --seed N [options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--base-url` | yes | — | OpenAI-compatible base URL (e.g. `http://localhost:8080/v1`) |
| `--model` | yes | — | Model identifier |
| `--seed` | yes | — | Battery seed (int) |
| `--order` | no | `A` | Order A or B |
| `--out` | no | `runs/` | Output directory for checkpoint and report |
| `--max-tokens` | no | 6144 | Max tokens per request |
| `--timeout` | no | 120 | Per-request timeout in seconds |
| `--key-env` | no | `PSICOTEST_API_KEY` | Environment variable holding the API key |
| `--auth` | no | `bearer` | Auth scheme: `bearer` or `x-api-key` |
| `--resume` | no | flag | Resume from existing checkpoint |

### 5.2 Exit behavior

| Condition | Exit code |
|---|---|
| Battery completed and scored | 0 |
| Key env var missing or empty | 3 |
| HTTP 401/403 | 3 |
| Transport failure after retries | 4 |
| HTTP 400, non-JSON, missing choices, model mismatch | 7 |
| `prompt_tokens` decreased | 7 |
| Resume header/hash mismatch | 6 |
| Internal error (checker exception, etc.) | 1 |

### 5.3 Output files

- Checkpoint: `{out}/{battery}_{seed}_{order}.jsonl`
- Report: `{out}/{battery}_{seed}_{order}.report.json`

---

## 6. Session report schema and determinism

### 6.1 Checkpoint JSONL (DESIGN §12.3)

One JSON object per line. Lines are flushed and fsynced after each write.

**Header (line 1):**
```python
{
    "type": "header",
    "schema": 1,
    "battery_version": "v2",
    "manifest_sha256": str,  # sha256(canonical_json(SLOTS_V2_as_dict))
    "psicotest_version": str,
    "python_version": str,
    "platform": str,
    "base_url": str,
    "model": str,
    "auth_scheme": str,  # "bearer" or "x-api-key"
    "key_env": str,  # env var name, never the value
    "seed": int,
    "order": str,
    "params": dict,  # request params minus messages
    "started_at": str,  # UTC ISO 8601
}
```

**Turn record:**
```python
{
    "type": "turn",
    "turn": int,
    "slot": str | None,
    "kind": str,
    "request": {
        "n_messages": int,
        "messages_sha256": str,
        "prompt_chars": int,
        "params_sha256": str,
    },
    "response": {
        "status": int,
        "model": str,
        "content": str,
        "reasoning_content": str | None,
        "finish_reason": str,
        "usage": {
            "prompt_tokens": int,
            "completion_tokens": int,
            "reasoning_tokens": int | None,
        },
    },
    "timing": {
        "started_at": str,
        "wall_s": float,
    },
    "effective_tok_s": float | None,
    "attempts": int,
    "scoring": {
        "outcome": str,
        "score": int,
        "value": object,
        "flags": list[str],
        "detail": str,
    },
    "rules": {
        "R1": str,
        "R2": str,
        "R3": str,
        "R3_NOTE": str,
    },
    "telemetry": dict,  # from measure()
}
```

**Error record:**
```python
{
    "type": "error",
    "turn": int,
    "attempt": int,
    "kind": str,  # "connect", "timeout", "http_5xx", "http_429", "http_4xx", "protocol"
    "http_status": int | None,
    "message": str,  # truncated to 500 chars
}
```

**Footer:**
```python
{
    "type": "footer",
    "completed_at": str,
    "n_turns": 30,
}
```

### 6.2 Session report JSON

Written after the footer. Deterministic: same inputs produce byte-identical output.

```python
{
    "schema": 1,
    "battery_version": "v2",
    "manifest_sha256": str,
    "base_url": str,
    "model": str,
    "seed": int,
    "order": str,
    "started_at": str,
    "completed_at": str,
    "capability": {
        "score": int,
        "max": 21,
        "by_family": {
            "ST": {"score": int, "max": int},
            "AR": {"score": int, "max": int},
            # ... all 10 capability families
        },
    },
    "protocol": {
        "setup_ok": bool,
        "clar_ok": int,
        "clar_miss": int,
        "clar_over": int,
        "clar_bad": int,
        "rcl_score": int,
    },
    "rules": {
        "R1": {"ok": int, "fail": int, "na": int},
        "R2": {"ok": int, "fail": int, "na": int},
        "R3": {"hit": int, "miss": int, "false": int, "clean": int, "na": int},
    },
    "trunc_count": int,
    "tokens": {
        "prompt_total": int,
        "completion_total": int,
        "reasoning_total": int,
    },
    "timing": {
        "wall_s_total": float,
        "wall_s_mean": float,
    },
    "telemetry": {
        "leak_chars": int,
        "loop_count": int,
        "selfcorr_total": int,
    },
    "errors": [
        {"turn": int, "attempts": int, "last_kind": str},
    ],
}
```

Key ordering is explicit via `collections.OrderedDict` or by building the dict in definition order (Python 3.7+ dict ordering). No `sort_keys=True` is used—the order matches the schema above.

### 6.3 Determinism guarantees

- `messages_sha256` = `sha256(canonical_json(messages))`.
- `params_sha256` = `sha256(canonical_json(params))`.
- `manifest_sha256` = `sha256(canonical_json(slots_as_list_of_dicts))`.
- Report content is fully determined by the checkpoint content.
- Wall times and ISO timestamps are recorded but do not affect any scored field.

---

## 7. Test strategy

### 7.1 Test files and method counts

The existing test suite has 272 methods across T1+T2+T2.5+T3. T4 adds at least 30 and at most 45 new methods.

| File | Methods | Description |
|---|---|---|
| `test_runner_transport.py` | 6 | Transport protocol, HTTPTransport mock |
| `test_runner_client.py` | 8 | Client class with fake transport |
| `test_runner_driver.py` | 6 | Conversation driver logic |
| `test_runner_checkpoint.py` | 5 | JSONL read/write, resume |
| `test_runner_report.py` | 4 | Report generation |
| `test_runner_battery.py` | 4 | Battery layout, turn builder |
| `test_runner_integration.py` | 5 | End-to-end with fakes |
| `test_cli_run.py` | 4 | CLI argument parsing, exit codes |
| **Total** | **42** | |

### 7.2 `tests/test_runner_transport.py`

```python
class TestTransport(unittest.TestCase):
    def test_transport_protocol_signature(self): ...
    def test_http_transport_builds_request(self): ...
    def test_http_transport_parses_response(self): ...
    def test_http_transport_timeout_handling(self): ...
    def test_transport_error_types(self): ...
    def test_auth_header_schemes(self): ...
```

- No socket is opened; `HTTPTransport` is tested via monkeypatched `urllib.request.urlopen`.
- `TransportError`, `AuthError`, `ProtocolError` are distinct exception types.

### 7.3 `tests/test_runner_client.py`

```python
class TestClient(unittest.TestCase):
    def test_client_with_fake_transport(self): ...
    def test_client_retries_on_5xx(self): ...
    def test_client_retries_on_429(self): ...
    def test_client_no_retry_on_401(self): ...
    def test_client_no_retry_on_400(self): ...
    def test_client_prompt_tokens_monotonic(self): ...
    def test_client_model_mismatch_error(self): ...
    def test_client_extracts_reasoning_content(self): ...
```

- Uses a `FakeTransport` that returns canned responses.
- Retry delays are not time-waited; the test asserts the delay value passed.

### 7.4 `tests/test_runner_driver.py`

```python
class TestDriver(unittest.TestCase):
    def test_driver_oracle_full_run(self): ...
    def test_driver_scores_each_turn(self): ...
    def test_driver_handles_trunc(self): ...
    def test_driver_r3_triggers(self): ...
    def test_driver_amb_protocol(self): ...
    def test_driver_history_excludes_reasoning(self): ...
```

- Uses `fakes.FakeServer` with persona `oracle` via a transport adapter.
- Asserts 21/21 capability, 3 CLAR_OK, R3 4 HIT.

### 7.5 `tests/test_runner_checkpoint.py`

```python
class TestCheckpoint(unittest.TestCase):
    def test_checkpoint_write_flush_fsync(self): ...
    def test_checkpoint_read_truncated_line(self): ...
    def test_resume_validates_header(self): ...
    def test_resume_validates_messages_sha256(self): ...
    def test_resume_completed_is_noop(self): ...
```

- Tests use `io.StringIO` and `tempfile.NamedTemporaryFile`.

### 7.6 `tests/test_runner_report.py`

```python
class TestReport(unittest.TestCase):
    def test_report_deterministic_bytes(self): ...
    def test_report_from_oracle_checkpoint(self): ...
    def test_report_key_order(self): ...
    def test_report_aggregation_counts(self): ...
```

### 7.7 `tests/test_runner_battery.py`

```python
class TestBattery(unittest.TestCase):
    def test_battery_layout_26_slots(self): ...
    def test_battery_layout_30_turns(self): ...
    def test_turn_builder_r3_prefix(self): ...
    def test_turn_builder_amb_reply_prompt(self): ...
```

### 7.8 `tests/test_runner_integration.py`

```python
class TestIntegration(unittest.TestCase):
    def test_full_run_oracle(self): ...
    def test_full_run_crasher_resume(self): ...
    def test_full_run_auth_reject(self): ...
    def test_full_run_ctx_shrink(self): ...
    def test_checkpoint_report_match(self): ...
```

- Uses `fakes.FakeServer` personas.
- `crasher` test verifies resume: first run exits 4 with partial checkpoint, second run with `oracle` completes.

### 7.9 `tests/test_cli_run.py`

```python
class TestCliRun(unittest.TestCase):
    def test_run_requires_base_url(self): ...
    def test_run_requires_model(self): ...
    def test_run_requires_seed(self): ...
    def test_run_missing_key_exit3(self): ...
```

### 7.10 Forbidden patterns

- No `socket.socket()` or `urllib.request.urlopen()` calls in any test file.
- No `time.sleep()` assertions. Retry delays are injected or mocked.
- Tests use the existing `fakes.FakeServer` from T2/T3.
- Every test method name is unique against the existing 272-method suite.

### 7.11 Fake transport adapter

`tests/fake_transport.py` (if needed) adapts `fakes.FakeServer` to the `Transport` protocol:

```python
class FakeServerTransport:
    def __init__(self, server: FakeServer):
        self.server = server

    def request(self, method, url, headers, body) -> tuple[int, dict, bytes]:
        path = urllib.parse.urlparse(url).path
        status, resp = self.server.handle(method, path, headers, body)
        return status, {"content-type": "application/json"}, json.dumps(resp).encode()
```

---

## 8. `tools/run_live.py`

An opt-in script for live-server testing. Not run by CI.

```python
#!/usr/bin/env python3
"""
Live-server test for psicotest runner.

Usage:
    python tools/run_live.py --base-url URL --model NAME --seed N [--order A|B]

Requires PSICOTEST_API_KEY in environment.
"""

import argparse
import os
import sys

sys.path.insert(0, "src")

from psicotest.runner import run_battery, HTTPTransport


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--order", default="A", choices=["A", "B"])
    parser.add_argument("--out", default="runs")
    args = parser.parse_args()

    key = os.environ.get("PSICOTEST_API_KEY")
    if not key:
        print("PSICOTEST_API_KEY not set", file=sys.stderr)
        return 3

    transport = HTTPTransport(timeout=120)
    return run_battery(
        transport=transport,
        base_url=args.base_url,
        model=args.model,
        api_key=key,
        seed=args.seed,
        order=args.order,
        out_dir=args.out,
    )


if __name__ == "__main__":
    sys.exit(main())
```

This script:
- Uses the real `HTTPTransport` with network access.
- Is excluded from `python -m unittest discover -s tests`.
- Exercises the same code paths as the test suite.

---

## 9. Acceptance checklist

- [ ] `ruff check .` and `ruff format --check .` are clean with ruff 0.17.1.
- [ ] `PYTHONHASHSEED=0 PYTHONPATH=src python3 -m unittest discover -s tests` passes.
- [ ] `PYTHONHASHSEED=1 PYTHONPATH=src python3 -m unittest discover -s tests` passes.
- [ ] Both pass on Python 3.11 and 3.12.
- [ ] The test suite total is between 302 and 317 methods (272 + 30..45).
- [ ] `test_banned_constructs.test_no_banned_constructs` scans every file under `src/psicotest/runner/` with zero violations.
- [ ] No file under `src/psicotest/runner/` contains bytes `>= 0x80`.
- [ ] No file opens a network socket in the test suite.
- [ ] No test uses `time.sleep()` or depends on wall-clock timing.
- [ ] `tools/run_live.py` exists and is executable but is not imported by tests.
- [ ] The checkpoint JSONL schema matches §6.1.
- [ ] The session report JSON schema matches §6.2.
- [ ] Two runs with the same seed/order produce byte-identical reports (excluding timestamps).
- [ ] Exit codes match §5.2 for each error condition.
- [ ] The 42 new test methods have unique names against the existing suite.
- [ ] The PR description lists every §10 HOLE with its default.

---

## 10. HOLE register (owner decisions; defaults pinned above)

| # | Topic | Pinned default |
|---|---|---|
| H1 | Request seed derivation | `derive_seed("req", battery, seed, order, turn) % (2**31)` per DESIGN §2.3, or `None` if server rejects it. Tests use `None` for deterministic fakes |
| H2 | `reasoning_effort` default | Not sent unless explicitly requested. T4 does not implement preflight item 7 checks |
| H3 | Extended sampling fields (`top_k`, `min_p`) | Not sent. T4 scope excludes `--no-extended-sampling` and related flags |
| H4 | Checkpoint path template | `{out_dir}/{battery}_{seed}_{order}.jsonl`. Battery is always `"v2"` |
| H5 | Report path template | Same basename with `.report.json` suffix |
| H6 | Manifest hash source | `canonical_json(list of SlotSpec asdict)`. Does not require `batteries/v2.json` file |
| H7 | `psicotest_version` source | `psicotest.__version__` if defined, else `"dev"` |
| H8 | Key value redaction | Before writing any artifact, check for key substring (length ≥ 8). Match → refuse write, exit 1. The key env var name is logged, never the value |
| H9 | Error message truncation | 500 chars, no secret scan needed (errors don't contain keys) |
| H10 | Token counting for effective tok/s | `completion_tokens / wall_s`. `None` if `wall_s < 0.01` |
| H11 | Reasoning tokens extraction | From `completion_tokens_details.reasoning_tokens` if present, else `None` |
| H12 | Resume partial turn handling | Drop the last line if it's not valid JSON or lacks required fields |
| H13 | Resume on completed file | No-op, exit 0 |
| H14 | Header fields for resume validation | `manifest_sha256`, `seed`, `order`, `model`, `params` (minus messages). `base_url` may differ (server moved) |
| H15 | CLI `--resume` flag | Flag presence enables resume. No checkpoint → start fresh |
| H16 | Default output directory | `runs/` created if missing |
| H17 | Battery version in report | Always `"v2"`, from `SLOTS_V2` |
| H18 | Telemetry aggregation in report | Sum `leak_total` across content/reasoning. Count turns with `loop: true`. Sum `selfcorr.total` |
| H19 | Transport timeout vs request timeout | Single timeout covers connect + read. Monotonic clock for elapsed time |
| H20 | SSL verification | Default `ssl.create_default_context()`. No `--insecure` flag in T4 scope |

---

## 11. API signatures

### 11.1 `runner/transport.py`

```python
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
        timeout: float,
    ) -> tuple[int, dict[str, str], bytes]:
        """Returns (status_code, response_headers, response_body)."""
        ...


class HTTPTransport:
    def __init__(self, timeout: float = 120): ...
    def request(self, method, url, headers, body, timeout) -> tuple[int, dict, bytes]: ...
```

### 11.2 `runner/client.py`

```python
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
        timeout: float = 120,
    ): ...

    def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 6144,
        temperature: float = 0.6,
        top_p: float = 0.95,
        seed: int | None = None,
    ) -> Response: ...
```

### 11.3 `runner/battery.py`

```python
def battery_layout(seed: int, order: str = "A") -> list[Turn]:
    """Returns 30 Turn objects for the battery."""
    ...


def build_turns(seed: int, order: str = "A") -> list[Turn]:
    """Alias for battery_layout."""
    ...
```

### 11.4 `runner/driver.py`

```python
def run_battery(
    *,
    transport: Transport,
    base_url: str,
    model: str,
    api_key: str,
    seed: int,
    order: str = "A",
    out_dir: str = "runs",
    max_tokens: int = 6144,
    timeout: float = 120,
    auth_scheme: str = "bearer",
    key_env: str = "PSICOTEST_API_KEY",
    resume: bool = False,
) -> int:
    """
    Run the full battery. Returns exit code.
    """
    ...
```

### 11.5 `runner/checkpoint.py`

```python
def write_header(path: Path, header: dict) -> None: ...
def write_turn(path: Path, record: dict) -> None: ...
def write_error(path: Path, record: dict) -> None: ...
def write_footer(path: Path, footer: dict) -> None: ...


def load_checkpoint(path: Path) -> tuple[dict | None, list[dict], dict | None]:
    """Returns (header, turns, footer). Missing file returns (None, [], None)."""
    ...


def validate_resume(header: dict, current: dict) -> str | None:
    """Returns None if valid, or an error message."""
    ...


def rebuild_messages(turns: list[Turn], responses: list[dict]) -> list[dict]:
    """Rebuild message history from turns and recorded responses."""
    ...
```

### 11.6 `runner/report.py`

```python
def write_report(checkpoint_path: Path, report_path: Path) -> None:
    """Generate session report from checkpoint."""
    ...


def aggregate_checkpoint(header: dict, turns: list[dict]) -> dict:
    """Compute aggregated metrics from checkpoint data."""
    ...
```

---

## 12. Implementation order

1. `transport.py`: exceptions, `Transport` protocol, `HTTPTransport` (tested with mocks).
2. `client.py`: `Client` class with retry logic, `Response` dataclass.
3. `battery.py`: move/adapt `battery_layout` from `tests/battery_layout.py`.
4. `checkpoint.py`: JSONL writer/reader, resume validation.
5. `driver.py`: orchestration, per-turn loop, scoring.
6. `report.py`: aggregation and deterministic JSON output.
7. `__init__.py`: exports.
8. `cli.py`: add `run` subcommand with argparse.
9. `tools/run_live.py`: opt-in script.
10. Tests in order of dependencies.
11. Update `test_banned_constructs.py`.

---

## 13. Relation to existing code

### 13.1 Reused without changes

- `psicotest.rng`: `derive_seed`, `Rng`
- `psicotest.spec`: `Turn`, `Item`, `CheckResult`, `canonical_json`
- `psicotest.checkers`: `check_turn`, `check_rules`, `measure`
- `psicotest.generators`: `SLOTS_V2`, `build_slot_item`, `SETUP_TEXT`, `R3_TEXT`, `RCL_TEXT`, `reply_prompt`, `trigger_animal`
- `tests/fakes.py`: `FakeServer`, `PERSONAS`, `oracle_answer`

### 13.2 Moved to `runner/battery.py`

The turn-building logic from `tests/battery_layout.py` is promoted to production code in `runner/battery.py`. The test helper remains and imports from `runner.battery`.

### 13.3 `cli.py` changes

Add subparser for `run`:

```python
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="psicotest", description="llm-psicotest")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run battery")
    run_parser.add_argument("--base-url", required=True)
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--seed", type=int, required=True)
    run_parser.add_argument("--order", default="A", choices=["A", "B"])
    run_parser.add_argument("--out", default="runs")
    run_parser.add_argument("--max-tokens", type=int, default=6144)
    run_parser.add_argument("--timeout", type=float, default=120)
    run_parser.add_argument("--key-env", default="PSICOTEST_API_KEY")
    run_parser.add_argument("--auth", default="bearer", choices=["bearer", "x-api-key"])
    run_parser.add_argument("--resume", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "run":
        from psicotest.runner import run_battery, HTTPTransport
        import os

        key = os.environ.get(args.key_env)
        if not key:
            print(f"{args.key_env} not set", file=sys.stderr)
            return EXIT_AUTH

        transport = HTTPTransport(timeout=args.timeout)
        return run_battery(
            transport=transport,
            base_url=args.base_url,
            model=args.model,
            api_key=key,
            seed=args.seed,
            order=args.order,
            out_dir=args.out,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            auth_scheme=args.auth,
            key_env=args.key_env,
            resume=args.resume,
        )

    parser.print_help()
    return 0
```

## Accepted deviations

- Response message `content` null is coerced to an empty string.
- Absent `finish_reason` raises ProtocolError instead of defaulting to `"stop"`.
- The configured timeout bounds each socket operation (open and body read) rather than one wall-clock deadline per request (refines H19).
- 3xx responses raise ProtocolError; redirects are never followed.
- Resume-integrity violations raise ValueError and map to EXIT_INTERNAL.
- Report writes are atomic (temp file plus `os.replace`) and the report is regenerated on completed-resume.
