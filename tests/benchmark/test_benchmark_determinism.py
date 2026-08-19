from __future__ import annotations

import pytest

from tools.readiness_engine import _context_fragments
from tools.spec_driven_ai_benchmark import (
    DETERMINISM_SCHEMA,
    build_critical_finding_evidence_summary,
    build_determinism_summary,
    compare_benchmark_runs,
    normalize_benchmark_payload,
    validate_critical_finding_evidence,
)


def _payload(
    worker_count: int,
    *,
    readiness: str = "not_ready",
    elapsed_seconds: float = 0.1,
    temp_root: str = "C:/tmp/benchmark-a",
    reverse_results: bool = False,
) -> dict:
    results = [
        {
            "workflow": "specguard_gate",
            "case": "case-a",
            "status": "blocked",
            "blocked": True,
            "implementation_ready": False,
            "readiness": readiness,
            "issue_summary": {"critical": 1, "major": 0, "minor": 0},
            "findings": [{
                "stable_id": "readiness-a",
                "severity": "Critical",
                "title": "Ownership boundary is unclear",
                "evidence": ["The caller can request every row."],
            }],
            "elapsed_seconds": elapsed_seconds,
            "package_path": "specguard_packages\\case-a",
            "stdout_tail": f"temporary root: {temp_root}",
        },
        {
            "workflow": "specguard_gate",
            "case": "case-b",
            "status": "passed",
            "blocked": False,
            "implementation_ready": True,
            "readiness": "ready",
            "issue_summary": {"critical": 0, "major": 0, "minor": 0},
            "findings": [],
            "elapsed_seconds": elapsed_seconds + 0.2,
            "package_path": "specguard_packages\\case-b",
            "stdout_tail": f"temporary root: {temp_root}",
        },
    ]
    if reverse_results:
        results.reverse()
    return {
        "schema": "specguard-impact-benchmark/v2",
        "started_at": "2026-08-19T00:00:00+00:00",
        "finished_at": "2026-08-19T00:01:00+00:00",
        "metadata": {
            "run_started_at": "2026-08-19T00:00:00+00:00",
            "run_finished_at": "2026-08-19T00:01:00+00:00",
            "environment": {
                "python_version": "3.11.0",
                "python_implementation": "CPython",
                "platform": "platform-a",
                "os_name": "posix",
                "notes": ["Local provider-free readiness gate benchmark."],
            },
            "run_config": {"max_workers": worker_count, "temp_root": temp_root},
        },
        "run_config": {"max_workers": worker_count, "temp_root": temp_root},
        "results": results,
        "aggregates": {"gate_only": {"evaluated_cases": 2, "blocked_weak_cases": 1}},
        "temp_removed": True,
    }


def test_normalized_payload_removes_only_documented_execution_variance() -> None:
    previous = normalize_benchmark_payload(_payload(1, elapsed_seconds=0.1))
    current = normalize_benchmark_payload(
        _payload(6, elapsed_seconds=99.9, temp_root="D:/other", reverse_results=True)
    )

    assert previous == current
    assert "started_at" not in previous
    assert previous["results"][0]["package_path"] == "specguard_packages/case-a"
    assert previous["results"][0]["findings"][0]["stable_id"] == "readiness-a"


def test_readiness_evidence_fragments_preserve_source_order() -> None:
    context = "alpha - beta - alpha - gamma"

    assert _context_fragments(context) == ["alpha", "beta", "gamma"]


def test_compare_reports_case_and_field_for_semantic_drift() -> None:
    comparison = compare_benchmark_runs(
        _payload(1),
        _payload(6, readiness="ready"),
    )

    assert comparison["identical"] is False
    assert comparison["differences"] == [{
        "case_id": "case-a",
        "field_path": "results[specguard_gate:case-a].readiness",
        "prior_value": "not_ready",
        "new_value": "ready",
    }]


def test_determinism_summary_requires_three_repeats_and_compares_worker_counts() -> None:
    runs = [
        {"worker_count": worker_count, "repeat": repeat, "payload": _payload(worker_count)}
        for worker_count in (1, 6)
        for repeat in range(1, 4)
    ]

    summary = build_determinism_summary(runs)

    assert summary["schema"] == DETERMINISM_SCHEMA
    assert summary["passed"] is True
    assert summary["repeat_counts"] == {"1": 3, "6": 3}
    assert summary["semantic_agreement"] is True
    assert summary["gate_metrics_match"] is True
    assert len(summary["comparisons"]) == 5


def test_critical_finding_evidence_is_required_or_explicitly_exempted() -> None:
    missing = [{
        "workflow": "specguard_gate",
        "case": "missing-evidence",
        "issue_summary": {"critical": 1},
        "findings": [{
            "stable_id": "readiness-missing",
            "severity": "Critical",
            "title": "Missing evidence",
            "evidence": [],
        }],
    }]
    summary = build_critical_finding_evidence_summary(missing)

    assert summary["valid"] is False
    with pytest.raises(ValueError, match="missing-evidence:readiness-missing"):
        validate_critical_finding_evidence(missing)

    exempted = [{
        **missing[0],
        "findings": [{
            **missing[0]["findings"][0],
            "evidence_exception": "Evidence is unavailable for this documented fixture.",
        }],
    }]
    assert build_critical_finding_evidence_summary(exempted)["valid"] is True
