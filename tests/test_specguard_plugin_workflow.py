from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_PATH = ROOT / ".agents" / "plugins" / "marketplace.json"
SKILL_PATH = ROOT / "plugins" / "specguard" / "skills" / "specguard-workflow" / "SKILL.md"
README_PATH = ROOT / "plugins" / "specguard" / "README.md"
CODEX_PLUGIN_DOC_PATH = ROOT / "docs" / "codex-plugin.md"


def _assert_contains_all(text: str, required: tuple[str, ...]) -> None:
    missing = [item for item in required if item not in text]
    assert not missing


def _assert_mentions_all_concepts(text: str, concepts: tuple[tuple[str, ...], ...]) -> None:
    normalized = text.lower()
    missing = [
        "/".join(concept)
        for concept in concepts
        if not all(term.lower() in normalized for term in concept)
    ]
    assert not missing


def _assert_default_heuristic_command(text: str) -> None:
    assert re.search(r"specguard run <(?:path|package)> --no-llm --no-follow-up", text)


def _assert_suggestion_only_boundary(text: str) -> None:
    _assert_mentions_all_concepts(
        text,
        (
            ("suggestion", "only"),
            ("not", "modify"),
            ("spec"),
            ("SpecGuard evidence", "Codex suggestion"),
            ("Needs user decision",),
            ("not", "invent"),
            ("rerun", "SpecGuard"),
        ),
    )


def test_specguard_plugin_skill_defines_heuristic_first_cli_workflow() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    _assert_contains_all(
        skill,
        (
            "specguard --help",
            "python -m cli.specguard --help",
            "specs/*/spec.md",
            "specguard run <path> --llm --no-follow-up",
            "specguard run <path> --llm --follow-up",
            "readiness-review.json",
            "readiness-review-detail.json",
            "implementation-output.md",
        ),
    )
    _assert_default_heuristic_command(skill)
    _assert_mentions_all_concepts(
        skill,
        (
            ("heuristic", "default"),
            ("structured files",),
            ("terminal logs",),
            ("handoff", "availability"),
        ),
    )


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

    _assert_default_heuristic_command(readme)
    _assert_contains_all(
        readme,
        ("specguard run <package> --llm --follow-up", "Plugin Result Contract"),
    )
    _assert_mentions_all_concepts(
        readme,
        (
            ("Detail Review", "default gate"),
            ("structured files", "terminal log scraping"),
            ("implementation handoff", "allowed"),
        ),
    )


def test_root_readme_documents_plugin_quickstart_steps() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    _assert_contains_all(
        readme,
        (
            "## Codex App Plugin",
            "pip install spec-guard",
            "specguard --help",
            "codex plugin marketplace add KoreaNirsa/spec-guard --ref main",
            "SpecGuard Plugins",
            "mkdir your-codex-project-folder",
            "cd your-codex-project-folder",
            "specguard example copy specs/your-feature-name --force",
        ),
    )
    _assert_mentions_all_concepts(
        readme,
        (
            ("Python", "3.11", "3.12", "3.13"),
            ("Codex CLI", "plugin marketplace"),
            ("Installing the plugin", "SpecGuard CLI"),
            ("not", "official OpenAI Plugin Directory"),
            ("Open", "your-codex-project-folder", "Codex"),
            ("Run SpecGuard", "specs/your-feature-name"),
        ),
    )
    assert "specs/my-feature" not in readme


def test_specguard_plugin_documents_suggestion_only_spec_refinement_boundary() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    combined = skill + "\n" + readme

    _assert_suggestion_only_boundary(skill)
    _assert_suggestion_only_boundary(readme)
    _assert_contains_all(
        combined,
        ("Addressed finding: <Severity> - <Finding title>", "not an applied patch"),
    )


def test_codex_plugin_guide_documents_app_setup_and_mvp_flow() -> None:
    doc = CODEX_PLUGIN_DOC_PATH.read_text(encoding="utf-8")

    _assert_contains_all(
        doc,
        (
            ".agents/plugins/marketplace.json",
            "codex plugin marketplace add KoreaNirsa/spec-guard --ref main",
            "SpecGuard Plugins",
            "pip install spec-guard",
            "plugins/specguard/",
            "plugins/specguard/.codex-plugin/plugin.json",
            "implementation-output.md",
            "Plugin Result Contract](plugin-result-contract.md)",
            "Spec Refinement Safety Boundary",
            "mkdir your-codex-project-folder",
            "cd your-codex-project-folder",
            "specguard example copy specs/your-feature-name --force",
        ),
    )
    _assert_default_heuristic_command(doc)
    _assert_mentions_all_concepts(
        doc,
        (
            ("Python", "3.11", "3.12", "3.13"),
            ("Codex CLI", "plugin marketplace"),
            ("not", "official OpenAI Plugin Directory"),
            ("Installing the plugin", "specguard", "CLI"),
            ("CLI", "canonical engine"),
            ("Create or select", "spec package"),
            ("manually edit", "spec package"),
            ("Detail Review", "optional", "advisory"),
            ("Open", "your-codex-project-folder", "Codex"),
            ("Run SpecGuard", "specs/your-feature-name"),
        ),
    )
    assert "specs/my-feature" not in doc


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

    _assert_contains_all(doc, ("missing_cli", "missing_provider_for_llm"))
    _assert_mentions_all_concepts(
        doc,
        (
            ("Do not", "native plugin engine"),
            ("Do not", "full MCP"),
            ("Do not", "automatic spec rewriting"),
        ),
    )


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
