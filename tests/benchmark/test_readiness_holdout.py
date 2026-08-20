from __future__ import annotations

from tools.readiness_holdout import (
    HOLDOUT_PATH,
    build_metrics,
    load_holdout,
    main,
    validate_holdout,
    wilson_interval,
)


def test_checked_in_holdout_is_frozen_and_separate() -> None:
    payload = load_holdout()

    assert validate_holdout(payload) == []
    assert payload["status"] == "frozen"
    assert payload["corpus_scope"] == "holdout"
    assert payload["freeze_policy"]["expectation_changes_require_explicit_review"] is True
    assert payload["freeze_policy"]["heuristic_tuning_uses_holdout_failures"] is False
    assert len(payload["pairs"]) >= 30
    assert {pair["language"] for pair in payload["pairs"]} == {"en", "ko", "mixed"}
    assert len({pair["semantic_scenario"] for pair in payload["pairs"]}) == len(payload["pairs"])
    assert all(
        pair["provenance"]["not_calibrated_fixture"]
        for pair in payload["pairs"]
    )


def test_holdout_validation_requires_non_empty_version() -> None:
    missing_version = load_holdout()
    missing_version.pop("version")
    blank_version = load_holdout()
    blank_version["version"] = " "

    for payload in (missing_version, blank_version):
        assert "version must be a non-empty string" in validate_holdout(payload)


def test_holdout_records_resolved_label_disagreement() -> None:
    payload = load_holdout()
    resolved = [
        variant
        for pair in payload["pairs"]
        for variant_name in ("safe", "unsafe")
        for variant in [pair[variant_name]]
        if variant["adjudication"]["status"] == "resolved"
    ]

    assert resolved
    assert all(variant["adjudication"]["final_label"] == variant["expected"] for variant in resolved)


def test_wilson_interval_is_bounded_and_absent_for_empty_sample() -> None:
    interval = wilson_interval(30, 30)

    assert interval is not None
    assert 0 <= interval[0] <= interval[1] <= 1
    assert wilson_interval(0, 0) is None


def test_metrics_include_classification_rates_and_confidence_intervals() -> None:
    records = [
        {"domain": "ownership", "language": "en", "expected": "weak", "blocked": True},
        {"domain": "ownership", "language": "en", "expected": "ready", "blocked": False},
        {"domain": "ownership", "language": "ko", "expected": "weak", "blocked": False},
        {"domain": "cache", "language": "ko", "expected": "ready", "blocked": True},
    ]

    metrics = build_metrics(records)

    assert metrics["overall"]["confusion_matrix"] == {
        "true_positive_blocked_weak": 1,
        "true_negative_allowed_ready": 1,
        "false_positive_blocked_ready": 1,
        "false_negative_allowed_weak": 1,
    }
    assert metrics["overall"]["weak_recall"]["percent"] == 50.0
    assert metrics["overall"]["weak_recall"]["confidence_interval_95"] is not None
    assert set(metrics["by_language"]) == {"en", "ko"}
    assert set(metrics["by_domain"]) == {"cache", "ownership"}


def test_holdout_cli_validates_checked_in_corpus() -> None:
    assert main(["--validate", "--corpus", str(HOLDOUT_PATH)]) == 0
