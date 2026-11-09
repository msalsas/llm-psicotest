# Calibration

Live calibration of the battery against a real quantized model, run on each battery version as it was frozen (v2–v6). The purpose is to check that the battery discriminates at the intended difficulty: a quantized model should score clearly below the maximum, and failures should concentrate in identifiable families rather than in format or protocol handling.

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
- Budget behavior inverts with difficulty. On v6r, IQ3 hits the reasoning
  budget cap 29 times across the four seeds (11, 9, 0, 9) and IQ2 nine
  times, all on seed 17. On v6l0 the picture flips: IQ2 hits the cap 23
  times (6, 7, 0, 10) against IQ3 five, with IQ2's hits on easy items,
  reasoning up to 19k characters and 15 loop flags, 8 of them on scored-OK
  turns.

## Quant comparison on the final composition

Run provenance:

- Model: all four arms serve the same base model, Qwen3.8-Flash-Next GGUF.
  They differ only in quantization and server: UD-Q3_K_XL and one IQ2_XS
  deployment are served by Unsloth Studio; IQ3_S and a second IQ2_XS
  deployment run on Strata llama-server. The
  Studio `/v1/models` endpoint reports only `unsloth/Qwen3.8-Flash-Next-GGUF`
  without the quant, so for the UD-Q3_K_XL arm the quant name comes from the
  bench records; the Studio IQ2_XS arm is confirmed via `/props` (see
  'IQ2_XS on the same Studio host' below).
- KV cache: both Unsloth Studio arms run with KV cache dtype `q8_0`. This is
  operator-reported server configuration; `/props` does not expose it.
- Battery: final composition, manifest `f794a595` (ST-L1 + LOG-L0), seeds 7,
  11, 13 and 17, 38 scored turns each (29 capability-scored, the rest
  protocol turns). All four runs are clean (rc=0, manifest hash verified in
  the run headers).
- The Strata comparison runs record manifest `6a56ad80` in their headers, a
  pre-patch registry hash; their prompts are verified level-0 (S05 prompt is
  642 chars against 830 in the original v6, same model and seed), making
  them compositionally equivalent to `f794a595`.

Compared against IQ3_S and IQ2_XS (both Strata) on the same seeds. The
Studio IQ2_XS arm is reported separately below. Totals per seed
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
- PR: UD-Q3_K_XL is the only configuration with full marks on all four
  seeds on the final composition (IQ3_S reached 2/2 on every seed only on
  the v6r battery).
- LOG: full marks on all four seeds.
- SYP: IQ2_XS scores 0 on seed 17, which drives its mean.
- FPRE is solved on one seed in four (mean 0.25) by every configuration.
- AR, AR2, CSP, IV, NOOP and PC: full marks for all three configurations.

Acceptance rule, pre-registered before the runs: the candidate must match or
beat IQ3_S on at least 2 of 4 seeds with no per-seed regression greater
than 1. The rule is satisfied outright: 4/4 seeds ahead, no regressions.
UD-Q3_K_XL is the strongest scorer observed on this battery by mean.

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

### IQ2_XS on the same Studio host (November 2026)

Measured 2026-11-08. This arm pairs directly against the UD-Q3_K_XL
reference: same server, same KV-cache configuration, same output budget
(24576 tokens), and both arms emit visible reasoning on every turn.

Setup:

- Model: Qwen3.8-Flash-Next GGUF, quant IQ2_XS, served by Unsloth Studio
  under alias `unsloth/Qwen3.8-Flash-Next-GGUF`. The quant is confirmed via
  `/props` (`model_ftype: IQ2_XS - 2.3125 bpw`), captured before and after
  every seed; props are byte-identical within each seed.
- KV cache: `q8_0`, as for the reference arm (operator-reported, not
  props-verified).
- Battery: final composition, manifest `f794a595`, order A, seeds 7, 11, 13
  and 17, 38 scored turns each (29 capability-scored, the rest protocol
  turns). temp 0.6, top_p 0.95, `max_tokens=24576`, client timeout 900 s.
- All four runs are clean (rc=0), with no budget-cap hits. Both arms
  emitted visible reasoning content on all 152 turns of each comparison
  (verified turn-by-turn in the run records).

Totals per seed (maximum 29):

| Seed | UD-Q3_K_XL (Studio) | IQ2_XS (Studio) |
|---|---|---|
| 7 | 28 | 28 |
| 11 | 28 | 26 |
| 13 | 28 | 29 |
| 17 | 29 | 27 |

Means are 28.25 and 27.5. For orientation only, the same IQ2_XS quant on
Strata scored 24, 24, 22 and 20 (mean 22.5). That comparison is confounded
by a different server and by output budget behavior: Strata ran at a
6144-token budget where reasoning filled the output and truncated content
(see the budget-behavior notes above), while these Studio runs used 24576. Reasoning
was present in both; only its budget regime differs.

In November the Strata IQ2_XS arm was rerun at the standard budget of 24576
tokens on manifest `f794a595`. It scored 25, 26, 26 and 25 (mean 25.5), with
zero truncations and zero budget hits. The rerun removes the truncation
confound described above but not the server confound. The Strata KV cache
uses int8 by default, the same 8-bit class as the `q8_0` used on Studio, so
the KV format is approximately matched. Engine parity is still not
established, because the Strata server version and context size are not
recorded and the build does not report its settings at runtime.
Against Studio IQ2_XS at the same budget, 11 items were won only on Studio
and 3 only on Strata (McNemar exact two-sided p = 0.057). That is suggestive
but not significant at alpha = 0.05 at this battery size. These numbers were
checked against the raw reports by the maintainer of this table.

The Strata IQ3_S arm was rerun the same way at 24576 tokens on manifest
`f794a595`. It scored 29, 28, 28 and 27 (mean 28.0), with no truncations, no
budget hits and no degenerate-sentence flags. All four arms at the standard
budget share manifest `f794a595`, so item-level pairing across them is valid.
Against Strata IQ2_XS, same engine and same budget, 11 items were won only by
IQ3_S and 1 only by IQ2_XS (McNemar exact two-sided p = 0.0063 over 116
paired capability items). Engine and output budget are held equal as far as
they are recorded, so the difference is attributable to quantization. It is
the first significant difference in the table. Each arm is a single run per
seed, so run-to-run variance at fixed settings is not measured, and the
server version is not recorded for either Strata arm. Against Studio
UD-Q3_K_XL the discordant items split 1 to 2 (p = 1.0), which is not a
significant difference, though with three discordant items the test has
little power to detect one, and engine and quantization both differ. Against
Studio IQ2_XS they split 5 to 3 (p = 0.73). The IQ2_XS engine residual from
the previous paragraph (p = 0.057) stands. These numbers were checked against
the raw reports by the maintainer of this table. Within this section four
McNemar comparisons pair the same 116 capability items across the four
standard-budget arms (p = 0.0063, 0.057, 1.0 and 0.73). A Bonferroni
correction over those four keeps the quantization result significant at 0.05
(adjusted p = 0.025) and leaves the IQ2_XS engine residual insignificant.
Other comparisons in this document pair different item sets, so they are not
part of that family.

Turn-level pairing against the reference (same seed, same prompt sequence),
upgrades / downgrades of IQ2_XS relative to UD-Q3_K_XL:

| Seed | Upgrades | Downgrades |
|---|---|---|
| 7 | 1 | 0 |
| 11 | 0 | 2 |
| 13 | 1 | 0 |
| 17 | 0 | 2 |
| Pooled | 2 | 4 |

Pairing covers all scored turns. The seed-7 upgrade falls on a protocol
clarification turn (S17a), which is why the capability total there does not
move; the remaining flips are all capability-scored.

- One of the four downgrades is infrastructure, not quantization: seed 11
  turn 18 timed out on its second attempt and was recorded TRUNC.
- McNemar exact two-sided test on the pooled discordants (2 against 4):
  no significant difference between the two Studio arms (p = 0.6875; 6
  discordant pairs, low power). Excluding the infrastructure TRUNC pair
  leaves 2 upgrades against 3 downgrades, p = 1.0.

Degenerate sentences: IQ2_XS fails `degenerate_sentence` at turn 36 (deep
context, 71 messages) on seeds 11 and 17. The UD-Q3_K_XL reference has zero
degenerate-sentence flags across all 152 turns. This is consistent with
deep-context degradation under the lower-bit quant, though it rests on two
seeds and a single turn.

Timing: IQ2_XS on Studio took 44-81 min per seed, against 57-440 min for
the reference arm. Reference-arm timings include interrupted-and-resumed
runs (see harness findings above), so they are indicative only.

Interpretation:

- Within one server and one reasoning mode, UD-Q3_K_XL and IQ2_XS show no
  significant difference at this battery size.
- The clearest quant-associated signal is deep-context sentence
  degeneration at turn 36.
- The Strata IQ2_XS gap cannot be attributed to the quant alone from these
  data (see the confounds above).

## Errata

- 2026-11-07: earlier revisions named the tested model as Qwen3-8B.
  Incorrect: all runs served Qwen3.8-Flash-Next GGUF; server telemetry
  confirms. The wording of pre-registered rule R1 was corrected accordingly
  (removing the wrong size tag) without changing its meaning.
- 2026-11-07: the final-composition notes said FPRE was unsolved for every
  configuration; the table shows a 0.25 mean (one seed in four) for all
  three. They also called UD-Q3_K_XL the first configuration with 4/4 full
  PR marks; IQ3_S already had that on v6r. The pilot setup said "every v6
  line" ran on Strata; the UD-Q3_K_XL arm ran on Unsloth Studio. The
  introduction's "small quantized model" was a leftover of the wrong size
  claim. All four corrected.
