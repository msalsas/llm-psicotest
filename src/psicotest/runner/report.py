import json
import os
from pathlib import Path

from psicotest.checkers.common import CAPABILITY_FAMILIES
from psicotest.generators import SLOTS_V2
from psicotest.runner import checkpoint

REPORT_SCHEMA_VERSION = 1


def aggregate_checkpoint(header: dict, turns: list[dict]) -> dict:
    slot_family = {spec.slot: spec.family for spec in SLOTS_V2}
    capability_slots = frozenset(spec.slot for spec in SLOTS_V2 if spec.capability)
    by_family = {family: {"score": 0, "max": 0} for family in CAPABILITY_FAMILIES}
    cap_score = 0
    clar_ok = 0
    clar_miss = 0
    clar_over = 0
    clar_bad = 0
    rcl_score = 0
    setup_ok = False
    r1 = {"ok": 0, "fail": 0, "na": 0}
    r2 = {"ok": 0, "fail": 0, "na": 0}
    r3 = {"hit": 0, "miss": 0, "false": 0, "clean": 0, "na": 0}
    trunc_count = 0
    prompt_total = 0
    completion_total = 0
    reasoning_total = 0
    wall = []
    leak_chars = 0
    loop_count = 0
    selfcorr_total = 0
    for record in turns:
        scoring = record["scoring"]
        rules = record["rules"]
        usage = record["response"]["usage"]
        telemetry = record["telemetry"]
        slot = record.get("slot")
        base = slot[:-1] if slot is not None and slot[-1] in "ab" else slot
        kind = record["kind"]
        outcome = scoring["outcome"]
        if kind == "item" and base in capability_slots:
            cap_score += scoring["score"]
            family = slot_family[base]
            by_family[family]["score"] += scoring["score"]
            by_family[family]["max"] += 1
        if kind == "amb_ask":
            if outcome == "CLAR_OK":
                clar_ok += 1
            elif outcome == "CLAR_MISS":
                clar_miss += 1
            elif outcome == "CLAR_OVER":
                clar_over += 1
            elif outcome == "CLAR_BAD":
                clar_bad += 1
        if outcome == "RCL":
            rcl_score = scoring["score"]
        if record["turn"] == 1:
            setup_ok = outcome == "OK"
        if outcome == "TRUNC":
            trunc_count += 1
        if rules["R1"] == "R1_OK":
            r1["ok"] += 1
        elif rules["R1"] == "R1_FAIL":
            r1["fail"] += 1
        else:
            r1["na"] += 1
        if rules["R2"] == "R2_OK":
            r2["ok"] += 1
        elif rules["R2"] == "R2_FAIL":
            r2["fail"] += 1
        else:
            r2["na"] += 1
        if rules["R3"] == "R3_HIT":
            r3["hit"] += 1
        elif rules["R3"] == "R3_MISS":
            r3["miss"] += 1
        elif rules["R3"] == "R3_FALSE":
            r3["false"] += 1
        elif rules["R3"] == "R3_CLEAN":
            r3["clean"] += 1
        else:
            r3["na"] += 1
        prompt_total += usage["prompt_tokens"]
        completion_total += usage["completion_tokens"]
        if usage.get("reasoning_tokens") is not None:
            reasoning_total += usage["reasoning_tokens"]
        wall.append(record["timing"]["wall_s"])
        leak_chars += (
            telemetry["leak"]["content"]["total"] + telemetry["leak"]["reasoning"]["total"]
        )
        if telemetry["loop"]["content"] or telemetry["loop"]["reasoning"]:
            loop_count += 1
        selfcorr_total += (
            telemetry["selfcorr"]["content"]["total"] + telemetry["selfcorr"]["reasoning"]["total"]
        )
    wall_total = sum(wall)
    wall_mean = wall_total / (len(wall) or 1)
    return {
        "schema": REPORT_SCHEMA_VERSION,
        "battery_version": "v2",
        "manifest_sha256": header["manifest_sha256"],
        "base_url": header["base_url"],
        "model": header["model"],
        "seed": header["seed"],
        "order": header["order"],
        "started_at": header["started_at"],
        "completed_at": "",
        "capability": {"score": cap_score, "max": 21, "by_family": by_family},
        "protocol": {
            "setup_ok": setup_ok,
            "clar_ok": clar_ok,
            "clar_miss": clar_miss,
            "clar_over": clar_over,
            "clar_bad": clar_bad,
            "rcl_score": rcl_score,
        },
        "rules": {"R1": r1, "R2": r2, "R3": r3},
        "trunc_count": trunc_count,
        "tokens": {
            "prompt_total": prompt_total,
            "completion_total": completion_total,
            "reasoning_total": reasoning_total,
        },
        "timing": {"wall_s_total": wall_total, "wall_s_mean": wall_mean},
        "telemetry": {
            "leak_chars": leak_chars,
            "loop_count": loop_count,
            "selfcorr_total": selfcorr_total,
        },
    }


def _load_errors(path) -> list[dict]:
    errors = []
    for line in Path(path).read_text("utf-8").split("\n"):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("type") == "error":
            errors.append(record)
    return errors


def _summarize_errors(errors, turns) -> list[dict]:
    attempts_by_turn = {record["turn"]: record["attempts"] for record in turns}
    summary = []
    for error in errors:
        turn_no = error["turn"]
        attempts = attempts_by_turn.get(turn_no, error["attempt"])
        if summary and summary[-1]["turn"] == turn_no:
            summary[-1]["attempts"] = attempts
            summary[-1]["last_kind"] = error["kind"]
        else:
            summary.append({"turn": turn_no, "attempts": attempts, "last_kind": error["kind"]})
    return summary


def write_report(checkpoint_path: Path, report_path: Path) -> None:
    header, turns, footer = checkpoint.load_checkpoint(checkpoint_path)
    report = aggregate_checkpoint(header, turns)
    if footer is not None:
        report["completed_at"] = footer["completed_at"]
    report["errors"] = _summarize_errors(_load_errors(checkpoint_path), turns)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    report_path = Path(report_path)
    tmp_path = report_path.with_name(report_path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, report_path)
