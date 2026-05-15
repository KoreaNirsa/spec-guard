from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from tools.post_run import readiness_report_stale_reason
from tools.readiness_engine import is_review_source_artifact
from tools.spec_validator import validate_spec_basis, validate_technical_design


DEFAULT_SPEC_ROOTS = ("specs",)
REQUIRED_READINESS_FILES = (
    "discovery.md",
    "spec.md",
    "technical-design.md",
    "readiness-review.json",
)

@dataclass(frozen=True)
class FeatureReadinessGateResult:
    feature_dir: Path
    ok: bool
    messages: tuple[str, ...]


def changed_files_from_git(base_ref: str, head_ref: str = "HEAD", *, cwd: Path | None = None) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def changed_feature_dirs(
    changed_files: list[str],
    repo_root: Path,
    spec_roots: tuple[str, ...] = DEFAULT_SPEC_ROOTS,
) -> list[Path]:
    feature_dirs: set[Path] = set()
    root_parts = [_normalize_parts(spec_root) for spec_root in spec_roots]

    for changed_file in changed_files:
        relative = _normalize_changed_path(changed_file)
        if relative is None:
            continue
        parts = relative.parts
        for spec_root_parts in root_parts:
            if not _starts_with(parts, spec_root_parts) or len(parts) == len(spec_root_parts):
                continue
            feature_dirs.add(_feature_dir_for_changed_path(repo_root, relative, spec_root_parts))
            break

    return sorted(feature_dirs, key=lambda path: path.as_posix())


def validate_feature_readiness(
    feature_dir: Path,
    *,
    changed_files: list[str] | None = None,
    repo_root: Path | None = None,
) -> FeatureReadinessGateResult:
    messages: list[str] = []
    for filename in REQUIRED_READINESS_FILES:
        if not (feature_dir / filename).exists():
            messages.append(f"Missing required readiness input: {feature_dir / filename}")

    if messages:
        return FeatureReadinessGateResult(feature_dir, False, tuple(messages))

    spec_validation = validate_spec_basis(feature_dir)
    if not spec_validation.ok:
        messages.extend(spec_validation.messages)

    technical_validation = validate_technical_design(feature_dir)
    if not technical_validation.ok:
        messages.extend(technical_validation.messages)

    stale_reason = readiness_report_stale_reason(feature_dir)
    if stale_reason:
        messages.append(stale_reason)

    changed_stale_reason = _changed_source_without_report_reason(
        feature_dir,
        changed_files=changed_files,
        repo_root=repo_root,
    )
    if changed_stale_reason:
        messages.append(changed_stale_reason)

    report = _load_readiness_report(feature_dir)
    if report is None:
        messages.append(f"Invalid readiness report JSON: {feature_dir / 'readiness-review.json'}")
    elif _readiness_blocked(report):
        summary = report.get("summary", {})
        messages.append(
            "SpecGuard readiness is not READY: "
            f"blocked={report.get('blocked')}, "
            f"implementation_ready={_implementation_ready(report)}, "
            f"summary={json.dumps(summary, sort_keys=True)}"
        )

    return FeatureReadinessGateResult(feature_dir, not messages, tuple(messages))


def run_readiness_gate(
    changed_files: list[str],
    repo_root: Path,
    spec_roots: tuple[str, ...] = DEFAULT_SPEC_ROOTS,
) -> tuple[bool, list[FeatureReadinessGateResult]]:
    feature_dirs = changed_feature_dirs(changed_files, repo_root, spec_roots)
    results = [
        validate_feature_readiness(feature_dir, changed_files=changed_files, repo_root=repo_root)
        for feature_dir in feature_dirs
    ]
    return all(result.ok for result in results), results


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate PRs on READY SpecGuard feature packages.")
    parser.add_argument("--base-ref", help="Base git ref for changed-file detection, such as origin/main.")
    parser.add_argument("--head-ref", default="HEAD", help="Head git ref for changed-file detection.")
    parser.add_argument("--changed-file", action="append", help="Explicit changed file path. Can be repeated.")
    parser.add_argument("--spec-root", action="append", help="Spec package root to inspect. Defaults to specs.")
    args = parser.parse_args()

    repo_root = Path.cwd()
    spec_roots = tuple(args.spec_root or DEFAULT_SPEC_ROOTS)
    changed_files = args.changed_file or _changed_files_from_args(args, repo_root)
    ok, results = run_readiness_gate(changed_files, repo_root, spec_roots)

    if not results:
        print(f"[PASS] No changed SpecGuard spec packages under: {', '.join(spec_roots)}")
        return 0

    for result in results:
        label = _display_path(result.feature_dir, repo_root)
        if result.ok:
            print(f"[PASS] {label} is READY.")
            continue
        print(f"[FAIL] {label} is not ready for merge.")
        for message in result.messages:
            print(f"- {message}")

    return 0 if ok else 1


def _changed_files_from_args(args: argparse.Namespace, repo_root: Path) -> list[str]:
    if not args.base_ref:
        raise SystemExit("--base-ref is required unless --changed-file is provided.")
    return changed_files_from_git(args.base_ref, args.head_ref, cwd=repo_root)


def _feature_dir_for_changed_path(repo_root: Path, relative: PurePosixPath, spec_root_parts: tuple[str, ...]) -> Path:
    spec_root = repo_root.joinpath(*spec_root_parts)
    candidate = repo_root.joinpath(*relative.parent.parts)
    while candidate != spec_root.parent:
        if (candidate / "spec.md").exists():
            return candidate
        if candidate == spec_root:
            break
        candidate = candidate.parent

    feature_name = relative.parts[len(spec_root_parts)]
    return spec_root / feature_name


def _load_readiness_report(feature_dir: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads((feature_dir / "readiness-review.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _readiness_blocked(report: dict[str, Any]) -> bool:
    return report.get("blocked") is not False or _implementation_ready(report) is not True


def _changed_source_without_report_reason(
    feature_dir: Path,
    *,
    changed_files: list[str] | None,
    repo_root: Path | None,
) -> str | None:
    if not changed_files or repo_root is None:
        return None
    try:
        feature_relative = PurePosixPath(feature_dir.relative_to(repo_root).as_posix())
    except ValueError:
        return None

    changed_within_feature = [
        relative_to_feature
        for changed_file in changed_files
        if (relative_to_feature := _relative_changed_path(feature_relative, changed_file)) is not None
    ]
    source_changes = [
        path.as_posix()
        for path in changed_within_feature
        if is_review_source_artifact(path)
    ]
    if not source_changes:
        return None
    report_changed = any(path.as_posix() == "readiness-review.json" for path in changed_within_feature)
    if report_changed:
        return None
    return (
        "SpecGuard Review report is stale for this PR: changed source artifact(s) "
        f"{', '.join(sorted(source_changes))} without updating readiness-review.json."
    )


def _implementation_ready(report: dict[str, Any]) -> object:
    readiness = report.get("readiness")
    if not isinstance(readiness, dict):
        return None
    return readiness.get("implementation_ready")


def _normalize_changed_path(value: str) -> PurePosixPath | None:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return None
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path


def _relative_changed_path(feature_relative: PurePosixPath, changed_file: str) -> PurePosixPath | None:
    changed_path = _normalize_changed_path(changed_file)
    if changed_path is None:
        return None
    if changed_path == feature_relative:
        return PurePosixPath(".")
    if not _starts_with(changed_path.parts, feature_relative.parts):
        return None
    return PurePosixPath(*changed_path.parts[len(feature_relative.parts):])


def _normalize_parts(value: str) -> tuple[str, ...]:
    return PurePosixPath(value.strip().replace("\\", "/")).parts


def _starts_with(parts: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return len(parts) >= len(prefix) and parts[:len(prefix)] == prefix


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
