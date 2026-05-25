from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.readiness_engine import (
    READINESS_EVIDENCE_EXCERPT_LIMIT,
    is_review_source_artifact,
    run_readiness_review,
)
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


def _normalized_source_text(package: Path) -> str:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in package.rglob("*.md")
        if is_review_source_artifact(path.relative_to(package))
    )
    return " ".join(source.lower().split())


def _excerpt_is_source_derived(excerpt: str, source_text: str) -> bool:
    normalized = " ".join(excerpt.lower().replace("[...]", " ").split()).strip()
    normalized = normalized.removesuffix("...").strip()
    if not normalized:
        return False
    if normalized in source_text:
        return True
    words = normalized.split()
    if len(words) < 6:
        return False
    return any(" ".join(words[index:index + 6]) in source_text for index in range(len(words) - 5))


def _assert_critical_issue_shape(issue: dict[str, object], package: Path) -> None:
    assert issue["severity"] == "Critical"

    evidence = issue.get("evidence")
    assert isinstance(evidence, list)
    assert evidence
    assert all(isinstance(excerpt, str) and excerpt.strip() for excerpt in evidence)
    assert all(len(excerpt) <= READINESS_EVIDENCE_EXCERPT_LIMIT for excerpt in evidence)

    source_text = _normalized_source_text(package)
    assert all(_excerpt_is_source_derived(excerpt, source_text) for excerpt in evidence)

    impact = issue.get("impact")
    assert isinstance(impact, str)
    assert impact.startswith(("Generated code", "A generated API", "AI implementation"))

    fix = issue.get("fix")
    assert isinstance(fix, str)
    assert fix.startswith(("Require", "Define", "Specify", "Replace", "Separate", "Resolve", "Include"))


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


def test_deterministic_critical_findings_have_actionable_source_evidence(tmp_path: Path) -> None:
    checked_critical = 0
    weak_cases = [
        case
        for case in benchmark_cases(include_gate_only_extra_cases=True, include_korean_cases=True)
        if case.get("expectation") == "weak"
    ]

    for case in weak_cases:
        package = make_specguard_package(tmp_path, case)
        run_readiness_review(package)
        payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))
        critical_issues = [issue for issue in payload["issues"] if issue["severity"] == "Critical"]
        assert critical_issues, case["id"]
        for issue in critical_issues:
            checked_critical += 1
            _assert_critical_issue_shape(issue, package)

    assert checked_critical > 0


def test_placeholder_critical_finding_has_source_evidence(tmp_path: Path) -> None:
    package = _write_feature(
        tmp_path,
        spec_lines=[
            "# Spec: placeholder architecture",
            "",
            "## Requirements",
            "",
            "- TaskService creates tasks for the authenticated user.",
            "- Title must be non-blank after trimming.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Non-blank title creates a task.",
            "- [ ] Blank title returns TaskError.",
            "",
            "## Error Cases",
            "",
            "- Blank title returns TaskError.",
        ],
        design_lines=[
            "# Technical Design: placeholder architecture",
            "",
            "## Architecture",
            "",
            "- TBD",
            "",
            "## Data Flow",
            "",
            "1. Controller receives create request.",
            "2. Service trims title and stores the task.",
            "",
            "## State",
            "",
            "- Task states: active, deleted.",
            "",
            "## Failure Handling",
            "",
            "- Blank title returns TaskError.",
        ],
    )

    result = run_readiness_review(package)
    payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert not result.ok
    assert payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(payload, "Architecture is still a placeholder")
    _assert_critical_issue_shape(issue, package)


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
    assert all(isinstance(excerpt, str) and excerpt.strip() for excerpt in evidence)
    assert all(len(excerpt) <= 260 for excerpt in evidence)
    assert issue["impact"].startswith("Generated code")
    assert issue["fix"].startswith("Require")


def test_background_job_domain_has_paired_ready_and_weak_guards(tmp_path: Path) -> None:
    ready_case = _benchmark_case("ready_background_job_retry_budget")
    ready_ok, ready_payload = _run_benchmark_case(tmp_path, ready_case["id"])

    assert ready_case["domain"] == "background_jobs"
    assert ready_ok
    assert ready_payload["readiness"]["status"] in {"ready", "ready_with_warnings"}
    assert ready_payload["summary"]["critical"] == 0

    weak_case = _benchmark_case("weak_background_job_retry_unbounded")
    weak_package = make_specguard_package(tmp_path, weak_case)
    weak_result = run_readiness_review(weak_package)
    weak_payload = json.loads(
        weak_package.joinpath("readiness-review.json").read_text(encoding="utf-8"),
    )

    assert not weak_result.ok
    assert weak_payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(weak_payload, "Background job retry contract is unsafe")
    _assert_critical_issue_shape(issue, weak_package)


def test_korean_background_job_counterpart_preserves_source_mapping_and_guard_shape(
    tmp_path: Path,
) -> None:
    ready_case = _benchmark_case("ready_background_job_retry_budget_ko")
    ready_ok, ready_payload = _run_benchmark_case(tmp_path, ready_case["id"])

    assert ready_case["language"] == "ko"
    assert ready_case["domain"] == "background_jobs"
    assert ready_case["source_case_id"] == "ready_background_job_retry_budget"
    assert ready_ok
    assert ready_payload["readiness"]["status"] in {"ready", "ready_with_warnings"}
    assert ready_payload["summary"]["critical"] == 0

    weak_case = _benchmark_case("weak_background_job_retry_unbounded_ko")
    weak_package = make_specguard_package(tmp_path, weak_case)
    weak_result = run_readiness_review(weak_package)
    weak_payload = json.loads(
        weak_package.joinpath("readiness-review.json").read_text(encoding="utf-8"),
    )

    assert weak_case["source_case_id"] == "weak_background_job_retry_unbounded"
    assert not weak_result.ok
    assert weak_payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(weak_payload, "Background job retry contract is unsafe")
    _assert_critical_issue_shape(issue, weak_package)


@pytest.mark.parametrize(
    ("language", "spec_lines", "design_lines", "expected_evidence"),
    [
        (
            "en",
            [
                "# Spec: workspace invite recipient binding",
                "",
                "## Requirements",
                "",
                "- InviteService creates workspace invite tokens for a target email.",
                "- Any authenticated user can accept an invite when they know the token.",
                "- The accept flow does not need to verify that the current user's email matches the target email.",
                "",
                "## Acceptance Criteria",
                "",
                "- [ ] A user with the token is added to the workspace.",
                "",
                "## Error Cases",
                "",
                "- Missing token returns 400.",
            ],
            [
                "# Technical Design: workspace invite recipient binding",
                "",
                "## Architecture",
                "",
                "- InviteService owns invite creation and acceptance.",
                "- InviteRepository stores invite_id, token_hash, workspace_id, target_email, role, expires_at, accepted_at.",
                "",
                "## Data Flow",
                "",
                "1. Admin creates an invite for target_email.",
                "2. User submits token.",
                "3. Service resolves invite by token_hash only and creates membership for the current user without comparing target_email.",
                "",
                "## State",
                "",
                "- Invite states: pending, accepted, expired.",
                "- accepted and expired are terminal.",
                "",
                "## Failure Handling",
                "",
                "- Missing token returns 400.",
                "- Expired token returns 410.",
            ],
            "any authenticated user can accept an invite",
        ),
        (
            "ko",
            [
                "# Spec: workspace invite recipient binding",
                "",
                "## Requirements",
                "",
                "- InviteService는 target_email로 워크스페이스 초대 토큰을 만든다.",
                "- 토큰을 아는 모든 사용자가 초대를 수락할 수 있다.",
                "- 수락 흐름은 현재 사용자 이메일이 target_email과 일치하는지 검증하지 않는다.",
                "",
                "## Acceptance Criteria",
                "",
                "- [ ] 토큰을 제출한 사용자가 워크스페이스 멤버가 된다.",
                "",
                "## Error Cases",
                "",
                "- 토큰 누락은 400을 반환한다.",
            ],
            [
                "# Technical Design: workspace invite recipient binding",
                "",
                "## Architecture",
                "",
                "- InviteService가 초대 생성과 수락을 담당한다.",
                "- InviteRepository는 invite_id, token_hash, workspace_id, target_email, role, expires_at, accepted_at을 저장한다.",
                "",
                "## Data Flow",
                "",
                "1. 관리자가 target_email로 초대를 만든다.",
                "2. 사용자가 토큰을 제출한다.",
                "3. 서비스는 token_hash만 조회하고 현재 사용자 이메일과 target_email을 비교하지 않은 채 멤버십을 생성한다.",
                "",
                "## State",
                "",
                "- 초대 상태는 pending, accepted, expired이다.",
                "- accepted와 expired는 terminal이다.",
                "",
                "## Failure Handling",
                "",
                "- 토큰 누락은 400을 반환한다.",
                "- 만료된 토큰은 410을 반환한다.",
            ],
            "토큰을 아는 모든 사용자가 초대를 수락할 수 있다",
        ),
    ],
)
def test_workspace_invite_recipient_false_negative_blocks_with_evidence(
    tmp_path: Path,
    language: str,
    spec_lines: list[str],
    design_lines: list[str],
    expected_evidence: str,
) -> None:
    package = _write_feature(tmp_path, spec_lines=spec_lines, design_lines=design_lines)

    result = run_readiness_review(package)
    payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert language in {"en", "ko"}
    assert not result.ok
    assert payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(payload, "Workspace invite recipient binding is unsafe")
    evidence = " ".join(issue.get("evidence", []))
    assert issue["severity"] == "Critical"
    assert expected_evidence in evidence
    assert issue["impact"].startswith("Generated code")
    assert issue["fix"].startswith("Require")


def test_workspace_invite_ambiguous_email_verification_still_blocks(tmp_path: Path) -> None:
    package = _write_feature(
        tmp_path,
        spec_lines=[
            "# Spec: ambiguous workspace invite recipient binding",
            "",
            "## Requirements",
            "",
            "- InviteService creates workspace invite tokens.",
            "- Users with the invite token can accept the invite.",
            "- Email verification succeeds before membership creation.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Valid invite token creates membership.",
            "- [ ] Expired token returns 410.",
            "",
            "## Error Cases",
            "",
            "- Missing token returns 400.",
            "- Expired token returns 410.",
        ],
        design_lines=[
            "# Technical Design: ambiguous workspace invite recipient binding",
            "",
            "## Architecture",
            "",
            "- InviteService owns invite lookup and acceptance.",
            "- InviteRepository stores token_hash and workspace_id.",
            "",
            "## Data Flow",
            "",
            "1. User submits token.",
            "2. Service resolves token_hash.",
            "3. Service creates membership after email verification succeeds.",
        ],
    )

    result = run_readiness_review(package)
    payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert not result.ok
    assert payload["readiness"]["status"] == "not_ready"
    issue = _issue_by_title(payload, "Workspace invite recipient binding is unsafe")
    assert issue["severity"] == "Critical"


@pytest.mark.parametrize(
    ("language", "spec_lines", "design_lines"),
    [
        (
            "en",
            [
                "# Spec: safe workspace invite recipient binding",
                "",
                "## Requirements",
                "",
                "- InviteService creates workspace invite tokens for invited_email.",
                "- A user with the invite token can accept only after the service verifies the authenticated user's verified email matches invited_email.",
                "- Invite tokens expire after 7 days.",
                "- Accepting an invite verifies that the authenticated user's verified email matches invited_email.",
                "- Email mismatch returns 403 and leaves the invite pending.",
                "",
                "## Acceptance Criteria",
                "",
                "- [ ] A user with the invite token and matching verified email is added to the workspace.",
                "- [ ] Matching invited_email creates membership.",
                "- [ ] Mismatched email returns 403.",
                "- [ ] Expired invite returns 410.",
                "",
                "## Error Cases",
                "",
                "- Missing token returns 400.",
                "- Email mismatch returns 403.",
                "- Expired token returns 410.",
            ],
            [
                "# Technical Design: safe workspace invite recipient binding",
                "",
                "## Architecture",
                "",
                "- InviteService owns invite creation, recipient verification, expiry, and acceptance.",
                "- InviteRepository stores invite_id, token_hash, workspace_id, invited_email, role, expires_at, accepted_at.",
                "",
                "## Data Flow",
                "",
                "1. Admin creates an invite for invited_email.",
                "2. User submits token.",
                "3. Service resolves token_hash, checks expiry, and compares invited_email to the authenticated user's verified email.",
                "4. Service creates membership only after the email comparison succeeds.",
                "",
                "## State",
                "",
                "- Invite states: pending, accepted, expired.",
                "- accepted and expired are terminal.",
                "",
                "## Failure Handling",
                "",
                "- Missing token returns 400.",
                "- Email mismatch returns 403.",
                "- Expired token returns 410.",
            ],
        ),
        (
            "ko",
            [
                "# Spec: safe workspace invite recipient binding",
                "",
                "## Requirements",
                "",
                "- InviteService는 invited_email에 묶인 워크스페이스 초대 토큰을 만든다.",
                "- 초대 토큰은 7일 후 만료된다.",
                "- 초대 수락은 인증된 사용자의 검증된 이메일이 invited_email과 일치하는지 서버에서 검증한다.",
                "- 이메일 불일치는 403을 반환하고 초대는 pending 상태로 남긴다.",
                "",
                "## Acceptance Criteria",
                "",
                "- [ ] invited_email이 일치하면 멤버십을 만든다.",
                "- [ ] 이메일이 일치하지 않으면 403을 반환한다.",
                "- [ ] 만료된 초대는 410을 반환한다.",
                "",
                "## Error Cases",
                "",
                "- 토큰 누락은 400을 반환한다.",
                "- 이메일 불일치는 403을 반환한다.",
                "- 만료된 토큰은 410을 반환한다.",
            ],
            [
                "# Technical Design: safe workspace invite recipient binding",
                "",
                "## Architecture",
                "",
                "- InviteService가 초대 생성, 수신자 검증, 만료, 수락을 담당한다.",
                "- InviteRepository는 invite_id, token_hash, workspace_id, invited_email, role, expires_at, accepted_at을 저장한다.",
                "",
                "## Data Flow",
                "",
                "1. 관리자가 invited_email로 초대를 만든다.",
                "2. 사용자가 토큰을 제출한다.",
                "3. 서비스는 token_hash를 조회하고 만료를 확인한 뒤 invited_email과 인증된 사용자의 검증된 이메일을 비교한다.",
                "4. 이메일 비교가 성공한 뒤에만 멤버십을 만든다.",
                "",
                "## State",
                "",
                "- 초대 상태는 pending, accepted, expired이다.",
                "- accepted와 expired는 terminal이다.",
                "",
                "## Failure Handling",
                "",
                "- 토큰 누락은 400을 반환한다.",
                "- 이메일 불일치는 403을 반환한다.",
                "- 만료된 토큰은 410을 반환한다.",
            ],
        ),
    ],
)
def test_workspace_invite_recipient_ready_reference_remains_allowed(
    tmp_path: Path,
    language: str,
    spec_lines: list[str],
    design_lines: list[str],
) -> None:
    package = _write_feature(tmp_path, spec_lines=spec_lines, design_lines=design_lines)

    result = run_readiness_review(package)
    payload = json.loads(package.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert language in {"en", "ko"}
    assert result.ok
    assert payload["readiness"]["status"] in {"ready", "ready_with_warnings"}
    assert payload["summary"]["critical"] == 0
    assert "Workspace invite recipient binding is unsafe" not in {issue["title"] for issue in payload["issues"]}


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
    assert "None in the recorded v0.4.1 Korean 99-case gate-only layer" in doc
    assert "100 English cases and 100 Korean cases" in doc
    assert "2 selected ready/reference fixture results as missing" in doc
    assert "missing `evidence[]` excerpts" in doc
    assert "READY_WITH_WARNINGS" in doc
    assert "NOT_READY" in doc
