from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.report_language_benchmark import (
    REPORT_LANGUAGE_BENCHMARK_SCHEMA,
    build_report_language_benchmark,
)
from tools.spec_driven_ai_benchmark import main


@pytest.fixture(scope="module")
def benchmark_payload(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    return build_report_language_benchmark(tmp_path_factory.mktemp("report-language-benchmark"))


def test_report_language_benchmark_covers_required_matrix(
    benchmark_payload: dict[str, object],
) -> None:
    assert benchmark_payload["schema"] == REPORT_LANGUAGE_BENCHMARK_SCHEMA
    assert benchmark_payload["scenario_count"] == 12
    assert benchmark_payload["summary"] == {"passed": 12, "failed": 0, "all_passed": True}

    resolution_rows = benchmark_payload["resolution_rows"]
    assert isinstance(resolution_rows, list)
    assert all(row["resolution_matches"] for row in resolution_rows)
    assert all(row["machine_contract_invariant"] for row in resolution_rows)
    assert all(row["authored_files_unchanged"] for row in resolution_rows)
    assert all(all(row["human_checks"].values()) for row in resolution_rows)

    refresh_rows = benchmark_payload["artifact_refresh_rows"]
    assert isinstance(refresh_rows, list)
    assert all(row["passed"] for row in refresh_rows)
    assert benchmark_payload["legacy_rows"] == [{
        "id": "legacy_json_without_report_language",
        "expected_resolution": {"code": "en", "source": "fallback", "fallback_used": True},
        "actual_resolution": {"code": "en", "source": "fallback", "fallback_used": True},
        "passed": True,
    }]


def test_report_language_benchmark_cli_writes_json(tmp_path: Path) -> None:
    output = tmp_path / "report-language-matrix.json"

    assert main(["--report-language-matrix", "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == REPORT_LANGUAGE_BENCHMARK_SCHEMA
    assert payload["summary"]["all_passed"] is True


def test_report_language_matrix_ignores_process_conversation_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPECGUARD_CONVERSATION_LANGUAGE", "ko")

    payload = build_report_language_benchmark(tmp_path)
    rows = {row["id"]: row for row in payload["resolution_rows"]}

    assert rows["no_conversation_english_spec"]["actual_resolution"] == {
        "code": "en",
        "source": "spec",
        "fallback_used": False,
    }
    assert rows["unsupported_short_code_inconclusive_spec"]["actual_resolution"] == {
        "code": "en",
        "source": "fallback",
        "fallback_used": True,
    }


def test_checked_in_report_language_matrix_matches_current_behavior(
    benchmark_payload: dict[str, object],
) -> None:
    checked_in = json.loads(
        Path("docs/benchmark-results/report-language-matrix-v0.4.3.json").read_text(encoding="utf-8")
    )

    assert checked_in == benchmark_payload
