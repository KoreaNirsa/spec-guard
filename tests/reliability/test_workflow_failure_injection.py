from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import threading
import time
from pathlib import Path

import pytest

from tools.post_run import (
    derive_plugin_run_state,
    plugin_run_state_path,
    readiness_report_stale_reason,
)
from tools.readiness_engine import review_artifact_paths
from tools.runner import run_pipeline
import tools.readiness_engine as readiness_engine
import tools.atomic as atomic
import tools.runner as runner


ROOT = Path(__file__).resolve().parents[2]
READY_EXAMPLE = ROOT / "examples" / "example"
FIXTURES = ROOT / "tests" / "fixtures" / "plugin-result-contract"


def _feature(tmp_path: Path, name: str = "failure-scenarios") -> Path:
    target = tmp_path / "specs" / name
    shutil.copytree(READY_EXAMPLE, target)
    return target


def _authored_snapshot(feature: Path) -> dict[str, bytes]:
    return {
        relative.as_posix(): (feature / relative).read_bytes()
        for relative in review_artifact_paths(feature)
    }


def _write_report(feature: Path, fixture_name: str) -> None:
    payload = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
    (feature / "readiness-review.json").write_text(json.dumps(payload), encoding="utf-8")
    (feature / "readiness-review.md").write_text("# Previous review\n", encoding="utf-8")


def test_atomic_generated_file_replacement_preserves_previous_target_on_failure(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "readiness-review.json"
    target.write_text('{"status":"old"}\n', encoding="utf-8")

    def fail_replace(*args, **kwargs):
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(atomic.os, "replace", fail_replace)

    with pytest.raises(OSError, match="atomic replace"):
        atomic.atomic_write_text(target, '{"status":"new"}\n')

    assert target.read_text(encoding="utf-8") == '{"status":"old"}\n'
    assert not list(tmp_path.glob(".readiness-review.json.*.tmp"))


def test_authored_edit_marks_previous_report_and_handoff_stale(tmp_path: Path) -> None:
    feature = _feature(tmp_path)
    assert run_pipeline(feature).ok

    feature.joinpath("spec.md").write_text(
        feature.joinpath("spec.md").read_text(encoding="utf-8") + "\n- Added after the previous review.\n",
        encoding="utf-8",
    )

    state = derive_plugin_run_state(
        feature,
        command="specguard run specs/failure-scenarios --no-llm --no-follow-up",
        returncode=0,
    )

    assert state.state == "stale_review"
    assert state.stale_reason is not None
    assert "spec.md" in state.stale_reason
    assert state.relevant_files == ()
    assert not any(path.endswith("implementation-output.md") for path in state.known_files)


def test_corrupt_readiness_report_is_not_current_or_actionable(tmp_path: Path) -> None:
    feature = _feature(tmp_path)
    assert run_pipeline(feature).ok
    (feature / "readiness-review.json").write_text('{"readiness":', encoding="utf-8")

    state = derive_plugin_run_state(
        feature,
        command="specguard run specs/failure-scenarios --no-llm --no-follow-up",
        returncode=1,
    )

    assert state.state == "cli_execution_failed"
    assert state.relevant_files == ()
    assert any(path.endswith("readiness-review.json") for path in state.known_files)
    assert not any(path.endswith("implementation-output.md") for path in state.relevant_files)
    assert "Rerun SpecGuard" in state.next_action


def test_ready_report_without_handoff_requires_full_pipeline_rerun(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    for name in ("discovery.md", "spec.md", "technical-design.md"):
        (feature / name).write_text(f"# {name}\n", encoding="utf-8")
    _write_report(feature, "ready.json")

    state = derive_plugin_run_state(
        feature,
        command="specguard run feature --no-llm --no-follow-up",
        returncode=0,
    )

    assert state.state == "ready"
    assert state.relevant_files == (
        (feature / "readiness-review.json").as_posix(),
        (feature / "readiness-review.md").as_posix(),
    )
    assert "Rerun the full SpecGuard pipeline" in state.next_action
    assert "implementation-output.md" not in "\n".join(state.relevant_files)


def test_report_write_failure_records_failed_stage_without_authored_changes(tmp_path: Path, monkeypatch) -> None:
    feature = _feature(tmp_path)
    authored_before = _authored_snapshot(feature)

    def fail_report_write(path: Path, content: str, **kwargs) -> None:
        if path.name == "readiness-review.json":
            raise OSError("simulated report write failure")
        return original_atomic_write(path, content, **kwargs)

    original_atomic_write = readiness_engine.atomic_write_text
    monkeypatch.setattr(readiness_engine, "atomic_write_text", fail_report_write)

    result = run_pipeline(feature)
    state_payload = json.loads(plugin_run_state_path(feature).read_text(encoding="utf-8"))

    assert not result.ok
    assert result.details["failure-scenarios.failed_stage"] == "readiness_review"
    assert state_payload["state"] == "pipeline_failed"
    assert state_payload["failed_stage"] == "readiness_review"
    assert state_payload["relevant_files"] == [plugin_run_state_path(feature).as_posix()]
    assert _authored_snapshot(feature) == authored_before
    assert (feature / "implementation-output.md").exists()
    assert not any(path.endswith("implementation-output.md") for path in state_payload["relevant_files"])


def test_interruption_after_readiness_suppresses_previous_handoff(tmp_path: Path, monkeypatch) -> None:
    feature = _feature(tmp_path)
    assert run_pipeline(feature).ok
    authored_before = _authored_snapshot(feature)

    def fail_tests(*args, **kwargs):
        raise RuntimeError("simulated interruption between readiness and handoff")

    monkeypatch.setattr(runner, "generate_tests", fail_tests)
    result = run_pipeline(feature)
    state_payload = json.loads(plugin_run_state_path(feature).read_text(encoding="utf-8"))
    state = derive_plugin_run_state(
        feature,
        command="specguard run specs/failure-scenarios --no-llm --no-follow-up",
        returncode=1,
    )

    assert not result.ok
    assert result.details["failure-scenarios.failed_stage"] == "tests"
    assert state_payload["failed_stage"] == "tests"
    assert state.state == "pipeline_failed"
    assert state.relevant_files == (plugin_run_state_path(feature).as_posix(),)
    assert "implementation-output.md" not in "\n".join(state.relevant_files)
    assert _authored_snapshot(feature) == authored_before


def test_provider_timeout_and_retry_exhaustion_is_redacted_and_recoverable(tmp_path: Path, monkeypatch) -> None:
    feature = _feature(tmp_path)

    def fail_review(*args, **kwargs):
        raise TimeoutError("provider timeout after retry exhaustion; diagnostic=private-marker")

    monkeypatch.setattr(runner, "run_readiness_review", fail_review)
    result = run_pipeline(feature)
    state_payload = json.loads(plugin_run_state_path(feature).read_text(encoding="utf-8"))

    rendered = "\n".join(result.messages + result.next_steps + state_payload["messages"])
    assert not result.ok
    assert state_payload["failure_category"] == "timeout"
    assert state_payload["failed_stage"] == "readiness_review"
    assert "private-marker" not in rendered
    assert "timed out" in rendered
    assert "rerun" in state_payload["next_action"].lower()


def test_concurrent_runs_are_serialized_and_do_not_mix_artifacts(tmp_path: Path, monkeypatch) -> None:
    feature = _feature(tmp_path)
    original_review = runner.run_readiness_review
    active = 0
    maximum_active = 0
    counters_lock = threading.Lock()

    def tracked_review(*args, **kwargs):
        nonlocal active, maximum_active
        with counters_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            time.sleep(0.05)
            return original_review(*args, **kwargs)
        finally:
            with counters_lock:
                active -= 1

    monkeypatch.setattr(runner, "run_readiness_review", tracked_review)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run_pipeline(feature, force=True), range(2)))

    assert maximum_active == 1
    assert all(result.ok for result in results)
    payload = json.loads((feature / "readiness-review.json").read_text(encoding="utf-8"))
    assert payload["input"]["artifact_count"] == len(payload["input"]["artifacts"])
    assert payload["readiness"]["status"] in {"ready", "ready_with_warnings"}
    assert not plugin_run_state_path(feature).exists()


def test_legacy_report_without_additive_metadata_remains_safe(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    feature.mkdir()
    for name in ("discovery.md", "spec.md", "technical-design.md"):
        (feature / name).write_text(f"# {name}\n", encoding="utf-8")
    _write_report(feature, "ready.json")
    payload = json.loads((feature / "readiness-review.json").read_text(encoding="utf-8"))
    payload.pop("review_input", None)
    payload.pop("cache", None)
    (feature / "readiness-review.json").write_text(json.dumps(payload), encoding="utf-8")
    (feature / "implementation-output.md").write_text("# Handoff\n", encoding="utf-8")

    state = derive_plugin_run_state(
        feature,
        command="specguard run feature --no-llm --no-follow-up",
        returncode=0,
    )

    assert readiness_report_stale_reason(feature) is None
    assert state.state == "ready"
    assert (feature / "implementation-output.md").as_posix() in state.relevant_files
