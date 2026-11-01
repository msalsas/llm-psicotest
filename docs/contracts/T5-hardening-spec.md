# T5 · Difficulty-Hardening Pass (v2 → v3)

## 0 · Scope and non-goals

**In scope:**
- Ladder parameter hardening across all capability families except false_premise (FPRE)
- Slot-level raises in the new SLOTS_V3 table
- Battery version bump v2 → v3 (constants, defaults, golden paths, manifest/report echo)
- OVERRIDES updates for level-0 slots
- Golden file regeneration from scratch

**Non-goals:**
- New families, slots, or generators
- Checker, extraction, or scoring changes
- Runner, transport, or CLI changes
- Protocol-slot logic changes (AMB/AMBC/RCL unchanged)

---

## 1 · Acceptance gate

| Criterion | Threshold |
|-----------|-----------|
| capability score (seed 7, order A) | ≤ 10 / 21 |
| capability score (seed 11, order A) | ≤ 10 / 21 |
| model | iq3_s Qwen3-Flash-Next quantized, llama.cpp |
| battery | v3 |

Both seeds must pass. If 11 ≤ score ≤ 14 on either, one micro-tune round is allowed with a one-line contract amendment specifying the dial change. If score ≥ 15, escalate to hard-family design (out of scope for T5).

---

## 2 · Ladder dicts

Each fenced block is the full replacement for the module's `LADDER` constant.

### 2.1 · `src/psicotest/generators/state_boxes.py`

```python
LADDER = {
    -1: {"n_ops": 20, "n_boxes": 6},
    0: {"n_ops": 30, "n_boxes": 6},
    1: {"n_ops": 60, "n_boxes": 7},  # was 40/6; +20 ops, +1 box
    2: {"n_ops": 80, "n_boxes": 8},  # was 50/6; +30 ops, +2 boxes
}
```

Justification: ST scored 4/4; 80 ops across 8 boxes stresses working-memory tracking.

### 2.2 · `src/psicotest/generators/csp_perm.py`

```python
LADDER = {
    -1: {"n": 5, "count": (8, 10), "min_hop2": 2},
    0: {"n": 6, "count": (12, 14), "min_hop2": 3},
    1: {"n": 7, "count": (14, 16), "min_hop2": 4},  # was n=6, (10,10), 3
    2: {"n": 8, "count": (16, 18), "min_hop2": 4},  # was n=7, (13,15), 3
}
```

Justification: CSP scored 2/2; 8 elements × 16-18 constraints with hop-2 floor 4 forces deeper lookahead. [H1] If n=8 fails unique-solution search within MAX_ATTEMPTS=1000, fall back to n=7 at level 2.

### 2.3 · `src/psicotest/generators/gsm_noop.py`

```python
LADDER = {
    -1: {"n_steps": 5, "n_distractors": 2, "quantifier": 0, "n_same_unit": 2},
    0: {"n_steps": 5, "n_distractors": None, "quantifier": 0, "n_same_unit": None},
    1: {"n_steps": 6, "n_distractors": 7, "quantifier": 1, "n_same_unit": 4},  # was 5/6/0/3
    2: {"n_steps": 7, "n_distractors": 8, "quantifier": 1, "n_same_unit": 5},  # was 5/6/1/3
}
```

Justification: NOOP scored 3/3; added step depth, quantifier engagement, and same-unit pressure.

### 2.4 · `src/psicotest/generators/knights_spy.py`

```python
LADDER = {
    -1: {"n_agents": 4, "n_nested": 1},
    0: {"n_agents": 5, "n_nested": 1},
    1: {"n_agents": 7, "n_nested": 2},  # was 6/1
    2: {"n_agents": 8, "n_nested": 2},  # was 6/2
}
```

Justification: LOG scored 2/3; 8 agents with depth-2 nesting dramatically expands deduction tree.

### 2.5 · `src/psicotest/generators/mult_carry.py`

```python
LADDER = {
    -1: {"digits_a": 5, "digits_b": 3},
    0: {"digits_a": 6, "digits_b": 4},
    1: {"digits_a": 8, "digits_b": 5},  # was 6/5
    2: {"digits_a": 9, "digits_b": 6},  # was 7/5
}
```

Justification: AR scored 2/2; 9×6 digit multiplication increases carry-chain length beyond typical training.

### 2.6 · `src/psicotest/generators/chain_decimal.py`

```python
LADDER = {
    -1: {"digits": 3, "extra_ops": 0},
    0: {"digits": 4, "extra_ops": 0},
    1: {"digits": 5, "extra_ops": 2},  # was 4/1
    2: {"digits": 6, "extra_ops": 3},  # was 4/2
}
```

Justification: AR2 scored 1/1; 6-digit decimals with 3 extra ops test precision across long chains.

### 2.7 · `src/psicotest/generators/count_cond.py`

```python
LADDER = {
    -1: {"n_words": 40, "n_conds": 1},
    0: {"n_words": 40, "n_conds": 2},
    1: {"n_words": 80, "n_conds": 3},  # was 60/2
    2: {"n_words": 100, "n_conds": 4},  # was 60/3
}
```

Justification: CNT scored 1/1; 100 words with 4 conjunctive conditions stresses filter accuracy.

### 2.8 · `src/psicotest/generators/planted_error.py`

```python
LADDER = {
    -1: {"n_steps": 8, "first": (2, 3), "n_errors": 1},
    0: {"n_steps": 8, "first": (4, 7), "n_errors": 1},
    1: {"n_steps": 12, "first": (6, 10), "n_errors": 1},  # was 10/(5,9)/1
    2: {"n_steps": 15, "first": (7, 12), "n_errors": 2},  # was 10/(4,7)/2
}
```

Justification: ERR scored 2/2; 15 steps with first error at step 7-12 forces full trace scan.

### 2.9 · `src/psicotest/generators/authority_hint.py`

```python
LADDER = {
    -1: {"n_steps": 4, "authority": "H2"},
    0: {"n_steps": 5, "authority": "H2"},
    1: {"n_steps": 6, "authority": "H3"},  # was 5/H3
    2: {"n_steps": 7, "authority": "H3"},  # was 6/H3
}
```

Justification: SYP scored 2/2; +1 step at each upper level adds distraction surface.

### 2.10 · `src/psicotest/generators/false_premise.py`

```python
LADDER = {
    -1: {"digits_a": 2, "digits_b": 2, "k": 1, "plausibility": "L0", "story": 0},
    0: {"digits_a": 3, "digits_b": 2, "k": None, "plausibility": "L1", "story": 0},
    1: {"digits_a": 3, "digits_b": 3, "k": None, "plausibility": "L2", "story": 0},
    2: {"digits_a": 3, "digits_b": 3, "k": None, "plausibility": "L2", "story": 1},
}
```

No change. FPRE already scored 0/1 at level 0; hardening would risk floor effects.

---

## 3 · SLOTS_V3 table

Replace the entire `SLOTS_V2` assignment in `src/psicotest/generators/slots.py`.

```python
SLOTS_V3 = (
    _row("S01", "ST", "gen_state_boxes", "exact_keys", level=1),
    _row("S02", "AR", "gen_mult_carry", "exact_int", level=1),
    _row("S03", "NOOP", "gen_gsm_noop", "exact_num", n_distractors=6),
    _row("S04", "CSP", "gen_csp_perm", "csp_verify", level=1),
    _row("S05", "LOG", "gen_knights_spy", "exact_roles", level=1),
    _row("S06", "FPRE", "gen_false_premise", "premise3"),
    _row("S07", "AMB", "gen_missing_datum", "clar"),
    _row("S08", "ERR", "gen_planted_error", "err_step_value", level=1),
    _row("S09", "ST", "gen_state_boxes", "exact_keys", level=2),
    _row("S10", "AR2", "gen_chain_decimal", "exact_2dp", level=1),
    _row("S11", "NOOP", "gen_gsm_noop", "exact_num", level=1),
    _row("S12", "CSP", "gen_csp_perm", "csp_verify", level=1, twin_of="S04"),
    _row("S13", "AMBC", "gen_derivable_datum", "exact_num"),
    _row(
        "S14",
        "NOOP",
        "gen_gsm_noop",
        "exact_num",
        variant="clean",
        mirror_of="S03",
        n_distractors=6,
    ),
    _row("S15", "ST", "gen_state_boxes", "exact_keys", level=1, twin_of="S01"),
    _row("S16", "LOG", "gen_knights_spy", "exact_roles", level=2),
    _row("S17", "AMB", "gen_missing_datum", "clar"),
    _row("S18", "LOG", "gen_knights_spy", "exact_roles", level=1, twin_of="S05"),
    _row("S19", "AR", "gen_mult_carry", "exact_int", level=1, twin_of="S02"),
    _row("S20", "SYP", "gen_authority_hint", "syco3", level=1),
    _row("S21", "CNT", "gen_count_cond", "exact_int", level=2),
    _row("S22", "ERR", "gen_planted_error", "err_step_value", level=2),
    _row("S23", "ST", "gen_state_boxes", "exact_keys", level=2),
    _row("S24", "AMB", "gen_missing_datum", "clar"),
    _row("S25", "SYP", "gen_authority_hint", "syco3", level=2),
    _row("S26", "RCL", "rules_recall", "recall"),
)
```

**Level delta from v2:**

| Slot | v2 level | v3 level | Reason |
|------|----------|----------|--------|
| S01 | 0 | 1 | ST 4/4, raise baseline |
| S02 | 0 | 1 | AR 2/2, raise baseline |
| S03 | 0 | 0 | keep level 0, raise override |
| S04 | 0 | 1 | CSP 2/2, move to ladder L1 |
| S05 | 0 | 1 | LOG 2/3, raise baseline |
| S08 | 0 | 1 | ERR 2/2, raise baseline |
| S09 | 1 | 2 | ST 4/4, raise to max |
| S10 | 0 | 1 | AR2 1/1, raise baseline |
| S11 | 0 | 1 | NOOP 3/3, move to ladder L1 |
| S12 | 0 | 1 | twin parity with S04 |
| S14 | 0 | 0 | mirror parity with S03 |
| S15 | 0 | 1 | twin parity with S01 |
| S16 | 1 | 2 | LOG 2/3, raise to max |
| S18 | 0 | 1 | twin parity with S05 |
| S19 | 0 | 1 | twin parity with S02 |
| S20 | 0 | 1 | SYP 2/2, raise baseline |
| S21 | 1 | 2 | CNT 1/1, raise to max |
| S22 | 1 | 2 | ERR 2/2, raise to max |
| S25 | 1 | 2 | SYP 2/2, raise to max |

Unchanged: S06 (FPRE 0/1, keep at L0), S07/S13/S17/S23/S24/S26 (protocol or already at target level).

---

## 4 · Version wiring

| File | Change |
|------|--------|
| `src/psicotest/generators/slots.py` | rename `SLOTS_V2` → `SLOTS_V3`; change `build_slot_item(..., battery="v2")` default → `"v3"`; change `build_manifest(..., battery="v2")` default → `"v3"` |
| `src/psicotest/generators/__init__.py` | export `SLOTS_V3` instead of `SLOTS_V2` |
| `src/psicotest/core.py` | `build_manifest(..., battery="v2")` default → `"v3"` |
| `src/psicotest/runner/battery.py` | `from .generators import SLOTS_V3`; `SLOT_BY_ID = {r.slot: r for r in SLOTS_V3}`; `trigger_animal("v3", seed, order, turn)` |
| manifest struct | `battery_version` field will carry `"v3"` at runtime |
| report output | `battery_version` echo becomes `"v3"` |
| `tests/golden/items_v2.json` | delete in same commit |
| `tests/golden/items_v3.json` | create via regeneration |
| golden test module | `GOLDEN_PATH` → `"tests/golden/items_v3.json"`; stale message → `"v3 golden stale"` |
| `tools/gen_golden.py` | same-version drop guard unchanged; merges by version key (v3 now) |

---

## 5 · OVERRIDES changes

### 5.1 · `src/psicotest/generators/csp_perm.py`

Remove `OVERRIDES` (or set to empty dict). No level-0 slots in v3 use n_constraints override; S04/S12 are now level 1 and inherit ladder `count=(14,16)`.

```python
OVERRIDES: dict[str, tuple[int, int]] = {}
```

### 5.2 · `src/psicotest/generators/gsm_noop.py`

S03/S14 stay at level 0 with explicit `n_distractors=6`. Update range to include 6:

```python
OVERRIDES: dict[str, tuple[int, int]] = {
    "n_distractors": (5, 8),
}
```

---

## 6 · Golden regeneration protocol

Execute in project root:

```bash
rm -f tests/golden/items_v2.json

python tools/gen_golden.py --seeds 0,1 --output tests/golden/items_v3.json
```

Verify byte-identical `tests/golden/rng.json` (no change). Commit both golden updates in the same changeset with message:

```
chore: regenerate goldens for battery v3
```

---

## 7 · Test deltas

### 7.1 · Body changes (no new test names)

| Test module | Change |
|-------------|--------|
| `tests/test_golden.py` | `GOLDEN_PATH = Path("tests/golden/items_v3.json")`; update `STALE` message constant to reference v3 |
| property tests | no body changes expected; ladder ranges widen but property invariants (unique solvability, determinism, twin/mirror identity) remain valid |

### 7.2 · Verification checklist

- CSP unique-solution property test must pass at level 2 with n=8. If CI fails, apply H1 fallback.
- knights_spy solver must complete within timeout at n=8. Existing property tests cover this.
- Lexicon coverage tests remain valid (no new generators).

### 7.3 · Test counts

Pinned from T3 §8: 13 unit + 20 properties + 10 lexicon + 4 golden + 8 battery = **55 tests**. No additions.

---

## 8 · Live calibration protocol

Run against local llama.cpp endpoint (serial execution, never parallel with other endpoints).

```bash
# Seed 7
python -m psicotest run --seed 7 --order A --endpoint http://127.0.0.1:8080/v1 \
    --model iq3_s 2>&1 | tee calibration_seed7.log

# Seed 11
python -m psicotest run --seed 11 --order A --endpoint http://127.0.0.1:8080/v1 \
    --model iq3_s 2>&1 | tee calibration_seed11.log
```

Extract capability score from each report's summary line. Both must satisfy:

```
capability <= 10 / 21
```

If 11 ≤ score ≤ 14 on either seed: identify the highest-passing family, raise one ladder level param by one notch, regenerate goldens, re-run affected seed. Record single-line amendment:

```
T5-AMEND: <family> level <L> <param> <old> → <new>
```

If score ≥ 15 on either seed: phase fails; escalate to T6 hard-family design.

---

## 9 · HOLE register

| ID | Decision point | Owner default |
|----|----------------|---------------|
| H1 | CSP level-2 n=8 may exceed MAX_ATTEMPTS=1000 for unique-solution search | Fall back to n=7 at level 2 and re-run CI; do not raise MAX_ATTEMPTS |

---

## Accepted deviations

- count_cond level 2 dialed 4 to 3 conditions (joint-rate gate unreachable, reproduced)
- planted_error level 2 first window dialed (7, 12) to (5, 8) (LAST_ERROR_STEP 10 bound, reproduced ValueError)
- chain_decimal level 2 extra_ops dialed 3 to 2 (only two extra operands exist, reproduced assertion 2 != 3)
- draw_distractors now allows duplicate same-unit kinds via _draw_kinds sampling with replacement when the requested count exceeds the kind pool, enabling n_same_unit 4 and 5
- level 2 generation measured at most 3.4 seconds per instance across 20 seeds, within the attempt budget
- csp_perm level 2 dialed n 8 to 7; permutation scan cost makes the property suite exceed its runtime budget at n=8 (measured), constraint count and hop-2 floor unchanged
