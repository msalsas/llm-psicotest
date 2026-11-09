# Community results

This table collects runs from contributors against battery v6, so that different models, quantizations and servers can be compared on identical prompts. The authoritative calibration data for this repository's own development stays in [docs/CALIBRATION.md](docs/CALIBRATION.md). This file is the open, community-maintained comparison.

## Rules

- Battery v6 only: manifest `f794a595`. Results from older battery versions belong in the contributor's own notes, not in this table. Runs recording any other manifest stamp go under Superseded runs.
- Standard protocol is seeds 7, 11, 13 and 17 with order A, stated in the Seeds column. Single-seed rows are accepted but marked, e.g. `7 (single)`.
- Config notes list server name, server version, context size, KV cache dtype and `max_tokens`. Write `not recorded` for an unknown value, and `operator-reported` or `inferred` for a value not read from the server.
- The standard output budget is `--max-tokens 24576` with a client timeout of 900 s, passed explicitly: the CLI default is 6144, and `tools/run_live.py` cannot change it. On servers that count reasoning tokens inside `max_tokens`, a smaller budget can truncate a reasoning-heavy model's answers and depress its score. A run at any other output budget goes under Superseded runs, stating its budget.
- One row per arm, an arm being one model + quantization + server combination. A new model is a new row. Do not edit other contributors' rows except to fix an obvious typo.
- A rerun of an arm at the standard output budget replaces its earlier row: mark the new row as a rerun in Notable outcomes and move the earlier row to Superseded runs.
- Reviewers may ask for the `report.json` of each run before merging a row. Numbers without a reproducible configuration will not be merged.

## Results

Mean score is the mean capability score over the listed seeds, out of 29. Score % is that mean as a percentage of 29. Rows are sorted by mean score, highest first.

| Date | Model | Quantization | Server / config notes | Seeds | Mean score | Score % | Notable outcomes | By |
|---|---|---|---|---|---|---:|---|---|
| 2026-11 | Qwen3.8-Flash-Next GGUF | UD-Q3_K_XL | Unsloth Studio; max_tokens 24576; server version and context size not recorded; KV q8_0 (operator-reported) | 7, 11, 13, 17 (A) | 28.25 / 29 | 97.4% | Reference arm. Zero degenerate-sentence flags across 152 turns. Per-seed totals 28/28/28/29. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ3_S | Strata llama-server; max_tokens 24576; server version and context size not recorded; KV int8 (inferred from Strata default) | 7, 11, 13, 17 (A) | 28.00 / 29 | 96.6% | Rerun at the standard budget. Zero truncations, budget hits and degenerate-sentence flags across 152 turns. Per-seed totals 29/28/28/27. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Unsloth Studio; max_tokens 24576; server version and context size not recorded; KV q8_0 (operator-reported) | 7, 11, 13, 17 (A) | 27.50 / 29 | 94.8% | Not significantly different from UD-Q3_K_XL (4 v 1, p = 0.3750). Fails degenerate_sentence at turn 36 (deep context) on 2 of 4 seeds. Per-seed totals 28/26/29/27. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Strata llama-server; max_tokens 24576; server version and context size not recorded; KV int8 (inferred from Strata default) | 7, 11, 13, 17 (A) | 25.50 / 29 | 87.9% | Rerun at the standard budget. Zero truncations and zero budget hits on all four seeds. Per-seed totals 25/26/26/25. | msalsas |

All rows in the main table use the same base model, manifest `f794a595` and the standard output budget.

### Superseded runs

Not ranked and not item-pairable with the main table. Details in [docs/CALIBRATION.md](docs/CALIBRATION.md).

| Date | Model | Quantization | Server / config notes | Seeds | Mean score | Score % | Why superseded | By |
|---|---|---|---|---|---|---:|---|---|
| 2026-10 | Qwen3.8-Flash-Next GGUF | IQ3_S | Strata llama-server; max_tokens 6144; manifest `6a56ad80`; server version, context size and KV dtype not recorded | 7, 11, 13, 17 (A) | 26.75 / 29 | 92.2% | Rerun: 28.00. Zero truncated turns; 5, 0, 0 and 0 of 38 turns per seed reached the output ceiling. Per-seed totals 27/26/26/28. | msalsas |
| 2026-10 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Strata llama-server; max_tokens 6144; manifest `6a56ad80`; server version, context size and KV dtype not recorded | 7, 11, 13, 17 (A) | 22.50 / 29 | 77.6% | Rerun: 25.50. Zero truncated turns; 6, 7, 0 and 10 of 38 turns per seed reached the output ceiling. Per-seed totals 24/24/22/20. | msalsas |

## Adding a row

Open a pull request that adds one row to the main table in mean-score order, keeping the column order above. A row moved to Superseded runs keeps its columns, adds its output budget and manifest stamp to the config notes, and replaces Notable outcomes with the rerun's mean score. If your server behaves unusually, for example by counting reasoning tokens inside `max_tokens`, say so in the config notes.
