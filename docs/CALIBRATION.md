# Calibration

Live calibration of the battery against a real quantized model, run on each battery version as it was frozen (v2–v6). The purpose is to check that the battery discriminates at the intended difficulty: a small quantized model should score clearly below the maximum, and failures should concentrate in identifiable families rather than in format or protocol handling.

## Setup

| Parameter | Value |
|---|---|
| Model | Qwen3.8-Flash-Next GGUF, quantized IQ3_S (with IQ2_XS and UD-Q3_K_XL arms added later) |
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

The battery measures constrained prose, cross-turn consistency and structural prose metrics, but in these runs it has not reproduced the free-form defects this quant shows in casual long conversations: CJK glyph leakage into English text and degradation of sentence structure. Within the battery the model produced no CJK characters and passed every PR, PC and IV item. Whatever triggers those defects in long unstructured chats is not exercised by the current turn structure. A conversational free-form block aimed at them is future work and is not implemented.

## Follow-up: Unsloth A/B (closed)

Done: the Unsloth A/B ran on the final composition (manifest `f794a595`) with the UD-Q3_K_XL quant of the same base model served by Unsloth Studio; see [Quant comparison on the final composition](#quant-comparison-on-the-final-composition).

## Re-leveling pilot: LOG to level 0 (November 2026)

Measured 2026-11-03 and 2026-11-04. This is v6 tuning, not a new battery
generation. The manifest hash remains the strict identity: pre-re-level v6
starts `a18556a3`, the ST re-level starts `6a56ad80`, and the battery shipped
with this section starts `f794a595`. The Unsloth A/B line above is
closed by the section "Quant comparison on the final composition" below.

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

Setup: same Strata host as every v6 line, quant swapped between runs (one
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
- Budget behavior inverts with difficulty. On v6r, IQ3 hits the reasoning
  budget cap 29 times across the four seeds (11, 9, 0, 9) and IQ2 nine
  times, all on seed 17. On v6l0 the picture flips: IQ2 hits the cap 23
  times (6, 7, 0, 10) against IQ3 five, with IQ2's hits on easy items,
  reasoning up to 19k characters and 15 loop flags, 8 of them on scored-OK
  turns.

## Quant comparison on the final composition

Run provenance:

- Model: all three arms serve the same base model, Qwen3.8-Flash-Next GGUF.
  They differ only in quantization and server: UD-Q3_K_XL served by Unsloth
  Studio; IQ3_S and IQ2_XS served by Strata llama-server. The Studio
  `/v1/models` endpoint reports only `unsloth/Qwen3.8-Flash-Next-GGUF`
  without the quant, so the quant name comes from the bench records.
- Battery: final composition, manifest `f794a595` (ST-L1 + LOG-L0), seeds 7,
  11, 13 and 17, 38 scored turns each (29 capability-scored, the rest
  protocol turns). All four runs are clean (rc=0, manifest hash verified in
  the run headers).
- The Strata comparison runs record manifest `6a56ad80` in their headers, a
  pre-patch registry hash; their prompts are verified level-0 (S05 prompt is
  642 chars against 830 in the original v6, same model and seed), making
  them compositionally equivalent to `f794a595`.

Compared against IQ3_S and IQ2_XS on the same seeds. Totals per seed
(maximum 29):

| Seed | UD-Q3_K_XL (Studio) | IQ3_S | IQ2_XS |
|---|---|---|---|
| 7 | 28 | 27 | 24 |
| 11 | 28 | 26 | 24 |
| 13 | 28 | 26 | 22 |
| 17 | 29 | 28 | 20 |

Family means (UD-Q3_K_XL / IQ3_S / IQ2_XS):

| Family | Max | UD-Q3_K_XL (Studio) | IQ3_S | IQ2_XS |
|---|---|---|---|---|
| ST | 4 | 4.0 | 4.0 | 3.0 |
| PR | 2 | 2.0 | 1.25 | 0.5 |
| LOG | 3 | 3.0 | 2.25 | 2.0 |
| CNT | 1 | 1.0 | 1.0 | 0.25 |
| IC | 2 | 2.0 | 2.0 | 1.25 |
| SYP | 2 | 2.0 | 2.0 | 1.5 |
| ERR | 2 | 2.0 | 2.0 | 1.75 |
| FPRE | 1 | 0.25 | 0.25 | 0.25 |

- ST: UD-Q3_K_XL has full marks on all four seeds.
- PR: the first configuration in the pilot with full marks on all four seeds.
- LOG: full marks on all four seeds.
- SYP: IQ2_XS scores 0 on seed 17, which drives its mean.
- FPRE is unsolved for every configuration to date.
- AR, AR2, CSP, IV, NOOP and PC: full marks for all three configurations.

Acceptance rule, pre-registered before the runs: the candidate must match or
beat IQ3_S on at least 2 of 4 seeds with no per-seed regression greater
than 1. The rule is satisfied outright: 4/4 seeds ahead, no regressions.
UD-Q3_K_XL is the strongest scorer observed on this battery.

Harness findings that qualify the comparison:

- Unsloth Studio counts reasoning tokens inside `max_tokens`. At the
  6144-token output budget used for the Strata runs, Qwen3.8-Flash-Next
  filled the entire budget with reasoning and returned empty content
  (trunc_count 22-34 per seed, `finish_reason=length`). The final
  answer appeared only inside the reasoning text. The clean runs use
  `max_tokens=24576`. Budget-family telemetry is therefore server-dependent
  and not comparable across servers; scoring families are comparable because
  prompts are byte-identical.
- Heavy reasoning turns can exceed 300 s at 24k output, so the pilot resumed
  with a 900 s per-turn timeout. Turn-level checkpoint resume (strict
  turn-sequence and message-hash validation) completed the three interrupted
  runs without re-running scored turns.

## Errata

- 2026-11-07: earlier revisions named the tested model as Qwen3-8B.
  Incorrect: all runs served Qwen3.8-Flash-Next GGUF; server telemetry
  confirms. The wording of pre-registered rule R1 was corrected accordingly
  (removing the wrong size tag) without changing its meaning.
