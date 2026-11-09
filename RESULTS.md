# Community results

This table collects runs from contributors against battery v6, so that different models, quantizations and servers can be compared on identical prompts. The authoritative calibration data for this repository's own development stays in [docs/CALIBRATION.md](docs/CALIBRATION.md). This file is the open, community-maintained comparison.

## Rules

- Battery v6 only: manifest `f794a595` or a verified compositionally-equivalent manifest. Results from older battery versions belong in the contributor's own notes, not in this table.
- Standard protocol is seeds 7, 11, 13 and 17 with order A. Any deviation must be visible in the Seeds column. Single-seed rows are accepted but marked, e.g. `7 (single)`.
- Report the server and every scoring-relevant flag: server name and version if known, context size, KV cache dtype and the `max_tokens` used. On servers that count reasoning tokens inside `max_tokens`, a too-small budget truncates answers and invalidates the score; state what you used.
- The standard output budget is `--max-tokens 24576` with a client timeout of 900 s, passed explicitly: the CLI default is 6144. Reasoning-heavy models fill a smaller budget with thinking tokens and truncate their answers, which depresses scores independently of model quality; the October Strata runs listed under Superseded runs ran at 6144 for historical reasons. A run at any other output budget is not ranked in the main table: put it under Superseded runs and say which budget it used.
- One row per arm, an arm being one model + quantization + server combination. A new model is a new row. Do not edit other contributors' rows except to fix an obvious typo.
- A rerun of an arm at the standard output budget replaces its earlier row: mark the new row as a rerun in Notable outcomes and move the earlier row to Superseded runs. An arm measured only at a non-standard budget lives under Superseded runs as well. A row that lacks any required config flag (server version, context size, KV cache dtype) must say which ones are missing in its config notes.
- Reviewers may ask for the `report.json` of each run before merging a row. Numbers without a reproducible configuration will not be merged.

## Results

Mean score is the mean capability score over the listed seeds, out of 29. Score % is that mean as a percentage of 29. Rows are sorted by mean score, highest first.

| Date | Model | Quantization | Server / config notes | Seeds | Mean score | Score % | Notable outcomes | By |
|---|---|---|---|---|---|---:|---|---|
| 2026-11 | Qwen3.8-Flash-Next GGUF | UD-Q3_K_XL | Unsloth Studio, KV cache q8_0, max_tokens 24576 | 7, 11, 13, 17 (A) | 28.25 / 29 | 97.4% | Reference arm. Zero degenerate-sentence flags across 152 turns. Per-seed totals 28/28/28/29. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ3_S | Strata llama-server, max_tokens 24576, KV cache int8 (Strata's default when no `--kv` flag is given; inferred from that default, not reported by the server), server version and context size not recorded | 7, 11, 13, 17 (A) | 28.00 / 29 | 96.6% | Rerun of the superseded October IQ3_S run at the standard budget. Zero truncations, zero budget hits and zero degenerate-sentence flags across 152 turns. Per-seed totals 29/28/28/27. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Unsloth Studio, KV cache q8_0, max_tokens 24576 | 7, 11, 13, 17 (A) | 27.50 / 29 | 94.8% | Not significantly different from the UD-Q3_K_XL arm (p = 0.375). Fails degenerate_sentence at turn 36 (deep context) on 2 of 4 seeds. Per-seed totals 28/26/29/27. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Strata llama-server, max_tokens 24576, KV cache int8 (Strata's default when no `--kv` flag is given; inferred from that default, not reported by the server), server version and context size not recorded | 7, 11, 13, 17 (A) | 25.50 / 29 | 87.9% | Rerun of the superseded October IQ2_XS run at the standard budget. Zero truncations and zero budget hits on all four seeds. Per-seed totals 25/26/26/25. | msalsas |

All rows in the main table use the same base model, manifest `f794a595` and the standard output budget, and differ only in quantization, server and KV cache dtype.

### Superseded runs (non-standard output budget)

Runs superseded by a rerun at the standard budget, or measured only at a non-standard budget. They are not ranked and not item-pairable with the main table; each row states its manifest and budget, and they follow the standard seed protocol in the Rules unless a row says otherwise. Details in [docs/CALIBRATION.md](docs/CALIBRATION.md).

| Date | Quantization | Server | Mean score | Score % | Why superseded | By |
|---|---|---|---|---:|---|---|
| 2026-10 | IQ3_S | Strata llama-server, 6144 tokens, manifest `6a56ad80` | 26.75 / 29 | 92.2% | Reran at the standard budget, 28.00. Server version, context size and KV cache dtype not recorded. Per-seed totals 27/26/26/28. | msalsas |
| 2026-10 | IQ2_XS | Strata llama-server, 6144 tokens, manifest `6a56ad80` | 22.50 / 29 | 77.6% | Reran at the standard budget, 25.50. Reasoning filled the 6144-token budget and truncated content. Per-seed totals 24/24/22/20. | msalsas |

## Adding a row

Open a pull request that adds one row to the main table in mean-score order, keeping the column order above. A rerun at the standard budget also moves that arm's earlier row to Superseded runs. If your server behaves unusually, for example by counting reasoning tokens inside `max_tokens`, say so in the config notes.
