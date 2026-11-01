# T5D Implementation Contract

## Scope

T5D extends the psicotest battery from v4 to v5 with two new item families designed as discriminators for constrained prose generation. These families test capabilities where small LLMs empirically fail: structural constraint adherence and cross-turn consistency.

**New artifacts:**
- `src/psicotest/generators/prose_block.py` — family PR, key `gen_prose_block`
- `src/psicotest/generators/prose_consistency.py` — family PC, key `gen_prose_consistency`
- `src/psicotest/checkers/prose_block.py` — checker key `PR`
- `src/psicotest/checkers/prose_consistency.py` — checker key `PC`
- `src/psicotest/extract.py` additions — block extractor for BEGIN/END protocol
- Wiring updates: `slots.py`, `registry.py` (generators + checkers), `runner/battery.py`, `runner/driver.py` (PC cross-turn extension)

**Unchanged:** All existing generators, checkers, extraction logic for ANSWER: protocol, turn numbering 1–32, SLOTS_V4 content (renamed but frozen), ORDER_A/ORDER_B existing entries.

---

## New Modules

### 1. `src/psicotest/generators/prose_block.py`

```python
"""Constrained prose block generator (family PR)."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psicotest.rng import Rng

# Static topic pool — ASCII only, >= 12 entries
TOPIC_POOL: tuple[str, ...] = (
    "morning routines",
    "city parks",
    "old books",
    "train stations",
    "mountain trails",
    "local bakeries",
    "night markets",
    "small gardens",
    "harbor towns",
    "forest paths",
    "brick buildings",
    "country roads",
)

# Required-phrase pool per level (drawn at generation time)
PHRASE_POOL_L0: tuple[str, ...] = (
    "in fact",
    "on occasion",
    "for now",
    "at last",
    "by chance",
    "with care",
)
PHRASE_POOL_L1: tuple[str, ...] = (
    "without doubt",
    "in contrast",
    "by design",
    "on balance",
)
PHRASE_POOL_L2: tuple[str, ...] = (
    "in summary",
    "by all accounts",
    "on reflection",
)

# Same-start-word pool (levels 1, 2)
START_WORD_POOL_L1: tuple[str, ...] = (
    "This",
    "Such",
    "Many",
    "Most",
)
START_WORD_POOL_L2: tuple[str, ...] = (
    "Curiously",
    "Notably",
    "Surprisingly",
)

# Banned letter pools per level
BANNED_POOL_L0: tuple[str, ...] = ("e", "a")
BANNED_POOL_L1: tuple[str, ...] = ("e", "t")
BANNED_POOL_L2: tuple[str, ...] = ("e",)  # fixed


def _generate_level_0(rng: Rng) -> dict:
    """Level 0: words 50–80, sentences exactly 5, banned {e,a}, required phrase 2-word."""
    topic = rng.choice(TOPIC_POOL)
    banned = rng.choice(BANNED_POOL_L0)
    phrase = rng.choice(PHRASE_POOL_L0)
    return {
        "topic": topic,
        "word_count_min": 50,
        "word_count_max": 80,
        "sentence_count": 5,
        "banned_letter": banned,
        "required_phrase": phrase,
        "same_start_word": None,
        "topic_sentence": False,
    }


def _generate_level_1(rng: Rng) -> dict:
    """Level 1: words 40–60 exact, sentences exactly 6, banned {e,t}, required phrase, same-start-word."""
    topic = rng.choice(TOPIC_POOL)
    banned = rng.choice(BANNED_POOL_L1)
    phrase = rng.choice(PHRASE_POOL_L1)
    start_word = rng.choice(START_WORD_POOL_L1)
    return {
        "topic": topic,
        "word_count_min": 40,
        "word_count_max": 60,
        "sentence_count": 6,
        "banned_letter": banned,
        "required_phrase": phrase,
        "same_start_word": start_word,
        "topic_sentence": False,
    }


def _generate_level_2(rng: Rng) -> dict:
    """Level 2: words 30–45 exact, sentences exactly 5, banned e, same-start-word (harder), required phrase, Topic sentence."""
    topic = rng.choice(TOPIC_POOL)
    phrase = rng.choice(PHRASE_POOL_L2)
    start_word = rng.choice(START_WORD_POOL_L2)
    return {
        "topic": topic,
        "word_count_min": 30,
        "word_count_max": 45,
        "sentence_count": 5,
        "banned_letter": "e",
        "required_phrase": phrase,
        "same_start_word": start_word,
        "topic_sentence": True,  # first sentence: "Topic: {topic}..."
    }


LADDER: dict[int, dict] = {
    -1: {},  # unused for slots
    0: {"generator": _generate_level_0},
    1: {"generator": _generate_level_1},
    2: {"generator": _generate_level_2},
}


def generate(rng: Rng, level: int) -> dict:
    """
    Generate a prose_block item.

    Returns dict with keys:
        prompt: str — the instruction text shown to model
        constraints: dict — all constraint parameters (for checker)
        answer_protocol: str — always "block"
    """
    gen_fn = LADDER[level]["generator"]
    constraints = gen_fn(rng)

    # Build prompt
    lines = [
        f"Write a short paragraph about {constraints['topic']}.",
        "",
        "Your response MUST satisfy ALL of the following constraints:",
        f"- Word count: between {constraints['word_count_min']} and {constraints['word_count_max']} words (inclusive)",
        f"- Exactly {constraints['sentence_count']} sentences (delimited by . ! or ?)",
        f"- Do NOT use the letter '{constraints['banned_letter']}' anywhere (case-insensitive)",
        f'- Include the phrase "{constraints["required_phrase"]}" verbatim',
    ]

    if constraints["same_start_word"]:
        lines.append(
            f'- Every sentence must start with the word "{constraints["same_start_word"]}"'
        )

    if constraints["topic_sentence"]:
        lines.append(
            f'- Your first sentence must begin with exactly "Topic: {constraints["topic"]}"'
        )

    lines.extend(
        [
            "",
            "Format your answer as a single block:",
            "BEGIN",
            "<your paragraph here>",
            "END",
            "",
            "Do not include any text outside the BEGIN/END markers except optional brief preamble.",
        ]
    )

    return {
        "prompt": "\n".join(lines),
        "constraints": constraints,
        "answer_protocol": "block",
    }
```

**Data shape of `item["constraints"]`:**
```python
{
    "topic": str,  # e.g. "morning routines"
    "word_count_min": int,  # inclusive lower bound
    "word_count_max": int,  # inclusive upper bound
    "sentence_count": int,  # exact count required
    "banned_letter": str,  # single lowercase ASCII letter
    "required_phrase": str,  # must appear verbatim (case-insensitive match)
    "same_start_word": str | None,  # if set, every sentence starts with this
    "topic_sentence": bool,  # if True, first sentence must start "Topic: {topic}"
}
```

---

### 2. `src/psicotest/generators/prose_consistency.py`

```python
"""Cross-turn consistency generator (family PC)."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psicotest.rng import Rng

# Frozen decision question pool: (question_id, canonical_answer, base_question, variant_surfaces)
# canonical_answer is "yes" or "no"
# variant_surfaces is tuple of paraphrases; index 0 = variant-1, index 1 = variant-2
DECISION_POOL: tuple[tuple[str, str, str, tuple[str, str]], ...] = (
    (
        "cmp_47_23",
        "yes",
        "Is 47 greater than 23?",
        (
            "Consider the numbers 47 and 23. Is the first number larger than the second?",
            "Compare forty-seven to twenty-three. Does the former exceed the latter?",
        ),
    ),
    (
        "cmp_15_89",
        "no",
        "Is 15 greater than 89?",
        (
            "Think about 15 and 89. Is 15 the bigger number?",
            "Between fifteen and eighty-nine, is fifteen larger?",
        ),
    ),
    (
        "order_mon_wed",
        "yes",
        "Does Monday come before Wednesday in a standard week?",
        (
            "In the days of the week, is Monday earlier than Wednesday?",
            "Considering a typical week, does Monday precede Wednesday?",
        ),
    ),
    (
        "order_sat_tue",
        "no",
        "Does Saturday come before Tuesday in a standard week?",
        (
            "In the weekly order, is Saturday earlier than Tuesday?",
            "Does Saturday precede Tuesday in a normal week?",
        ),
    ),
    (
        "cmp_100_99",
        "yes",
        "Is 100 greater than 99?",
        (
            "Compare one hundred to ninety-nine. Is the first larger?",
            "Between 100 and 99, is 100 the greater value?",
        ),
    ),
    (
        "cmp_50_50",
        "no",
        "Is 50 greater than 50?",
        (
            "Are fifty and fifty such that the first exceeds the second?",
            "Compare 50 to itself. Is it greater than itself?",
        ),
    ),
    (
        "order_jan_mar",
        "yes",
        "Does January come before March in the calendar year?",
        (
            "In the standard calendar, is January earlier than March?",
            "Considering months, does January precede March?",
        ),
    ),
    (
        "order_dec_feb",
        "no",
        "Does December come before February in the calendar year?",
        (
            "In the yearly order, is December earlier than February?",
            "Does December precede February in a calendar year?",
        ),
    ),
)


def generate(rng: Rng, level: int, variant: int) -> dict:
    """
    Generate a prose_consistency item.

    Args:
        rng: deterministic RNG (MUST use same derive path for twins)
        level: ladder level (0, 1, 2) — currently unused, reserved
        variant: 1 or 2 — which surface paraphrase to use

    Returns dict with keys:
        prompt: str
        question_id: str — stable ID for twin matching
        canonical_answer: str — "yes" or "no"
        variant: int — 1 or 2
        answer_protocol: str — always "line" (uses ANSWER: extraction)
    """
    if variant not in (1, 2):
        raise ValueError(f"variant must be 1 or 2, got {variant}")

    q = rng.choice(DECISION_POOL)
    question_id, canonical_answer, _base, surfaces = q
    surface = surfaces[variant - 1]

    prompt_lines = [
        surface,
        "",
        "Answer with exactly one word: yes or no.",
        "",
        "ANSWER: <your answer>",
    ]

    return {
        "prompt": "\n".join(prompt_lines),
        "question_id": question_id,
        "canonical_answer": canonical_answer,
        "variant": variant,
        "answer_protocol": "line",
    }


# LADDER not used in the typical sense; level is reserved.
# The generator entry point differs: generate(rng, level, variant).
LADDER: dict[int, dict] = {
    -1: {},
    0: {"generator": generate},
    1: {"generator": generate},
    2: {"generator": generate},
}
```

**Note:** The `generate` signature differs from standard generators by adding `variant` parameter. The slot wiring must pass `variant=1` or `variant=2` explicitly. See Wiring section.

**Twin mechanism:** Both S31 and S32 MUST use the same RNG derive path (e.g., `rng.derive("PC")`) so they draw the identical `question_id`. The `variant` parameter selects which surface paraphrase.

---

### 3. `src/psicotest/extract.py` additions

Add to existing module:

```python
import re

# Existing: RESP_LINE_RE for "ANSWER: <value>" extraction
# (leave unchanged)

# New: Block extraction for BEGIN/END protocol
BLOCK_RE: re.Pattern[str] = re.compile(
    r"^BEGIN\s*\n(.*?)\n\s*END\s*$",
    re.MULTILINE | re.DOTALL,
)


def extract_block(content: str) -> tuple[str | None, list[str]]:
    """
    Extract prose content from BEGIN/END block.

    Args:
        content: full model response

    Returns:
        (extracted_text, flags)
        - extracted_text is None if no valid block found
        - flags may contain "no_block" if extraction failed
    """
    match = BLOCK_RE.search(content)
    if match is None:
        return None, ["no_block"]
    return match.group(1).strip(), []
```

**HOLE:** Verify `BLOCK_RE` handles edge cases: BEGIN with trailing whitespace, END with leading whitespace, nested BEGIN (takes first match). Write unit tests for these during implementation.

---

## Checkers Spec

### 1. `src/psicotest/checkers/prose_block.py`

```python
"""Checker for PR (prose_block) items."""

from __future__ import annotations
import re
from typing import TYPE_CHECKING

from psicotest.extract import extract_block
from psicotest.checkers.base import CheckOutcome  # HOLE: verify actual import path

if TYPE_CHECKING:
    pass

# Sentence delimiter pattern
SENTENCE_END_RE: re.Pattern[str] = re.compile(r"[.!?]")


def _count_words(text: str) -> int:
    """Count words (whitespace-split tokens)."""
    return len(text.split())


def _count_sentences(text: str) -> int:
    """Count sentences by terminal punctuation."""
    # Split on delimiters, filter empty
    parts = SENTENCE_END_RE.split(text)
    return sum(1 for p in parts if p.strip())


def _extract_sentences(text: str) -> list[str]:
    """Extract individual sentences (text before each delimiter)."""
    sentences = []
    last = 0
    for m in SENTENCE_END_RE.finditer(text):
        sent = text[last : m.end()].strip()
        if sent:
            sentences.append(sent)
        last = m.end()
    return sentences


def check(content: str, item: dict) -> CheckOutcome:
    """
    Check PR item response.

    Args:
        content: full model response (visible content)
        item: item dict with "constraints" key

    Returns:
        CheckOutcome with:
            outcome: "pass" | "fail"
            flags: list[str] — names of failed constraints
            score: 1 if pass, 0 if fail
    """
    flags: list[str] = []
    constraints = item["constraints"]

    # Extract block
    block_text, extract_flags = extract_block(content)
    flags.extend(extract_flags)

    if block_text is None:
        return CheckOutcome(outcome="fail", flags=flags, score=0)

    # Word count
    wc = _count_words(block_text)
    if wc < constraints["word_count_min"]:
        flags.append("word_count_low")
    if wc > constraints["word_count_max"]:
        flags.append("word_count_high")

    # Sentence count
    sc = _count_sentences(block_text)
    if sc != constraints["sentence_count"]:
        flags.append("sentence_count")

    # Banned letter
    banned = constraints["banned_letter"].lower()
    if banned in block_text.lower():
        flags.append("banned_letter")

    # Required phrase
    phrase = constraints["required_phrase"].lower()
    if phrase not in block_text.lower():
        flags.append("missing_phrase")

    # Same-start-word (if applicable)
    start_word = constraints.get("same_start_word")
    if start_word:
        sentences = _extract_sentences(block_text)
        for i, sent in enumerate(sentences):
            words = sent.split()
            if not words or words[0].lower() != start_word.lower():
                flags.append("same_start_word")
                break  # flag once

    # Topic sentence (if applicable)
    if constraints.get("topic_sentence"):
        topic = constraints["topic"]
        expected_prefix = f"Topic: {topic}".lower()
        sentences = _extract_sentences(block_text)
        if not sentences or not sentences[0].lower().startswith(expected_prefix):
            flags.append("topic_sentence")

    outcome = "pass" if not flags else "fail"
    score = 1 if outcome == "pass" else 0
    return CheckOutcome(outcome=outcome, flags=flags, score=score)
```

**Flags emitted:** `no_block`, `word_count_low`, `word_count_high`, `sentence_count`, `banned_letter`, `missing_phrase`, `same_start_word`, `topic_sentence`

**HOLE:** Confirm `CheckOutcome` constructor signature matches existing codebase (may be dataclass, NamedTuple, or class). Adjust import and instantiation accordingly.

---

### 2. `src/psicotest/checkers/prose_consistency.py`

```python
"""Checker for PC (prose_consistency) items."""

from __future__ import annotations
import re
from typing import TYPE_CHECKING

from psicotest.checkers.base import CheckOutcome  # HOLE: verify import

if TYPE_CHECKING:
    pass


YES_NO_RE: re.Pattern[str] = re.compile(r"\b(yes|no)\b", re.IGNORECASE)


def _parse_yes_no(text: str) -> str | None:
    """Extract first yes/no from text, lowercase."""
    match = YES_NO_RE.search(text)
    if match:
        return match.group(1).lower()
    return None


def check(
    content: str,
    item: dict,
    prior_answers: dict[str, str] | None = None,
) -> CheckOutcome:
    """
    Check PC item response.

    For variant-1 (first twin): checks correctness only.
    For variant-2 (second twin): checks correctness AND consistency with variant-1.

    Args:
        content: model response (uses ANSWER: extraction upstream; content is extracted value)
        item: item dict with question_id, canonical_answer, variant
        prior_answers: dict mapping slot_id -> extracted answer for prior turns
                       (required for variant-2; see driver extension)

    Returns:
        CheckOutcome
    """
    flags: list[str] = []

    # Parse answer
    answer = _parse_yes_no(content)
    if answer is None:
        flags.append("unparseable")
        return CheckOutcome(outcome="fail", flags=flags, score=0)

    canonical = item["canonical_answer"].lower()
    variant = item["variant"]
    question_id = item["question_id"]

    # Correctness check
    if answer != canonical:
        flags.append("incorrect")

    # Consistency check (variant-2 only)
    if variant == 2:
        if prior_answers is None:
            flags.append("missing_twin_context")
        else:
            # Find the variant-1 twin's answer
            twin_slot = _find_twin_slot(item, prior_answers)
            if twin_slot is None:
                flags.append("twin_not_found")
            else:
                twin_answer = _parse_yes_no(prior_answers.get(twin_slot, ""))
                if twin_answer is None:
                    flags.append("twin_unparseable")
                elif twin_answer != answer:
                    flags.append("inconsistent")

    outcome = "pass" if not flags else "fail"
    score = 1 if outcome == "pass" else 0
    return CheckOutcome(outcome=outcome, flags=flags, score=score)


def _find_twin_slot(item: dict, prior_answers: dict[str, str]) -> str | None:
    """
    Find the slot ID of the variant-1 twin for this variant-2 item.

    HOLE: Implementation depends on how slot metadata is structured.
    Option A: item contains "twin_slot" field set at generation time.
    Option B: scan prior_answers for matching question_id.

    Implementer must verify which approach the driver supports.
    """
    # Placeholder: assume item["twin_slot"] is set by wiring
    return item.get("twin_slot")
```

**Flags emitted:** `unparseable`, `incorrect`, `missing_twin_context`, `twin_not_found`, `twin_unparseable`, `inconsistent`

**Driver extension required** — see Wiring section.

---

## Battery and Wiring Diffs

### File: `src/psicotest/generators/registry.py`

```diff
+ from psicotest.generators import prose_block
+ from psicotest.generators import prose_consistency

  GENERATORS: dict[str, Callable] = {
      # ... existing entries ...
+     "gen_prose_block": prose_block.generate,
+     "gen_prose_consistency": prose_consistency.generate,
  }
```

**HOLE:** Verify registry uses direct function reference or module + attribute string. Adjust registration format accordingly.

---

### File: `src/psicotest/checkers/registry.py`

```diff
+ from psicotest.checkers import prose_block as pr_checker
+ from psicotest.checkers import prose_consistency as pc_checker

  CHECKERS: dict[str, Callable] = {
      # ... existing entries ...
+     "PR": pr_checker.check,
+     "PC": pc_checker.check,
  }
```

---

### File: `src/psicotest/generators/slots.py`

```diff
  # Rename constant
- SLOTS_V4: list[Slot] = [
+ SLOTS_V5: list[Slot] = [
      # ... existing 26 slots unchanged ...
+     _row("S29", "PR", "gen_prose_block", "PR", level=1),
+     _row("S30", "PR", "gen_prose_block", "PR", level=2),
+     _row("S31", "PC", "gen_prose_consistency", "PC", level=0, variant=1, twin_slot="S32"),
+     _row("S32", "PC", "gen_prose_consistency", "PC", level=0, variant=2, twin_slot="S31"),
  ]

+ # Backwards compat alias (deprecate in v6)
+ SLOTS_V4 = SLOTS_V5[:26]
```

**Note on PC slots:**
- Both S31 and S32 must use `rng.derive("PC")` (same path) so they get the same `question_id`.
- `variant` passed to generator selects surface paraphrase.
- `twin_slot` metadata for checker cross-reference.

**HOLE:** Verify `_row` signature supports extra kwargs (`variant`, `twin_slot`). If not, extend `Slot` dataclass/namedtuple with optional fields.

---

### File: `src/psicotest/runner/battery.py`

```diff
  BATTERY_VERSION = "v5"  # was "v4"

  ORDER_A: list[int] = [
      # ... existing 32 turns unchanged ...
+     33,  # S29 (PR level 1)
+     34,  # S31 (PC variant-1)
+     35,  # S30 (PR level 2)
+     36,  # S32 (PC variant-2)
  ]

  ORDER_B: list[int] = [
      # ... existing mirror logic ...
+     # S31 and S32 must remain >= 10 turns apart
+     # Suggested: ORDER_B puts S31 at turn 34, S32 at turn 36 (matches ORDER_A gap)
+     33,  # S29
+     34,  # S31
+     35,  # S30
+     36,  # S32
  ]
```

**Twin separation constraint:** `|turn(S31) - turn(S32)| >= 10`. With turns 34 and 36 that's only 2 apart — **VIOLATES REQUIREMENT**.

**Correction:** Adjust ORDER:
```python
ORDER_A: list[int] = [
    # ... existing 32 ...
    33,  # S29 (PR level 1)
    34,  # S31 (PC variant-1)  <-- early
    35,  # S30 (PR level 2)
    # ... interleave with earlier turns if possible, else:
    36,  # placeholder filler or moved existing
    ...,
    # S32 must be turn >= 44 to satisfy gap
]
```

**HOLE:** The 4 new slots cannot all fit in turns 33–36 while maintaining PC twin separation >= 10. Options:
1. Extend ORDER to 44+ turns (add filler/repeat slots 37–43)
2. Insert S32 into existing turn sequence (move something)
3. Relax gap to >= 2 (needs design approval)

**Recommendation:** Extend to 44 turns with filler items (perhaps PR level 0 practice items, non-scored). Mark as **Accepted deviation** candidate if implementer cannot extend turn count.

---

### File: `src/psicotest/runner/driver.py`

**Extension for PC cross-turn context:**

```diff
  class Driver:
      def __init__(self, ...):
          # ... existing ...
+         self._turn_answers: dict[str, str] = {}  # slot_id -> extracted answer

      def _run_turn(self, turn_num: int, slot: Slot, ...) -> TurnResult:
          # ... existing: send prompt, get response, extract answer ...

+         # Store extracted answer for cross-turn reference
+         self._turn_answers[slot.slot_id] = extracted_answer

          # ... existing: call checker ...
-         outcome = checker(content, item)
+         # Pass prior answers for checkers that need cross-turn context
+         if slot.family == "PC":
+             outcome = checker(content, item, prior_answers=self._turn_answers)
+         else:
+             outcome = checker(content, item)

          # ... existing: return result ...
```

**Accepted deviation point:** This changes the checker call signature for PC family. The `prior_answers` parameter is optional and only PC checker uses it. All other checkers ignore it (signature unchanged for them). If the checker registry uses a uniform `check(content, item)` interface, the PC checker must be special-cased in driver or wrapped.

**Alternative design:** Pass `prior_answers` to all checkers as optional kwarg; existing checkers' signatures accept `**kwargs` and ignore. Verify existing checker signatures support this.

---

### File: `src/psicotest/report.py` (or wherever capability map lives)

```diff
  CAPABILITY_MAP: dict[str, list[str]] = {
      # ... existing families ...
+     "PR": ["S29", "S30"],
+     "PC": ["S31", "S32"],
  }

- MAX_CAPABILITY = 23
+ MAX_CAPABILITY = 27
```

**Capability count:**
| Family | Slots | Points |
|--------|-------|--------|
| Existing 23 families | S01–S26* | 23 |
| PR | S29, S30 | 2 |
| PC | S31, S32 | 2 |
| **Total** | | **27** |

**HOLE:** Verify existing 26 slots map to 23 capability points (some slots may be twins/variants counted once). Recount by reading `CAPABILITY_MAP` before finalizing. The user spec said 28; reconcile discrepancy.

---

## Test Plan

### Unit Tests: `tests/test_checkers_prose_block.py`

| Test | Constraint | Input | Expected |
|------|------------|-------|----------|
| `test_no_block` | extraction | "Hello world" (no BEGIN/END) | flags=["no_block"], fail |
| `test_word_count_low` | word_count | 30 words in [50,80] window | flags=["word_count_low"], fail |
| `test_word_count_high` | word_count | 100 words in [50,80] window | flags=["word_count_high"], fail |
| `test_word_count_pass` | word_count | 65 words in [50,80] window | pass |
| `test_sentence_count_wrong` | sentence_count | 4 sentences, expected 5 | flags=["sentence_count"], fail |
| `test_banned_letter_present` | banned_letter | "e" banned, text contains "the" | flags=["banned_letter"], fail |
| `test_banned_letter_absent` | banned_letter | "e" banned, text avoids it | pass (this constraint) |
| `test_missing_phrase` | required_phrase | "in fact" required, absent | flags=["missing_phrase"], fail |
| `test_phrase_present` | required_phrase | "in fact" required, present | pass |
| `test_same_start_word_violated` | same_start_word | "This" required, sentence 2 starts "Another" | flags=["same_start_word"], fail |
| `test_topic_sentence_violated` | topic_sentence | expected "Topic: parks", got "Parks are..." | flags=["topic_sentence"], fail |
| `test_all_constraints_pass` | all | valid prose meeting all level-2 constraints | pass |

### Unit Tests: `tests/test_checkers_prose_consistency.py`

| Test | Scenario | Expected |
|------|----------|----------|
| `test_parse_yes` | content="ANSWER: Yes" | answer="yes" |
| `test_parse_no` | content="ANSWER: NO" | answer="no" |
| `test_unparseable` | content="ANSWER: maybe" | flags=["unparseable"], fail |
| `test_correct_v1` | answer="yes", canonical="yes", variant=1 | pass |
| `test_incorrect_v1` | answer="no", canonical="yes", variant=1 | flags=["incorrect"], fail |
| `test_consistent_v2` | answer="yes", twin_answer="yes", canonical="yes" | pass |
| `test_inconsistent_v2` | answer="yes", twin_answer="no", canonical="yes" | flags=["inconsistent"], fail |
| `test_both_wrong_but_consistent` | answer="no", twin="no", canonical="yes" | flags=["incorrect"], fail (inconsistency not flagged if both same) |

### Unit Tests: `tests/test_extract.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_block_simple` | "BEGIN\nHello\nEND" | ("Hello", []) |
| `test_block_multiline` | "BEGIN\nLine1\nLine2\nEND" | ("Line1\nLine2", []) |
| `test_block_with_preamble` | "Sure!\nBEGIN\nText\nEND" | ("Text", []) |
| `test_no_begin` | "Text\nEND" | (None, ["no_block"]) |
| `test_no_end` | "BEGIN\nText" | (None, ["no_block"]) |
| `test_nested_begin` | "BEGIN\nBEGIN\nInner\nEND\nEND" | takes first BEGIN to first END |

### Determinism Tests: `tests/test_determinism.py`

```python
def test_prose_block_deterministic():
    for seed in [0, 42, 12345]:
        rng1 = Rng(seed)
        rng2 = Rng(seed)
        for level in [0, 1, 2]:
            item1 = prose_block.generate(rng1.derive("PR"), level)
            item2 = prose_block.generate(rng2.derive("PR"), level)
            assert item1 == item2


def test_prose_consistency_twins_same_question():
    for seed in [0, 42, 12345]:
        rng = Rng(seed)
        item1 = prose_consistency.generate(rng.derive("PC"), level=0, variant=1)
        rng = Rng(seed)  # reset
        item2 = prose_consistency.generate(rng.derive("PC"), level=0, variant=2)
        assert item1["question_id"] == item2["question_id"]
        assert item1["canonical_answer"] == item2["canonical_answer"]
        assert item1["variant"] != item2["variant"]
```

### Property Tests: `tests/test_properties_prose.py`

```python
from hypothesis import given, strategies as st


@given(seed=st.integers(0, 2**32 - 1), level=st.sampled_from([0, 1, 2]))
def test_prose_block_satisfiable_by_construction(seed, level):
    """Every generated prose_block has at least one valid answer."""
    rng = Rng(seed)
    item = prose_block.generate(rng.derive("PR"), level)
    c = item["constraints"]

    # Construct a proof instance
    proof = _construct_proof_instance(c)

    # Wrap in block
    content = f"BEGIN\n{proof}\nEND"

    outcome = pr_checker.check(content, item)
    assert outcome.outcome == "pass", f"Proof instance failed: {outcome.flags}"


def _construct_proof_instance(c: dict) -> str:
    """Build a minimal valid prose string for given constraints."""
    # Use words without banned letter
    safe_words = _get_safe_words(c["banned_letter"], count=100)

    # Build sentences
    sentences = []
    words_per_sentence = c["word_count_min"] // c["sentence_count"]

    for i in range(c["sentence_count"]):
        if c.get("same_start_word"):
            start = c["same_start_word"]
        elif i == 0 and c.get("topic_sentence"):
            start = f"Topic: {c['topic']}"
        else:
            start = safe_words[i * words_per_sentence]

        # Fill sentence
        sent_words = [start] + safe_words[i * words_per_sentence + 1 : (i + 1) * words_per_sentence]
        sentences.append(" ".join(sent_words) + ".")

    # Insert required phrase
    text = " ".join(sentences)
    phrase = c["required_phrase"]
    # Inject phrase into first sentence if not already safe
    # ... (implementation detail)

    return text


def _get_safe_words(banned: str, count: int) -> list[str]:
    """Return common words not containing the banned letter."""
    # Static pool of e-free, a-free, t-free words
    # (precomputed and frozen for determinism)
    ...
```

**HOLE:** The `_construct_proof_instance` implementation is non-trivial. The implementer must verify that word pools exist for each banned letter (e, a, t) with sufficient variety. If lipogram construction is too hard, fall back to a fixed proof corpus per level.

### Golden Tests

```bash
# Regenerate golden file
python tools/gen_golden.py --write --force

# Golden file location
tests/golden/items_v5.json
```

Golden file must include all 30 slots (26 existing + 4 new) with deterministic seed.

### Banned-Constructs Enforcement

New files must pass existing `tests/test_banned_constructs.py`:
- No `eval`, `exec`, `compile`
- No `import os.system`, `subprocess` raw calls outside allowed patterns
- No floating-point arithmetic in scoring
- No network I/O in generators/checkers

### Integration: Two-Seed Verification

```bash
PYTHONHASHSEED=0 python -m pytest tests/ -v
PYTHONHASHSEED=42 python -m pytest tests/ -v
```

Both must pass. Any hash-dependent ordering in generators will cause failures.

### Live Run (Acceptance, Not Gate)

```bash
# After tests pass
python -m psicotest.runner --model <target-model> --battery v5 --output iq_v5_results.json
```

Record: total score, per-family breakdown, PR/PC flag distribution. No numeric gate — this is ceiling data for the discriminator items.

---

## Accepted Deviations Anticipated

1. **PC checker cross-turn context**: If extending `check(content, item)` to `check(content, item, prior_answers=None)` proves incompatible with the checker registry's uniform dispatch, wrap PC checker in driver with explicit prior-answer injection. Mark in code: `# T5D deviation: PC checker requires prior_answers`.

2. **Twin turn separation**: If ORDER cannot be extended to 44+ turns to satisfy >= 10 turn gap for PC twins, document the actual gap achieved and add a `KNOWN_LIMITATION` constant. Minimum acceptable gap: 6 turns (half the requested).

3. **Slot kwargs extension**: If `_row()` / `Slot` cannot accept `variant` and `twin_slot` fields, encode them in a separate `SLOT_METADATA` dict keyed by slot_id, and merge at runtime in driver.

4. **Proof instance generator**: If constructing valid lipogram prose programmatically is infeasible for property tests, replace with corpus-driven approach: frozen `PROOF_INSTANCES` dict mapping `(level, banned_letter)` to a known-valid string, verified once manually.

5. **Capability count**: If recount shows existing 26 slots map to something other than 23 capabilities, adjust `MAX_CAPABILITY` arithmetic accordingly and note the discrepancy in commit message.

---

## Summary Checklist

| Artifact | Action | Depends On |
|----------|--------|------------|
| `prose_block.py` | Create | — |
| `prose_consistency.py` | Create | — |
| `extract.py` | Add `extract_block` | — |
| `checkers/prose_block.py` | Create | `extract.py`, `CheckOutcome` shape |
| `checkers/prose_consistency.py` | Create | Driver extension |
| `generators/registry.py` | Register 2 keys | Generators exist |
| `checkers/registry.py` | Register 2 keys | Checkers exist |
| `slots.py` | Rename constant, add S29–S32 | `_row` kwargs |
| `battery.py` | Bump version, extend ORDER | Twin separation decision |
| `driver.py` | Add `_turn_answers` for PC | — |
| `report.py` | Update capability map | Recount |
| Unit tests | Create | Modules exist |
| Property tests | Create | Proof instance strategy |
| Golden v5 | Generate | All wiring complete |
| Live run | Execute | Tests green |
T5D_EXIT=0

## Accepted deviations

1. **PC twin placement (D6).** D6 says "PC twins at ORDER_A turns 31 and 36 (gap 5)",
   but turn 31 is S27 and turn 32 is S28 in the frozen ORDER_A, and D6 also forbids
   reshuffling turns 1..32 — the literal instruction is unsatisfiable. The twins are
   placed at the ends of the only free block, ORDER_A turns 33 and 36 (gap 3, the
   maximum achievable without touching turns 1..32), with PR at turns 34 and 35.
   The >=10-turn twin separation preference is recorded here per D6: the turn
   permutation is frozen, enlarging it for v5 would re-shuffle all 32 turns and
   invalidate the whole golden set twice more; revisit in v6.
   Evidence: src/psicotest/runner/battery.py ORDER_A tail; the recorded preference
   is the contract's own "Twin separation constraint" section.

2. **ORDER_B tail is identical to ORDER_A.** `P` (the 22-turn mirror list) was not
   extended; turns 33-36 fall back to the existing identity mapping, so ORDER_B
   keeps S31 at turn 33 before S32 at turn 36. Extending P would have mirrored the
   new turns onto existing ones (S31 would land at turn 5, reshuffling ORDER_B's
   turns 1..32) and scored variant-2 before variant-1. This follows D12's "ORDER_B
   derives as it already does" with unchanged derivation input.
   Evidence: src/psicotest/runner/battery.py (P unchanged); the pinned ORDER_B_SLOTS
   mapping in tests/test_generators_battery.py is unchanged.

3. **D5's pinned unit test wording.** D5 demands "twin wrong-but-parseable +
   variant-2 correct+same word = pass", which contradicts D5's own rule sentence
   ("variant-2 scores pass if it is correct and does not contradict a parseable twin
   answer"): if the twin is wrong and variant-2 repeats the twin's word, variant-2
   is incorrect and must fail. Implemented the rule sentence (authoritative) and
   pinned the consistent test: twin "no" (wrong) + variant-2 "no" scores WRONG with
   detail "incorrect" and never "inconsistent"; the pass case (correct + agreeing
   twin) and the missing-twin non-failure are pinned too.
   Evidence: tests/test_prose_families.py
   (TestProseConsistencyChecker.test_d5_twin_wrong_but_parseable_same_word).

4. **Contract flag names live in CheckResult.detail.** The contract's checker flags
   (no_block, word_count_low/high, sentence_count, banned_letter, missing_phrase,
   same_start_word, topic_lead, unparseable, incorrect, inconsistent,
   missing_twin_context) are not in the framework's fixed FLAG_ORDER vocabulary and
   make_result() rejects unknown flags, so the checkers return outcome
   OK/WRONG/NOANS/TRUNC with the framework flags (FMT, R2_OK/R2_FAIL, plus the
   standard LEAK/LOOP/MULTI/REASONING_ONLY from prepare) and report each failed
   constraint as a ";"-joined detail token using the contract's names. A missing
   BEGIN/END block maps to outcome NOANS (the framework's "nothing parseable"
   outcome) with detail "no_block".
   Evidence: src/psicotest/checkers/prose_block.py, src/psicotest/checkers/prose_consistency.py;
   make_result in src/psicotest/checkers/common.py.

5. **PC twin lookup scans `prior` (D4 fallback).** The Item dataclass has no spare
   top-level field for the sibling slot id, so per D4's "otherwise" branch the PC
   checker scans the driver's slot->content `prior` mapping for the slot whose
   ANSWER value parses as yes/no; the PC twins are the only yes/no family in the
   battery, and the lowest slot id wins for determinism. The choice is recorded
   here as D4 instructs.
   Evidence: src/psicotest/checkers/prose_consistency.py::_twin_answer.

6. **Pools curated around the fixed proofs (D7/D9).** One fixed proof per level can
   only satisfy every draw if the pools are degenerate where a draw would otherwise
   be unsatisfiable by a single fixed string: START_WORD_POOL_L1/L2 and
   TOPIC_POOL_L2 have exactly one entry each (every sentence must start with the
   drawn word; the level-2 first sentence must start with the drawn topic words),
   every phrase in a level pool appears verbatim in that level's proof, and all
   topics avoid e, a and t entirely. Contract pool entries that contain a letter
   banned at their level ("in contrast" has t, "without doubt" has t, "on
   reflection" has e, "Topic:" lead-in contains e) were replaced per D7's "fix the
   pool, not the proof"; the level-2 "Topic: {topic}" lead-in is replaced by "first
   sentence starts with the two topic words" as D7 rules.
   Evidence: src/psicotest/generators/prose_block.py (pools, _PROOFS); module
   docstring states the D8 sentence/word counting invariant; tests/test_prose_families.py
   (TestProsePoolInvariants, TestProofInstances).

7. **R1 audit understands the block protocol.** check_rules R1 is protocol-aware:
   for items with answer_kind "block" (PR) it verifies a BEGIN/END block is present
   instead of demanding an ANSWER line, because the PR prompt explicitly instructs
   the block format; without this every PR turn would flag R1_FAIL forever.
   Evidence: src/psicotest/checkers/rules.py; pinned R1 counts {ok: 33, fail: 0,
   na: 3} in tests/test_runner_report.py.

8. **PC "base" variant aliases pc1.** The golden tool appends an animal case with
   variant "base" for every non-rule generator, so gen_prose_consistency accepts
   "base" (same surface as pc1) and spec.VARIANTS gained "pc1"/"pc2".
   Evidence: src/psicotest/spec.py VARIANTS; src/psicotest/generators/prose_consistency.py
   _SURFACE_INDEX.

9. **README left untouched (D14).** The repository README is a two-line stub with
   no families table and no calibration wording, so there was no table row to add
   for PR and PC; zero sentences added (D14 allows at most one).

10. **rng.json unchanged.** tools/gen_golden.py --write --force (rng mode) reported
    no change; only tests/golden/items_v4.json was deleted and items_v5.json
    regenerated per D12 (all item digests shift because the battery label is part of
    the instance/surface seed derivation).

11. **Turn layout.** Section: turn layout. Deviation: implementation pins S31 at turn
   31, S29 at 33, S30 at 34, S32 at 36. Rationale: turns 1..32 permutation stays
   frozen so the v4 golden ordering evidence remains comparable and only 4 new turns
   are added. Impact: the >=10-turn twin gap from the contract body is reduced to 5
   (already covered by deviation 1; not duplicated here).

12. **Driver prior map shape.** Section: driver prior map. Deviation: the prior map
   stores full visible ITEM response content per slot id, not pre-extracted answers;
   the PC checker parses the twin's ANSWER line itself. Rationale: extraction stays
   inside checkers, keeping the driver protocol-agnostic and reusing one extractor.
   Impact: prior values may contain reasoning text alongside the answer.
