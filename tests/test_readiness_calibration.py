from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.readiness_engine import run_readiness_review
from tools.spec_driven_ai_benchmark import benchmark_cases, make_specguard_package


def _benchmark_case(case_id: str) -> dict[str, str]:
    return next(
        case
        for case in benchmark_cases(include_gate_only_extra_cases=True, include_korean_cases=True)
        if case["id"] == case_id
    )


def _run_benchmark_case(tmp_path: Path, case_id: str) -> tuple[bool, dict[str, object]]:
    package = make_specguard_package(tmp_path, _benchmark_case(case_id))
    result = run_readiness_review(package)
    payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    return result.ok, payload


def _issue_by_title(payload: dict[str, object], title: str) -> dict[str, object]:
    issues = payload["issues"]
    assert isinstance(issues, list)
    return next(issue for issue in issues if issue["title"] == title)


def _write_feature(
    root: Path,
    *,
    spec_lines: list[str],
    design_lines: list[str],
) -> Path:
    package = root / "feature"
    package.mkdir()
    package.joinpath("discovery.md").write_text(
        "\n".join([
            "# Discovery: calibration fixture",
            "",
            "## Foundation",
            "",
            "- Goal: verify readiness calibration before implementation.",
            "",
            "## Mechanisms",
            "",
            "- Components: API, service, repository.",
            "",
            "## Stress Test",
            "",
            "- Boundary mistakes must block implementation.",
            "",
            "## Synthesis",
            "",
            "- Implement only after readiness passes.",
        ]),
        encoding="utf-8",
    )
    package.joinpath("spec.md").write_text("\n".join(spec_lines), encoding="utf-8")
    package.joinpath("technical-design.md").write_text("\n".join(design_lines), encoding="utf-8")
    return package


@pytest.mark.parametrize(
    ("case_id", "expected_title", "expected_evidence"),
    [
        ("fault_title_no_trim", "Task title validation is unsafe", "title made only of spaces is allowed"),
        (
            "weak_document_share_client_enforced",
            "Document share ownership boundary is unsafe",
            "client is responsible",
        ),
    ],
)
def test_known_false_negative_calibration_cases_block_with_evidence(
    tmp_path: Path,
    case_id: str,
    expected_title: str,
    expected_evidence: str,
) -> None:
    ok, payload = _run_benchmark_case(tmp_path, case_id)

    assert not ok
    assert payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(payload, expected_title)
    evidence = " ".join(issue.get("evidence", []))
    assert expected_evidence in evidence
    assert expected_evidence in issue["description"]


@pytest.mark.parametrize(
    ("case_id", "source_case_id"),
    [
        ("fault_title_no_trim_ko", "fault_title_no_trim"),
        ("weak_document_share_client_enforced_ko", "weak_document_share_client_enforced"),
    ],
)
def test_korean_counterpart_calibration_cases_remain_blocked(
    tmp_path: Path,
    case_id: str,
    source_case_id: str,
) -> None:
    case = _benchmark_case(case_id)
    ok, payload = _run_benchmark_case(tmp_path, case_id)

    assert case["language"] == "ko"
    assert case["source_case_id"] == source_case_id
    assert not ok
    assert payload["readiness"]["status"] == "not_ready"
    assert payload["summary"]["critical"] >= 1


def test_korean_safe_complete_case_remains_implementation_ready(tmp_path: Path) -> None:
    ok, payload = _run_benchmark_case(tmp_path, "ready_canonical_task_service_ko")

    assert ok
    assert payload["readiness"]["status"] in {"ready", "ready_with_warnings"}
    assert payload["summary"]["critical"] == 0


def test_mixed_korean_prose_with_english_identifiers_blocks_document_share_boundary(
    tmp_path: Path,
) -> None:
    package = _write_feature(
        tmp_path,
        spec_lines=[
            "# Spec: mixed document share",
            "",
            "## Requirements",
            "",
            "- create_share_link는 document_id, owner_id, tenant_id, idempotency_key, expires_at을 받는다.",
            "- 클라이언트가 owner_id가 인증 사용자와 일치하는지 확인한다.",
            "- 서버는 document_id만 조회하고 owner predicate는 사용하지 않는다.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] 문서가 존재하면 share link를 생성한다.",
            "",
            "## Error Cases",
            "",
            "- Missing owner_id returns 401.",
        ],
        design_lines=[
            "# Technical Design: mixed document share",
            "",
            "## Architecture",
            "",
            "- ShareService는 document_id만 사용해서 문서를 조회한다.",
            "",
            "## Data Flow",
            "",
            "1. 클라이언트가 document_id, owner_id, tenant_id, idempotency_key, expires_at을 보낸다.",
            "2. 서비스는 소유권 검증 없이 share link를 만든다.",
            "",
            "## State",
            "",
            "- Link states: active, revoked.",
            "",
            "## Failure Handling",
            "",
            "- Missing owner_id returns 401.",
        ],
    )

    result = run_readiness_review(package)
    payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert not result.ok
    assert payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(payload, "Document share ownership boundary is unsafe")
    assert "owner predicate" in " ".join(issue.get("evidence", []))


def test_mixed_korean_prose_with_english_identifiers_blocks_task_title_validation(
    tmp_path: Path,
) -> None:
    package = _write_feature(
        tmp_path,
        spec_lines=[
            "# Spec: mixed task title",
            "",
            "## Requirements",
            "",
            "- TaskService는 create_task, list_tasks, complete_task, delete_task를 제공한다.",
            "- create_task는 user_id, title, idempotency_key를 받는다.",
            "- title은 caller가 보낸 문자열 그대로 저장하고 앞뒤 공백을 보존한다.",
            "- 공백만 있는 title도 클라이언트 표시 정책으로 허용한다.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] create_task는 앞뒤 공백이 있는 title을 그대로 저장한다.",
            "",
            "## Error Cases",
            "",
            "- Blank user_id raises TaskError.",
        ],
        design_lines=[
            "# Technical Design: mixed task title",
            "",
            "## Architecture",
            "",
            "- TaskService owns task persistence.",
            "",
            "## Data Flow",
            "",
            "1. create_task validates user_id.",
            "2. 서비스는 title을 trim하지 않고 저장한다.",
            "",
            "## State",
            "",
            "- Task states: open, completed, deleted.",
            "",
            "## Failure Handling",
            "",
            "- Missing task_id raises TaskError.",
        ],
    )

    result = run_readiness_review(package)
    payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert not result.ok
    assert payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(payload, "Task title validation is unsafe")
    assert "공백만 있는 title" in " ".join(issue.get("evidence", []))


def test_task_title_preservation_after_non_blank_validation_remains_ready(
    tmp_path: Path,
) -> None:
    package = _write_feature(
        tmp_path,
        spec_lines=[
            "# Spec: safe task title preservation",
            "",
            "## Requirements",
            "",
            "- TaskService exposes create_task.",
            "- create_task rejects title when title.strip() is empty.",
            "- create_task preserves leading and trailing spaces in the stored title after validation succeeds.",
            "- The title `  buy milk  ` remains exactly `  buy milk  `.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] A space-only title raises TaskError.",
            "- [ ] A valid title with leading and trailing spaces is stored unchanged.",
            "",
            "## Error Cases",
            "",
            "- Empty or space-only title raises TaskError.",
        ],
        design_lines=[
            "# Technical Design: safe task title preservation",
            "",
            "## Architecture",
            "",
            "- TaskService owns create_task validation and persistence.",
            "",
            "## Data Flow",
            "",
            "1. create_task validates title.strip() before persistence.",
            "2. It stores the original title only after non-blank validation succeeds.",
            "",
            "## State",
            "",
            "- Task states: open, completed, deleted.",
            "",
            "## Failure Handling",
            "",
            "- Space-only title raises TaskError.",
        ],
    )

    result = run_readiness_review(package)
    payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert result.ok
    assert payload["summary"]["critical"] == 0
    assert "Task title validation is unsafe" not in {issue["title"] for issue in payload["issues"]}


@pytest.mark.parametrize(
    ("language", "case_id", "expected_status"),
    [
        ("en", "ready_canonical_task_service", "ready_with_warnings"),
        ("ko", "ready_canonical_task_service_ko", "ready_with_warnings"),
        ("en", "fault_title_no_trim", "not_ready"),
        ("ko", "fault_title_no_trim_ko", "not_ready"),
    ],
)
def test_calibration_fixture_matrix_covers_language_and_readiness_statuses(
    tmp_path: Path,
    language: str,
    case_id: str,
    expected_status: str,
) -> None:
    case = _benchmark_case(case_id)
    _, payload = _run_benchmark_case(tmp_path, case_id)

    assert case.get("language", "en") == language
    assert payload["readiness"]["status"] == expected_status
