import argparse
import os
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="psicotest", description="llm-psicotest")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run battery")
    run_parser.add_argument("--base-url", required=True)
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--seed", type=int, required=True)
    run_parser.add_argument("--order", default="A", choices=["A", "B"])
    run_parser.add_argument("--out", default="runs")
    run_parser.add_argument("--max-tokens", type=int, default=6144)
    run_parser.add_argument("--timeout", type=float, default=240)
    run_parser.add_argument("--key-env", default="PSICOTEST_API_KEY")
    run_parser.add_argument("--auth", default="bearer", choices=["bearer", "x-api-key"])
    run_parser.add_argument("--resume", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "run":
        from psicotest.runner import HTTPTransport, run_battery
        from psicotest.runner.driver import EXIT_AUTH

        key = os.environ.get(args.key_env)
        if not key:
            print(f"{args.key_env} not set", file=sys.stderr)
            return EXIT_AUTH

        transport = HTTPTransport(timeout=args.timeout)
        return run_battery(
            transport=transport,
            base_url=args.base_url,
            model=args.model,
            api_key=key,
            seed=args.seed,
            order=args.order,
            out_dir=args.out,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            auth_scheme=args.auth,
            key_env=args.key_env,
            resume=args.resume,
        )

    parser.print_help()
    return 0
