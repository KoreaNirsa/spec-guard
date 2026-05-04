from __future__ import annotations

import argparse
import getpass
import subprocess
from pathlib import Path

from tools.discovery_engine import DISCOVERY_PROMPTS, answers_from_args, collect_answers, collect_llm_answers, initialize_specs
from tools.llm_client import (
    LLMConfigError,
    LLMRequestError,
    LLMSettings,
    build_llm_client,
    clear_llm_settings,
    codex_available,
    config_path,
    load_llm_settings,
    save_llm_settings,
)
from tools.runner import run_pipeline
from tools.ux import print_banner, print_hint, print_section


ROOT = Path.cwd()
DISCOVERY_DEFAULTS = {key: default for key, _prompt, default in DISCOVERY_PROMPTS}


class SpecGuardHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


def init_project(args: argparse.Namespace) -> int:
    print_banner("Discovery creates draft specs under specs/.")
    llm_client = _build_llm_client(args, purpose="init", allow_setup=not args.non_interactive)
    if _requires_llm(args) and llm_client is None:
        return 1

    if llm_client is not None and not args.non_interactive:
        print_section("LLM Discovery")
        print_hint("The assistant will stream questions in real time. Type 'done' or 'complete' to finish.")
        answers = collect_llm_answers(args, llm_client)
    else:
        print_section("Discovery")
        answers = answers_from_args(args) if args.non_interactive else collect_answers(args)

    print_section("Spec Draft")
    try:
        result = initialize_specs(ROOT, answers, force=args.force, llm_client=llm_client)
    except LLMRequestError as exc:
        _print_llm_failure(exc)
        return 1
    result.print()
    return 0 if result.ok else 1


def run(args: argparse.Namespace) -> int:
    print_banner("Run Technical Design, Grill Me, Test, Contract, and Implementation Outputs.")
    llm_client = _build_llm_client(args, purpose="run", allow_setup=False)
    if _requires_llm(args) and llm_client is None:
        return 1

    print_section("Pipeline")
    if args.force:
        print_hint("Regenerating derived artifacts where SpecGuard owns the output.")
    else:
        print_hint("Missing artifacts are generated; stale tests and contracts are refreshed from the spec.")

    try:
        result = run_pipeline(Path(args.path), llm_client=llm_client, force=args.force)
    except LLMRequestError as exc:
        _print_llm_failure(exc)
        return 1
    result.print()
    return 0 if result.ok else 1


def auth(args: argparse.Namespace) -> int:
    if args.auth_command == "status":
        print_banner("LLM provider status.")
        settings = load_llm_settings(ROOT)
        if settings is None:
            print("[WARN] No LLM provider configured.")
            print(f"- Config path: {config_path(ROOT)}")
            print("- Run: python -m cli.specguard auth setup")
            return 1
        print("[PASS] SpecGuard LLM configuration")
        print(f"- Mode: {settings.mode}")
        print(f"- Model: {settings.model or '(provider default)'}")
        if settings.mode == "openai":
            print(f"- API key source: {settings.api_key_env if not settings.api_key else 'local config'}")
            print(f"- Endpoint: {settings.endpoint}")
        if settings.mode == "codex":
            print(f"- Codex command: {settings.codex_command}")
            print(f"- Codex available: {'yes' if codex_available(settings.codex_command) else 'no'}")
        return 0

    if args.auth_command == "logout":
        print_banner("Reset SpecGuard LLM provider configuration.")
        settings = load_llm_settings(ROOT)
        removed = clear_llm_settings(ROOT)
        print("[PASS] Removed local SpecGuard LLM configuration." if removed else "[WARN] No local SpecGuard LLM configuration was found.")
        if args.codex:
            command = "codex"
            if settings and settings.mode == "codex":
                command = settings.codex_command
            subprocess.run([command, "logout"], cwd=ROOT, check=False)
        return 0

    if args.auth_command == "setup":
        print_banner("Configure SpecGuard LLM provider.")
        return _setup_llm(args)

    print("[FAIL] Unknown auth command.")
    return 1


def _requires_llm(args: argparse.Namespace) -> bool:
    return not getattr(args, "no_llm", False)


def _build_llm_client(args: argparse.Namespace, *, purpose: str, allow_setup: bool) -> object | None:
    if getattr(args, "no_llm", False):
        return None

    mode = getattr(args, "llm_mode", None)
    try:
        return build_llm_client(ROOT, mode=mode, model=getattr(args, "llm_model", None))
    except LLMConfigError as exc:
        if allow_setup and _prompt_yes_no("No LLM provider is configured. Set it up now?", default=True):
            setup_args = argparse.Namespace(
                mode=None,
                model=getattr(args, "llm_model", None),
                api_key=None,
                api_key_env="OPENAI_API_KEY",
                endpoint="https://api.openai.com/v1/responses",
                codex_command="codex",
                codex_profile=None,
                skip_login=False,
            )
            if _setup_llm(setup_args) == 0:
                try:
                    return build_llm_client(ROOT, mode=mode, model=getattr(args, "llm_model", None))
                except LLMConfigError as retry_exc:
                    exc = retry_exc
        print("[FAIL] SpecGuard LLM configuration")
        print(f"- {exc}")
        print("- Run: python -m cli.specguard auth setup")
        if purpose == "run":
            print("- Use --no-llm only for local heuristic checks or CI examples.")
        return None


def _setup_llm(args: argparse.Namespace) -> int:
    mode = args.mode
    if not mode:
        default_mode = "codex" if codex_available(args.codex_command) else "openai"
        mode = _prompt("Provider mode (codex/openai)", default_mode).lower()
    if mode not in {"codex", "openai"}:
        print("[FAIL] Unsupported provider mode. Use codex or openai.")
        return 1

    if mode == "codex":
        model = args.model or _prompt("Model (blank keeps Codex default)", "")
        model = model or None
        codex_command = args.codex_command or "codex"
        if not codex_available(codex_command):
            print("[FAIL] Local Codex CLI was not found.")
            print("- Install Codex, or choose OpenAI Platform mode: python -m cli.specguard auth setup --mode openai")
            return 1
        settings = LLMSettings(mode="codex", model=model, codex_command=codex_command, codex_profile=args.codex_profile)
        path = save_llm_settings(ROOT, settings)
        print(f"[PASS] Saved local Codex provider config: {path}")
        if not args.skip_login and _prompt_yes_no("Run `codex login` now?", default=False):
            subprocess.run([codex_command, "login"], cwd=ROOT, check=False)
        return 0

    model = args.model or _prompt("Model", "gpt-5.1")
    api_key = args.api_key
    if api_key is None:
        entered = getpass.getpass("OpenAI API key (leave empty to use environment variable): ").strip()
        api_key = entered or None
    settings = LLMSettings(
        mode="openai",
        model=model,
        endpoint=args.endpoint,
        api_key=api_key,
        api_key_env=args.api_key_env,
    )
    path = save_llm_settings(ROOT, settings)
    print(f"[PASS] Saved OpenAI Platform provider config: {path}")
    if not api_key:
        print(f"- Set {args.api_key_env} before running LLM workflows.")
    return 0


def _prompt(label: str, default: str) -> str:
    try:
        value = input(f"{label} [{default}]: ").strip()
    except EOFError:
        value = ""
    return value or default


def _prompt_yes_no(label: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    try:
        value = input(f"{label} [{suffix}]: ").strip().lower()
    except EOFError:
        value = ""
    if not value:
        return default
    return value in {"y", "yes"}


def _print_llm_failure(exc: Exception) -> None:
    print("[FAIL] LLM workflow failed")
    print(f"- {exc}")
    print("- Check provider status: python -m cli.specguard auth status")
    print("- Reconfigure provider: python -m cli.specguard auth setup")


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
    init_parser.add_argument("--llm", action="store_true", help="Use configured LLM mode. Kept for compatibility; LLM is the default.")
    init_parser.add_argument("--no-llm", action="store_true", help="Use local deterministic Discovery without LLM")
    init_parser.add_argument("--llm-mode", choices=["codex", "openai"], help="Override the configured LLM provider mode")
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
    run_parser.add_argument("--llm", action="store_true", help="Use configured LLM mode. Kept for compatibility; LLM is the default.")
    run_parser.add_argument("--no-llm", action="store_true", help="Use local deterministic generators and heuristic Grill Me")
    run_parser.add_argument("--llm-mode", choices=["codex", "openai"], help="Override the configured LLM provider mode")
    run_parser.add_argument("--llm-model", help="Override SPECGUARD_LLM_MODEL for this run")
    run_parser.set_defaults(func=run)

    auth_parser = subparsers.add_parser("auth", formatter_class=SpecGuardHelpFormatter)
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)

    auth_setup = auth_subparsers.add_parser("setup", formatter_class=SpecGuardHelpFormatter)
    auth_setup.add_argument("--mode", choices=["codex", "openai"], help="LLM provider mode")
    auth_setup.add_argument("--model", help="Model name for the selected provider")
    auth_setup.add_argument("--api-key", help="Store an OpenAI API key in local ignored config")
    auth_setup.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable for the OpenAI API key")
    auth_setup.add_argument("--endpoint", default="https://api.openai.com/v1/responses", help="OpenAI Responses API endpoint")
    auth_setup.add_argument("--codex-command", default="codex", help="Local Codex CLI command")
    auth_setup.add_argument("--codex-profile", help="Codex CLI profile")
    auth_setup.add_argument("--skip-login", action="store_true", help="Do not offer to run codex login during setup")
    auth_setup.set_defaults(func=auth)

    auth_status = auth_subparsers.add_parser("status", formatter_class=SpecGuardHelpFormatter)
    auth_status.set_defaults(func=auth)

    auth_logout = auth_subparsers.add_parser("logout", formatter_class=SpecGuardHelpFormatter)
    auth_logout.add_argument("--codex", action="store_true", help="Also run codex logout")
    auth_logout.set_defaults(func=auth)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
