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
    assert payload["candidates"][0]["path"].endswith("/specs/billing-export")
    assert payload["candidates"][0]["spec_path"].endswith("/specs/billing-export/spec.md")
    assert not package.joinpath("readiness-review.json").exists()
    assert not package.joinpath("readiness-review.md").exists()
    assert not package.joinpath("implementation-output.md").exists()
    assert not package.joinpath("technical-design.md").exists()
