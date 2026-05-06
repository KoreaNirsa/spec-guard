from __future__ import annotations

import json
import os
import time
from pathlib import Path

from tools.pr_readiness_gate import changed_feature_dirs, run_readiness_gate, validate_feature_readiness


def write_ready_feature(base: Path, name: str = "billing-export") -> Path:
    feature = base / "specs" / name
    feature.mkdir(parents=True)
    feature.joinpath("discovery.md").write_text(
        "\n".join([
            "# Discovery",
            "",
            "## Foundation",
            "",
            "- Goal: Export billing records safely.",
            "",
            "## Mechanisms",
            "",
            "- Components: API, export service, contract.",
            "",
            "## Stress Test",
            "",
            "- Failure: Unauthorized access is rejected.",
            "",
            "## Synthesis",
            "",
            "- Decision: Proceed after validation passes.",
            "",
        ]),
        encoding="utf-8",
    )
    feature.joinpath("spec.md").write_text(
        "\n".join([
            "# Spec",
            "",
            "## Requirements",
            "",
            "- The system must export owned records.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Authorized exports succeed.",
            "",
            "## Error Cases",
            "",
            "- Unauthorized access",
            "",
        ]),
        encoding="utf-8",
    )
    feature.joinpath("technical-design.md").write_text(
        "\n".join([
            "# Technical Design",
            "",
            "## Architecture",
            "",
            "API layer calls an export service.",
            "",
            "## Data Flow",
            "",
            "1. Request arrives.",
            "2. Service validates authorization.",
            "3. Response is returned.",
            "",
            "## State",
            "",
            "- Initial state: requested.",
            "- Terminal state: completed or rejected.",
            "",
            "## Failure Handling",
            "",
            "- Unauthorized access returns 403.",
            "",
        ]),
        encoding="utf-8",
    )
    write_readiness_report(feature, blocked=False, implementation_ready=True)
    return feature


def write_readiness_report(feature: Path, *, blocked: bool, implementation_ready: bool) -> None:
    feature.joinpath("readiness-review.json").write_text(
        json.dumps({
            "blocked": blocked,
            "readiness": {"implementation_ready": implementation_ready},
            "summary": {"critical": 0, "major": 0, "minor": 1},
            "issues": [],
        }),
        encoding="utf-8",
    )


def test_changed_feature_dirs_discovers_changed_spec_packages(tmp_path: Path) -> None:
    feature = write_ready_feature(tmp_path)

    feature_dirs = changed_feature_dirs(
        [
            "README.md",
            "specs/billing-export/spec.md",
            "specs/billing-export/checklists/spec-readiness.md",
        ],
        tmp_path,
    )

    assert feature_dirs == [feature]


def test_readiness_gate_passes_when_no_spec_package_changed(tmp_path: Path) -> None:
    ok, results = run_readiness_gate(["README.md", "docs/workflow.md"], tmp_path)

    assert ok
    assert results == []


def test_readiness_gate_passes_when_changed_package_is_ready_and_report_changed(tmp_path: Path) -> None:
    write_ready_feature(tmp_path)

    ok, results = run_readiness_gate(
        [
            "specs/billing-export/spec.md",
            "specs/billing-export/readiness-review.json",
        ],
        tmp_path,
    )

    assert ok
    assert len(results) == 1
    assert results[0].ok


def test_readiness_gate_fails_when_changed_source_does_not_update_report(tmp_path: Path) -> None:
    write_ready_feature(tmp_path)

    ok, results = run_readiness_gate(["specs/billing-export/spec.md"], tmp_path)

    assert not ok
    assert len(results) == 1
    assert any("without updating readiness-review.json" in message for message in results[0].messages)


def test_readiness_gate_fails_when_changed_package_is_not_ready(tmp_path: Path) -> None:
    feature = write_ready_feature(tmp_path)
    write_readiness_report(feature, blocked=True, implementation_ready=False)

    result = validate_feature_readiness(feature)

    assert not result.ok
    assert any("not READY" in message for message in result.messages)


def test_readiness_gate_fails_when_report_is_stale(tmp_path: Path) -> None:
    feature = write_ready_feature(tmp_path)
    report_path = feature / "readiness-review.json"
    spec_path = feature / "spec.md"
    old_time = time.time() - 20
    newer_time = time.time() - 10
    os.utime(report_path, (old_time, old_time))
    os.utime(spec_path, (newer_time, newer_time))

    result = validate_feature_readiness(feature)

    assert not result.ok
    assert any("stale" in message.lower() for message in result.messages)


def test_readiness_gate_fails_when_required_inputs_are_missing(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "missing-inputs"
    feature.mkdir(parents=True)
    feature.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")

    result = validate_feature_readiness(feature)

    assert not result.ok
    assert any("discovery.md" in message for message in result.messages)
    assert any("technical-design.md" in message for message in result.messages)
    assert any("readiness-review.json" in message for message in result.messages)
