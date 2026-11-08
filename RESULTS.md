# Community results

This table collects runs from contributors against battery v6, so that different models, quantizations and servers can be compared on identical prompts. The authoritative calibration data for this repository's own development stays in [docs/CALIBRATION.md](docs/CALIBRATION.md). This file is the open, community-maintained comparison.

## Rules

- Battery v6 only: manifest `f794a595` or a verified compositionally-equivalent manifest. Results from older battery versions belong in the contributor's own notes, not in this table.
- Standard protocol is seeds 7, 11, 13 and 17 with order A. Any deviation must be visible in the Seeds column. Single-seed rows are accepted but marked, e.g. `7 (single)`.
- Report the server and every scoring-relevant flag: server name and version if known, context size, KV cache dtype and the `max_tokens` used. On servers that count reasoning tokens inside `max_tokens`, a too-small budget truncates answers and invalidates the score; state what you used.
- One row per arm, an arm being one model + quantization + server combination. A new model is a new row. Do not edit other contributors' rows except to fix an obvious typo.
- Reviewers may ask for the `report.json` of each run before merging a row. Numbers without a reproducible configuration will not be merged.

## Results

Mean score is the mean capability score over the listed seeds, out of 29. Newest first.

| Date | Model | Quantization | Server / config notes | Seeds | Mean score | Notable outcomes | By |
|---|---|---|---|---|---|---|---|
| 2026-11 | Qwen3.8-Flash-Next GGUF | UD-Q3_K_XL | Unsloth Studio, KV cache q8_0, max_tokens 24576 | 7, 11, 13, 17 (A) | 28.25 / 29 | Reference arm. Zero degenerate-sentence flags across 152 turns. Per-seed totals 28/28/28/29. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Unsloth Studio, KV cache q8_0, max_tokens 24576 | 7, 11, 13, 17 (A) | 27.50 / 29 | McNemar vs UD-Q3_K_XL arm p = 0.6875, not significantly different at this battery size. Fails degenerate_sentence at turn 36 (deep context) on 2 of 4 seeds. Per-seed totals 28/26/29/27. | msalsas |
| 2026-10 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Strata llama-server, max_tokens 6144 | 7, 11, 13, 17 (A) | 22.50 / 29 | Score confounded by output-budget behavior: reasoning filled the 6144-token budget and truncated content. Not comparable to the Studio IQ2_XS row as a quantization effect. Per-seed totals 24/24/22/20. | msalsas |
| 2026-10 | Qwen3.8-Flash-Next GGUF | IQ3_S | Strata llama-server, max_tokens 6144 | 7, 11, 13, 17 (A) | 26.75 / 29 | Same output-budget regime as the Strata IQ2_XS row. Per-seed totals 27/26/26/28. | msalsas |

The four initial rows use the same base model and differ only in quantization and server.

## Adding a row

Open a pull request that adds one line to the table, newest first, keeping the column order above. If your server behaves unusually, for example by counting reasoning tokens inside `max_tokens`, say so in the config notes.
