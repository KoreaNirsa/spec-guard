from __future__ import annotations

import argparse
from pathlib import Path

from tools.discovery_engine import DISCOVERY_PROMPTS, answers_from_args, collect_answers, collect_llm_answers, initialize_specs
from tools.llm_client import LLMConfigError, OpenAIResponsesClient
from tools.runner import run_pipeline
from tools.ux import print_banner, print_hint, print_section


ROOT = Path.cwd()
DISCOVERY_DEFAULTS = {key: default for key, _prompt, default in DISCOVERY_PROMPTS}


class SpecGuardHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


def init_project(args: argparse.Namespace) -> int:
    print_banner("Discovery creates draft specs under specs/.")
    llm_client = _build_llm_client(args)
    if args.llm and llm_client is None:
        return 1

    if args.llm and not args.non_interactive:
        print_section("LLM Discovery")
        print_hint("The assistant will stream questions in real time. Type 'done' or '완료' to finish.")
        answers = collect_llm_answers(args, llm_client)
    else:
        print_section("Discovery")
        answers = answers_from_args(args) if args.non_interactive else collect_answers(args)

    print_section("Spec Draft")
    result = initialize_specs(ROOT, answers, force=args.force, llm_client=llm_client)
    result.print()
    return 0 if result.ok else 1


def run(args: argparse.Namespace) -> int:
    print_banner("Run Technical Design, Grill Me, Test, Contract, and Implementation Outputs.")
    llm_client = _build_llm_client(args)
    if args.llm and llm_client is None:
        return 1
    print_section("Pipeline")
    if args.force:
        print_hint("Regenerating derived artifacts where SpecGuard owns the output.")
    else:
        print_hint("Missing artifacts are generated; stale tests and contracts are refreshed from the spec.")
    result = run_pipeline(Path(args.path), llm_client=llm_client, force=args.force)
    result.print()
    return 0 if result.ok else 1


def _build_llm_client(args: argparse.Namespace) -> OpenAIResponsesClient | None:
    if not getattr(args, "llm", False):
        return None
    try:
        return OpenAIResponsesClient.from_env(model=getattr(args, "llm_model", None))
    except LLMConfigError as exc:
        print("[FAIL] SpecGuard LLM configuration")
        print(f"- {exc}")
        print("- Set OPENAI_API_KEY and optionally SPECGUARD_LLM_MODEL, or pass --llm-model.")
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="specguard",
        description="SpecGuard refines specs into validated implementation-ready artifacts.",
        formatter_class=SpecGuardHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        description=(
            "Run Discovery and generate draft specs under specs/.\n"
            "Interactive mode shows a default for every question. Press Enter to accept it."
        ),
        epilog=(
            "Examples:\n"
            "  specguard init\n"
            "  specguard init billing-export\n"
            "  specguard init todo-api,billing-export --non-interactive"
        ),
        formatter_class=SpecGuardHelpFormatter,
    )
    init_parser.add_argument(
        "feature",
        nargs="?",
        default=DISCOVERY_DEFAULTS["feature_names"],
        help="Feature name or comma-separated feature names. In interactive mode, pressing Enter keeps this default.",
    )
    init_parser.add_argument("--non-interactive", action="store_true", help="Generate specs from CLI values and defaults")
    init_parser.add_argument("--force", action="store_true", help="Overwrite generated discovery and spec drafts")
    init_parser.add_argument("--llm", action="store_true", help="Use streaming LLM Discovery and draft spec.md from the conversation")
    init_parser.add_argument("--llm-model", help="Override SPECGUARD_LLM_MODEL for this run")
    init_parser.add_argument("--problem", default=DISCOVERY_DEFAULTS["problem"], help="Default answer for the problem Discovery question")
    init_parser.add_argument("--users", default=DISCOVERY_DEFAULTS["users"], help="Default answer for the users Discovery question")
    init_parser.add_argument("--outcomes", default=DISCOVERY_DEFAULTS["outcomes"], help="Default answer for the outcomes Discovery question")
    init_parser.add_argument("--constraints", default=DISCOVERY_DEFAULTS["constraints"], help="Default answer for the constraints Discovery question")
    init_parser.add_argument("--flows", default=DISCOVERY_DEFAULTS["flows"], help="Default answer for the flows Discovery question")
    init_parser.add_argument("--data", default=DISCOVERY_DEFAULTS["data"], help="Default answer for the data Discovery question")
    init_parser.add_argument("--dependencies", default=DISCOVERY_DEFAULTS["dependencies"], help="Default answer for the dependencies Discovery question")
    init_parser.add_argument("--risks", default=DISCOVERY_DEFAULTS["risks"], help="Default answer for the risks Discovery question")
    init_parser.add_argument(
        "--out-of-scope",
        dest="out_of_scope",
        default=DISCOVERY_DEFAULTS["out_of_scope"],
        help="Default answer for the out-of-scope Discovery question",
    )
    init_parser.add_argument("--acceptance", default=DISCOVERY_DEFAULTS["acceptance"], help="Default answer for the acceptance Discovery question")
    init_parser.set_defaults(func=init_project)

    run_parser = subparsers.add_parser("run", formatter_class=SpecGuardHelpFormatter)
    run_parser.add_argument("path", nargs="?", default="specs")
    run_parser.add_argument("--force", action="store_true", help="Regenerate derived artifacts instead of reusing existing files")
    run_parser.add_argument("--llm", action="store_true", help="Use the configured LLM for Technical Design and Grill Me")
    run_parser.add_argument("--llm-model", help="Override SPECGUARD_LLM_MODEL for this run")
    run_parser.set_defaults(func=run)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
