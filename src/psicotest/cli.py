import argparse


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="psicotest", description="llm-psicotest")
    parser.parse_args(argv)
    return 0
