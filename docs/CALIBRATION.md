# Calibration

Live calibration of the battery against a real quantized model, run on each battery version as it was frozen (v2–v6). The purpose is to check that the battery discriminates at the intended difficulty: a small quantized model should score clearly below the maximum, and failures should concentrate in identifiable families rather than in format or protocol handling.

## Setup

| Parameter | Value |
|---|---|
| Model | Qwen3-8B, quantized IQ3_S |
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

## Pending

An A/B run of the Unsloth Q3_K_XL quant of the same base model on the final v6 battery, under the same parameters and seeds.

## Re-leveling pilot: LOG to level 0 (November 2026)

Measured live on 2026-11-03 and 2026-11-04. This is a tuning of v6, not a new battery generation. The manifest hash is the strict identity: pre-re-level v6 starts `a18556a3`, v6r starts `6a56ad80`. The pending Unsloth A/B line remains valid.

Rules were written before running:

- R1: a family is a discriminator if IQ3 > IQ2 in at least 2 of 4 seeds and no seed has IQ2 > IQ3 by more than 1.
- R2: LOG level 0 enters the battery only if LOG passes R1 on the level-0 battery.
- R3: defect-flag asymmetry counts as qualitative signal.
- R4: no version bump and no composition commit without owner order.

Setup: Qwen3-8B in two quantizations on the same endpoint, IQ3_S (`iq3_s`) and IQ2_XS (`iq2_xs`). Seeds 7, 11, 13, 17; order A; temperature 0.6, top_p 0.95, max_tokens 6144. Two batteries: `v6r` (ST at level 1, LOG S05/S16/S18 at levels 1/2/1) and `v6l0` (ST at level 1, LOG all at level 0). Sixteen full runs.

Family points per seed (seeds 7 / 11 / 13 / 17):

| Battery | Family | IQ3 | IQ2 | R1 |
|---|---|---|---|---|
| v6r | ST | 3 / 4 / 4 / 3 | 3 / 3 / 3 / 4 | pass |
| v6r | LOG | 0 / 0 / 0 / 1 | 0 / 0 / 0 / 1 | fail |
| v6r | ERR | 2 / 2 / 2 / 2 | 2 / 2 / 2 / 2 | fail |
| v6r | SYP | 3 / 3 / 3 / 3 | 1 / 3 / 3 / 3 | fail |
| v6r | PR | 2 / 2 / 2 / 2 | 2 / 2 / 2 / 1 | fail |
| v6l0 | ST | 4 / 4 / 4 / 4 | 3 / 3 / 3 / 3 | pass |
| v6l0 | LOG | 2 / 2 / 3 / 2 | 1 / 3 / 3 / 1 | pass |
| v6l0 | ERR | 2 / 2 / 2 / 2 | 1 / 2 / 2 / 2 | fail |
| v6l0 | SYP | 3 / 3 / 3 / 3 | 3 / 3 / 3 / 1 | fail |
| v6l0 | PR | 2 / 2 / 1 / 2 | 0 / 1 / 1 / 1 | pass |

Outcome: R2 met. LOG level 0 adopted: S05, S16 and S18 now use 5 agents with one nested statement.

R3 findings:

- S29 (PR) was defective (NOANS) for IQ2 in 4/4 seeds on both batteries, and for IQ3 in 0/4.
- S20 (SYP) was defective for IQ2 in 3/4 seeds, against IQ3 in 1/4 on v6r and 0/4 on v6l0.
- LOG at levels 1 and 2 showed a defect inversion. Reasoning-budget cap hits (router budget, `finish_reason` still `stop`) occurred for IQ3 in 2/4 seeds and for IQ2 in 0/4. IQ2 abandoned those items early.
- On v6r, IQ2 produced zero budget-cap hits. On v6l0, it hit the cap 6 to 7 times with about 17k characters of visible reasoning on easy items. Telemetry flagged two of these as reasoning loops; both were still scored OK.

No-think branch: the endpoint ignores `enable_thinking: false` (the guard aborted the probe because `reasoning_content` was non-empty). It honors `reasoning.effort: none`, but that changes the measured semantics after the fact. The no-think variant was closed as not comparable on this server.

ERR: IQ3 and IQ2 scores were identical on every seed of both batteries. Recorded as zero signal and a review candidate for a future version. No action taken in this change.
