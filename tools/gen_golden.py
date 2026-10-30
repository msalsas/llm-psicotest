import argparse
import importlib
import json
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "tests" / "golden" / "rng.json"


def _rng():
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    return importlib.import_module("psicotest.rng")


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
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)
    data = render(build_rng_golden())
    if args.write:
        if args.path.exists():
            if args.path.read_bytes() == data:
                return 0
            if not args.force:
                print(f"refusing to overwrite different file: {args.path}", file=sys.stderr)
                return 1
        args.path.parent.mkdir(parents=True, exist_ok=True)
        args.path.write_bytes(data)
        return 0
    if not args.path.exists():
        print(f"golden file missing: {args.path}", file=sys.stderr)
        return 1
    if args.path.read_bytes() != data:
        print(f"golden file out of date: {args.path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
