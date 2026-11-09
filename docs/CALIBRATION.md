# Calibration

Live calibration of the battery against a real quantized model, run on each battery version as it was frozen (v2–v6). The purpose is to check that the battery discriminates at the intended difficulty: a quantized model should score clearly below the maximum, and failures should concentrate in identifiable families rather than in format or protocol handling. For this model the premise does not hold at the top: the November standard-budget arms sit near the ceiling (UD-Q3_K_XL 28.25 of 29), so the battery does not discriminate there.

## Setup

This table covers the v2-v6 IQ3_S pilot lines; the standard-budget runs are set up under [Quant comparison on the final composition](#quant-comparison-on-the-final-composition).

| Parameter | Value |
|---|---|
| Model | Qwen3.8-Flash-Next GGUF, quantized IQ3_S |
| Serving | OpenAI-compatible endpoint, model alias `iq3_s` |
| `max_tokens` | 6144 |
| `temperature` | 0.6 |
| `top_p` | 0.95 |
| Order | A |
| Seeds | 7 and 11 (v2: single run) |

The model emits visible chain-of-thought before its answer. Equivalent invocation on the current battery:

```sh
psicotest run --base-url <server>/v1 --model iq3_s --seed 7
psicotest run --base-url <server>/v1 --model iq3_s --seed 11
```

## Results by battery version

Capability score over the version's maximum.

| Version | Max | Seed 7 | Seed 11 | % |
|---|---|---|---|---|
| v2 | 21 | 19 (single run) | — | 90.5 |
| v3 | 21 | 16 | 18 | 76.2 / 85.7 |
| v4 | 23 | 19 | 19 | 82.6 |
| v5 | 27 | 24 | 20 | 88.9 / 74.1 |
| v6 | 29 | 22 | 22 | 75.9 |

Each version added items or raised difficulty ladders, so scores are not comparable across rows; they show where each frozen battery sat relative to its own maximum for this model.

## v6 by family

| Family | Max | Seed 7 | Seed 11 |
|---|---|---|---|
| ST | 4 | 2 | 2 |
| AR | 2 | 2 | 2 |
| AR2 | 1 | 1 | 1 |
| NOOP | 3 | 3 | 3 |
| CSP | 2 | 2 | 2 |
| LOG | 3 | 0 | 0 |
| CNT | 1 | 1 | 0 |
| ERR | 2 | 1 | 2 |
| FPRE | 1 | 0 | 0 |
| SYP | 2 | 2 | 2 |
| IC | 2 | 2 | 2 |
| PR | 2 | 2 | 2 |
| PC | 2 | 2 | 2 |
| IV | 2 | 2 | 2 |
| **Total** | **29** | **22** | **22** |

The two seeds produce the same total and the same per-family results except for one item alternating between CNT and ERR: both seeds fail ST 2/4, LOG 0/3 and FPRE 0/1; seed 7 additionally fails one ERR item, seed 11 the CNT item.

Constrained prose (PR), cross-turn consistency twins (PC) and interview structural metrics (IV) scored 2/2 on both seeds. Zero CJK-range characters were observed in any of the six structured runs across v4, v5 and v6 (two seeds each).

## Known limitation

The battery measures constrained prose, cross-turn consistency and structural prose metrics, but in these runs it has not reproduced the free-form defects this quant shows in casual long conversations: CJK glyph leakage into English text and degradation of sentence structure. Within the battery the model produced no CJK characters and passed every PR, PC and IV item in v2–v6 pilots. Whatever triggers those defects in long unstructured chats is not exercised by the current turn structure. A conversational free-form block aimed at them is future work and is not implemented.

## Re-leveling pilot: LOG to level 0 (November 2026)

Measured 2026-11-03 and 2026-11-04. This is v6 tuning, not a new battery
generation. Pre-re-level v6 starts `a18556a3`, the eight v6l0 runs below
record `6a56ad80`, and the battery shipped with this section starts
`f794a595`.

The decision rules were written down before the extension runs, and the
extension was made to meet them:

- R1. A family is a quant discriminator on a battery when IQ3 (IQ-series)
  scores above IQ2 in at least 2 of 4 seeds and no seed inverts by more than
  one point.
- R2. The LOG re-level enters the composition only if LOG passes R1 on the
  level-0 battery.
- R3. A consistent defect-flag asymmetry (no-answer or reasoning-loop flags
  on IQ2 at the same slots where IQ3 shows none) counts as qualitative
  support independently of scores.
- R4. If R1 fails everywhere, the composition freezes at current levels and
  the experiment is archived here.

Setup: same Strata host as the earlier v6 lines, quant swapped between runs (one
server at a time). Battery variants: "v6r" (ST re-level only, the baseline
for this branch) and "v6l0" (v6r plus LOG slots at level 0). Seeds 7, 11,
13, 17; sixteen full runs. Family points below are the `by_family` values
of each run's report, so they are exactly what the CLI prints; ST has a
maximum of 4, LOG of 3, and the rest of 2.

| Battery | Family | IQ3 per seed | IQ2 per seed | R1 |
|---|---|---|---|---|
| v6r | ST | 3 4 4 3 | 3 3 3 4 | pass |
| v6r | LOG | 0 0 0 1 | 0 0 0 1 | fail |
| v6r | ERR | 2 2 2 2 | 2 2 2 2 | fail |
| v6r | SYP | 2 2 2 2 | 0 2 2 2 | fail |
| v6r | PR | 2 2 2 2 | 1 1 2 1 | pass |
| v6l0 | ST | 4 4 4 4 | 3 3 3 3 | pass |
| v6l0 | LOG | 2 2 3 2 | 1 3 3 1 | pass |
| v6l0 | ERR | 2 2 2 2 | 1 2 2 2 | fail |
| v6l0 | SYP | 2 2 2 2 | 2 2 2 0 | fail |
| v6l0 | PR | 2 1 0 2 | 1 0 0 1 | pass |

R2 is met: at level 0, LOG separates the quants on the level-0 battery
(IQ3 wins 2 of 4 seeds, no inversion above one point); at levels 1/2 it
does not. ST confirms on both batteries, and on v6l0 the gap is exactly
one point on every seed.

Findings:

- The prose premise-to-conclusion item S29 (level 2) carries the cleanest
  defect asymmetry: IQ2 produced no usable answer for S29 on every seed of
  the level-0 battery and on one v6r seed, IQ3 on none of the sixteen runs.
  The three v6r seeds where IQ2 did answer S29 carry reasoning-loop flags
  on those scored-OK turns; IQ3 has no loop flag on S29 anywhere.
- S30 (prose level 3) has the opposite shape: IQ3 loses it on two v6l0
  seeds (wrong answer), IQ2 loses it on two seeds of each battery. Noisy
  either way; it stays at level 3.
- SYP fails R1 on both batteries. It stays in the battery for one
  qualitative reason: surface-twin answer inversions appear on IQ2 in 2 of
  16 runs and on IQ3 in 0 of 16, a defect no other family exposes.
- ERR is identical between quants on v6r (2 2 2 2 both) and on v6l0 IQ2
  loses one item on seed 7. It discriminates nothing and is the removal
  candidate for a future cycle; it is not removed here because doing so
  breaks comparability with archived runs.
- Ceiling hits move with item difficulty. On v6r, IQ3 hits the output
  budget 29 times across the four seeds (11, 9, 0, 9) and IQ2 nine
  times, all on seed 17. On v6l0 the picture flips: IQ2 reaches the output
  ceiling on 23 turns (6, 7, 0, 10) against IQ3 five (all on seed 7), with
  IQ2's hits on easy items, reasoning up to 19k characters and 15 loop
  flags, 8 of them on scored-OK turns. None was recorded as TRUNC.

## Quant comparison on the final composition

Run provenance:

- Model: all four arms serve the same base model, Qwen3.8-Flash-Next GGUF.
  They differ in quantization and server: UD-Q3_K_XL and one IQ2_XS
  deployment are served by Unsloth Studio; IQ3_S and a second IQ2_XS
  deployment run on Strata llama-server. The
  Studio `/v1/models` endpoint reports only `unsloth/Qwen3.8-Flash-Next-GGUF`
  without the quant, so for the UD-Q3_K_XL arm the quant name comes from the
  bench records; the Studio IQ2_XS arm is confirmed via `/props`.
- KV cache: both Unsloth Studio arms run with `q8_0` (operator-reported;
  `/props` does not expose it).
- Battery: final composition, manifest `f794a595` (ST-L1 + LOG-L0), seeds 7,
  11, 13 and 17, 38 scored turns each (29 capability-scored, the rest
  protocol turns). The four UD-Q3_K_XL Studio seeds are clean (rc=0,
  manifest hash verified in the run headers).

Totals per seed (maximum 29), all four arms at `max_tokens=24576`:

| Seed | UD-Q3_K_XL (Studio) | IQ2_XS (Studio) | IQ3_S (Strata) | IQ2_XS (Strata) |
|---|---|---|---|---|
| 7 | 28 | 28 | 29 | 25 |
| 11 | 28 | 26 | 28 | 26 |
| 13 | 28 | 29 | 28 | 26 |
| 17 | 29 | 27 | 27 | 25 |
| Mean | 28.25 | 27.50 | 28.00 | 25.50 |

Family means:

| Family | Max | UD-Q3_K_XL (Studio) | IQ2_XS (Studio) | IQ3_S (Strata) | IQ2_XS (Strata) |
|---|---|---|---|---|---|
| ST | 4 | 4.00 | 4.00 | 4.00 | 3.75 |
| NOOP | 3 | 3.00 | 3.00 | 3.00 | 3.00 |
| LOG | 3 | 3.00 | 2.75 | 3.00 | 2.50 |
| AR | 2 | 2.00 | 2.00 | 2.00 | 2.00 |
| CSP | 2 | 2.00 | 2.00 | 2.00 | 2.00 |
| ERR | 2 | 2.00 | 2.00 | 2.00 | 1.75 |
| SYP | 2 | 2.00 | 2.00 | 2.00 | 0.75 |
| IC | 2 | 2.00 | 2.00 | 2.00 | 2.00 |
| PR | 2 | 2.00 | 2.00 | 1.75 | 1.75 |
| PC | 2 | 2.00 | 2.00 | 2.00 | 2.00 |
| IV | 2 | 2.00 | 1.50 | 2.00 | 2.00 |
| AR2 | 1 | 1.00 | 1.00 | 1.00 | 1.00 |
| CNT | 1 | 1.00 | 0.75 | 1.00 | 1.00 |
| FPRE | 1 | 0.25 | 0.50 | 0.25 | 0.00 |

- Strata IQ2_XS loses its points in SYP (0.75 of 2), LOG (2.50), ST (3.75),
  ERR (1.75), PR (1.75) and FPRE (0.00).
- The other three arms are within 0.25 of every family maximum except IV on
  Studio IQ2_XS (1.50) and FPRE, where no arm exceeds 0.50 of 1.

Acceptance rule, pre-registered before the runs: the candidate must match or
beat IQ3_S on at least 2 of 4 seeds with no per-seed regression greater
than 1. Against the superseded IQ3_S run (mean 26.75) UD-Q3_K_XL is ahead
on all four seeds; against the standard-budget rerun it is ahead on seed 17,
tied on 11 and 13 and one behind on 7, so the rule holds against both
references.

Harness findings that qualify the comparison:

- Unsloth Studio counts reasoning tokens inside `max_tokens`, and at 6144
  tokens the UD-Q3_K_XL arm collapsed (see [Superseded runs](#superseded-runs)),
  so the clean runs use `max_tokens=24576`. Budget telemetry is therefore
  not comparable across servers, and scores are only comparable at the same
  output budget.
- Heavy reasoning turns can exceed 300 s at 24k output, so the pilot resumed
  with a 900 s per-turn timeout. Turn-level checkpoint resume (strict
  turn-sequence and message-hash validation) completed the three interrupted
  runs without re-running scored turns.

### Superseded runs

All ran at 6144 tokens and none is item-pairable with the standard-budget
arms.

- October Strata (the v6l0 runs above): IQ3_S scored 27, 26, 26 and 28
  (mean 26.75), IQ2_XS 24, 24, 22 and 20 (mean 22.5). Their headers record
  manifest stamp `6a56ad80`, which differs from `f794a595`. Zero TRUNC
  outcomes; ceiling hits are in the ceiling-hit finding above.
- Studio UD-Q3_K_XL probes (`unsloth-final-seed*-trunc6144-invalid`):
  reasoning filled the budget and content came back empty
  (`finish_reason=length`), the answer only inside the reasoning.
  `trunc_count` was 22, 33, 22 and 34 of 38 turns and scores 10, 3, 10 and
  2 (mean 6.25, against 28.25 at 24576).

### IQ2_XS at the standard budget, on both hosts (November 2026)

Measured 2026-11-08. The Studio IQ2_XS arm pairs directly against the
UD-Q3_K_XL reference: same server, same KV-cache configuration, same output
budget (24576 tokens).

Setup:

- Model: Qwen3.8-Flash-Next GGUF, quant IQ2_XS, served by Unsloth Studio
  under alias `unsloth/Qwen3.8-Flash-Next-GGUF`. The quant is confirmed via
  `/props` (`model_ftype: IQ2_XS - 2.3125 bpw`), captured before and after
  every seed; props are byte-identical within each seed.
- KV cache and battery as for the reference arm; order A, temp 0.6, top_p
  0.95, `max_tokens=24576`, client timeout 900 s.
- All four runs are clean (rc=0), with no budget-cap hits. Both arms
  emitted visible reasoning content on all 152 turns of each comparison.

In November the Strata IQ2_XS arm was rerun at 24576 tokens on manifest
`f794a595`, with zero truncations and zero budget hits. This removes the
budget and manifest differences of the October run but not the server
confound. The operator reports Strata runs with its defaults, and the Strata
control project ships int8 KV as its default, the same 8-bit class as Studio's
`q8_0`; the value is inferred, not read from the server. Engine parity is not
established: the Strata server version and context size are not recorded.

The Strata IQ3_S arm was rerun the same way, with no truncations, budget hits
or degenerate-sentence flags. All four standard-budget arms share manifest
`f794a595`, so item-level pairing across them is valid.

Pairing base: the 29 capability-scored slots on 4 seeds, 116 paired items,
from the per-turn JSONL scoring records (AMBC slot S13 is scored but outside
the /29). Exact two-sided sign test (McNemar exact) on the discordant items,
read as items won only by the first arm against items won only by the
second:

| Pair | Discordant | p |
|---|---|---|
| Strata IQ3_S vs Strata IQ2_XS (same server) | 11 v 1 | 0.0063 |
| Studio UD-Q3_K_XL vs Strata IQ2_XS | 11 v 0 | 0.0010 |
| Studio IQ2_XS vs Strata IQ2_XS (same quant, two servers) | 11 v 3 | 0.0574 |
| Studio UD-Q3_K_XL vs Studio IQ2_XS (same server) | 4 v 1 | 0.3750 |
| Strata IQ3_S vs Studio IQ2_XS | 5 v 3 | 0.7266 |
| Studio UD-Q3_K_XL vs Strata IQ3_S | 2 v 1 | 1.0000 |

A Bonferroni correction over these six pairs sets the threshold at
0.05 / 6 = 0.00833, and two pairs clear it. Strata IQ3_S against Strata
IQ2_XS shares host, deployment, output budget and manifest and differs in
the quantized file (server version and context size unrecorded for both).
Studio UD-Q3_K_XL against Strata IQ2_XS changes quantization, server and
KV-cache provenance at once. Studio UD-Q3_K_XL against Strata IQ3_S has only
three discordant items, so the test has little power there.

The p-values are indicative, since items within a seed share one
conversation rather than being independent. Each arm is one run per seed,
so run-to-run variance is not measured.

Turn-level pairing of the two Studio arms pairs all 152 scored turns per arm,
not the 116-item capability base: IQ2_XS has 2 upgrades against 4 downgrades
relative to UD-Q3_K_XL, exact McNemar p = 0.6875. The seed-7 upgrade falls on
a protocol clarification turn (S17a), so the capability total does not move.
Seed 11 turn 18 timed out on its second attempt and was recorded TRUNC;
excluding that infrastructure pair leaves 2 against 3, p = 1.0.

Degenerate sentences: IQ2_XS fails `degenerate_sentence` at turn 36 (deep
context, 71 messages) on seeds 11 and 17. The UD-Q3_K_XL reference has zero
degenerate-sentence flags across all 152 turns. This is consistent with
deep-context degradation under the lower-bit quant, though it rests on two
seeds and a single turn.

Timing: IQ2_XS on Studio took 44-81 min per seed, against 57-440 min for
the reference arm. Reference-arm timings include resumed runs, so they
are indicative only.

Interpretation:

- Within one server and one reasoning mode, UD-Q3_K_XL and IQ2_XS are not
  distinguishable at this battery size.
- The only quantization signal that survives correction with the server held
  fixed is the Strata pair; the clearest single-item symptom is deep-context
  sentence degeneration at turn 36 on the Studio IQ2_XS arm.
- The same quant on two servers does not separate significantly, so a server
  effect is neither shown nor excluded.

## Errata

- 2026-11-07: model renamed from Qwen3-8B to Qwen3.8-Flash-Next GGUF (server
  telemetry confirms); R1 wording and the intro's "small quantized model" fixed.
- 2026-11-07: FPRE was 0.25 for all three configurations, not unsolved; IQ3_S
  had 4/4 full PR marks on v6r first; the UD-Q3_K_XL arm ran on Studio, not Strata.
- 2026-11-09: McNemar family gained Studio UD-Q3_K_XL against Strata IQ2_XS
  (six pairs); October Strata runs are neither truncated nor equivalent to
  `f794a595`.
- 2026-11-09: turn-level pairing base is 152 turns, not 148; the family table
  mixed output budgets and now uses the four standard-budget arms.
