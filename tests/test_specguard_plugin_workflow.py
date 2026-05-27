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
PLUGIN_EXAMPLES_DOC_PATH = ROOT / "docs" / "plugin-examples.md"
PLUGIN_SCENARIO_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "plugin-workflow-scenarios" / "scenarios.json"
PR_REVIEW_KOREAN_EXAMPLE = "PR Review를 설정해줘"
ENCODING_ARTIFACT_MARKERS = ("PR Review瑜", "ㅼ젙", "댁쨾", "\ufffd", "Ã", "Â")


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


def _load_plugin_scenario_fixture() -> dict[str, object]:
    return json.loads(PLUGIN_SCENARIO_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_specguard_plugin_skill_defines_heuristic_first_cli_workflow() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    _assert_contains_all(
        skill,
        (
            "specguard --help",
            "python -m cli.specguard --help",
            "**/specs/*/spec.md",
            "hidden, dependency, build, and generated directories",
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
            ("multiple", "candidate", "explicit"),
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


def test_specguard_plugin_skill_defines_result_summary_prompt_contract() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    _assert_contains_all(
        skill,
        (
            "## Result Summary Prompt Contract",
            "Use `readiness-review.json` as the only machine-readable source of readiness state.",
            "`status`: `readiness.status` plus `review_level`.",
            "`counts`: `summary.critical`, `summary.major`, and `summary.minor`.",
            "`findings`: top `issues[]` entries by `severity` and `title`; for `not_ready`, list Critical findings first",
            "`reports`: `readiness-review.json` and `readiness-review.md` when present.",
            "`handoff`: report yes only when `readiness.status` is `ready` or `ready_with_warnings`, `readiness.implementation_ready` is true, and `implementation-output.md` exists.",
            "`next_action`: derive from the resolved state, not from terminal logs or generated Markdown prose.",
            "Keep `SpecGuard evidence` separate from `Codex interpretation`",
            "`ready_with_warnings`: implementation is allowed when handoff is available; warnings are optional cleanup, not blockers.",
            "`not_ready`: implementation is blocked; summarize Critical findings first",
            "`validation_failed_before_review`: report that no current readiness result exists",
            "`timeout` and `cli_execution_failed`: include the attempted command, known files for diagnostics, and the next safe action",
        ),
    )
    _assert_mentions_all_concepts(
        skill,
        (
            ("terminal output", "must not determine", "readiness status"),
            ("ready", "implementation may proceed", "handoff"),
            ("stale_review", "old files", "current result", "rerun command"),
            ("implementation-output.md", "relevant handoff"),
            ("Codex interpretation", "implementation input"),
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


def test_specguard_plugin_docs_keep_pr_review_korean_example_readable() -> None:
    for path in (SKILL_PATH, README_PATH, CODEX_PLUGIN_DOC_PATH):
        text = path.read_text(encoding="utf-8")

        assert PR_REVIEW_KOREAN_EXAMPLE in text
        artifacts = [marker for marker in ENCODING_ARTIFACT_MARKERS if marker in text]
        assert not artifacts, f"{path} contains encoding artifacts: {artifacts}"


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
            ("nested", "specs"),
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
            ("nested", "specs"),
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
            "non-excluded `**/specs/*/spec.md`",
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


def test_plugin_workflow_scenario_fixtures_cover_issue_212_examples() -> None:
    fixture = _load_plugin_scenario_fixture()
    assert fixture["schema"] == "specguard-plugin-validation-scenarios/v1"

    scenarios = fixture["scenarios"]
    assert isinstance(scenarios, list)
    by_state = {scenario["expected_state"]: scenario for scenario in scenarios}

    assert {
        "plugin_available",
        "missing_cli",
        "ready",
        "ready_with_warnings",
        "not_ready",
        "stale_review",
        "validation_failed_before_review",
    } <= set(by_state)

    for scenario in scenarios:
        assert scenario["id"]
        assert scenario["category"] in {"install", "run", "recovery"}
        assert isinstance(scenario["commands"], list)
        assert all(isinstance(command, str) and command for command in scenario["commands"])
        assert isinstance(scenario["stable_files"], list)
        assert isinstance(scenario["safety_boundaries"], list)
        assert scenario["safety_boundaries"]

    assert "codex plugin marketplace add KoreaNirsa/spec-guard --ref main" in by_state["plugin_available"]["commands"]
    assert "specguard --help" in by_state["missing_cli"]["commands"]
    assert "python -m cli.specguard --help" in by_state["missing_cli"]["commands"]

    for state in ("ready", "ready_with_warnings", "not_ready", "stale_review", "validation_failed_before_review"):
        assert "specguard run <package> --no-llm --no-follow-up" in by_state[state]["commands"]

    for state in ("ready", "ready_with_warnings"):
        assert by_state[state]["handoff"] == "allowed"
        assert "readiness-review.json" in by_state[state]["stable_files"]
        assert "readiness-review.md" in by_state[state]["stable_files"]
        assert "implementation-output.md" in by_state[state]["stable_files"]

    assert by_state["not_ready"]["handoff"] == "blocked"
    assert "readiness-review.json" in by_state["not_ready"]["stable_files"]
    assert "readiness-review.md" in by_state["not_ready"]["stable_files"]
    assert "implementation-output.md" not in by_state["not_ready"]["stable_files"]

    failure_categories = {
        scenario["failure_category"]
        for scenario in scenarios
        if scenario["failure_category"] is not None
    }
    assert {"missing_cli", "stale_review", "validation_failed_before_review"} <= failure_categories

    fixture_text = json.dumps(fixture)
    assert "Todo ownership boundary is unclear" not in fixture_text
    assert "Detailed blocker description" not in fixture_text


def test_plugin_examples_docs_separate_packaged_and_contributor_only_fixtures() -> None:
    doc = PLUGIN_EXAMPLES_DOC_PATH.read_text(encoding="utf-8")
    guide = CODEX_PLUGIN_DOC_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    development = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    combined = "\n".join((doc, guide, readme, development, root_readme))

    _assert_contains_all(
        doc,
        (
            "tools/resources/example/",
            "specguard example copy specs/your-feature-name --force",
            "specguard run specs/your-feature-name --no-llm --no-follow-up",
            "tests/fixtures/plugin-workflow-scenarios/scenarios.json",
            "not packaged resources",
            "must not grow into a full sample application without a separate scope decision",
            "python -m pytest tests/test_specguard_plugin_workflow.py -q",
            "python -m pytest tests/test_plugin_result_contract.py -q",
            "python -m pytest tests/test_packaging.py -q",
        ),
    )
    _assert_contains_all(
        combined,
        (
            "Plugin Examples And Contributor Fixtures",
            "tests/fixtures/plugin-workflow-scenarios/",
            "stable commands, file names, failure categories, and safety boundaries",
        ),
    )
    assert "tests/fixtures/plugin-workflow-scenarios" not in pyproject


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
