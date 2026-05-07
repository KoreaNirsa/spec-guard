from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.llm_client import describe_llm_client
from tools.progress import progress_activity
from tools.result import CheckResult
from tools.ux import green, red, yellow


READINESS_READY_MINOR_LIMIT = 5
READINESS_WARNING_MAJOR_LIMIT = 2
READINESS_WARNING_MINOR_LIMIT = 10
READINESS_REVIEW_MODES = {"initial", "verification"}
READINESS_CACHE_SCHEMA_VERSION = "0.1"
READINESS_CACHE_PROMPT_VERSION = "readiness-review-v1"
SPECGUARD_STATE_DIR = ".specguard"
READINESS_CACHE_DIR = "readiness-cache"
GENERATED_ARTIFACT_NAMES = {
    "readiness-review.md",
    "readiness-review.json",
    "implementation-output.md",
    "spec.proposed.md",
    "grill.md",
    "grill.json",
}


READINESS_PROMPT = """You are SpecGuard's readiness review board: a principal software architect, security reviewer, reliability engineer, API contract reviewer, and test strategist.

Your task is NOT to approve the implementation basis.
Your task is to BREAK the implementation basis before a coding agent sees it.

Review every spec package artifact together: Discovery, spec, plan, tasks, constitution, checklists, technical design, and any other authored spec document.

Use the SpecGuard Review method:
- Find contradictions between artifacts.
- Attack missing requirements, undefined state, ambiguous ownership, weak contracts, unsafe retries, auth gaps, versioning gaps, and untestable acceptance criteria.
- Convert implementation guesses into Critical or Major findings.
- Treat style-only improvements as Minor.

Readiness thresholds:
- READY: Critical=0, Major=0, Minor<=5.
- READY_WITH_WARNINGS: Critical=0, Major<=2, Minor<=10.
- NOT_READY: Critical>=1, Major>=3, or Minor>10.

Critical findings always block implementation. Major findings should mean the implementer cannot complete required behavior without an important product, security, state, contract, persistence, or ownership decision. Best-practice suggestions, optional hardening, future extensibility, broad reliability improvements, and weakly evidenced risks should be Minor or omitted.
"""


@dataclass(frozen=True)
class ReadinessIssue:
    severity: str
    title: str
    description: str
    impact: str
    fix: str


@dataclass(frozen=True)
class ReviewArtifact:
    path: str
    content: str


@dataclass(frozen=True)
class CachedReview:
    cache_dir: Path
    cache_key: str
    payload: dict


def _contains(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _section(content: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _is_placeholder(text: str) -> bool:
    if not text.strip():
        return True
    for line in text.splitlines():
        stripped = line.strip().lower()
        if not stripped:
            continue
        bullet_text = stripped.lstrip("-*0123456789.[] x")
        if "{{ " in stripped or stripped.startswith("describe ") or stripped.startswith("- list "):
            return True
        if bullet_text in {"pending", "tbd"}:
            return True
    return False


def _review_artifacts(path: Path) -> list[ReviewArtifact]:
    preferred = [
        path / "discovery.md",
        path / "spec.md",
        path / "plan.md",
        path / "tasks.md",
        path / "constitution.md",
        path / "technical-design.md",
    ]
    preferred.extend(sorted((path / "checklists").glob("*.md")) if (path / "checklists").exists() else [])

    seen: set[Path] = set()
    artifacts: list[ReviewArtifact] = []
    for candidate in preferred + sorted(path.rglob("*.md")):
        if candidate in seen or not candidate.exists() or not candidate.is_file():
            continue
        seen.add(candidate)
        relative = candidate.relative_to(path)
        if candidate.name in GENERATED_ARTIFACT_NAMES:
            continue
        if relative.parts and relative.parts[0] == "tests":
            continue
        artifacts.append(ReviewArtifact(str(relative).replace("\\", "/"), candidate.read_text(encoding="utf-8")))
    return artifacts


def _artifact_content(artifacts: list[ReviewArtifact], name: str) -> str:
    for artifact in artifacts:
        if artifact.path == name:
            return artifact.content
    return ""


def _render_artifact_input(artifacts: list[ReviewArtifact]) -> str:
    return "\n\n".join([f"# Artifact: {artifact.path}\n\n{artifact.content}" for artifact in artifacts])


def _previous_findings_text(previous_report: dict | None) -> str:
    if not previous_report:
        return "No previous SpecGuard Review report was available."

    issues = previous_report.get("issues", [])
    if not isinstance(issues, list) or not issues:
        return "Previous SpecGuard Review had no findings."

    lines = [
        "Use these previous findings as the verification backlog.",
        f"Previous summary: {json.dumps(previous_report.get('summary', {}), ensure_ascii=False)}",
        "",
    ]
    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, dict):
            continue
        lines.extend([
            f"{index}. [{issue.get('severity', 'Unknown')}] {issue.get('title', 'Untitled issue')}",
            f"   Description: {issue.get('description', 'Not specified.')}",
            f"   Required fix: {issue.get('fix', 'Not specified.')}",
        ])
    return "\n".join(lines)


def _load_previous_report(path: Path) -> dict | None:
    report_path = path / "readiness-review.json"
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _readiness_cache_root(feature_dir: Path) -> tuple[Path, str]:
    resolved = feature_dir.resolve()
    for parent in resolved.parents:
        if parent.name == "specs":
            relative = resolved.relative_to(parent)
            return parent.parent / SPECGUARD_STATE_DIR / READINESS_CACHE_DIR, _slugify_path(relative)
    return resolved.parent / SPECGUARD_STATE_DIR / READINESS_CACHE_DIR, _slugify_path(Path(resolved.name))


def _slugify_path(path: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", path.as_posix()).strip("-._")
    return slug or "feature"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _client_cache_identity(llm_client: object) -> dict[str, str]:
    settings = getattr(llm_client, "settings", None)
    config = getattr(llm_client, "config", None)
    mode = getattr(settings, "mode", None)
    if not mode:
        mode = "openai" if config is not None else llm_client.__class__.__name__
    model = getattr(llm_client, "model", None) or getattr(settings, "model", None) or getattr(config, "model", None) or ""
    endpoint = getattr(settings, "endpoint", None) or getattr(config, "endpoint", None) or ""
    codex_profile = getattr(settings, "codex_profile", None) or ""

    return {
        "mode": str(mode),
        "model": str(model),
        "endpoint": str(endpoint),
        "codex_profile": str(codex_profile),
        "client_class": llm_client.__class__.__name__,
    }


def _review_artifact_manifest(artifacts: list[ReviewArtifact]) -> list[dict[str, object]]:
    return [
        {
            "path": artifact.path,
            "characters": len(artifact.content),
            "sha256": _sha256_text(artifact.content),
        }
        for artifact in artifacts
    ]


def _stable_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _build_llm_review_request(
    artifacts: list[ReviewArtifact],
    *,
    review_mode: str,
    previous_report: dict | None,
) -> tuple[str, str]:
    instructions = _verification_review_instructions() if review_mode == "verification" else _initial_review_instructions()
    input_text = _render_artifact_input(artifacts)
    if review_mode == "verification":
        input_text = "\n\n".join([
            "# Previous SpecGuard Review Findings",
            _previous_findings_text(previous_report),
            "# Current Spec Package Artifacts",
            input_text,
        ])
    return instructions, input_text


def _review_cache_metadata(
    artifacts: list[ReviewArtifact],
    *,
    review_mode: str,
    instructions: str,
    input_text: str,
    llm_client: object,
) -> tuple[str, dict[str, object]]:
    artifact_manifest = _review_artifact_manifest(artifacts)
    artifact_fingerprint = hashlib.sha256(_stable_json(artifact_manifest).encode("utf-8")).hexdigest()
    client_identity = _client_cache_identity(llm_client)
    metadata: dict[str, object] = {
        "schema_version": READINESS_CACHE_SCHEMA_VERSION,
        "prompt_version": READINESS_CACHE_PROMPT_VERSION,
        "review_mode": review_mode,
        "client": client_identity,
        "artifact_fingerprint": artifact_fingerprint,
        "input_fingerprint": _sha256_text(input_text),
        "instructions_fingerprint": _sha256_text(instructions),
        "artifact_count": len(artifacts),
        "total_input_characters": sum(len(artifact.content) for artifact in artifacts),
        "artifacts": artifact_manifest,
    }
    cache_key = hashlib.sha256(_stable_json(metadata).encode("utf-8")).hexdigest()
    metadata["cache_key"] = cache_key
    return cache_key, metadata


def _load_cached_review(feature_dir: Path, cache_key: str) -> CachedReview | None:
    cache_root, feature_slug = _readiness_cache_root(feature_dir)
    cache_dir = cache_root / feature_slug / cache_key
    report_path = cache_dir / "readiness-review.md"
    report_json_path = cache_dir / "readiness-review.json"
    metadata_path = cache_dir / "metadata.json"
    if not report_path.exists() or not report_json_path.exists() or not metadata_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(metadata, dict) or metadata.get("cache_key") != cache_key or not isinstance(payload, dict):
        return None
    return CachedReview(cache_dir=cache_dir, cache_key=cache_key, payload=payload)


def _copy_cached_review(cached: CachedReview, report_path: Path, report_json_path: Path) -> None:
    shutil.copyfile(cached.cache_dir / "readiness-review.md", report_path)
    shutil.copyfile(cached.cache_dir / "readiness-review.json", report_json_path)


def _store_cached_review(
    feature_dir: Path,
    cache_key: str,
    metadata: dict[str, object],
    report_path: Path,
    report_json_path: Path,
) -> Path:
    cache_root, feature_slug = _readiness_cache_root(feature_dir)
    cache_dir = cache_root / feature_slug / cache_key
    cache_dir.mkdir(parents=True, exist_ok=True)
    metadata = dict(metadata)
    metadata["created_at"] = datetime.now(timezone.utc).isoformat()
    (cache_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(report_path, cache_dir / "readiness-review.md")
    shutil.copyfile(report_json_path, cache_dir / "readiness-review.json")
    return cache_dir


def _analyze(artifacts: list[ReviewArtifact]) -> list[ReadinessIssue]:
    text = _render_artifact_input(artifacts).lower()
    technical_design = _artifact_content(artifacts, "technical-design.md")
    technical_design_text = technical_design.lower()
    issues: list[ReadinessIssue] = []

    architecture = _section(technical_design, "Architecture")
    data_flow = _section(technical_design, "Data Flow")
    state = _section(technical_design, "State")
    failure = _section(technical_design, "Failure Handling")

    if _is_placeholder(architecture):
        issues.append(ReadinessIssue(
            "Critical",
            "Architecture is still a placeholder",
            "The technical design does not name concrete components, ownership boundaries, or persistence responsibilities.",
            "AI implementation can invent architecture that conflicts with the intended workflow.",
            "Define the API layer, service layer, data store, external dependencies, and ownership for each decision.",
        ))

    if _is_placeholder(state):
        issues.append(ReadinessIssue(
            "Major",
            "State transitions are underspecified",
            "The design lists state headings but does not define valid transitions or invalid transitions.",
            "Race conditions and impossible states can slip into generated code.",
            "Add allowed states, transition rules, terminal states, and rejection behavior for invalid transitions.",
        ))

    if _is_placeholder(failure):
        issues.append(ReadinessIssue(
            "Major",
            "Failure handling is not actionable",
            "Timeout, retry, rollback, and fallback behavior are not specific enough to test.",
            "The implementation may retry unsafe operations or hide partial failures.",
            "Define per-dependency timeout, retry policy, idempotency requirement, and user-visible error response.",
        ))

    if _contains(text, "login", "password", "refresh token"):
        if not _contains(text, "expire", "ttl", "refresh"):
            issues.append(ReadinessIssue(
                "Critical",
                "Token lifecycle is missing",
                "Authentication is described without token expiration, refresh, revocation, or replay handling.",
                "Leaked or replayed tokens can remain valid longer than intended.",
                "Define access token TTL, refresh token rotation, revocation, and replay detection.",
            ))
        if not _contains(text, "rate limit", "lockout", "brute"):
            issues.append(ReadinessIssue(
                "Major",
                "Brute-force protection is missing",
                "Login failure behavior does not mention throttling, account lockout, or abuse monitoring.",
                "Attackers can automate credential guessing against the endpoint.",
                "Add rate limits by account and IP, progressive delay, audit logging, and lockout rules.",
            ))

    if _contains(text, "todo", "todos"):
        if not _contains(technical_design_text, "owner_user_id", "owner id", "authorization", "tenant"):
            issues.append(ReadinessIssue(
                "Critical",
                "Todo ownership boundary is unclear",
                "The technical design does not prove that users can only read or mutate their own todos.",
                "A generated API may expose cross-user data through list, update, or delete operations.",
                "Require owner-scoped queries and authorization checks for every todo read/write path.",
            ))
        if _contains(text, "delete") and not _contains(technical_design_text, "soft delete", "restore", "audit"):
            issues.append(ReadinessIssue(
                "Major",
                "Delete semantics are unsafe",
                "The spec allows deletion but does not define hard delete, soft delete, restore, or audit behavior.",
                "Data loss and compliance issues can appear after code generation.",
                "Choose hard or soft delete explicitly and define audit records, restore behavior, and API response codes.",
            ))

    if "external" in text and not _contains(text, "timeout", "retry", "fallback"):
        issues.append(ReadinessIssue(
            "Major",
            "External dependency failure path is absent",
            "The design mentions external dependencies without concrete timeout, retry, or fallback policy.",
            "The service can hang, duplicate side effects, or return inconsistent results.",
            "Define timeout budgets, retryable errors, non-retryable errors, and circuit-breaker behavior.",
        ))

    if _is_placeholder(data_flow):
        issues.append(ReadinessIssue(
            "Minor",
            "Data flow is too generic",
            "The data flow does not name concrete inputs, validation points, storage calls, or outputs.",
            "Tests generated from this design will be broad and weak.",
            "Rewrite the flow using request fields, validation rules, persistence calls, and response shapes.",
        ))

    if not issues:
        issues.append(ReadinessIssue(
            "Minor",
            "No obvious readiness triggers found",
            "The documents passed the built-in heuristic checks, but this is not a security review.",
            "Subtle domain-specific bugs may still exist.",
            "Run the strict SpecGuard Review prompt with a model and add human review before implementation.",
        ))

    return issues


def _parse_llm_issues(text: str) -> list[ReadinessIssue]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        payload = json.loads(cleaned[start:end + 1])

    raw_issues = payload.get("issues", []) if isinstance(payload, dict) else []
    issues: list[ReadinessIssue] = []
    for raw in raw_issues:
        if not isinstance(raw, dict):
            continue
        severity = str(raw.get("severity", "Minor")).title()
        if severity not in {"Critical", "Major", "Minor"}:
            severity = "Minor"
        issues.append(ReadinessIssue(
            severity=severity,
            title=str(raw.get("title", "Untitled LLM finding")),
            description=str(raw.get("description", "No description provided.")),
            impact=str(raw.get("impact", "Impact is not specified.")),
            fix=str(raw.get("fix", "Update the spec or technical design to make this explicit.")),
        ))
    if not issues:
        issues.append(ReadinessIssue(
            "Minor",
            "No LLM readiness findings returned",
            "The model returned no Critical, Major, or Minor findings.",
            "The local heuristic checks may still be useful as a backstop.",
            "Review the artifacts manually and rerun SpecGuard Review when the spec changes.",
        ))
    return _calibrate_issues(issues)


def _calibrate_issues(issues: list[ReadinessIssue]) -> list[ReadinessIssue]:
    calibrated: list[ReadinessIssue] = []
    for issue in issues:
        if issue.severity == "Major" and _major_should_downgrade(issue):
            calibrated.append(ReadinessIssue(
                "Minor",
                issue.title,
                issue.description,
                issue.impact,
                issue.fix,
            ))
            continue
        calibrated.append(issue)
    return calibrated


def _major_should_downgrade(issue: ReadinessIssue) -> bool:
    text = " ".join([issue.title, issue.description, issue.impact, issue.fix]).lower()
    non_blocking_markers = (
        "best practice",
        "best-practice",
        "optional",
        "future",
        "extensibility",
        "style",
        "naming",
        "cleanup",
        "polish",
        "nice to have",
        "could improve",
        "recommended hardening",
        "broad reliability",
        "weakly evidenced",
    )
    blocking_markers = (
        "cannot implement",
        "requires guessing",
        "must guess",
        "missing required",
        "contradict",
        "unsafe",
        "security",
        "authorization",
        "ownership",
        "state transition",
        "persistence",
        "data loss",
        "contract mismatch",
        "migration",
        "transaction",
        "idempotency",
    )
    return any(marker in text for marker in non_blocking_markers) and not any(marker in text for marker in blocking_markers)


def _initial_review_instructions() -> str:
    return "\n".join([
        "You are SpecGuard's readiness review board: principal architect, security reviewer, reliability engineer, API contract reviewer, and test strategist.",
        "Your task is NOT to approve the implementation basis. Your task is to break it before Codex or Claude Code implements from it.",
        "Analyze every provided spec artifact together, including Discovery, spec.md, plan.md, tasks.md, constitution.md, checklists, technical-design.md, and any additional authored spec document.",
        "Use SpecGuard Review: find contradictions, missing requirements, undefined state, security gaps, data ownership gaps, versioning gaps, weak contracts, untestable acceptance criteria, unsafe failure handling, and implementation assumptions.",
        _readiness_policy_prompt_line(),
        "Severity calibration: Critical means unsafe, contradictory, or impossible to implement deterministically; Major means implementation would require guessing or would miss an important product, security, state, contract, persistence, or ownership decision; Minor means useful cleanup that does not block implementation.",
        "Downgrade best-practice suggestions, optional hardening, future extensibility, broad reliability improvements, and weakly evidenced risks to Minor or omit them.",
        "Return ONLY JSON with this shape:",
        '{"issues":[{"severity":"Critical|Major|Minor","title":"...","description":"...","impact":"...","fix":"..."}]}',
        "Do not include positive feedback. Every finding must be actionable and mapped to a spec, plan, task, checklist, technical design, test, or contract update.",
    ])


def _verification_review_instructions() -> str:
    return "\n".join([
        "You are SpecGuard's Verification Review board.",
        "This is NOT a fresh broad SpecGuard Review. Verify whether the regenerated spec package resolves the previous Readiness Findings.",
        "Your primary job is to close, downgrade, or keep previous findings based on the current artifacts.",
        "Add a new Critical or Major finding only when there is direct evidence in the current artifacts that implementation would be unsafe, contradictory, or would require an important guess.",
        "Do not create new blockers for best-practice improvements, optional hardening, style, naming, or future extensibility. Those are Minor or omitted.",
        "Respect explicit out-of-scope, deferred, or accepted-risk decisions when they are documented in the spec package and do not contradict safety or contract requirements.",
        _readiness_policy_prompt_line(),
        "Severity calibration: Critical means a concrete unsafe/contradictory blocker remains; Major means a concrete implementation-critical decision is still missing; Minor means non-blocking clarity or polish.",
        "Return ONLY JSON with this shape:",
        '{"issues":[{"severity":"Critical|Major|Minor","title":"...","description":"...","impact":"...","fix":"..."}]}',
        "Every Critical or Major finding must cite evidence from the current artifacts and explain why it blocks implementation now.",
    ])


def _analyze_with_llm(
    llm_client: object,
    *,
    instructions: str,
    input_text: str,
) -> list[ReadinessIssue]:
    text = llm_client.generate_text(instructions, input_text, max_output_tokens=2500)
    return _parse_llm_issues(text)


def _render_group(title: str, issues: list[ReadinessIssue]) -> str:
    if not issues:
        return f"## {title}\n\n- None detected by the local heuristic engine.\n"

    lines = [f"## {title}", ""]
    for issue in issues:
        lines.extend([
            f"### {issue.title}",
            "",
            f"Description: {issue.description}",
            "",
            f"Impact: {issue.impact}",
            "",
            f"Fix: {issue.fix}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _build_summary(issues: list[ReadinessIssue]) -> dict[str, int]:
    return {
        "critical": sum(1 for issue in issues if issue.severity == "Critical"),
        "major": sum(1 for issue in issues if issue.severity == "Major"),
        "minor": sum(1 for issue in issues if issue.severity == "Minor"),
    }


def _readiness_status(summary: dict[str, int]) -> str:
    if summary["critical"] == 0 and summary["major"] == 0 and summary["minor"] <= READINESS_READY_MINOR_LIMIT:
        return "ready"
    if (
        summary["critical"] == 0
        and summary["major"] <= READINESS_WARNING_MAJOR_LIMIT
        and summary["minor"] <= READINESS_WARNING_MINOR_LIMIT
    ):
        return "ready_with_warnings"
    return "not_ready"


def _is_implementation_ready(summary: dict[str, int]) -> bool:
    return _readiness_status(summary) in {"ready", "ready_with_warnings"}


def _readiness_text(summary: dict[str, int]) -> str:
    status = _readiness_status(summary)
    if status == "ready":
        return f"Implementation-ready: Critical=0, Major=0, Minor<={READINESS_READY_MINOR_LIMIT}."
    if status == "ready_with_warnings":
        return (
            "Implementation-ready with warnings: "
            f"Critical=0, Major<={READINESS_WARNING_MAJOR_LIMIT}, Minor<={READINESS_WARNING_MINOR_LIMIT}."
        )
    return (
        "Not implementation-ready: requires no Critical findings, "
        f"Major<={READINESS_WARNING_MAJOR_LIMIT}, and Minor<={READINESS_WARNING_MINOR_LIMIT}."
    )


def _readiness_policy_prompt_line() -> str:
    return (
        "Readiness policy: READY when Critical=0, Major=0, Minor<=5; "
        "READY_WITH_WARNINGS when Critical=0, Major<=2, Minor<=10; "
        "NOT_READY when Critical>=1, Major>=3, or Minor>10."
    )


def _build_report(artifacts: list[ReviewArtifact], issues: list[ReadinessIssue], review_mode: str) -> str:
    summary = _build_summary(issues)
    status = _readiness_status(summary)
    critical = [issue for issue in issues if issue.severity == "Critical"]
    major = [issue for issue in issues if issue.severity == "Major"]
    minor = [issue for issue in issues if issue.severity == "Minor"]

    return "\n".join([
        "# SpecGuard Review Result",
        "",
        f"- Review mode: {review_mode}",
        "",
        "## Readiness",
        "",
        f"- Status: {status.upper()}",
        f"- READY criteria: Critical=0, Major=0, Minor<={READINESS_READY_MINOR_LIMIT}",
        f"- READY_WITH_WARNINGS criteria: Critical=0, Major<={READINESS_WARNING_MAJOR_LIMIT}, Minor<={READINESS_WARNING_MINOR_LIMIT}",
        f"- Current: Critical={summary['critical']}, Major={summary['major']}, Minor={summary['minor']}",
        "",
        _render_group("Critical Issues", critical),
        _render_group("Major Issues", major),
        _render_group("Minor Issues", minor),
        "## Improvement Suggestions",
        "",
        "- Convert every Critical item into acceptance criteria before implementation.",
        "- Review Major warning items before implementation and either accept the risk or clarify the spec package.",
        "- Add tests for authorization, invalid state, retry, timeout, and duplicate request behavior.",
        "- Re-run `specguard run` after updating `spec.md` and `technical-design.md`.",
        "",
        "## Prompt Mode",
        "",
        "```text",
        READINESS_PROMPT.strip(),
        "```",
        "",
        "## Input Summary",
        "",
        *[f"- {artifact.path}: {len(artifact.content)} characters" for artifact in artifacts],
        "",
    ])


def _build_json_report(artifacts: list[ReviewArtifact], issues: list[ReadinessIssue], review_mode: str) -> str:
    summary = _build_summary(issues)
    status = _readiness_status(summary)
    artifact_lengths = {artifact.path: len(artifact.content) for artifact in artifacts}
    total_characters = sum(artifact_lengths.values())
    payload = {
        "schema_version": "0.1",
        "review_mode": review_mode,
        "blocked": not _is_implementation_ready(summary),
        "readiness": {
            "implementation_ready": _is_implementation_ready(summary),
            "criteria": {
                "ready": {
                    "critical": 0,
                    "major": 0,
                    "minor_max": READINESS_READY_MINOR_LIMIT,
                },
                "ready_with_warnings": {
                    "critical": 0,
                    "major_max": READINESS_WARNING_MAJOR_LIMIT,
                    "minor_max": READINESS_WARNING_MINOR_LIMIT,
                },
            },
            "status": status,
        },
        "summary": summary,
        "issues": [asdict(issue) for issue in issues],
        "input": {
            "artifact_count": len(artifacts),
            "total_characters": total_characters,
            "discovery_characters": artifact_lengths.get("discovery.md", 0),
            "spec_characters": artifact_lengths.get("spec.md", 0),
            "technical_design_characters": artifact_lengths.get("technical-design.md", 0),
            "artifacts": [{"path": artifact.path, "characters": len(artifact.content)} for artifact in artifacts],
        },
        "prompt_mode": READINESS_PROMPT.strip(),
    }
    return json.dumps(payload, indent=2) + "\n"


def run_readiness_review(path: Path, llm_client: object | None = None, review_mode: str = "initial") -> CheckResult:
    if review_mode not in READINESS_REVIEW_MODES:
        raise ValueError(f"Unsupported SpecGuard Review mode: {review_mode}")

    result = CheckResult("SpecGuard Review")
    discovery_path = path / "discovery.md"
    spec_path = path / "spec.md"
    technical_design_path = path / "technical-design.md"
    report_path = path / "readiness-review.md"
    report_json_path = path / "readiness-review.json"

    if not discovery_path.exists():
        result.add_error(f"Missing discovery file: {discovery_path}")
        return result
    if not spec_path.exists():
        result.add_error(f"Missing spec file: {spec_path}")
        return result
    if not technical_design_path.exists():
        result.add_error(f"Missing technical design file: {technical_design_path}")
        return result

    artifacts = _review_artifacts(path)
    total_input_characters = sum(len(artifact.content) for artifact in artifacts)
    previous_report = _load_previous_report(path) if review_mode == "verification" else None
    mode = "LLM" if llm_client else "heuristic"
    cache_hit: CachedReview | None = None
    cache_key = ""
    cache_metadata: dict[str, object] | None = None
    llm_elapsed_ms: int | None = None
    llm_summary = describe_llm_client(llm_client) if llm_client else ""
    try:
        if llm_client:
            instructions, input_text = _build_llm_review_request(
                artifacts,
                review_mode=review_mode,
                previous_report=previous_report,
            )
            cache_key, cache_metadata = _review_cache_metadata(
                artifacts,
                review_mode=review_mode,
                instructions=instructions,
                input_text=input_text,
                llm_client=llm_client,
            )
            cache_hit = _load_cached_review(path, cache_key)
            if cache_hit:
                _copy_cached_review(cache_hit, report_path, report_json_path)
                issues = _parse_llm_issues(json.dumps({"issues": cache_hit.payload.get("issues", [])}))
            else:
                activity = (
                    f"waiting for LLM SpecGuard Review "
                    f"({llm_summary}, {review_mode}, {len(artifacts)} artifacts, {total_input_characters} chars)"
                )
                started = time.perf_counter()
                with progress_activity(activity):
                    issues = _analyze_with_llm(llm_client, instructions=instructions, input_text=input_text)
                llm_elapsed_ms = int((time.perf_counter() - started) * 1000)
        else:
            issues = _analyze(artifacts)
    except (json.JSONDecodeError, ValueError) as exc:
        result.add_error(f"LLM SpecGuard Review response could not be parsed as JSON: {exc}")
        return result
    summary = _build_summary(issues)
    critical_count = summary["critical"]
    major_count = summary["major"]
    minor_count = summary["minor"]
    implementation_ready = _is_implementation_ready(summary)

    if not cache_hit:
        report_path.write_text(_build_report(artifacts, issues, review_mode), encoding="utf-8")
        report_json_path.write_text(_build_json_report(artifacts, issues, review_mode), encoding="utf-8")
        if llm_client and cache_metadata is not None:
            _store_cached_review(path, cache_key, cache_metadata, report_path, report_json_path)
    result.details.update(summary)
    if cache_hit:
        result.details["cache_hit"] = True
        result.details["cache_key"] = cache_key
        result.add_info(f"Reused cached {mode} {review_mode} readiness report: {report_path}")
        result.add_info(f"Reused cached {mode} {review_mode} machine-readable readiness report: {report_json_path}")
        result.add_info(f"SpecGuard Review cache hit: {cache_key[:12]} ({cache_hit.cache_dir})")
    else:
        result.add_info(f"Generated {mode} {review_mode} readiness report: {report_path}")
        result.add_info(f"Generated {mode} {review_mode} machine-readable readiness report: {report_json_path}")
        if llm_client and cache_key:
            result.details["cache_hit"] = False
            result.details["cache_key"] = cache_key
            result.add_info(f"SpecGuard Review cache stored: {cache_key[:12]}")
    result.add_info(f"Reviewed spec artifacts: {', '.join(artifact.path for artifact in artifacts)}")
    result.add_info(f"SpecGuard Review input size: {len(artifacts)} artifact(s), {total_input_characters} characters.")
    if llm_elapsed_ms is not None:
        result.details[f"{review_mode}_llm_review_ms"] = llm_elapsed_ms
        result.add_info(
            f"LLM {review_mode} SpecGuard Review call: {llm_summary}, "
            f"{len(artifacts)} artifact(s), {total_input_characters} characters, {llm_elapsed_ms}ms."
        )
    if implementation_ready:
        if _readiness_status(summary) == "ready_with_warnings":
            result.add_info(yellow(f"[READY_WITH_WARNINGS] {_readiness_text(summary)} Current: {critical_count} critical, {major_count} major, {minor_count} minor."))
            result.add_next_step(f"Review warning findings in: {report_path}")
        else:
            result.add_info(green(f"[READY] {_readiness_text(summary)} Current: {critical_count} critical, {major_count} major, {minor_count} minor."))
    else:
        result.add_error(red(f"[NOT READY] {_readiness_text(summary)} Current: {critical_count} critical, {major_count} major, {minor_count} minor."))
        result.add_next_step(f"Open the human report: {report_path}")
        result.add_next_step(f"Use the machine-readable report for automation: {report_json_path}")
        result.add_next_step(
            "Fix spec package artifacts so Critical and Major issues become explicit requirements or verified constraints, and Minor findings stay within the readiness threshold."
        )
        result.add_next_step("Do not start external AI implementation until SpecGuard reports READY and writes implementation-output.md.")
        result.add_next_step(f"Run again: specguard run {path}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    result = run_readiness_review(Path(args.path))
    result.print()
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
