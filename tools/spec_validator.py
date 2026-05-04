from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.result import CheckResult


SPEC_REQUIRED_SECTIONS = {
    "requirements": "Requirements",
    "acceptance": "Acceptance Criteria",
    "error": "Error Cases",
}

DISCOVERY_REQUIRED_SECTIONS = {
    "foundation": "Foundation",
    "mechanisms": "Mechanisms",
    "stress": "Stress Test",
    "synthesis": "Synthesis",
}

TECHNICAL_DESIGN_REQUIRED_SECTIONS = {
    "architecture": "Architecture",
    "data flow": "Data Flow",
    "state": "State",
}

PLACEHOLDER_MARKERS = (
    "describe ",
    "list ",
    "pending",
    "tbd",
    "{{ ",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def _has_section(content: str, section: str) -> bool:
    return section.lower() in content


def _section(content: str, heading: str) -> str:
    marker = f"## {heading}".lower()
    start = content.find(marker)
    if start == -1:
        return ""
    body_start = content.find("\n", start)
    if body_start == -1:
        return ""
    next_heading = content.find("\n## ", body_start + 1)
    if next_heading == -1:
        return content[body_start:].strip()
    return content[body_start:next_heading].strip()


def _has_placeholder(content: str) -> bool:
    for line in content.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        bullet_text = lowered.lstrip("-*0123456789.[] x")
        if "{{ " in lowered:
            return True
        if bullet_text in {"pending", "tbd"}:
            return True
        if lowered.startswith("describe ") or lowered.startswith("- list "):
            return True
    return False


def _bullet_count(section: str) -> int:
    return sum(1 for line in section.splitlines() if line.strip().startswith("-"))


def _validate_doc(path: Path, sections: dict[str, str], result: CheckResult) -> None:
    if not path.exists():
        result.add_error(f"Missing required file: {path}")
        return

    content = _read(path)
    for key, label in sections.items():
        if not _has_section(content, key):
            result.add_error(f"{path} must include section: {label}")
            continue

        section = _section(content, label)
        if not section:
            result.add_error(f"{path} section is empty: {label}")
        elif _has_placeholder(section):
            result.add_error(f"{path} section still contains placeholder text: {label}")


def _feature_dirs(path: Path) -> list[Path]:
    if (path / "spec.md").exists():
        return [path]
    if path.is_dir():
        return sorted({spec.parent for spec in path.rglob("spec.md")})
    return [path]


def _validate_path(path: Path, result: CheckResult) -> list[Path]:
    if not path.exists():
        result.add_error(f"Path does not exist: {path}")
        return []

    feature_dirs = _feature_dirs(path)
    if not feature_dirs:
        result.add_error(f"No feature specs found in: {path}")
        return []
    return feature_dirs


def _validate_spec_file(feature_dir: Path, result: CheckResult) -> None:
    spec_path = feature_dir / "spec.md"
    if spec_path.exists():
        spec = _read(spec_path)
        acceptance = _section(spec, "Acceptance Criteria")
        errors = _section(spec, "Error Cases")
        if _bullet_count(acceptance) == 0:
            result.add_error(f"{spec_path} must include at least one acceptance criterion")
        if _bullet_count(errors) == 0:
            result.add_error(f"{spec_path} must include at least one error case")


def validate_spec_basis(path: Path) -> CheckResult:
    result = CheckResult("SpecGuard spec basis validation")
    feature_dirs = _validate_path(path, result)
    if not result.ok:
        return result

    for feature_dir in feature_dirs:
        _validate_doc(feature_dir / "discovery.md", DISCOVERY_REQUIRED_SECTIONS, result)
        _validate_doc(feature_dir / "spec.md", SPEC_REQUIRED_SECTIONS, result)
        _validate_spec_file(feature_dir, result)

    if result.ok:
        result.add_info("Discovery and spec checks passed.")
    return result


def validate_technical_design(path: Path) -> CheckResult:
    result = CheckResult("SpecGuard technical design validation")
    feature_dirs = _validate_path(path, result)
    if not result.ok:
        return result

    for feature_dir in feature_dirs:
        _validate_doc(feature_dir / "technical-design.md", TECHNICAL_DESIGN_REQUIRED_SECTIONS, result)

    if result.ok:
        result.add_info("Technical design checks passed.")
    return result


def validate_feature(path: Path) -> CheckResult:
    result = CheckResult("SpecGuard validation")
    feature_dirs = _validate_path(path, result)
    if not result.ok:
        return result

    for feature_dir in feature_dirs:
        _validate_doc(feature_dir / "discovery.md", DISCOVERY_REQUIRED_SECTIONS, result)
        _validate_doc(feature_dir / "spec.md", SPEC_REQUIRED_SECTIONS, result)
        _validate_doc(feature_dir / "technical-design.md", TECHNICAL_DESIGN_REQUIRED_SECTIONS, result)
        _validate_spec_file(feature_dir, result)
        tests_dir = feature_dir / "tests"
        if not tests_dir.exists() or not any(tests_dir.glob("*.md")):
            result.add_error(f"Missing test scenarios in: {tests_dir}")

    if result.ok:
        result.add_info("Discovery, spec, technical design, and test scenario checks passed.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="specs")
    args = parser.parse_args()
    result = validate_feature(Path(args.path))
    result.print()
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
