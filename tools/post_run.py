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


def generate_spec_revision(feature_dir: Path, llm_client: object) -> str:
    discovery = _read_optional(feature_dir / "discovery.md")
    spec = _read_optional(feature_dir / "spec.md")
    technical_design = _read_optional(feature_dir / "technical-design.md")
    grill = _read_optional(feature_dir / "grill.md")
    instructions = "\n".join([
        "You are SpecGuard's spec refinement assistant.",
        "Revise spec.md so the Grill Me findings become explicit requirements, acceptance criteria, error cases, and constraints.",
        "SpecGuard is not prompt-to-code. Do not write application code.",
        "Return ONLY the full replacement Markdown for spec.md.",
        "Preserve the feature intent and the existing spec structure when possible.",
        "Do not include commentary, patch markers, or code fences.",
    ])
    input_text = "\n\n".join([
        "# Discovery",
        discovery,
        "# Current spec.md",
        spec,
        "# technical-design.md",
        technical_design,
        "# Grill Me report",
        grill,
    ])
    return _strip_markdown_fence(llm_client.generate_text(instructions, input_text, max_output_tokens=4000))


def apply_spec_revision(feature_dir: Path, revised_spec: str) -> Path:
    spec_path = feature_dir / "spec.md"
    spec_path.write_text(revised_spec.rstrip() + "\n", encoding="utf-8")
    return spec_path


def _read_optional(path: Path) -> str:
    if not path.exists():
        return f"{path.name} is missing."
    return path.read_text(encoding="utf-8")


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped
