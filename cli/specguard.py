from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import threading
import time
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
from tools.post_run import (
    apply_spec_revision,
    blocked_feature_reports,
    feature_readiness_reports,
    generate_spec_revision,
    readiness_report_stale_reason,
    render_readiness_summary,
    validate_spec_revision_intent,
    write_proposed_spec_revision,
)
from tools.runner import run_pipeline
from tools.strict_e2e import run_strict_e2e_pipeline
from tools.ux import bold, green, menu_item, print_banner, print_error, print_hint, print_section, print_success, print_warning, yellow


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
        print_hint("Questions appear instantly. The configured LLM generates the draft spec after your answers.")
        print_hint("Press Enter to accept defaults, or type 'done' / 'complete' to finish early.")
        try:
            answers = collect_llm_answers(args, llm_client)
        except LLMRequestError as exc:
            _print_llm_failure(exc)
            return 1
    else:
        print_section("Discovery")
        answers = answers_from_args(args) if args.non_interactive else collect_answers(args)

    print_section("Spec Draft")
    try:
        result = _run_with_progress(
            "Generating spec draft",
            lambda: initialize_specs(ROOT, answers, force=args.force, llm_client=llm_client),
        )
    except LLMRequestError as exc:
        _print_llm_failure(exc)
        return 1
    result.print()
    return 0 if result.ok else 1


def run(args: argparse.Namespace) -> int:
    print_banner("Run Technical Design, SpecGuard Review, Test, Contract, and Implementation Handoff.")
    llm_client = _build_llm_client(args, purpose="run", allow_setup=False)
    if _requires_llm(args) and llm_client is None:
        return 1
    strict_e2e = getattr(args, "strict_e2e", False)
    strict_max_iterations = getattr(args, "strict_max_iterations", 3)
    if strict_e2e and llm_client is None:
        print_error("[FAIL] Strict E2E requires an LLM provider.")
        print("- Re-run without --no-llm, or configure one: python -m cli.specguard auth setup")
        return 1

    print_section("Pipeline")
    if args.force:
        print_hint("Regenerating derived artifacts where SpecGuard owns the output.")
    elif strict_e2e:
        print_hint(f"Running strict E2E with at most {strict_max_iterations} verification iteration(s).")
    else:
        print_hint("Missing artifacts are generated; stale tests and contracts are refreshed from the spec.")

    try:
        if strict_e2e:
            result = _run_with_progress(
                "Running strict E2E pipeline",
                lambda: run_strict_e2e_pipeline(
                    Path(args.path),
                    llm_client,
                    force=args.force,
                    max_iterations=strict_max_iterations,
                ),
            )
        else:
            result = _run_with_progress(
                "Running pipeline",
                lambda: run_pipeline(Path(args.path), llm_client=llm_client, force=args.force),
            )
    except LLMRequestError as exc:
        _print_llm_failure(exc)
        return 1
    result.print()

    if not strict_e2e and _should_offer_follow_up(args):
        try:
            result = _run_follow_up_loop(args, llm_client, result)
        except LLMRequestError as exc:
            _print_llm_failure(exc)
            return 1
    return 0 if result.ok else 1


def auth(args: argparse.Namespace) -> int:
    if args.auth_command == "status":
        print_banner("LLM provider status.")
        settings = load_llm_settings(ROOT)
        if settings is None:
            print_warning("[WARN] No LLM provider configured.")
            print(f"- Config path: {config_path(ROOT)}")
            print("- Run: python -m cli.specguard auth setup")
            return 1
        print_success("[PASS] SpecGuard LLM configuration")
        print(f"- Mode: {settings.mode}")
        print(f"- Model: {settings.model or '(provider default)'}")
        print(f"- Timeout: {settings.timeout}s")
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
        if removed:
            print_success("[PASS] Removed local SpecGuard LLM configuration.")
        else:
            print_warning("[WARN] No local SpecGuard LLM configuration was found.")
        if args.codex:
            command = "codex"
            if settings and settings.mode == "codex":
                command = settings.codex_command
            _run_codex_account_command(command, "logout")
        return 0

    if args.auth_command == "setup":
        print_banner("Configure SpecGuard LLM provider.")
        return _setup_llm(args)

    print_error("[FAIL] Unknown auth command.")
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
                timeout=180,
                codex_command="codex",
                codex_profile=None,
                skip_login=False,
            )
            if _setup_llm(setup_args) == 0:
                try:
                    return build_llm_client(ROOT, mode=mode, model=getattr(args, "llm_model", None))
                except LLMConfigError as retry_exc:
                    exc = retry_exc
        print_error("[FAIL] SpecGuard LLM configuration")
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
        print_error("[FAIL] Unsupported provider mode. Use codex or openai.")
        return 1

    if mode == "codex":
        model = args.model or _prompt("Model", "gpt-5.4")
        timeout = args.timeout or 180
        codex_command = args.codex_command or "codex"
        if not codex_available(codex_command):
            print_error("[FAIL] Local Codex CLI was not found.")
            print("- Install Codex, or choose OpenAI Platform mode: python -m cli.specguard auth setup --mode openai")
            return 1
        settings = LLMSettings(
            mode="codex",
            model=model,
            timeout=timeout,
            codex_command=codex_command,
            codex_profile=args.codex_profile,
        )
        path = save_llm_settings(ROOT, settings)
        print_success(f"[PASS] Saved local Codex provider config: {path}")
        if not args.skip_login and _prompt_yes_no("Run `codex login` now?", default=False):
            _run_codex_account_command(codex_command, "login")
        return 0

    model = args.model or _prompt("Model", "gpt-5.1")
    timeout = args.timeout or 180
    api_key = args.api_key
    if api_key is None and not os.getenv(args.api_key_env):
        entered = getpass.getpass("OpenAI API key (leave empty to use environment variable): ").strip()
        api_key = entered or None
    settings = LLMSettings(
        mode="openai",
        model=model,
        timeout=timeout,
        endpoint=args.endpoint,
        api_key=api_key,
        api_key_env=args.api_key_env,
    )
    path = save_llm_settings(ROOT, settings)
    print_success(f"[PASS] Saved OpenAI Platform provider config: {path}")
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


def _run_codex_account_command(codex_command: str, action: str) -> None:
    resolved = _resolve_local_command(codex_command)
    if resolved is None:
        print_warning(f"[WARN] Codex command was not found, so `codex {action}` was skipped.")
        print("- SpecGuard provider config is still saved. If Codex is already logged in, run/init can continue.")
        print("- Otherwise run `codex login` manually, or set --codex-command to the full executable path.")
        return
    try:
        subprocess.run([resolved, action], cwd=ROOT, check=False)
    except FileNotFoundError:
        print_warning(f"[WARN] Codex command could not be launched, so `codex {action}` was skipped.")
        print("- SpecGuard provider config is still saved. If Codex is already logged in, run/init can continue.")
        print("- Otherwise run `codex login` manually, or set --codex-command to the full executable path.")


def _resolve_local_command(command: str) -> str | None:
    if Path(command).exists():
        return command
    return shutil.which(command) or shutil.which(f"{command}.cmd")


def _should_offer_follow_up(args: argparse.Namespace) -> bool:
    if getattr(args, "no_follow_up", False):
        return False
    if getattr(args, "follow_up", False):
        return True
    if _is_ci_environment():
        return False
    if sys.stdin.isatty() and sys.stdout.isatty():
        return True
    return _has_terminal_environment_hint()


def _is_ci_environment() -> bool:
    return os.getenv("CI", "").lower() in {"1", "true", "yes"}


def _has_terminal_environment_hint() -> bool:
    if os.getenv("MSYSTEM") or os.getenv("MINGW_PREFIX"):
        return True
    term = os.getenv("TERM", "")
    return bool(term and term.lower() != "dumb")


def _run_follow_up_loop(args: argparse.Namespace, llm_client: object | None, result: object) -> object:
    path = Path(args.path)
    while True:
        print_section("Continue")
        print(menu_item("[1] View Readiness Findings"))
        print(menu_item("[2] Regenerate spec from Readiness Findings (auto-runs SpecGuard Review after)"))
        print(menu_item("[q] Exit"))
        try:
            choice = input("Choose action: ").strip().lower()
        except EOFError:
            print("")
            print_warning("[WARN] Input stream closed. Leaving the follow-up menu.")
            return result

        if choice == "":
            print_hint("No action selected. Choose 1, 2, or q to exit.")
            continue
        if choice in {"q", "quit", "exit"}:
            return result
        if choice in {"1", "r", "review"}:
            _print_readiness_review(path)
            continue
        if choice in {"2", "f", "fix", "revise"}:
            result = _revise_spec_from_readiness(path, args, llm_client, result)
            continue

        print_warning("[WARN] Choose 1, 2, or q to exit.")


def _print_readiness_review(path: Path) -> None:
    reports = feature_readiness_reports(path)
    if not reports:
        print_warning("[WARN] No SpecGuard Review report found. Run the pipeline first.")
        return
    print_section("SpecGuard Review")
    for index, (feature_dir, report) in enumerate(reports, start=1):
        if index > 1:
            print("")
        print(render_readiness_summary(feature_dir, report))
        stale_reason = readiness_report_stale_reason(feature_dir)
        if stale_reason:
            print(yellow(f"- warning: {stale_reason}"))
            print(yellow("- rerun did not update SpecGuard Review if validation failed before the SpecGuard Review step."))


def _revise_spec_from_readiness(path: Path, args: argparse.Namespace, llm_client: object | None, result: object) -> object:
    if llm_client is None:
        print_warning("[WARN] LLM spec revision requires a configured provider.")
        print("- Re-run without --no-llm, or configure one: python -m cli.specguard auth setup")
        return result

    reports = blocked_feature_reports(path) or feature_readiness_reports(path)
    if not reports:
        print_warning("[WARN] No SpecGuard Review report found. Run the pipeline first.")
        return result

    selected = _select_feature_report(reports)
    if selected is None:
        return result
    feature_dir, _report = selected

    print_section("Spec Revision")
    print_hint(f"Generating a revised spec.md from Readiness Findings: {feature_dir}")
    print_hint("Local Codex can take a minute or two here. Keep this terminal open.")
    try:
        revised_spec = _run_with_progress(
            "Revising spec.md",
            lambda: generate_spec_revision(feature_dir, llm_client),
        )
    except LLMRequestError as exc:
        _print_llm_failure(exc)
        print_hint("The follow-up menu is still open. Review findings or retry after adjusting timeout/model.")
        return result
    intent_check = validate_spec_revision_intent(feature_dir, revised_spec)
    if not intent_check.ok:
        proposal_path = write_proposed_spec_revision(feature_dir, revised_spec)
        intent_check.add_info(f"Kept original spec.md unchanged. Proposed revision written to: {proposal_path}")
        intent_check.print()
        print_hint("SpecGuard stopped before Verification Review because the proposed revision may alter product intent.")
        return result
    _print_markdown_preview(revised_spec)
    spec_path = apply_spec_revision(feature_dir, revised_spec)
    print_success(f"[PASS] Updated spec: {spec_path}")
    print_hint("Automatically running Verification Review so SpecGuard Review checks whether the regenerated spec is ready.")
    try:
        return _rerun_pipeline(args, llm_client, force=True, review_mode="verification")
    except LLMRequestError as exc:
        _print_llm_failure(exc)
        print_hint("The follow-up menu is still open. Retry after adjusting timeout/model or review Readiness Findings.")
        return result
    return result


def _select_feature_report(reports: list[tuple[Path, dict]]) -> tuple[Path, dict] | None:
    if len(reports) == 1:
        return reports[0]

    print("Select a feature:")
    for index, (feature_dir, report) in enumerate(reports, start=1):
        summary = report.get("summary", {})
        print(
            f"[{index}] {feature_dir} "
            f"(critical={summary.get('critical', 0)}, major={summary.get('major', 0)}, minor={summary.get('minor', 0)})"
        )
    try:
        value = input("Feature [1]: ").strip()
    except EOFError:
        return None
    selected = 1 if not value else int(value) if value.isdigit() else 0
    if selected < 1 or selected > len(reports):
        print_warning("[WARN] Invalid feature selection.")
        return None
    return reports[selected - 1]


def _print_markdown_preview(markdown: str, *, max_lines: int = 22) -> None:
    lines = markdown.splitlines()
    print("")
    print("Preview:")
    for line in lines[:max_lines]:
        print(line)
    if len(lines) > max_lines:
        print(f"... {len(lines) - max_lines} more line(s)")
    print("")


def _run_with_progress(label: str, operation):
    stop = threading.Event()
    started_at = time.monotonic()
    failed = False

    def render() -> None:
        tick = 0
        while not stop.wait(0.25):
            elapsed = int(time.monotonic() - started_at)
            sys.stdout.write("\r" + _progress_line(label, elapsed, tick))
            sys.stdout.flush()
            tick += 1

    thread = threading.Thread(target=render, daemon=True)
    thread.start()
    try:
        return operation()
    except Exception:
        failed = True
        raise
    finally:
        stop.set()
        thread.join(timeout=1)
        elapsed = int(time.monotonic() - started_at)
        sys.stdout.write("\r" + (" " * 100) + "\r")
        sys.stdout.flush()
        status = "stopped" if failed else "completed"
        print_hint(f"{label} {status} after {elapsed}s.")


def _progress_line(label: str, elapsed_seconds: int, tick: int) -> str:
    width = 18
    active = tick % width
    bar = "".join("#" if index <= active else "-" for index in range(width))
    phases = _progress_phases(label)
    phase = phases[min(elapsed_seconds // 20, len(phases) - 1)]
    return f"> {bold(label)} {green('[' + bar + ']')} {elapsed_seconds:>3}s - {phase}"


def _progress_phases(label: str) -> tuple[str, ...]:
    lowered = label.lower()
    if "pipeline" in lowered:
        return (
            "validating spec artifacts",
            "generating technical design",
            "running SpecGuard Review",
            "building tests, contracts, and outputs",
        )
    if "spec draft" in lowered or "draft" in lowered:
        return (
            "preparing discovery answers",
            "generating spec package",
            "writing draft artifacts",
            "finalizing spec draft",
        )
    return (
        "preparing compact SpecGuard Review context",
        "waiting for LLM provider response",
        "reading model output",
        "finalizing spec draft",
    )


def _rerun_pipeline(args: argparse.Namespace, llm_client: object | None, *, force: bool, review_mode: str = "initial") -> object:
    print_section("Pipeline")
    if review_mode == "verification":
        print_hint("Re-running SpecGuard in Verification Review mode from the regenerated specs.")
    else:
        print_hint("Re-running SpecGuard from the current specs.")
    result = _run_with_progress(
        "Running pipeline",
        lambda: run_pipeline(Path(args.path), llm_client=llm_client, force=force, review_mode=review_mode),
    )
    result.print()
    return result


def _print_llm_failure(exc: Exception) -> None:
    print_error("[FAIL] LLM workflow failed")
    print(f"- {exc}")
    if "newer version of Codex" in str(exc):
        print("- Update the Codex CLI/app, or reconfigure SpecGuard with a Codex-supported model.")
        print("- Example: python -m cli.specguard auth setup --mode codex --model gpt-5.1 --skip-login")
    if "timed out" in str(exc).lower():
        print("- The provider is reachable, but the request exceeded the configured timeout.")
        print("- Retry the action, or increase timeout: python -m cli.specguard auth setup --mode codex --timeout 240 --skip-login")
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
    run_parser.add_argument("--no-llm", action="store_true", help="Use local deterministic generators and heuristic SpecGuard Review")
    run_parser.add_argument("--llm-mode", choices=["codex", "openai"], help="Override the configured LLM provider mode")
    run_parser.add_argument("--llm-model", help="Override SPECGUARD_LLM_MODEL for this run")
    run_parser.add_argument("--strict-e2e", action="store_true", help="Automatically regenerate blocked specs and rerun Verification Review")
    run_parser.add_argument("--strict-max-iterations", type=int, default=3, help="Maximum strict E2E verification iterations")
    run_parser.add_argument("--follow-up", action="store_true", help="Force the interactive post-run action menu")
    run_parser.add_argument("--no-follow-up", action="store_true", help="Do not show the interactive post-run action menu")
    run_parser.set_defaults(func=run)

    auth_parser = subparsers.add_parser("auth", formatter_class=SpecGuardHelpFormatter)
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)

    auth_setup = auth_subparsers.add_parser("setup", formatter_class=SpecGuardHelpFormatter)
    auth_setup.add_argument("--mode", choices=["codex", "openai"], help="LLM provider mode")
    auth_setup.add_argument("--model", help="Model name for the selected provider; Codex setup defaults to gpt-5.4")
    auth_setup.add_argument("--timeout", type=int, help="Provider request timeout in seconds")
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
