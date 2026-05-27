from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.grill_loop import (
    ALLOWED_RESOLUTIONS,
    build_grill_payload,
    build_grill_patch_plan,
    apply_grill_patch_plan,
    load_grill_payload,
    record_grill_decision,
    write_grill_rerun_comparison,
)
from tools.readiness_engine import run_readiness_review


ROOT = Path(__file__).resolve().parents[2]
PACKAGED_EXAMPLE = ROOT / "tools" / "resources" / "example"


def _copy_blocked_example(tmp_path: Path) -> Path:
    feature = tmp_path / "specs" / "todo-privacy"
    shutil.copytree(PACKAGED_EXAMPLE, feature)
    return feature


def _run_cli(
    *args: str,
    input_text: str | None = None,
    expected_returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, "-m", "cli.specguard", *args],
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == expected_returncode, completed.stdout + completed.stderr
    return completed


def test_grill_findings_contract_has_stable_ids_and_questions(tmp_path: Path) -> None:
    feature = _copy_blocked_example(tmp_path)

    result = run_readiness_review(feature)

    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    report = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    rebuilt = build_grill_payload(feature, report)

    assert not result.ok
    assert payload["schema_version"] == "0.1"
    assert payload["source_report"].endswith("readiness-review.json")
    assert payload["decision_record_path"].endswith("decisions/specguard-decisions.jsonl")
    assert payload["readiness_status"] == "not_ready"
    assert payload["readiness_summary"]["problem"].startswith("Blocking readiness issue:")
    assert payload["resolution_prompts"]["update-spec"]["example_prompt"].startswith("update-spec ->")
    assert payload["question_order"]
    assert payload["question_order"] == [finding["id"] for finding in payload["findings"]]
    assert payload["question_order"] == [finding["id"] for finding in rebuilt["findings"]]

    first = payload["findings"][0]
    assert first["id"].startswith("SG-")
    assert first["severity"] == "Critical"
    assert first["evidence"]
    assert first["source_location"]["review_path"].startswith("readiness-review.json#/issues/")
    assert "spec-contract gap" in first["question"]
    assert "authorization" in first["question"]
    assert "ownership" in first["question"]
    assert set(first["allowed_resolution"]) == set(ALLOWED_RESOLUTIONS)


def test_grill_decision_records_patch_only_user_confirmed_update_spec(tmp_path: Path) -> None:
    feature = _copy_blocked_example(tmp_path)
    run_readiness_review(feature)
    finding = load_grill_payload(feature)["findings"][0]

    record_grill_decision(
        feature,
        review_id=finding["id"],
        decision="Todo reads and writes must be scoped to the authenticated owner\nbefore data is returned or mutated.",
        resolution="update-spec",
        target="spec.md#Requirements",
    )
    record_grill_decision(
        feature,
        review_id=finding["id"],
        decision="Keep this question visible for a later product decision.",
        resolution="defer",
    )
    record_grill_decision(
        feature,
        review_id=finding["id"],
        decision="This generated suggestion was not confirmed by the user.",
        source="codex-suggestion",
        resolution="update-spec",
        target="spec.md#Requirements",
    )

    plan = build_grill_patch_plan(feature)
    result = apply_grill_patch_plan(feature, plan)
    spec = feature.joinpath("spec.md").read_text(encoding="utf-8")

    assert feature.joinpath("decisions", "specguard-decisions.jsonl").exists()
    assert feature.joinpath("decisions", "specguard-patch-plan.json").exists()
    assert [entry["status"] for entry in plan["entries"]] == ["apply", "skipped", "skipped"]
    assert len(result.applied) == 1
    assert len(result.skipped) == 2
    assert f"SpecGuard decision {finding['id']}" in spec
    assert "Todo reads and writes must be scoped to the authenticated owner before data is returned or mutated." in spec
    assert "authenticated owner\nbefore data" not in spec
    assert "Keep this question visible" not in spec
    assert "generated suggestion was not confirmed" not in spec


def test_grill_rerun_comparison_tracks_deferred_and_unresolved_findings(tmp_path: Path) -> None:
    feature = _copy_blocked_example(tmp_path)
    run_readiness_review(feature)
    previous = load_grill_payload(feature)
    deferred_id = previous["findings"][0]["id"]

    record_grill_decision(
        feature,
        review_id=deferred_id,
        decision="User deferred the ownership contract decision.",
        resolution="defer",
    )
    run_readiness_review(feature)
    current = load_grill_payload(feature)
    comparison = write_grill_rerun_comparison(feature, previous, current)

    assert feature.joinpath("decisions", "specguard-rerun-comparison.json").exists()
    assert deferred_id in comparison["deferred"]
    assert deferred_id not in comparison["unresolved"]
    assert comparison["current_readiness_status"] == "not_ready"
    assert comparison["previous_finding_count"] >= 1
    assert comparison["current_finding_count"] >= 1


def test_grill_cli_e2e_records_patches_and_verifies_blocked_package(tmp_path: Path) -> None:
    feature = _copy_blocked_example(tmp_path)

    _run_cli("run", str(feature), "--no-llm", "--no-follow-up", expected_returncode=1)
    _run_cli("grill", str(feature), "findings")
    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    finding = payload["findings"][0]

    ask_input = (
        "update-spec\n"
        "Todo reads and writes must be scoped to the authenticated owner before data is returned or mutated.\n"
        "spec.md#Requirements\n"
    )
    ask = _run_cli("grill", str(feature), "ask", "--limit", "1", input_text=ask_input)
    _run_cli("grill", str(feature), "plan")
    _run_cli("grill", str(feature), "apply")
    verify = _run_cli("grill", str(feature), "verify", expected_returncode=1)

    spec = feature.joinpath("spec.md").read_text(encoding="utf-8")
    comparison = json.loads(feature.joinpath("decisions", "specguard-rerun-comparison.json").read_text(encoding="utf-8"))
    assert f"Recorded decision: {finding['id']}" in ask.stdout
    assert "Problem: Blocking readiness issue:" in ask.stdout
    assert "Response examples:" in ask.stdout
    assert "update-spec -> Server must enforce owner-scoped todo reads and writes." in ask.stdout
    assert f"SpecGuard decision {finding['id']}" in spec
    assert comparison["current_readiness_status"] == "not_ready"
    assert comparison["unresolved"]
    assert "Grill Me Verification" in verify.stdout


def test_grill_findings_ignore_artifact_paths_outside_feature_dir(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "todo-privacy"
    feature.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("outside-only evidence", encoding="utf-8")
    report = {
        "readiness": {"status": "not_ready"},
        "input": {"artifacts": [{"path": "../outside.md"}]},
        "issues": [
            {
                "severity": "Critical",
                "title": "Unsafe artifact path",
                "evidence": "outside-only evidence",
                "fix": "Stay inside the feature directory.",
            }
        ],
    }

    payload = build_grill_payload(feature, report)

    assert payload["findings"][0]["source_location"] == {
        "path": "readiness-review.json",
        "line": None,
        "review_path": "readiness-review.json#/issues/0",
    }


def test_readiness_review_keeps_report_when_grill_output_emission_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = _copy_blocked_example(tmp_path)

    def fail_grill_output(*_args: object, **_kwargs: object) -> None:
        raise OSError("grill output failed")

    monkeypatch.setattr("tools.readiness_engine.write_grill_outputs", fail_grill_output)
    result = run_readiness_review(feature)

    assert feature.joinpath("readiness-review.json").exists()
    assert any("Skipped Grill companion artifacts" in message for message in result.messages)
