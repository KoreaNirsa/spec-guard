from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from tools.progress import progress_activity
from tools.readiness_engine import is_review_source_artifact, review_artifact_paths
from tools.result import CheckResult
from tools.spec_packages import SUPPORTED_PACKAGE_PATH_EXAMPLES, discover_spec_packages


SPECGUARD_STATE_DIR = ".specguard"
SPEC_REVISION_AUDIT_DIR = "spec-revisions"
PLUGIN_RUN_STATE_FILENAME = "run-state.json"
PLUGIN_RUN_STATE_SCHEMA_VERSION = "specguard.plugin_run_state.v1"
DESIGN_REUSE_SAFE_SECTIONS = {
    "acceptance criteria",
    "review & acceptance checklist",
}
DESIGN_REFRESH_KEYWORDS = {
    "api",
    "architecture",
    "auth",
    "authorization",
    "cache",
    "contract",
    "database",
    "dependency",
    "endpoint",
    "idempotency",
    "migration",
    "ownership",
    "persistence",
    "queue",
    "retry",
    "state",
    "timeout",
    "transaction",
}


@dataclass(frozen=True)
class SpecRevisionAudit:
    spec_path: Path
    audit_dir: Path
    original_path: Path
    diff_path: Path


@dataclass(frozen=True)
class PluginRunState:
    state: str
    command: str
    package_path: str = ""
    failure_category: str | None = None
    failed_stage: str | None = None
    messages: tuple[str, ...] = ()
    next_steps: tuple[str, ...] = ()
    known_files: tuple[str, ...] = ()
    relevant_files: tuple[str, ...] = ()
    next_action: str = ""
    stale_reason: str | None = None


@dataclass(frozen=True)
class PluginReadinessSummary:
    feature_dir: str
    status: str
    review_level: str
    critical: int
    major: int
    minor: int
    handoff_available: bool
    top_findings: tuple[str, ...] = ()
    report_files: tuple[str, ...] = ()
    reviewed_artifact_count: int = 0
    standard_reviewed_artifacts: tuple[str, ...] = ()
    additional_authored_count: int = 0
    additional_authored_artifacts: tuple[str, ...] = ()
    report_path: str | None = None
    handoff_path: str | None = None
    edit_target: str | None = None
    rerun_command: str = ""
    next_action: str = ""


@dataclass(frozen=True)
class PluginRerunSuggestion:
    finding: str
    suggested_clarification: str
    scope_check: str
    next_step: str


@dataclass(frozen=True)
class PluginRerunGuidance:
    feature_dir: str
    state: str
    command: str
    stale_reason: str | None = None
    previous_report_files: tuple[str, ...] = ()
    suggestions: tuple[PluginRerunSuggestion, ...] = ()
    next_action: str = ""


@dataclass(frozen=True)
class SpecRevisionSoftening:
    revised_spec: str
    demoted_items: tuple[str, ...] = ()


_STOPWORDS = {
    "about",
    "after",
    "before",
    "between",
    "cannot",
    "could",
    "from",
    "given",
    "must",
    "need",
    "needs",
    "only",
    "return",
    "returns",
    "should",
    "spec",
    "specification",
    "system",
    "that",
    "their",
    "then",
    "this",
    "when",
    "with",
    "without",
}


def feature_dirs(path: Path) -> list[Path]:
    return discover_spec_packages(path)


def load_readiness_report(feature_dir: Path) -> dict[str, Any] | None:
    report_path = feature_dir / "readiness-review.json"
    if not report_path.exists():
        return None
    return json.loads(report_path.read_text(encoding="utf-8"))


def feature_readiness_reports(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    reports: list[tuple[Path, dict[str, Any]]] = []
    for feature_dir in feature_dirs(path):
        report = load_readiness_report(feature_dir)
        if report is not None:
            reports.append((feature_dir, report))
    return reports


def blocked_feature_reports(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    return [(feature_dir, report) for feature_dir, report in feature_readiness_reports(path) if report.get("blocked")]


def render_readiness_summary(feature_dir: Path, report: dict[str, Any], *, limit: int = 5) -> str:
    summary = report.get("summary", {})
    readiness = report.get("readiness", {})
    status = readiness.get("status", "unknown") if isinstance(readiness, dict) else "unknown"
    issues = report.get("issues", [])
    lines = [
        f"{feature_dir}",
        f"- blocked: {bool(report.get('blocked'))}",
        f"- status: {status}",
        f"- critical: {summary.get('critical', 0)}, major: {summary.get('major', 0)}, minor: {summary.get('minor', 0)}",
    ]
    for issue in issues[:limit]:
        lines.extend([
            f"- [{issue.get('severity', 'Unknown')}] {issue.get('title', 'Untitled issue')}",
            f"  impact: {issue.get('impact', 'Not specified.')}",
            f"  fix: {issue.get('fix', 'Not specified.')}",
        ])
    if len(issues) > limit:
        lines.append(f"- ... {len(issues) - limit} more issue(s)")
    return "\n".join(lines)


def build_plugin_readiness_summary(
    feature_dir: Path,
    report: dict[str, Any],
    *,
    limit: int = 3,
    artifact_limit: int = 6,
) -> PluginReadinessSummary:
    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    status = _readiness_status(report)
    handoff_available = _implementation_handoff_available(feature_dir, report)
    reviewed_artifacts = _plugin_reviewed_artifacts(report)
    standard_artifacts = tuple(path for path in reviewed_artifacts if _is_standard_review_artifact(path))
    additional_artifacts = tuple(path for path in reviewed_artifacts if not _is_standard_review_artifact(path))
    return PluginReadinessSummary(
        feature_dir=feature_dir.as_posix(),
        status=status,
        review_level=str(report.get("review_level") or "unknown"),
        critical=_summary_count(summary, "critical"),
        major=_summary_count(summary, "major"),
        minor=_summary_count(summary, "minor"),
        handoff_available=handoff_available,
        top_findings=_plugin_top_findings(report, status=status, limit=limit),
        report_files=_plugin_summary_report_files(feature_dir, handoff_available=handoff_available),
        reviewed_artifact_count=len(reviewed_artifacts),
        standard_reviewed_artifacts=standard_artifacts[:artifact_limit],
        additional_authored_count=len(additional_artifacts),
        additional_authored_artifacts=additional_artifacts[:artifact_limit],
        report_path=_plugin_human_report_path(feature_dir),
        handoff_path=(feature_dir / "implementation-output.md").as_posix() if handoff_available else None,
        edit_target=(feature_dir / "spec.md").as_posix() if status in {"not_ready", "ready_with_warnings"} else None,
        rerun_command=_default_plugin_rerun_command(feature_dir),
        next_action=_plugin_next_action(feature_dir, status, report),
    )


def render_plugin_readiness_summary(
    feature_dir: Path,
    report: dict[str, Any],
    *,
    limit: int = 3,
    artifact_limit: int = 6,
) -> str:
    summary = build_plugin_readiness_summary(feature_dir, report, limit=limit, artifact_limit=artifact_limit)
    lines = [
        summary.feature_dir,
        f"- status: {summary.status}",
        f"- review level: {summary.review_level}",
        f"- findings: Critical {summary.critical}, Major {summary.major}, Minor {summary.minor}",
        f"- handoff available: {'yes' if summary.handoff_available else 'no'}",
    ]
    if summary.top_findings:
        lines.append("- top findings:")
        lines.extend(f"  - {finding}" for finding in summary.top_findings)
    else:
        lines.append("- top findings: none")

    lines.append("- reports:")
    if summary.report_files:
        lines.extend(f"  - {path}" for path in summary.report_files)
    else:
        lines.append("  - none")
    lines.extend(_render_plugin_artifact_summary(summary))
    lines.extend([
        f"- report path: {summary.report_path or 'unavailable'}",
        f"- handoff path: {summary.handoff_path or 'unavailable'}",
        f"- edit target: {summary.edit_target or 'none'}",
        f"- rerun command: {summary.rerun_command}",
    ])
    lines.append(f"- next action: {summary.next_action}")
    return "\n".join(lines)


def build_plugin_rerun_guidance(
    feature_dir: Path,
    report: dict[str, Any] | None = None,
    *,
    limit: int = 3,
    command: str | None = None,
) -> PluginRerunGuidance:
    current_report = report if report is not None else _load_readiness_report_safely(feature_dir)
    rerun_command = command or _default_plugin_rerun_command(feature_dir)
    stale_reason = readiness_report_stale_reason(feature_dir)
    state = "stale_review"
    if not stale_reason:
        state = _readiness_status(current_report) if current_report else "validation_failed_before_review"
        if state not in {"ready", "ready_with_warnings", "not_ready"}:
            state = "validation_failed_before_review"
    suggestions = _plugin_rerun_suggestions(current_report, limit=limit) if current_report else ()
    if stale_reason:
        next_action = (
            "Treat previous findings as suggestions only. User updates the spec package, "
            f"then reruns `{rerun_command}` before implementation starts."
        )
    elif state == "validation_failed_before_review":
        next_action = f"Rerun `{rerun_command}` to produce a fresh readiness result before implementation starts."
    else:
        next_action = "Use the fresh readiness result; do not treat previous suggestions as implementation input."
    return PluginRerunGuidance(
        feature_dir=feature_dir.as_posix(),
        state=state,
        command=rerun_command,
        stale_reason=stale_reason,
        previous_report_files=_plugin_previous_report_files(feature_dir),
        suggestions=suggestions,
        next_action=next_action,
    )


def render_plugin_rerun_guidance(
    feature_dir: Path,
    report: dict[str, Any] | None = None,
    *,
    limit: int = 3,
    command: str | None = None,
) -> str:
    guidance = build_plugin_rerun_guidance(feature_dir, report, limit=limit, command=command)
    lines = [
        guidance.feature_dir,
        f"- state: {guidance.state}",
        f"- rerun command: {guidance.command}",
    ]
    if guidance.stale_reason:
        lines.append(f"- stale reason: {guidance.stale_reason}")

    lines.append("- previous reports:")
    if guidance.previous_report_files:
        lines.extend(f"  - {path}" for path in guidance.previous_report_files)
    else:
        lines.append("  - none")

    if guidance.suggestions:
        lines.append("- previous findings and clarifications: suggestion only")
        for suggestion in guidance.suggestions:
            lines.extend([
                f"  - finding: {suggestion.finding}",
                f"    suggested clarification: {suggestion.suggested_clarification}",
                f"    scope check: {suggestion.scope_check}",
                f"    next step: {suggestion.next_step}",
            ])
    else:
        lines.append("- previous findings and clarifications: none")

    lines.append(f"- next action: {guidance.next_action}")
    return "\n".join(lines)


def render_plugin_rerun_result(
    feature_dir: Path,
    *,
    command: str | None = None,
    started_at: float | None = None,
    returncode: int | None = None,
    timed_out: bool = False,
    cli_available: bool = True,
    spec_package_exists: bool | None = None,
    provider_required: bool = False,
    provider_available: bool = True,
    limit: int = 3,
) -> str:
    rerun_command = command or _default_plugin_rerun_command(feature_dir)
    state = derive_plugin_run_state(
        feature_dir,
        command=rerun_command,
        started_at=started_at,
        returncode=returncode,
        timed_out=timed_out,
        cli_available=cli_available,
        spec_package_exists=spec_package_exists,
        provider_required=provider_required,
        provider_available=provider_available,
    )
    lines = [
        feature_dir.as_posix(),
        f"- command: {state.command}",
        f"- state: {state.state}",
    ]
    if state.stale_reason:
        lines.append(f"- stale reason: {state.stale_reason}")

    if state.state in {"ready", "ready_with_warnings", "not_ready"}:
        report = _load_readiness_report_safely(feature_dir)
        if report is not None:
            summary = build_plugin_readiness_summary(feature_dir, report, limit=limit)
            lines.extend([
                f"- fresh result: {_plugin_fresh_result_label(summary.status)}",
                f"- status: {summary.status}",
                f"- review level: {summary.review_level}",
                f"- findings: Critical {summary.critical}, Major {summary.major}, Minor {summary.minor}",
                f"- handoff available: {'yes' if summary.handoff_available else 'no'}",
            ])
            if summary.top_findings:
                lines.append("- top findings:")
                lines.extend(f"  - {finding}" for finding in summary.top_findings)
            else:
                lines.append("- top findings: none")
            lines.append("- reports:")
            if summary.report_files:
                lines.extend(f"  - {path}" for path in summary.report_files)
            else:
                lines.append("  - none")
            lines.extend(_render_plugin_artifact_summary(summary))

    elif state.known_files:
        lines.append("- known files:")
        lines.extend(f"  - {path}" for path in state.known_files)

    lines.append(f"- next action: {state.next_action}")
    return "\n".join(lines)


def plugin_run_state_path(feature_dir: Path) -> Path:
    return feature_dir / SPECGUARD_STATE_DIR / PLUGIN_RUN_STATE_FILENAME


def write_pre_review_failure_run_state(
    feature_dir: Path,
    *,
    command: str,
    failed_stage: str,
    messages: list[str] | tuple[str, ...],
    next_steps: list[str] | tuple[str, ...],
) -> Path:
    path = plugin_run_state_path(feature_dir)
    relevant_files = (path.as_posix(),)
    state = PluginRunState(
        state="validation_failed_before_review",
        command=command,
        package_path=feature_dir.as_posix(),
        failure_category="validation_failed_before_review",
        failed_stage=failed_stage,
        messages=tuple(messages),
        next_steps=tuple(next_steps),
        known_files=_known_plugin_files(feature_dir, include_handoff=False),
        relevant_files=relevant_files,
        next_action="Fix validation errors in the spec package, then rerun SpecGuard before using any old readiness report.",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_plugin_run_state_payload(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def readiness_report_stale_reason(feature_dir: Path) -> str | None:
    report_path = feature_dir / "readiness-review.json"
    if not report_path.exists():
        return None

    current_sources = [relative.as_posix() for relative in review_artifact_paths(feature_dir)]
    reviewed_sources = _reviewed_source_paths(report_path)
    if reviewed_sources is not None:
        current_set = set(current_sources)
        added_sources = sorted(current_set - reviewed_sources)
        removed_sources = sorted(reviewed_sources - current_set)
        if added_sources or removed_sources:
            parts: list[str] = []
            if added_sources:
                parts.append(f"new source file(s): {', '.join(added_sources)}")
            if removed_sources:
                parts.append(f"removed source file(s): {', '.join(removed_sources)}")
            return f"SpecGuard Review report may be stale; source artifact set changed ({'; '.join(parts)})"

    report_mtime = report_path.stat().st_mtime
    newer_sources = [
        relative
        for relative in current_sources
        if (feature_dir / relative).exists() and (feature_dir / relative).stat().st_mtime > report_mtime
    ]
    if not newer_sources:
        return None
    return f"SpecGuard Review report may be stale; newer source file(s): {', '.join(newer_sources)}"


def derive_plugin_run_state(
    feature_dir: Path,
    *,
    command: str,
    started_at: float | None = None,
    returncode: int | None = None,
    timed_out: bool = False,
    cli_available: bool = True,
    spec_package_exists: bool | None = None,
    provider_required: bool = False,
    provider_available: bool = True,
) -> PluginRunState:
    if not cli_available:
        return PluginRunState(
            state="missing_cli",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="missing_cli",
            next_action="Install SpecGuard or run from a source checkout where `python -m cli.specguard --help` works.",
        )

    if spec_package_exists is None:
        spec_package_exists = (feature_dir / "spec.md").exists()
    if not spec_package_exists:
        return PluginRunState(
            state="missing_spec_package",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="missing_spec_package",
            known_files=_known_plugin_files(feature_dir, include_handoff=False),
            next_action=_missing_spec_package_next_action(),
        )

    if provider_required and not provider_available:
        return PluginRunState(
            state="missing_provider_for_llm",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="missing_provider_for_llm",
            known_files=_known_plugin_files(feature_dir),
            next_action="Configure a provider with `specguard auth setup`, or rerun the default heuristic gate without LLM review.",
        )

    known_files = _known_plugin_files(feature_dir)
    if timed_out:
        return PluginRunState(
            state="timeout",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="timeout",
            known_files=known_files,
            next_action="Retry after checking provider status or increasing the configured timeout; do not start implementation from an incomplete run.",
        )

    report_path = feature_dir / "readiness-review.json"
    pre_review_state = _current_pre_review_run_state(feature_dir, command=command, started_at=started_at)
    if pre_review_state is not None:
        return pre_review_state

    if not report_path.exists():
        return PluginRunState(
            state="validation_failed_before_review",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="validation_failed_before_review",
            known_files=_known_plugin_files(feature_dir, include_handoff=False),
            next_action="Fix validation errors in the spec package, then rerun SpecGuard before using any old readiness report.",
        )

    stale_reason = readiness_report_stale_reason(feature_dir)
    if stale_reason:
        return PluginRunState(
            state="stale_review",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="stale_review",
            known_files=_known_plugin_files(feature_dir, include_handoff=False),
            next_action="Rerun `specguard run <package> --no-llm --no-follow-up` so the readiness report matches the current source artifacts.",
            stale_reason=stale_reason,
        )

    if started_at is not None and returncode not in {0, None} and report_path.stat().st_mtime < started_at:
        return PluginRunState(
            state="validation_failed_before_review",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="validation_failed_before_review",
            known_files=_known_plugin_files(feature_dir, include_handoff=False),
            next_action="Fix the pre-review failure and rerun SpecGuard; the older readiness report was not reused as the current result.",
        )

    report = _load_readiness_report_safely(feature_dir)
    if report is None:
        return PluginRunState(
            state="cli_execution_failed",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="cli_execution_failed",
            known_files=known_files,
            next_action="Rerun SpecGuard and inspect the readiness JSON file; the current report could not be loaded.",
        )

    state = _readiness_status(report)
    if state not in {"ready", "ready_with_warnings", "not_ready"}:
        return PluginRunState(
            state="cli_execution_failed",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="cli_execution_failed",
            known_files=known_files,
            next_action="Rerun SpecGuard and inspect readiness-review.json; the readiness status is missing or unsupported.",
        )

    if returncode not in {0, None} and state != "not_ready":
        return PluginRunState(
            state="cli_execution_failed",
            command=command,
            package_path=feature_dir.as_posix(),
            failure_category="cli_execution_failed",
            known_files=known_files,
            next_action="Fix the later pipeline failure and rerun SpecGuard before starting implementation.",
        )

    return PluginRunState(
        state=state,
        command=command,
        package_path=feature_dir.as_posix(),
        known_files=known_files,
        relevant_files=_relevant_plugin_files(feature_dir, report),
        next_action=_plugin_next_action(feature_dir, state, report),
    )


def _reviewed_source_paths(report_path: Path) -> set[str] | None:
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    source_input = payload.get("input")
    if not isinstance(source_input, dict):
        return None
    artifacts = source_input.get("artifacts")
    if not isinstance(artifacts, list):
        return None

    paths: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            return None
        path = artifact.get("path")
        if not isinstance(path, str):
            return None
        paths.add(path)
    return paths


def _load_readiness_report_safely(feature_dir: Path) -> dict[str, Any] | None:
    try:
        return load_readiness_report(feature_dir)
    except (OSError, json.JSONDecodeError):
        return None


def _current_pre_review_run_state(
    feature_dir: Path,
    *,
    command: str,
    started_at: float | None,
) -> PluginRunState | None:
    path = plugin_run_state_path(feature_dir)
    if not path.exists():
        return None

    state = _load_plugin_run_state(path, command=command, feature_dir=feature_dir)
    if state is None or state.state != "validation_failed_before_review":
        return None

    state_mtime = path.stat().st_mtime
    report_path = feature_dir / "readiness-review.json"
    if report_path.exists() and report_path.stat().st_mtime >= state_mtime:
        return None
    newer_sources = [
        relative
        for relative in review_artifact_paths(feature_dir)
        if (feature_dir / relative).exists() and (feature_dir / relative).stat().st_mtime > state_mtime
    ]
    if newer_sources:
        return None
    if started_at is not None and state_mtime < started_at:
        return None
    return state


def _load_plugin_run_state(path: Path, *, command: str, feature_dir: Path) -> PluginRunState | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != PLUGIN_RUN_STATE_SCHEMA_VERSION:
        return None
    state = payload.get("state")
    if not isinstance(state, str) or not state:
        return None

    relevant_files = _tuple_of_strings(payload.get("relevant_files"))
    if not relevant_files and state == "validation_failed_before_review":
        relevant_files = (path.as_posix(),)
    return PluginRunState(
        state=state,
        command=command,
        package_path=str(payload.get("package_path") or feature_dir.as_posix()),
        failure_category=_optional_string(payload.get("failure_category")) or state,
        failed_stage=_optional_string(payload.get("failed_stage")),
        messages=_tuple_of_strings(payload.get("messages")),
        next_steps=_tuple_of_strings(payload.get("next_steps")),
        known_files=_tuple_of_strings(payload.get("known_files")),
        relevant_files=relevant_files,
        next_action=str(payload.get("next_action") or "Fix validation errors in the spec package, then rerun SpecGuard."),
        stale_reason=_optional_string(payload.get("stale_reason")),
    )


def _plugin_run_state_payload(state: PluginRunState) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": PLUGIN_RUN_STATE_SCHEMA_VERSION,
        "state": state.state,
        "command": state.command,
        "package_path": state.package_path,
        "failure_category": state.failure_category,
        "failed_stage": state.failed_stage,
        "messages": list(state.messages),
        "next_steps": list(state.next_steps),
        "known_files": list(state.known_files),
        "relevant_files": list(state.relevant_files),
        "next_action": state.next_action,
    }
    if state.stale_reason is not None:
        payload["stale_reason"] = state.stale_reason
    return payload


def _tuple_of_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _known_plugin_files(feature_dir: Path, *, include_handoff: bool = True) -> tuple[str, ...]:
    names = [
        "readiness-review.json",
        "readiness-review.md",
        f"{SPECGUARD_STATE_DIR}/{PLUGIN_RUN_STATE_FILENAME}",
    ]
    if include_handoff:
        names.append("implementation-output.md")
    return tuple((feature_dir / name).as_posix() for name in names if (feature_dir / name).exists())


def _readiness_status(report: dict[str, Any]) -> str:
    readiness = report.get("readiness", {})
    status = readiness.get("status") if isinstance(readiness, dict) else None
    if report.get("blocked") or status == "not_ready":
        return "not_ready"
    return str(status or "unknown")


def _summary_count(summary: dict[str, Any], key: str) -> int:
    value = summary.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _default_plugin_rerun_command(feature_dir: Path) -> str:
    return f"specguard run {feature_dir.as_posix()} --no-llm --no-follow-up"


def _plugin_previous_report_files(feature_dir: Path) -> tuple[str, ...]:
    files = [
        feature_dir / "readiness-review.json",
        feature_dir / "readiness-review.md",
    ]
    return tuple(path.as_posix() for path in files if path.exists())


def _plugin_rerun_suggestions(report: dict[str, Any], *, limit: int) -> tuple[PluginRerunSuggestion, ...]:
    raw_issues = report.get("issues", [])
    if not isinstance(raw_issues, list) or limit <= 0:
        return ()

    suggestions: list[PluginRerunSuggestion] = []
    for issue in raw_issues:
        if not isinstance(issue, dict):
            continue
        suggestions.append(
            PluginRerunSuggestion(
                finding=_plugin_finding_title(issue),
                suggested_clarification=str(issue.get("fix") or "Review the full readiness report for the suggested clarification."),
                scope_check=(
                    "Needs user decision; do not invent product behavior or treat this suggestion as implementation "
                    "input until the user updates the spec package and reruns SpecGuard."
                ),
                next_step="User reviews and edits the spec package, then reruns SpecGuard.",
            )
        )
        if len(suggestions) >= limit:
            break
    return tuple(suggestions)


def _plugin_fresh_result_label(status: str) -> str:
    if status == "ready_with_warnings":
        return "ready with warnings"
    if status == "not_ready":
        return "still blocked"
    return status


def _plugin_top_findings(report: dict[str, Any], *, status: str, limit: int) -> tuple[str, ...]:
    raw_issues = report.get("issues", [])
    if not isinstance(raw_issues, list) or limit <= 0:
        return ()

    issues = [(index, issue) for index, issue in enumerate(raw_issues) if isinstance(issue, dict)]
    if status == "not_ready":
        critical = [(index, issue) for index, issue in issues if issue.get("severity") == "Critical"]
        non_critical = [(index, issue) for index, issue in issues if issue.get("severity") != "Critical"]
        ordered = critical + non_critical
    else:
        severity_rank = {"Critical": 0, "Major": 1, "Minor": 2}
        ordered = sorted(
            issues,
            key=lambda item: (severity_rank.get(str(item[1].get("severity")), 9), item[0]),
        )
    return tuple(_plugin_finding_title(issue) for _, issue in ordered[:limit])


def _plugin_finding_title(issue: dict[str, Any]) -> str:
    severity = str(issue.get("severity") or "Unknown")
    title = str(issue.get("title") or "Untitled issue")
    return f"[{severity}] {title}"


def _implementation_handoff_available(feature_dir: Path, report: dict[str, Any]) -> bool:
    readiness = report.get("readiness", {})
    implementation_ready = isinstance(readiness, dict) and readiness.get("implementation_ready") is True
    return (
        _readiness_status(report) in {"ready", "ready_with_warnings"}
        and implementation_ready
        and (feature_dir / "implementation-output.md").exists()
    )


def _plugin_summary_report_files(feature_dir: Path, *, handoff_available: bool) -> tuple[str, ...]:
    files = [
        feature_dir / "readiness-review.json",
        feature_dir / "readiness-review.md",
    ]
    if handoff_available:
        files.append(feature_dir / "implementation-output.md")
    return tuple(path.as_posix() for path in files if path.exists())


def _plugin_reviewed_artifacts(report: dict[str, Any]) -> tuple[str, ...]:
    source_input = report.get("input")
    if not isinstance(source_input, dict):
        return ()
    artifacts = source_input.get("artifacts")
    if not isinstance(artifacts, list):
        return ()

    paths: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        value = artifact.get("path")
        if not isinstance(value, str):
            continue
        normalized = PurePosixPath(value.replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts or not is_review_source_artifact(normalized):
            continue
        path = normalized.as_posix()
        if path not in paths:
            paths.append(path)
    return tuple(paths)


def _is_standard_review_artifact(path: str) -> bool:
    return path in {
        "discovery.md",
        "spec.md",
        "plan.md",
        "tasks.md",
        "constitution.md",
        "technical-design.md",
    } or path.startswith("checklists/")


def _render_plugin_artifact_summary(summary: PluginReadinessSummary) -> list[str]:
    lines = [f"- reviewed authored Markdown: {summary.reviewed_artifact_count}"]
    if summary.standard_reviewed_artifacts:
        lines.append("  - standard:")
        lines.extend(f"    - {path}" for path in summary.standard_reviewed_artifacts)
        hidden_standard = (
            summary.reviewed_artifact_count
            - summary.additional_authored_count
            - len(summary.standard_reviewed_artifacts)
        )
        if hidden_standard > 0:
            lines.append(f"    - ... {hidden_standard} more standard file(s)")
    if summary.additional_authored_artifacts:
        lines.append(f"  - additional: {summary.additional_authored_count}")
        lines.extend(f"    - {path}" for path in summary.additional_authored_artifacts)
        hidden = summary.additional_authored_count - len(summary.additional_authored_artifacts)
        if hidden > 0:
            lines.append(f"    - ... {hidden} more authored Markdown file(s)")
    else:
        lines.append("  - additional: none")
    return lines


def _plugin_human_report_path(feature_dir: Path) -> str | None:
    path = feature_dir / "readiness-review.md"
    return path.as_posix() if path.exists() else None


def _relevant_plugin_files(feature_dir: Path, report: dict[str, Any]) -> tuple[str, ...]:
    files = [
        feature_dir / "readiness-review.json",
        feature_dir / "readiness-review.md",
    ]
    if _implementation_handoff_available(feature_dir, report):
        files.append(feature_dir / "implementation-output.md")
    return tuple(path.as_posix() for path in files if path.exists())


def _plugin_next_action(feature_dir: Path, state: str, report: dict[str, Any]) -> str:
    if state == "not_ready":
        return "Fix the Critical readiness findings in the spec package, then rerun SpecGuard."
    if state == "ready_with_warnings":
        if _implementation_handoff_available(feature_dir, report):
            return "Implementation may proceed with warnings; use implementation-output.md as the implementation handoff."
        return "Rerun the full SpecGuard pipeline so implementation-output.md is generated before implementation starts."
    if state == "ready":
        if _implementation_handoff_available(feature_dir, report):
            return "Use implementation-output.md as the implementation handoff."
        return "Rerun the full SpecGuard pipeline so implementation-output.md is generated before implementation starts."
    return "Rerun SpecGuard after correcting the reported recovery state."


def _missing_spec_package_next_action() -> str:
    examples = " or ".join(SUPPORTED_PACKAGE_PATH_EXAMPLES)
    return (
        f"Create or select a SpecGuard package such as {examples}, then rerun `specguard discover <path>` "
        "before starting review; no SpecGuard readiness review has run yet."
    )


def generate_spec_revision(feature_dir: Path, llm_client: object, review_level: str | None = None) -> str:
    with progress_activity("assembling Spec Revision context"):
        discovery = _compact_text(_read_optional(feature_dir / "discovery.md"), 2500)
        spec = _compact_text(_read_optional(feature_dir / "spec.md"), 6000)
        plan = _compact_text(_read_optional(feature_dir / "plan.md"), 2500)
        tasks = _compact_text(_read_optional(feature_dir / "tasks.md"), 2500)
        constitution = _compact_text(_read_optional(feature_dir / "constitution.md"), 2500)
        checklist = _compact_text(_read_optional(feature_dir / "checklists" / "spec-readiness.md"), 2500)
        technical_design = _compact_text(_read_optional(feature_dir / "technical-design.md"), 3500)
        readiness_findings = _compact_readiness_findings(feature_dir, review_level=review_level)
        low_mode = (review_level or _readiness_report_level(feature_dir)).lower() == "low"
        priority_instruction = (
            "Prioritize Critical Readiness Findings. Treat Major and Minor findings as optional warning cleanup only; "
            "do not expand implementation scope to satisfy them."
            if low_mode
            else "Prioritize Critical and Major Readiness Findings."
        )
        instructions = "\n".join([
            "You are SpecGuard's spec refinement assistant and implementation-readiness editor.",
            "Revise spec.md so the Readiness Findings become explicit requirements, acceptance criteria, error cases, constraints, state rules, ownership rules, and contract expectations.",
            "Maintain consistency with plan.md, tasks.md, constitution.md, checklists/spec-readiness.md, and technical-design.md.",
            "SpecGuard is not prompt-to-code. Do not write application code.",
            "Return ONLY the full replacement Markdown for spec.md.",
            "Preserve the feature intent, user goal, existing acceptance coverage, and explicit out-of-scope decisions.",
            "Do not delete, weaken, or replace existing acceptance criteria unless the Readiness Findings directly require that change.",
            "Do not promote any documented out-of-scope or non-goal item into Requirements, Acceptance Criteria, or Error Cases.",
            "Preserve these exact level-2 headings because SpecGuard validates them: ## Requirements, ## Acceptance Criteria, ## Error Cases.",
            "Put at least one Markdown checklist or bullet item under ## Acceptance Criteria and at least one bullet item under ## Error Cases.",
            "Do not rename ## Acceptance Criteria to Acceptance Scenarios or place all criteria under another heading.",
            priority_instruction,
            "Do not include commentary, patch markers, or code fences.",
        ])
        input_text = "\n\n".join([
            "# Discovery excerpt",
            discovery,
            "# Current spec.md",
            spec,
            "# plan.md excerpt",
            plan,
            "# tasks.md excerpt",
            tasks,
            "# constitution.md excerpt",
            constitution,
            "# checklists/spec-readiness.md excerpt",
            checklist,
            "# technical-design.md excerpt",
            technical_design,
            "# Readiness Findings",
            readiness_findings,
        ])
    with progress_activity("waiting for LLM Spec Revision response"):
        generated = llm_client.generate_text(instructions, input_text, max_output_tokens=3000)
    with progress_activity("parsing revised spec markdown"):
        return _strip_markdown_fence(generated)


def apply_spec_revision(feature_dir: Path, revised_spec: str) -> Path:
    spec_path = feature_dir / "spec.md"
    spec_path.write_text(revised_spec.rstrip() + "\n", encoding="utf-8")
    return spec_path


def apply_spec_revision_with_audit(feature_dir: Path, revised_spec: str) -> SpecRevisionAudit:
    spec_path = feature_dir / "spec.md"
    original_spec = spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""
    normalized_revised = revised_spec.rstrip() + "\n"
    audit_dir = _unique_revision_audit_dir(feature_dir)
    original_path = audit_dir / "spec.original.md"
    diff_path = audit_dir / "spec.diff"

    audit_dir.mkdir(parents=True, exist_ok=False)
    original_path.write_text(original_spec, encoding="utf-8")
    diff_path.write_text(_spec_revision_diff(feature_dir, original_spec, normalized_revised), encoding="utf-8")
    spec_path.write_text(normalized_revised, encoding="utf-8")
    return SpecRevisionAudit(spec_path=spec_path, audit_dir=audit_dir, original_path=original_path, diff_path=diff_path)


def soften_low_mode_spec_revision(feature_dir: Path, revised_spec: str) -> SpecRevisionSoftening:
    original_spec = _read_optional(feature_dir / "spec.md")
    original_items = _out_of_scope_items(original_spec)
    if not original_items:
        return SpecRevisionSoftening(revised_spec)

    revised_without_promotions, demoted_items = _remove_promoted_out_of_scope_items(revised_spec, original_items)
    if not demoted_items:
        return SpecRevisionSoftening(revised_spec)

    revised_with_boundaries = _ensure_out_of_scope_boundaries(revised_without_promotions, demoted_items)
    return SpecRevisionSoftening(revised_with_boundaries, tuple(demoted_items))


def validate_spec_revision_intent(feature_dir: Path, revised_spec: str) -> CheckResult:
    result = CheckResult("Intent Preservation Check")
    original_spec = _read_optional(feature_dir / "spec.md")
    normalized_revised = _normalize(revised_spec)

    _check_title_intent(original_spec, revised_spec, result)
    _check_problem_intent(original_spec, normalized_revised, result)
    _check_acceptance_coverage(original_spec, normalized_revised, result)
    _check_out_of_scope(original_spec, revised_spec, result)

    if result.ok:
        result.add_info("Revised spec preserves title/problem intent, acceptance coverage, and out-of-scope boundaries.")
    else:
        result.add_next_step("Review the updated spec.md and SpecGuard audit diff before rerunning SpecGuard.")
    return result


def spec_revision_design_refresh_reason(original_spec: str, revised_spec: str) -> str | None:
    if _normalize(original_spec) == _normalize(revised_spec):
        return None

    changed_sections = _changed_sections(original_spec, revised_spec)
    if not changed_sections:
        return "changed content outside recognized spec sections"

    design_sections = sorted(section for section in changed_sections if section.lower() not in DESIGN_REUSE_SAFE_SECTIONS)
    if design_sections:
        return f"changed design-significant section(s): {', '.join(design_sections)}"

    diff_text = _normalized_diff_text(original_spec, revised_spec)
    for keyword in sorted(DESIGN_REFRESH_KEYWORDS):
        if keyword in diff_text:
            return f"changed acceptance wording references design-sensitive term: {keyword}"

    return None


def _unique_revision_audit_dir(feature_dir: Path) -> Path:
    state_root, feature_slug = _specguard_state_root(feature_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = state_root / SPEC_REVISION_AUDIT_DIR / feature_slug / timestamp
    if not base.exists():
        return base
    suffix = 2
    while True:
        candidate = base.with_name(f"{base.name}-{suffix}")
        if not candidate.exists():
            return candidate
        suffix += 1


def _specguard_state_root(feature_dir: Path) -> tuple[Path, str]:
    resolved = feature_dir.resolve()
    for parent in resolved.parents:
        if parent.name == "specs":
            relative = resolved.relative_to(parent)
            return parent.parent / SPECGUARD_STATE_DIR, _slugify_path(relative)
    return resolved.parent / SPECGUARD_STATE_DIR, _slugify_path(Path(resolved.name))


def _slugify_path(path: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", path.as_posix()).strip("-._")
    return slug or "feature"


def _spec_revision_diff(feature_dir: Path, original_spec: str, revised_spec: str) -> str:
    spec_path = feature_dir / "spec.md"
    display_path = _display_spec_path(spec_path, feature_dir)
    diff_lines = difflib.unified_diff(
        original_spec.splitlines(),
        revised_spec.splitlines(),
        fromfile=f"{display_path} (original)",
        tofile=f"{display_path} (updated)",
        lineterm="",
    )
    rendered = "\n".join(diff_lines)
    return rendered + "\n" if rendered else "No textual changes.\n"


def _display_spec_path(spec_path: Path, feature_dir: Path) -> str:
    resolved_spec = spec_path.resolve()
    for parent in feature_dir.resolve().parents:
        if parent.name == "specs":
            try:
                return resolved_spec.relative_to(parent.parent).as_posix()
            except ValueError:
                break
    return spec_path.as_posix()


def _read_optional(path: Path) -> str:
    if not path.exists():
        return f"{path.name} is missing."
    return path.read_text(encoding="utf-8")


def _compact_readiness_findings(feature_dir: Path, review_level: str | None = None) -> str:
    report = load_readiness_report(feature_dir)
    if not report:
        return _compact_text(_read_optional(feature_dir / "readiness-review.md"), 3000)

    issues = report.get("issues", [])
    if not isinstance(issues, list):
        return json.dumps(report, indent=2)

    low_mode = (review_level or str(report.get("review_level") or "")).lower() == "low"
    severity_rank = {"Critical": 0, "Major": 1, "Minor": 2}
    all_dict_issues = [issue for issue in issues if isinstance(issue, dict)]
    candidate_issues = all_dict_issues
    if low_mode:
        candidate_issues = [issue for issue in candidate_issues if issue.get("severity") == "Critical"]
    sorted_issues = sorted(
        candidate_issues,
        key=lambda issue: severity_rank.get(str(issue.get("severity")), 9),
    )
    lines = [
        (
            "Use these Critical Readiness Findings as the required revision backlog."
            if low_mode
            else "Use these Readiness Findings as the required revision backlog."
        ),
        f"Summary: {json.dumps(report.get('summary', {}), ensure_ascii=False)}",
        "",
    ]
    if low_mode and not sorted_issues:
        lines.append("No Critical blocker findings are present; Major and Minor findings are non-blocking warnings in low mode.")
        return "\n".join(lines)
    for index, issue in enumerate(sorted_issues[:12], start=1):
        lines.extend([
            f"{index}. [{issue.get('severity', 'Unknown')}] {issue.get('title', 'Untitled issue')}",
            f"   Impact: {issue.get('impact', 'Not specified.')}",
            f"   Required spec change: {issue.get('fix', 'Not specified.')}",
        ])
    if len(sorted_issues) > 12:
        lines.append(f"... {len(sorted_issues) - 12} additional minor/detail findings omitted from the prompt.")
    if low_mode and len(candidate_issues) < len(all_dict_issues):
        lines.append("Major and Minor findings are intentionally omitted from the low-mode required revision backlog.")
    return "\n".join(lines)


def _readiness_report_level(feature_dir: Path) -> str:
    report = load_readiness_report(feature_dir)
    if not report:
        return ""
    return str(report.get("review_level") or "")


def _compact_text(text: str, max_characters: int) -> str:
    if len(text) <= max_characters:
        return text
    head = max_characters // 2
    tail = max_characters - head
    return "\n".join([
        text[:head].rstrip(),
        "",
        f"... omitted {len(text) - max_characters} characters ...",
        "",
        text[-tail:].lstrip(),
    ])


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _check_title_intent(original_spec: str, revised_spec: str, result: CheckResult) -> None:
    original_title = _first_heading(original_spec)
    revised_title = _first_heading(revised_spec)
    if not original_title or not revised_title:
        return

    original_tokens = _keywords(original_title)
    if len(original_tokens) < 2:
        return
    revised_tokens = _keywords(revised_title)
    if len(original_tokens & revised_tokens) < min(2, len(original_tokens)):
        result.add_error(
            "Intent Preservation Check blocked spec revision: revised title no longer matches the original feature intent."
        )


def _check_problem_intent(original_spec: str, normalized_revised: str, result: CheckResult) -> None:
    problem = _section(original_spec, "Problem")
    if not problem:
        return

    problem_tokens = _keywords(problem)
    if len(problem_tokens) < 4:
        return

    preserved = sum(1 for token in problem_tokens if token in normalized_revised)
    if preserved / len(problem_tokens) < 0.5:
        result.add_error(
            "Intent Preservation Check blocked spec revision: revised spec no longer preserves the original Problem statement."
        )


def _check_acceptance_coverage(original_spec: str, normalized_revised: str, result: CheckResult) -> None:
    original_items = _list_items(_section(original_spec, "Acceptance Criteria"))
    if not original_items:
        return

    missing: list[str] = []
    for item in original_items:
        if not _item_is_preserved(item, normalized_revised):
            missing.append(item)

    if missing:
        preview = "; ".join(missing[:3])
        result.add_error(
            "Intent Preservation Check blocked spec revision: revised spec drops or weakens existing acceptance coverage "
            f"({preview})."
        )


def _check_out_of_scope(original_spec: str, revised_spec: str, result: CheckResult) -> None:
    original_items = _out_of_scope_items(original_spec)
    if not original_items:
        return

    revised_out_of_scope = _normalize("\n".join(_out_of_scope_sections(revised_spec)))
    protected_body = _normalize(
        "\n".join([
            _section(revised_spec, "Requirements"),
            _section(revised_spec, "Acceptance Criteria"),
            _section(revised_spec, "Error Cases"),
        ])
    )

    missing_boundaries: list[str] = []
    promoted_boundaries: list[str] = []
    for item in original_items:
        if not _item_is_preserved(item, revised_out_of_scope):
            missing_boundaries.append(item)

        tokens = _keywords(item)
        if len(tokens) >= 2 and tokens.issubset(set(protected_body.split())):
            promoted_boundaries.append(item)

    if missing_boundaries:
        preview = "; ".join(missing_boundaries[:3])
        result.add_error(
            "Intent Preservation Check blocked spec revision: revised spec drops documented out-of-scope boundaries "
            f"({preview})."
        )
    if promoted_boundaries:
        preview = "; ".join(promoted_boundaries[:3])
        result.add_error(
            "Intent Preservation Check blocked spec revision: revised spec appears to promote out-of-scope items into implementation scope "
            f"({preview})."
        )


def _remove_promoted_out_of_scope_items(revised_spec: str, original_items: list[str]) -> tuple[str, list[str]]:
    protected_headings = {"requirements", "acceptance criteria", "error cases"}
    demoted_items: list[str] = []
    current_heading = ""
    kept_lines: list[str] = []
    for line in revised_spec.splitlines():
        heading_match = re.match(r"^##\s+(.+?)\s*$", line)
        if heading_match:
            current_heading = heading_match.group(1).strip().lower()
            kept_lines.append(line)
            continue

        list_item = _list_item_text(line)
        if current_heading in protected_headings and list_item:
            promoted = _matching_out_of_scope_item(list_item, original_items)
            if promoted is not None:
                if promoted not in demoted_items:
                    demoted_items.append(promoted)
                continue
        kept_lines.append(line)
    return "\n".join(kept_lines).rstrip() + "\n", demoted_items


def _ensure_out_of_scope_boundaries(revised_spec: str, demoted_items: list[str]) -> str:
    revised_out_of_scope = _normalize("\n".join(_out_of_scope_sections(revised_spec)))
    missing_items = [item for item in demoted_items if not _item_is_preserved(item, revised_out_of_scope)]
    if not missing_items:
        return revised_spec

    lines = [revised_spec.rstrip(), "", "## Out of Scope", ""]
    lines.extend(f"- {item}" for item in missing_items)
    return "\n".join(lines).rstrip() + "\n"


def _list_item_text(line: str) -> str | None:
    stripped = line.strip()
    checklist = re.match(r"^[-*]\s+\[[ xX]\]\s+(.+)$", stripped)
    bullet = re.match(r"^[-*]\s+(.+)$", stripped)
    numbered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
    if checklist:
        return checklist.group(1).strip()
    if bullet:
        return bullet.group(1).strip()
    if numbered:
        return numbered.group(1).strip()
    return None


def _matching_out_of_scope_item(candidate: str, original_items: list[str]) -> str | None:
    candidate_tokens = set(_normalize(candidate).split())
    for item in original_items:
        tokens = _keywords(item)
        if len(tokens) >= 2 and tokens.issubset(candidate_tokens):
            return item
    return None


def _first_heading(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _section(content: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _sections(content: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", content, flags=re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[heading] = content[start:end].strip()
    return sections


def _changed_sections(original_spec: str, revised_spec: str) -> set[str]:
    original_sections = _sections(original_spec)
    revised_sections = _sections(revised_spec)
    headings = set(original_sections) | set(revised_sections)
    return {
        heading
        for heading in headings
        if _normalize(original_sections.get(heading, "")) != _normalize(revised_sections.get(heading, ""))
    }


def _normalized_diff_text(original_spec: str, revised_spec: str) -> str:
    diff_lines = difflib.unified_diff(
        original_spec.splitlines(),
        revised_spec.splitlines(),
        lineterm="",
    )
    return _normalize("\n".join(line for line in diff_lines if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))))


def _out_of_scope_sections(content: str) -> list[str]:
    sections: list[str] = []
    for heading in ("Out of Scope", "Non-goals", "Non Goals", "Non-goal"):
        section = _section(content, heading)
        if section:
            sections.append(section)
    return sections


def _out_of_scope_items(content: str) -> list[str]:
    items: list[str] = []
    for section in _out_of_scope_sections(content):
        items.extend(_list_items(section))
    return items


def _list_items(section: str) -> list[str]:
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        checklist = re.match(r"^[-*]\s+\[[ xX]\]\s+(.+)$", stripped)
        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        numbered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if checklist:
            items.append(checklist.group(1).strip())
        elif bullet:
            items.append(bullet.group(1).strip())
        elif numbered:
            items.append(numbered.group(1).strip())
    return items


def _item_is_preserved(item: str, normalized_target: str) -> bool:
    normalized_item = _normalize(item)
    if normalized_item and normalized_item in normalized_target:
        return True

    tokens = _keywords(item)
    if not tokens:
        return True
    target_tokens = set(normalized_target.split())
    overlap = len(tokens & target_tokens)
    required = min(3, max(1, len(tokens) - 1))
    return overlap >= required


def _keywords(text: str) -> set[str]:
    normalized = _normalize(text)
    return {
        token
        for token in normalized.split()
        if len(token) >= 4 and token not in _STOPWORDS
    }


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))
