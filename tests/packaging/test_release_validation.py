from __future__ import annotations

from pathlib import Path

import pytest

from tools.release_validation import (
    project_version,
    validate_plugin_manifest,
    validate_release_tag,
    version_from_release_tag,
)


ROOT = Path(__file__).resolve().parents[2]


def test_release_tag_matches_project_version() -> None:
    version = project_version(ROOT / "pyproject.toml")

    assert version_from_release_tag(f"v{version}") == version
    assert version_from_release_tag(f"refs/tags/v{version}") == version
    validate_release_tag(f"v{version}", version)


def test_release_tag_mismatch_blocks_publish() -> None:
    with pytest.raises(ValueError, match="does not match package version"):
        validate_release_tag("v9.9.9", project_version(ROOT / "pyproject.toml"))


@pytest.mark.parametrize("tag", ["release-0.4.3", "v", "refs/heads/main", ""])
def test_non_version_release_tag_is_rejected(tag: str) -> None:
    with pytest.raises(ValueError, match="must be a version tag"):
        version_from_release_tag(tag)


def test_plugin_manifest_and_skill_paths_are_release_ready() -> None:
    manifest = validate_plugin_manifest(ROOT / "plugins/specguard/.codex-plugin/plugin.json")

    assert manifest["name"] == "specguard"
    assert manifest["skills"] == "./skills/"


def test_pull_request_workflow_covers_supported_python_and_windows() -> None:
    workflow = (ROOT / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")

    assert 'python-version: ["3.11", "3.12", "3.13"]' in workflow
    assert "windows-latest" in workflow
    assert (
        "tests-required:\n"
        "    name: Tests\n"
        "    runs-on: ubuntu-latest\n"
        "    if: ${{ always() }}\n"
        "    needs: tests"
    ) in workflow
    assert "package-validation:" in workflow
    assert "needs: tests-required" in workflow
    assert "--artifact-kind wheel" in workflow
    assert "--artifact-kind sdist" in workflow


def test_publish_workflow_gates_build_and_publish_on_validation() -> None:
    workflow = (ROOT / ".github/workflows/publish-pypi.yml").read_text(encoding="utf-8")

    assert "validate-release:" in workflow
    assert '--tag "${{ github.ref_name }}"' in workflow
    assert "needs: validate-release" in workflow
    assert "needs: tests" in workflow
    assert "needs: package-smoke" in workflow
    assert 'artifact-kind: ["wheel", "sdist"]' in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
