from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.result import CheckResult


GRILL_PROMPT = """You are a senior software architect, security expert, and reliability engineer.

Your task is NOT to approve the design.
Your task is to BREAK the design.

Analyze the design aggressively and identify logic flaws, edge cases,
security issues, performance risks, and failure scenarios.
"""


@dataclass(frozen=True)
class GrillIssue:
    severity: str
    title: str
    description: str
    impact: str
    fix: str


def _contains(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _section(content: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _is_placeholder(text: str) -> bool:
    lowered = text.lower()
    return not text.strip() or _contains(lowered, "describe ", "list ", "pending", "tbd")


def _analyze(spec: str, design: str) -> list[GrillIssue]:
    text = f"{spec}\n{design}".lower()
    design_text = design.lower()
    issues: list[GrillIssue] = []

    architecture = _section(design, "Architecture")
    data_flow = _section(design, "Data Flow")
    state = _section(design, "State")
    failure = _section(design, "Failure Handling")

    if _is_placeholder(architecture):
        issues.append(GrillIssue(
            "Critical",
            "Architecture is still a placeholder",
            "The design does not name concrete components, ownership boundaries, or persistence responsibilities.",
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

    if _contains(text, "todo", "task"):
        if not _contains(design_text, "owner_user_id", "owner id", "authorization", "tenant"):
            issues.append(GrillIssue(
                "Critical",
                "Todo ownership boundary is unclear",
                "The design does not prove that users can only read or mutate their own todos.",
                "A generated API may expose cross-user data through list, update, or delete operations.",
                "Require owner-scoped queries and authorization checks for every todo read/write path.",
            ))
        if _contains(text, "delete") and not _contains(design_text, "soft delete", "restore", "audit"):
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


def _build_report(spec: str, design: str, issues: list[GrillIssue]) -> str:
    critical = [issue for issue in issues if issue.severity == "Critical"]
    major = [issue for issue in issues if issue.severity == "Major"]
    minor = [issue for issue in issues if issue.severity == "Minor"]

    return "\n".join([
        "# Grill Result",
        "",
        _render_group("Critical Issues", critical),
        _render_group("Major Issues", major),
        _render_group("Minor Issues", minor),
        "## Improvement Suggestions",
        "",
        "- Convert every Critical and Major item into acceptance criteria before implementation.",
        "- Add tests for authorization, invalid state, retry, timeout, and duplicate request behavior.",
        "- Re-run `specguard run` after updating `spec.md` and `design.md`.",
        "",
        "## Prompt Mode",
        "",
        "```text",
        GRILL_PROMPT.strip(),
        "```",
        "",
        "## Input Summary",
        "",
        f"- Spec characters: {len(spec)}",
        f"- Design characters: {len(design)}",
        "",
    ])


def _build_json_report(spec: str, design: str, issues: list[GrillIssue]) -> str:
    summary = _build_summary(issues)
    payload = {
        "schema_version": "0.1",
        "blocked": bool(summary["critical"] or summary["major"]),
        "summary": summary,
        "issues": [asdict(issue) for issue in issues],
        "input": {
            "spec_characters": len(spec),
            "design_characters": len(design),
        },
        "prompt_mode": GRILL_PROMPT.strip(),
    }
    return json.dumps(payload, indent=2) + "\n"


def run_grill(path: Path) -> CheckResult:
    result = CheckResult("Grill Me")
    spec_path = path / "spec.md"
    design_path = path / "design.md"
    grill_path = path / "grill.md"
    grill_json_path = path / "grill.json"

    if not spec_path.exists():
        result.add_error(f"Missing spec file: {spec_path}")
        return result
    if not design_path.exists():
        result.add_error(f"Missing design file: {design_path}")
        return result

    spec = spec_path.read_text(encoding="utf-8")
    design = design_path.read_text(encoding="utf-8")
    issues = _analyze(spec, design)
    summary = _build_summary(issues)
    critical_count = summary["critical"]
    major_count = summary["major"]

    grill_path.write_text(_build_report(spec, design, issues), encoding="utf-8")
    grill_json_path.write_text(_build_json_report(spec, design, issues), encoding="utf-8")
    result.details.update(summary)
    result.add_info(f"Generated concrete grill report: {grill_path}")
    result.add_info(f"Generated machine-readable grill report: {grill_json_path}")
    if critical_count or major_count:
        result.add_error(f"Blocked by Grill Me findings: {critical_count} critical, {major_count} major")
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
