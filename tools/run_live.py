#!/usr/bin/env python3
"""
Live-server test for psicotest runner.

Usage:
    python tools/run_live.py --base-url URL --model NAME --seed N [--order A|B]

Requires PSICOTEST_API_KEY in environment.
"""

import argparse
import os
import sys

sys.path.insert(0, "src")

from psicotest.runner import HTTPTransport, run_battery


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--order", default="A", choices=["A", "B"])
    parser.add_argument("--out", default="runs")
    args = parser.parse_args()

    key = os.environ.get("PSICOTEST_API_KEY")
    if not key:
        print("PSICOTEST_API_KEY not set", file=sys.stderr)
        return 3

    transport = HTTPTransport(timeout=120)
    return run_battery(
        transport=transport,
        base_url=args.base_url,
        model=args.model,
        api_key=key,
        seed=args.seed,
        order=args.order,
        out_dir=args.out,
    )


if __name__ == "__main__":
    sys.exit(main())
