from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any


GRILL_SCHEMA_VERSION = "0.1"
GRILL_FINDINGS_PATH = Path("grill.json")
GRILL_MARKDOWN_PATH = Path("grill.md")
DECISION_RECORDS_PATH = Path("decisions") / "specguard-decisions.jsonl"
PATCH_PLAN_PATH = Path("decisions") / "specguard-patch-plan.json"
RERUN_COMPARISON_PATH = Path("decisions") / "specguard-rerun-comparison.json"
USER_CONFIRMED_SOURCE = "user-confirmed"
ALLOWED_RESOLUTIONS = ("update-spec", "mark-intentional", "defer", "reject")
PATCHABLE_RESOLUTION = "update-spec"
SEVERITY_ORDER = {"Critical": 0, "Major": 1, "Minor": 2}


@dataclass(frozen=True)
class GrillOutput:
    payload: dict[str, Any]
    json_path: Path
    markdown_path: Path


@dataclass(frozen=True)
class GrillPatchResult:
    plan: dict[str, Any]
    applied: tuple[dict[str, Any], ...]
    skipped: tuple[dict[str, Any], ...]
    diff: str


def build_grill_payload(feature_dir: Path, report: dict[str, Any] | None = None) -> dict[str, Any]:
    current_report = report if report is not None else _load_readiness_report(feature_dir)
    findings = _structured_findings(feature_dir, current_report)
    question_order = [finding["id"] for finding in findings]
    readiness = current_report.get("readiness", {})
    return {
        "schema_version": GRILL_SCHEMA_VERSION,
        "source_report": (feature_dir / "readiness-review.json").as_posix(),
        "decision_record_path": (feature_dir / DECISION_RECORDS_PATH).as_posix(),
        "review_mode": current_report.get("review_mode"),
        "review_level": current_report.get("review_level"),
        "readiness_status": readiness.get("status") if isinstance(readiness, dict) else None,
        "findings": findings,
        "question_order": question_order,
    }


def write_grill_outputs(feature_dir: Path, report: dict[str, Any] | None = None) -> GrillOutput:
    payload = build_grill_payload(feature_dir, report)
    json_path = feature_dir / GRILL_FINDINGS_PATH
    markdown_path = feature_dir / GRILL_MARKDOWN_PATH
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_grill_markdown(payload), encoding="utf-8")
    return GrillOutput(payload=payload, json_path=json_path, markdown_path=markdown_path)


def render_grill_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SpecGuard Grill Me Findings",
        "",
        f"- Schema version: {payload.get('schema_version')}",
        f"- Source report: {payload.get('source_report')}",
        f"- Decision records: {payload.get('decision_record_path')}",
        f"- Readiness status: {payload.get('readiness_status')}",
        "",
        "## Questions",
        "",
    ]
    findings = _findings_by_id(payload)
    question_order = payload.get("question_order", [])
    ordered_ids = question_order if isinstance(question_order, list) else []
    if not ordered_ids:
        lines.append("- No readiness findings were available.")
        return "\n".join(lines).rstrip() + "\n"

    for review_id in ordered_ids:
        finding = findings.get(str(review_id))
        if not finding:
            continue
        location = finding.get("source_location", {})
        location_text = location.get("path", "unknown") if isinstance(location, dict) else "unknown"
        if isinstance(location, dict) and location.get("line") is not None:
            location_text = f"{location_text}:{location['line']}"
        evidence = finding.get("evidence", [])
        evidence_lines = [str(item) for item in evidence] if isinstance(evidence, list) else []
        lines.extend([
            f"### {finding.get('id')} - {finding.get('title')}",
            "",
            f"- Severity: {finding.get('severity')}",
            f"- Source location: {location_text}",
            f"- Suggested clarification question: {finding.get('question')}",
            f"- Allowed resolutions: {', '.join(str(item) for item in finding.get('allowed_resolution', []))}",
            "",
            "Evidence:",
            "",
        ])
        if evidence_lines:
            lines.extend(f"- {item}" for item in evidence_lines)
        else:
            lines.append("- None")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def record_grill_decision(
    feature_dir: Path,
    *,
    review_id: str,
    decision: str,
    resolution: str,
    target: str | None = None,
    source: str = USER_CONFIRMED_SOURCE,
    created_at: str | None = None,
) -> dict[str, Any]:
    if resolution not in ALLOWED_RESOLUTIONS:
        raise ValueError(f"Unsupported Grill me resolution: {resolution}")
    if not review_id.strip():
        raise ValueError("review_id is required")
    if not decision.strip():
        raise ValueError("decision is required")
    payload = load_grill_payload(feature_dir)
    finding = _findings_by_id(payload).get(review_id)
    if finding is None:
        raise ValueError(f"Unknown Grill me review id: {review_id}")
    if resolution == PATCHABLE_RESOLUTION and not target:
        raise ValueError("target is required for update-spec decisions")

    record = {
        "schema_version": GRILL_SCHEMA_VERSION,
        "review_id": review_id,
        "finding_title": finding.get("title"),
        "decision": decision.strip(),
        "source": source,
        "resolution": resolution,
        "target": target,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }
    path = feature_dir / DECISION_RECORDS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def load_grill_payload(feature_dir: Path) -> dict[str, Any]:
    path = feature_dir / GRILL_FINDINGS_PATH
    if not path.exists():
        return write_grill_outputs(feature_dir).payload
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid Grill me findings payload: {path}")
    return payload


def load_decision_records(feature_dir: Path) -> tuple[dict[str, Any], ...]:
    path = feature_dir / DECISION_RECORDS_PATH
    if not path.exists():
        return ()
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid decision JSONL at {path}:{line_number}: {exc}") from exc
        if isinstance(record, dict):
            records.append(record)
    return tuple(records)


def build_grill_patch_plan(feature_dir: Path, decisions: tuple[dict[str, Any], ...] | None = None) -> dict[str, Any]:
    payload = load_grill_payload(feature_dir)
    findings = _findings_by_id(payload)
    records = decisions if decisions is not None else load_decision_records(feature_dir)
    entries: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        review_id = str(record.get("review_id", ""))
        resolution = str(record.get("resolution", ""))
        source = str(record.get("source", ""))
        entry = {
            "decision_index": index,
            "review_id": review_id,
            "resolution": resolution,
            "target": record.get("target"),
            "status": "skipped",
            "reason": "",
        }
        if review_id not in findings:
            entry["reason"] = "review_id is not present in grill.json"
        elif source != USER_CONFIRMED_SOURCE:
            entry["reason"] = "source is not user-confirmed"
        elif resolution != PATCHABLE_RESOLUTION:
            entry["reason"] = f"resolution is {resolution}; no spec patch is allowed"
        else:
            target = _parse_markdown_target(feature_dir, record.get("target"))
            if target is None:
                entry["reason"] = "target must be an existing Markdown heading, for example spec.md#Requirements"
            else:
                path, heading = target
                entry.update({
                    "status": "apply",
                    "path": path.relative_to(feature_dir).as_posix(),
                    "heading": heading,
                    "text": _decision_patch_line(record),
                })
        entries.append(entry)

    plan = {
        "schema_version": GRILL_SCHEMA_VERSION,
        "decision_record_path": (feature_dir / DECISION_RECORDS_PATH).as_posix(),
        "entries": entries,
    }
    plan_path = feature_dir / PATCH_PLAN_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan


def apply_grill_patch_plan(feature_dir: Path, plan: dict[str, Any] | None = None) -> GrillPatchResult:
    patch_plan = plan if plan is not None else build_grill_patch_plan(feature_dir)
    entries = patch_plan.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("Patch plan entries must be a list")

    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    diffs: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("status") != "apply":
            if isinstance(entry, dict):
                skipped.append(entry)
            continue
        path_value = entry.get("path")
        heading = str(entry.get("heading", ""))
        text = str(entry.get("text", "")).strip()
        if not path_value or not heading or not text:
            skipped.append({**entry, "reason": "patch plan entry is incomplete"})
            continue
        path = _safe_feature_path(feature_dir, str(path_value))
        if path is None or path.suffix.lower() != ".md" or not path.exists():
            skipped.append({**entry, "reason": "patch path is not an existing Markdown file"})
            continue

        original = path.read_text(encoding="utf-8")
        updated, changed = _append_to_markdown_heading(original, heading, text)
        if not changed:
            skipped.append({**entry, "reason": "decision text is already present"})
            continue
        path.write_text(updated, encoding="utf-8")
        applied.append(entry)
        diffs.append(
            "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    updated.splitlines(keepends=True),
                    fromfile=f"a/{path.relative_to(feature_dir).as_posix()}",
                    tofile=f"b/{path.relative_to(feature_dir).as_posix()}",
                )
            )
        )

    return GrillPatchResult(
        plan=patch_plan,
        applied=tuple(applied),
        skipped=tuple(skipped),
        diff="\n".join(diff for diff in diffs if diff),
    )


def compare_grill_rerun(
    previous_payload: dict[str, Any],
    current_payload: dict[str, Any],
    decisions: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    previous_findings = _findings_by_id(previous_payload)
    current_findings = _findings_by_id(current_payload)
    previous_ids = set(previous_findings)
    current_ids = set(current_findings)
    deferred_ids = {
        str(record.get("review_id"))
        for record in decisions
        if record.get("resolution") in {"defer", "reject"}
    }
    comparison = {
        "schema_version": GRILL_SCHEMA_VERSION,
        "resolved": sorted(previous_ids - current_ids - deferred_ids),
        "unresolved": sorted((previous_ids & current_ids) - deferred_ids),
        "deferred": sorted(deferred_ids & previous_ids),
        "new": sorted(current_ids - previous_ids),
        "current_readiness_status": current_payload.get("readiness_status"),
        "previous_finding_count": len(previous_ids),
        "current_finding_count": len(current_ids),
    }
    return comparison


def write_grill_rerun_comparison(
    feature_dir: Path,
    previous_payload: dict[str, Any],
    current_payload: dict[str, Any],
) -> dict[str, Any]:
    comparison = compare_grill_rerun(previous_payload, current_payload, load_decision_records(feature_dir))
    path = feature_dir / RERUN_COMPARISON_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    return comparison


def _structured_findings(feature_dir: Path, report: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = _report_artifacts(report)
    raw_issues = report.get("issues", [])
    if not isinstance(raw_issues, list):
        raw_issues = []

    seen_ids: dict[str, int] = {}
    findings: list[dict[str, Any]] = []
    for index, raw_issue in enumerate(raw_issues):
        if not isinstance(raw_issue, dict):
            continue
        severity = _severity(raw_issue.get("severity"))
        evidence = _issue_evidence(raw_issue)
        base_id = _stable_review_id(raw_issue, evidence)
        seen_ids[base_id] = seen_ids.get(base_id, 0) + 1
        review_id = base_id if seen_ids[base_id] == 1 else f"{base_id}-{seen_ids[base_id]}"
        finding = {
            "id": review_id,
            "type": _slug(raw_issue.get("title", "finding")),
            "severity": severity,
            "title": str(raw_issue.get("title", "Untitled finding")),
            "evidence": evidence,
            "source_location": _source_location(feature_dir, artifacts, evidence, index),
            "question": _clarification_question(raw_issue),
            "suggested_clarification": str(raw_issue.get("fix", "Clarify this requirement in the spec.")),
            "allowed_resolution": list(ALLOWED_RESOLUTIONS),
        }
        findings.append(finding)
    findings.sort(key=lambda item: (SEVERITY_ORDER.get(str(item.get("severity")), 99), str(item.get("title")), str(item.get("id"))))
    return findings


def _load_readiness_report(feature_dir: Path) -> dict[str, Any]:
    path = feature_dir / "readiness-review.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing readiness report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid readiness report: {path}")
    return payload


def _report_artifacts(report: dict[str, Any]) -> tuple[str, ...]:
    input_info = report.get("input", {})
    raw_artifacts = input_info.get("artifacts", []) if isinstance(input_info, dict) else []
    paths: list[str] = []
    if isinstance(raw_artifacts, list):
        for artifact in raw_artifacts:
            if isinstance(artifact, dict) and artifact.get("path"):
                paths.append(str(artifact["path"]))
    return tuple(paths)


def _severity(value: object) -> str:
    severity = str(value or "Minor").title()
    return severity if severity in SEVERITY_ORDER else "Minor"


def _issue_evidence(raw_issue: dict[str, Any]) -> list[str]:
    raw_evidence = raw_issue.get("evidence")
    if isinstance(raw_evidence, str) and raw_evidence.strip():
        return [raw_evidence.strip()]
    if isinstance(raw_evidence, list):
        evidence = [str(item).strip() for item in raw_evidence if str(item).strip()]
        if evidence:
            return evidence
    description = str(raw_issue.get("description", "")).strip()
    return [description] if description else []


def _stable_review_id(raw_issue: dict[str, Any], evidence: list[str]) -> str:
    parts = [
        str(raw_issue.get("title", "")),
        str(raw_issue.get("description", "")),
        str(raw_issue.get("impact", "")),
        str(raw_issue.get("fix", "")),
        "\n".join(evidence),
    ]
    digest = hashlib.sha1("\0".join(_normalize_text(part) for part in parts).encode("utf-8")).hexdigest()
    return f"SG-{digest[:12].upper()}"


def _source_location(feature_dir: Path, artifacts: tuple[str, ...], evidence: list[str], issue_index: int) -> dict[str, Any]:
    review_path = f"readiness-review.json#/issues/{issue_index}"
    for excerpt in evidence:
        match = _locate_excerpt(feature_dir, artifacts, excerpt)
        if match is not None:
            path, line = match
            return {"path": path, "line": line, "review_path": review_path}
    return {"path": "readiness-review.json", "line": None, "review_path": review_path}


def _locate_excerpt(feature_dir: Path, artifacts: tuple[str, ...], excerpt: str) -> tuple[str, int] | None:
    normalized_excerpt = _normalize_text(excerpt)
    if not normalized_excerpt:
        return None
    needle = normalized_excerpt[:120]
    for relative in artifacts:
        path = _safe_feature_path(feature_dir, str(relative))
        if path is None or not path.exists() or not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(content.splitlines(), start=1):
            if needle in _normalize_text(line):
                return relative, line_number
        if needle in _normalize_text(content):
            return relative, 1
    return None


def _clarification_question(raw_issue: dict[str, Any]) -> str:
    title = str(raw_issue.get("title", "this finding")).strip()
    fix = str(raw_issue.get("fix", "Clarify the spec contract.")).strip()
    return (
        f"What spec-contract decision resolves \"{title}\"? "
        f"Confirm the exact requirement, mark it intentional, defer it, or reject it. "
        f"Suggested clarification: {fix}"
    )


def _slug(value: object) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug or "finding"


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _findings_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_findings = payload.get("findings", [])
    if not isinstance(raw_findings, list):
        return {}
    return {
        str(finding.get("id")): finding
        for finding in raw_findings
        if isinstance(finding, dict) and finding.get("id")
    }


def _parse_markdown_target(feature_dir: Path, target: object) -> tuple[Path, str] | None:
    if not isinstance(target, str) or "#" not in target:
        return None
    path_text, heading = target.split("#", 1)
    heading = heading.strip("# ").strip()
    if not path_text.strip() or not heading:
        return None
    path = _safe_feature_path(feature_dir, path_text.strip())
    if path is None or path.suffix.lower() != ".md" or not path.exists():
        return None
    if _find_markdown_heading(path.read_text(encoding="utf-8"), heading) is None:
        return None
    return path, heading


def _safe_feature_path(feature_dir: Path, relative_path: str) -> Path | None:
    candidate = feature_dir / relative_path
    try:
        root = feature_dir.resolve()
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved


def _decision_patch_line(record: dict[str, Any]) -> str:
    decision = " ".join(str(record.get("decision", "")).split())
    return f"- SpecGuard decision {record.get('review_id')}: {decision}"


def _append_to_markdown_heading(markdown: str, heading: str, text: str) -> tuple[str, bool]:
    lines = markdown.splitlines()
    heading_index = _find_markdown_heading(markdown, heading)
    if heading_index is None:
        return markdown, False
    heading_level = len(lines[heading_index]) - len(lines[heading_index].lstrip("#"))
    section_end = len(lines)
    for index in range(heading_index + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", lines[index])
        if match and len(match.group(1)) <= heading_level:
            section_end = index
            break
    section_lines = lines[heading_index + 1:section_end]
    if text in section_lines:
        return markdown, False

    insertion = [text]
    insert_at = section_end
    if insert_at > 0 and lines[insert_at - 1].strip():
        insertion.insert(0, "")
    if insert_at < len(lines) and lines[insert_at].strip():
        insertion.append("")
    updated_lines = lines[:insert_at] + insertion + lines[insert_at:]
    return "\n".join(updated_lines).rstrip() + "\n", True


def _find_markdown_heading(markdown: str, heading: str) -> int | None:
    wanted = _normalize_heading(heading)
    for index, line in enumerate(markdown.splitlines()):
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match and _normalize_heading(match.group(1)) == wanted:
            return index
    return None


def _normalize_heading(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()
