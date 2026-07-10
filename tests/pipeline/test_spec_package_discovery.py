from __future__ import annotations

from pathlib import Path

from tools.spec_packages import discover_spec_packages, resolve_spec_packages, spec_package_discovery_preview_payload


def write_package(base: Path, name: str = "billing-export") -> Path:
    package = base / "specs" / name
    package.mkdir(parents=True)
    package.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
    return package


def test_discovers_root_specs_package(tmp_path: Path) -> None:
    package = write_package(tmp_path)

    assert discover_spec_packages(tmp_path) == [package]


def test_discovers_nested_specs_package(tmp_path: Path) -> None:
    package = write_package(tmp_path / "services" / "billing")

    assert discover_spec_packages(tmp_path) == [package]


def test_multiple_specs_packages_require_explicit_resolution(tmp_path: Path) -> None:
    root_package = write_package(tmp_path, "root-feature")
    nested_package = write_package(tmp_path / "services" / "billing", "nested-feature")

    resolution = resolve_spec_packages(tmp_path)

    assert resolution.ambiguous
    assert resolution.packages == (root_package, nested_package)


def test_discovery_preview_payload_marks_single_candidate(tmp_path: Path) -> None:
    write_package(tmp_path)

    payload = spec_package_discovery_preview_payload(tmp_path, display_root=tmp_path)

    assert payload == {
        "schema_version": "specguard.discovery_preview.v1",
        "requested_path": ".",
        "status": "resolved",
        "reason": "single_candidate",
        "path_exists": True,
        "candidate_count": 1,
        "selection_required": False,
        "review_allowed": True,
        "candidates": [
            {
                "index": 1,
                "path": "specs/billing-export",
                "spec_path": "specs/billing-export/spec.md",
                "review_command": "specguard run specs/billing-export --no-llm --no-follow-up",
                "review_args": ["specguard", "run", "specs/billing-export", "--no-llm", "--no-follow-up"],
            }
        ],
        "next_action": {
            "type": "run_review",
            "candidate_index": 1,
            "command": "specguard run specs/billing-export --no-llm --no-follow-up",
            "args": ["specguard", "run", "specs/billing-export", "--no-llm", "--no-follow-up"],
        },
    }


def test_discovery_preview_quotes_review_command_paths_with_spaces(tmp_path: Path) -> None:
    write_package(tmp_path, "billing export")

    payload = spec_package_discovery_preview_payload(tmp_path, display_root=tmp_path)

    assert payload["candidates"] == [
        {
            "index": 1,
            "path": "specs/billing export",
            "spec_path": "specs/billing export/spec.md",
            "review_command": 'specguard run "specs/billing export" --no-llm --no-follow-up',
            "review_args": ["specguard", "run", "specs/billing export", "--no-llm", "--no-follow-up"],
        }
    ]
    assert payload["next_action"] == {
        "type": "run_review",
        "candidate_index": 1,
        "command": 'specguard run "specs/billing export" --no-llm --no-follow-up',
        "args": ["specguard", "run", "specs/billing export", "--no-llm", "--no-follow-up"],
    }


def test_discovery_preview_payload_marks_ambiguous_candidates(tmp_path: Path) -> None:
    write_package(tmp_path, "root-feature")
    write_package(tmp_path / "services" / "billing", "nested-feature")

    payload = spec_package_discovery_preview_payload(tmp_path, display_root=tmp_path)

    assert payload["status"] == "ambiguous"
    assert payload["reason"] == "multiple_candidates"
    assert payload["candidate_count"] == 2
    assert payload["selection_required"] is True
    assert payload["review_allowed"] is False
    assert payload["candidates"] == [
        {
            "index": 1,
            "path": "specs/root-feature",
            "spec_path": "specs/root-feature/spec.md",
            "review_command": "specguard run specs/root-feature --no-llm --no-follow-up",
            "review_args": ["specguard", "run", "specs/root-feature", "--no-llm", "--no-follow-up"],
        },
        {
            "index": 2,
            "path": "services/billing/specs/nested-feature",
            "spec_path": "services/billing/specs/nested-feature/spec.md",
            "review_command": "specguard run services/billing/specs/nested-feature --no-llm --no-follow-up",
            "review_args": [
                "specguard",
                "run",
                "services/billing/specs/nested-feature",
                "--no-llm",
                "--no-follow-up",
            ],
        },
    ]
    assert payload["next_action"] == {
        "type": "choose_candidate",
        "command_template": "specguard run <selected-path> --no-llm --no-follow-up",
        "bulk_review_default": False,
    }


def test_discovery_preview_payload_marks_missing_package_states(tmp_path: Path) -> None:
    empty_payload = spec_package_discovery_preview_payload(tmp_path, display_root=tmp_path)
    missing_payload = spec_package_discovery_preview_payload(tmp_path / "missing", display_root=tmp_path)

    assert empty_payload["status"] == "missing_spec_package"
    assert empty_payload["reason"] == "no_candidates"
    assert empty_payload["path_exists"] is True
    assert empty_payload["selection_required"] is False
    assert empty_payload["review_allowed"] is False
    assert empty_payload["candidates"] == []
    assert empty_payload["next_action"] == {
        "type": "create_or_select_package",
        "command_template": "specguard init <feature-name>",
        "supported_package_paths": [
            "specs/<feature>/spec.md",
            "backend/specs/<feature>/spec.md",
        ],
        "manual_shape": {
            "required_file": "spec.md",
            "root_package": "specs/<feature>/",
            "nested_package": "backend/specs/<feature>/",
        },
        "next_commands": [
            "specguard init <feature-name>",
            "specguard discover <path>",
            "specguard run specs/<feature> --no-llm --no-follow-up",
        ],
        "review_status": "not_reviewed",
    }
    assert missing_payload["status"] == "missing_spec_package"
    assert missing_payload["reason"] == "path_not_found"
    assert missing_payload["path_exists"] is False
    assert missing_payload["selection_required"] is False
    assert missing_payload["review_allowed"] is False
    assert missing_payload["candidates"] == []


def test_discovery_excludes_hidden_dependency_build_and_generated_dirs(tmp_path: Path) -> None:
    visible = write_package(tmp_path / "services" / "billing", "visible")
    for excluded in (".hidden", "node_modules", "build", "generated"):
        write_package(tmp_path / excluded, "ignored")

    assert discover_spec_packages(tmp_path) == [visible]

    payload = spec_package_discovery_preview_payload(tmp_path, display_root=tmp_path)
    assert payload["candidates"] == [
        {
            "index": 1,
            "path": "services/billing/specs/visible",
            "spec_path": "services/billing/specs/visible/spec.md",
            "review_command": "specguard run services/billing/specs/visible --no-llm --no-follow-up",
            "review_args": ["specguard", "run", "services/billing/specs/visible", "--no-llm", "--no-follow-up"],
        }
    ]
