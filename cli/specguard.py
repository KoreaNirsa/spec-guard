from __future__ import annotations

import argparse
from pathlib import Path

from tools.discovery_engine import answers_from_args, collect_answers, initialize_specs
from tools.runner import run_pipeline


ROOT = Path.cwd()


def init_project(args: argparse.Namespace) -> int:
    answers = answers_from_args(args) if args.non_interactive else collect_answers(args)
    result = initialize_specs(ROOT, answers, force=args.force)
    result.print()
    return 0 if result.ok else 1


def run(args: argparse.Namespace) -> int:
    result = run_pipeline(Path(args.path))
    result.print()
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="specguard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("feature", nargs="?", help="Feature name or comma-separated feature names")
    init_parser.add_argument("--non-interactive", action="store_true", help="Generate specs from CLI values and defaults")
    init_parser.add_argument("--force", action="store_true", help="Overwrite generated discovery and spec drafts")
    init_parser.add_argument("--problem")
    init_parser.add_argument("--users")
    init_parser.add_argument("--outcomes")
    init_parser.add_argument("--constraints")
    init_parser.add_argument("--flows")
    init_parser.add_argument("--data")
    init_parser.add_argument("--dependencies")
    init_parser.add_argument("--risks")
    init_parser.add_argument("--out-of-scope", dest="out_of_scope")
    init_parser.add_argument("--acceptance")
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
