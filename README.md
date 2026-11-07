# llm-psicotest

[![CI](https://github.com/msalsas/llm-psicotest/actions/workflows/ci.yml/badge.svg)](https://github.com/msalsas/llm-psicotest/actions/workflows/ci.yml)

A hard reasoning battery for LLMs served behind an OpenAI-compatible `/chat/completions` endpoint, aimed at local servers and quantized models. Each battery version is frozen: every item is produced by a deterministic generator from a seeded RNG, so a given `(battery version, seed, order)` yields byte-identical prompts on any machine, and the slot manifest hash is recorded in every run. Every answer is scored by a programmatic checker against a computed key; no LLM judge is used anywhere. The battery runs as a single multi-turn conversation that also carries format rules, clarification probes, a mid-conversation rule injection and a rule-recall check, so instruction persistence is measured alongside capability. Each run writes a per-turn JSONL transcript (request parameters, raw content, reasoning content, usage, timing, scoring, rule flags, telemetry) and an aggregated `report.json`. Pure Python standard library, no runtime dependencies.

## Install

Requires Python 3.11 or newer.

```sh
git clone https://github.com/msalsas/llm-psicotest.git
cd llm-psicotest
python3 -m pip install -e .
```

This installs the `psicotest` console script. Installation is optional; see `tools/run_live.py` below.

## Quickstart

The API key is read from an environment variable, never from the command line. Local servers that ignore authentication still need a non-empty value.

```sh
export PSICOTEST_API_KEY=sk-local
psicotest run --base-url http://127.0.0.1:8080/v1 --model my-model --seed 7
```

`psicotest run` options:

| Option | Default | Meaning |
|---|---|---|
| `--base-url` | required | Server base URL, OpenAI-compatible |
| `--model` | required | Model name sent in the request |
| `--seed` | required | Instance seed; same seed, same items |
| `--order` | `A` | Turn order `A` or `B` (B permutes the item turns) |
| `--out` | `runs` | Output directory |
| `--max-tokens` | `6144` | `max_tokens` per request |
| `--timeout` | `240` | HTTP timeout, seconds (reasoning-heavy models may need 600-900) |
| `--key-env` | `PSICOTEST_API_KEY` | Environment variable holding the key |
| `--auth` | `bearer` | `bearer` (`Authorization: Bearer`) or `x-api-key` |
| `--resume` | off | Continue an interrupted run from its checkpoint |

Some servers count reasoning tokens inside `max_tokens` (for example Unsloth Studio). For reasoning-heavy models on such servers the `6144` default can truncate most turns; a calibration run of this kind used `--max-tokens 24576` with `--timeout 900`.

Sampling is fixed at `temperature=0.6`, `top_p=0.95`. Without installing, the same run is available as:

```sh
PSICOTEST_API_KEY=sk-local python3 tools/run_live.py --base-url http://127.0.0.1:8080/v1 --model my-model --seed 7
```

`tools/run_live.py` accepts `--base-url`, `--model`, `--seed`, `--order` and `--out` only, with the defaults above for everything else. It must be run from the repository root.

Outputs, in `--out`:

- `v6_<seed>_<order>.jsonl` — checkpoint and transcript: one header record, one record per turn, error records for retried requests, one footer record. Written incrementally; `--resume` validates the header and manifest hash before continuing.
- `v6_<seed>_<order>.report.json` — aggregated report (schema 1).

Exit codes: `0` ok, `1` internal, `2` usage, `3` auth (including missing key), `4` transport, `5` preflight, `6` resume mismatch, `7` protocol, `8` self-test, `9` incompatible server. The runner refuses to write any artifact that contains the API key.

## Battery v6

38 turns: one setup turn, 29 capability items, three ambiguity probes (each an ask turn and a reply turn), one derivable-datum control, one rule-recall turn. The setup turn states three rules for the whole conversation: R1 (last line is exactly `ANSWER: <value>`), R2 (decimal point, no thousands separator, no units on the ANSWER line) and the clarification protocol (reply only `CLARIFICATION: <one question>` when an essential datum is missing). Turn 11 injects R3 (when the problem mentions an animal, add `ANIMAL: <singular name>` immediately before the ANSWER line); four later turns carry an animal trigger.

### Capability families

| Code | Name | Items | What is checked |
|---|---|---|---|
| ST | State tracking | 4 | Final contents of 7 boxes after 60 add/remove/transfer/swap operations |
| AR | Long multiplication | 2 | Exact product of an 8-digit by 5-digit integer with dense carries |
| AR2 | Decimal chain arithmetic | 1 | Multi-operation decimal chain, exact to 2 decimal places |
| NOOP | Irrelevant-information arithmetic | 3 | Word problem with numeric distractors; one item is the distractor-free mirror of another |
| CSP | Constraint satisfaction | 2 | Permutation of 7 entities satisfying 14–16 constraints, verified against the constraints, not a stored answer |
| LOG | Knights, knaves and spy | 3 | Role assignment for 5 agents with one nested statement, unique solution |
| CNT | Conditional counting | 1 | Count of words in a 130-word list satisfying four letter/length conditions |
| ERR | Planted-error detection | 2 | Number of the first erroneous step and the corrected final value in a worked solution with 1 or 3 planted errors |
| FPRE | False premise | 1 | Correct result when the prompt asserts a wrong intermediate product; adopting it scores `PREMISE_ABSORBED` |
| SYP | Sycophancy | 2 | Correct result against a stated authority hint; adopting the hint scores `FLIPPED` |
| IC | Instruction chain | 2 | Token list after a chain of list-editing instructions, including rotations and moves |
| PR | Constrained prose | 2 | Prose block in `BEGIN`/`END` meeting word and sentence counts, a banned letter, required phrases and sentence-start constraints |
| PC | Cross-turn consistency | 2 | Yes/no two-hop question asked twice in paraphrase, far apart; the second twin must be correct and agree with the first |
| IV | Interview prose | 2 | At least 150 words of opinion prose; structural metrics only: no repeated 8-gram, sentence lengths within 3–45 words, word floor |

Twins (CSP, ST, LOG, AR, PC) share an instance with an earlier slot but use a different surface, so a pair tests stability, not recall.

### Protocol slots (not part of the capability score)

| Code | Turns | Checked |
|---|---|---|
| AMB | 3 ask + 3 reply | Ask turn must be a single clarification for the missing datum (`CLAR_OK` / `CLAR_MISS` / `CLAR_BAD`); the reply turn supplies the datum |
| AMBC | 1 | The datum looks missing but is derivable; asking scores `CLAR_OVER` |
| RCL | 1 | Model lists the rules in force; `rcl_score` is the number of R1, R2, R3 recalled (0–3), clarification-protocol recall is recorded but not scored |

## Scoring

- **Capability score**: one point per capability item, 0 or 1. The maximum is derived from the slot table (count of capability slots), not hard-coded; for v6 it is **29**. `report.json` gives the total and a per-family `score`/`max` breakdown.
- **Protocol sub-scores**: `setup_ok`, `clar_ok`, `clar_miss`, `clar_over`, `clar_bad`, `rcl_score`. Reported separately; they do not enter the capability score.
- **Rule flags**: every turn is classified for R1 (`ok`/`fail`/`na`), R2 (`ok`/`fail`/`na`; not applied to CSP and LOG) and, from turn 12, R3 (`hit`, `miss`, `false` for an ANIMAL line without a trigger, `clean`, `na`). Rule flags are reported as counts and do not change item scores.
- **Leak hook**: every response is scanned for CJK-range characters (Han, kana, Hangul, Bopomofo, CJK punctuation). On a capability item, any such character in the visible content forces the outcome to `WRONG`, score 0, flag `leak`. `telemetry.leak_chars` in the report counts Han/kana/Hangul/Bopomofo characters across content and reasoning of all turns.
- **Other telemetry**: truncation count (`TRUNC` outcomes), token totals including reasoning tokens when the server reports them, wall time, repetition-loop count, self-correction marker count, and a per-turn error summary. Reasoning-budget hits are inferred per run from completion tokens (report key budget, cross-checked against the server's budget marker) and reported separately from trunc_count; the run header records a best-effort GET /models snapshot of the served model (header key server).

Item outcomes beyond `OK`/`WRONG` (`NOANS`, `AMBIG`, `TRUNC`, `PREMISE_ABSORBED`, `FLIPPED`, `WRONG_OTHER`, …) and flags (`FMT`, `REASONING_ONLY`, …) are recorded per turn in the JSONL.

### Comparing models

The battery is a comparator, not a quality gate: it does not define a pass or fail threshold. A valid comparison runs different models or servers on the same frozen battery version with the same seeds and item order, then compares the capability score and the per-family breakdown. Scores from different battery versions are not comparable, because each version changes the difficulty of its items.

## Calibration

Live calibration against a quantized 8B model across battery versions v2–v6, with per-family results and known limitations, is in [docs/CALIBRATION.md](docs/CALIBRATION.md).

## Repository layout

```
src/psicotest/
  rng.py            seeded RNG (sole randomness source; stdlib `random` is banned by lint)
  spec.py           Item, Turn, CheckResult, canonical JSON
  generators/       one deterministic generator per family; slots.py holds SLOTS_V6
  checkers/         programmatic checkers, extraction, rule checks, CJK and telemetry
  runner/           transport, client, battery layout, driver, checkpoint, report
  cli.py            `psicotest run`
tools/
  run_live.py       live run without installing
  gen_golden.py     regenerates tests/golden/*.json
tests/              unit, property, golden and fake-transport integration tests
docs/contracts/     implementation contracts (T1–T5E)
```

## Testing

```sh
python3 -m unittest discover -s tests
```

Test modules add `src` to `sys.path` through `tests/_bootstrap.py`. CI (`.github/workflows/ci.yml`) runs the suite on Python 3.11, 3.12 and 3.13, x86-64 and arm64, under `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1`, plus `ruff check` and `ruff format --check`. Golden files in `tests/golden/` pin the RNG stream and every v6 item; any change to generated items fails the golden tests.

## Contracts

`docs/contracts/` holds the implementation contracts each stage was built against: RNG (T1), checkers (T2), rule resurfacing (T2.5), generators (T3), runner (T4), difficulty hardening (T5, T5C, T5E) and the prose block (T5D).

## License

MIT. See [LICENSE](LICENSE).
