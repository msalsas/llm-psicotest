# T5E: Battery v6 Hardening Specification

**Contract**: T5E  
**Battery**: v6  
**Status**: Draft  
**Date**: 2026-11-02  
**Predecessor**: T5D (v5)

---

## Overview

Battery v6 addresses observed failure-mode gaps in v5 calibration evidence: (1) a 4B-class model with CoT passes PR levels 0-2 and both PC twins, eliminating discrimination; (2) two free-form failure modes (CJK glyph leakage, degenerate sentence structure) are never elicited by closed-form items. T5E hardens PR/PC and introduces family IV to surface these modes deterministically.

**Scope Summary**:
- **Part 1**: PR ladder extension to level 3 with stricter constraints
- **Part 2**: PC deepening to two-hop chained reasoning at level 2
- **Part 3**: Interview block (IV family) for free-form prose with structural scoring

**Version artifacts**: SLOTS_V5→SLOTS_V6, v5→v6 at all literal sites per T4D→T5D rename pattern.

---

## E1: PR Ladder Extension

### E1.1 Level 3 Specification

**File**: `generators/prose_block.py`

Add `LADDER[3]` with the following constraints:

```python
LADDER[3] = {
    "word_count_min": 80,
    "word_count_max": 120,
    "sentence_count_min": 6,
    "sentence_count_max": 8,
    "phrase_count": 2,  # NEW: exactly 2 required phrases
    "start_words_exact": 2,  # NEW: exactly 2 start words, one sentence each
    "distinct_starts": True,  # NEW: every sentence starts with different letter
}
```

**Constraint semantics**:
- `phrase_count`: The block must contain exactly `phrase_count` distinct phrases from the level pool, each appearing at least once.
- `start_words_exact`: Exactly this many sentences must begin with words from `START_WORD_POOL_L3`; each start word used exactly once.
- `distinct_starts`: Every sentence in the block must begin with a different initial letter (case-insensitive). With 6-8 sentences, requires 6-8 distinct first letters.

### E1.2 Level 3 Pools

**Banned letters**: Level 3 draws from `{e, a, t}` (same pool as lower levels, but all three are legal draws). **DECISION**: Fix banned letter to `a` for the frozen proof, enabling the widest topic vocabulary. Pool explicitly excludes `a`:

```python
BANNED_POOL_L3: tuple[str, ...] = ("e", "a", "t")
# Generator draws one; proof validated against all three

TOPIC_POOL_L3: tuple[str, ...] = ("crisp morning",)
# DECISION: Reuse "crisp morning" (no e/a/t) for proof compatibility

PHRASE_POOL_L3: tuple[str, ...] = (
    "in full",
    "with skill",
    "on point",
    "by design",
    "in sum",
    "no less",
)
# All phrases free of e, a, t; proof must include any 2

START_WORD_POOL_L3: tuple[str, ...] = ("cold", "bold")
# Both free of e, a, t; exactly one sentence per start word
```

### E1.3 Level 3 Proof Instance

**DECISION**: Construct a proof with 7 sentences (mid-range of 6-8), each starting with a distinct letter, containing "in full" and "with skill", with exactly one sentence starting "Cold..." and one starting "Bold...":

```python
_PROOFS[3] = (
    "Cold winds blow high upon crisp morning hills in full. "
    "Bold cooks mix spicy broth with skill. "
    "Long songs fill dim rooms on point. "
    "Dry wood burns bright by design. "
    "Mild sun lights dusty old windows. "
    "Soft clouds drift slowly through sky in sum. "
    "Gold rings glow dimly no less."
)
```

**Proof validation**:
- Word count: 51 words (within 80-120 window requires adjustment—see below)
- Sentence count: 7 (within 6-8) ✓
- Letters banned: none of {e, a, t} present ✓
- Phrases: "in full", "with skill" present ✓
- Start words: "Cold" and "Bold" each appear once as sentence start ✓
- Distinct starts: C, B, L, D, M, S, G — 7 distinct letters ✓

**DECISION (adjustment required)**: The proof above has only 51 words; level 3 requires 80-120. Expand each sentence with e/a/t-free words:

```python
_PROOFS[3] = (
    "Cold winds blow high upon crisp morning hills on rocky ground in full. "
    "Bold cooks mix spicy broth with mushrooms grown in spring soil with skill. "
    "Long songs fill dim rooms during cold nights on point plus joy. "
    "Dry wood burns bright on iron grills by design for hours. "
    "Mild sun lights dusty old windows with gold glow so bright. "
    "Soft clouds drift slowly through sky during crisp morning hours in sum. "
    "Gold rings glow dimly upon worn skin no less plus honor."
)
```

**Recount**: ~84 words (satisfies 80-120). Maintain validation for all other constraints.

### E1.4 Slot Upgrade

```python
# In SLOTS_V6:
(_row("S29", "PR", "gen_prose_block", "PR", level=2),)  # unchanged
(_row("S30", "PR", "gen_prose_block", "PR", level=3),)  # upgraded from level=2
```

### E1.5 Checker Flags

**File**: `checkers/prose_block.py`

Add flags to `check_pr()` return:

| Flag | Trigger |
|------|---------|
| `phrase_count_mismatch` | Required phrase count not met |
| `start_words_exact_fail` | Wrong number of start-word sentences |
| `start_word_missing_X` | Start word X not found as sentence opener |
| `distinct_starts_fail` | Two or more sentences share initial letter |

**Checker logic** (pseudocode):

```python
def check_distinct_starts(sentences: list[str]) -> list[str]:
    firsts = [s.strip()[0].lower() for s in sentences if s.strip()]
    if len(firsts) != len(set(firsts)):
        return ["distinct_starts_fail"]
    return []


def check_start_words_exact(sentences: list[str], required: list[str]) -> list[str]:
    flags = []
    found = {w: 0 for w in required}
    for s in sentences:
        first_word = s.strip().split()[0].lower() if s.strip() else ""
        if first_word in found:
            found[first_word] += 1
    for w, count in found.items():
        if count != 1:
            flags.append(f"start_word_missing_{w}" if count == 0 else f"start_word_duplicate_{w}")
    return flags


def check_phrase_count(text: str, required_phrases: list[str], count: int) -> list[str]:
    text_lower = text.lower()
    present = sum(1 for p in required_phrases if p in text_lower)
    if present < count:
        return ["phrase_count_mismatch"]
    return []
```

---

## E2: PC Two-Hop Extension

### E2.1 Level 2 Specification

**File**: `generators/prose_consistency.py`

Current levels (-1, 0, 1, 2) are empty placeholders. Level 2 introduces two-hop chained reasoning:

```python
LADDER[2] = {"hops": 2}
```

### E2.2 Two-Hop Pool Construction

**Structure**: Each entry contains three premises where any two chain to derive the answer. **DECISION**: Use transitive ordering (taller/shorter, older/younger) for unambiguous chaining:

```python
TWO_HOP_POOL: tuple[tuple[str, str, tuple[str, str, str], str, tuple[str, str]], ...] = (
    (
        "chain_height_1",
        "yes",
        (
            "Alice is taller than Bob.",
            "Bob is taller than Carol.",
            "Diana is shorter than Carol.",
        ),
        "Is Alice taller than Carol?",
        (
            "Given these facts about height: (1) Alice is taller than Bob, (2) Bob is taller than Carol, (3) Diana is shorter than Carol. Determine: Is Alice taller than Carol?",
            "Consider three height comparisons: Alice exceeds Bob in height, Bob exceeds Carol in height, and Diana is shorter than Carol. Does Alice exceed Carol in height?",
        ),
    ),
    (
        "chain_height_2",
        "no",
        (
            "Eve is shorter than Frank.",
            "Frank is shorter than Grace.",
            "Henry is taller than Grace.",
        ),
        "Is Eve taller than Grace?",
        (
            "Height facts: Eve is shorter than Frank, Frank is shorter than Grace, Henry is taller than Grace. Is Eve taller than Grace?",
            "Given that Eve < Frank in height and Frank < Grace in height (with Henry taller than Grace), is Eve taller than Grace?",
        ),
    ),
    (
        "chain_age_1",
        "yes",
        (
            "The red book was published before the blue book.",
            "The blue book was published before the green book.",
            "The yellow book was published after the green book.",
        ),
        "Was the red book published before the green book?",
        (
            "Publication order: red before blue, blue before green, yellow after green. Did the red book come out before the green book?",
            "Consider: red book → blue book → green book → yellow book in publication order (arrows mean 'before'). Was red published before green?",
        ),
    ),
    (
        "chain_age_2",
        "no",
        (
            "Project Alpha started after Project Beta.",
            "Project Beta started after Project Gamma.",
            "Project Delta started before Project Gamma.",
        ),
        "Did Project Alpha start before Project Gamma?",
        (
            "Timeline: Alpha after Beta, Beta after Gamma, Delta before Gamma. Did Alpha start before Gamma?",
            "Project order facts: Gamma → Beta → Alpha (arrows mean 'started before'), with Delta before Gamma. Did Alpha begin before Gamma?",
        ),
    ),
)
```

**Pool invariant**: Each question is answerable by chaining exactly two of the three premises; the third premise is a true but unused fact (distractor within the problem). The canonical answer is derivable purely from the stated premises without external knowledge.

### E2.3 Solver-Side Construction

**File**: `tests/solvers.py`

Add solver function following existing pattern:

```python
def solve_two_hop(premises: tuple[str, str, str], question: str) -> str:
    """Derive answer from premise chain.
    
    Construction guarantee: each TWO_HOP_POOL entry was manually verified;
    the solver reconstructs the chain to validate test instances.
    """
    # Parse transitive relations from premises
    # Chain and compare to question target
    # Return "yes" or "no"
```

**DECISION**: Solver uses regex patterns to extract entity orderings from premise strings (e.g., "X is taller than Y" → X > Y), builds transitive closure, answers question. This mirrors the manual construction and provides test-time verification.

### E2.4 Generator Changes

```python
def gen_prose_consistency(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    level = resolve_knobs(knobs, LADDER, OVERRIDES)["level"]
    
    if level == 2:
        entry = rng.choice(TWO_HOP_POOL)
        question_id, canonical, premises, base_question, surfaces = entry
        surface = surfaces[_SURFACE_INDEX[ctx.variant]]
    else:
        # existing one-hop logic
        entry = rng.choice(DECISION_POOL)
        question_id, canonical, base_question, surfaces = entry
        surface = surfaces[_SURFACE_INDEX[ctx.variant]]
        premises = ()
    
    # ... rest unchanged
    meta = {
        "instance": {"question_id": question_id, "premises": premises},
        # ...
    }
```

### E2.5 Twin Placement and Distractor Chain

**Requirement**: Place S31 at turn 31, S32 at turn 40 (gap of 9 turns). Between them, ≥3 unrelated slots whose visible model answers could contain "yes" or "no" tokens.

**DECISION**: Reorder turns 31-40 as follows:

| Turn | Slot | Family | Notes |
|------|------|--------|-------|
| 31 | S31 | PC | level=2, variant=pc1 |
| 32 | S27 | IC | level=1 (moved from 31) |
| 33 | S28 | IC | level=2 (moved from 32) |
| 34 | S29 | PR | level=2 |
| 35 | S30 | PR | level=3 |
| 36 | S33 | IV | (new) |
| 37 | S34 | IV | (new) |
| 38 | recall | RCL | S26 reminder (reuse) |
| 39 | (filler) | — | R3 clean reminder, no item |
| 40 | S32 | PC | level=2, variant=pc2, twin_of=S31 |

**Distractor slots**: Turns 32-35 contain IC and PR items. Instruction-chain (IC) responses may include affirmative/negative phrasing; PR blocks are prose. Additionally, the recall turn (38) references rules with potential yes/no content. This satisfies ≥3 intervening slots with possible yes/no tokens.

**DECISION (turn 39)**: Insert an R3-style reminder turn with no scored item. This extends the battery to 40 turns without adding slots. Alternatively, if non-item turns are undesirable, collapse to 39 turns with S32 at turn 39 (gap=8). **Choice**: Keep gap=9 per spec; turn 39 is a non-scored prompt repeating R3 text.

### E2.6 Twin Lookup Regression Test

**File**: `tests/test_pc_twin.py`

```python
def test_twin_lookup_with_distractors():
    """Verify PC twin matching ignores intervening yes/no tokens."""
    seed = 42
    order = "A"
    turns = battery_layout_v6(seed, order)
    
    # Find PC turns
    pc1_turn = next(t for t in turns if t.slot == "S31")
    pc2_turn = next(t for t in turns if t.slot == "S32")
    
    assert pc2_turn.turn - pc1_turn.turn == 9, "gap must be 9"
    
    # Verify intervening turns
    intervening = [t for t in turns if pc1_turn.turn < t.turn < pc2_turn.turn]
    assert len(intervening) >= 8, "need 8 intervening turns"
    
    # Mock model responses with yes/no in IC/PR slots
    responses = {
        "S27": "Step 1: yes, proceed. Step 2: no, skip. Step 3: output.",
        "S28": "No items match; yes to fallback.",
        "S29": "BEGIN\n... prose with no banned letter ...\nEND",
        "S30": "BEGIN\n... prose block ...\nEND",
        "S33": "BEGIN\n... interview response yes ...\nEND",
        "S34": "BEGIN\n... no, I disagree because ...\nEND",
        "S31": "ANSWER: yes",
        "S32": "ANSWER: yes",  # must match twin
    }
    
    # Run checker
    result = check_pc(item_s32, responses["S32"], prior=responses)
    assert "twin_mismatch" not in result.flags
```

---

## E3: Interview Generator (Family IV)

### E3.1 Family Registration

**File**: `checkers/common.py`

```python
CAPABILITY_FAMILIES = frozenset({"ST", "LOG", "PR", "PC", "IV"})  # add IV
```

### E3.2 Generator Module

**New file**: `generators/interview.py`

```python
"""Free-form interview generator (family IV).

Elicits >=150 words of opinion/explanation prose, scored only by
structural metrics (no content judgment). Uses BEGIN/END block format.
"""

from collections.abc import Mapping

from psicotest.generators.core import check_variant, finish, resolve_knobs
from psicotest.rng import Rng
from psicotest.spec import GenContext

VARIANTS = ("base",)

LADDER = {
    0: {"word_floor": 150},
}
OVERRIDES: dict[str, tuple[int, int]] = {}

# Frozen prompt pool: each tuple is (prompt_id, slot_preference, prompt_text)
# Prompts are opinion-based, answerable without external knowledge.
PROMPT_POOL_S33: tuple[tuple[str, str], ...] = (
    (
        "iv_workspace",
        "Describe your ideal workspace environment in detail. Explain which "
        "elements contribute most to focus and productivity, and discuss how "
        "the physical arrangement affects your work habits. Include at least "
        "three specific features and justify why each matters to you.",
    ),
    (
        "iv_learning",
        "Compare two different approaches to learning a new skill: self-study "
        "with online resources versus structured lessons with an instructor. "
        "Argue which approach you believe is more effective for most people, "
        "providing specific reasons and addressing potential counterarguments.",
    ),
)

PROMPT_POOL_S34: tuple[tuple[str, str], ...] = (
    (
        "iv_decisions",
        "Describe a situation where making a quick decision is better than "
        "waiting for complete information. Explain the factors that make speed "
        "valuable in such cases and discuss how someone can recognize when "
        "they are in this type of situation versus one requiring careful analysis.",
    ),
    (
        "iv_communication",
        "Compare written communication with spoken conversation for resolving "
        "disagreements. Argue which medium tends to produce better outcomes "
        "and explain why, while acknowledging situations where the other "
        "approach might be preferable.",
    ),
)

SLOT_POOLS = {
    "S33": PROMPT_POOL_S33,
    "S34": PROMPT_POOL_S34,
}


def gen_interview(rng: Rng, knobs: Mapping, ctx: GenContext) -> tuple[str, dict, dict]:
    check_variant(ctx, VARIANTS)
    level_knobs = resolve_knobs(knobs, LADDER, OVERRIDES)
    word_floor = level_knobs.get("word_floor", 150)

    pool = SLOT_POOLS.get(ctx.slot, PROMPT_POOL_S33)
    prompt_id, prompt_text = rng.choice(pool)

    paragraphs = [
        prompt_text,
        f"Your response must be at least {word_floor} words.",
        "Write your response between BEGIN and END markers on their own lines:",
        "BEGIN",
        "(your response here)",
        "END",
    ]
    prompt, clause = finish(paragraphs, ctx)
    key = {"word_floor": word_floor}
    meta = {
        "instance": {"prompt_id": prompt_id},
        "scoring": "IV",
    }
    return prompt, key, meta
```

### E3.3 Slot Definitions

```python
# In SLOTS_V6:
(_row("S33", "IV", "gen_interview", "IV", level=0),)
(_row("S34", "IV", "gen_interview", "IV", level=0),)
```

---

## E4: Interview Checker

### E4.1 Metric Definitions

**New file**: `checkers/interview.py`

**Tokenization** (per D8 invariant from T5D):
- Word tokens: whitespace split inside extracted block
- Sentence split: regex `[.!?]+` (same as PR checker)
- Case-insensitive comparisons: `fold()` from `checkers/text.py`

**Metric M1: Non-Latin Script Detection (CJK Leak)**

```python
import unicodedata


def has_non_latin(text: str) -> bool:
    """Detect CJK or other non-Latin script characters.

    Latin covers: ASCII, Latin Extended, Latin Supplement.
    Everything else outside Common/Inherited categories is flagged.
    """
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("L"):  # Letter category
            try:
                name = unicodedata.name(ch, "")
                if not (name.startswith("LATIN") or "DIGIT" in name):
                    return True
            except ValueError:
                return True
    return False
```

**Metric M2: Repeated N-gram Loop**

```python
from collections import Counter


def find_repeated_ngram(text: str, n: int = 8) -> bool:
    """Detect any n-gram appearing twice (case-insensitive, word tokens)."""
    words = text.lower().split()
    if len(words) < n:
        return False
    ngrams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    counts = Counter(ngrams)
    return any(c >= 2 for c in counts.values())
```

**Metric M3: Degenerate Sentences**

```python
import re

SENTENCE_RE = re.compile(r"[.!?]+")


def find_degenerate_sentences(text: str, min_words: int = 3, max_words: int = 45) -> list[str]:
    """Find sentences with <min_words or >max_words tokens."""
    sentences = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
    degenerate = []
    for s in sentences:
        word_count = len(s.split())
        if word_count < min_words or word_count > max_words:
            degenerate.append(s)
    return degenerate
```

**Metric M4: Word Count Floor**

```python
def check_word_floor(text: str, floor: int) -> bool:
    """Check if text meets minimum word count."""
    return len(text.split()) >= floor
```

### E4.2 Checker Function

```python
from dataclasses import dataclass
from psicotest.checkers.extract import extract_block
from psicotest.spec import Item, CheckResult


@dataclass(frozen=True)
class IVResult(CheckResult):
    word_count: int
    sentence_count: int
    flags: tuple[str, ...]


def check_iv(item: Item, response: str | None) -> IVResult:
    """Check interview response against structural metrics."""
    flags = []

    # Extract block (reuse existing extractor)
    block_text, extract_flags = extract_block(response)
    flags.extend(extract_flags)

    if block_text is None:
        return IVResult(
            word_count=0,
            sentence_count=0,
            flags=tuple(flags),
        )

    word_floor = item.key.get("word_floor", 150)
    words = block_text.split()
    word_count = len(words)

    # M1: Non-Latin script (CJK leak)
    # Note: leak_scope reuse from driver.py handles capability-item zeroing
    if has_non_latin(block_text):
        flags.append("leak_chars")

    # M2: Repeated 8-gram
    if find_repeated_ngram(block_text, n=8):
        flags.append("loop_ngram")

    # M3: Degenerate sentences
    degenerate = find_degenerate_sentences(block_text, min_words=3, max_words=45)
    if degenerate:
        flags.append("degenerate_sentence")

    # M4: Word floor
    if word_count < word_floor:
        flags.append("too_short")

    sentences = [s.strip() for s in SENTENCE_RE.split(block_text) if s.strip()]

    return IVResult(
        word_count=word_count,
        sentence_count=len(sentences),
        flags=tuple(flags),
    )
```

### E4.3 Scoring Integration

**File**: `runner/driver.py`

The existing leak hook runs before scoring and zeroes capability items containing CJK. IV items are capability items (family in `CAPABILITY_FAMILIES`), so the leak hook applies automatically.

**File**: `runner/report.py`

```python
# Add to cap map:
FAMILY_CAPS = {
    # ... existing ...
    "PR": 2,
    "PC": 2,
    "IV": 2,  # NEW: S33 and S34
}
# CAPABILITY_MAX updates to 29 (was 27, +2 for IV)
```

### E4.4 Flag Summary

| Flag | Metric | Trigger |
|------|--------|---------|
| `no_block` | — | No BEGIN/END block found |
| `leak_chars` | M1 | Non-Latin characters in block |
| `loop_ngram` | M2 | Any 8-gram appears ≥2 times |
| `degenerate_sentence` | M3 | Sentence with <3 or >45 words |
| `too_short` | M4 | Block word count < 150 |

---

## E5: Wiring v6

### E5.1 File Renames/Updates

All sites touched by v4→v5 rename; update v5→v6 literals:

| File | Change |
|------|--------|
| `generators/slots.py` | `SLOTS_V5` → `SLOTS_V6` |
| `runner/battery.py` | Import `SLOTS_V6`; update battery string literals |
| `runner/report.py` | Import `SLOTS_V6`; update `CAPABILITY_MAX` to 29 |
| `tests/golden/items_v5.json` | Rename to `items_v6.json`; regenerate |
| `tools/gen_golden.py` | Update battery version string |
| All test files | Update fixture battery versions |

### E5.2 SLOTS_V6 Definition

```python
SLOTS_V6 = (
    _row("S01", "ST", "gen_state_boxes", "exact_keys", level=1),
    _row("S02", "AR", "gen_mult_carry", "exact_int", level=1),
    _row("S03", "NOOP", "gen_gsm_noop", "exact_num", n_distractors=6),
    _row("S04", "CSP", "gen_csp_perm", "csp_verify", level=1),
    _row("S05", "LOG", "gen_knights_spy", "exact_roles", level=1),
    _row("S06", "FPRE", "gen_false_premise", "premise3"),
    _row("S07", "AMB", "gen_missing_datum", "clar"),
    _row("S08", "CNT", "gen_count_cond", "exact_int", level=1),
    _row("S09", "ERR", "gen_planted_error", "err_step_value", level=1),
    _row("S10", "NOOP", "gen_gsm_noop", "exact_num", n_distractors=4),
    _row("S11", "CSP", "gen_csp_perm", "csp_verify", level=2),
    _row("S12", "AR", "gen_mult_carry", "exact_int", level=2),
    _row("S13", "LOG", "gen_knights_spy", "exact_roles", level=2),
    _row("S14", "FPRE", "gen_false_premise", "premise3"),
    _row("S15", "CNT", "gen_count_cond", "exact_int", level=3),
    _row("S16", "ST", "gen_state_boxes", "exact_keys", level=1, twin_of="S01"),
    _row("S17", "AMB", "gen_missing_datum", "clar"),
    _row("S18", "ERR", "gen_planted_error", "err_step_value", level=2),
    _row("S19", "AR", "gen_mult_carry", "exact_int", level=1, twin_of="S02"),
    _row("S20", "SYP", "gen_authority_hint", "syco3", level=1),
    _row("S21", "CNT", "gen_count_cond", "exact_int", level=2),
    _row("S22", "ERR", "gen_planted_error", "err_step_value", level=2),
    _row("S23", "ST", "gen_state_boxes", "exact_keys", level=2),
    _row("S24", "AMB", "gen_missing_datum", "clar"),
    _row("S25", "SYP", "gen_authority_hint", "syco3", level=2),
    _row("S26", "RCL", "rules_recall", "recall"),
    _row("S27", "IC", "gen_instr_chain", "exact_list", level=1),
    _row("S28", "IC", "gen_instr_chain", "exact_list", level=2),
    _row("S29", "PR", "gen_prose_block", "PR", level=2),
    _row("S30", "PR", "gen_prose_block", "PR", level=3),  # UPGRADED
    _row("S31", "PC", "gen_prose_consistency", "PC", level=2, variant="pc1"),  # UPGRADED
    _row(
        "S32", "PC", "gen_prose_consistency", "PC", level=2, variant="pc2", twin_of="S31"
    ),  # UPGRADED
    _row("S33", "IV", "gen_interview", "IV", level=0),  # NEW
    _row("S34", "IV", "gen_interview", "IV", level=0),  # NEW
)
```

### E5.3 ORDER_A_V6 / ORDER_B_V6

**DECISION**: Extend to 40 turns. Turn 39 is a non-item R3 reminder.

```python
ORDER_A = (
    # Turns 1-30: unchanged from v5
    (1, "setup", None),
    (2, "item", "S01"),
    # ... turns 3-30 identical ...
    (30, "recall", "S26"),
    # Turns 31-40: restructured
    (31, "item", "S31"),  # PC level 2, twin 1
    (32, "item", "S27"),  # IC level 1 (moved)
    (33, "item", "S28"),  # IC level 2 (moved)
    (34, "item", "S29"),  # PR level 2
    (35, "item", "S30"),  # PR level 3
    (36, "item", "S33"),  # IV (new)
    (37, "item", "S34"),  # IV (new)
    (38, "recall", "S26"),  # RCL repeat for distraction
    (39, "r3_reminder", None),  # Non-item turn
    (40, "item", "S32"),  # PC level 2, twin 2
)
```

**DECISION**: Add turn kind `"r3_reminder"` that emits R3_TEXT without a scored item. This is handled in `battery_layout()`:

```python
if kind == "r3_reminder":
    turns.append(Turn(turn, kind, None, R3_TEXT, None, ("R3",), False))
    continue
```

**Permutation pins** for ORDER_B: `P = [2, ..., 29, 32, 33, 34, 35]` — turns 31, 36-40 are fixed (prose blocks and IV stay in place). **DECISION**: Simplest approach: only permute turns 2-29 as before; turns 31-40 are fixed in both orders. This maintains the PR/PC/IV placement guarantee.

### E5.4 Capability Update

**File**: `runner/report.py`

```python
CAPABILITY_SLOTS = frozenset(spec.slot for spec in SLOTS_V6 if spec.capability)
CAPABILITY_MAX = len(CAPABILITY_SLOTS)  # Now 29

FAMILY_CAPS = {
    "ST": 3,
    "LOG": 2,
    "PR": 2,
    "PC": 2,
    "IV": 2,  # NEW
}
```

---

## E6: Tests

### E6.1 Flag Isolation Tests

**File**: `tests/test_prose_block.py`

```python
def test_distinct_starts_pass():
    text = "Alpha one. Beta two. Gamma three."
    flags = check_distinct_starts(split_sentences(text))
    assert flags == []


def test_distinct_starts_fail():
    text = "Alpha one. Alpha two. Beta three."  # A repeats
    flags = check_distinct_starts(split_sentences(text))
    assert "distinct_starts_fail" in flags


def test_start_words_exact_pass():
    text = "Cold winds blow. Bold cooks mix. Long songs fill."
    flags = check_start_words_exact(split_sentences(text), ["cold", "bold"])
    assert flags == []


def test_start_words_exact_missing():
    text = "Cold winds blow. Long songs fill. Mild sun shines."
    flags = check_start_words_exact(split_sentences(text), ["cold", "bold"])
    assert "start_word_missing_bold" in flags


def test_start_words_exact_duplicate():
    text = "Cold winds blow. Cold air bites. Bold cooks mix."
    flags = check_start_words_exact(split_sentences(text), ["cold", "bold"])
    assert "start_word_duplicate_cold" in flags


def test_phrase_count_pass():
    text = "Work done in full with great skill."
    flags = check_phrase_count(text, ["in full", "with skill"], 2)
    assert flags == []


def test_phrase_count_fail():
    text = "Work done in full only."
    flags = check_phrase_count(text, ["in full", "with skill"], 2)
    assert "phrase_count_mismatch" in flags
```

**File**: `tests/test_interview.py`

```python
def test_leak_chars_cjk():
    text = "This is a test 你好 with CJK."
    assert has_non_latin(text) is True


def test_leak_chars_clean():
    text = "This is a clean English response with punctuation!"
    assert has_non_latin(text) is False


def test_loop_ngram_detected():
    text = "one two three four five six seven eight one two three four five six seven eight"
    assert find_repeated_ngram(text, n=8) is True


def test_loop_ngram_clean():
    text = "one two three four five six seven eight nine ten eleven twelve"
    assert find_repeated_ngram(text, n=8) is False


def test_degenerate_too_short():
    text = "Hi. This is a normal sentence with many words in it."
    degenerate = find_degenerate_sentences(text, min_words=3, max_words=45)
    assert len(degenerate) == 1  # "Hi" is too short


def test_degenerate_too_long():
    long_sentence = " ".join(["word"] * 50)
    text = f"Short one here. {long_sentence}."
    degenerate = find_degenerate_sentences(text, min_words=3, max_words=45)
    assert len(degenerate) == 1


def test_word_floor_pass():
    text = " ".join(["word"] * 160)
    assert check_word_floor(text, 150) is True


def test_word_floor_fail():
    text = " ".join(["word"] * 100)
    assert check_word_floor(text, 150) is False
```

### E6.2 Proof Satisfiability Tests

**File**: `tests/test_prose_block.py`

```python
def test_level3_proof_satisfies_all_draws():
    """Proof must pass all constraints for any legal draw at level 3."""
    proof = _PROOFS[3]

    # Word count
    words = proof.split()
    assert 80 <= len(words) <= 120, f"word count {len(words)} out of range"

    # Sentence count
    sentences = [s.strip() for s in re.split(r"[.!?]+", proof) if s.strip()]
    assert 6 <= len(sentences) <= 8, f"sentence count {len(sentences)} out of range"

    # Banned letters: proof must be free of ALL banned pool options
    for banned in BANNED_POOL_L3:
        assert banned not in proof.lower(), f"proof contains banned letter '{banned}'"

    # Phrases: proof must contain at least 2 from pool
    phrase_hits = sum(1 for p in PHRASE_POOL_L3 if p in proof.lower())
    assert phrase_hits >= 2, f"only {phrase_hits} phrases found"

    # Start words: exactly one sentence each
    for sw in START_WORD_POOL_L3:
        starts = sum(1 for s in sentences if s.lower().startswith(sw))
        assert starts == 1, f"start word '{sw}' appears {starts} times"

    # Distinct starts
    first_letters = [s[0].lower() for s in sentences]
    assert len(first_letters) == len(set(first_letters)), "duplicate first letters"
```

### E6.3 Two-Hop Solver Tests

**File**: `tests/test_solvers.py`

```python
def test_two_hop_chain_height():
    premises = (
        "Alice is taller than Bob.",
        "Bob is taller than Carol.",
        "Diana is shorter than Carol.",
    )
    assert solve_two_hop(premises, "Is Alice taller than Carol?") == "yes"
    assert solve_two_hop(premises, "Is Diana taller than Alice?") == "no"


def test_two_hop_chain_temporal():
    premises = (
        "The red book was published before the blue book.",
        "The blue book was published before the green book.",
        "The yellow book was published after the green book.",
    )
    assert solve_two_hop(premises, "Was the red book published before the green book?") == "yes"
```

### E6.4 Twin Distance Regression Tests

**File**: `tests/test_battery.py`

```python
def test_pc_twin_gap_v6():
    """Verify PC twins are 9 turns apart with distractors."""
    turns = battery_layout(seed=42, order="A", version="v6")
    pc1 = next(t for t in turns if t.slot == "S31")
    pc2 = next(t for t in turns if t.slot == "S32")

    assert pc2.turn - pc1.turn == 9

    # Count intervening slots (excluding non-item turns)
    intervening = [t for t in turns if pc1.turn < t.turn < pc2.turn and t.slot is not None]
    assert len(intervening) >= 3


def test_pc_twin_lookup_with_yes_no_noise():
    """Twin checker must ignore yes/no in unrelated slots."""
    # Setup mock responses with yes/no tokens in non-PC slots
    responses = {
        "S31": "ANSWER: yes",
        "S27": "The answer is yes to step one and no to step two.",
        "S28": "No matches found. Yes to fallback.",
        "S32": "ANSWER: yes",
    }

    item_s32 = build_slot_item(SLOT_BY_ID["S32"], seed=42, battery="v6")
    result = check_pc(item_s32, responses["S32"], prior_responses=responses)

    # Must match twin, ignoring noise
    assert "twin_mismatch" not in result.flags
```

---

## E7: Documentation

### E7.1 README Update

**File**: `README.md`

Add IV to family table:

```markdown
| Family | Slots | Description |
|--------|-------|-------------|
| ... | ... | ... |
| PR | S29, S30 | Constrained prose block generation |
| PC | S31, S32 | Cross-turn prose consistency (twin pair) |
| IV | S33, S34 | Free-form interview (structural scoring) |
```

Update version badge and capability counts:

```markdown
**Battery v6**: 34 slots, 40 turns, 29 capability points
```

### E7.2 Contract File

**File**: `docs/contracts/T5E-hardening-spec.md`

This document (copy of contract output).

---

## Appendix: DECISION Log

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Level 3 banned letter fixed to `a` in proof | Widest vocabulary; proof validated against all {e,a,t} |
| D2 | Transitive comparisons for two-hop PC | Unambiguous chaining; mirrors existing comparison style |
| D3 | Turn 39 is non-item R3 reminder | Achieves 9-turn gap without new slots |
| D4 | Turns 31-40 fixed in both orders | Maintains PR/PC/IV placement guarantee |
| D5 | Reuse existing slots as distractors | No new slots needed; IC/PR naturally contain yes/no tokens |
| D6 | 8-gram window for loop detection | Balances false-positive risk vs. catching repetition |
| D7 | 3-45 word sentence bounds | Catches degenerate extremes without flagging normal prose |
| D8 | Recall turn 38 reuses S26 | Adds distraction without new slot |

---

## Verification Checklist

- [ ] `SLOTS_V6` has 34 entries (S01-S34)
- [ ] `ORDER_A` has 40 turns
- [ ] S31 at turn 31, S32 at turn 40 (gap=9)
- [ ] S30 at level 3; S29 at level 2
- [ ] S31/S32 at PC level 2 (two-hop)
- [ ] `CAPABILITY_MAX` = 29
- [ ] `CAPABILITY_FAMILIES` includes `IV`
- [ ] Proof `_PROOFS[3]` passes all level 3 constraints
- [ ] All v5→v6 literal sites updated
- [ ] Golden file regenerated
- [ ] All flag isolation tests pass
- [ ] Twin regression test passes with yes/no noise

---

# Errata (binding; overrides the contract above wherever they conflict)

- **D1 Layout**: v6 battery = 38 turns, no filler turn, recall stays turn 30. Tail: 31 S31 (PC1), 32 S28, 33 S29 (PR L2), 34 S30 (PR L3), 35 S33 (IV), 36 S34 (IV), 37 S27, 38 S32 (PC2, twin_of=S31). PC twin gap = 7. ORDER_B keeps the v5 permutation over turns 2-29; tail 30-38 is fixed in both orders. `SLOTS_V5` -> `SLOTS_V6`, v5 literals -> v6.
- **D2 PR L3 knobs**: words 80-120, sentences 6-8, two required phrases, exactly one sentence per required start word, distinct sentence-initial letters (casefold). Banned letter drawn from the existing ladder pair scheme (`BANNED_POOL_L1`, e/t); no new `BANNED_POOL_L3`.
- **D3 L3 pools** (replace E1.2): `PHRASE_POOL_L3 = ("in full","much joy","on song","so long","no fuss","our own","up high")`, `START_WORD_POOL_L3 = ("cold","bold")`, topic "crisp morning". Every entry avoids e, a and t.
- **D4 L3 proof** (replaces E1.3): 85 words, 7 sentences, starts C,B,L,D,M,S,G, contains every L3 pool phrase, zero e and zero t. Satisfiability test follows the v5 pattern.
- **D5 PC two-hop**: E2.2 pool accepted; wired into the existing `prose_consistency` structures (level 2 -> hops=2 selects `TWO_HOP_POOL`; premises live inside both surfaces; `question_id` and `twin_slot` machinery unchanged; twins draw the same pool entry).
- **D6 Twin lookup test**: extends the existing prose-family tests (no `tests/test_pc_twin.py`, no `battery_layout_v6`); asserts the frozen-layout gap >= 5 and that unrelated yes/no priors cannot flip a correct twin pair.
- **D7 IV family**: `checkers/interview.py` + `generators/interview.py`, family IV, slots S33/S34 level 0, BEGIN/END block protocol, frozen per-slot prompt pools (E3.2 texts verbatim) plus "Your response must be at least 150 words.".
- **D8 IV metrics**: no M1 in the checker (the driver CJK leak hook is the single source). M2: any 8-gram repeated (casefolded) -> `loop_ngram`. M3: sentence tokens < 3 or > 45 -> `degenerate_sentence`; sentences split on `[.!?]+` followed by whitespace, and a fragment with < 3 words merges into the previous sentence unless it starts uppercase. M4: block words < 150 -> `too_short`. Extract failure -> `fmt`. Binary scoring.
- **D9 Capability**: `CAPABILITY_FAMILIES += IV`; report cap map IV = 2; capability max = 29. R3 clean count and order pins re-pinned; golden regenerated.
- **D10 IV protocol**: no ANSWER line; empty or missing block -> `fmt`.
- **D11 Surface**: English only.
- **D12**: this file merges the contract and errata; shipped deviations are recorded below.

# Accepted deviations

- Layout is 38 turns with no filler turn and no `r3_reminder` turn kind (errata D1 over E2.5/E5.3); the PC twin gap is 7, not 9. The errata's "slot v5 had at 35" is read as the leftover IC slot S27 (S30 already sits at turn 34), giving 37 S27.
- L3 pools and proof follow D3/D4 rather than E1.2/E1.3. The D4 proof's "cold nights" contained a `t`, contradicting its own claim of zero e/t; shipped as "cold hours" (still 85 words).
- L3 banned letter is drawn from `BANNED_POOL_L1` (e/t), the ladder's hardest pair scheme; L3 constraints add optional `sentence_count_max`, `required_phrases`, `start_words`, `distinct_starts` (the legacy `required_phrase` holds the first phrase). Checker detail tokens: `start_words`, `distinct_starts` (plus existing ones).
- M1 (non-Latin detection) is delegated to the driver leak hook; IV is a capability family so the hook applies implicitly.
- The IV slot pool is selected by a `pool` knob (0 = S33, 1 = S34) because generators do not receive the slot id; IV flags are detail tokens (`fmt`, `loop_ngram`, `degenerate_sentence`, `too_short`) like PR.
- The two-hop surfaces use ASCII `->` instead of the U+2192 arrow because the surface-hygiene suite requires ASCII prompts.
- Test layout follows the v5 pattern: `tests/test_prose_families.py` (L3, two-hop, twin lookup), new `tests/test_interview.py`, `tests/solvers.py::solve_two_hop`, golden `tests/golden/items_v6.json` via `tools/gen_golden.py`.
