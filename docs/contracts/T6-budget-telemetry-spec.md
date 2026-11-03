# Budget telemetry and server snapshot: implementation contract

## 0. Scope and invariants

- The v6 battery stays frozen. Do not touch `src/psicotest/generators/**`, `SLOTS_V6`, `src/psicotest/checkers/` (except the two telemetry files named below), scoring, rules or battery layout.
- The chat request path and body stay byte-identical: same URL `base_url + "/chat/completions"`, same `build_request_body`, same sampling params and seed derivation.
- The only new network call is one best-effort `GET base_url + "/models"`. It is made once per fresh run, before turn 1. It is never made on resume.
- Stdlib only. No code comments, no new docstrings. English only. Python 3.11+.
- All of these must pass from the repo root:
  - `PYTHONPATH=src python3 -m unittest discover -s tests`
  - `ruff check .`
  - `ruff format --check .`
- Before committing, copy `.telemetry-fixture.in.json` byte-for-byte to `tests/fixtures/budget_golden.json`, then delete `.telemetry-fixture.in.json`.

## 1. Inference rule (budget cap)

Inputs are a run's `completion_tokens` values in turn order. Four constants:

| Constant | Value |
|---|---|
| `BUDGET_MARGIN` | 448 |
| `BUDGET_BAND` | 32 |
| `BUDGET_MIN_CLUSTER` | 4 |
| `BUDGET_MIN_GAP` | 256 |

`infer_budget_cap(cts)` works as follows:

1. If `len(cts) < BUDGET_MIN_CLUSTER`, return `None`.
2. Set `top = max(cts)`. Set `window = sorted(c for c in cts if c >= top - BUDGET_MARGIN)`.
3. Find the cap: the smallest value `low` in `window` such that the number of values `v` in `window` with `low <= v <= low + BUDGET_BAND` is at least `BUDGET_MIN_CLUSTER`. If no such `low` exists, return `None`.
4. Set `below = [c for c in cts if c < cap]`. If `below` is empty, return `None`: with nothing below it, there is no separation. If `cap - max(below) < BUDGET_MIN_GAP`, return `None`.
5. Return `cap`.

`budget_flags(cts)` returns `[cap is not None and c >= cap for c in cts]`, where `cap` comes from `infer_budget_cap`.

### Why these values

- **Cluster signature.** The server stops reasoning at a fixed budget, so capped turns pile up at "budget plus a short answer". In the archived runs the pile floors are 4638, 4638, 4638 and 4631. Each pile has at least 5 turns within 32 tokens of its floor (seed11 has the fewest: 4638, 4638, 4652, 4653, 4656). A run is flagged only if it shows a dense band near its top, separated from everything below it.
- **What can never be flagged:**
  - a lone maximum (band count 1);
  - a no-cap run whose top values are spread out;
  - a dense top with no gap below it;
  - an all-equal run.
- **Choice of `BUDGET_MARGIN = 448`.**
  - The window must contain every run's whole pile, so the margin must be at least the largest per-run (max minus floor). That is 268, from iq2xs-seed11: 4899 − 4631.
  - For the plain max-minus-margin stage alone not to sweep in the largest uncapped turn, the margin must be below the smallest per-run (max minus largest uncapped). That is 628, from seed11: 4738 − 4110.
  - 448 is the midpoint of [268, 628), leaving 180 tokens of slack on each side. It is also inside the brief's interval.
- **`BUDGET_MIN_GAP = 256`** is under half of the smallest observed pile-to-uncapped gap (528, seed11). The rule prefers false negatives. A capped run with a natural turn just below the pile goes unflagged, and the marker cross-check then shows the disagreement in the report.

### Result on the archived fixture

| Run | Cap | Flagged turns | Gap to largest uncapped |
|---|---|---|---|
| `strata-v6-seed7` | 4638 | 8 | 716 |
| `strata-v6-seed11` | 4638 | 6 | 528 |
| `strata-iq2xs-seed7` | 4638 | 8 | 867 |
| `strata-iq2xs-seed11` | 4631 | 12 | 1587 |

- The union of flagged (run, turn) pairs is exactly the 34 pairs where `phrase` is true, and all 152 rows agree.
- Flagged kinds are `item` and `recall` (the recall is iq2xs-seed11 turn 30).

## 2. Files

### 2.1 CREATE `src/psicotest/checkers/budget.py`

This module is the only place the marker string lives.

```python
from collections.abc import Sequence

BUDGET_MARKER = "I have thought about this long enough; time to give my answer"
BUDGET_MARGIN = 448
BUDGET_BAND = 32
BUDGET_MIN_CLUSTER = 4
BUDGET_MIN_GAP = 256


def has_budget_marker(text: str | None) -> bool:
    return BUDGET_MARKER in (text or "")


def infer_budget_cap(completion_tokens: Sequence[int]) -> int | None:
    values = list(completion_tokens)
    if len(values) < BUDGET_MIN_CLUSTER:
        return None
    top = max(values)
    window = sorted(value for value in values if value >= top - BUDGET_MARGIN)
    cap = None
    for index, low in enumerate(window):
        count = sum(1 for value in window[index:] if value <= low + BUDGET_BAND)
        if count >= BUDGET_MIN_CLUSTER:
            cap = low
            break
    if cap is None:
        return None
    below = [value for value in values if value < cap]
    if not below or cap - max(below) < BUDGET_MIN_GAP:
        return None
    return cap


def budget_flags(completion_tokens: Sequence[int]) -> list[bool]:
    values = list(completion_tokens)
    cap = infer_budget_cap(values)
    return [cap is not None and value >= cap for value in values]
```

### 2.2 MODIFY `src/psicotest/checkers/telemetry.py`

The per-turn telemetry block moves to schema 2.

- Add `from psicotest.checkers.budget import has_budget_marker` to the first-party import group, in sorted order.
- In `measure`, change `"schema": 1` to `"schema": 2`.
- Append one key after `"loop"`, as the last key:
  `"budget": {"marker": {"content": has_budget_marker(content), "reasoning": has_budget_marker(reasoning)}}`
- Nothing else changes.

Exact per-turn telemetry schema 2 fields, in order:

- `schema` (int 2)
- `chars`
- `leak`
- `cjk_punct`
- `selfcorr`
- `loop`
- `budget`
  - `marker`
    - `content` (bool)
    - `reasoning` (bool)

The per-turn `budget_hit` is not written into the checkpoint (see ERRATA 4). The checkpoint stores the per-turn marker evidence. The per-run token inference is materialized per turn in `report.budget.hit_turns`.

### 2.3 MODIFY `src/psicotest/runner/client.py`

Add a module constant after `DEFAULT_TOP_P`:

```python
SNAPSHOT_TIMEOUT = 30
```

Add these module functions, placed after the `Response` dataclass:

```python
def null_server_snapshot(status: str, http_status: int | None = None) -> dict:
    return {
        "status": status,
        "http_status": http_status,
        "model_id": None,
        "owned_by": None,
        "label": None,
        "instance_id": None,
        "gpus": None,
        "aliases": None,
    }


def _str_or_none(value) -> str | None:
    return value if isinstance(value, str) else None


def _str_list_or_none(value) -> list[str] | None:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return None


def _int_list_or_none(value) -> list[int] | None:
    if isinstance(value, list) and all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        return list(value)
    return None


def _meta_of(entry: dict) -> dict:
    meta = entry.get("meta")
    return meta if isinstance(meta, dict) else {}


def parse_models_payload(model: str, status: int, body: bytes) -> dict:
    if status != 200:
        return null_server_snapshot("http_error", status)
    try:
        data = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return null_server_snapshot("bad_payload", status)
    entries = data.get("data") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return null_server_snapshot("bad_payload", status)
    candidates = [entry for entry in entries if isinstance(entry, dict)]
    entry = next((item for item in candidates if item.get("id") == model), None)
    if entry is None:
        entry = next(
            (
                item
                for item in candidates
                if isinstance(_meta_of(item).get("aliases"), list)
                and model in _meta_of(item)["aliases"]
            ),
            None,
        )
    if entry is None:
        return null_server_snapshot("model_not_listed", status)
    meta = _meta_of(entry)
    return {
        "status": "ok",
        "http_status": status,
        "model_id": _str_or_none(entry.get("id")),
        "owned_by": _str_or_none(entry.get("owned_by")),
        "label": _str_or_none(meta.get("label")),
        "instance_id": _str_or_none(meta.get("instanceId")),
        "gpus": _int_list_or_none(meta.get("gpus")),
        "aliases": _str_list_or_none(meta.get("aliases")),
    }
```

Add a method to `Client`, placed after `_observe_prompt_tokens`:

```python
    def server_snapshot(self) -> dict:
        url = self._base_url + "/models"
        try:
            status, _headers, body = self._transport.request(
                "GET", url, self._headers, None, min(self._timeout, SNAPSHOT_TIMEOUT)
            )
        except Exception:
            return null_server_snapshot("transport_error")
        try:
            return parse_models_payload(self._model, status, body)
        except Exception:
            return null_server_snapshot("bad_payload", status if isinstance(status, int) else None)
```

- The method makes one attempt: no retries and no `_wait`.
- It must not touch `_last_errors`, `_last_prompt_tokens` or `_last_attempts`.
- `chat` and `build_request_body` stay unchanged.

Status values:

- `ok`
- `model_not_listed`
- `http_error`
- `bad_payload`
- `transport_error`
- `redacted` (set by the driver)

### 2.4 MODIFY `src/psicotest/runner/driver.py`

- Add module constant `HEADER_SCHEMA = 2`, placed after `BATTERY_VERSION`.
- Import `null_server_snapshot` from `psicotest.runner.client`, added to the existing parenthesized import in sorted order.
- Add this function after `_write_errors`:

```python
def _server_snapshot(client: Client, api_key: str) -> dict:
    snapshot = client.server_snapshot()
    if api_key and len(api_key) >= 8 and api_key in json.dumps(snapshot, ensure_ascii=False):
        return null_server_snapshot("redacted", snapshot.get("http_status"))
    return snapshot
```

- In `run_battery`, change the header's `"schema": 1` to `"schema": HEADER_SCHEMA`. Otherwise the header dict literal is unchanged.
- Replace `if not resumed and not _write_record(checkpoint_path, api_key, header): return EXIT_INTERNAL` with:

```python
    if not resumed:
        header["server"] = _server_snapshot(client, api_key)
        if not _write_record(checkpoint_path, api_key, header):
            return EXIT_INTERNAL
```

- `RESUME_FIELDS`, `validate_resume`, turn loop, scoring, leak hook and record layout are all unchanged.

Exact header schema 2 fields, in order:

`type`, `schema` (int 2), `battery_version`, `manifest_sha256`, `psicotest_version`, `python_version`, `platform`, `base_url`, `model`, `auth_scheme`, `key_env`, `seed`, `order`, `params`, `started_at`, `server`.

`server` has these fields, in order:

| Field | Type |
|---|---|
| `status` | str |
| `http_status` | int or null |
| `model_id` | str or null |
| `owned_by` | str or null |
| `label` | str or null |
| `instance_id` | str or null |
| `gpus` | list[int] or null |
| `aliases` | list[str] or null |

### 2.5 MODIFY `src/psicotest/runner/report.py`

- Add `from psicotest.checkers.budget import budget_flags, infer_budget_cap`.
- Change `REPORT_SCHEMA_VERSION = 1` to `REPORT_SCHEMA_VERSION = 2`.
- Add these functions before `aggregate_checkpoint`:

```python
def _turn_marker(record: dict) -> bool | None:
    budget = record.get("telemetry", {}).get("budget")
    if not isinstance(budget, dict) or not isinstance(budget.get("marker"), dict):
        return None
    marker = budget["marker"]
    return bool(marker.get("content")) or bool(marker.get("reasoning"))


def summarize_budget(turns: list[dict]) -> dict:
    tokens = [record["response"]["usage"]["completion_tokens"] for record in turns]
    flags = budget_flags(tokens)
    hit_turns = [record["turn"] for record, flag in zip(turns, flags, strict=True) if flag]
    markers = [_turn_marker(record) for record in turns]
    if any(marker is None for marker in markers):
        marker_hits = None
        marker_crosscheck = None
        marker_disagree_turns = None
    else:
        marker_hits = sum(1 for marker in markers if marker)
        marker_crosscheck = sum(
            1 for flag, marker in zip(flags, markers, strict=True) if flag == marker
        )
        marker_disagree_turns = [
            record["turn"]
            for record, flag, marker in zip(turns, flags, markers, strict=True)
            if flag != marker
        ]
    return {
        "cap": infer_budget_cap(tokens),
        "budget_hits": len(hit_turns),
        "hit_turns": hit_turns,
        "marker_hits": marker_hits,
        "marker_crosscheck": marker_crosscheck,
        "marker_disagree_turns": marker_disagree_turns,
    }
```

- In the dict returned by `aggregate_checkpoint`:
  - insert `"budget": summarize_budget(turns)` right after `"trunc_count"`;
  - insert `"server": header.get("server")` right after `"telemetry"`.
- The `trunc_count` logic is unchanged.

Report schema 2 top-level keys, in order:

`schema`, `battery_version`, `manifest_sha256`, `base_url`, `model`, `seed`, `order`, `started_at`, `completed_at`, `capability`, `protocol`, `rules`, `trunc_count`, `budget`, `tokens`, `timing`, `telemetry`, `server`, `errors`.

`budget` keys, in order:

| Key | Type |
|---|---|
| `cap` | int or null |
| `budget_hits` | int |
| `hit_turns` | list[int] |
| `marker_hits` | int or null |
| `marker_crosscheck` | int or null |
| `marker_disagree_turns` | list[int] or null |

Reading schema-1 archives:

- `completion_tokens` has always been recorded, so the token rule still runs and `budget_hits` is an int.
- The marker fields are null, because the schema-1 telemetry block has no `budget` key.
- `server` is null.
- No new required key is read, so loading never raises `KeyError`.

### 2.6 MODIFY `README.md`

- Replace the line-97 bullet "Other telemetry" with the same text plus one sentence: `Reasoning-budget hits are inferred per run from completion tokens (report key budget, cross-checked against the server's budget marker) and reported separately from trunc_count; the run header records a best-effort GET /models snapshot of the served model (header key server).`
- No other README change.

### 2.7 Unchanged

- `tools/run_live.py`: see ERRATA 1.
- `tests/fakes.py` and `tests/fake_transport.py`.
- `checkpoint.py`, `transport.py`, `cli.py`, `runner/__init__.py`.

### 2.8 CREATE `tests/fixtures/budget_golden.json`

A verbatim copy of `.telemetry-fixture.in.json`. Delete the transport file afterwards.

## 3. Existing tests: minimal edits forced by the schema bumps

No scoring, outcome or rule assertion changes.

- **E1.** `tests/test_telemetry.py::TestTelemetry::test_measure_schema`: the sorted key list becomes `["budget", "chars", "cjk_punct", "leak", "loop", "schema", "selfcorr"]`.
- **E2.** `tests/test_runner_driver.py::TestDriver::test_driver_scores_each_turn`: `record["telemetry"]["schema"]` must equal `2`.
- **E3.** `tests/test_runner_report.py`:
  - `TOP_KEYS` gets `"budget"` inserted after `"trunc_count"` and `"server"` inserted after `"telemetry"`;
  - in `test_report_from_oracle_checkpoint`, `report["schema"]` must equal `2`.

All other existing tests stay byte-unchanged and green. This includes:

- the golden corpus, generators and checkers suites;
- the `test_runner_checkpoint` sample schema-1 records;
- `test_driver_history_excludes_reasoning`. Its Recorder raises on the GET because it calls `json.loads(None)`. The snapshot catches that and records `transport_error`, so the Recorder still holds 38 bodies.

Do not assert any `budget_hits` value on an unmodified fake-oracle run: the fake token counts are arbitrary.

## 4. New tests

Each new file starts with `import _bootstrap`, uses `unittest`, and ends with the `if __name__ == "__main__": unittest.main()` block.

Shared helper, defined in each file that needs it:

`rewrite(path, fn)` reads the jsonl, applies `fn(record)` to each parsed record, and writes each line back as `json.dumps(record, ensure_ascii=False) + "\n"`.

### 4.1 `tests/test_budget.py`

`FIXTURE = Path(__file__).resolve().parent / "fixtures" / "budget_golden.json"`.

`by_run()` returns `dict[run, list[row]]`, with rows sorted by `turn`.

**Class `TestBudgetFixture`:**

1. `test_fixture_shape`
   - 152 rows.
   - Every row's key set is `{"run", "turn", "kind", "slot", "ct", "fr", "phrase"}`.
   - The runs are `{"strata-v6-seed7", "strata-v6-seed11", "strata-iq2xs-seed7", "strata-iq2xs-seed11"}`.
   - Each run's turns are exactly 1..38.
   - Every `fr == "stop"`.
2. `test_flagged_set_is_the_34`
   - The flagged set is the (run, turn) pairs where `budget_flags([r["ct"] for r in rows])` is true per run.
   - It equals `{(r["run"], r["turn"]) for r in rows if r["phrase"]}`.
   - Its length is 34.
3. `test_token_rule_agrees_with_phrase_on_all_rows`
   - For all 152 rows, `flag == row["phrase"]` (run with `subTest`).
4. `test_per_run_caps_and_counts`
   - `infer_budget_cap` gives `{"strata-v6-seed7": 4638, "strata-v6-seed11": 4638, "strata-iq2xs-seed7": 4638, "strata-iq2xs-seed11": 4631}`.
   - Per-run flagged counts are 8, 6, 8 and 12 for the same runs.
   - The kinds of flagged rows are `{"item", "recall"}`.
5. `test_gap_and_margin_window`
   - The maximum `ct` of unflagged rows is 4110.
   - The minimum `ct` of flagged rows is 4631; the difference is 521.
   - `max over runs (max ct − cap) == 268`.
   - `min over runs (max ct − max unflagged ct) == 628`.
   - `268 <= BUDGET_MARGIN < 628`.

**Class `TestBudgetInference`:**

6. `test_boundary_4110_vs_4631`
   - Input `[41, 300, 4110, 4631, 4636, 4638, 4652]`.
   - Cap is 4631.
   - Flags are `[False, False, False, True, True, True, True]`.
7. `test_boundary_tail_within_margin`
   - Input `[41, 300, 4110, 4631, 4636, 4638, 4652, 4899]`.
   - Cap is 4631.
   - Flags are `[False, False, False, True, True, True, True, True]`.
8. `test_no_cap_run_max_1200`
   - Input `[58, 1200, 651, 397, 833, 152, 673, 213, 558, 858, 353, 1139, 216, 96]`.
   - Cap is `None`; no flags are set.
9. `test_lone_max_not_flagged`
   - Input `[41, 300, 1200, 4899]` gives cap `None`.
10. `test_dense_top_without_gap_not_flagged`
    - Input `[1200, 1190, 1180, 1170, 1100, 900, 300]` gives cap `None`.
11. `test_gap_below_min_gap_not_flagged`
    - Input `[41, 300, 4400, 4631, 4636, 4638, 4652]` gives cap `None`.
12. `test_all_equal_run_not_flagged`
    - `[41] * 38` gives cap `None` and all flags false.
13. `test_empty_and_short`
    - `infer_budget_cap([])` is `None`; `budget_flags([]) == []`.
    - `infer_budget_cap([4638, 4638, 4638])` is `None`.
14. `test_constants_pinned`
    - `BUDGET_MARGIN == 448`, `BUDGET_BAND == 32`, `BUDGET_MIN_CLUSTER == 4`, `BUDGET_MIN_GAP == 256`.
15. `test_marker_constant`
    - `BUDGET_MARKER == "I have thought about this long enough; time to give my answer"`.
    - `has_budget_marker(None)` is false.
    - `has_budget_marker("x " + BUDGET_MARKER + ".")` is true.
    - `has_budget_marker(BUDGET_MARKER[:-1])` is false.
16. `test_marker_defined_once`
    - Scan every `*.py` file under `Path(__file__).resolve().parent.parent / "src" / "psicotest"` for the literal string.
    - The list of matching file names is exactly `["budget.py"]`.

### 4.2 `tests/test_telemetry.py`

Add one method to `TestTelemetry`:

17. `test_measure_budget_marker`
    - `m = measure("ANSWER: 1", "abc " + BUDGET_MARKER + ".")`.
    - `m["schema"] == 2`.
    - `m["budget"] == {"marker": {"content": False, "reasoning": True}}`.
    - `measure(BUDGET_MARKER, None)["budget"]["marker"] == {"content": True, "reasoning": False}`.
    - `measure(None, None)["budget"]["marker"] == {"content": False, "reasoning": False}`.

### 4.3 `tests/test_server_snapshot.py`

Local test fixtures:

- `STRATA = {"object": "list", "data": [{"id": "iq3_s", "owned_by": "strata", "meta": {"instanceId": "inst-1", "gpus": [0], "label": "Qwen3.8-Flash-Next IQ3_S", "aliases": ["iq3_s"]}}]}`.
- A local `ScriptTransport` with the same shape as the one in `test_runner_client`: it records calls, and script items are `(status, payload-or-bytes)` pairs or exceptions. Bytes are returned raw; anything else goes through `json.dumps(...).encode()`.

**Class `TestClientSnapshot`:**

18. `test_snapshot_ok_strata_payload`
    - Client is `Client(t, "http://fake/v1", "iq3_s", "secret-key")`.
    - The snapshot equals `{"status": "ok", "http_status": 200, "model_id": "iq3_s", "owned_by": "strata", "label": "Qwen3.8-Flash-Next IQ3_S", "instance_id": "inst-1", "gpus": [0], "aliases": ["iq3_s"]}`.
    - Exactly one call, with method `"GET"`, url `"http://fake/v1/models"`, body `None` and timeout 30.
    - The call's `headers["Authorization"] == "Bearer secret-key"`.
19. `test_snapshot_alias_match`
    - Data is `[{"id": "other"}, {"id": "q-int", "meta": {"aliases": ["iq3_s"]}}]`.
    - `model_id == "q-int"`, `aliases == ["iq3_s"]`, status `ok`.
20. `test_snapshot_model_not_listed`
    - Data is `[{"id": "other"}]`.
    - The snapshot equals `null_server_snapshot("model_not_listed", 200)`.
21. `test_snapshot_http_404`
    - The snapshot equals `null_server_snapshot("http_error", 404)`.
22. `test_snapshot_transport_error`
    - The script raises `TransportError("x")`.
    - The snapshot equals `null_server_snapshot("transport_error")`.
23. `test_snapshot_bad_payload`
    - `(200, b"not json")` gives `null_server_snapshot("bad_payload", 200)`.
    - `(200, {"data": "x"})` gives the same.
24. `test_snapshot_bad_types`
    - Meta is `{"gpus": ["0"], "aliases": [1], "label": 5}` with `id == "iq3_s"`.
    - Status is `ok`; `gpus`, `aliases`, `label`, `instance_id` and `owned_by` are all `None`.
25. `test_snapshot_leaves_chat_state`
    - After the snapshot: `_last_errors == []`, `_last_prompt_tokens is None`, `_last_attempts == 0`.
    - A following `chat` call, scripted with an ok chat body for model `iq3_s`, succeeds.
    - That chat call's url ends with `"/chat/completions"`.
    - Its body keys are `{"model", "messages", "max_tokens", "temperature", "top_p"}`.
26. `test_snapshot_x_api_key_scheme`
    - With `auth_scheme="x-api-key"`, the GET headers carry `x-api-key == "secret-key"` and no `Authorization`.

**Class `TestDriverSnapshot`:**

These use `fakes.FakeServer("oracle", battery_layout(7, "A"))` and `FakeServerTransport`, with `client._wait` patched to a no-op. `Intercept(inner, on_get)` routes GETs whose url ends with `/models` to `on_get()` and delegates everything else. It counts GETs.

27. `test_header_snapshot_populated`
    - `on_get` returns `(200, headers, json bytes of STRATA with id and aliases set to "fake-model")`.
    - Exit code is `EXIT_OK`.
    - `records[0]["schema"] == 2`.
    - `records[0]["server"]` equals the full expected dict.
    - There are 38 turn records.
    - `report["server"] == records[0]["server"]`.
    - `report["capability"]["score"] == 29`.
    - The header's `list(...)[-1] == "server"`.
28. `test_header_snapshot_failure_nulls_run_continues`
    - `on_get` raises `TransportError`.
    - Exit code is `EXIT_OK`.
    - `records[0]["server"] == null_server_snapshot("transport_error")`.
    - There are 38 turns and a footer is present.
    - `capability.score == 29`.
29. `test_header_snapshot_default_fake_server`
    - No intercept.
    - Server status is `ok`, `model_id == "fake-model"`.
    - `owned_by`, `label`, `instance_id`, `gpus` and `aliases` are all `None`.
30. `test_resume_does_not_refetch`
    - Run `crasher` (exit `EXIT_TRANSPORT`).
    - Then resume with `oracle` through `Intercept`.
    - The GET count during the resume is 0.
    - `records[0]` is equal before and after the resume.
    - Exit code is `EXIT_OK`.
31. `test_snapshot_redacted_if_key_echoed`
    - `on_get` returns a payload whose label contains `API_KEY`.
    - Exit code is `EXIT_OK`.
    - `records[0]["server"] == null_server_snapshot("redacted", 200)`.

### 4.4 `tests/test_report_budget.py`

`oracle_run(tmp)` works like the helper in `test_runner_report`.

`downgrade(record)` turns a record into schema 1:

- header: set `schema` to 1 and pop `server`;
- turns: set `telemetry.schema` to 1 and pop `telemetry.budget`.

`set_tokens(mapping)` sets `usage.completion_tokens` to `mapping.get(turn, 50 * turn)` for every turn.

32. `test_schema1_archive_loads`
    - Steps: oracle run, then downgrade, then `set_tokens({})`, then `write_report`.
    - `write_report` raises no exception.
    - `report["budget"] == {"cap": None, "budget_hits": 0, "hit_turns": [], "marker_hits": None, "marker_crosscheck": None, "marker_disagree_turns": None}`.
    - `report["server"] is None`.
    - `report["schema"] == 2`.
    - `trunc_count == 0`.
    - `capability.score == 29`.
33. `test_schema1_archive_token_rule_still_applies`
    - Downgrade, then `set_tokens({6: 4638, 11: 4639, 18: 4652, 21: 4652})`.
    - `cap == 4638`, `budget_hits == 4`, `hit_turns == [6, 11, 18, 21]`.
    - The three marker fields are `None`.
34. `test_schema2_crosscheck_counts`
    - No downgrade.
    - `set_tokens({6: 4638, 11: 4639, 18: 4652, 21: 4652, 30: 4794})`.
    - Set `telemetry.budget.marker.reasoning = True` on turns 6, 11, 18 and 21.
    - `report["budget"] == {"cap": 4638, "budget_hits": 5, "hit_turns": [6, 11, 18, 21, 30], "marker_hits": 4, "marker_crosscheck": 37, "marker_disagree_turns": [30]}`.
35. `test_budget_does_not_touch_scoring`
    - Build a report from an unmodified oracle run and from the test-34 modified copy.
    - `capability`, `protocol`, `rules` and `trunc_count` are equal between the two.
    - Every turn's `scoring` and `rules` in the checkpoint are equal to the unmodified ones.
36. `test_budget_key_order`
    - `list(report["budget"]) == ["cap", "budget_hits", "hit_turns", "marker_hits", "marker_crosscheck", "marker_disagree_turns"]`.
    - The top-level keys equal the schema 2 list in 2.5, with `errors` last.
37. `test_trunc_count_separate`
    - Persona `truncator`.
    - `trunc_count == 38`.
    - `report["budget"]["marker_hits"] == 0`.
    - `"budget" in report` and `"trunc_count" in report` are both true and are separate keys.
