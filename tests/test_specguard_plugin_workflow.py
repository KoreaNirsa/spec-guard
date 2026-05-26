from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_PATH = ROOT / ".agents" / "plugins" / "marketplace.json"
SKILL_PATH = ROOT / "plugins" / "specguard" / "skills" / "specguard-workflow" / "SKILL.md"
README_PATH = ROOT / "plugins" / "specguard" / "README.md"
CODEX_PLUGIN_DOC_PATH = ROOT / "docs" / "codex-plugin.md"
CODEX_PLUGIN_ROADMAP_PATH = ROOT / "docs" / "codex-plugin-hardening-roadmap.md"
CODEX_PLUGIN_GRILL_LOOP_DOC_PATH = ROOT / "docs" / "cli-grill-me-loop.md"


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


def test_specguard_plugin_docs_cover_readiness_summary_ux() -> None:
    contract = (ROOT / "docs" / "plugin-result-contract.md").read_text(encoding="utf-8")
    guide = CODEX_PLUGIN_DOC_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    skill = SKILL_PATH.read_text(encoding="utf-8")
    combined = "\n".join((contract, guide, readme, skill))

    _assert_contains_all(
        contract,
        (
            "## Plugin Readiness Summary UX",
            "readiness status from `readiness.status`",
            "review level from `review_level`",
            "Critical, Major, and Minor counts from `summary`",
            "top findings using each issue's `severity` and `title`",
            "`implementation-output.md` only when handoff is available",
        ),
    )
    _assert_mentions_all_concepts(
        combined,
        (
            ("stable", "readiness JSON fields"),
            ("Critical", "first", "not_ready"),
            ("ready_with_warnings", "implementation-output.md", "exists"),
            ("full", "reports", "detailed", "finding", "prose"),
        ),
    )


def test_specguard_plugin_docs_cover_guided_rerun_loop() -> None:
    contract = (ROOT / "docs" / "plugin-result-contract.md").read_text(encoding="utf-8")
    guide = CODEX_PLUGIN_DOC_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    skill = SKILL_PATH.read_text(encoding="utf-8")
    combined = "\n".join((contract, guide, readme, skill))

    _assert_contains_all(
        contract,
        (
            "## Guided Plugin Rerun Loop",
            "`state: stale_review`",
            "the rerun command: `specguard run <package> --no-llm --no-follow-up`",
            "Previous findings, suggested clarification text, and Codex-authored wording are not implementation input.",
            "A fresh `readiness.status: \"not_ready\"` should be reported as still blocked.",
        ),
    )
    _assert_contains_all(
        skill,
        (
            "## Guided Rerun Loop",
            "Rerun `specguard run <path> --no-llm --no-follow-up` after the user updates the spec package.",
            "If the fresh result is `not_ready`, report it as still blocked",
        ),
    )
    _assert_mentions_all_concepts(
        combined,
        (
            ("edited", "spec", "stale_review"),
            ("previous", "findings", "suggestions only"),
            ("Needs user decision", "unclear", "behavior"),
            ("fresh", "status", "finding counts", "current report paths", "next action"),
        ),
    )


def test_specguard_plugin_skill_documents_pr_review_setup_workflow() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    _assert_contains_all(
        skill,
        (
            "## PR Review Setup Workflow",
            "PR Review를 설정해줘",
            "git status --short --branch",
            "git remote -v",
            "specguard actions install-pr-review",
            ".github/workflows/specguard-pr-review.yml",
            "SPECGUARD_OPENAI_API_KEY",
            "SPECGUARD_PR_REVIEW_MODEL",
            "SPECGUARD_REVIEW_SPEC_PATHS",
            "gh auth status",
            "gh secret set SPECGUARD_OPENAI_API_KEY --repo <owner/name>",
            "GitHub repository Settings > Secrets and variables > Actions",
        ),
    )
    _assert_mentions_all_concepts(
        skill,
        (
            ("ask", "before", "writing", "workflow"),
            ("Installing", "plugin", "does not install", "CLI"),
            ("Required", "secret", "Optional", "variables"),
            ("do not", "invent", "generate", "store", "commit", "API keys"),
            ("do not", "echo", "API key"),
            ("manual setup instructions",),
        ),
    )


def test_specguard_plugin_docs_cover_pr_review_setup_boundaries() -> None:
    guide = CODEX_PLUGIN_DOC_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    combined = guide + "\n" + readme

    _assert_contains_all(
        combined,
        (
            "@SpecGuard PR Review를 설정해줘",
            "specguard actions install-pr-review",
            ".github/workflows/specguard-pr-review.yml",
            "SPECGUARD_OPENAI_API_KEY",
            "SPECGUARD_PR_REVIEW_MODEL",
            "SPECGUARD_REVIEW_SPEC_PATHS",
            "gh secret set SPECGUARD_OPENAI_API_KEY --repo <owner/name>",
            "GitHub Settings > Secrets and variables > Actions",
        ),
    )
    _assert_mentions_all_concepts(
        combined,
        (
            ("PR Review setup", "opt-in", "advisory"),
            ("Installing", "plugin", "does not install", "CLI"),
            ("ask", "before", "workflow"),
            ("Required", "secret", "Optional", "variables"),
            ("must not", "invent", "generate", "store", "commit", "API keys"),
            ("manual", "GitHub Settings"),
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
            "Codex Plugin Hardening Roadmap](codex-plugin-hardening-roadmap.md)",
            "CLI-Driven Grill Me Loop](cli-grill-me-loop.md)",
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
            ("Grill me", "grill.json", "decisions"),
            ("Open", "your-codex-project-folder", "Codex"),
            ("Run SpecGuard", "specs/your-feature-name"),
        ),
    )
    assert "specs/my-feature" not in doc


def test_codex_plugin_hardening_roadmap_prioritizes_v04x_work() -> None:
    roadmap = CODEX_PLUGIN_ROADMAP_PATH.read_text(encoding="utf-8")

    _assert_contains_all(
        roadmap,
        (
            "## Immediate v0.4.1",
            "## Should-Have v0.4.x",
            "## Later v0.4.x",
            "Related issue: #174",
            "Related issue: #175",
            "Plugin Run And Recovery States",
            "Result Summary UX",
            "CLI-Driven Grill Me Loop",
            "Native Plugin Or MCP Exploration",
            "readiness-review.json",
            "Related issue: #194",
        ),
    )
    _assert_mentions_all_concepts(
        roadmap,
        (
            ("user problem", "expected behavior", "non-goals"),
            ("missing contracts",),
            ("CLI", "canonical engine"),
            ("default", "plugin gate", "--no-llm", "--no-follow-up"),
            ("Do not", "automatic spec rewriting"),
            ("Do not", "LLM review", "default gate"),
            ("Do not", "official plugin directory"),
        ),
    )


def test_cli_grill_me_loop_documents_traceable_decision_workflow() -> None:
    doc = CODEX_PLUGIN_GRILL_LOOP_DOC_PATH.read_text(encoding="utf-8")

    _assert_contains_all(
        doc,
        (
            "Related issue: #211",
            "Related design: #194",
            "specguard grill <package> findings",
            "<package>/grill.json",
            "readiness_summary",
            "resolution_prompts",
            "<package>/decisions/specguard-decisions.jsonl",
            "spec review -> Grill me questions -> decision record -> spec patch -> spec review rerun",
            "\"id\": \"SG-001\"",
            "\"allowed_resolution\": [\"update-spec\", \"mark-intentional\", \"defer\", \"reject\"]",
            "\"source\": \"user-confirmed\"",
            "specguard run <package> --no-llm --no-follow-up",
            "<package>/decisions/specguard-rerun-comparison.json",
        ),
    )
    _assert_mentions_all_concepts(
        doc,
        (
            ("CLI", "canonical review engine"),
            ("stable", "review ids"),
            ("severity", "evidence", "location", "question"),
            ("not_ready", "Problem", "Counts"),
            ("update-spec", "mark-intentional", "defer", "reject"),
            ("User", "Confirm", "defer", "reject"),
            ("patch", "only", "confirmed decisions"),
            ("show", "before/after diff"),
            ("rerun", "SpecGuard"),
            ("schema version", "0.1"),
            ("Deferred", "rejected", "excluded", "spec patches"),
            ("Do not", "LLM review", "default gate"),
        ),
    )


def test_codex_plugin_guide_covers_required_validation_scenarios() -> None:
    doc = CODEX_PLUGIN_DOC_PATH.read_text(encoding="utf-8")

    for scenario in (
        "missing `specguard` CLI",
        "missing spec package",
        "existing spec package reaches `ready`",
        "existing spec package is `not_ready` with Critical findings",
        "`ready_with_warnings` handoff guidance",
        "edited spec package rerun loop",
        "fresh rerun result",
        "stale readiness report",
        "validation failure before review",
        "optional detail review requested without provider setup",
        "CLI timeout",
        "unclassified CLI failure",
        "PR Review setup requested",
        "CLI-driven Grill me loop",
    ):
        assert scenario in doc

    _assert_contains_all(
        doc,
        (
            "missing_cli",
            "missing_spec_package",
            "stale_review",
            "validation_failed_before_review",
            "missing_provider_for_llm",
            "timeout",
            "cli_execution_failed",
            "SPECGUARD_OPENAI_API_KEY",
        ),
    )
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
