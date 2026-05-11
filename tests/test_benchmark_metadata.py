from __future__ import annotations

from pathlib import Path

from tools.spec_driven_ai_benchmark import (
    BENCHMARK_RESULT_SCHEMA,
    GATE_ONLY_EXTRA_CASES,
    build_benchmark_metadata,
    build_aggregates,
    build_benchmark_payload,
    benchmark_cases,
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
    assert payload["temp_removed"] is False
    assert "aggregates" in payload
    assert payload["aggregates"]["impact"]["raw_contract_defect_rate"] is None
    assert payload["suite_counts"]["impact_v2"] == 18


def test_benchmark_cases_can_include_supplemental_gate_only_suite() -> None:
    cases = benchmark_cases(include_gate_only_extra_cases=True)

    assert len(GATE_ONLY_EXTRA_CASES) == 50
    assert len(cases) == 68
    assert sum(1 for case in GATE_ONLY_EXTRA_CASES if case["expectation"] == "good") == 15
    assert sum(1 for case in GATE_ONLY_EXTRA_CASES if case["expectation"] == "weak") == 35
    assert {case["suite"] for case in GATE_ONLY_EXTRA_CASES} == {"gate_only_supplemental_v1"}


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
