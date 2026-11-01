import json
import sys
import time
from pathlib import Path

from psicotest.checkers.registry import check_turn
from psicotest.checkers.rules import check_rules
from psicotest.checkers.telemetry import measure
from psicotest.generators import SLOTS_V4
from psicotest.rng import derive_seed
from psicotest.runner import battery, checkpoint
from psicotest.runner.client import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    Client,
)
from psicotest.runner.report import CAPABILITY_SLOTS
from psicotest.runner.transport import (
    AuthError,
    ProtocolError,
    Transport,
    TransportError,
)

BATTERY_VERSION = "v4"

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

_WRITERS = {
    "header": checkpoint.write_header,
    "turn": checkpoint.write_turn,
    "error": checkpoint.write_error,
    "footer": checkpoint.write_footer,
}


def _checkpoint_path(seed: int, order: str) -> str:
    return f"{BATTERY_VERSION}_{seed}_{order}.jsonl"


def _report_path(seed: int, order: str) -> str:
    return f"{BATTERY_VERSION}_{seed}_{order}.report.json"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _version() -> str:
    import psicotest

    return getattr(psicotest, "__version__", "dev")


def _python_version() -> str:
    info = sys.version_info
    return f"{info.major}.{info.minor}.{info.micro}"


def _json_safe(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _write_record(path, api_key, record) -> bool:
    line = json.dumps(record, ensure_ascii=False)
    if api_key and len(api_key) >= 8 and api_key in line:
        print("refusing to write artifact containing the API key", file=sys.stderr)
        return False
    _WRITERS[record["type"]](path, record)
    return True


def _write_errors(path, api_key, turn_no, client) -> bool:
    for error in client._last_errors:
        record = {
            "type": "error",
            "turn": turn_no,
            "attempt": error["attempt"],
            "kind": error["kind"],
            "http_status": error["http_status"],
            "message": error["message"][:500],
        }
        if not _write_record(path, api_key, record):
            return False
    return True


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
    timeout: "float" = 240,
    auth_scheme: str = "bearer",
    key_env: str = "PSICOTEST_API_KEY",
    resume: bool = False,
) -> int:
    from psicotest.runner.report import write_report

    turns = battery.battery_layout(seed, order)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    checkpoint_path = out_path / _checkpoint_path(seed, order)
    report_path = out_path / _report_path(seed, order)
    manifest = checkpoint.canonical_hash(list(SLOTS_V4))
    params = {
        "max_tokens": max_tokens,
        "temperature": DEFAULT_TEMPERATURE,
        "top_p": DEFAULT_TOP_P,
    }
    client = Client(
        transport,
        base_url,
        model,
        api_key,
        auth_scheme=auth_scheme,
        timeout=timeout,
    )
    header = {
        "type": "header",
        "schema": 1,
        "battery_version": BATTERY_VERSION,
        "manifest_sha256": manifest,
        "psicotest_version": _version(),
        "python_version": _python_version(),
        "platform": sys.platform,
        "base_url": base_url,
        "model": model,
        "auth_scheme": auth_scheme,
        "key_env": key_env,
        "seed": seed,
        "order": order,
        "params": params,
        "started_at": _utc_now(),
    }
    messages = []
    start = 0
    resumed = False
    if resume and checkpoint_path.exists():
        try:
            old_header, done, footer = checkpoint.load_checkpoint(checkpoint_path)
        except ValueError as exc:
            print(str(exc)[:500], file=sys.stderr)
            return EXIT_INTERNAL
        if footer is not None:
            write_report(checkpoint_path, report_path)
            return EXIT_OK
        current = {
            "manifest_sha256": manifest,
            "seed": seed,
            "order": order,
            "model": model,
            "params": params,
        }
        problem = checkpoint.validate_resume(old_header, current)
        if problem is not None:
            print(problem, file=sys.stderr)
            return EXIT_RESUME_MISMATCH
        try:
            checkpoint.validate_resume_turns(done, turns)
        except ValueError as exc:
            print(str(exc)[:500], file=sys.stderr)
            return EXIT_INTERNAL
        responses = [record["response"] for record in done]
        messages = checkpoint.rebuild_messages(turns[: len(done)], responses)
        if done:
            client._observe_prompt_tokens(done[-1]["response"]["usage"]["prompt_tokens"])
        start = len(done)
        resumed = True
    if not resumed and not _write_record(checkpoint_path, api_key, header):
        return EXIT_INTERNAL
    for turn in turns[start:]:
        started_at = _utc_now()
        t0 = time.monotonic()
        req_seed = derive_seed("req", BATTERY_VERSION, seed, order, turn.turn) % (1 << 31)
        request_messages = [*messages, {"role": "user", "content": turn.prompt_en}]
        try:
            response = client.chat(request_messages, max_tokens=max_tokens, seed=req_seed)
        except AuthError:
            _write_errors(checkpoint_path, api_key, turn.turn, client)
            return EXIT_AUTH
        except ProtocolError:
            _write_errors(checkpoint_path, api_key, turn.turn, client)
            return EXIT_PROTOCOL
        except TransportError:
            _write_errors(checkpoint_path, api_key, turn.turn, client)
            return EXIT_TRANSPORT
        except Exception as exc:
            print(str(exc)[:500], file=sys.stderr)
            return EXIT_INTERNAL
        wall_s = time.monotonic() - t0
        if not _write_errors(checkpoint_path, api_key, turn.turn, client):
            return EXIT_INTERNAL
        effective_tok_s = response.completion_tokens / wall_s if wall_s * 100 >= 1 else None
        try:
            result = check_turn(
                turn, response.content, response.finish_reason, response.reasoning_content
            )
            rules = check_rules(response.content, turn, response.finish_reason)
        except Exception as exc:
            print(str(exc)[:500], file=sys.stderr)
            return EXIT_INTERNAL
        telemetry = measure(response.content, response.reasoning_content)
        scoring = {
            "outcome": result.outcome,
            "score": result.score,
            "value": _json_safe(result.value),
            "flags": _json_safe(result.flags),
            "detail": result.detail,
        }
        if turn.kind == "item" and turn.slot is not None and turn.slot in CAPABILITY_SLOTS:
            leak_content = telemetry["leak"]["content"]
            cjk_chars = (
                leak_content["han"]
                + leak_content["kana"]
                + leak_content["hangul"]
                + leak_content["bopomofo"]
                + telemetry["cjk_punct"]["content"]
            )
            if cjk_chars > 0:
                scoring["outcome"] = "WRONG"
                scoring["score"] = 0
                if "leak" not in scoring["flags"]:
                    scoring["flags"].append("leak")
        req_params = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": DEFAULT_TEMPERATURE,
            "top_p": DEFAULT_TOP_P,
            "seed": req_seed,
        }
        record = {
            "type": "turn",
            "turn": turn.turn,
            "slot": turn.slot,
            "kind": turn.kind,
            "request": {
                "n_messages": len(request_messages),
                "messages_sha256": checkpoint.canonical_hash(request_messages),
                "prompt_chars": len(turn.prompt_en),
                "params_sha256": checkpoint.canonical_hash(req_params),
            },
            "response": {
                "status": response.status,
                "model": response.model,
                "content": response.content,
                "reasoning_content": response.reasoning_content,
                "finish_reason": response.finish_reason,
                "usage": {
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "reasoning_tokens": response.reasoning_tokens,
                },
            },
            "timing": {"started_at": started_at, "wall_s": wall_s},
            "effective_tok_s": effective_tok_s,
            "attempts": client._last_attempts,
            "scoring": scoring,
            "rules": rules,
            "telemetry": telemetry,
        }
        if not _write_record(checkpoint_path, api_key, record):
            return EXIT_INTERNAL
        messages.append({"role": "user", "content": turn.prompt_en})
        messages.append({"role": "assistant", "content": response.content})
    footer = {"type": "footer", "completed_at": _utc_now(), "n_turns": len(turns)}
    if not _write_record(checkpoint_path, api_key, footer):
        return EXIT_INTERNAL
    write_report(checkpoint_path, report_path)
    return EXIT_OK
