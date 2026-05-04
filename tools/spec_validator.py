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

DESIGN_REQUIRED_SECTIONS = {
    "architecture": "Architecture",
    "data flow": "Data Flow",
    "state": "State",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def _has_section(content: str, section: str) -> bool:
    return section.lower() in content


def _validate_doc(path: Path, sections: dict[str, str], result: CheckResult) -> None:
    if not path.exists():
        result.add_error(f"Missing required file: {path}")
        return

    content = _read(path)
    for key, label in sections.items():
        if not _has_section(content, key):
            result.add_error(f"{path} must include section: {label}")


def _feature_dirs(path: Path) -> list[Path]:
    if path.name == "specs" or path.is_dir() and (path / "spec.md").exists() is False:
        return sorted([child for child in path.iterdir() if child.is_dir()])
    return [path]


def validate_feature(path: Path) -> CheckResult:
    result = CheckResult("SpecGuard validation")
    if not path.exists():
        result.add_error(f"Path does not exist: {path}")
        return result

    feature_dirs = _feature_dirs(path)
    if not feature_dirs:
        result.add_error(f"No feature specs found in: {path}")
        return result

    for feature_dir in feature_dirs:
        _validate_doc(feature_dir / "spec.md", SPEC_REQUIRED_SECTIONS, result)
        _validate_doc(feature_dir / "design.md", DESIGN_REQUIRED_SECTIONS, result)

        tests_dir = feature_dir / "tests"
        if not tests_dir.exists() or not any(tests_dir.glob("*.md")):
            result.add_error(f"Missing test scenarios in: {tests_dir}")

    if result.ok:
        result.add_info("Spec, design, and test scenario checks passed.")
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
