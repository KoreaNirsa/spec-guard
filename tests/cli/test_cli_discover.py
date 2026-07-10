from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import cli.specguard as specguard_cli


def write_package(base: Path, name: str = "billing-export") -> Path:
    package = base / "specs" / name
    package.mkdir(parents=True)
    package.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
    return package


def test_discover_cli_outputs_json_without_writing_artifacts(tmp_path: Path, capsys) -> None:
    package = write_package(tmp_path)

    exit_code = specguard_cli.discover(Namespace(path=str(tmp_path)))

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["schema_version"] == "specguard.discovery_preview.v1"
    assert payload["status"] == "resolved"
    assert payload["candidate_count"] == 1
    assert payload["selection_required"] is False
    assert payload["review_allowed"] is True
    assert payload["candidates"][0]["path"].endswith("/specs/billing-export")
    assert payload["candidates"][0]["spec_path"].endswith("/specs/billing-export/spec.md")
    assert payload["candidates"][0]["index"] == 1
    assert payload["candidates"][0]["review_command"].endswith("/specs/billing-export --no-llm --no-follow-up")
    assert payload["next_action"]["type"] == "run_review"
    assert not package.joinpath("readiness-review.json").exists()
    assert not package.joinpath("readiness-review.md").exists()
    assert not package.joinpath("implementation-output.md").exists()
    assert not package.joinpath("technical-design.md").exists()


def test_discover_cli_reports_ambiguous_candidates_for_selection(tmp_path: Path, capsys) -> None:
    write_package(tmp_path, "root-feature")
    write_package(tmp_path / "services" / "billing", "nested-feature")

    exit_code = specguard_cli.discover(Namespace(path=str(tmp_path)))

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ambiguous"
    assert payload["selection_required"] is True
    assert payload["review_allowed"] is False
    assert payload["next_action"] == {
        "type": "choose_candidate",
        "command_template": "specguard run <selected-path> --no-llm --no-follow-up",
        "bulk_review_default": False,
    }
    assert [candidate["index"] for candidate in payload["candidates"]] == [1, 2]
    assert payload["candidates"][0]["path"].endswith("/specs/root-feature")
    assert payload["candidates"][1]["path"].endswith("/services/billing/specs/nested-feature")
    assert payload["candidates"][0]["review_command"].endswith("/specs/root-feature --no-llm --no-follow-up")
    assert payload["candidates"][1]["review_command"].endswith(
        "/services/billing/specs/nested-feature --no-llm --no-follow-up"
    )


def test_discover_cli_reports_missing_package_guidance(tmp_path: Path, capsys) -> None:
    exit_code = specguard_cli.discover(Namespace(path=str(tmp_path)))

    payload = json.loads(capsys.readouterr().out)
    next_action = payload["next_action"]

    assert exit_code == 0
    assert payload["status"] == "missing_spec_package"
    assert payload["review_allowed"] is False
    assert next_action["type"] == "create_or_select_package"
    assert next_action["supported_package_paths"] == [
        "specs/<feature>/spec.md",
        "backend/specs/<feature>/spec.md",
    ]
    assert next_action["manual_shape"]["required_file"] == "spec.md"
    assert next_action["review_status"] == "not_reviewed"


def test_discover_cli_offers_draft_source_without_writing_files(tmp_path: Path, capsys) -> None:
    source = tmp_path / "docs" / "requirements.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Requirements\n", encoding="utf-8")
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    exit_code = specguard_cli.discover(Namespace(path=str(tmp_path)))

    payload = json.loads(capsys.readouterr().out)
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert exit_code == 0
    assert payload["draft_sources"][0]["path"].endswith("/docs/requirements.md")
    assert payload["next_action"]["type"] == "offer_draft_package"
    assert payload["next_action"]["requires_user_approval"] is True
    assert before == after
