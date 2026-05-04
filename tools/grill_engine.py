from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.result import CheckResult
from tools.ux import green, red


GRILL_MINOR_READY_LIMIT = 5


GRILL_PROMPT = """You are SpecGuard's Grill Review board: a principal software architect, security reviewer, reliability engineer, API contract reviewer, and test strategist.

Your task is NOT to approve the implementation basis.
Your task is to BREAK the implementation basis before a coding agent sees it.

Review every spec package artifact together: Discovery, spec, plan, tasks, constitution, checklists, technical design, and any other authored spec document.

Use the Grill Review technique:
- Find contradictions between artifacts.
- Attack missing requirements, undefined state, ambiguous ownership, weak contracts, unsafe retries, auth gaps, versioning gaps, and untestable acceptance criteria.
- Convert implementation guesses into Critical or Major findings.
- Treat style-only improvements as Minor.

Implementation-ready threshold:
- Critical: 0
- Major: 0
- Minor: 5 or fewer, and none may hide a requirement ambiguity.
"""


@dataclass(frozen=True)
class GrillIssue:
    severity: str
    title: str
    description: str
    impact: str
    fix: str


@dataclass(frozen=True)
class ReviewArtifact:
    path: str
    content: str


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

    excluded_names = {"grill.md", "implementation-output.md"}
    seen: set[Path] = set()
    artifacts: list[ReviewArtifact] = []
    for candidate in preferred + sorted(path.rglob("*.md")):
        if candidate in seen or not candidate.exists() or not candidate.is_file():
            continue
        seen.add(candidate)
        relative = candidate.relative_to(path)
        if candidate.name in excluded_names:
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


def _analyze(artifacts: list[ReviewArtifact]) -> list[GrillIssue]:
    text = _render_artifact_input(artifacts).lower()
    technical_design = _artifact_content(artifacts, "technical-design.md")
    technical_design_text = technical_design.lower()
    issues: list[GrillIssue] = []

    architecture = _section(technical_design, "Architecture")
    data_flow = _section(technical_design, "Data Flow")
    state = _section(technical_design, "State")
    failure = _section(technical_design, "Failure Handling")

    if _is_placeholder(architecture):
        issues.append(GrillIssue(
            "Critical",
            "Architecture is still a placeholder",
            "The technical design does not name concrete components, ownership boundaries, or persistence responsibilities.",
            "AI implementation can invent architecture that conflicts with the intended workflow.",
            "Define the API layer, service layer, data store, external dependencies, and ownership for each decision.",
        ))

    if _is_placeholder(state):
        issues.append(GrillIssue(
            "Major",
            "State transitions are underspecified",
            "The design lists state headings but does not define valid transitions or invalid transitions.",
            "Race conditions and impossible states can slip into generated code.",
            "Add allowed states, transition rules, terminal states, and rejection behavior for invalid transitions.",
        ))

    if _is_placeholder(failure):
        issues.append(GrillIssue(
            "Major",
            "Failure handling is not actionable",
            "Timeout, retry, rollback, and fallback behavior are not specific enough to test.",
            "The implementation may retry unsafe operations or hide partial failures.",
            "Define per-dependency timeout, retry policy, idempotency requirement, and user-visible error response.",
        ))

    if _contains(text, "login", "password", "refresh token"):
        if not _contains(text, "expire", "ttl", "refresh"):
            issues.append(GrillIssue(
                "Critical",
                "Token lifecycle is missing",
                "Authentication is described without token expiration, refresh, revocation, or replay handling.",
                "Leaked or replayed tokens can remain valid longer than intended.",
                "Define access token TTL, refresh token rotation, revocation, and replay detection.",
            ))
        if not _contains(text, "rate limit", "lockout", "brute"):
            issues.append(GrillIssue(
                "Major",
                "Brute-force protection is missing",
                "Login failure behavior does not mention throttling, account lockout, or abuse monitoring.",
                "Attackers can automate credential guessing against the endpoint.",
                "Add rate limits by account and IP, progressive delay, audit logging, and lockout rules.",
            ))

    if _contains(text, "todo", "todos"):
        if not _contains(technical_design_text, "owner_user_id", "owner id", "authorization", "tenant"):
            issues.append(GrillIssue(
                "Critical",
                "Todo ownership boundary is unclear",
                "The technical design does not prove that users can only read or mutate their own todos.",
                "A generated API may expose cross-user data through list, update, or delete operations.",
                "Require owner-scoped queries and authorization checks for every todo read/write path.",
            ))
        if _contains(text, "delete") and not _contains(technical_design_text, "soft delete", "restore", "audit"):
            issues.append(GrillIssue(
                "Major",
                "Delete semantics are unsafe",
                "The spec allows deletion but does not define hard delete, soft delete, restore, or audit behavior.",
                "Data loss and compliance issues can appear after code generation.",
                "Choose hard or soft delete explicitly and define audit records, restore behavior, and API response codes.",
            ))

    if "external" in text and not _contains(text, "timeout", "retry", "fallback"):
        issues.append(GrillIssue(
            "Major",
            "External dependency failure path is absent",
            "The design mentions external dependencies without concrete timeout, retry, or fallback policy.",
            "The service can hang, duplicate side effects, or return inconsistent results.",
            "Define timeout budgets, retryable errors, non-retryable errors, and circuit-breaker behavior.",
        ))

    if _is_placeholder(data_flow):
        issues.append(GrillIssue(
            "Minor",
            "Data flow is too generic",
            "The data flow does not name concrete inputs, validation points, storage calls, or outputs.",
            "Tests generated from this design will be broad and weak.",
            "Rewrite the flow using request fields, validation rules, persistence calls, and response shapes.",
        ))

    if not issues:
        issues.append(GrillIssue(
            "Minor",
            "No obvious grill triggers found",
            "The documents passed the built-in heuristic checks, but this is not a security review.",
            "Subtle domain-specific bugs may still exist.",
            "Run the strict Grill Me prompt with a model and add human review before implementation.",
        ))

    return issues


def _parse_llm_issues(text: str) -> list[GrillIssue]:
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
    issues: list[GrillIssue] = []
    for raw in raw_issues:
        if not isinstance(raw, dict):
            continue
        severity = str(raw.get("severity", "Minor")).title()
        if severity not in {"Critical", "Major", "Minor"}:
            severity = "Minor"
        issues.append(GrillIssue(
            severity=severity,
            title=str(raw.get("title", "Untitled LLM finding")),
            description=str(raw.get("description", "No description provided.")),
            impact=str(raw.get("impact", "Impact is not specified.")),
            fix=str(raw.get("fix", "Update the spec or technical design to make this explicit.")),
        ))
    if not issues:
        issues.append(GrillIssue(
            "Minor",
            "No LLM grill findings returned",
            "The model returned no Critical, Major, or Minor findings.",
            "The local heuristic checks may still be useful as a backstop.",
            "Review the artifacts manually and rerun Grill Me when the spec changes.",
        ))
    return issues


def _analyze_with_llm(artifacts: list[ReviewArtifact], llm_client: object) -> list[GrillIssue]:
    instructions = "\n".join([
        "You are SpecGuard's Grill Review board: principal architect, security reviewer, reliability engineer, API contract reviewer, and test strategist.",
        "Your task is NOT to approve the implementation basis. Your task is to break it before Codex or Claude Code implements from it.",
        "Analyze every provided spec artifact together, including Discovery, spec.md, plan.md, tasks.md, constitution.md, checklists, technical-design.md, and any additional authored spec document.",
        "Use Grill Review: find contradictions, missing requirements, undefined state, security gaps, data ownership gaps, versioning gaps, weak contracts, untestable acceptance criteria, unsafe failure handling, and implementation assumptions.",
        f"Readiness policy: implementation is allowed only when Critical=0, Major=0, and Minor<={GRILL_MINOR_READY_LIMIT}.",
        "Severity calibration: Critical means unsafe, contradictory, or impossible to implement deterministically; Major means implementation would require guessing or would miss an important test/contract; Minor means useful cleanup that does not block implementation.",
        "Return ONLY JSON with this shape:",
        '{"issues":[{"severity":"Critical|Major|Minor","title":"...","description":"...","impact":"...","fix":"..."}]}',
        "Do not include positive feedback. Every finding must be actionable and mapped to a spec, plan, task, checklist, technical design, test, or contract update.",
    ])
    input_text = _render_artifact_input(artifacts)
    text = llm_client.generate_text(instructions, input_text, max_output_tokens=2500)
    return _parse_llm_issues(text)


def _render_group(title: str, issues: list[GrillIssue]) -> str:
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


def _build_summary(issues: list[GrillIssue]) -> dict[str, int]:
    return {
        "critical": sum(1 for issue in issues if issue.severity == "Critical"),
        "major": sum(1 for issue in issues if issue.severity == "Major"),
        "minor": sum(1 for issue in issues if issue.severity == "Minor"),
    }


def _is_implementation_ready(summary: dict[str, int]) -> bool:
    return summary["critical"] == 0 and summary["major"] == 0 and summary["minor"] <= GRILL_MINOR_READY_LIMIT


def _readiness_text(summary: dict[str, int]) -> str:
    if _is_implementation_ready(summary):
        return f"Implementation-ready: Critical=0, Major=0, Minor<={GRILL_MINOR_READY_LIMIT}."
    return f"Not implementation-ready: requires Critical=0, Major=0, Minor<={GRILL_MINOR_READY_LIMIT}."


def _build_report(artifacts: list[ReviewArtifact], issues: list[GrillIssue]) -> str:
    summary = _build_summary(issues)
    critical = [issue for issue in issues if issue.severity == "Critical"]
    major = [issue for issue in issues if issue.severity == "Major"]
    minor = [issue for issue in issues if issue.severity == "Minor"]

    return "\n".join([
        "# Grill Result",
        "",
        "## Readiness",
        "",
        f"- Status: {'READY' if _is_implementation_ready(summary) else 'NOT READY'}",
        f"- Criteria: Critical=0, Major=0, Minor<={GRILL_MINOR_READY_LIMIT}",
        f"- Current: Critical={summary['critical']}, Major={summary['major']}, Minor={summary['minor']}",
        "",
        _render_group("Critical Issues", critical),
        _render_group("Major Issues", major),
        _render_group("Minor Issues", minor),
        "## Improvement Suggestions",
        "",
        "- Convert every Critical and Major item into acceptance criteria before implementation.",
        "- Add tests for authorization, invalid state, retry, timeout, and duplicate request behavior.",
        "- Re-run `specguard run` after updating `spec.md` and `technical-design.md`.",
        "",
        "## Prompt Mode",
        "",
        "```text",
        GRILL_PROMPT.strip(),
        "```",
        "",
        "## Input Summary",
        "",
        *[f"- {artifact.path}: {len(artifact.content)} characters" for artifact in artifacts],
        "",
    ])


def _build_json_report(artifacts: list[ReviewArtifact], issues: list[GrillIssue]) -> str:
    summary = _build_summary(issues)
    artifact_lengths = {artifact.path: len(artifact.content) for artifact in artifacts}
    payload = {
        "schema_version": "0.1",
        "blocked": not _is_implementation_ready(summary),
        "readiness": {
            "implementation_ready": _is_implementation_ready(summary),
            "criteria": {
                "critical": 0,
                "major": 0,
                "minor_max": GRILL_MINOR_READY_LIMIT,
            },
            "status": "ready" if _is_implementation_ready(summary) else "not_ready",
        },
        "summary": summary,
        "issues": [asdict(issue) for issue in issues],
        "input": {
            "discovery_characters": artifact_lengths.get("discovery.md", 0),
            "spec_characters": artifact_lengths.get("spec.md", 0),
            "technical_design_characters": artifact_lengths.get("technical-design.md", 0),
            "artifacts": [{"path": artifact.path, "characters": len(artifact.content)} for artifact in artifacts],
        },
        "prompt_mode": GRILL_PROMPT.strip(),
    }
    return json.dumps(payload, indent=2) + "\n"


def run_grill(path: Path, llm_client: object | None = None) -> CheckResult:
    result = CheckResult("Grill Me")
    discovery_path = path / "discovery.md"
    spec_path = path / "spec.md"
    technical_design_path = path / "technical-design.md"
    grill_path = path / "grill.md"
    grill_json_path = path / "grill.json"

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
    try:
        issues = _analyze_with_llm(artifacts, llm_client) if llm_client else _analyze(artifacts)
    except (json.JSONDecodeError, ValueError) as exc:
        result.add_error(f"LLM Grill Me response could not be parsed as JSON: {exc}")
        return result
    summary = _build_summary(issues)
    critical_count = summary["critical"]
    major_count = summary["major"]
    minor_count = summary["minor"]
    implementation_ready = _is_implementation_ready(summary)

    grill_path.write_text(_build_report(artifacts, issues), encoding="utf-8")
    grill_json_path.write_text(_build_json_report(artifacts, issues), encoding="utf-8")
    result.details.update(summary)
    mode = "LLM" if llm_client else "heuristic"
    result.add_info(f"Generated {mode} grill report: {grill_path}")
    result.add_info(f"Generated {mode} machine-readable grill report: {grill_json_path}")
    result.add_info(f"Reviewed spec artifacts: {', '.join(artifact.path for artifact in artifacts)}")
    if implementation_ready:
        result.add_info(green(f"[READY] {_readiness_text(summary)} Current: {critical_count} critical, {major_count} major, {minor_count} minor."))
    else:
        result.add_error(red(f"[NOT READY] {_readiness_text(summary)} Current: {critical_count} critical, {major_count} major, {minor_count} minor."))
        result.add_next_step(f"Open the human report: {grill_path}")
        result.add_next_step(f"Use the machine-readable report for automation: {grill_json_path}")
        result.add_next_step(
            "Fix spec package artifacts so Critical and Major issues become explicit requirements or verified constraints, and Minor findings stay within the readiness threshold."
        )
        result.add_next_step(f"Run again: specguard run {path}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    result = run_grill(Path(args.path))
    result.print()
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
