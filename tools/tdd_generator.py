from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tools.report_language import report_language_from_payload, resolve_report_language


def _bullets_for_section(content: str, *headings: str) -> list[str]:
    heading_pattern = "|".join(re.escape(heading) for heading in headings)
    pattern = rf"^##\s+(?:{heading_pattern})\s*$([\s\S]*?)(?=^##\s+|\Z)"
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


def generate_tests(path: Path, force: bool = False) -> Path:
    spec_path = path / "spec.md"
    if not spec_path.exists():
        raise FileNotFoundError(f"Missing spec file: {spec_path}")

    tests_dir = path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    output = tests_dir / f"{path.name}.test.md"
    if output.exists() and not force:
        return output

    spec = spec_path.read_text(encoding="utf-8")
    acceptance = _bullets_for_section(spec, "Acceptance Criteria", "인수 조건", "인수 기준")
    errors = _bullets_for_section(spec, "Error Cases", "오류 상황", "오류 사례")

    report_path = path / "readiness-review.json"
    if report_path.exists():
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("report_language"), dict):
            language_resolution = report_language_from_payload(payload)
        else:
            language_resolution = resolve_report_language([spec])
    else:
        language_resolution = resolve_report_language([spec])

    if language_resolution.code == "ko":
        success_cases = acceptance or ["주요 정상 경로가 모든 인수 조건을 충족합니다."]
        failure_cases = errors or ["잘못된 입력을 명확한 오류와 함께 거부합니다."]
        content = "\n".join([
            f"# TDD 시나리오: {path.name}",
            "",
            "## 원본",
            "",
            f"- 스펙: `{spec_path.name}`",
            "",
            "## 성공 시나리오",
            "",
            *[f"- [ ] {case}" for case in success_cases],
            "",
            "## 실패 시나리오",
            "",
            *[f"- [ ] {case}" for case in failure_cases],
            "",
            "## 경계 시나리오",
            "",
            "- [ ] 빈 값, 최댓값, 중복 요청을 처리합니다.",
            "- [ ] 동시 또는 반복 요청이 안전하지 않은 부작용을 만들지 않습니다.",
            "",
            "## 참고",
            "",
            f"{len(spec)}자의 스펙에서 생성했습니다. 구현 전에 실행 가능한 테스트로 교체하세요.",
            "",
        ])
        output.write_text(content, encoding="utf-8")
        return output

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
