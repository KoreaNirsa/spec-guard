from __future__ import annotations

from pathlib import Path

from tools.spec_driven_ai_benchmark import (
    BENCHMARK_RESULT_SCHEMA,
    build_benchmark_metadata,
    build_benchmark_payload,
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
    metadata = build_benchmark_metadata(run_started_at="2026-05-07T00:00:00Z")
    payload = build_benchmark_payload(Path("benchmark-root"), [], metadata, temp_removed=False)

    assert payload["metadata"]["schema"] == BENCHMARK_RESULT_SCHEMA
    assert payload["metadata"]["specguard"]["package_version"] != ""
    assert payload["metadata"]["specguard"]["git_commit"] != ""
    assert payload["temp_removed"] is False
    assert "aggregates" in payload
