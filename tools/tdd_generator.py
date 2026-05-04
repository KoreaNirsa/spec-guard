from __future__ import annotations

import argparse
import re
from pathlib import Path


def _bullets_for_section(content: str, heading: str) -> list[str]:
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return []
    bullets: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            bullets.append(stripped[5:].strip())
        elif stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets


def generate_tests(path: Path) -> Path:
    spec_path = path / "spec.md"
    if not spec_path.exists():
        raise FileNotFoundError(f"Missing spec file: {spec_path}")

    tests_dir = path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    output = tests_dir / f"{path.name}.test.md"
    spec = spec_path.read_text(encoding="utf-8")
    acceptance = _bullets_for_section(spec, "Acceptance Criteria")
    errors = _bullets_for_section(spec, "Error Cases")

    success_cases = acceptance or ["Primary happy path satisfies all acceptance criteria."]
    failure_cases = errors or ["Invalid input is rejected with a clear error."]

    content = "\n".join([
        f"# TDD Scenarios: {path.name}",
        "",
        "## Source",
        "",
        f"- Spec: `{spec_path.name}`",
        "",
        "## Success Cases",
        "",
        *[f"- [ ] {case}" for case in success_cases],
        "",
        "## Failure Cases",
        "",
        *[f"- [ ] {case}" for case in failure_cases],
        "",
        "## Boundary Cases",
        "",
        "- [ ] Empty values, maximum values, and duplicate requests are handled.",
        "- [ ] Concurrent or repeated requests do not create unsafe side effects.",
        "",
        "## Notes",
        "",
        f"Generated from a spec with {len(spec)} characters. Replace these scenarios with executable tests before implementation.",
        "",
    ])
    output.write_text(content, encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    output = generate_tests(Path(args.path))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
