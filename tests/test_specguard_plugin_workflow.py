from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_PATH = ROOT / ".agents" / "plugins" / "marketplace.json"
SKILL_PATH = ROOT / "plugins" / "specguard" / "skills" / "specguard-workflow" / "SKILL.md"
README_PATH = ROOT / "plugins" / "specguard" / "README.md"
CODEX_PLUGIN_DOC_PATH = ROOT / "docs" / "codex-plugin.md"


def test_specguard_plugin_skill_defines_heuristic_first_cli_workflow() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    assert "specguard --help" in skill
    assert "python -m cli.specguard --help" in skill
    assert "specs/*/spec.md" in skill
    assert "specguard run <path> --no-llm --no-follow-up" in skill
    assert "specguard run <path> --llm --no-follow-up" in skill
    assert "specguard run <path> --llm --follow-up" in skill
    assert "readiness-review-detail.json" in skill
    assert "Do not add `--llm`" in skill
    assert "Use `readiness-review.json` as the machine result" in skill
    assert "Do not scrape terminal logs for readiness state" in skill
    assert "handoff availability" in skill


def test_specguard_plugin_skill_documents_common_failure_categories() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    for category in (
        "missing_cli",
        "missing_spec_package",
        "validation_failed_before_review",
        "stale_review",
        "missing_provider_for_llm",
        "timeout",
        "cli_execution_failed",
    ):
        assert category in skill


def test_specguard_plugin_readme_points_to_structured_result_handling() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "specguard run <package> --no-llm --no-follow-up" in readme
    assert "specguard run <package> --llm --follow-up" in readme
    assert "Do not treat Detail Review as the default gate" in readme
    assert "structured files, not terminal log scraping" in readme
    assert "whether implementation handoff is allowed" in readme
    assert "Plugin Result Contract" in readme


def test_root_readme_documents_plugin_quickstart_steps() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## Codex App Plugin" in readme
    assert "pip install spec-guard" in readme
    assert "specguard --help" in readme
    assert "codex plugin marketplace add KoreaNirsa/spec-guard --ref main" in readme
    assert "select the `SpecGuard Plugins` source and install `SpecGuard`" in readme
    assert "Run SpecGuard on specs/my-feature." in readme
    assert "Installing the plugin does not install the SpecGuard CLI" in readme
    assert "not the official OpenAI Plugin Directory" in readme


def test_specguard_plugin_documents_suggestion_only_spec_refinement_boundary() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    combined = skill + "\n" + readme

    assert "The MVP plugin must not modify spec package files" in skill
    assert "The MVP plugin is suggestion-only" in readme
    assert "Addressed finding: <Severity> - <Finding title>" in skill
    assert "SpecGuard evidence" in combined
    assert "Codex suggestion" in combined
    assert "Needs user decision" in combined
    assert "not an applied patch" in combined
    assert "must not invent fields, requirements, states, error behavior, ownership rules, or product behavior" in readme
    assert "reruns SpecGuard" in combined


def test_codex_plugin_guide_documents_app_setup_and_mvp_flow() -> None:
    doc = CODEX_PLUGIN_DOC_PATH.read_text(encoding="utf-8")

    assert ".agents/plugins/marketplace.json" in doc
    assert "codex plugin marketplace add KoreaNirsa/spec-guard --ref main" in doc
    assert "SpecGuard Plugins" in doc
    assert "not the official OpenAI Plugin Directory" in doc
    assert "Installing the plugin does not install the `specguard` CLI" in doc
    assert "pip install spec-guard" in doc
    assert "plugins/specguard/" in doc
    assert "plugins/specguard/.codex-plugin/plugin.json" in doc
    assert "CLI is the canonical engine" in doc
    assert "Create or select a spec package" in doc
    assert "specguard run <package> --no-llm --no-follow-up" in doc
    assert "manually edit the spec package" in doc
    assert "implementation-output.md" in doc
    assert "Codex-backed Detail Review is optional and advisory" in doc
    assert "Plugin Result Contract](plugin-result-contract.md)" in doc
    assert "Spec Refinement Safety Boundary" in doc


def test_codex_plugin_guide_covers_required_validation_scenarios() -> None:
    doc = CODEX_PLUGIN_DOC_PATH.read_text(encoding="utf-8")

    for scenario in (
        "missing `specguard` CLI",
        "existing spec package reaches `READY`",
        "existing spec package is `NOT_READY` with Critical findings",
        "`READY_WITH_WARNINGS` handoff guidance",
        "optional detail review requested without provider setup",
    ):
        assert scenario in doc

    assert "missing_cli" in doc
    assert "missing_provider_for_llm" in doc
    assert "Do not claim native plugin engine support" in doc
    assert "Do not document full MCP support until it exists" in doc
    assert "Do not document automatic spec rewriting" in doc


def test_specguard_plugin_marketplace_metadata_points_to_plugin() -> None:
    marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))

    assert marketplace["name"] == "specguard-plugins"
    assert marketplace["interface"]["displayName"] == "SpecGuard Plugins"

    plugins = marketplace["plugins"]
    assert len(plugins) == 1

    [plugin] = plugins
    assert plugin["name"] == "specguard"
    assert plugin["source"] == {
        "source": "local",
        "path": "./plugins/specguard",
    }
    assert plugin["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert plugin["category"] == "Developer Tools"
    assert (ROOT / "plugins" / "specguard" / ".codex-plugin" / "plugin.json").is_file()
