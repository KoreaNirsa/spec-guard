from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def feature_dirs(path: Path) -> list[Path]:
    if (path / "spec.md").exists():
        return [path]
    if path.is_dir():
        return sorted({spec.parent for spec in path.rglob("spec.md")})
    return []


def load_grill_report(feature_dir: Path) -> dict[str, Any] | None:
    report_path = feature_dir / "grill.json"
    if not report_path.exists():
        return None
    return json.loads(report_path.read_text(encoding="utf-8"))


def feature_grill_reports(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    reports: list[tuple[Path, dict[str, Any]]] = []
    for feature_dir in feature_dirs(path):
        report = load_grill_report(feature_dir)
        if report is not None:
            reports.append((feature_dir, report))
    return reports


def blocked_feature_reports(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    return [(feature_dir, report) for feature_dir, report in feature_grill_reports(path) if report.get("blocked")]


def render_grill_summary(feature_dir: Path, report: dict[str, Any], *, limit: int = 5) -> str:
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


def grill_report_stale_reason(feature_dir: Path) -> str | None:
    report_path = feature_dir / "grill.json"
    if not report_path.exists():
        return None

    report_mtime = report_path.stat().st_mtime
    sources = [
        feature_dir / "discovery.md",
        feature_dir / "spec.md",
        feature_dir / "technical-design.md",
    ]
    newer_sources = [source.name for source in sources if source.exists() and source.stat().st_mtime > report_mtime]
    if not newer_sources:
        return None
    return f"Grill Me report may be stale; newer source file(s): {', '.join(newer_sources)}"


def generate_spec_revision(feature_dir: Path, llm_client: object) -> str:
    discovery = _compact_text(_read_optional(feature_dir / "discovery.md"), 2500)
    spec = _compact_text(_read_optional(feature_dir / "spec.md"), 6000)
    technical_design = _compact_text(_read_optional(feature_dir / "technical-design.md"), 3500)
    grill_findings = _compact_grill_findings(feature_dir)
    instructions = "\n".join([
        "You are SpecGuard's spec refinement assistant.",
        "Revise spec.md so the Grill Me findings become explicit requirements, acceptance criteria, error cases, and constraints.",
        "SpecGuard is not prompt-to-code. Do not write application code.",
        "Return ONLY the full replacement Markdown for spec.md.",
        "Preserve the feature intent and the existing spec structure when possible.",
        "Preserve these exact level-2 headings because SpecGuard validates them: ## Requirements, ## Acceptance Criteria, ## Error Cases.",
        "Put at least one Markdown checklist or bullet item under ## Acceptance Criteria and at least one bullet item under ## Error Cases.",
        "Do not rename ## Acceptance Criteria to Acceptance Scenarios or place all criteria under another heading.",
        "Prioritize Critical and Major Grill Me findings.",
        "Do not include commentary, patch markers, or code fences.",
    ])
    input_text = "\n\n".join([
        "# Discovery excerpt",
        discovery,
        "# Current spec.md",
        spec,
        "# technical-design.md excerpt",
        technical_design,
        "# Grill Me findings",
        grill_findings,
    ])
    return _strip_markdown_fence(llm_client.generate_text(instructions, input_text, max_output_tokens=3000))


def apply_spec_revision(feature_dir: Path, revised_spec: str) -> Path:
    spec_path = feature_dir / "spec.md"
    spec_path.write_text(revised_spec.rstrip() + "\n", encoding="utf-8")
    return spec_path


def _read_optional(path: Path) -> str:
    if not path.exists():
        return f"{path.name} is missing."
    return path.read_text(encoding="utf-8")


def _compact_grill_findings(feature_dir: Path) -> str:
    report = load_grill_report(feature_dir)
    if not report:
        return _compact_text(_read_optional(feature_dir / "grill.md"), 3000)

    issues = report.get("issues", [])
    if not isinstance(issues, list):
        return json.dumps(report, indent=2)

    severity_rank = {"Critical": 0, "Major": 1, "Minor": 2}
    sorted_issues = sorted(
        [issue for issue in issues if isinstance(issue, dict)],
        key=lambda issue: severity_rank.get(str(issue.get("severity")), 9),
    )
    lines = [
        "Use these Grill Me findings as the required revision backlog.",
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
