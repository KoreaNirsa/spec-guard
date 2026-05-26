from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from tools.post_run import derive_plugin_run_state, readiness_report_stale_reason
from tools.runner import run_pipeline


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "plugin-result-contract"
FIXTURE_NAMES = [
    "ready.json",
    "ready-with-warnings.json",
    "not-ready.json",
    "llm-cache-miss.json",
]
GENERATED_ARTIFACT_NAMES = {
    "readiness-review.md",
    "readiness-review.json",
    "readiness-review-detail.md",
    "readiness-review-detail.json",
    "implementation-output.md",
    "spec.proposed.md",
    "grill.md",
    "grill.json",
}
GENERATED_ARTIFACT_PREFIXES = (
    ".specguard/",
    "contracts/",
    "tests/",
)


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _write_review_sources(feature: Path) -> None:
    for name in ("discovery.md", "spec.md", "technical-design.md"):
        feature.joinpath(name).write_text(f"# {name}\n", encoding="utf-8")


def _is_generated_source_path(path: str) -> bool:
    return path in GENERATED_ARTIFACT_NAMES or path.startswith(GENERATED_ARTIFACT_PREFIXES)


def _handoff_available(feature_dir: Path, payload: dict[str, object]) -> bool:
    readiness = payload.get("readiness", {})
    if not isinstance(readiness, dict):
        return False
    return (
        readiness.get("status") in {"ready", "ready_with_warnings"}
        and readiness.get("implementation_ready") is True
        and (feature_dir / "implementation-output.md").exists()
    )


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_plugin_result_contract_fixtures_expose_stable_consumer_shape(fixture_name: str) -> None:
    payload = _load_fixture(fixture_name)

    assert payload["schema_version"] == "0.1"
    assert payload["review_mode"] in {"initial", "verification"}
    assert payload["review_level"] in {"low", "medium", "high"}
    assert isinstance(payload["blocked"], bool)

    readiness = payload["readiness"]
    assert isinstance(readiness, dict)
    assert readiness["status"] in {"ready", "ready_with_warnings", "not_ready"}
    assert isinstance(readiness["implementation_ready"], bool)
    assert isinstance(readiness["criteria"], dict)

    summary = payload["summary"]
    assert isinstance(summary, dict)
    assert set(summary) >= {"critical", "major", "minor"}
    assert all(isinstance(summary[key], int) for key in ("critical", "major", "minor"))

    issues = payload["issues"]
    assert isinstance(issues, list)
    for issue in issues:
        assert set(issue) >= {"severity", "title", "description", "impact", "fix"}
        assert issue["severity"] in {"Critical", "Major", "Minor"}

    source_input = payload["input"]
    assert isinstance(source_input, dict)
    assert isinstance(source_input["artifact_count"], int)
    assert isinstance(source_input["total_characters"], int)
    assert isinstance(source_input["artifacts"], list)
    assert source_input["artifact_count"] == len(source_input["artifacts"])
    for artifact in source_input["artifacts"]:
        assert set(artifact) >= {"path", "characters"}
        assert not _is_generated_source_path(artifact["path"])
        assert isinstance(artifact["characters"], int)

    review_input = payload.get("review_input")
    if review_input is not None:
        assert isinstance(review_input, dict)
        assert set(review_input) >= {"mode", "review_level", "artifact_count", "total_characters", "artifacts"}

    cache = payload.get("cache")
    if cache is not None:
        assert isinstance(cache, dict)
        assert cache["enabled"] is True
        assert isinstance(cache["hit"], bool)
        assert isinstance(cache["stored"], bool)
        assert set(cache) >= {"review_mode", "review_level", "provider", "model", "prompt_version"}


def test_plugin_result_contract_fixtures_cover_minimum_consumer_states() -> None:
    payloads = [_load_fixture(name) for name in FIXTURE_NAMES]
    statuses = {payload["readiness"]["status"] for payload in payloads}

    assert {"ready", "ready_with_warnings", "not_ready"} <= statuses
    assert any("cache" in payload for payload in payloads)
    assert any(payload["blocked"] is True for payload in payloads)
    assert any(payload["blocked"] is False for payload in payloads)


def test_plugin_result_contract_handoff_availability_uses_status_and_file_existence(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    ready_payload = _load_fixture("ready.json")
    not_ready_payload = _load_fixture("not-ready.json")

    assert _handoff_available(feature, ready_payload) is False

    feature.joinpath("implementation-output.md").write_text("# Handoff\n", encoding="utf-8")

    assert _handoff_available(feature, ready_payload) is True
    assert _handoff_available(feature, not_ready_payload) is False


def test_plugin_result_contract_stale_review_is_derived_from_source_mtime(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    for name in ("discovery.md", "spec.md", "technical-design.md"):
        feature.joinpath(name).write_text(f"# {name}\n", encoding="utf-8")
    feature.joinpath("readiness-review.json").write_text(
        json.dumps(_load_fixture("ready.json")),
        encoding="utf-8",
    )

    older = time.time() - 200
    report_time = time.time() - 100
    for name in ("discovery.md", "spec.md", "technical-design.md"):
        os.utime(feature / name, (older, older))
    os.utime(feature / "readiness-review.json", (report_time, report_time))
    os.utime(feature / "spec.md", None)

    stale_reason = readiness_report_stale_reason(feature)

    assert stale_reason is not None
    assert "spec.md" in stale_reason


def test_plugin_result_contract_stale_review_detects_new_source_artifact(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    _write_review_sources(feature)
    feature.joinpath("readiness-review.json").write_text(
        json.dumps(_load_fixture("ready.json")),
        encoding="utf-8",
    )

    older = time.time() - 200
    report_time = time.time() - 100
    for name in ("discovery.md", "spec.md", "technical-design.md"):
        os.utime(feature / name, (older, older))
    os.utime(feature / "readiness-review.json", (report_time, report_time))
    feature.joinpath("domain-rules.md").write_text("# Domain Rules\n", encoding="utf-8")

    stale_reason = readiness_report_stale_reason(feature)

    assert stale_reason is not None
    assert "domain-rules.md" in stale_reason


def test_plugin_result_contract_stale_review_detects_source_set_change_without_newer_mtime(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    _write_review_sources(feature)
    feature.joinpath("readiness-review.json").write_text(
        json.dumps(_load_fixture("ready.json")),
        encoding="utf-8",
    )

    older = time.time() - 200
    report_time = time.time() - 100
    feature.joinpath("domain-rules.md").write_text("# Domain Rules\n", encoding="utf-8")
    for name in ("discovery.md", "spec.md", "technical-design.md", "domain-rules.md"):
        os.utime(feature / name, (older, older))
    os.utime(feature / "readiness-review.json", (report_time, report_time))

    stale_reason = readiness_report_stale_reason(feature)

    assert stale_reason is not None
    assert "source artifact set changed" in stale_reason
    assert "domain-rules.md" in stale_reason


def test_plugin_result_contract_stale_review_detects_removed_reviewed_source(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    _write_review_sources(feature)
    payload = _load_fixture("ready.json")
    payload["input"]["artifacts"].append({"path": "domain-rules.md", "characters": 50})
    payload["input"]["artifact_count"] = len(payload["input"]["artifacts"])
    feature.joinpath("readiness-review.json").write_text(json.dumps(payload), encoding="utf-8")

    stale_reason = readiness_report_stale_reason(feature)

    assert stale_reason is not None
    assert "removed source file(s): domain-rules.md" in stale_reason


def test_plugin_result_contract_validation_failure_has_no_fresh_readiness_report(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    feature.joinpath("discovery.md").write_text("# Discovery\n\n- Goal: invalid spec check.\n", encoding="utf-8")
    feature.joinpath("spec.md").write_text("# Spec\n\nMissing required sections.\n", encoding="utf-8")

    result = run_pipeline(feature)

    assert not result.ok
    assert result.details["failed_before_readiness_review"] is True
    assert not feature.joinpath("readiness-review.json").exists()


def test_plugin_run_state_derives_ready_with_current_handoff(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    _write_review_sources(feature)
    feature.joinpath("readiness-review.json").write_text(json.dumps(_load_fixture("ready.json")), encoding="utf-8")
    feature.joinpath("readiness-review.md").write_text("# Review\n", encoding="utf-8")
    feature.joinpath("implementation-output.md").write_text("# Handoff\n", encoding="utf-8")

    state = derive_plugin_run_state(
        feature,
        command="specguard run feature --no-llm --no-follow-up",
        returncode=0,
    )

    assert state.state == "ready"
    assert state.command == "specguard run feature --no-llm --no-follow-up"
    assert any(path.endswith("readiness-review.json") for path in state.relevant_files)
    assert any(path.endswith("readiness-review.md") for path in state.relevant_files)
    assert any(path.endswith("implementation-output.md") for path in state.relevant_files)
    assert "implementation-output.md" in state.next_action


def test_plugin_run_state_omits_handoff_for_not_ready(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    _write_review_sources(feature)
    feature.joinpath("readiness-review.json").write_text(json.dumps(_load_fixture("not-ready.json")), encoding="utf-8")
    feature.joinpath("readiness-review.md").write_text("# Review\n", encoding="utf-8")
    feature.joinpath("implementation-output.md").write_text("# Old handoff\n", encoding="utf-8")

    state = derive_plugin_run_state(feature, command="specguard run feature --no-llm --no-follow-up", returncode=1)

    assert state.state == "not_ready"
    assert any(path.endswith("readiness-review.json") for path in state.relevant_files)
    assert any(path.endswith("readiness-review.md") for path in state.relevant_files)
    assert not any(path.endswith("implementation-output.md") for path in state.relevant_files)


def test_plugin_run_state_reports_stale_review_without_relevant_files(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    _write_review_sources(feature)
    feature.joinpath("readiness-review.json").write_text(json.dumps(_load_fixture("ready.json")), encoding="utf-8")
    feature.joinpath("readiness-review.md").write_text("# Review\n", encoding="utf-8")
    feature.joinpath("domain-rules.md").write_text("# Domain Rules\n", encoding="utf-8")

    state = derive_plugin_run_state(feature, command="specguard run feature --no-llm --no-follow-up", returncode=0)

    assert state.state == "stale_review"
    assert state.relevant_files == ()
    assert any(path.endswith("readiness-review.json") for path in state.known_files)
    assert state.stale_reason is not None
    assert "domain-rules.md" in state.stale_reason


def test_plugin_run_state_validation_failure_does_not_reuse_old_ready_report(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    _write_review_sources(feature)
    feature.joinpath("readiness-review.json").write_text(json.dumps(_load_fixture("ready.json")), encoding="utf-8")
    older = time.time() - 200
    started_at = time.time() - 100
    for name in ("discovery.md", "spec.md", "technical-design.md", "readiness-review.json"):
        os.utime(feature / name, (older, older))

    state = derive_plugin_run_state(
        feature,
        command="specguard run feature --no-llm --no-follow-up",
        started_at=started_at,
        returncode=1,
    )

    assert state.state == "validation_failed_before_review"
    assert state.relevant_files == ()
    assert "older readiness report was not reused" in state.next_action


@pytest.mark.parametrize(
    ("kwargs", "expected_state"),
    (
        ({"cli_available": False}, "missing_cli"),
        ({"spec_package_exists": False}, "missing_spec_package"),
        ({"provider_required": True, "provider_available": False}, "missing_provider_for_llm"),
        ({"timed_out": True}, "timeout"),
    ),
)
def test_plugin_run_state_reports_preflight_and_timeout_categories(
    tmp_path: Path,
    kwargs: dict[str, object],
    expected_state: str,
) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    if expected_state != "missing_spec_package":
        feature.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")

    state = derive_plugin_run_state(
        feature,
        command="specguard run feature --no-llm --no-follow-up",
        **kwargs,
    )

    assert state.state == expected_state
    assert state.command == "specguard run feature --no-llm --no-follow-up"
    assert state.next_action


def test_plugin_run_state_reports_cli_execution_failed_after_fresh_ready_review(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    _write_review_sources(feature)
    feature.joinpath("readiness-review.json").write_text(json.dumps(_load_fixture("ready.json")), encoding="utf-8")
    feature.joinpath("readiness-review.md").write_text("# Review\n", encoding="utf-8")
    started_at = time.time() - 100
    fresh = time.time()
    os.utime(feature / "readiness-review.json", (fresh, fresh))

    state = derive_plugin_run_state(
        feature,
        command="specguard run feature --no-llm --no-follow-up",
        started_at=started_at,
        returncode=2,
    )

    assert state.state == "cli_execution_failed"
    assert any(path.endswith("readiness-review.json") for path in state.known_files)
    assert state.relevant_files == ()
    assert "rerun SpecGuard" in state.next_action
