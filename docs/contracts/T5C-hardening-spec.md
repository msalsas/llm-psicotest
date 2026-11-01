# T5-C Implementation Contract: Battery v4 Hardening

## Goal

Deliver battery v4 such that model `iq3_s` scores ≤10/23 (capability max rises from 21 to 23 via new IC family) on both seeds 7 and 11, order A. Current baseline is 16/21 (seed 7) and 18/21 (seed 11). Target flip: at least 8 of the 18 passing points on seed 11 must fail under v4.

---

## Global Rules

1. All level-2 generators must complete in ≤3 s worst-case on Raspberry Pi 5.
2. Full suite runtime budget: ≤45 min on Pi 5 with transport timeout 240 s.
3. Deterministic generation from `(battery_version=4, seed, slot, order)`.
4. CJK leak rule applies to capability items only (not protocol slots AMB/AMBC/RCL/setup).
5. English prose everywhere; no CJK in prompts or surfaces.
6. stdlib-only; mypy-clean public signatures; no comments unless load-bearing.

---

## Per-File Diffs

### src/psicotest/generators/csp.py

Replace LADDER:

```python
LADDER: dict[int, dict] = {
    -1: {
        "n": 5,
        "clue_count": (8, 10),
        "min_hop2": 2,
        "neg_unary_frac": 0.0,
        "neg_binary_frac": 0.0,
        "disj_count": 0,
    },
    0: {
        "n": 6,
        "clue_count": (12, 14),
        "min_hop2": 3,
        "neg_unary_frac": 0.0,
        "neg_binary_frac": 0.0,
        "disj_count": 0,
    },
    1: {
        "n": 7,
        "clue_count": (16, 18),
        "min_hop2": 4,
        "neg_unary_frac": 0.0,
        "neg_binary_frac": 0.0,
        "disj_count": 0,
    },
    2: {
        "n": 7,
        "clue_count": (20, 24),
        "min_hop2": 5,
        "neg_unary_frac": 0.25,
        "neg_binary_frac": 0.20,
        "disj_count": (1, 2),
    },
}
```

New clue type enum (module-level):

```python
from enum import Enum, auto


class ClueKind(Enum):
    UNARY_POS = auto()  # "Alice sits in seat 3"
    UNARY_NEG = auto()  # "Alice does not sit in seat 3"
    BINARY_POS = auto()  # "Alice sits immediately next to Bob"
    BINARY_NEG = auto()  # "Alice does not sit next to Bob"
    DISJUNCTIVE = auto()  # "Alice is in seat 2 or seat 5"
```

Clue data shape:

```python
Clue = tuple[ClueKind, ...]
# UNARY_POS:    (ClueKind.UNARY_POS, person_idx: int, seat: int)
# UNARY_NEG:    (ClueKind.UNARY_NEG, person_idx: int, seat: int)
# BINARY_POS:   (ClueKind.BINARY_POS, person_a: int, person_b: int)
# BINARY_NEG:   (ClueKind.BINARY_NEG, person_a: int, person_b: int)
# DISJUNCTIVE:  (ClueKind.DISJUNCTIVE, person_idx: int, seat_a: int, seat_b: int)
```

Replace `_gen_clues` signature and core logic:

```python
def _gen_clues(
    rng: Rng,
    n: int,
    solution: list[int],
    cfg: dict,
) -> list[Clue]:
    """Generate clue set for CSP instance with mixed polarity and disjunctions."""
```

Generation algorithm sketch:
1. Draw `clue_count` from cfg range.
2. Compute disjunction target: `disj_count` if int else `rng.randint(*disj_count)`.
3. Partition remaining clues: `neg_unary_frac` of unaries are NEG, `neg_binary_frac` of binaries are NEG.
4. Generate disjunctive clues first (each names one person, two seats, exactly one seat matches solution).
5. Fill remaining with unary/binary mix respecting polarity fractions.
6. Ensure `min_hop2` binary clues exist (hop-2 = persons 2 apart in solution).
7. Verify uniqueness: only one permutation satisfies all clues.

Surface templates (English):

```python
SURFACE_TEMPLATES = {
    ClueKind.UNARY_POS: "{name} sits in seat {seat}.",
    ClueKind.UNARY_NEG: "{name} does not sit in seat {seat}.",
    ClueKind.BINARY_POS: "{name_a} sits immediately next to {name_b}.",
    ClueKind.BINARY_NEG: "{name_a} does not sit next to {name_b}.",
    ClueKind.DISJUNCTIVE: "{name} is in seat {seat_a} or seat {seat_b}.",
}
```

### src/psicotest/solvers/csp_scan.py

Extend `_check_perm` to handle all clue kinds:

```python
def _check_perm(perm: tuple[int, ...], clues: list[Clue]) -> bool:
    for clue in clues:
        kind = clue[0]
        if kind == ClueKind.UNARY_POS:
            _, pidx, seat = clue
            if perm[pidx] != seat:
                return False
        elif kind == ClueKind.UNARY_NEG:
            _, pidx, seat = clue
            if perm[pidx] == seat:
                return False
        elif kind == ClueKind.BINARY_POS:
            _, pa, pb = clue
            if abs(perm[pa] - perm[pb]) != 1:
                return False
        elif kind == ClueKind.BINARY_NEG:
            _, pa, pb = clue
            if abs(perm[pa] - perm[pb]) == 1:
                return False
        elif kind == ClueKind.DISJUNCTIVE:
            _, pidx, sa, sb = clue
            if perm[pidx] not in (sa, sb):
                return False
    return True
```

### src/psicotest/generators/noop.py

Replace LADDER:

```python
LADDER: dict[int, dict] = {
    -1: {"distractor_count": 4, "allow_dup_kinds": False},
    0: {"distractor_count": 5, "allow_dup_kinds": False},
    1: {"distractor_count": 6, "allow_dup_kinds": True},
    2: {"distractor_count": 8, "allow_dup_kinds": True},
}
```

Add near-miss distractor kinds (module-level constant):

```python
DISTRACTOR_KINDS: list[str] = [
    "red_herring_arithmetic",
    "plausible_date",
    "irrelevant_definition",
    "unrelated_fact",
    "contextual_trivia",
    "misleading_statistic",
    "false_premise",
    "circular_reference",
]
```

Sampling uses `rng.choices(DISTRACTOR_KINDS, k=distractor_count)` when `allow_dup_kinds=True`.

Checker verification note: existing `checkers/noop.py` uses exact set equality via `set(parsed) == set(expected)`. Confirm this rejects supersets; if not, change to `parsed == expected` after sorting both.

### src/psicotest/generators/err.py

Replace LADDER:

```python
LADDER: dict[int, dict] = {
    -1: {
        "chain_len": 12,
        "n_errors": 1,
        "min_gap": 2,
        "first_error_after": 0,
        "last_error_step": 10,
    },
    0: {
        "chain_len": 14,
        "n_errors": 2,
        "min_gap": 2,
        "first_error_after": 2,
        "last_error_step": 12,
    },
    1: {
        "chain_len": 16,
        "n_errors": 2,
        "min_gap": 3,
        "first_error_after": 2,
        "last_error_step": 13,
    },
    2: {
        "chain_len": 18,
        "n_errors": 3,
        "min_gap": 3,
        "first_error_after": 3,
        "last_error_step": 14,
    },
}
```

Constraint summary for level 2:
- 18 steps total.
- 3 errors.
- No error in steps 0, 1, 2 (first_error_after=3 means earliest error at step 3).
- Errors at steps ≤14.
- Minimum 3 steps between consecutive errors.
- Valid error positions with gap 3 in range [3, 14]: e.g., {3, 7, 11}, {4, 8, 12}, {3, 8, 13}, etc.

Error placement algorithm:

```python
def _place_errors(rng: Rng, cfg: dict) -> list[int]:
    first = cfg["first_error_after"]
    last = cfg["last_error_step"]
    gap = cfg["min_gap"]
    n = cfg["n_errors"]
    # Greedy random: pick first error in [first, last - (n-1)*gap]
    # then next in [prev+gap, ...], etc.
    positions = []
    lo = first
    for i in range(n):
        hi = last - (n - 1 - i) * gap
        pos = rng.randint(lo, hi)
        positions.append(pos)
        lo = pos + gap
    return positions
```

### src/psicotest/generators/cnt.py

Replace LADDER:

```python
LADDER: dict[int, dict] = {
    -1: {
        "word_count": (40, 60),
        "cond_count": 1,
        "negated": False,
        "joint_rate_range": (0.15, 0.35),
    },
    0: {
        "word_count": (60, 80),
        "cond_count": 1,
        "negated": False,
        "joint_rate_range": (0.12, 0.28),
    },
    1: {
        "word_count": (80, 100),
        "cond_count": 2,
        "negated": False,
        "joint_rate_range": (0.08, 0.20),
    },
    2: {
        "word_count": (100, 120),
        "cond_count": 2,
        "negated": True,
        "joint_rate_range": (0.05, 0.15),
    },
}
```

Condition types (module-level):

```python
CONDITION_TYPES: list[str] = [
    "starts_with",
    "ends_with",
    "contains_substring",
    "length_equals",
    "length_greater_than",
]
```

Negated compound surface example:
> "Count words that do NOT both start with 's' and have length greater than 5."

Satisfiability argument for level 2:
- Word pool of 100-120 words drawn from English word lists.
- Two conditions with negation: we count words failing at least one condition.
- Joint rate 0.05-0.15 means 5-18 words satisfy both conditions.
- Complement (negated count) = 82-115 words.
- Generator rejection-samples until joint rate falls in range; with 100+ word corpus and two independent conditions each affecting ~30% of words, P(joint in [0.05, 0.15]) ≈ 0.6 per attempt. Expected attempts ≤2.

### src/psicotest/generators/ar.py

Replace LADDER:

```python
LADDER: dict[int, dict] = {
    -1: {
        "op": "add",
        "digits": (2, 2),
        "chain_steps": 1,
        "decimal": False,
        "allow_negative_intermediate": False,
    },
    0: {
        "op": "mul",
        "digits": (2, 2),
        "chain_steps": 1,
        "decimal": False,
        "allow_negative_intermediate": False,
    },
    1: {
        "op": "mul",
        "digits": (2, 3),
        "chain_steps": 1,
        "decimal": False,
        "allow_negative_intermediate": False,
    },
    2: {
        "op": "mixed",
        "digits": (3, 3),
        "chain_steps": 2,
        "decimal": True,
        "allow_negative_intermediate": True,
    },
}
```

Level 2 instance structure:
1. Step 1: 3-digit × 3-digit multiplication → intermediate A (up to 6 digits).
2. Step 2: A minus B where B > A chosen to produce negative intermediate C.
3. Final: C + D where D chosen so final answer is positive (avoids negative final confusion).

Surface template:

```
Calculate the following in order:
Step 1: {a} × {b} = ?
Step 2: (result of Step 1) − {c} = ?
Step 3: (result of Step 2) + {d} = ?

Provide only the final numeric answer.
```

Decimal variant: one operand is `X.YZ` form with 2 decimal places; intermediate stays exact.

### src/psicotest/generators/ar2.py

Replace LADDER:

```python
LADDER: dict[int, dict] = {
    -1: {"extra_operands": 1, "ops": ["+"], "precedence_trap": False},
    0: {"extra_operands": 2, "ops": ["+", "-"], "precedence_trap": False},
    1: {"extra_operands": 2, "ops": ["+", "*"], "precedence_trap": True},
    2: {"extra_operands": 2, "ops": ["+", "-", "*"], "precedence_trap": True, "parens": True},
}
```

Level 2 design (2 extra operands = 3 total operands a, b, c):
- Expression form: `(a OP1 b) OP2 c` where parentheses are explicit in surface.
- Precedence trap: surface text shows arithmetic without parentheses first, then clarifies with parentheses.
- Example surface: "What is 7 + 3 × 5, computed as (7 + 3) × 5?"
- This tests whether model follows explicit parenthetical grouping vs. standard precedence.

Operations chosen so parenthetical grouping differs from standard precedence:
- Pattern: `(a + b) * c` where standard `a + b * c` gives different result.
- Or: `(a - b) * c` vs `a - b * c`.

### src/psicotest/generators/st.py

Replace LADDER:

```python
LADDER: dict[int, dict] = {
    -1: {"boxes": 2, "ops": 40},
    0: {"boxes": 3, "ops": 60},
    1: {"boxes": 3, "ops": 80},
    2: {"boxes": 4, "ops": 120},
}
```

Solver unchanged (simulation). Generator ensures 120 ops completes in <1 s via simple loop.

### src/psicotest/generators/syp.py

Replace LADDER:

```python
LADDER: dict[int, dict] = {
    -1: {"word_count": (200, 250), "error_count": 1, "semantic_errors": 0},
    0: {"word_count": (250, 300), "error_count": 2, "semantic_errors": 0},
    1: {"word_count": (300, 400), "error_count": 2, "semantic_errors": 1},
    2: {"word_count": (450, 550), "error_count": 3, "semantic_errors": 1},
}
```

Semantic error types (off-by-one facts):

```python
SEMANTIC_ERROR_TEMPLATES: list[tuple[str, str]] = [
    ("founded in {year}", "founded in {year + 1}"),
    ("{n} countries", "{n + 1} countries"),
    ("the {ordinal} largest", "the {ordinal + 1} largest"),
    ("{n} percent", "{n + 1} percent"),
    ("since {year}", "since {year - 1}"),
]
```

Checker update in `checkers/syp.py`:
- Extract planted error spans from instance metadata.
- For each planted error, check if candidate reproduces the erroneous value.
- Paraphrase tolerance: use token-level Jaccard on non-error spans; threshold 0.7.
- If any planted error value appears in candidate answer → FAIL.

### src/psicotest/generators/instr_chain.py (NEW FILE)

```python
"""INSTRUCTION_CHAIN generator: sequential token-list transformations."""

from __future__ import annotations
from typing import Any
from psicotest.rng import Rng

LADDER: dict[int, dict] = {
    -1: {"token_count": 6, "op_count": 4, "has_rotate": False, "has_move": False, "decoy": True},
    0: {"token_count": 7, "op_count": 4, "has_rotate": True, "has_move": False, "decoy": True},
    1: {"token_count": 8, "op_count": 5, "has_rotate": True, "has_move": True, "decoy": True},
    2: {"token_count": 9, "op_count": 6, "has_rotate": True, "has_move": True, "decoy": True},
}

TOKEN_POOL: list[str] = [
    "apple",
    "bronze",
    "candle",
    "delta",
    "ember",
    "frost",
    "grain",
    "harbor",
    "index",
    "jasper",
    "kindle",
    "lemon",
    "marble",
    "noble",
    "orbit",
    "prism",
    "quartz",
    "riddle",
    "spark",
    "timber",
    "umbra",
    "velvet",
    "willow",
    "xenon",
    "yellow",
    "zephyr",
]

OP_KINDS: list[str] = ["reverse", "rotate", "replace", "swap", "move"]


def draw(rng: Rng, cfg: dict) -> dict[str, Any] | None:
    """Generate instruction chain instance."""
    ...


def valid(instance: dict[str, Any]) -> bool:
    """Validate instance structure."""
    ...


def surface(instance: dict[str, Any]) -> str:
    """Build surface prompt text."""
    ...
```

Operation definitions:

| Op | Params | Effect |
|----|--------|--------|
| reverse | none | Reverse entire list |
| rotate | k: int | Rotate right by k positions |
| replace | old: str, new: str | Replace token `old` with `new` |
| swap | i: int, j: int | Swap positions i and j (0-indexed) |
| move | i: int | Move token at position i to end |

Surface template:

```
You have the following list of tokens:
[{tokens joined by ", "}]

Apply these operations in order:
1. {op1 description}
2. {op2 description}
...
N. {opN description}

Note: Ignore instruction {k} above.

What is the final list? Provide your answer as a comma-separated list on the ANSWER: line.
```

**HOLE DECISION — Decoy semantics**: The "Note: Ignore instruction {k}" line is a TRAP. The correct answer executes ALL instructions including instruction k. The decoy tests whether the model incorrectly skips an instruction. Checker accepts only the result of applying all operations in sequence.

Answer protocol: `ANSWER: token1, token2, ..., tokenN`

### src/psicotest/solvers/instr_chain.py (NEW FILE)

```python
"""Deterministic solver for INSTRUCTION_CHAIN."""

from __future__ import annotations
from typing import Any


def solve(instance: dict[str, Any]) -> list[str]:
    """Apply all operations in sequence, ignoring decoy instruction."""
    tokens = list(instance["tokens"])
    for op in instance["operations"]:
        kind = op["kind"]
        if kind == "reverse":
            tokens = tokens[::-1]
        elif kind == "rotate":
            k = op["k"] % len(tokens)
            tokens = tokens[-k:] + tokens[:-k]
        elif kind == "replace":
            tokens = [op["new"] if t == op["old"] else t for t in tokens]
        elif kind == "swap":
            i, j = op["i"], op["j"]
            tokens[i], tokens[j] = tokens[j], tokens[i]
        elif kind == "move":
            i = op["i"]
            tokens.append(tokens.pop(i))
    return tokens
```

### src/psicotest/checkers/instr_chain.py (NEW FILE)

```python
"""Checker for INSTRUCTION_CHAIN family."""

from __future__ import annotations
import re
from typing import Any


def check(instance: dict[str, Any], response: str) -> tuple[bool, str]:
    """Verify ANSWER: line matches expected token list exactly."""
    expected = instance["expected"]
    match = re.search(r"ANSWER:\s*(.+)", response, re.IGNORECASE)
    if not match:
        return False, "no_answer_line"
    raw = match.group(1).strip()
    parsed = [t.strip().lower() for t in raw.split(",")]
    if parsed == [t.lower() for t in expected]:
        return True, "ok"
    return False, "mismatch"
```

### src/psicotest/generators/slots.py

Delete `SLOTS_V3`, add `SLOTS_V4`:

```python
SLOTS_V4: list[tuple[str, str, int, float]] = [
    # (slot_id, generator, level, weight)
    # ST family (4 points)
    ("S01", "gen_st", -1, 1.0),
    ("S02", "gen_st", 0, 1.0),
    ("S03", "gen_st", 1, 1.0),
    ("S04", "gen_st", 2, 1.0),
    # AR family (2 points)
    ("S05", "gen_ar", 0, 1.0),
    ("S06", "gen_ar", 2, 1.0),
    # AR2 family (1 point)
    ("S07", "gen_ar2", 2, 1.0),
    # NOOP family (3 points)
    ("S08", "gen_noop", 0, 1.0),
    ("S09", "gen_noop", 1, 1.0),
    ("S10", "gen_noop", 2, 1.0),
    # CSP family (2 points)
    ("S11", "gen_csp", 1, 1.0),
    ("S12", "gen_csp", 2, 1.0),
    # LOG family (3 points)
    ("S13", "gen_log", 0, 1.0),
    ("S14", "gen_log", 1, 1.0),
    ("S15", "gen_log", 2, 1.0),
    # CNT family (1 point)
    ("S16", "gen_cnt", 2, 1.0),
    # ERR family (2 points)
    ("S17", "gen_err", 1, 1.0),
    ("S18", "gen_err", 2, 1.0),
    # FPRE family (1 point)
    ("S19", "gen_fpre", 2, 1.0),
    # SYP family (2 points)
    ("S20", "gen_syp", 1, 1.0),
    ("S21", "gen_syp", 2, 1.0),
    # Protocol slots (not capability)
    ("S22", "gen_amb", 0, 1.0),
    ("S23", "gen_ambc", 0, 1.0),
    ("S24", "gen_rcl", 0, 1.0),
    ("S25", "gen_setup", 0, 1.0),
    ("S26", "gen_setup", 1, 1.0),
    # IC family (2 points) — NEW
    ("S27", "gen_instr_chain", 1, 1.0),
    ("S28", "gen_instr_chain", 2, 1.0),
]


def build_slot_item(slot_id: str, seed: int, order: str, battery: str = "v4") -> dict: ...
```

**HOLE DECISION — Slot IDs**: S27 and S28 for INSTRUCTION_CHAIN (extend range to 28).

### src/psicotest/generators/__init__.py

Update imports:

```python
from psicotest.generators.slots import SLOTS_V4
from psicotest.generators.instr_chain import draw as gen_instr_chain

__all__ = [
    "SLOTS_V4",
    # ... existing generators ...
    "gen_instr_chain",
]
```

### src/psicotest/generators/registry.py

Change battery literal in golden loop:

```python
BATTERY = "v4"
```

### src/psicotest/runner/battery.py

```python
from psicotest.generators.slots import SLOTS_V4

SLOT_BY_ID: dict[str, tuple] = {s[0]: s for s in SLOTS_V4}
```

Update `trigger_animal` if it references battery version (change `"v3"` → `"v4"`).

### src/psicotest/runner/report.py

Update imports and constants:

```python
from psicotest.generators.slots import SLOTS_V4


def battery_version() -> str:
    return "v4"


CAPABILITY_SLOTS: set[str] = {
    "S01",
    "S02",
    "S03",
    "S04",  # ST
    "S05",
    "S06",  # AR
    "S07",  # AR2
    "S08",
    "S09",
    "S10",  # NOOP
    "S11",
    "S12",  # CSP
    "S13",
    "S14",
    "S15",  # LOG
    "S16",  # CNT
    "S17",
    "S18",  # ERR
    "S19",  # FPRE
    "S20",
    "S21",  # SYP
    "S27",
    "S28",  # IC (new)
}

CAPABILITY_MAX = 23
```

### src/psicotest/runner/driver.py

Fix filename bug and update version:

```python
BATTERY_VERSION = "v4"


def _checkpoint_path(seed: int, order: str) -> str:
    return f"v4_{seed}_{order}.jsonl"


def _report_path(seed: int, order: str) -> str:
    return f"v4_{seed}_{order}.report.json"
```

### src/psicotest/runner/client.py

Raise default timeout:

```python
DEFAULT_TIMEOUT = 240
```

### src/psicotest/tools/run_live.py

Update timeout:

```python
transport = HTTPTransport(timeout=240)
```

### src/psicotest/tools/gen_golden.py

Update battery literal and version guard:

```python
BATTERY = "v4"


def main():
    if BATTERY != "v4":
        raise RuntimeError("gen_golden expects battery v4")
    ...
```

---

## CJK Leak Rule — Scoring Hook

Location: `src/psicotest/runner/scoring.py` (new file) or inline in `report.py`.

Hook point: After extracting candidate answer content, before calling family-specific checker.

```python
import re

CJK_PATTERN = re.compile(
    r"[\u4e00-\u9fff"  # Han
    r"\u3040-\u309f"  # Hiragana
    r"\u30a0-\u30ff"  # Katakana
    r"\uac00-\ud7af"  # Hangul
    r"\u3100-\u312f"  # Bopomofo
    r"\u3000-\u303f"  # CJK punctuation
    r"]"
)


def check_cjk_leak(content: str) -> bool:
    """Return True if content contains any CJK character or punctuation."""
    return bool(CJK_PATTERN.search(content))


def score_item(slot_id: str, instance: dict, response: str) -> dict:
    """Score a single item, applying leak rule first for capability slots."""
    from psicotest.runner.report import CAPABILITY_SLOTS

    # Extract answer content (not reasoning)
    answer_content = extract_answer_content(response)

    if slot_id in CAPABILITY_SLOTS:
        if check_cjk_leak(answer_content):
            return {"outcome": "FAIL", "flag": "leak", "detail": "cjk_in_content"}

    # Proceed to family checker
    checker = get_checker_for_slot(slot_id)
    passed, detail = checker(instance, response)
    return {"outcome": "PASS" if passed else "FAIL", "flag": None, "detail": detail}
```

Rationale for scoring path vs. telemetry: Telemetry already counts CJK for observation. The leak rule is a deterministic quality gate that affects the score, so it belongs in scoring logic, not telemetry. This makes it model-agnostic and reproducible.

---

## Test Updates

### Golden corpus regeneration

```bash
rm tests/golden/items_v3.json
PYTHONPATH=src python3 tools/gen_golden.py
# Creates tests/golden/items_v4.json
```

### tests/test_generators_properties.py mirror constants

Update these constants to match new LADDERs:

```python
CNT_LADDER_LEVELS = {-1, 0, 1, 2}
CNT_LEVEL2_COND_COUNT = 2
CNT_LEVEL2_NEGATED = True

ERR_LEVEL2_N_ERRORS = 3
ERR_LEVEL2_CHAIN_LEN = 18
ERR_LEVEL2_MIN_GAP = 3
ERR_LEVEL2_FIRST_ERROR_AFTER = 3
ERR_LEVEL2_LAST_ERROR_STEP = 14

AR2_LEVEL2_EXTRA_OPERANDS = 2
AR2_LEVEL2_PARENS = True

CSP_LEVEL2_CLUE_COUNT_RANGE = (20, 24)
CSP_LEVEL2_MIN_HOP2 = 5
CSP_LEVEL2_DISJ_COUNT_RANGE = (1, 2)

IC_LEVEL2_TOKEN_COUNT = 9
IC_LEVEL2_OP_COUNT = 6
IC_LADDER_LEVELS = {-1, 0, 1, 2}

REALIZED_N_SLOTS = 28
CAPABILITY_MAX = 23
```

### New test file: tests/test_instr_chain.py

```python
"""Tests for INSTRUCTION_CHAIN generator and solver."""

import unittest
from psicotest.rng import Rng
from psicotest.generators.instr_chain import draw, valid, LADDER
from psicotest.solvers.instr_chain import solve
from psicotest.checkers.instr_chain import check


class TestInstrChain(unittest.TestCase):
    def test_draw_all_levels(self):
        for level in LADDER:
            rng = Rng(seed=42, slot="S27", battery_version=4)
            instance = draw(rng, LADDER[level])
            self.assertIsNotNone(instance)
            self.assertTrue(valid(instance))

    def test_solver_deterministic(self):
        rng = Rng(seed=42, slot="S27", battery_version=4)
        instance = draw(rng, LADDER[2])
        result1 = solve(instance)
        result2 = solve(instance)
        self.assertEqual(result1, result2)

    def test_checker_exact_match(self):
        instance = {"expected": ["apple", "bronze", "candle"]}
        passed, _ = check(instance, "ANSWER: apple, bronze, candle")
        self.assertTrue(passed)

    def test_checker_rejects_subset(self):
        instance = {"expected": ["apple", "bronze", "candle"]}
        passed, _ = check(instance, "ANSWER: apple, bronze")
        self.assertFalse(passed)

    def test_decoy_ignored_in_solver(self):
        rng = Rng(seed=7, slot="S28", battery_version=4)
        instance = draw(rng, LADDER[2])
        # Solver applies ALL ops; decoy_instruction_index in instance is metadata only
        result = solve(instance)
        self.assertEqual(len(result), LADDER[2]["token_count"])
```

---

## Accepted Deviations Policy

Create file `docs/contracts/T5C-hardening-spec.md` with this header:

```markdown
# T5-C Implementation Deviations

This document records deviations from the T5-C contract during implementation.

## Format

Each deviation entry:
- **Section**: Contract section reference
- **Deviation**: What changed
- **Rationale**: Why the change was necessary
- **Impact**: Effect on acceptance gate or determinism

---

## Deviations

(none yet)
```

Implementer must append entries here for any deviation from this contract.

---

## House Style

- No comments unless load-bearing (e.g., explaining non-obvious constraint).
- English everywhere: prompts, surfaces, code, docstrings.
- stdlib only: no numpy, no external deps.
- mypy-clean type hints on all public functions.
- No new dependencies.

---

## Determinism and Cost Budget

### Per-instance generation limits (worst-case, Pi 5)

| Family | Level 2 budget | Critical knob |
|--------|----------------|---------------|
| CSP | 2.5 s | n=7 (5040 permutations), uniqueness check |
| ERR | 0.5 s | chain_len=18 |
| CNT | 1.0 s | word_count=120, rejection sampling |
| ST | 0.8 s | ops=120 |
| SYP | 1.5 s | word_count=550, error placement |
| IC | 0.3 s | op_count=6 |
| AR | 0.1 s | trivial |
| AR2 | 0.1 s | trivial |
| NOOP | 0.2 s | distractor_count=8 |

### Full suite budget

- 28 slots × avg 1.5 s generation = 42 s generation overhead.
- Transport timeout: 240 s per turn.
- Worst-case single run: 28 × 240 s = 112 min.
- Realistic (most turns <60 s): 28 × 60 s = 28 min.
- Target: ≤45 min typical on Pi 5 (achieved with current model response times).

Budget-critical knobs:
1. CSP n: keep at 7 (n=8 → 40320 perms, ~15× slower).
2. Transport timeout: 240 s is hard ceiling; raise further only if calibration shows need.
3. ERR chain_len: 18 is max (validation loop is O(chain_len)).

---

## HOLE Register

| ID | Location | Decision |
|----|----------|----------|
| H1 | IC slot IDs | S27 (level 1), S28 (level 2) |
| H2 | IC decoy semantics | Decoy says "Ignore instruction k" but is a TRAP: correct answer executes ALL instructions. Checker rejects answers that skipped instruction k. |
| H3 | Capability max | 23 (21 + 2 from IC) |
| H4 | Acceptance threshold | ≤11/23 (~47.8%) |

---

## Accepted deviations

Recorded per the Accepted Deviations Policy (E13). Where the errata/contract could not be
implemented as written, the measured evidence for the change is given below.

### D1. CSP level-2 count is (14, 16), not (20, 24); `hop2` rewritten for speed

- **Section**: E2 / `src/psicotest/generators/csp_perm.py`
- **Deviation**: `LADDER[2]` is `{"n": 7, "count": (14, 16), "min_hop2": 5}` instead of the
  pinned `(20, 24)`; additionally `hop2()` was rewritten from the incremental prefix scan to a
  mathematically equivalent single pass over all permutations (violation-set equivalence:
  clue `i` is necessary iff some permutation violates exactly `i`; verified 0 mismatches
  against the original implementation on valid instances, ~16% faster per call).
- **Rationale**: the pinned `(20, 24) / min_hop2 5` is infeasible for this draw family: measured
  acceptance 0.0% (300/300 rejected, all `hop2_low`, across 3 independent RNG streams; a full
  enumeration of the distinct-kind condition space confirms dense clue sets make 5 individually
  necessary binary clues structurally unreachable). E2's own escape hatch does not help:
  at the sanctioned fallback `(18, 22) / 5` acceptance is 1.0% and the 20-seed probe shows
  worst item 44.4 s with 13/20 seeds over the 5 s budget (mean 8.4 s). `(16, 18) / 5` still
  breaches: worst 7.99 s, 3/20 seeds over 5 s (acceptance 3.0%). `(14, 16) / 5` is the highest
  clue count at `min_hop2 5` that passes E2's budget gate (acceptance 5.3%).
- **Impact**: E2's hardness knob `min_hop2 5` is kept; only the clue-count bump is reduced.
  Measured 20-seed probe at the shipped values: worst draw 2.522 s, mean 0.764 s, 0 exhausted
  seeds (budget: any draw ≤ 5 s — OK). The `hop2` rewrite returns identical values, so item
  distributions and determinism are unchanged.

### D2. CNT level-2 adds per-level `key_hi=26` and `single_letter` composition on top of the prescribed MIN_RATE=10

- **Section**: E5 / `src/psicotest/generators/count_cond.py`
- **Deviation**: `LADDER[2]` is `{"n_words": 130, "n_conds": 4, "min_rate": 10, "key_hi": 26,
  "single_letter": True}`. `key_hi` raises the level-2 key ceiling from the global
  `KEY_RANGE = (8, 20)` to 26 for level 2 only (global constant untouched); `single_letter`
  restricts level-2 condition composition to exactly one letter-op plus `len_eq`, `len_ge`,
  `vowels_eq` (the only composition whose conjunction rate can pass the rate gate), with
  uniform arguments.
- **Rationale**: with the prescribed MIN_RATE=10 alone, measured acceptance is 0.136%
  (200k-attempt simulation: 0.25% pass the rate gate, the key ceiling then cuts 45%), i.e.
  ~25.5% exhaustion probability per item, and `GeneratorExhausted` was observed in practice on
  the battery seed. The errata's satisfiability proof ("30 seeds with zero attempt
  exhaustion") is unachievable at 0.136%.
- **Impact**: measured acceptance rises to ~1.2%; satisfiability probe: 30/30 seeds, zero
  exhaustion, worst item 0.223 s, keys 8..26 (all other levels unchanged at 8..20). The test
  mirror gained `CNT_KEY_HI` to match.

### D3. ORDER_A extended with turns 31-32 for S27/S28

- **Section**: E11 / `src/psicotest/runner/battery.py`
- **Deviation**: `ORDER_A` gains `(31, "item", "S27")` and `(32, "item", "S28")`. In order B
  these two turns stay at positions 31/32 (they are not part of the `P` permutation).
- **Rationale**: the errata's battery.py edit list names only the `trigger_animal` version
  bump, but without turns the new IC slots would never be generated in a run, making the IC
  family dead weight and the capability max of 23 unattainable (the run's whole purpose).
- **Impact**: 32 turns per run; order-B slot permutation for turns 1..30 unchanged; twins,
  triggers and protocol slots untouched.

### D4. Timeout 240 s also applied to `run_battery` and CLI defaults

- **Section**: E11 / `src/psicotest/runner/driver.py`, `src/psicotest/cli.py`
- **Deviation**: `run_battery(timeout=...)` default 120 → 240 and CLI `--timeout` default
  120 → 240, in addition to the prescribed `client.py` default and `run_live.py`
  `HTTPTransport(timeout=240)`.
- **Rationale**: `run_live.py` calls `run_battery` without a `timeout` argument, so with the
  driver default left at 120 the prescribed 240 s ceiling would not reach the run entry
  points; contract global rule 2 sets 240 s as the transport hard ceiling.
- **Impact**: none on determinism; only default timing behaviour when no explicit timeout is
  passed.

### D5. `gen_instr_chain` registered with variants `("base",)` only

- **Section**: E1/E9 / `src/psicotest/generators/registry.py`
- **Deviation**: the IC generator declares no `relabel` variant (most capability generators
  carry `("base", "relabel")`).
- **Rationale**: relabeling applies to surface naming drawn from `surface_rng`; IC surfaces
  are built purely from the instance content (the token list and operations), so a relabel
  fork would be a no-op while doubling golden entries.
- **Impact**: IC contributes 6 golden keys (5 seeds × base + 1 animal case) instead of 11;
  golden count 132 → 138.

### D6. ST level 2 ships 150 operations over 9 boxes, not 120 over 4

- **Section**: E7 / `src/psicotest/generators/state_boxes.py`
- **Deviation**: the contract body prescribes level 2 at 120 operations over 4 boxes; the
  implementation uses 150 operations over 9 boxes.
- **Rationale**: state-tracking pressure scales with operation count and working-set width
  together; 4 boxes would make level 2 narrower than the 7-box level 1 and therefore
  easier in effect.
- **Impact**: ST level-2 items longer and wider than the contract specified.

### D7. AR level 2 scales the multiplication ladder to 12x8 digits instead of the mixed decimal chain

- **Section**: E6 / `src/psicotest/generators/mult_carry.py`
- **Deviation**: the contract body prescribes a mixed three-step decimal chain with negative
  intermediates for AR level 2; the implementation scales the pure multiplication ladder to
  12x8 digits.
- **Rationale**: the AR surface builder has a fixed single-product shape and decimal chains
  are already carried by the AR2 family; restructuring AR into a chain would duplicate AR2
  rather than add a distinct capability.
- **Impact**: AR stays a single-product family at higher digit counts.
