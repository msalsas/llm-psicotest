Errata authored in two parts; part 1 is Opus's own errata from the design session, part 2 is a fact audit of the merged code.

## Part 1: architect errata (as emitted with the contract)

1. **`run_live.py` does not write `props.json`.** The merged `tools/run_live.py` makes no `/props` fetch and writes no `props.json`. It only builds an `HTTPTransport` and calls `run_battery`. A repo-wide search finds `/props` only in the test fakes (`with_props`/`no_props` personas, `PROPS_BODY`) and in `docs/contracts/T2-checkers-spec.md`. Nothing needs dropping. `run_live.py` stays unchanged, and the harness (`Client.server_snapshot` → `header.server`) becomes the single source.
2. **The brief's margin interval (248, 788) does not match the fixture.**
   - For a global max-minus-margin rule, the 34 are reproduced only for a margin in [268, 789): 4899 − 4631 = 268 and 4899 − 4110 = 789. At 248, iq2xs-seed11 would lose 4631, 4636, 4638 (three of them), 4639 and 4646.
   - For per-run inference, the bound is [268, 628), set by seed11: 4738 − 4110 = 628.
   - The chosen 448 is valid under all of these.
3. **The fixture's `phrase` column holds booleans, not the marker text.** "Marker constant matches the fixture" is therefore implemented as tests 15–16: a literal pin, a check that the string is defined in exactly one source file, and behavior checks. Tests 2–3 provide the phrase/token agreement.
4. **`budget_hit` is not written into each checkpoint turn.** A flag based on a per-run inferred cap cannot be known when an append-only, fsynced checkpoint turn is written: inferring from the run so far would miss early capped turns. So the per-turn telemetry block (schema 2) carries the marker evidence. The per-turn token-rule flag is derived once per run in `report.budget.hit_turns`, using `summarize_budget` over `budget_flags`.
5. **"Existing suites green unchanged" cannot hold literally with the required schema bumps.** Three existing assertions pin schema 1 and exact key lists (E1–E3). Those are the only edits, and no scoring, outcome or rule assertion is touched.
6. **Schema-1 archives get a real token-rule count.** `completion_tokens` has always been recorded, so `budget_hits` is computed retroactively as an int, not `None`. Only the marker fields and `server` are null.
7. **`trunc_count` is outcome-based.** It counts `TRUNC` outcomes, which the checkers derive from `finish_reason`; it does not read raw `finish_reason`. That is semantically the same and is left unchanged.
8. **The snapshot adds one request.** It adds one `GET {base_url}/models` per fresh run. Requests and bodies on the chat path are unchanged.
9. **One existing test now exercises the snapshot's failure path.** In `test_driver_history_excludes_reasoning`, the Recorder raises a `TypeError` on the bodyless GET. The snapshot catches it, the header records `transport_error`, and the test stays green unchanged.

## Part 2: merged-code fact audit

# T6 implementer errata (facts about the merged code; this file WINS over the contract wherever they contradict)

1. `TransportError` lives in `psicotest/runner/transport.py`, not in `client.py`. New test files import it as `from psicotest.runner.transport import TransportError` (see `tests/fake_transport.py`).
2. The scripted transport in `tests/test_runner_client.py` is `FakeTransport` (around line 40), not `ScriptTransport`. Model the local `ScriptTransport` of `tests/test_server_snapshot.py` on it, but record `timeout` in each call entry as well; the stock one does not record it.
3. `battery_layout` is a function in `psicotest.runner.battery`; driver tests import it as `from psicotest.runner.battery import battery_layout`. `FakeServer` is imported from `tests/fakes.py` as `import fakes`; `FakeServerTransport` from `tests/fake_transport.py`. The Recorder class in `tests/test_runner_driver.py` calls `json.loads(body)` unconditionally, so a bodyless GET raises `TypeError` exactly as the contract's note 9 says.
4. `RESUME_FIELDS` exists at module level in `src/psicotest/runner/checkpoint.py` with value `("manifest_sha256", "seed", "order", "model", "params")`. `checkpoint.validate_resume` compares only these fields, so header schema 2 and the new `server` key cannot break resume. Do not touch `checkpoint.py`.
5. `FakeServer.handle` already answers `GET */models` with `(200, {"object": "list", "data": [{"id": self.model, "object": "model"}]})` (default model `fake-model`) and validates auth headers before routing. `Client` default timeout is `DEFAULT_TIMEOUT = 240`, so `min(self._timeout, SNAPSHOT_TIMEOUT)` is 30 in tests. Legacy `/props` personas (`with_props`, `no_props`, `PROPS_BODY`) stay untouched.
6. Archive naming: copy the contract verbatim to `docs/contracts/T6-budget-telemetry-spec.md` and this errata verbatim to `docs/contracts/T6-budget-telemetry-errata.md`. Delete the three dot-prefixed transport files afterwards. The fixture copy `tests/fixtures/budget_golden.json` must be byte-identical to `.telemetry-fixture.in.json` (verify with sha256sum before deleting the transport file).
