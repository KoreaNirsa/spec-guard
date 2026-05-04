from __future__ import annotations

import argparse
from pathlib import Path

from tools.runner import run_pipeline


ROOT = Path.cwd()


def init_project(args: argparse.Namespace) -> int:
    for directory in ("specs", "examples"):
        (ROOT / directory).mkdir(exist_ok=True)
    print("SpecGuard project folders are ready.")
    return 0


def run(args: argparse.Namespace) -> int:
    result = run_pipeline(Path(args.path))
    result.print()
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="specguard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.set_defaults(func=init_project)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("path", nargs="?", default="specs")
    run_parser.set_defaults(func=run)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
