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
DEFAULT_REVIEW_LEVEL = "low"
MEDIUM_REVIEW_LEVEL = "medium"
READINESS_REVIEW_LEVELS = {"low", "medium", "high"}
DELTA_REVIEW_CORE_ARTIFACTS = {"spec.md", "technical-design.md"}
DELTA_REVIEW_MAX_EXCERPTS_PER_ARTIFACT = 3
DELTA_REVIEW_EXCERPT_RADIUS = 450
GENERATED_ARTIFACT_MANIFEST_PATH = "generated-artifacts.md"
LOW_REVIEW_FULL_ARTIFACTS = {"spec.md", "technical-design.md", GENERATED_ARTIFACT_MANIFEST_PATH}
LOW_REVIEW_ARTIFACT_LIMITS = {
    "discovery.md": 1200,
    "plan.md": 1200,
    "tasks.md": 800,
    "constitution.md": 800,
    "checklists/spec-readiness.md": 800,
}
LOW_REVIEW_MAX_OUTPUT_TOKENS = 1400
DEFAULT_REVIEW_MAX_OUTPUT_TOKENS = 2500
READINESS_CACHE_SCHEMA_VERSION = "0.2"
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
    metadata: dict[str, object]


@dataclass(frozen=True)
class ReadinessPolicy:
    review_level: str
    ready_major_limit: int
    ready_minor_limit: int
    warning_major_limit: int | None
    warning_minor_limit: int | None
    not_ready_text: str
    prompt_line: str


READINESS_POLICIES = {
    "low": ReadinessPolicy(
        review_level="low",
        ready_major_limit=0,
        ready_minor_limit=0,
        warning_major_limit=None,
        warning_minor_limit=None,
        not_ready_text="requires no Critical findings; Major and Minor findings are warnings in low mode.",
        prompt_line=(
            "Readiness policy for low review level: NOT_READY only when Critical>=1. "
            "READY when Critical=0 and there are no Major or Minor warnings. "
            "READY_WITH_WARNINGS when Critical=0 and Major or Minor warnings exist. "
            "Major and Minor findings are warning-level findings and do not block implementation in low mode."
        ),
    ),
    "medium": ReadinessPolicy(
        review_level="medium",
        ready_major_limit=0,
        ready_minor_limit=READINESS_READY_MINOR_LIMIT,
        warning_major_limit=READINESS_WARNING_MAJOR_LIMIT,
        warning_minor_limit=READINESS_WARNING_MINOR_LIMIT,
        not_ready_text=(
            f"requires no Critical findings, Major<={READINESS_WARNING_MAJOR_LIMIT}, "
            f"and Minor<={READINESS_WARNING_MINOR_LIMIT}."
        ),
        prompt_line=(
            "Readiness policy for medium review level: READY when Critical=0, Major=0, Minor<=5; "
            "READY_WITH_WARNINGS when Critical=0, Major<=2, Minor<=10; "
            "NOT_READY when Critical>=1, Major>=3, or Minor>10."
        ),
    ),
    "high": ReadinessPolicy(
        review_level="high",
        ready_major_limit=0,
        ready_minor_limit=READINESS_READY_MINOR_LIMIT,
        warning_major_limit=READINESS_WARNING_MAJOR_LIMIT,
        warning_minor_limit=READINESS_WARNING_MINOR_LIMIT,
        not_ready_text=(
            f"requires no Critical findings, Major<={READINESS_WARNING_MAJOR_LIMIT}, "
            f"and Minor<={READINESS_WARNING_MINOR_LIMIT}."
        ),
        prompt_line=(
            "Readiness policy for high review level: use the medium gate thresholds in this release, "
            "with stricter review attention. READY when Critical=0, Major=0, Minor<=5; "
            "READY_WITH_WARNINGS when Critical=0, Major<=2, Minor<=10; "
            "NOT_READY when Critical>=1, Major>=3, or Minor>10."
        ),
    ),
}


def _contains(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def normalize_review_level(review_level: str | None) -> str:
    normalized = (review_level or DEFAULT_REVIEW_LEVEL).strip().lower()
    if normalized not in READINESS_REVIEW_LEVELS:
        raise ValueError(f"Unsupported SpecGuard Review level: {review_level}")
    return normalized


def review_level_gate_text(review_level: str | None) -> str:
    policy = _readiness_policy(review_level)
    if policy.review_level == "low":
        return "blocks Critical findings only; Major and Minor findings are warnings"
    return (
        f"blocks Critical findings, Major>{policy.warning_major_limit}, "
        f"or Minor>{policy.warning_minor_limit}"
    )


def _readiness_policy(review_level: str | None) -> ReadinessPolicy:
    return READINESS_POLICIES[normalize_review_level(review_level)]


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
    manifest = _generated_artifact_manifest(path)
    if manifest is not None:
        artifacts.append(manifest)
    return artifacts


def _generated_artifact_manifest(path: Path) -> ReviewArtifact | None:
    generated_roots = [path / "contracts", path / "tests"]
    manifest_entries: list[str] = []
    for root in generated_roots:
        if not root.exists():
            continue
        for candidate in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = candidate.relative_to(path)
            relative_path = str(relative).replace("\\", "/")
            if candidate.name in GENERATED_ARTIFACT_NAMES:
                continue
            manifest_entries.append(f"- {relative_path}: present")

    if not manifest_entries:
        return None

    content = "\n".join([
        "# Generated Artifact Manifest",
        "",
        "These generated verification artifacts exist on disk but are not included in full to keep SpecGuard Review input small.",
        "Use this manifest only as availability evidence for referenced tests and contracts; do not infer additional requirements from it.",
        "",
        *manifest_entries,
        "",
    ])
    return ReviewArtifact(GENERATED_ARTIFACT_MANIFEST_PATH, content)


def _artifact_content(artifacts: list[ReviewArtifact], name: str) -> str:
    for artifact in artifacts:
        if artifact.path == name:
            return artifact.content
    return ""


def _render_artifact_input(artifacts: list[ReviewArtifact]) -> str:
    return "\n\n".join([f"# Artifact: {artifact.path}\n\n{artifact.content}" for artifact in artifacts])


def _build_low_review_input(artifacts: list[ReviewArtifact]) -> tuple[str, dict[str, object]]:
    compact_artifacts: list[ReviewArtifact] = []
    for artifact in artifacts:
        if artifact.path in LOW_REVIEW_FULL_ARTIFACTS:
            compact_artifacts.append(artifact)
            continue
        compact_artifacts.append(ReviewArtifact(artifact.path, _compact_low_review_content(artifact)))
    input_text = _render_artifact_input(compact_artifacts)
    metadata = _review_input_metadata("low_compact", compact_artifacts, len(input_text), DEFAULT_REVIEW_LEVEL)
    metadata["source_artifact_count"] = len(artifacts)
    metadata["source_total_characters"] = sum(len(artifact.content) for artifact in artifacts)
    return input_text, metadata


def _compact_low_review_content(artifact: ReviewArtifact) -> str:
    limit = LOW_REVIEW_ARTIFACT_LIMITS.get(artifact.path, 600)
    if len(artifact.content) <= limit:
        return artifact.content
    omitted = len(artifact.content) - limit
    return "\n".join([
        artifact.content[:limit].rstrip(),
        "",
        f"[SpecGuard low-mode compact excerpt: {omitted} character(s) omitted. Use medium or high review level for full artifact context.]",
    ])


def _review_max_output_tokens(review_level: str) -> int:
    return LOW_REVIEW_MAX_OUTPUT_TOKENS if normalize_review_level(review_level) == "low" else DEFAULT_REVIEW_MAX_OUTPUT_TOKENS


def _previous_findings_text(previous_report: dict | None, review_level: str) -> str:
    if not previous_report:
        return "No previous SpecGuard Review report was available."

    issues = _verification_backlog_issues(previous_report, review_level)
    if not issues:
        if normalize_review_level(review_level) == "low":
            return "Previous SpecGuard Review had no Critical blockers to verify."
        return "Previous SpecGuard Review had no findings."

    lines = [
        (
            "Use these previous Critical blockers as the verification backlog."
            if normalize_review_level(review_level) == "low"
            else "Use these previous findings as the verification backlog."
        ),
        f"Previous backlog summary: {json.dumps(_verification_backlog_summary(issues), ensure_ascii=False)}",
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
    review_level: str,
    previous_report: dict | None,
) -> tuple[str, str, dict[str, object]]:
    instructions = (
        _verification_review_instructions(review_level)
        if review_mode == "verification"
        else _initial_review_instructions(review_level)
    )
    full_input = _render_artifact_input(artifacts)
    if review_mode != "verification":
        if normalize_review_level(review_level) == "low":
            low_input, low_metadata = _build_low_review_input(artifacts)
            return instructions, low_input, low_metadata
        return instructions, full_input, _review_input_metadata("full", artifacts, len(full_input), review_level)

    delta_input, delta_metadata = _build_delta_verification_input(artifacts, previous_report, review_level)
    if delta_input:
        delta_metadata["review_level"] = review_level
        return instructions, delta_input, delta_metadata

    input_text = "\n\n".join([
        "# Previous SpecGuard Review Findings",
        _previous_findings_text(previous_report, review_level),
        "# Current Spec Package Artifacts",
        full_input,
    ])
    metadata = _review_input_metadata("full", artifacts, len(input_text), review_level)
    metadata["fallback_reason"] = delta_metadata.get("fallback_reason", "delta context unavailable")
    return instructions, input_text, metadata


def _review_input_metadata(
    mode: str,
    artifacts: list[ReviewArtifact],
    total_characters: int,
    review_level: str,
) -> dict[str, object]:
    return {
        "mode": mode,
        "review_level": review_level,
        "artifact_count": len(artifacts),
        "total_characters": total_characters,
        "artifacts": [{"path": artifact.path, "characters": len(artifact.content)} for artifact in artifacts],
    }


def _build_delta_verification_input(
    artifacts: list[ReviewArtifact],
    previous_report: dict | None,
    review_level: str,
) -> tuple[str | None, dict[str, object]]:
    issues = _verification_backlog_issues(previous_report, review_level)
    if not issues:
        return None, {"fallback_reason": "missing previous findings"}

    terms = _finding_terms(issues)
    if not terms:
        return None, {"fallback_reason": "previous findings did not expose searchable terms"}

    evidence_blocks: list[str] = []
    included_paths: list[str] = []
    missing_core_evidence: list[str] = []
    for artifact in artifacts:
        excerpts = _artifact_excerpts(artifact.content, terms)
        if excerpts:
            evidence_blocks.append(f"# Artifact excerpts: {artifact.path}\n\n" + "\n\n---\n\n".join(excerpts))
            included_paths.append(artifact.path)
        elif artifact.path in DELTA_REVIEW_CORE_ARTIFACTS:
            missing_core_evidence.append(artifact.path)

    if missing_core_evidence:
        return None, {"fallback_reason": f"core artifact missing finding evidence: {', '.join(missing_core_evidence)}"}

    if not DELTA_REVIEW_CORE_ARTIFACTS.issubset(set(included_paths)):
        return None, {"fallback_reason": "core spec or technical design artifact missing"}

    input_text = "\n\n".join([
        "# Previous SpecGuard Review Findings",
        _previous_findings_text(previous_report, review_level),
        "# Verification Review Delta Evidence",
        "Review only whether the previous findings are resolved, downgraded, or still blocking using the compact current evidence below.",
        *evidence_blocks,
    ])
    metadata: dict[str, object] = {
        "mode": "delta",
        "artifact_count": len(included_paths),
        "total_characters": len(input_text),
        "artifacts": [{"path": path} for path in included_paths],
        "previous_finding_count": len(issues),
    }
    return input_text, metadata


def _verification_backlog_issues(previous_report: dict | None, review_level: str) -> list[object]:
    issues = previous_report.get("issues", []) if isinstance(previous_report, dict) else []
    if not isinstance(issues, list):
        return []
    dict_issues = [issue for issue in issues if isinstance(issue, dict)]
    if normalize_review_level(review_level) == "low":
        return [issue for issue in dict_issues if issue.get("severity") == "Critical"]
    return dict_issues


def _verification_backlog_summary(issues: list[object]) -> dict[str, int]:
    return {
        "critical": sum(1 for issue in issues if isinstance(issue, dict) and issue.get("severity") == "Critical"),
        "major": sum(1 for issue in issues if isinstance(issue, dict) and issue.get("severity") == "Major"),
        "minor": sum(1 for issue in issues if isinstance(issue, dict) and issue.get("severity") == "Minor"),
    }


def _finding_terms(issues: list[object]) -> set[str]:
    terms: set[str] = set()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        text = " ".join(
            str(issue.get(key, ""))
            for key in ("title", "description", "impact", "fix")
        )
        terms.update(
            token
            for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", text.lower())
            if token not in {
                "implementation",
                "required",
                "requires",
                "spec",
                "technical",
                "design",
                "finding",
                "should",
                "without",
                "update",
            }
        )
    return terms


def _artifact_excerpts(content: str, terms: set[str]) -> list[str]:
    lowered = content.lower()
    excerpts: list[str] = []
    used_ranges: list[tuple[int, int]] = []
    for term in sorted(terms, key=len, reverse=True):
        position = lowered.find(term)
        if position == -1:
            continue
        start = max(0, position - DELTA_REVIEW_EXCERPT_RADIUS)
        end = min(len(content), position + len(term) + DELTA_REVIEW_EXCERPT_RADIUS)
        if any(start <= used_end and end >= used_start for used_start, used_end in used_ranges):
            continue
        used_ranges.append((start, end))
        prefix = "[...]\n" if start > 0 else ""
        suffix = "\n[...]" if end < len(content) else ""
        excerpts.append(prefix + content[start:end].strip() + suffix)
        if len(excerpts) >= DELTA_REVIEW_MAX_EXCERPTS_PER_ARTIFACT:
            break
    return excerpts


def _review_cache_metadata(
    artifacts: list[ReviewArtifact],
    *,
    review_mode: str,
    review_level: str,
    max_output_tokens: int,
    instructions: str,
    input_text: str,
    llm_client: object,
) -> tuple[str, dict[str, object]]:
    artifact_manifest = _review_artifact_manifest(artifacts)
    artifact_fingerprint = hashlib.sha256(_stable_json(artifact_manifest).encode("utf-8")).hexdigest()
    client_identity = _client_cache_identity(llm_client)
    input_fingerprint = _sha256_text(input_text)
    instructions_fingerprint = _sha256_text(instructions)
    cache_basis: dict[str, object] = {
        "schema_version": READINESS_CACHE_SCHEMA_VERSION,
        "prompt_version": READINESS_CACHE_PROMPT_VERSION,
        "review_mode": review_mode,
        "review_level": review_level,
        "client": client_identity,
        "input_fingerprint": input_fingerprint,
        "instructions_fingerprint": instructions_fingerprint,
        "max_output_tokens": max_output_tokens,
    }
    cache_key = hashlib.sha256(_stable_json(cache_basis).encode("utf-8")).hexdigest()
    metadata: dict[str, object] = {
        **cache_basis,
        "cache_key": cache_key,
        "cache_key_fields": [
            "schema_version",
            "prompt_version",
            "review_mode",
            "review_level",
            "client.mode",
            "client.model",
            "client.codex_profile",
            "client.client_class",
            "input_fingerprint",
            "instructions_fingerprint",
            "max_output_tokens",
        ],
        "artifact_fingerprint": artifact_fingerprint,
        "artifact_count": len(artifacts),
        "total_input_characters": sum(len(artifact.content) for artifact in artifacts),
        "artifacts": artifact_manifest,
    }
    return cache_key, metadata


def _cache_entry_dir(feature_dir: Path, cache_key: str) -> Path:
    cache_root, feature_slug = _readiness_cache_root(feature_dir)
    return cache_root / feature_slug / cache_key


def _load_cached_review(feature_dir: Path, cache_key: str) -> CachedReview | None:
    cache_dir = _cache_entry_dir(feature_dir, cache_key)
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
    return CachedReview(cache_dir=cache_dir, cache_key=cache_key, payload=payload, metadata=metadata)


def _cache_metadata_candidates(feature_dir: Path) -> list[tuple[float, Path, dict[str, object]]]:
    cache_root, feature_slug = _readiness_cache_root(feature_dir)
    feature_cache_root = cache_root / feature_slug
    if not feature_cache_root.exists():
        return []

    candidates: list[tuple[float, Path, dict[str, object]]] = []
    for cache_dir in feature_cache_root.iterdir():
        metadata_path = cache_dir / "metadata.json"
        if not cache_dir.is_dir() or not metadata_path.exists():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(metadata, dict):
            candidates.append((metadata_path.stat().st_mtime, cache_dir, metadata))
    return candidates


def _closest_cache_metadata(feature_dir: Path, metadata: dict[str, object]) -> tuple[Path, dict[str, object]] | None:
    candidates = _cache_metadata_candidates(feature_dir)
    if not candidates:
        return None

    comparison_fields = [
        "schema_version",
        "prompt_version",
        "review_mode",
        "review_level",
        "client.mode",
        "client.client_class",
        "client.model",
        "client.codex_profile",
        "max_output_tokens",
        "instructions_fingerprint",
        "input_fingerprint",
    ]

    def score(item: tuple[float, Path, dict[str, object]]) -> tuple[int, float]:
        mtime, _cache_dir, candidate = item
        matches = sum(
            1
            for field in comparison_fields
            if _cache_metadata_value(candidate, field) == _cache_metadata_value(metadata, field)
        )
        return matches, mtime

    _mtime, cache_dir, closest = max(candidates, key=score)
    return cache_dir, closest


def _cache_metadata_value(metadata: dict[str, object], field: str) -> object:
    current: object = metadata
    for part in field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _artifact_cache_map(value: object) -> dict[str, object]:
    if not isinstance(value, list):
        return {}
    mapped: dict[str, object] = {}
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            mapped[item["path"]] = item.get("sha256") or item.get("characters")
    return mapped


def _artifact_manifest_change_reason(previous: object, current: object) -> str:
    previous_map = _artifact_cache_map(previous)
    current_map = _artifact_cache_map(current)
    if not previous_map and not current_map:
        return ""

    added = sorted(set(current_map) - set(previous_map))
    removed = sorted(set(previous_map) - set(current_map))
    changed = sorted(path for path in set(previous_map) & set(current_map) if previous_map[path] != current_map[path])
    if changed:
        return "artifact hash changed: " + ", ".join(changed[:3])
    if added:
        return "artifact set changed: added " + ", ".join(added[:3])
    if removed:
        return "artifact set changed: removed " + ", ".join(removed[:3])
    return ""


def _cache_miss_reason(feature_dir: Path, metadata: dict[str, object]) -> str:
    closest = _closest_cache_metadata(feature_dir, metadata)
    if closest is None:
        return "no cache entry for this feature"
    _cache_dir, previous = closest

    comparisons = [
        ("schema_version", "cache schema version changed"),
        ("prompt_version", "prompt version changed"),
        ("review_mode", "review mode changed"),
        ("review_level", "review level changed"),
        ("client.mode", "provider changed"),
        ("client.client_class", "provider client changed"),
        ("client.model", "model changed"),
        ("client.codex_profile", "Codex profile changed"),
        ("max_output_tokens", "max output token budget changed"),
        ("instructions_fingerprint", "review instructions changed"),
    ]
    for field, label in comparisons:
        previous_value = _cache_metadata_value(previous, field)
        current_value = _cache_metadata_value(metadata, field)
        if previous_value != current_value:
            return f"{label}: {previous_value or '<empty>'} -> {current_value or '<empty>'}"

    artifact_reason = _artifact_manifest_change_reason(previous.get("artifacts"), metadata.get("artifacts"))
    if artifact_reason:
        return artifact_reason
    if previous.get("input_fingerprint") != metadata.get("input_fingerprint"):
        return "review input changed"
    return "cache key changed"


def _cache_report_info(
    metadata: dict[str, object],
    *,
    hit: bool,
    miss_reason: str = "",
    cache_dir: Path | None = None,
    stored: bool = False,
) -> dict[str, object]:
    client = metadata.get("client", {})
    if not isinstance(client, dict):
        client = {}
    cache_key = str(metadata.get("cache_key", ""))
    info: dict[str, object] = {
        "enabled": True,
        "hit": hit,
        "cache_key": cache_key,
        "cache_key_prefix": cache_key[:12],
        "stored": stored,
        "schema_version": metadata.get("schema_version"),
        "prompt_version": metadata.get("prompt_version"),
        "review_mode": metadata.get("review_mode"),
        "review_level": metadata.get("review_level"),
        "provider": client.get("mode"),
        "model": client.get("model"),
        "client_class": client.get("client_class"),
        "input_fingerprint": metadata.get("input_fingerprint"),
        "instructions_fingerprint": metadata.get("instructions_fingerprint"),
        "artifact_fingerprint": metadata.get("artifact_fingerprint"),
        "max_output_tokens": metadata.get("max_output_tokens"),
    }
    if miss_reason:
        info["miss_reason"] = miss_reason
    if cache_dir is not None:
        info["cache_dir"] = str(cache_dir)
    return info


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


def _parse_llm_issues(text: str, review_level: str = DEFAULT_REVIEW_LEVEL) -> list[ReadinessIssue]:
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
    return _calibrate_issues(issues, review_level)


def _calibrate_issues(issues: list[ReadinessIssue], review_level: str = DEFAULT_REVIEW_LEVEL) -> list[ReadinessIssue]:
    calibrated: list[ReadinessIssue] = []
    for issue in issues:
        if issue.severity == "Major" and _major_should_downgrade(issue, review_level):
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


def _major_should_downgrade(issue: ReadinessIssue, review_level: str = DEFAULT_REVIEW_LEVEL) -> bool:
    review_level = normalize_review_level(review_level)
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
    medium_blocking_markers = (
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
    if review_level != "low":
        return any(marker in text for marker in non_blocking_markers) and not any(marker in text for marker in medium_blocking_markers)

    low_non_blocking_markers = non_blocking_markers + (
        "automatic retry",
        "retry queue",
        "retry queues",
        "failed email delivery",
        "bulk invite import",
        "bulk import",
        "cross-workspace invite",
        "cross workspace invite",
        "future scalability",
        "scalability",
        "observability",
        "monitoring",
        "nice-to-have",
        "could add",
        "could support",
        "consider adding",
        "later iteration",
    )
    low_blocking_markers = (
        "cannot implement",
        "requires guessing",
        "must guess",
        "missing required",
        "required behavior",
        "product intent drift",
        "out-of-scope",
        "promoted into scope",
        "contradict",
        "contract contradiction",
        "contract mismatch",
        "impossible state",
        "state transition",
        "authorization gap",
        "authorization",
        "auth gap",
        "ownership gap",
        "ownership",
        "tenant isolation",
        "security hole",
        "data loss",
        "destructive",
        "unsafe deletion",
        "credential",
        "secret",
        "token lifecycle",
    )
    return any(marker in text for marker in low_non_blocking_markers) and not any(marker in text for marker in low_blocking_markers)


def _initial_review_instructions(review_level: str) -> str:
    policy = _readiness_policy(review_level)
    if policy.review_level == "low":
        return "\n".join([
            "You are SpecGuard's low-level readiness gate.",
            "Your job is a minimum safety gate before Codex or Claude Code implements from the spec package.",
            "Do not perform a broad architecture, reliability, scalability, or best-practice consulting review.",
            f"Review level: {policy.review_level}.",
            "Analyze the provided spec artifacts together, including Discovery, spec.md, plan.md, tasks.md, constitution.md, checklists, technical-design.md, and any additional authored spec document.",
            "If generated-artifacts.md is supplied, treat it only as evidence that referenced tests and contracts exist on disk; do not infer extra requirements from the manifest.",
            _readiness_policy_prompt_line(policy.review_level),
            "Critical calibration: use Critical only when direct evidence shows product intent drift, an out-of-scope item promoted into implementation scope, an authorization or ownership gap, a security hole, a contract contradiction, impossible state behavior, destructive side-effect ambiguity, or a missing required behavior that makes implementation unsafe or indeterminate.",
            "Major and Minor calibration: Major and Minor findings are warnings in low mode. Use them for useful clarity gaps, but they must not block implementation.",
            "Downgrade or omit best-practice suggestions, optional hardening, future scalability, retry queues, bulk import, broad reliability improvements, and weakly evidenced risks unless they directly create a Critical blocker.",
            "Return ONLY JSON with this shape:",
            '{"issues":[{"severity":"Critical|Major|Minor","title":"...","description":"...","impact":"...","fix":"..."}]}',
            "Every Critical finding must cite exact evidence from the current artifacts and explain why implementation must stop now. Do not include positive feedback.",
        ])
    return "\n".join([
        "You are SpecGuard's readiness review board: principal architect, security reviewer, reliability engineer, API contract reviewer, and test strategist.",
        "Your task is NOT to approve the implementation basis. Your task is to break it before Codex or Claude Code implements from it.",
        f"Review level: {policy.review_level}.",
        "Analyze every provided spec artifact together, including Discovery, spec.md, plan.md, tasks.md, constitution.md, checklists, technical-design.md, and any additional authored spec document.",
        "If generated-artifacts.md is supplied, treat it only as evidence that referenced tests and contracts exist on disk; do not infer extra requirements from the manifest.",
        "Use SpecGuard Review: find contradictions, missing requirements, undefined state, security gaps, data ownership gaps, versioning gaps, weak contracts, untestable acceptance criteria, unsafe failure handling, and implementation assumptions.",
        _readiness_policy_prompt_line(policy.review_level),
        "Severity calibration: Critical means unsafe, contradictory, or impossible to implement deterministically; Major means implementation would require guessing or would miss an important product, security, state, contract, persistence, or ownership decision; Minor means useful cleanup that does not block implementation.",
        "Downgrade best-practice suggestions, optional hardening, future extensibility, broad reliability improvements, and weakly evidenced risks to Minor or omit them.",
        "Return ONLY JSON with this shape:",
        '{"issues":[{"severity":"Critical|Major|Minor","title":"...","description":"...","impact":"...","fix":"..."}]}',
        "Do not include positive feedback. Every finding must be actionable and mapped to a spec, plan, task, checklist, technical design, test, or contract update.",
    ])


def _verification_review_instructions(review_level: str) -> str:
    policy = _readiness_policy(review_level)
    if policy.review_level == "low":
        return "\n".join([
            "You are SpecGuard's low-level Verification Review board.",
            f"Review level: {policy.review_level}.",
            "This is NOT a fresh broad review. Verify whether the regenerated spec package resolves previous Critical blockers and preserves product intent.",
            "Your job is a minimum safety gate: keep only concrete implementation-destabilizing blockers as Critical.",
            "If generated-artifacts.md is supplied, treat it only as evidence that referenced tests and contracts exist on disk; do not infer extra requirements from the manifest.",
            "Do not create new blockers for best-practice improvements, optional hardening, future scalability, retry queues, bulk import, broad reliability, style, naming, or weakly evidenced risks.",
            "Respect explicit out-of-scope, deferred, or accepted-risk decisions when they are documented in the spec package and do not contradict safety or contract requirements.",
            _readiness_policy_prompt_line(policy.review_level),
            "Critical calibration: Critical means direct evidence of product intent drift, authorization or ownership gaps, security holes, contract contradictions, impossible state behavior, destructive side-effect ambiguity, or missing required behavior that makes implementation unsafe or indeterminate.",
            "Major and Minor findings are warnings in low mode and should describe useful non-blocking cleanup only.",
            "Return ONLY JSON with this shape:",
            '{"issues":[{"severity":"Critical|Major|Minor","title":"...","description":"...","impact":"...","fix":"..."}]}',
            "Every Critical finding must cite exact evidence from the current artifacts and explain why implementation must stop now.",
        ])
    return "\n".join([
        "You are SpecGuard's Verification Review board.",
        f"Review level: {policy.review_level}.",
        "This is NOT a fresh broad SpecGuard Review. Verify whether the regenerated spec package resolves the previous Readiness Findings.",
        "Your primary job is to close, downgrade, or keep previous findings based on the current artifacts.",
        "If generated-artifacts.md is supplied, treat it only as evidence that referenced tests and contracts exist on disk; do not infer extra requirements from the manifest.",
        "Add a new Critical or Major finding only when there is direct evidence in the current artifacts that implementation would be unsafe, contradictory, or would require an important guess.",
        "Do not create new blockers for best-practice improvements, optional hardening, style, naming, or future extensibility. Those are Minor or omitted.",
        "Respect explicit out-of-scope, deferred, or accepted-risk decisions when they are documented in the spec package and do not contradict safety or contract requirements.",
        _readiness_policy_prompt_line(policy.review_level),
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
    review_level: str,
    max_output_tokens: int = DEFAULT_REVIEW_MAX_OUTPUT_TOKENS,
) -> list[ReadinessIssue]:
    text = llm_client.generate_text(instructions, input_text, max_output_tokens=max_output_tokens)
    return _parse_llm_issues(text, review_level)


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


def _readiness_status(summary: dict[str, int], review_level: str | None = DEFAULT_REVIEW_LEVEL) -> str:
    policy = _readiness_policy(review_level)
    if (
        summary["critical"] == 0
        and summary["major"] <= policy.ready_major_limit
        and summary["minor"] <= policy.ready_minor_limit
    ):
        return "ready"
    if policy.warning_major_limit is None or policy.warning_minor_limit is None:
        return "ready_with_warnings" if summary["critical"] == 0 else "not_ready"
    if (
        summary["critical"] == 0
        and summary["major"] <= policy.warning_major_limit
        and summary["minor"] <= policy.warning_minor_limit
    ):
        return "ready_with_warnings"
    return "not_ready"


def _is_implementation_ready(summary: dict[str, int], review_level: str | None = DEFAULT_REVIEW_LEVEL) -> bool:
    return _readiness_status(summary, review_level) in {"ready", "ready_with_warnings"}


def _readiness_text(summary: dict[str, int], review_level: str | None = DEFAULT_REVIEW_LEVEL) -> str:
    policy = _readiness_policy(review_level)
    status = _readiness_status(summary, policy.review_level)
    if status == "ready":
        return (
            f"Implementation-ready ({policy.review_level}): "
            f"Critical=0, Major<={policy.ready_major_limit}, Minor<={policy.ready_minor_limit}."
        )
    if status == "ready_with_warnings":
        if policy.warning_major_limit is None or policy.warning_minor_limit is None:
            return "Implementation-ready with warnings (low): Critical=0; Major and Minor findings are warnings."
        return (
            f"Implementation-ready with warnings ({policy.review_level}): "
            f"Critical=0, Major<={policy.warning_major_limit}, Minor<={policy.warning_minor_limit}."
        )
    return f"Not implementation-ready ({policy.review_level}): {policy.not_ready_text}"


def _readiness_policy_prompt_line(review_level: str | None = DEFAULT_REVIEW_LEVEL) -> str:
    return _readiness_policy(review_level).prompt_line


def _readiness_criteria(policy: ReadinessPolicy) -> dict[str, object]:
    criteria: dict[str, object] = {
        "review_level": policy.review_level,
        "ready": {
            "critical": 0,
            "major_max": policy.ready_major_limit,
            "minor_max": policy.ready_minor_limit,
        },
        "not_ready": policy.not_ready_text,
    }
    if policy.warning_major_limit is None or policy.warning_minor_limit is None:
        criteria["ready_with_warnings"] = {
            "critical": 0,
            "major_max": None,
            "minor_max": None,
            "note": "Major and Minor findings are warnings in low mode.",
        }
    else:
        criteria["ready_with_warnings"] = {
            "critical": 0,
            "major_max": policy.warning_major_limit,
            "minor_max": policy.warning_minor_limit,
        }
    return criteria


def _build_report(
    artifacts: list[ReviewArtifact],
    issues: list[ReadinessIssue],
    review_mode: str,
    review_level: str,
    review_input: dict[str, object] | None = None,
    cache_info: dict[str, object] | None = None,
) -> str:
    summary = _build_summary(issues)
    policy = _readiness_policy(review_level)
    status = _readiness_status(summary, policy.review_level)
    critical = [issue for issue in issues if issue.severity == "Critical"]
    major = [issue for issue in issues if issue.severity == "Major"]
    minor = [issue for issue in issues if issue.severity == "Minor"]
    warning_criteria = (
        "Critical=0; Major/Minor are warnings"
        if policy.warning_major_limit is None or policy.warning_minor_limit is None
        else f"Critical=0, Major<={policy.warning_major_limit}, Minor<={policy.warning_minor_limit}"
    )

    return "\n".join([
        "# SpecGuard Review Result",
        "",
        f"- Review mode: {review_mode}",
        f"- Review level: {policy.review_level}",
        "",
        "## Readiness",
        "",
        f"- Status: {status.upper()}",
        f"- READY criteria: Critical=0, Major<={policy.ready_major_limit}, Minor<={policy.ready_minor_limit}",
        f"- READY_WITH_WARNINGS criteria: {warning_criteria}",
        (
            f"- Blockers: Critical={summary['critical']}; "
            f"Warnings: Major={summary['major']}, Minor={summary['minor']} (non-blocking in low mode)"
            if policy.review_level == "low"
            else (
                f"- Gate counts: Critical={summary['critical']}, Major={summary['major']}, "
                f"Minor={summary['minor']}"
            )
        ),
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
        _readiness_policy_prompt_line(policy.review_level),
        "```",
        "",
        "## Input Summary",
        "",
        *[f"- {artifact.path}: {len(artifact.content)} characters" for artifact in artifacts],
        "",
        "## Review Input",
        "",
        f"- Mode: {review_input.get('mode', 'full') if review_input else 'full'}",
        f"- Artifacts sent to LLM: {review_input.get('artifact_count', len(artifacts)) if review_input else len(artifacts)}",
        f"- Characters sent to LLM: {review_input.get('total_characters', sum(len(artifact.content) for artifact in artifacts)) if review_input else sum(len(artifact.content) for artifact in artifacts)}",
        "",
        *_render_cache_report_lines(cache_info),
    ])


def _render_cache_report_lines(cache_info: dict[str, object] | None) -> list[str]:
    if not cache_info:
        return []
    status = "hit" if cache_info.get("hit") else "miss"
    lines = [
        "## Cache",
        "",
        f"- Status: {status}",
        f"- Key: {cache_info.get('cache_key_prefix', '')}",
    ]
    if cache_info.get("miss_reason"):
        lines.append(f"- Miss reason: {cache_info['miss_reason']}")
    if cache_info.get("stored"):
        lines.append("- Stored: true")
    if cache_info.get("provider") or cache_info.get("model"):
        lines.append(f"- Provider: {cache_info.get('provider') or '<unknown>'}; model: {cache_info.get('model') or '<default>'}")
    lines.append("")
    return lines


def _build_json_report(
    artifacts: list[ReviewArtifact],
    issues: list[ReadinessIssue],
    review_mode: str,
    review_level: str,
    review_input: dict[str, object] | None = None,
    cache_info: dict[str, object] | None = None,
) -> str:
    summary = _build_summary(issues)
    policy = _readiness_policy(review_level)
    status = _readiness_status(summary, policy.review_level)
    artifact_lengths = {artifact.path: len(artifact.content) for artifact in artifacts}
    total_characters = sum(artifact_lengths.values())
    payload = {
        "schema_version": "0.1",
        "review_mode": review_mode,
        "review_level": policy.review_level,
        "blocked": not _is_implementation_ready(summary, policy.review_level),
        "readiness": {
            "implementation_ready": _is_implementation_ready(summary, policy.review_level),
            "criteria": _readiness_criteria(policy),
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
        "prompt_mode": _readiness_policy_prompt_line(policy.review_level),
    }
    if review_input is not None:
        payload["review_input"] = review_input
    if cache_info is not None:
        payload["cache"] = cache_info
    return json.dumps(payload, indent=2) + "\n"


def run_readiness_review(
    path: Path,
    llm_client: object | None = None,
    review_mode: str = "initial",
    review_level: str = DEFAULT_REVIEW_LEVEL,
    report_stem: str = "readiness-review",
) -> CheckResult:
    if review_mode not in READINESS_REVIEW_MODES:
        raise ValueError(f"Unsupported SpecGuard Review mode: {review_mode}")
    review_level = normalize_review_level(review_level)

    result = CheckResult("SpecGuard Review")
    discovery_path = path / "discovery.md"
    spec_path = path / "spec.md"
    technical_design_path = path / "technical-design.md"
    report_path = path / f"{report_stem}.md"
    report_json_path = path / f"{report_stem}.json"

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
    review_input: dict[str, object] | None = None
    mode = "LLM" if llm_client else "heuristic"
    cache_hit: CachedReview | None = None
    cache_key = ""
    cache_metadata: dict[str, object] | None = None
    cache_miss_reason = ""
    cache_info: dict[str, object] | None = None
    llm_elapsed_ms: int | None = None
    llm_summary = describe_llm_client(llm_client) if llm_client else ""
    try:
        if llm_client:
            instructions, input_text, review_input = _build_llm_review_request(
                artifacts,
                review_mode=review_mode,
                review_level=review_level,
                previous_report=previous_report,
            )
            max_output_tokens = _review_max_output_tokens(review_level)
            review_input["max_output_tokens"] = max_output_tokens
            cache_key, cache_metadata = _review_cache_metadata(
                artifacts,
                review_mode=review_mode,
                review_level=review_level,
                max_output_tokens=max_output_tokens,
                instructions=instructions,
                input_text=input_text,
                llm_client=llm_client,
            )
            cache_hit = _load_cached_review(path, cache_key)
            if cache_hit:
                issues = _parse_llm_issues(json.dumps({"issues": cache_hit.payload.get("issues", [])}), review_level)
                cache_info = _cache_report_info(cache_metadata, hit=True, cache_dir=cache_hit.cache_dir)
            else:
                cache_miss_reason = _cache_miss_reason(path, cache_metadata)
                cache_info = _cache_report_info(
                    cache_metadata,
                    hit=False,
                    miss_reason=cache_miss_reason,
                    cache_dir=_cache_entry_dir(path, cache_key),
                    stored=True,
                )
                review_artifact_count = review_input.get("artifact_count", len(artifacts)) if review_input else len(artifacts)
                review_characters = review_input.get("total_characters", total_input_characters) if review_input else total_input_characters
                activity = (
                    f"cache miss: {cache_miss_reason}; waiting for LLM SpecGuard Review "
                    f"({llm_summary}, {review_mode}, {review_artifact_count} artifacts, {review_characters} chars)"
                )
                started = time.perf_counter()
                with progress_activity(activity):
                    issues = _analyze_with_llm(
                        llm_client,
                        instructions=instructions,
                        input_text=input_text,
                        review_level=review_level,
                        max_output_tokens=max_output_tokens,
                    )
                llm_elapsed_ms = int((time.perf_counter() - started) * 1000)
        else:
            issues = _analyze(artifacts)
            review_input = _review_input_metadata("heuristic", artifacts, total_input_characters, review_level)
    except (json.JSONDecodeError, ValueError) as exc:
        result.add_error(f"LLM SpecGuard Review response could not be parsed as JSON: {exc}")
        return result
    summary = _build_summary(issues)
    critical_count = summary["critical"]
    major_count = summary["major"]
    minor_count = summary["minor"]
    implementation_ready = _is_implementation_ready(summary, review_level)

    report_path.write_text(_build_report(artifacts, issues, review_mode, review_level, review_input, cache_info), encoding="utf-8")
    report_json_path.write_text(_build_json_report(artifacts, issues, review_mode, review_level, review_input, cache_info), encoding="utf-8")
    if llm_client and cache_metadata is not None and not cache_hit:
        _store_cached_review(path, cache_key, cache_metadata, report_path, report_json_path)
    result.details.update(summary)
    result.details["review_level"] = review_level
    if cache_hit:
        result.details["cache_hit"] = True
        result.details["cache_key"] = cache_key
        result.details["cache_dir"] = str(cache_hit.cache_dir)
        result.add_info(f"SpecGuard Review cache check: hit {cache_key[:12]}")
        result.add_info(f"Reused cached {mode} {review_mode} readiness report: {report_path}")
        result.add_info(f"Reused cached {mode} {review_mode} machine-readable readiness report: {report_json_path}")
        result.add_info(f"SpecGuard Review cache hit: {cache_key[:12]} ({cache_hit.cache_dir})")
    else:
        result.add_info(f"Generated {mode} {review_mode} readiness report: {report_path}")
        result.add_info(f"Generated {mode} {review_mode} machine-readable readiness report: {report_json_path}")
        if llm_client and cache_key:
            result.details["cache_hit"] = False
            result.details["cache_key"] = cache_key
            result.details["cache_miss_reason"] = cache_miss_reason
            result.add_info(f"SpecGuard Review cache check: miss {cache_key[:12]} ({cache_miss_reason})")
            result.add_info(f"SpecGuard Review cache stored: {cache_key[:12]}")
    result.add_info(f"SpecGuard Review level: {review_level} ({review_level_gate_text(review_level)}).")
    if review_level == "low":
        result.add_info(
            f"SpecGuard low gate: {critical_count} blocker(s); "
            f"{major_count + minor_count} warning finding(s) ({major_count} Major, {minor_count} Minor)."
        )
    result.add_info(f"Reviewed spec artifacts: {', '.join(artifact.path for artifact in artifacts)}")
    if review_input:
        result.add_info(
            "SpecGuard Review input size: "
            f"{review_input.get('artifact_count', len(artifacts))} artifact(s), "
            f"{review_input.get('total_characters', total_input_characters)} characters "
            f"({review_input.get('mode', 'full')} mode; full artifact set {len(artifacts)} artifact(s), {total_input_characters} characters)."
        )
    else:
        result.add_info(f"SpecGuard Review input size: {len(artifacts)} artifact(s), {total_input_characters} characters.")
    if llm_elapsed_ms is not None:
        result.details[f"{review_mode}_llm_review_ms"] = llm_elapsed_ms
        review_artifact_count = review_input.get("artifact_count", len(artifacts)) if review_input else len(artifacts)
        review_characters = review_input.get("total_characters", total_input_characters) if review_input else total_input_characters
        result.add_info(
            f"LLM {review_mode} SpecGuard Review call: {llm_summary}, "
            f"{review_artifact_count} artifact(s), {review_characters} characters, {llm_elapsed_ms}ms."
        )
    if implementation_ready:
        if _readiness_status(summary, review_level) == "ready_with_warnings":
            result.add_info(yellow(f"[READY_WITH_WARNINGS] {_readiness_text(summary, review_level)} Current: {critical_count} critical, {major_count} major, {minor_count} minor."))
            result.add_next_step(f"Review warning findings in: {report_path}")
        else:
            result.add_info(green(f"[READY] {_readiness_text(summary, review_level)} Current: {critical_count} critical, {major_count} major, {minor_count} minor."))
    else:
        result.add_error(red(f"[NOT READY] {_readiness_text(summary, review_level)} Current: {critical_count} critical, {major_count} major, {minor_count} minor."))
        result.add_next_step(f"Open the human report: {report_path}")
        result.add_next_step(f"Use the machine-readable report for automation: {report_json_path}")
        if review_level == "low":
            result.add_next_step("Fix Critical blockers so the spec package preserves product intent and implementation safety.")
        else:
            result.add_next_step(
                "Fix spec package artifacts so Critical and Major issues become explicit requirements or verified constraints, and Minor findings stay within the readiness threshold."
            )
        result.add_next_step("Do not start external AI implementation until SpecGuard reports READY and writes implementation-output.md.")
        result.add_next_step(f"Run again: specguard run {path}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--review-level", choices=sorted(READINESS_REVIEW_LEVELS), default=DEFAULT_REVIEW_LEVEL)
    args = parser.parse_args()
    result = run_readiness_review(Path(args.path), review_level=args.review_level)
    result.print()
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
