from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools.result import CheckResult


PROPOSED_SPEC_REVISION_NAME = "spec.proposed.md"

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
    if (path / "spec.md").exists():
        return [path]
    if path.is_dir():
        return sorted({spec.parent for spec in path.rglob("spec.md")})
    return []


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
    issues = report.get("issues", [])
    lines = [
        f"{feature_dir}",
        f"- blocked: {bool(report.get('blocked'))}",
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


def readiness_report_stale_reason(feature_dir: Path) -> str | None:
    report_path = feature_dir / "readiness-review.json"
    if not report_path.exists():
        return None

    report_mtime = report_path.stat().st_mtime
    sources = [
        feature_dir / "discovery.md",
        feature_dir / "spec.md",
        feature_dir / "plan.md",
        feature_dir / "tasks.md",
        feature_dir / "constitution.md",
        feature_dir / "checklists" / "spec-readiness.md",
        feature_dir / "technical-design.md",
    ]
    newer_sources = [source.name for source in sources if source.exists() and source.stat().st_mtime > report_mtime]
    if not newer_sources:
        return None
    return f"SpecGuard Review report may be stale; newer source file(s): {', '.join(newer_sources)}"


def generate_spec_revision(feature_dir: Path, llm_client: object) -> str:
    discovery = _compact_text(_read_optional(feature_dir / "discovery.md"), 2500)
    spec = _compact_text(_read_optional(feature_dir / "spec.md"), 6000)
    plan = _compact_text(_read_optional(feature_dir / "plan.md"), 2500)
    tasks = _compact_text(_read_optional(feature_dir / "tasks.md"), 2500)
    constitution = _compact_text(_read_optional(feature_dir / "constitution.md"), 2500)
    checklist = _compact_text(_read_optional(feature_dir / "checklists" / "spec-readiness.md"), 2500)
    technical_design = _compact_text(_read_optional(feature_dir / "technical-design.md"), 3500)
    readiness_findings = _compact_readiness_findings(feature_dir)
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
        "Prioritize Critical and Major Readiness Findings.",
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
    return _strip_markdown_fence(llm_client.generate_text(instructions, input_text, max_output_tokens=3000))


def apply_spec_revision(feature_dir: Path, revised_spec: str) -> Path:
    spec_path = feature_dir / "spec.md"
    spec_path.write_text(revised_spec.rstrip() + "\n", encoding="utf-8")
    return spec_path


def write_proposed_spec_revision(feature_dir: Path, revised_spec: str) -> Path:
    proposal_path = feature_dir / PROPOSED_SPEC_REVISION_NAME
    proposal_path.write_text(revised_spec.rstrip() + "\n", encoding="utf-8")
    return proposal_path


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
        result.add_next_step(
            f"Review the proposed revision manually, then edit spec.md or {PROPOSED_SPEC_REVISION_NAME} before rerunning SpecGuard."
        )
    return result


def _read_optional(path: Path) -> str:
    if not path.exists():
        return f"{path.name} is missing."
    return path.read_text(encoding="utf-8")


def _compact_readiness_findings(feature_dir: Path) -> str:
    report = load_readiness_report(feature_dir)
    if not report:
        return _compact_text(_read_optional(feature_dir / "readiness-review.md"), 3000)

    issues = report.get("issues", [])
    if not isinstance(issues, list):
        return json.dumps(report, indent=2)

    severity_rank = {"Critical": 0, "Major": 1, "Minor": 2}
    sorted_issues = sorted(
        [issue for issue in issues if isinstance(issue, dict)],
        key=lambda issue: severity_rank.get(str(issue.get("severity")), 9),
    )
    lines = [
        "Use these Readiness Findings as the required revision backlog.",
        f"Summary: {json.dumps(report.get('summary', {}), ensure_ascii=False)}",
        "",
    ]
    for index, issue in enumerate(sorted_issues[:12], start=1):
        lines.extend([
            f"{index}. [{issue.get('severity', 'Unknown')}] {issue.get('title', 'Untitled issue')}",
            f"   Impact: {issue.get('impact', 'Not specified.')}",
            f"   Required spec change: {issue.get('fix', 'Not specified.')}",
        ])
    if len(sorted_issues) > 12:
        lines.append(f"... {len(sorted_issues) - 12} additional minor/detail findings omitted from the prompt.")
    return "\n".join(lines)


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


def _first_heading(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _section(content: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


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
