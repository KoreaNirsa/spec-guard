from __future__ import annotations

import json
from pathlib import Path

from tools.spec_driven_ai_benchmark import (
    BENCHMARK_RESULT_SCHEMA,
    GATE_ONLY_EXTENDED_CASES,
    GATE_ONLY_EXTRA_CASES,
    READINESS_COVERAGE_GAP_TYPES,
    READINESS_COVERAGE_MATRIX_SCHEMA,
    build_benchmark_metadata,
    build_aggregates,
    build_benchmark_payload,
    build_readiness_coverage_matrix,
    benchmark_cases,
    load_readiness_coverage_results,
    main,
)


def test_benchmark_metadata_contains_version_traceability_keys() -> None:
    metadata = build_benchmark_metadata(run_started_at="2026-05-07T00:00:00Z")

    assert metadata["schema"] == BENCHMARK_RESULT_SCHEMA
    assert metadata["run_started_at"] == "2026-05-07T00:00:00Z"
    assert metadata["benchmark_script"]["path"] == "tools/spec_driven_ai_benchmark.py"
    assert metadata["benchmark_script"]["version"]
    assert metadata["specguard"]["package_version"] != ""
    assert metadata["specguard"]["git_commit"] != ""
    assert "git_tag" in metadata["specguard"]
    assert "git_dirty" in metadata["specguard"]
    assert metadata["environment"]["python_version"] != ""
    assert metadata["environment"]["python_implementation"] != ""
    assert metadata["environment"]["platform"] != ""
    assert metadata["environment"]["notes"]


def test_benchmark_payload_includes_metadata_and_result_schema() -> None:
    payload = build_benchmark_payload(
        root=Path("benchmark-root"),
        results=[],
        started_at="2026-05-07T00:00:00Z",
        finished_at="2026-05-07T00:10:00Z",
        max_workers=1,
        skip_codex=True,
        temp_removed=False,
    )

    assert payload["schema"] == BENCHMARK_RESULT_SCHEMA
    assert payload["metadata"]["schema"] == BENCHMARK_RESULT_SCHEMA
    assert payload["metadata"]["specguard"]["package_version"] != ""
    assert payload["metadata"]["specguard"]["git_commit"] != ""
    assert payload["metadata"]["run_config"]["max_workers"] == 1
    assert payload["metadata"]["run_config"]["skip_codex"] is True
    assert payload["metadata"]["fixture_counts"]["case_count"] == payload["case_count"]
    assert payload["metadata"]["fixture_counts"]["language_counts"] == payload["language_counts"]
    assert payload["temp_removed"] is False
    assert "aggregates" in payload
    assert payload["aggregates"]["impact"]["raw_contract_defect_rate"] is None
    assert payload["suite_counts"]["impact_v2"] == 18


def test_benchmark_cases_can_include_supplemental_gate_only_suite() -> None:
    cases = benchmark_cases(include_gate_only_extra_cases=True)

    assert len(GATE_ONLY_EXTRA_CASES) == 51
    assert len(GATE_ONLY_EXTENDED_CASES) == 41
    assert len(cases) == 110
    assert sum(1 for case in GATE_ONLY_EXTRA_CASES if case["expectation"] == "good") == 16
    assert sum(1 for case in GATE_ONLY_EXTRA_CASES if case["expectation"] == "weak") == 35
    assert sum(1 for case in GATE_ONLY_EXTENDED_CASES if case["expectation"] == "good") == 21
    assert sum(1 for case in GATE_ONLY_EXTENDED_CASES if case["expectation"] == "weak") == 20
    assert {case["suite"] for case in GATE_ONLY_EXTRA_CASES} == {"gate_only_supplemental_v1"}
    assert {case["suite"] for case in GATE_ONLY_EXTENDED_CASES} == {"gate_only_extended_v2"}


def test_benchmark_cases_can_include_korean_gate_only_layer() -> None:
    cases = benchmark_cases(include_gate_only_extra_cases=True, include_korean_cases=True)
    korean_cases = [case for case in cases if case["language"] == "ko"]

    assert len(cases) == 220
    assert len(korean_cases) == 110
    assert {case["suite"] for case in korean_cases} == {
        "impact_v2_ko",
        "gate_only_supplemental_v1_ko",
        "gate_only_extended_v2_ko",
    }
    assert sum(1 for case in korean_cases if case["expectation"] == "good") == 43
    assert sum(1 for case in korean_cases if case["expectation"] == "weak") == 67
    assert {case["source_case_id"] for case in korean_cases} == {
        case["id"]
        for case in benchmark_cases(include_gate_only_extra_cases=True)
    }
    assert all("한국어" in case["title"] for case in korean_cases)


def test_readiness_coverage_matrix_reports_fixture_gaps_without_running_gate() -> None:
    matrix = build_readiness_coverage_matrix(
        include_gate_only_extra_cases=True,
        include_korean_cases=True,
    )
    rows = matrix["rows"]
    first_row = rows[0]

    assert matrix["schema"] == READINESS_COVERAGE_MATRIX_SCHEMA
    assert matrix["case_count"] == 220
    assert matrix["language_counts"] == {"en": 110, "ko": 110}
    assert matrix["expectation_counts"] == {"good": 86, "weak": 134}
    assert matrix["actual_readiness_status_counts"] == {}
    assert matrix["readiness_result_coverage"] is None
    assert matrix["readiness_result_baseline"] is None
    assert set(READINESS_COVERAGE_GAP_TYPES) <= set(matrix["coverage_gaps"])
    assert matrix["coverage_gaps"]["english_only_source"] == []
    assert matrix["coverage_gaps"]["korean_only_source"] == []
    assert matrix["coverage_gaps"]["ready_only_domain_language"] == []
    assert matrix["coverage_gaps"]["weak_only_domain_language"] == []
    assert rows == sorted(
        rows,
        key=lambda row: (
            row["domain"],
            row["source_case_id"],
            row["language"],
            row["case_id"],
        ),
    )
    assert {
        "domain",
        "language",
        "case_id",
        "expectation",
        "source_case_id",
        "actual_readiness_status",
        "critical_count",
        "evidence_present",
        "gap_type",
        "gap_types",
        "follow_up_issue",
        "follow_up_issues",
    } <= set(first_row)
    assert all(row["actual_readiness_status"] is None for row in rows)
    assert all(row["critical_count"] is None for row in rows)
    assert all(row["evidence_present"] is None for row in rows)
    first_domain_row = matrix["domain_language_coverage"][0]
    assert {
        "domain",
        "language",
        "ready_case_count",
        "weak_case_count",
        "actual_readiness_status_counts",
        "critical_case_count",
        "evidence_present_counts",
        "source_counterpart_gap_count",
        "gap_type",
    } <= set(first_domain_row)
    assert first_domain_row["actual_readiness_status_counts"] == {}
    assert first_domain_row["critical_case_count"] == 0
    assert first_domain_row["evidence_present_counts"]["unknown"] == (
        first_domain_row["ready_case_count"] + first_domain_row["weak_case_count"]
    )
    assert first_domain_row["source_counterpart_gap_count"] == 0


def test_readiness_coverage_matrix_can_surface_results_when_available() -> None:
    cases = [{
        "id": "ready_fixture",
        "suite": "impact_v2",
        "domain": "task_service",
        "language": "en",
        "source_case_id": "ready_fixture",
        "category": "ready_reference",
        "expectation": "good",
        "title": "Ready fixture",
        "risk": "Baseline ready fixture.",
        "spec": "Spec.",
        "technical_design": "Design.",
    }]
    matrix = build_readiness_coverage_matrix(
        cases=cases,
        results=[{
            "workflow": "specguard_gate",
            "case": "ready_fixture",
            "readiness": "ready",
            "implementation_ready": True,
            "issue_summary": {"critical": 0, "major": 0, "minor": 0},
            "findings": [],
        }],
    )
    row = matrix["rows"][0]

    assert row["actual_readiness_status"] == "ready"
    assert row["actual_implementation_ready"] is True
    assert row["critical_count"] == 0
    assert row["evidence_present"] is False
    assert row["gap_types"] == ["english_only_source", "ready_only_domain_language"]
    assert row["follow_up_issue"] == "#182"
    assert matrix["actual_readiness_status_counts"] == {"ready": 1}
    assert matrix["domain_language_coverage"] == [{
        "domain": "task_service",
        "language": "en",
        "ready_case_count": 1,
        "weak_case_count": 0,
        "actual_readiness_status_counts": {"ready": 1},
        "critical_case_count": 0,
        "evidence_present_counts": {"true": 0, "false": 1, "unknown": 0},
        "source_counterpart_gap_count": 1,
        "gap_type": "ready_only_domain_language",
    }]
    assert matrix["readiness_result_coverage"] == {
        "expected_cases": 1,
        "evaluated_cases": 1,
        "missing_cases": 0,
        "unexpected_cases": 0,
        "is_complete": True,
    }
    assert matrix["readiness_result_baseline"]["evaluated_cases"] == 1
    assert matrix["readiness_result_baseline"]["false_positive_rate"] == 0.0


def test_readiness_coverage_matrix_preserves_missing_implementation_ready() -> None:
    cases = [{
        "id": "ready_fixture",
        "suite": "impact_v2",
        "domain": "task_service",
        "language": "en",
        "source_case_id": "ready_fixture",
        "category": "ready_reference",
        "expectation": "good",
        "title": "Ready fixture",
        "risk": "Baseline ready fixture.",
        "spec": "Spec.",
        "technical_design": "Design.",
    }]
    matrix = build_readiness_coverage_matrix(
        cases=cases,
        results=[{
            "workflow": "specguard_gate",
            "case": "ready_fixture",
            "readiness": "ready",
        }],
    )
    row = matrix["rows"][0]

    assert row["actual_readiness_status"] == "ready"
    assert row["actual_implementation_ready"] is None


def test_readiness_coverage_matrix_cli_writes_documented_json(tmp_path: Path) -> None:
    output = tmp_path / "readiness-coverage-matrix.json"
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps({
            "results": [{
                "workflow": "specguard_gate",
                "case": "ready_admin_role_audit",
                "readiness": "ready_with_warnings",
                "implementation_ready": True,
                "issue_summary": {"critical": 0, "major": 1, "minor": 0},
            }],
        }),
        encoding="utf-8",
    )

    assert main([
        "--coverage-matrix",
        "--coverage-matrix-results",
        str(results),
        "--include-gate-only-extra-cases",
        "--include-korean-cases",
        "--output",
        str(output),
    ]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == READINESS_COVERAGE_MATRIX_SCHEMA
    assert payload["case_count"] == 220
    assert payload["source"]["results_path"] == str(results).replace("\\", "/")
    assert payload["actual_readiness_status_counts"] == {"ready_with_warnings": 1}
    assert payload["readiness_result_coverage"] == {
        "expected_cases": 220,
        "evaluated_cases": 1,
        "missing_cases": 219,
        "unexpected_cases": 0,
        "is_complete": False,
    }
    assert payload["readiness_result_baseline"] is None
    assert payload["readiness_result_baseline_by_language"] is None
    assert payload["rows"][0]["actual_readiness_status"] == "ready_with_warnings"


def test_checked_in_readiness_coverage_matrix_matches_fixture_source() -> None:
    matrix_path = Path("docs/benchmark-results/readiness-coverage-matrix.json")
    results_path = Path("docs/benchmark-results/specguard-gate-only-v0.4.3.json")

    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    expected = build_readiness_coverage_matrix(
        results=load_readiness_coverage_results(results_path),
        results_source="docs/benchmark-results/specguard-gate-only-v0.4.3.json",
        include_gate_only_extra_cases=True,
        include_korean_cases=True,
    )

    assert payload == expected


def test_checked_in_gate_only_benchmark_records_refresh_metadata() -> None:
    results_path = Path("docs/benchmark-results/specguard-gate-only-v0.4.3.json")

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    metadata = payload["metadata"]

    assert metadata["benchmark_script"]["version"] == payload["benchmark_script_version"]
    assert metadata["benchmark_script"]["version"] == "8"
    assert metadata["run_config"] == payload["run_config"]
    assert metadata["run_config"]["max_workers"] == 6
    assert metadata["run_config"]["skip_codex"] is True
    assert metadata["run_config"]["include_gate_only_extra_cases"] is True
    assert metadata["run_config"]["include_korean_cases"] is True
    assert metadata["specguard"]["git_dirty"] is False
    assert metadata["fixture_counts"]["case_count"] == payload["case_count"] == 220
    assert metadata["fixture_counts"]["language_counts"] == payload["language_counts"] == {
        "en": 110,
        "ko": 110,
    }
    assert payload["aggregates"]["gate_only"]["false_positive_cases"] == []
    assert payload["aggregates"]["gate_only"]["false_negative_cases"] == []
    assert payload["determinism"]["passed"] is True
    assert payload["determinism"]["repeat_counts"] == {"1": 3, "6": 3}
    assert payload["determinism"]["gate_metrics_match"] is True
    assert payload["critical_finding_evidence"]["valid"] is True
    assert metadata["environment"]["python_version"]
    assert metadata["environment"]["notes"]


def test_benchmark_payload_reports_language_metrics() -> None:
    cases = benchmark_cases(include_gate_only_extra_cases=True, include_korean_cases=True)
    results = [
        {
            "workflow": "specguard_gate",
            "case": "ready_canonical_task_service",
            "implementation_ready": True,
        },
        {
            "workflow": "specguard_gate",
            "case": "fault_ownership_leak_ko",
            "implementation_ready": False,
        },
    ]

    payload = build_benchmark_payload(
        root=Path("benchmark-root"),
        results=results,
        cases=cases,
        started_at="2026-05-07T00:00:00Z",
        finished_at="2026-05-07T00:10:00Z",
        max_workers=1,
        skip_codex=True,
        include_gate_only_extra_cases=True,
        include_korean_cases=True,
        temp_removed=False,
    )

    assert payload["language_counts"] == {"en": 110, "ko": 110}
    assert payload["aggregates"]["gate_by_language"]["en"]["evaluated_cases"] == 1
    assert payload["aggregates"]["gate_by_language"]["ko"]["evaluated_cases"] == 1
    assert payload["aggregates"]["gate_by_language"]["ko"]["blocked_weak_cases"] == 1


def test_impact_aggregates_track_prevented_exposure_and_gate_errors() -> None:
    results = [
        {
            "workflow": "raw_ai",
            "case": "fault_ownership_leak",
            "score": {"contract_defects": 2, "contract_defect_rate": 20.0},
        },
        {
            "workflow": "specguard_gate",
            "case": "fault_ownership_leak",
            "implementation_ready": False,
        },
        {
            "workflow": "specguard_gate",
            "case": "ready_canonical_task_service",
            "implementation_ready": True,
        },
    ]

    aggregates = build_aggregates(results)

    assert aggregates["impact"]["blocked_before_codegen"] == 1
    assert aggregates["impact"]["prevented_exposure_cases"] == 1
    assert aggregates["impact"]["prevented_exposure_rate"] == 100.0
    assert aggregates["impact"]["false_positive_rate"] == 0.0


def test_gate_only_aggregates_compare_against_pr136_baseline() -> None:
    results = [
        {
            "workflow": "specguard_gate",
            "case": "fault_ownership_leak",
            "implementation_ready": False,
        },
        {
            "workflow": "specguard_gate",
            "case": "fault_deleted_visible",
            "implementation_ready": False,
        },
        {
            "workflow": "specguard_gate",
            "case": "ready_canonical_task_service",
            "implementation_ready": True,
        },
    ]

    aggregates = build_aggregates(results)
    comparison = aggregates["pr136_gate_baseline_comparison"]

    assert comparison["baseline_pr136"]["prevented_exposure_rate"] == 27.3
    assert comparison["current_gate_only"]["prevented_exposure_cases_against_pr136_raw_defects"] == 2
    assert aggregates["gate_by_suite"]["impact_v2"]["blocked_weak_cases"] == 2
