import dataclasses
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

from psicotest.spec import canonical_json

RESUME_FIELDS = ("manifest_sha256", "seed", "order", "model", "params")


def canonical_hash(obj) -> str:
    return hashlib.sha256(canonical_json(_to_decimal(obj))).hexdigest()


def _to_decimal(obj):
    if obj is None or isinstance(obj, (str, bytes, bool, int, Decimal)):
        return obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            field.name: _to_decimal(getattr(obj, field.name)) for field in dataclasses.fields(obj)
        }
    if isinstance(obj, dict):
        return {key: _to_decimal(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_decimal(value) for value in obj]
    return Decimal(str(obj))


def _write_line(path, record, mode):
    line = json.dumps(record, ensure_ascii=False)
    with open(path, mode, encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_header(path: Path, header: dict) -> None:
    _write_line(path, header, "w")


def write_turn(path: Path, record: dict) -> None:
    _write_line(path, record, "a")


def write_error(path: Path, record: dict) -> None:
    _write_line(path, record, "a")


def write_footer(path: Path, footer: dict) -> None:
    _write_line(path, footer, "a")


def _load_records(path) -> list[dict]:
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b"\n"):
        keep = raw.rfind(b"\n") + 1
        os.truncate(path, keep)
        raw = raw[:keep]
    records = []
    lines = raw.decode("utf-8").split("\n")
    last = len(lines) - 1
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            if index == last:
                continue
            break
        if not isinstance(record, dict) or "type" not in record:
            if index == last:
                continue
            break
        records.append(record)
    return records


def load_checkpoint(path: Path) -> tuple[dict | None, list[dict], dict | None]:
    if not Path(path).exists():
        return None, [], None
    records = _load_records(path)
    header = next((r for r in records if r.get("type") == "header"), None)
    turns = [r for r in records if r.get("type") == "turn"]
    footer = next((r for r in records if r.get("type") == "footer"), None)
    return header, turns, footer


def validate_resume(header: dict, current: dict) -> str | None:
    if not isinstance(header, dict):
        return "checkpoint header missing"
    for field in RESUME_FIELDS:
        if header.get(field) != current.get(field):
            return f"resume mismatch: {field}"
    return None


def validate_resume_turns(done: list[dict], turns: list) -> None:
    history = []
    for index, record in enumerate(done):
        turn_no = index + 1
        if record.get("turn") != turn_no:
            raise ValueError(f"resume turn sequence broken at {turn_no}")
        if index >= len(turns):
            raise ValueError("resume has more turns than the battery")
        turn = turns[index]
        user_message = {"role": "user", "content": turn.prompt_en}
        if record.get("request", {}).get("messages_sha256") != canonical_hash(
            [*history, user_message]
        ):
            raise ValueError(f"resume messages hash mismatch at turn {turn_no}")
        history.append(user_message)
        history.append({"role": "assistant", "content": record["response"]["content"]})


def rebuild_messages(turns, responses) -> list[dict]:
    messages = []
    for turn, response in zip(turns, responses, strict=True):
        messages.append({"role": "user", "content": turn.prompt_en})
        messages.append({"role": "assistant", "content": response["content"]})
    return messages
