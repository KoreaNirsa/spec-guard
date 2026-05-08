from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import json
import re
from pathlib import Path
from typing import Any

from tools.result import CheckResult


SPECGUARD_STATE_DIR = ".specguard"
SPEC_REVISION_AUDIT_DIR = "spec-revisions"
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


def generate_spec_revision(feature_dir: Path, llm_client: object, review_level: str | None = None) -> str:
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
    return _strip_markdown_fence(llm_client.generate_text(instructions, input_text, max_output_tokens=3000))


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
