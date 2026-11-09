# Community results

This table collects runs from contributors against battery v6, so that different models, quantizations and servers can be compared on identical prompts. The authoritative calibration data for this repository's own development stays in [docs/CALIBRATION.md](docs/CALIBRATION.md). This file is the open, community-maintained comparison.

## Rules

- Battery v6 only: manifest `f794a595` or a verified compositionally-equivalent manifest. Results from older battery versions belong in the contributor's own notes, not in this table.
- Standard protocol is seeds 7, 11, 13 and 17 with order A. Any deviation must be visible in the Seeds column. Single-seed rows are accepted but marked, e.g. `7 (single)`.
- Report the server and every scoring-relevant flag: server name and version if known, context size, KV cache dtype and the `max_tokens` used. On servers that count reasoning tokens inside `max_tokens`, a too-small budget truncates answers and invalidates the score; state what you used.
- The standard output budget is `--max-tokens 24576` with a client timeout of 900 s, passed explicitly: the CLI default is 6144. Reasoning-heavy models fill a smaller budget with thinking tokens and truncate their answers, which depresses scores independently of model quality; the two October Strata rows below ran at 6144 for historical reasons, one marked confounded and the other sharing its regime. Deviate only if you state it in the config notes.
- One row per arm, an arm being one model + quantization + server combination. A new model is a new row. Do not edit other contributors' rows except to fix an obvious typo.
- The same arm may have a second row when it is a rerun at a different output budget. Mark that row as a rerun in Notable outcomes. A row that lacks any required config flag (server version, context size, KV cache dtype) must say which ones are missing in its config notes.
- Reviewers may ask for the `report.json` of each run before merging a row. Numbers without a reproducible configuration will not be merged.

## Results

Mean score is the mean capability score over the listed seeds, out of 29. Score % is that mean as a percentage of 29. Rows are sorted by mean score, highest first.

| Date | Model | Quantization | Server / config notes | Seeds | Mean score | Score % | Notable outcomes | By |
|---|---|---|---|---|---|---:|---|---|
| 2026-11 | Qwen3.8-Flash-Next GGUF | UD-Q3_K_XL | Unsloth Studio, KV cache q8_0, max_tokens 24576 | 7, 11, 13, 17 (A) | 28.25 / 29 | 97.4% | Reference arm. Zero degenerate-sentence flags across 152 turns. Per-seed totals 28/28/28/29. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ3_S | Strata llama-server, max_tokens 24576, KV cache int8, Strata's default when no `--kv` flag is given resolved by presets.py in the Strata control project, not in this repo; the operator reports the deployment runs with defaults, and the server does not report the value at runtime; server version and context size not recorded | 7, 11, 13, 17 (A) | 28.00 / 29 | 96.6% | Rerun of the October Strata IQ3_S row at the standard budget. Zero truncations, zero budget hits and zero degenerate-sentence flags across 152 turns. Per-seed totals 29/28/28/27. See [docs/CALIBRATION.md](docs/CALIBRATION.md) for interpretation. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Unsloth Studio, KV cache q8_0, max_tokens 24576 | 7, 11, 13, 17 (A) | 27.50 / 29 | 94.8% | Not significantly different from the UD-Q3_K_XL arm on the 116 capability items (4 against 1 discordant items, McNemar exact p = 0.375). Fails degenerate_sentence at turn 36 (deep context) on 2 of 4 seeds. Per-seed totals 28/26/29/27. | msalsas |
| 2026-10 | Qwen3.8-Flash-Next GGUF | IQ3_S | Strata llama-server, max_tokens 6144 | 7, 11, 13, 17 (A) | 26.75 / 29 | 92.2% | Same output-budget regime as the October Strata IQ2_XS row; server version, context size and KV cache dtype not recorded. See the standard-budget rerun above. Per-seed totals 27/26/26/28. | msalsas |
| 2026-11 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Strata llama-server, max_tokens 24576, KV cache int8, Strata's default when no `--kv` flag is given resolved by presets.py in the Strata control project, not in this repo; the operator reports the deployment runs with defaults, and the server does not report the value at runtime; server version and context size not recorded | 7, 11, 13, 17 (A) | 25.50 / 29 | 87.9% | Rerun of the October Strata IQ2_XS row at the standard budget. Zero truncations and zero budget hits on all four seeds. Per-seed totals 25/26/26/25. See [docs/CALIBRATION.md](docs/CALIBRATION.md) for interpretation. | msalsas |
| 2026-10 | Qwen3.8-Flash-Next GGUF | IQ2_XS | Strata llama-server, max_tokens 6144 | 7, 11, 13, 17 (A) | 22.50 / 29 | 77.6% | Score confounded by output-budget behavior: reasoning filled the 6144-token budget and truncated content. Not comparable to the Studio IQ2_XS row as a quantization effect. See the standard-budget rerun above. Per-seed totals 24/24/22/20. | msalsas |

All rows so far use the same base model and differ only in quantization, server, output budget and KV cache dtype.

## Adding a row

Open a pull request that adds one line to the table in mean-score order, keeping the column order above. If your server behaves unusually, for example by counting reasoning tokens inside `max_tokens`, say so in the config notes.
