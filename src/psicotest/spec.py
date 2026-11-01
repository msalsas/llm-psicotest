import dataclasses
import json
import re
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction

from psicotest.rng import Rng

VARIANTS = ("base", "clean", "relabel", "pc1", "pc2")
GENERATOR_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
FAMILY_RE = re.compile(r"^[A-Z][A-Z0-9]*$")
ANIMAL_RE = re.compile(r"^[a-z]+$")


@dataclasses.dataclass(frozen=True)
class GenContext:
    variant: str
    animal: str | None
    surface_rng: Rng


@dataclasses.dataclass(frozen=True)
class Item:
    item_id: str
    battery_version: str
    slot: str
    family: str
    generator: str
    generator_version: int
    knobs: Mapping[str, object]
    variant: str
    instance_seed: int
    surface_seed: int
    animal: str | None
    prompt_en: str
    key: Mapping[str, object]
    meta: Mapping[str, object]
    answer_kind: str
    capability: bool


@dataclasses.dataclass(frozen=True)
class CheckResult:
    outcome: str
    score: int
    value: object
    flags: tuple[str, ...]
    detail: str


@dataclasses.dataclass(frozen=True)
class Turn:
    turn: int
    kind: str
    slot: str | None
    prompt_en: str
    item: Item | None
    rules_active: tuple[str, ...]
    r3_trigger: bool


@dataclasses.dataclass(frozen=True)
class GeneratorSpec:
    name: str
    version: int
    family: str
    variants: tuple[str, ...] = ("base",)

    def __post_init__(self) -> None:
        if not GENERATOR_NAME_RE.match(self.name):
            raise ValueError("invalid name")
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise ValueError("invalid version")
        if self.version < 1:
            raise ValueError("invalid version")
        if not FAMILY_RE.match(self.family):
            raise ValueError("invalid family")
        if not isinstance(self.variants, tuple):
            raise ValueError("invalid variants")
        if not self.variants:
            raise ValueError("invalid variants")
        if self.variants[0] != "base":
            raise ValueError("invalid variants")
        if len(set(self.variants)) != len(self.variants):
            raise ValueError("invalid variants")
        if any(v not in VARIANTS for v in self.variants):
            raise ValueError("invalid variants")

    def key(self, seed: int, variant: str = "base", animal: str | None = None) -> str:
        if variant not in self.variants:
            raise ValueError("unknown variant")
        return item_key(self.name, self.version, seed, variant, animal)


def item_key(
    generator: str,
    generator_version: int,
    seed: int,
    variant: str,
    animal: str | None = None,
) -> str:
    if not GENERATOR_NAME_RE.match(generator):
        raise ValueError("invalid generator")
    if isinstance(generator_version, bool) or not isinstance(generator_version, int):
        raise ValueError("invalid generator_version")
    if generator_version < 1:
        raise ValueError("invalid generator_version")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("invalid seed")
    if seed < 0:
        raise ValueError("invalid seed")
    if variant not in VARIANTS:
        raise ValueError("invalid variant")
    if animal is not None and not ANIMAL_RE.match(animal):
        raise ValueError("invalid animal")
    key = f"{generator}@{generator_version}/{seed}/{variant}"
    if animal is not None:
        key += f"/animal={animal}"
    return key


def canonical_json(obj) -> bytes:
    return json.dumps(
        _canon(obj),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canon(o):
    if o is None or isinstance(o, (bool, int, str)):
        return o
    if isinstance(o, Decimal):
        if not o.is_finite():
            raise ValueError("non-finite decimal")
        return str(o)
    if isinstance(o, Fraction):
        return f"{o.numerator}/{o.denominator}"
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return {f.name: _canon(getattr(o, f.name)) for f in dataclasses.fields(o)}
    if isinstance(o, Mapping):
        for k in o:
            if not isinstance(k, str):
                raise TypeError("mapping keys must be str")
        return {k: _canon(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_canon(x) for x in o]
    raise TypeError(f"unsupported type: {type(o).__name__}")
