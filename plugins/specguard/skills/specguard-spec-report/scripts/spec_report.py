from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MERMAID_REPORT_NAME = "specguard-report.mmd"
HTML_REPORT_NAME = "specguard-report.html"
SEVERITY_ORDER = {
    "Critical": 0,
    "Major": 1,
    "Minor": 2,
}


@dataclass(frozen=True)
class ReportContext:
    package: Path
    readiness_json_path: Path
    readiness_markdown_path: Path
    handoff_path: Path
    report: dict[str, Any] | None
    report_error: str | None


def _load_readiness_report(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "readiness-review.json was not found."
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"readiness-review.json is not valid JSON: {exc.msg}."
    if not isinstance(payload, dict):
        return None, "readiness-review.json did not contain a JSON object."
    return payload, None


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _compact(value: object, *, limit: int = 160) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _display_path(path: Path) -> str:
    return path.resolve().as_posix()


def _issue_sort_key(issue: dict[str, Any]) -> tuple[int, str]:
    severity = str(issue.get("severity", ""))
    return (SEVERITY_ORDER.get(severity, 99), str(issue.get("title", "")))


def _issues(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if report is None:
        return []
    return [issue for issue in _as_list(report.get("issues")) if isinstance(issue, dict)]


def _summary_text(report: dict[str, Any] | None) -> str:
    if report is None:
        return "unavailable"
    summary = _as_dict(report.get("summary"))
    values = []
    for label, key in (("Critical", "critical"), ("Major", "major"), ("Minor", "minor")):
        value = summary.get(key)
        values.append(f"{label} {value}" if isinstance(value, int) else f"{label} unknown")
    return ", ".join(values)


def _readiness_status(report: dict[str, Any] | None) -> str:
    if report is None:
        return "unavailable"
    readiness = _as_dict(report.get("readiness"))
    status = readiness.get("status")
    return str(status) if status else "unknown"


def _review_level(report: dict[str, Any] | None) -> str:
    if report is None:
        return "unavailable"
    level = report.get("review_level")
    return str(level) if level else "unknown"


def _source_artifacts(report: dict[str, Any] | None) -> list[str]:
    if report is None:
        return []
    source_input = _as_dict(report.get("input"))
    artifacts = []
    for artifact in _as_list(source_input.get("artifacts")):
        if isinstance(artifact, dict) and artifact.get("path"):
            artifacts.append(str(artifact["path"]))
    return artifacts


def _top_findings(report: dict[str, Any] | None, *, limit: int = 5) -> list[dict[str, Any]]:
    return sorted(_issues(report), key=_issue_sort_key)[:limit]


def _key_evidence(report: dict[str, Any] | None, *, limit: int = 5) -> list[str]:
    evidence_items: list[str] = []
    for issue in sorted(_issues(report), key=_issue_sort_key):
        severity = str(issue.get("severity", "Unknown"))
        title = str(issue.get("title", "Untitled finding"))
        raw_evidence = issue.get("evidence")
        if isinstance(raw_evidence, str):
            candidates = [raw_evidence]
        else:
            candidates = [str(item) for item in _as_list(raw_evidence)]
        for item in candidates:
            if item.strip():
                evidence_items.append(f"{severity} - {title}: {_compact(item, limit=180)}")
                if len(evidence_items) >= limit:
                    return evidence_items
    return evidence_items


def _handoff_status(context: ReportContext) -> str:
    report = context.report
    if report is None:
        return "unavailable"
    readiness = _as_dict(report.get("readiness"))
    status = readiness.get("status")
    implementation_ready = readiness.get("implementation_ready") is True
    if status in {"ready", "ready_with_warnings"} and implementation_ready and context.handoff_path.exists():
        return "available"
    return "blocked"


def _next_action(context: ReportContext) -> str:
    report = context.report
    if report is None:
        return "Run specguard run <package> --no-llm --no-follow-up to create a current readiness review."

    readiness = _as_dict(report.get("readiness"))
    status = readiness.get("status")
    implementation_ready = readiness.get("implementation_ready") is True
    if status in {"ready", "ready_with_warnings"}:
        if implementation_ready and context.handoff_path.exists():
            return "Use implementation-output.md as the current handoff after reviewing the report."
        return "Rerun the full SpecGuard pipeline before implementation so implementation-output.md is generated."
    if status == "not_ready" or report.get("blocked") is True:
        return "Resolve blocking findings in authored spec files, then rerun specguard run <package> --no-llm --no-follow-up."
    return "Rerun specguard run <package> --no-llm --no-follow-up before using this package for implementation."


def _mermaid_label(text: object) -> str:
    label = _compact(text, limit=120).replace("\\", "/").replace('"', "'")
    return f'"{label}"'


def render_mermaid(context: ReportContext) -> str:
    package_path = _display_path(context.package)
    lines = [
        "flowchart TD",
        f"  package[{_mermaid_label(f'Package: {package_path}')}]",
        f"  status[{_mermaid_label(f'Readiness: {_readiness_status(context.report)} ({_review_level(context.report)})')}]",
        f"  findings[{_mermaid_label(f'Findings: {_summary_text(context.report)}')}]",
        f"  handoff[{_mermaid_label(f'Handoff: {_handoff_status(context)}')}]",
        f"  next[{_mermaid_label(f'Next action: {_next_action(context)}')}]",
        "  package --> status --> findings --> handoff --> next",
    ]

    artifacts = _source_artifacts(context.report)[:4]
    if artifacts:
        lines.append(f"  sources[{_mermaid_label('Source artifacts: ' + ', '.join(artifacts))}]")
        lines.append("  sources --> status")

    for index, issue in enumerate(_top_findings(context.report, limit=4), start=1):
        severity = issue.get("severity", "Unknown")
        title = issue.get("title", "Untitled finding")
        lines.append(f"  finding{index}[{_mermaid_label(f'{severity}: {title}')}]")
        lines.append(f"  findings --> finding{index}")

    evidence = _key_evidence(context.report, limit=3)
    if evidence:
        for index, item in enumerate(evidence, start=1):
            lines.append(f"  evidence{index}[{_mermaid_label('Evidence: ' + item)}]")
            lines.append(f"  finding{min(index, max(1, len(_top_findings(context.report, limit=4))))} --> evidence{index}")
    elif context.report_error:
        lines.append(f"  missing[{_mermaid_label(context.report_error)}]")
        lines.append("  package --> missing")

    return "\n".join(lines) + "\n"


def _html_list(items: list[str], *, empty: str) -> str:
    if not items:
        return f"<p>{html.escape(empty)}</p>"
    return "<ul>\n" + "\n".join(f"  <li>{html.escape(item)}</li>" for item in items) + "\n</ul>"


def render_html(context: ReportContext) -> str:
    package_path = _display_path(context.package)
    readiness_json = _display_path(context.readiness_json_path)
    readiness_markdown = _display_path(context.readiness_markdown_path)
    handoff_path = _display_path(context.handoff_path)
    findings = [
        f"{issue.get('severity', 'Unknown')}: {issue.get('title', 'Untitled finding')}"
        for issue in _top_findings(context.report)
    ]
    evidence = _key_evidence(context.report)
    artifacts = _source_artifacts(context.report)
    report_error = context.report_error or "none"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SpecGuard Report - {html.escape(package_path)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; line-height: 1.5; color: #172033; }}
    main {{ max-width: 960px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #d8dee9; padding: 0.5rem 0.625rem; text-align: left; vertical-align: top; }}
    th {{ background: #f5f7fb; width: 14rem; }}
    code {{ background: #f5f7fb; padding: 0.125rem 0.25rem; border-radius: 0.25rem; }}
  </style>
</head>
<body>
<main>
  <h1>SpecGuard Human-Readable Report</h1>
  <p>This generated report is for review and decision-making only. It is not an authored spec input or implementation requirement.</p>

  <h2>Readiness State</h2>
  <table>
    <tr><th>Spec package</th><td><code>{html.escape(package_path)}</code></td></tr>
    <tr><th>Readiness status</th><td>{html.escape(_readiness_status(context.report))}</td></tr>
    <tr><th>Review level</th><td>{html.escape(_review_level(context.report))}</td></tr>
    <tr><th>Finding summary</th><td>{html.escape(_summary_text(context.report))}</td></tr>
    <tr><th>Handoff status</th><td>{html.escape(_handoff_status(context))}</td></tr>
    <tr><th>Next action</th><td>{html.escape(_next_action(context))}</td></tr>
  </table>

  <h2>Source And Generated Artifacts</h2>
  <table>
    <tr><th>Readiness JSON</th><td><code>{html.escape(readiness_json)}</code></td></tr>
    <tr><th>Readiness Markdown</th><td><code>{html.escape(readiness_markdown)}</code></td></tr>
    <tr><th>Implementation handoff</th><td><code>{html.escape(handoff_path)}</code></td></tr>
    <tr><th>Report error</th><td>{html.escape(report_error)}</td></tr>
  </table>
  {_html_list(artifacts, empty="No reviewed source artifact list was available.")}

  <h2>Finding Summary</h2>
  {_html_list(findings, empty="No readiness findings were reported.")}

  <h2>Key Evidence</h2>
  {_html_list(evidence, empty="No evidence excerpts were available in the readiness report.")}
</main>
</body>
</html>
"""


def build_context(package: Path) -> ReportContext:
    readiness_json_path = package / "readiness-review.json"
    report, report_error = _load_readiness_report(readiness_json_path)
    return ReportContext(
        package=package,
        readiness_json_path=readiness_json_path,
        readiness_markdown_path=package / "readiness-review.md",
        handoff_path=package / "implementation-output.md",
        report=report,
        report_error=report_error,
    )


def generate_reports(package: Path) -> tuple[Path, Path]:
    if not package.exists() or not package.is_dir():
        raise ValueError(f"Spec package does not exist: {package}")

    context = build_context(package)
    docs_dir = package / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    mermaid_path = docs_dir / MERMAID_REPORT_NAME
    html_path = docs_dir / HTML_REPORT_NAME

    mermaid_path.write_text(render_mermaid(context), encoding="utf-8")
    html_path.write_text(render_html(context), encoding="utf-8")
    return mermaid_path, html_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate human-readable SpecGuard report artifacts.")
    parser.add_argument("package", type=Path, help="Path to a SpecGuard spec package.")
    args = parser.parse_args(argv)

    try:
        mermaid_path, html_path = generate_reports(args.package)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Generated Mermaid report: {mermaid_path}")
    print(f"Generated HTML report: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
