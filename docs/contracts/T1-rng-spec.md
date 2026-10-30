# T1 implementation contract: `rng.py`, `spec.py`, golden fixtures, T1 tests

This contract covers only T1 from DESIGN §14. DESIGN.md is the source of truth. This document adds the API you asked for (`splitmix64`, `derive_item_seed`, `item_key`, `GeneratorSpec`, `tools/gen_golden.py`) without changing anything §3.1 or §4 already defines.

---

## 1. Files

| Action | Path |
|---|---|
| create | `src/psicotest/rng.py` |
| create | `src/psicotest/spec.py` |
| create | `tools/gen_golden.py` |
| create | `tests/_bootstrap.py` |
| create (generated) | `tests/golden/rng.json` |
| create | `tests/test_rng.py`, `tests/test_spec.py`, `tests/test_banned_constructs.py`, `tests/test_gen_golden.py` |
| modify | `pyproject.toml` (ruff section only, §7) |
| modify | `.github/workflows/ci.yml` (§7) |
| modify | `tests/test_scaffold.py`: add `import _bootstrap` as its own import block, between `import unittest` and `import psicotest.cli` |
| modify | `DESIGN.md` §3.1: add `splitmix64`, `derive_item_seed`, `item_key`, `VARIANTS`, `GeneratorSpec` to the rng/spec rows. §4.5: add the extra `rng.json` keys and `tools/gen_golden.py`. DESIGN requires any API addition to be recorded in the same change |

Do not touch `src/psicotest/__init__.py` or `src/psicotest/cli.py`.

## 2. Global rules

- Python ≥ 3.11 syntax only. No PEP 695 generics and no `type` statements. Use `typing.TypeVar`.
- Stdlib only: `hashlib`, `json`, `dataclasses`, `decimal`, `fractions`, `re`, `collections.abc`, `typing`, `pathlib`, `sys`, `argparse`, `importlib`, `ast`, `tempfile`, `unittest`.
- **Zero comments**: no `#` lines and no docstrings in any T1 file.
- `rng.py` must not import `spec.py`. `spec.py` imports `Rng` from `psicotest.rng`.
- `rng.py` and `spec.py` must pass the banned-constructs scan (§6.3). That means they cannot use the names `float`, `hash` or `id` anywhere, including in `isinstance` checks. Floats are rejected by falling through to the final `TypeError`, not by name.
- Every test module starts with this import layout. `_bootstrap` resolves as third-party and `psicotest` as first-party, so ruff's isort keeps `_bootstrap` first:
  ```python
  import unittest

  import _bootstrap

  from psicotest.rng import Rng
  ```

## 3. `src/psicotest/rng.py`

### 3.1 Module constants

```python
MASK64 = (1 << 64) - 1
GOLDEN_GAMMA = 0x9E3779B97F4A7C15
SEP = "\x1f"
ITEM_STREAMS = ("instance", "surface")
```

### 3.2 `splitmix64(state: int) -> tuple[int, int]`

- Raises `ValueError` unless `0 <= state <= MASK64`. A `bool` is rejected with `TypeError`.
- Returns `(new_state, output)` where:
  ```
  new_state = (state + GOLDEN_GAMMA) & MASK64
  z = new_state
  z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
  z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
  output = z ^ (z >> 31)
  ```
- It is a pure function with no hidden state.

### 3.3 `class Rng`

`__slots__ = ("_state",)`. There is no public state accessor.

| Member | Semantics |
|---|---|
| `__init__(self, seed: int)` | `TypeError` if `seed` is not an `int` or is a `bool`. `self._state = seed & MASK64`, so negative seeds and seeds ≥ 2⁶⁴ wrap |
| `next_u64(self) -> int` | `self._state, out = splitmix64(self._state)` then `return out`. All other methods draw **only** through `self.next_u64()` so a test subclass can override it |
| `below(self, n: int) -> int` | `TypeError` if `n` is a `bool` or not an `int`; `ValueError` if `n < 1` or `n > 2**64`. `limit = (1 << 64) - ((1 << 64) % n)`. Loop: `x = self.next_u64()`, return `x % n` if `x < limit`. Always consumes ≥ 1 draw, including when `n == 1`; `n == 2**64` is legal and consumes exactly one draw, returning it |
| `randint(self, lo: int, hi: int) -> int` | `ValueError` if `hi < lo`. Returns `lo + self.below(hi - lo + 1)` |
| `choice(self, seq: Sequence[T]) -> T` | `seq[self.below(len(seq))]`. An empty sequence raises `ValueError` (from `below(0)`) |
| `shuffle(self, lst: MutableSequence) -> None` | `for i in range(len(lst) - 1, 0, -1): j = self.below(i + 1)`, then swap `lst[i], lst[j]`. Makes `len - 1` draws, or 0 when `len < 2` |
| `sample(self, seq: Iterable[T], k: int) -> list[T]` | `lst = list(seq)`. `ValueError` unless `0 <= k <= len(lst)`. `for i in range(k): j = i + self.below(len(lst) - i)`, then swap. Returns `lst[:k]`. Makes exactly `k` draws and never mutates the input |
| `fork(self, label: str) -> Rng` | `TypeError` if `label` is not a `str`. Returns `Rng(derive_seed(self.next_u64(), label))`. The parent advances exactly one draw |

### 3.4 `derive_seed(*parts: str | int) -> int`

- Raises `ValueError` if there are no parts.
- Raises `TypeError` if any part is not a `str` or `int`, or is a `bool`.
- Raises `ValueError` if any `str` part contains `SEP`.
- Returns `int.from_bytes(hashlib.sha256(SEP.join(str.__str__(p) if isinstance(p, str) else int.__repr__(p) for p in parts).encode("utf-8")).digest()[:8], "big")`.
- Parts are converted with `str.__str__` for `str` parts and `int.__repr__` for `int` parts, so `__str__`/`__repr__` overrides cannot alter seeds.
- `hashlib.sha256` is the only hash used. The builtin `hash()` is never used.
- `derive_seed(1, 2) == derive_seed("1", "2")` holds by construction. This is intended and documented by a test.

### 3.5 `derive_item_seed(battery: str, slot: str, generator: str, generator_version: int, user_seed: int, stream: str) -> int`

- Raises `ValueError` if `stream not in ITEM_STREAMS`.
- Returns `derive_seed("psicotest", battery, slot, generator, generator_version, user_seed, stream)`. This is DESIGN §4.2, rows 1–2. Twin and mirror resolution belongs to T4 and is out of scope here.

## 4. `src/psicotest/spec.py`

### 4.1 Constants

```python
VARIANTS = ("base", "clean", "relabel")
GENERATOR_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
FAMILY_RE = re.compile(r"^[A-Z][A-Z0-9]*$")
ANIMAL_RE = re.compile(r"^[a-záéíóúüñ]+$")
```

### 4.2 Dataclasses

All are `@dataclass(frozen=True)`. Field order is exactly as listed.

| Class | Fields |
|---|---|
| `GenContext` | `variant: str`, `animal: str \| None`, `surface_rng: Rng` |
| `Item` | `item_id: str`, `battery_version: str`, `slot: str`, `family: str`, `generator: str`, `generator_version: int`, `knobs: Mapping[str, object]`, `variant: str`, `instance_seed: int`, `surface_seed: int`, `animal: str \| None`, `prompt_es: str`, `key: Mapping[str, object]`, `meta: Mapping[str, object]`, `answer_kind: str`, `capability: bool` |
| `CheckResult` | `outcome: str`, `score: int`, `value: object`, `flags: tuple[str, ...]`, `detail: str` |
| `Turn` | `turn: int`, `kind: str`, `slot: str \| None`, `prompt_es: str`, `item: Item \| None`, `rules_active: tuple[str, ...]`, `r3_trigger: bool` |
| `GeneratorSpec` | `name: str`, `version: int`, `family: str`, `variants: tuple[str, ...] = ("base",)` |

Only `GeneratorSpec` validates its fields. It does so in `__post_init__` and raises `ValueError` if any of these fail:
- `name` matches `GENERATOR_NAME_RE`.
- `version` is an `int`, not a `bool`, and ≥ 1.
- `family` matches `FAMILY_RE`.
- `variants` is a non-empty `tuple` whose first element is `"base"`, with no duplicates, and every element in `VARIANTS`.

`GeneratorSpec.key(self, seed: int, variant: str = "base", animal: str | None = None) -> str` raises `ValueError` if `variant not in self.variants`. Otherwise it returns `item_key(self.name, self.version, seed, variant, animal)`.

### 4.3 `item_key(generator: str, generator_version: int, seed: int, variant: str, animal: str | None = None) -> str`

- Returns `f"{generator}@{generator_version}/{seed}/{variant}"`, followed by `f"/animal={animal}"` when `animal is not None`.
- Raises `ValueError` when any of these hold:
  - `generator` does not match `GENERATOR_NAME_RE`.
  - `generator_version` is not an `int`, is a `bool`, or is < 1.
  - `seed` is not an `int`, is a `bool`, or is < 0.
  - `variant not in VARIANTS`.
  - `animal` is not `None` and does not match `ANIMAL_RE`.

### 4.4 `canonical_json(obj) -> bytes`

The function body is:

`json.dumps(_canon(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")`

`_canon` checks types in this order:

1. `None`, `bool`, `int`, `str`: returned unchanged.
2. `Decimal`: `ValueError` if `not o.is_finite()`, otherwise `str(o)`.
3. `Fraction`: `f"{o.numerator}/{o.denominator}"`.
4. A dataclass instance (`dataclasses.is_dataclass(o) and not isinstance(o, type)`): `{f.name: _canon(getattr(o, f.name)) for f in dataclasses.fields(o)}`. Do not use `asdict`, because it deep-copies.
5. `Mapping`: `TypeError` if any key is not a `str`, otherwise `{k: _canon(v)}`.
6. `list` or `tuple`: `[_canon(x) for x in o]`.
7. Anything else raises `TypeError`. That covers float, set, frozenset, bytes and `Rng`, so `GenContext` is not serializable by design.

## 5. `tools/gen_golden.py`

- `ROOT = Path(__file__).resolve().parents[1]`. `DEFAULT_PATH = ROOT / "tests" / "golden" / "rng.json"`.
- `_rng()` inserts `str(ROOT / "src")` at the front of `sys.path` if it is missing, then returns `importlib.import_module("psicotest.rng")`. Importing inside a function avoids ruff E402.
- `build_rng_golden() -> dict` builds the layout in §5.1. Every sequence starts from a **fresh** `Rng`.
- `render(data: dict) -> bytes` returns `(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")`.
- `main(argv: list[str] | None = None) -> int` uses argparse with these flags: `--check` (default mode), `--write`, `--force`, and `--path PATH` (default `DEFAULT_PATH`).

| Mode | File state | Result |
|---|---|---|
| check | identical | exit 0 |
| check | missing or different | message to stderr, exit 1 |
| `--write` | missing | write with `Path.write_bytes`, exit 0 |
| `--write` | identical | no-op, exit 0 |
| `--write` | different | refuse, file untouched, exit 1 |
| `--write --force` | any | overwrite, exit 0 |

- The script ends with `if __name__ == "__main__": raise SystemExit(main())`.

### 5.1 Layout of `tests/golden/rng.json`

The file has these keys in sorted order. Big integers are JSON integers. The file uses LF line endings, UTF-8, and ends with a newline.

| Key | Value |
|---|---|
| `below7_seed42` | 16 ints: `Rng(42).below(7)` ×16 |
| `chi2_below7_seed7_n70000` | string `"p/q"`: `Fraction(sum((c - 10000) ** 2 for c in counts), 10000)` |
| `counts_below7_seed7_n70000` | 7 ints: bin counts of `Rng(7).below(7)` ×70000 |
| `derive_seed` | list of `{"parts": [...], "value": int}` for exactly these parts, in this order: `["psicotest","v1","S01","gen_state_boxes",1,10001,"instance"]`, `["psicotest","v1","S01","gen_state_boxes",1,10001,"surface"]`, `["psicotest","v1",10001,"A",17,"animal"]`, `["req","v1",10001,"A",2]`, `["ñandú",0]`, `[""]`, `["abc"]` |
| `fork_surface_seed42` | 4 ints: first 4 `next_u64()` of `Rng(42).fork("surface")` |
| `next_u64` | `{"0": [16 ints], "1": [16 ints], "18446744073709551615": [16 ints]}` |
| `sample100_5_seed42` | 5 ints: `Rng(42).sample(range(100), 5)` |
| `schema` | `1` |
| `shuffle10_seed42` | 10 ints: `list(range(10))` after `Rng(42).shuffle` |

The item golden `items_v1.json` and its regeneration tool belong to T3 and are out of scope here.

## 6. Unit tests

`GOLDEN = json.loads((ROOT / "tests/golden/rng.json").read_text("utf-8"))`, with `ROOT = Path(__file__).resolve().parents[1]`.

**Pinned literals.** Constants named `PIN_*` are transcribed from the first tool run (§8 step 4) and written as hex or int literals in the test module. They act as a second lock alongside the JSON file.

### 6.1 `tests/test_rng.py` — `class TestRng(unittest.TestCase)`

| Test | Assertions |
|---|---|
| `test_splitmix64_function` | `assertEqual(splitmix64(0), (0x9E3779B97F4A7C15, 0xE220A8397B1DCDAF))`. Chaining the state through four calls gives outputs `[0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F, 0xF88BB8A8724C81EC]`. `assertRaises(ValueError)` for `-1` and `2**64`. `assertRaises(TypeError)` for `True` |
| `test_splitmix64_golden` | `assertEqual(set(GOLDEN["next_u64"]), {"0", "1", "18446744073709551615"})`. For each key, `[Rng(int(k)).next_u64() for _ in range(16)] == GOLDEN["next_u64"][k]` and length 16. `GOLDEN["next_u64"]["0"][:4]` equals the 4 hex anchors above. `GOLDEN["next_u64"]["1"][0] == PIN_SEED1_FIRST` and `GOLDEN["next_u64"]["18446744073709551615"][0] == PIN_SEEDMAX_FIRST` |
| `test_seed_normalization` | The first 3 outputs of `Rng(2**64)` equal those of `Rng(0)`. The first 3 outputs of `Rng(-1)` equal those of `Rng(2**64 - 1)`. `assertRaises(TypeError)` for `Rng(True)` and `Rng("1")` |
| `test_below_rejection_unbiased` | `r = Rng(7)`, 70000 × `below(7)`, collected into counts. `assertEqual(counts, GOLDEN["counts_below7_seed7_n70000"])` and `assertEqual(counts, PIN_COUNTS7)`. `assertEqual(sum(counts), 70000)`. Each count satisfies `9500 <= c <= 10500`. `chi2 = Fraction(sum((c - 10000) ** 2 for c in counts), 10000)`. `assertEqual(f"{chi2.numerator}/{chi2.denominator}", GOLDEN["chi2_below7_seed7_n70000"])`. `assertLess(chi2, Fraction(22458, 1000))` (χ²₆ critical value at p = 0.001). `assertAlmostEqual(chi2.numerator / chi2.denominator, PIN_CHI2, places=6)` |
| `test_below_rejection_path` | `class Scripted(Rng)` overrides `next_u64` to pop from a list. `TypeError` for `below(True)`, `below(1.0)`, `below("5")`; `ValueError` for `below(0)`, `below(-1)`, `below(2**64 + 1)`, `below(10**30)`. Case 1: script `[MASK64, 5]`, `below(3) == 2`, script empty afterwards. Case 2: script `[2**64 - 2, 2**64 - 1, 13]`, `below(7) == 6`, script empty. Case 3: script `[MASK64]`, `below(8) == 7` with one draw. Case 4: script `[13]`, `below(2**64) == 13` with exactly one draw |
| `test_below_rejects_zero` | `assertRaises(ValueError)` for `below(0)` and `below(-1)` |
| `test_below_n1_consumes_one_draw` | `r = Rng(42)`. `assertEqual(r.below(1), 0)`. `assertEqual(r.next_u64(), GOLDEN_SECOND_42)`, where `GOLDEN_SECOND_42` is the second output of a fresh `Rng(42)` |
| `test_below_golden` | `[Rng(42)…below(7) ×16] == GOLDEN["below7_seed42"] == PIN_BELOW7`. Every value is in `range(7)` |
| `test_shuffle_golden` | `lst = list(range(10))`, `Rng(42).shuffle(lst)`. `assertEqual(lst, GOLDEN["shuffle10_seed42"])` and `assertEqual(lst, PIN_SHUFFLE10)`. `sorted(lst) == list(range(10))`. Shuffling `[]` and `[9]` makes zero draws: the next `next_u64()` equals the first output of a fresh `Rng(42)` |
| `test_sample_golden` | `Rng(42).sample(range(100), 5) == GOLDEN["sample100_5_seed42"] == PIN_SAMPLE5`. The result has 5 distinct values, all in `range(100)`. `sample(range(5), 0) == []` with zero draws. `seq = [1, 2, 3]`; `sample(seq, 2)`; `seq == [1, 2, 3]`. `assertRaises(ValueError)` for `sample([1, 2], 3)` and `sample([1, 2], -1)` |
| `test_randint_and_choice` | `Rng(42).randint(5, 11) == 5 + Rng(42).below(7)`. `Rng(1).randint(3, 3) == 3`. `assertRaises(ValueError)` for `randint(4, 3)`. `Rng(42).choice(["a", "b", "c"]) == ["a", "b", "c"][Rng(42).below(3)]`. `assertRaises(ValueError)` for `choice([])` |
| `test_fork_independent` | `first, second` are the first two outputs of a fresh `Rng(42)`. `p = Rng(42)`, `c = p.fork("surface")`. `c.next_u64() == Rng(derive_seed(first, "surface")).next_u64()`. `p.next_u64() == second`. The first 4 outputs of a fresh fork equal `GOLDEN["fork_surface_seed42"]` and `PIN_FORK4`. `Rng(42).fork("a").next_u64() != Rng(42).fork("b").next_u64()`. The next 16 outputs of child and parent share no value (set intersection is empty). `assertRaises(TypeError)` for `fork(1)` |
| `test_derive_seed_golden` | `derive_seed("") == 0xE3B0C44298FC1C14`. `derive_seed("abc") == 0xBA7816BF8F01CFEA`. `derive_seed("a") == 0xCA978112CA1BBDCA`. `derive_seed("psicotest", "v1", "S01", "gen_state_boxes", 1, 10001, "instance") == int.from_bytes(hashlib.sha256(b"psicotest\x1fv1\x1fS01\x1fgen_state_boxes\x1f1\x1f10001\x1finstance").digest()[:8], "big")`. `derive_seed("ñandú", 0) == int.from_bytes(hashlib.sha256("ñandú\x1f0".encode("utf-8")).digest()[:8], "big")`. Each `GOLDEN["derive_seed"]` entry satisfies `derive_seed(*e["parts"]) == e["value"]`. The parts list equals the 7 vectors in §5.1, in order. `derive_seed(1, 2) == derive_seed("1", "2")`. Every value is `< 2**64` |
| `test_derive_seed_rejects` | `ValueError` for `derive_seed()` and `derive_seed("a\x1fb")`. `TypeError` for `derive_seed(True)`, `derive_seed(1.0)` and `derive_seed(None)` |
| `test_derive_item_seed` | `derive_item_seed("v1", "S01", "gen_state_boxes", 1, 10001, "instance") == GOLDEN["derive_seed"][0]["value"]`. The `"surface"` stream equals `GOLDEN["derive_seed"][1]["value"]`, and the two values differ. `assertRaises(ValueError)` for stream `"animal"` |
| `test_derive_seed_subclass_intenum` (in `tests/test_spec.py`) | An `int` subclass overriding `__repr__` (e.g. `class Weird(int)` returning `"WEIRD"`) and an `enum.IntEnum` member both produce the same seed as the plain int: `derive_seed(Weird(5)) == derive_seed(5)` and `derive_seed(Slot.ONE) == derive_seed(1)` |

### 6.2 `tests/test_spec.py` — `class TestSpec(unittest.TestCase)`

| Test | Assertions (`assertEqual` against exact bytes) |
|---|---|
| `test_canonical_json_bytes` | `canonical_json({"b": [1, Decimal("1.50"), Fraction(-3, 4)], "a": "ñ", "c": None, "d": True, "e": (2, 3), "f": 2**64})` gives `'{"a":"ñ","b":[1,"1.50","-3/4"],"c":null,"d":true,"e":[2,3],"f":18446744073709551616}'.encode("utf-8")` |
| `test_canonical_json_key_order_unicode` | `canonical_json({"é": 1, "z": 2, "Z": 3, "n": {"y": 1, "x": 2}})` gives `'{"Z":3,"n":{"x":2,"y":1},"z":2,"é":1}'.encode("utf-8")` |
| `test_decimal_fraction_serialization` | `canonical_json([Decimal("1.50"), Decimal("1E+2"), Decimal("-0.00"), Fraction(4, 2), Fraction(-3, 4), Fraction(3)])` gives `b'["1.50","1E+2","-0.00","2/1","-3/4","3/1"]'` |
| `test_canonical_json_rejects` | `TypeError` for `1.5`, `{1, 2}`, `frozenset()`, `{1: "a"}`, `b"x"`, `Rng(1)`, and `GenContext("base", None, Rng(1))`. `ValueError` for `Decimal("NaN")` and `Decimal("Infinity")` |
| `test_dataclass_serialization` | `canonical_json(CheckResult("OK", 1, Decimal("12.35"), ("R1_OK", "R2_OK"), ""))` gives `b'{"detail":"","flags":["R1_OK","R2_OK"],"outcome":"OK","score":1,"value":"12.35"}'`. `canonical_json(Turn(2, "item", "S01", "x", None, ("R1", "R2"), False))` gives `b'{"item":null,"kind":"item","prompt_es":"x","r3_trigger":false,"rules_active":["R1","R2"],"slot":"S01","turn":2}'`. `canonical_json(ITEM)` gives the `ITEM` bytes below |
| `test_dataclasses_frozen` | `assertRaises(dataclasses.FrozenInstanceError)` when assigning `ITEM.slot` and `GeneratorSpec("gen_x", 1, "ST").version` |
| `test_item_key_format` | `item_key("gen_state_boxes", 1, 42, "base") == "gen_state_boxes@1/42/base"`. `item_key("gen_gsm_noop", 3, 0, "clean") == "gen_gsm_noop@3/0/clean"`. `item_key("gen_state_boxes", 1, 42, "base", "oveja") == "gen_state_boxes@1/42/base/animal=oveja"` |
| `test_item_key_rejects` | `ValueError` for each argument set: `("Gen", 1, 1, "base")`, `("gen_x", 0, 1, "base")`, `("gen_x", True, 1, "base")`, `("gen_x", 1, -1, "base")`, `("gen_x", 1, True, "base")`, `("gen_x", 1, 1, "mirror")`, `("gen_x", 1, 1, "base", "Oveja")`, `("gen_x", 1, 1, "base", "")` |
| `test_generator_spec_validation` | `GeneratorSpec("gen_gsm_noop", 1, "NOOP", ("base", "clean")).variants == ("base", "clean")`. The default variants are `("base",)`. `ValueError` for: name `"GenX"`; version `0`; version `True`; family `"st"`; variants `()`, `("clean", "base")`, `("base", "base")`, `("base", "mirror")`, and the list `["base"]` |
| `test_generator_spec_key` | `GeneratorSpec("gen_gsm_noop", 2, "NOOP", ("base", "clean")).key(5, "clean") == "gen_gsm_noop@2/5/clean"`. `.key(5, animal="oveja") == "gen_gsm_noop@2/5/base/animal=oveja"`. `.key(5, "relabel")` raises `ValueError` |

The `ITEM` fixture is `Item("v1/S01/10001", "v1", "S01", "ST", "gen_state_boxes", 1, {"ops": 30, "boxes": 6}, "base", 5, 7, None, "Caja A: 3.", {"A": 5}, {}, "keys", True)`. It must serialize to:

```
b'{"animal":null,"answer_kind":"keys","battery_version":"v1","capability":true,"family":"ST","generator":"gen_state_boxes","generator_version":1,"instance_seed":5,"item_id":"v1/S01/10001","key":{"A":5},"knobs":{"boxes":6,"ops":30},"meta":{},"prompt_es":"Caja A: 3.","slot":"S01","surface_seed":7,"variant":"base"}'
```

### 6.3 `tests/test_banned_constructs.py` — `class TestBannedConstructs(unittest.TestCase)`

The module defines `find_violations(source: str, filename: str = "<s>") -> list[str]`. It returns a sorted list of `f"{filename}:{lineno}: {reason}"`, one entry per offending node:

| Rule | Detection |
|---|---|
| Banned modules | `ast.Import` alias, or `ast.ImportFrom` with `level == 0`, whose module equals `random`, `uuid` or `secrets`, or starts with one of them plus `.` |
| Banned from-imports | `from time import time` or `time_ns`; `from os import urandom` or `getrandom` |
| Banned attributes | An `ast.Attribute` chain rooted at an `ast.Name` whose last two dotted parts are one of: `time.time`, `time.time_ns`, `datetime.now`, `datetime.utcnow`, `datetime.today`, `date.today`, `os.urandom`, `os.getrandom` |
| Banned names | Any `ast.Name` with `id` in `{"hash", "id", "float"}` |
| Float literals | `ast.Constant` whose value is a `float` or `complex` |
| Unsorted set iteration | `ast.For.iter` or `ast.comprehension.iter` that is an `ast.Set`, an `ast.SetComp`, or an `ast.Call` to `set` or `frozenset` by name |

**Scan set:**
- `src/psicotest/rng.py`, `spec.py` and `interview.py`, each if it exists.
- Every `*.py` file under `src/psicotest/generators/` and `src/psicotest/checkers/`, if those directories exist.
- Paths are sorted.

| Test | Assertions |
|---|---|
| `test_no_banned_constructs` | `assertIn` for both `rng.py` and `spec.py` paths in the scan set. `assertEqual(all_violations, [])` |
| `test_detector_flags_samples` | `assertEqual(len(find_violations(s)), 1)` for each of these 15 snippets: `"import random"`, `"from random import choice"`, `"import uuid"`, `"import secrets"`, `"x = hash('a')"`, `"y = id(x)"`, `"z = float('1')"`, `"w = 1.5"`, `"import time\nt = time.time()"`, `"from time import time"`, `"import datetime\nd = datetime.datetime.now()"`, `"import os\nb = os.urandom(8)"`, `"for x in {1, 2}:\n    pass"`, `"a = [x for x in set(b)]"`, `"for x in frozenset(b):\n    pass"` |
| `test_detector_allows_clean_sample` | `assertEqual(find_violations("from fractions import Fraction\nfor k in sorted(set(d)):\n    q = Fraction(1, 3)\nn = int('5')"), [])` |

### 6.4 `tests/test_gen_golden.py` — `class TestGenGolden(unittest.TestCase)`

Load the tool with `importlib.util.spec_from_file_location("gen_golden", ROOT / "tools/gen_golden.py")`.

| Test | Assertions |
|---|---|
| `test_golden_file_matches_tool` | `assertEqual(mod.render(mod.build_rng_golden()), (ROOT / "tests/golden/rng.json").read_bytes())` |
| `test_golden_file_layout` | `assertEqual(sorted(data), ["below7_seed42", "chi2_below7_seed7_n70000", "counts_below7_seed7_n70000", "derive_seed", "fork_surface_seed42", "next_u64", "sample100_5_seed42", "schema", "shuffle10_seed42"])`. `data["schema"] == 1`. Lengths are 16, 7, 7, 4, 5 and 10 respectively. The raw bytes end with `b"\n"` and contain no `b"\r"` |
| `test_check_and_write_modes` | Uses `tempfile.TemporaryDirectory`, with `p` a path inside it. `main(["--check"]) == 0`. With `p` missing: `main(["--check", "--path", p]) == 1`; `main(["--write", "--path", p]) == 0`; the bytes then equal `render(build_rng_golden())`; `main(["--write", "--path", p]) == 0` again (no-op). Write `b"{}\n"` to `p`: `main(["--path", p]) == 1`; `main(["--write", "--path", p]) == 1` and the file still equals `b"{}\n"`; `main(["--write", "--force", "--path", p]) == 0` and the bytes equal the rendered golden |

## 7. Configuration and CI

**`pyproject.toml`**: replace the `[tool.ruff.lint]` section and add the following. Change the dev extra pin to `ruff==0.17.1` (matches the gate and CI); everything else stays unchanged.

```toml
[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "RUF", "TID"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"random".msg = "use psicotest.rng"

[tool.ruff.lint.isort]
known-first-party = ["psicotest"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["F401"]
```

**`tests/_bootstrap.py`**: computes `SRC = str(Path(__file__).resolve().parent.parent / "src")` and inserts it at `sys.path[0]` if it is not already present. Nothing else.

**`.github/workflows/ci.yml`** (DESIGN §4.6, which is the source of criterion S4):

- **`test` job**:
  - `strategy.fail-fast: false`.
  - Matrix: `os: [ubuntu-24.04, ubuntu-24.04-arm]` × `python-version: ["3.11", "3.12", "3.13"]`, with `runs-on: ${{ matrix.os }}`.
  - Steps: checkout, then `actions/setup-python@v5`. No `pip install`, because the runtime is stdlib only.
  - Two steps with `env: PYTHONPATH: src`: `PYTHONHASHSEED=0 python3 -m unittest discover -s tests -v`, then `PYTHONHASHSEED=1 python3 -m unittest discover -s tests -v`.
  - The goldens are checked in every cell (2 architectures × 3 Python versions × 2 hash seeds). This is how byte-identity across the matrix is verified.
- **`lint` job**: `ubuntu-24.04`, Python 3.11, `pip install ruff==0.17.1`, `ruff check .`, `ruff format --check .`. Run `ruff format .` locally before pushing.
- No network access beyond 127.0.0.1. T1 tests need none.

## 8. Implementation order

1. Write `rng.py`, `spec.py`, `_bootstrap.py`, the tool, and the pyproject/CI changes.
2. Run `PYTHONPATH=src python3 tools/gen_golden.py --write` to create `tests/golden/rng.json`.
3. Check the anchors (splitmix64 seed 0 ×4 and the three FIPS SHA-256 vectors) before going further. If a splitmix64 anchor fails, compare the implementation with DESIGN §4.1 line by line. Do not edit an anchor. If the mismatch persists, report it.
4. Copy these values from the generated file into `test_rng.py` as `PIN_*` literals:
   - `PIN_SEED1_FIRST`, `PIN_SEEDMAX_FIRST` (hex)
   - `PIN_BELOW7`, `PIN_SHUFFLE10`, `PIN_SAMPLE5`, `PIN_FORK4`, `PIN_COUNTS7`
   - `PIN_CHI2` (decimal, 6+ places)

   List these literals in the PR description.
5. Write the remaining tests and run `ruff format .`.

## 9. Acceptance

- `ruff check .` reports nothing.
- `PYTHONPATH=src python3 -m unittest discover -s tests` passes on Python 3.11, under both `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1`. The full suite is all tests in §6 plus the existing `test_scaffold`.
- `PYTHONPATH=src python3 tools/gen_golden.py --check` exits 0.
- No `#` comments or docstrings in any T1 file, no third-party imports, and no item goldens, generators, or other non-T1 modules.
