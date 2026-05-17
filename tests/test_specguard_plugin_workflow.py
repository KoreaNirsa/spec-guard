from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "plugins" / "specguard" / "skills" / "specguard-workflow" / "SKILL.md"
README_PATH = ROOT / "plugins" / "specguard" / "README.md"


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
