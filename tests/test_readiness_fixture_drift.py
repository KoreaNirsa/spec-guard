from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.spec_driven_ai_benchmark import (
    BENCHMARK_SCRIPT_VERSION,
    benchmark_cases,
)


EXPECTED_SUMMARY_PATH = (
    Path(__file__).parent / "fixtures" / "readiness-fixture-drift-summary.json"
)


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _build_fixture_drift_summary() -> dict[str, Any]:
    cases = benchmark_cases(
        include_gate_only_extra_cases=True,
        include_korean_cases=True,
    )
    source_case_mappings: dict[str, dict[str, Any]] = {}
    expectation_counts_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    domain_language_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    for case in cases:
        language = case.get("language", "en")
        expectation = case["expectation"]
        domain = case.get("domain", "task_service")
        source_case_id = case.get("source_case_id", case["id"])

        expectation_counts_by_language[language][expectation] += 1
        domain_language_counts[(domain, language)][expectation] += 1

        source_mapping = source_case_mappings.setdefault(
            source_case_id,
            {
                "source_case_id": source_case_id,
                "domains": set(),
                "expectations": set(),
                "languages": set(),
                "case_ids_by_language": {},
                "categories_by_language": {},
                "suites_by_language": {},
            },
        )
        source_mapping["domains"].add(domain)
        source_mapping["expectations"].add(expectation)
        source_mapping["languages"].add(language)
        source_mapping["case_ids_by_language"][language] = case["id"]
        source_mapping["categories_by_language"][language] = case["category"]
        source_mapping["suites_by_language"][language] = case.get("suite", "impact_v2")

    normalized_source_mappings = []
    for source_mapping in source_case_mappings.values():
        normalized_source_mappings.append({
            "source_case_id": source_mapping["source_case_id"],
            "domains": sorted(source_mapping["domains"]),
            "expectations": sorted(source_mapping["expectations"]),
            "languages": sorted(source_mapping["languages"]),
            "case_ids_by_language": {
                key: source_mapping["case_ids_by_language"][key]
                for key in sorted(source_mapping["case_ids_by_language"])
            },
            "categories_by_language": {
                key: source_mapping["categories_by_language"][key]
                for key in sorted(source_mapping["categories_by_language"])
            },
            "suites_by_language": {
                key: source_mapping["suites_by_language"][key]
                for key in sorted(source_mapping["suites_by_language"])
            },
        })

    domain_language_summary = []
    for (domain, language), counts in sorted(domain_language_counts.items()):
        domain_language_summary.append({
            "domain": domain,
            "language": language,
            "good": counts.get("good", 0),
            "weak": counts.get("weak", 0),
        })

    return {
        "schema": "specguard-readiness-fixture-drift-summary/v1",
        "benchmark_script_version": BENCHMARK_SCRIPT_VERSION,
        "case_source": "tools/spec_driven_ai_benchmark.py::benchmark_cases",
        "include_gate_only_extra_cases": True,
        "include_korean_cases": True,
        "case_count": len(cases),
        "source_case_count": len(source_case_mappings),
        "suite_counts": _sorted_counts(Counter(case.get("suite", "impact_v2") for case in cases)),
        "language_counts": _sorted_counts(Counter(case.get("language", "en") for case in cases)),
        "expectation_counts": _sorted_counts(Counter(case["expectation"] for case in cases)),
        "expectation_counts_by_language": {
            language: _sorted_counts(counts)
            for language, counts in sorted(expectation_counts_by_language.items())
        },
        "domain_language_summary": domain_language_summary,
        "source_case_mappings": sorted(
            normalized_source_mappings,
            key=lambda source_mapping: source_mapping["source_case_id"],
        ),
    }


def test_readiness_fixture_drift_summary_matches_checked_in_snapshot() -> None:
    expected = json.loads(EXPECTED_SUMMARY_PATH.read_text(encoding="utf-8"))
    actual = _build_fixture_drift_summary()

    assert actual == expected


def test_readiness_fixture_drift_summary_keeps_paired_language_mapping() -> None:
    summary = _build_fixture_drift_summary()

    assert summary["language_counts"] == {"en": 98, "ko": 98}
    assert summary["expectation_counts_by_language"] == {
        "en": {"good": 33, "weak": 65},
        "ko": {"good": 33, "weak": 65},
    }
    assert all(
        source_mapping["languages"] == ["en", "ko"]
        for source_mapping in summary["source_case_mappings"]
    )
