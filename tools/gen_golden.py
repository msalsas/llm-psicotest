import argparse
import hashlib
import importlib
import json
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "tests" / "golden" / "rng.json"
DEFAULT_ITEMS_PATH = ROOT / "tests" / "golden" / "items_v2.json"


def _module(name):
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    return importlib.import_module(name)


def _rng():
    return _module("psicotest.rng")


def build_items_golden() -> dict:
    registry = _module("psicotest.generators.registry")
    canonical_json = _module("psicotest.spec").canonical_json
    return {
        key: hashlib.sha256(canonical_json(item)).hexdigest()
        for key, item in registry.golden_items().items()
    }


def merge_items(old: dict, new: dict) -> dict:
    for key, digest in new.items():
        if key in old and old[key] != digest:
            raise ValueError(f"same-version key changed: {key}")
    versions = {}
    for key in new:
        name, _, rest = key.partition("@")
        versions.setdefault(name, set()).add(rest.split("/", 1)[0])
    for key in old:
        if key not in new:
            name, _, rest = key.partition("@")
            old_version = int(rest.split("/", 1)[0])
            if not any(int(v) > old_version for v in versions.get(name, ())):
                raise ValueError(f"same-version key dropped: {key}")
    return dict(new)


def render_items(data: dict) -> bytes:
    return _module("psicotest.spec").canonical_json(data) + b"\n"


def _may_replace(path: Path, new: dict) -> bool:
    try:
        merge_items(json.loads(path.read_text("utf-8")), new)
    except ValueError:
        return False
    return True


def build_rng_golden() -> dict:
    rng = _rng()
    Rng = rng.Rng
    below7 = []
    r = Rng(42)
    for _ in range(16):
        below7.append(r.below(7))
    counts = [0] * 7
    r = Rng(7)
    for _ in range(70000):
        counts[r.below(7)] += 1
    chi2 = Fraction(sum((c - 10000) ** 2 for c in counts), 10000)
    parts_list = [
        ["psicotest", "v1", "S01", "gen_state_boxes", 1, 10001, "instance"],
        ["psicotest", "v1", "S01", "gen_state_boxes", 1, 10001, "surface"],
        ["psicotest", "v1", 10001, "A", 17, "animal"],
        ["req", "v1", 10001, "A", 2],
        ["ñandú", 0],
        [""],
        ["abc"],
    ]
    derive = [{"parts": p, "value": rng.derive_seed(*p)} for p in parts_list]
    fork_r = Rng(42).fork("surface")
    fork4 = [fork_r.next_u64() for _ in range(4)]
    next_u64 = {}
    for seed in (0, 1, 18446744073709551615):
        r = Rng(seed)
        next_u64[str(seed)] = [r.next_u64() for _ in range(16)]
    sample5 = Rng(42).sample(range(100), 5)
    shuffle_lst = list(range(10))
    Rng(42).shuffle(shuffle_lst)
    return {
        "below7_seed42": below7,
        "chi2_below7_seed7_n70000": f"{chi2.numerator}/{chi2.denominator}",
        "counts_below7_seed7_n70000": counts,
        "derive_seed": derive,
        "fork_surface_seed42": fork4,
        "next_u64": next_u64,
        "sample100_5_seed42": sample5,
        "schema": 1,
        "shuffle10_seed42": shuffle_lst,
    }


def render(data: dict) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--items", action="store_true")
    parser.add_argument("--path", type=Path, default=None)
    args = parser.parse_args(argv)
    path = args.path or (DEFAULT_ITEMS_PATH if args.items else DEFAULT_PATH)
    new = build_items_golden() if args.items else None
    data = render_items(new) if args.items else render(build_rng_golden())
    if args.write:
        if path.exists():
            if path.read_bytes() == data:
                return 0
            if not args.force and not (args.items and _may_replace(path, new)):
                print(f"refusing to overwrite different file: {path}", file=sys.stderr)
                return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return 0
    if not path.exists():
        print(f"golden file missing: {path}", file=sys.stderr)
        return 1
    if path.read_bytes() != data:
        print(f"golden file out of date: {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
