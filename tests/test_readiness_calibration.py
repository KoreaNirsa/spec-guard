from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.readiness_engine import run_readiness_review
from tools.spec_driven_ai_benchmark import benchmark_cases, make_specguard_package


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_SUPPORT_DOC = ROOT / "docs" / "language-support.md"


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


def _first_issue_by_severity(payload: dict[str, object], severity: str) -> dict[str, object]:
    issues = payload["issues"]
    assert isinstance(issues, list)
    return next(issue for issue in issues if issue["severity"] == severity)


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


@pytest.mark.parametrize(
    "case_id",
    [
        "fault_ownership_leak_ko",
        "fault_idempotency_conflict_allows_new_task_ko",
        "weak_document_share_client_enforced_ko",
    ],
)
def test_korean_critical_findings_are_evidence_grounded_and_actionable(
    tmp_path: Path,
    case_id: str,
) -> None:
    ok, payload = _run_benchmark_case(tmp_path, case_id)

    assert not ok
    assert payload["readiness"]["status"] == "not_ready"
    issue = _first_issue_by_severity(payload, "Critical")
    evidence = issue.get("evidence")
    assert isinstance(evidence, list)
    assert evidence
    assert all(isinstance(excerpt, str) and excerpt.strip() for excerpt in evidence)
    assert all(len(excerpt) <= 260 for excerpt in evidence)
    assert issue["impact"].startswith("Generated code")
    assert issue["fix"].startswith(("Require", "Define", "Specify", "Replace", "Separate"))


def test_korean_weak_cases_do_not_emit_critical_findings_without_evidence(tmp_path: Path) -> None:
    missing_evidence: list[tuple[str, str]] = []
    korean_weak_cases = [
        case
        for case in benchmark_cases(include_gate_only_extra_cases=True, include_korean_cases=True)
        if case.get("language") == "ko" and case.get("expectation") == "weak"
    ]

    for case in korean_weak_cases:
        package = make_specguard_package(tmp_path, case)
        run_readiness_review(package)
        payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))
        for issue in payload["issues"]:
            if issue["severity"] == "Critical" and not issue.get("evidence"):
                missing_evidence.append((case["id"], issue["title"]))

    assert missing_evidence == []


def test_audit_domain_has_paired_ready_and_weak_guards(tmp_path: Path) -> None:
    ready_case = _benchmark_case("ready_audit_append_only_events")
    ready_ok, ready_payload = _run_benchmark_case(tmp_path, ready_case["id"])

    assert ready_case["domain"] == "audit"
    assert ready_ok
    assert ready_payload["readiness"]["status"] in {"ready", "ready_with_warnings"}
    assert ready_payload["summary"]["critical"] == 0

    weak_ok, weak_payload = _run_benchmark_case(tmp_path, "weak_audit_log_mutable")

    assert not weak_ok
    assert weak_payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(weak_payload, "Audit evidence is mutable")
    evidence = issue.get("evidence")
    assert issue["severity"] == "Critical"
    assert isinstance(evidence, list)
    assert evidence
    assert all(isinstance(excerpt, str) and excerpt.strip() for excerpt in evidence)
    assert all(len(excerpt) <= 260 for excerpt in evidence)
    assert issue["impact"].startswith("Generated code")
    assert issue["fix"].startswith("Require")


def test_korean_audit_counterpart_preserves_source_mapping_and_guard_shape(tmp_path: Path) -> None:
    ready_case = _benchmark_case("ready_audit_append_only_events_ko")
    ready_ok, ready_payload = _run_benchmark_case(tmp_path, ready_case["id"])

    assert ready_case["language"] == "ko"
    assert ready_case["domain"] == "audit"
    assert ready_case["source_case_id"] == "ready_audit_append_only_events"
    assert ready_ok
    assert ready_payload["readiness"]["status"] in {"ready", "ready_with_warnings"}
    assert ready_payload["summary"]["critical"] == 0

    weak_case = _benchmark_case("weak_audit_log_mutable_ko")
    weak_ok, weak_payload = _run_benchmark_case(tmp_path, weak_case["id"])

    assert weak_case["source_case_id"] == "weak_audit_log_mutable"
    assert not weak_ok
    assert weak_payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(weak_payload, "Audit evidence is mutable")
    evidence = issue.get("evidence")
    assert issue["severity"] == "Critical"
    assert isinstance(evidence, list)
    assert evidence
    assert issue["impact"].startswith("Generated code")
    assert issue["fix"].startswith("Require")


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
    ("language", "case_id", "review_level", "expected_status"),
    [
        ("ko", "ready_canonical_task_service_ko", "medium", "ready"),
        ("ko", "ready_canonical_task_service_ko", "low", "ready_with_warnings"),
        ("ko", "fault_title_no_trim_ko", "low", "not_ready"),
    ],
)
def test_korean_calibration_fixture_matrix_covers_readiness_statuses(
    tmp_path: Path,
    language: str,
    case_id: str,
    review_level: str,
    expected_status: str,
) -> None:
    case = _benchmark_case(case_id)
    package = make_specguard_package(tmp_path, case)
    run_readiness_review(package, review_level=review_level)
    payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert case.get("language", "en") == language
    assert payload["review_level"] == review_level
    assert payload["readiness"]["status"] == expected_status


def test_language_support_documents_korean_finding_quality_scope() -> None:
    doc = LANGUAGE_SUPPORT_DOC.read_text(encoding="utf-8")

    assert "## Korean Finding Quality Calibration" in doc
    assert "Current known Korean false positives" in doc
    assert "Current known Korean false negatives" in doc
    assert "None in the v0.4.0 Korean 98-case gate-only layer" in doc
    assert "missing `evidence[]` excerpts" in doc
    assert "READY_WITH_WARNINGS" in doc
    assert "NOT_READY" in doc
