from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import threading
import time
from importlib import resources
from pathlib import Path

from tools.action_installer import WorkflowInstallResult, install_workflow
from tools.discovery_engine import DISCOVERY_PROMPTS, answers_from_args, collect_answers, collect_llm_answers, initialize_specs
from tools.llm_client import (
    DEFAULT_CODEX_TIMEOUT,
    DEFAULT_OPENAI_TIMEOUT,
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
    apply_spec_revision_with_audit,
    blocked_feature_reports,
    feature_readiness_reports,
    generate_spec_revision,
    readiness_report_stale_reason,
    render_readiness_summary,
    spec_revision_design_refresh_reason,
    validate_spec_revision_intent,
)
from tools.progress import current_progress_activity
from tools.readiness_engine import (
    DEFAULT_REVIEW_LEVEL,
    MEDIUM_REVIEW_LEVEL,
    READINESS_REVIEW_LEVELS,
    normalize_review_level,
    review_level_gate_text,
)
from tools.runner import run_pipeline
from tools.strict_e2e import run_strict_e2e_pipeline
from tools.ux import bold, green, menu_item, print_banner, print_error, print_hint, print_section, print_success, print_warning, yellow


ROOT = Path.cwd()
DISCOVERY_DEFAULTS = {key: default for key, _prompt, default in DISCOVERY_PROMPTS}
CODEX_REASONING_EFFORT_CHOICES = ("minimal", "low", "medium", "high", "xhigh")


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
    if result.ok and hasattr(args, "no_actions") and not args.no_actions:
        if not _install_default_readiness_gate(force=getattr(args, "force_actions", False)):
            return 1
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
        print("- Re-run without --no-llm, or configure one: specguard auth setup")
        return 1
    review_level = _resolve_review_level(args, strict_e2e=strict_e2e)
    if review_level is None:
        return 1
    args.review_level = review_level

    print_section("Pipeline")
    if args.force:
        print_hint("Regenerating derived artifacts where SpecGuard owns the output.")
    elif strict_e2e:
        print_hint(f"Running strict E2E with at most {strict_max_iterations} verification iteration(s).")
    else:
        print_hint("Missing artifacts are generated; stale tests and contracts are refreshed from the spec.")
    print_hint(f"SpecGuard Review level: {review_level} ({review_level_gate_text(review_level)}).")

    try:
        if strict_e2e:
            result = _run_with_progress(
                "Running strict E2E pipeline",
                lambda: run_strict_e2e_pipeline(
                    Path(args.path),
                    llm_client,
                    force=args.force,
                    max_iterations=strict_max_iterations,
                    review_level=review_level,
                ),
            )
        else:
            result = _run_with_progress(
                "Running pipeline",
                lambda: run_pipeline(Path(args.path), llm_client=llm_client, force=args.force, review_level=review_level),
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


def copy_example(args: argparse.Namespace) -> int:
    feature_dir = _example_target_path(args.feature)
    print_banner("Copy authored example specs into a feature package.")

    source = resources.files("tools").joinpath("resources", "example")
    if not source.is_dir():
        print_error("[FAIL] Packaged example resources are missing.")
        print("- Reinstall SpecGuard, or use a source checkout with the example package.")
        return 1

    conflicts = sorted(path for path in _resource_relative_files(source) if (feature_dir / path).exists())
    if conflicts and not args.force:
        print_error("[FAIL] Example copy would overwrite existing files.")
        print(f"- Target: {feature_dir}")
        print("- Re-run with --force to replace the current draft package with the authored example.")
        for path in conflicts[:8]:
            print(f"- Existing file: {feature_dir / path}")
        if len(conflicts) > 8:
            print(f"- ... {len(conflicts) - 8} more existing file(s)")
        return 1

    copied = _copy_resource_tree(source, feature_dir)
    print_success("[PASS] Copied authored example specs.")
    print(f"- Target: {feature_dir}")
    print(f"- Files copied: {copied}")
    print("")
    print("Next steps:")
    print(f"- Run: specguard run {feature_dir} --no-follow-up")
    print("- Use --no-llm only for deterministic local smoke checks without a configured provider.")
    print("- Replace the example files with your own feature requirements before real implementation.")
    return 0


def actions(args: argparse.Namespace) -> int:
    if args.actions_command == "install-readiness-gate":
        return 0 if _install_default_readiness_gate(force=args.force) else 1
    if args.actions_command == "install-pr-review":
        return 0 if _install_pr_review(force=args.force) else 1
    if args.actions_command == "install":
        workflows: list[str] = []
        if args.readiness_gate:
            workflows.append("readiness-gate")
        if args.pr_review:
            workflows.append("pr-review")
        if not workflows:
            print_error("[FAIL] Choose at least one workflow to install.")
            print("- Example: specguard actions install --readiness-gate")
            print("- Example: specguard actions install --pr-review")
            return 1
        ok = True
        for workflow in workflows:
            if workflow == "readiness-gate":
                ok = _install_default_readiness_gate(force=args.force) and ok
            if workflow == "pr-review":
                ok = _install_pr_review(force=args.force) and ok
        return 0 if ok else 1

    print_error("[FAIL] Unknown actions command.")
    return 1


def _example_target_path(feature: str) -> Path:
    target = Path(feature)
    if target.is_absolute() or target.parts[:1] == ("specs",):
        return target
    return ROOT / "specs" / feature


def _resource_relative_files(root) -> list[Path]:
    files: list[Path] = []

    def visit(node, prefix: Path) -> None:
        for child in node.iterdir():
            child_path = prefix / child.name
            if child.is_dir():
                visit(child, child_path)
            else:
                files.append(child_path)

    visit(root, Path())
    return files


def _copy_resource_tree(source, target: Path) -> int:
    copied = 0
    target.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        destination = target / child.name
        if child.is_dir():
            copied += _copy_resource_tree(child, destination)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(child.read_bytes())
        copied += 1
    return copied


def _install_default_readiness_gate(*, force: bool) -> bool:
    try:
        result = install_workflow(ROOT, "readiness-gate", force=force)
    except (OSError, ValueError) as exc:
        print_error("[FAIL] Could not install SpecGuard Readiness Gate workflow.")
        print(f"- {exc}")
        return False

    _print_workflow_install_result(result, force_hint="--force-actions")
    if result.installed:
        print("")
        print("Merge protection:")
        print("- Add `SpecGuard Readiness Gate` as a required status check in your GitHub branch protection or ruleset.")
        print("")
        print("Optional PR Review:")
        print("- Run `specguard actions install-pr-review` to add AI-assisted PR review comments.")
    return True


def _install_pr_review(*, force: bool) -> bool:
    try:
        result = install_workflow(ROOT, "pr-review", force=force)
    except (OSError, ValueError) as exc:
        print_error("[FAIL] Could not install SpecGuard PR Review workflow.")
        print(f"- {exc}")
        return False

    _print_workflow_install_result(result, force_hint="--force")
    if result.installed:
        print("")
        print("Next steps:")
        print("1. Commit and push the workflow file.")
        print("2. Add this GitHub Actions secret in Repository Settings > Secrets and variables > Actions:")
        print("")
        print("SPECGUARD_OPENAI_API_KEY=sk-...")
        print("")
        print("Optional repository variables:")
        print("SPECGUARD_PR_REVIEW_MODEL=gpt-5.4-nano")
        print("SPECGUARD_REVIEW_SPEC_PATHS=specs/your-feature-name")
        print("")
        print("Use SPECGUARD_REVIEW_SPEC_PATHS when a PR changes only implementation files under develop/.")
    return True


def _print_workflow_install_result(result: WorkflowInstallResult, *, force_hint: str) -> None:
    display_path = _display_path(result.path)
    if result.installed:
        verb = "Updated" if result.overwritten else "Installed"
        print_success(f"[PASS] {verb} {result.name} workflow:")
        print(f"- {display_path}")
        return

    print_warning(f"[WARN] {result.name} workflow already exists; kept current file.")
    print(f"- {display_path}")
    print(f"- Re-run with {force_hint} to replace it.")


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def auth(args: argparse.Namespace) -> int:
    if args.auth_command == "status":
        print_banner("LLM provider status.")
        settings = load_llm_settings(ROOT)
        if settings is None:
            print_warning("[WARN] No LLM provider configured.")
            print(f"- Config path: {config_path(ROOT)}")
            print("- Run: specguard auth setup")
            return 1
        print_success("[PASS] SpecGuard LLM configuration")
        print(f"- Mode: {settings.mode}")
        print(f"- Model: {settings.model or '(provider default)'}")
        print(f"- Timeout: {settings.timeout}s")
        print("- Status checks saved configuration and command availability, not a full live model request.")
        if settings.mode == "openai":
            print(f"- API key source: {settings.api_key_env if not settings.api_key else 'local config'}")
            print(f"- Endpoint: {settings.endpoint}")
        if settings.mode == "codex":
            print(f"- Codex command: {settings.codex_command}")
            print(f"- Codex profile: {settings.codex_profile or '(default)'}")
            print(f"- Codex reasoning effort: {settings.codex_reasoning_effort or '(Codex default)'}")
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


def _resolve_review_level(args: argparse.Namespace, *, strict_e2e: bool = False) -> str | None:
    default = MEDIUM_REVIEW_LEVEL if strict_e2e else DEFAULT_REVIEW_LEVEL
    configured = getattr(args, "review_level", None) or os.getenv("SPECGUARD_REVIEW_LEVEL") or default
    try:
        return normalize_review_level(configured)
    except ValueError:
        print_error("[FAIL] Unsupported SpecGuard Review level.")
        print(f"- Received: {configured}")
        print(f"- Supported levels: {', '.join(sorted(READINESS_REVIEW_LEVELS))}")
        return None


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
                timeout=None,
                codex_command="codex",
                codex_profile=None,
                codex_reasoning_effort=None,
                skip_login=False,
            )
            if _setup_llm(setup_args) == 0:
                try:
                    return build_llm_client(ROOT, mode=mode, model=getattr(args, "llm_model", None))
                except LLMConfigError as retry_exc:
                    exc = retry_exc
        print_error("[FAIL] SpecGuard LLM configuration")
        print(f"- {exc}")
        print("- Run: specguard auth setup")
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
        timeout = args.timeout or DEFAULT_CODEX_TIMEOUT
        codex_command = args.codex_command or "codex"
        if not codex_available(codex_command):
            print_error("[FAIL] Local Codex CLI was not found.")
            print("- Install Codex, or choose OpenAI Platform mode: specguard auth setup --mode openai")
            return 1
        settings = LLMSettings(
            mode="codex",
            model=model,
            timeout=timeout,
            codex_command=codex_command,
            codex_profile=args.codex_profile,
            codex_reasoning_effort=args.codex_reasoning_effort,
        )
        path = save_llm_settings(ROOT, settings)
        print_success(f"[PASS] Saved local Codex provider config: {path}")
        if not args.skip_login and _prompt_yes_no("Run `codex login` now?", default=False):
            _run_codex_account_command(codex_command, "login")
        return 0

    model = args.model or _prompt("Model", "gpt-5.1")
    timeout = args.timeout or DEFAULT_OPENAI_TIMEOUT
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
        print("- Re-run without --no-llm, or configure one: specguard auth setup")
        return result

    reports = blocked_feature_reports(path) or feature_readiness_reports(path)
    if not reports:
        print_warning("[WARN] No SpecGuard Review report found. Run the pipeline first.")
        return result

    selected = _select_feature_report(reports)
    if selected is None:
        return result
    feature_dir, _report = selected
    original_spec = feature_dir.joinpath("spec.md").read_text(encoding="utf-8")

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
        audit = apply_spec_revision_with_audit(feature_dir, revised_spec)
        intent_check.add_info(f"Updated working spec.md for in-place review: {audit.spec_path}")
        intent_check.add_info(f"Original spec and unified diff written to: {audit.audit_dir}")
        intent_check.add_next_step(f"Review diff: {audit.diff_path}")
        intent_check.print()
        print_hint("SpecGuard stopped before Verification Review so you can review the applied spec diff.")
        return result
    _print_markdown_preview(revised_spec)
    refresh_reason = spec_revision_design_refresh_reason(original_spec, revised_spec)
    spec_path = apply_spec_revision(feature_dir, revised_spec)
    print_success(f"[PASS] Updated spec: {spec_path}")
    if refresh_reason:
        print_hint(f"Technical design refresh required before Verification Review: {refresh_reason}.")
    else:
        print_hint("Reusing existing technical-design.md for Verification Review because the spec revision does not change design-significant sections.")
    print_hint("Automatically running Verification Review so SpecGuard Review checks whether the regenerated spec is ready.")
    try:
        return _rerun_pipeline(
            args,
            llm_client,
            force=True,
            review_mode="verification",
            refresh_technical_design=bool(refresh_reason),
        )
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
            sys.stdout.write("\r" + _progress_line(label, elapsed, tick, activity=current_progress_activity()))
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


def _progress_line(label: str, elapsed_seconds: int, tick: int, activity: str | None = None) -> str:
    width = 18
    active = tick % width
    bar = "".join("#" if index <= active else "-" for index in range(width))
    if activity:
        phase = activity
    else:
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


def _rerun_pipeline(
    args: argparse.Namespace,
    llm_client: object | None,
    *,
    force: bool,
    review_mode: str = "initial",
    refresh_technical_design: bool | None = None,
) -> object:
    review_level = normalize_review_level(getattr(args, "review_level", None) or os.getenv("SPECGUARD_REVIEW_LEVEL") or DEFAULT_REVIEW_LEVEL)
    print_section("Pipeline")
    if review_mode == "verification":
        print_hint("Re-running SpecGuard in Verification Review mode from the regenerated specs.")
    else:
        print_hint("Re-running SpecGuard from the current specs.")
    print_hint(f"SpecGuard Review level: {review_level} ({review_level_gate_text(review_level)}).")
    result = _run_with_progress(
        "Running pipeline",
        lambda: run_pipeline(
            Path(args.path),
            llm_client=llm_client,
            force=force,
            review_mode=review_mode,
            review_level=review_level,
            refresh_technical_design=refresh_technical_design,
        ),
    )
    result.print()
    return result


def _print_llm_failure(exc: Exception) -> None:
    print_error("[FAIL] LLM workflow failed")
    print(f"- {exc}")
    if "newer version of Codex" in str(exc):
        print("- Update the Codex CLI/app, or reconfigure SpecGuard with a Codex-supported model.")
        print("- Example: specguard auth setup --mode codex --model gpt-5.1 --skip-login")
    if "timed out" in str(exc).lower():
        print("- The provider is reachable, but the request exceeded the configured timeout.")
        print(f"- Retry the action, or increase timeout: specguard auth setup --mode codex --timeout {DEFAULT_CODEX_TIMEOUT} --skip-login")
    print("- Check provider status: specguard auth status")
    print("- Reconfigure provider: specguard auth setup")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="specguard",
        description="SpecGuard refines specs into validated implementation-ready artifacts.",
        formatter_class=SpecGuardHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Create draft specs and install the default readiness gate",
        description=(
            "Run Discovery and generate draft specs under specs/.\n"
            "Interactive mode shows a default for every question. Press Enter to accept it.\n"
            "By default, init also installs the consumer SpecGuard Readiness Gate workflow."
        ),
        epilog=(
            "Examples:\n"
            "  specguard init\n"
            "  specguard init billing-export\n"
            "  specguard init todo-api,billing-export --non-interactive\n"
            "  specguard init billing-export --no-actions"
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
    init_parser.add_argument("--no-actions", action="store_true", help="Skip default readiness gate workflow installation")
    init_parser.add_argument("--force-actions", action="store_true", help="Overwrite an existing default SpecGuard Actions workflow")
    init_parser.add_argument("--llm", action="store_true", help="Compatibility flag; LLM Discovery is already the default")
    init_parser.add_argument("--no-llm", action="store_true", help="Skip live LLM requests and use deterministic local Discovery")
    init_parser.add_argument("--llm-mode", choices=["codex", "openai"], help="Use this provider for live Discovery without changing saved config")
    init_parser.add_argument("--llm-model", help="Use this model for live Discovery without changing saved config")
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

    example_parser = subparsers.add_parser(
        "example",
        help="Copy the packaged authored example",
        description="Work with packaged example spec packages for smoke testing the local workflow.",
        formatter_class=SpecGuardHelpFormatter,
    )
    example_subparsers = example_parser.add_subparsers(dest="example_command", required=True)

    example_copy = example_subparsers.add_parser(
        "copy",
        description=(
            "Copy the packaged authored example spec package into specs/<feature>.\n"
            "Typical sample flow: init -> copy -> run."
        ),
        epilog=(
            "Examples:\n"
            "  specguard auth setup --mode codex --model gpt-5.4 --skip-login\n"
            "  specguard init team-invite --non-interactive --no-llm\n"
            "  specguard example copy team-invite --force\n"
            "  specguard run specs/team-invite --no-follow-up"
        ),
        formatter_class=SpecGuardHelpFormatter,
    )
    example_copy.add_argument("feature", help="Feature name under specs/ or an explicit specs/<feature> path")
    example_copy.add_argument("--force", action="store_true", help="Overwrite existing files in the target package")
    example_copy.set_defaults(func=copy_example)

    run_parser = subparsers.add_parser(
        "run",
        help="Validate specs and produce implementation handoff artifacts",
        description=(
            "Run validation, technical design, SpecGuard Review, tests, contracts, and implementation handoff.\n"
            "LLM review is enabled by default when a provider is configured; use --no-llm for local deterministic checks."
        ),
        epilog=(
            "Examples:\n"
            "  specguard run specs/team-invite\n"
            "  specguard run specs/team-invite --no-llm --no-follow-up\n"
            "  specguard run specs/team-invite --strict-e2e --strict-max-iterations 2\n\n"
            "Timeout recovery:\n"
            f"  specguard auth setup --mode codex --timeout {DEFAULT_CODEX_TIMEOUT} --skip-login"
        ),
        formatter_class=SpecGuardHelpFormatter,
    )
    run_parser.add_argument("path", nargs="?", default="specs", help="Spec package directory or specs root to process")
    run_parser.add_argument("--force", action="store_true", help="Regenerate derived artifacts instead of reusing existing files")
    run_parser.add_argument("--llm", action="store_true", help="Compatibility flag; LLM review is already the default")
    run_parser.add_argument("--no-llm", action="store_true", help="Skip live LLM requests and use local generators plus heuristic SpecGuard Review")
    run_parser.add_argument("--llm-mode", choices=["codex", "openai"], help="Use this provider for live review without changing saved config")
    run_parser.add_argument("--llm-model", help="Use this model for live review without changing saved config")
    run_parser.add_argument(
        "--review-level",
        choices=sorted(READINESS_REVIEW_LEVELS),
        help="SpecGuard Review level; defaults to low, or medium for strict E2E unless SPECGUARD_REVIEW_LEVEL is set",
    )
    run_parser.add_argument("--strict-e2e", action="store_true", help="Automatically regenerate blocked specs and rerun Verification Review")
    run_parser.add_argument("--strict-max-iterations", type=int, default=3, help="Maximum strict E2E verification iterations")
    run_parser.add_argument("--follow-up", action="store_true", help="Force the interactive post-run action menu after the run")
    run_parser.add_argument("--no-follow-up", action="store_true", help="Never show the interactive post-run action menu")
    run_parser.set_defaults(func=run)

    actions_parser = subparsers.add_parser(
        "actions",
        help="Install consumer GitHub Actions workflows",
        description="Install packaged SpecGuard GitHub Actions workflows into the current repository.",
        formatter_class=SpecGuardHelpFormatter,
    )
    actions_subparsers = actions_parser.add_subparsers(dest="actions_command", required=True)

    actions_install_readiness = actions_subparsers.add_parser(
        "install-readiness-gate",
        description="Install the consumer SpecGuard Readiness Gate workflow.",
        epilog="Use this workflow as the required status check for merge protection.",
        formatter_class=SpecGuardHelpFormatter,
    )
    actions_install_readiness.add_argument("--force", action="store_true", help="Overwrite an existing workflow file")
    actions_install_readiness.set_defaults(func=actions)

    actions_install_pr_review = actions_subparsers.add_parser(
        "install-pr-review",
        description="Install the optional AI-assisted SpecGuard PR Review workflow.",
        epilog="Requires the SPECGUARD_OPENAI_API_KEY GitHub Actions secret after committing the workflow.",
        formatter_class=SpecGuardHelpFormatter,
    )
    actions_install_pr_review.add_argument("--force", action="store_true", help="Overwrite an existing workflow file")
    actions_install_pr_review.set_defaults(func=actions)

    actions_install = actions_subparsers.add_parser(
        "install",
        description="Install selected consumer SpecGuard GitHub Actions workflows.",
        epilog="Examples:\n  specguard actions install --readiness-gate\n  specguard actions install --pr-review",
        formatter_class=SpecGuardHelpFormatter,
    )
    actions_install.add_argument("--readiness-gate", action="store_true", help="Install the SpecGuard Readiness Gate workflow")
    actions_install.add_argument("--pr-review", action="store_true", help="Install the SpecGuard PR Review workflow")
    actions_install.add_argument("--force", action="store_true", help="Overwrite existing workflow files")
    actions_install.set_defaults(func=actions)

    auth_parser = subparsers.add_parser(
        "auth",
        help="Configure or inspect local LLM provider settings",
        description="Manage local SpecGuard LLM provider configuration.",
        formatter_class=SpecGuardHelpFormatter,
    )
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)

    auth_setup = auth_subparsers.add_parser(
        "setup",
        description=(
            "Save local SpecGuard LLM provider configuration.\n"
            "Codex mode uses the local Codex CLI/session; OpenAI mode uses the Responses API and an API key."
        ),
        epilog=(
            "Defaults:\n"
            f"  Codex timeout: {DEFAULT_CODEX_TIMEOUT}s\n"
            f"  OpenAI timeout: {DEFAULT_OPENAI_TIMEOUT}s\n\n"
            "Configuration check:\n"
            "  specguard auth status checks saved configuration and command availability, not a full live model request."
        ),
        formatter_class=SpecGuardHelpFormatter,
    )
    auth_setup.add_argument("--mode", choices=["codex", "openai"], help="Provider to save: local Codex CLI or OpenAI Platform")
    auth_setup.add_argument("--model", help="Model name for the selected provider; Codex setup defaults to gpt-5.4")
    auth_setup.add_argument("--timeout", type=int, help="Provider request timeout in seconds; Codex defaults to 600, OpenAI defaults to 180")
    auth_setup.add_argument("--api-key", help="Store an OpenAI API key in local ignored config")
    auth_setup.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable used for the OpenAI API key")
    auth_setup.add_argument("--endpoint", default="https://api.openai.com/v1/responses", help="OpenAI Responses API endpoint")
    auth_setup.add_argument("--codex-command", default="codex", help="Local Codex CLI command used by Codex mode")
    auth_setup.add_argument("--codex-profile", help="Optional Codex CLI profile")
    auth_setup.add_argument(
        "--codex-reasoning-effort",
        choices=CODEX_REASONING_EFFORT_CHOICES,
        help="Optional Codex exec reasoning effort for faster or stricter local review profiles",
    )
    auth_setup.add_argument("--skip-login", action="store_true", help="Save config without offering to run codex login")
    auth_setup.set_defaults(func=auth)

    auth_status = auth_subparsers.add_parser(
        "status",
        description="Check saved provider configuration and local command availability without making a live model request.",
        formatter_class=SpecGuardHelpFormatter,
    )
    auth_status.set_defaults(func=auth)

    auth_logout = auth_subparsers.add_parser(
        "logout",
        description="Remove local SpecGuard provider configuration.",
        formatter_class=SpecGuardHelpFormatter,
    )
    auth_logout.add_argument("--codex", action="store_true", help="Also run codex logout")
    auth_logout.set_defaults(func=auth)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
