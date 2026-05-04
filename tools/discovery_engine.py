from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from tools.result import CheckResult


DISCOVERY_PROMPTS = (
    ("feature_names", "Feature names to create, comma-separated", "sample-feature"),
    ("problem", "What problem should these specs solve?", "Capture the intended behavior before implementation."),
    ("users", "Who is affected by this feature?", "Users and developers who rely on the feature."),
    ("outcomes", "What outcomes must be true when this works?", "The feature behavior is clear, testable, and safe to implement."),
    ("constraints", "What constraints are non-negotiable?", "Keep the first pass small and implementation-ready."),
    ("flows", "What are the main user or system flows?", "Request, validation, operation, response."),
    ("data", "What data or entities matter?", "Input, output, state, and ownership data."),
    ("dependencies", "Which external systems or dependencies matter?", "Application services, storage, and API contracts."),
    ("risks", "What can fail, be abused, or become ambiguous?", "Invalid input, authorization gaps, unsafe state, and unclear failures."),
    ("out_of_scope", "What should be intentionally excluded?", "Large unrelated features and premature implementation choices."),
    ("acceptance", "What would prove the spec is ready?", "Acceptance criteria, error cases, tests, and contract expectations are explicit."),
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "sample-feature"


def _feature_title(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-") if part) or "Sample Feature"


def _split_features(value: str) -> list[str]:
    return [slugify(part) for part in value.split(",") if part.strip()]


def _answer(args: argparse.Namespace, key: str, default: str) -> str:
    value = getattr(args, key, None)
    if value:
        return value.strip()
    return default


def answers_from_args(args: argparse.Namespace) -> dict[str, str]:
    defaults = {key: default for key, _, default in DISCOVERY_PROMPTS}
    if getattr(args, "feature", None):
        defaults["feature_names"] = args.feature
    return {key: _answer(args, key, defaults[key]) for key, _, _default in DISCOVERY_PROMPTS}


def collect_answers(args: argparse.Namespace) -> dict[str, str]:
    answers: dict[str, str] = {}
    defaults = answers_from_args(args)
    print("SpecGuard Discovery")
    print("Answer the questions below. Press Enter to accept the default.")
    print("")

    for key, prompt, _default in DISCOVERY_PROMPTS:
        default = defaults[key]
        try:
            value = input(f"{prompt} [{default}]: ").strip()
        except EOFError:
            value = ""
        answers[key] = value or default
    return answers


def _discovery_markdown(feature_slug: str, answers: dict[str, str]) -> str:
    title = _feature_title(feature_slug)
    return "\n".join([
        f"# Discovery: {title}",
        "",
        "## Foundation",
        "",
        f"- Goal: {answers['problem']}",
        f"- Users: {answers['users']}",
        f"- Constraints: {answers['constraints']}",
        f"- Desired outcomes: {answers['outcomes']}",
        "",
        "## Mechanisms",
        "",
        f"- Feature focus: {title}",
        f"- Main flows: {answers['flows']}",
        f"- Data and entities: {answers['data']}",
        f"- Dependencies: {answers['dependencies']}",
        "",
        "## Stress Test",
        "",
        f"- Failure and abuse risks: {answers['risks']}",
        "- Boundary conditions: Empty, duplicate, invalid, and unauthorized requests must be handled.",
        "- Recovery expectation: Unsafe or ambiguous behavior should block implementation until clarified.",
        "",
        "## Differentiation",
        "",
        "- Existing option: Start coding directly from a natural-language request.",
        "- Difference: SpecGuard turns the request into a reviewed spec package before implementation.",
        f"- Non-goals: {answers['out_of_scope']}",
        "",
        "## Feasibility",
        "",
        "- Initial scope: Generate a spec draft and supporting validation artifacts.",
        "- Blocker: Missing acceptance criteria, error cases, or ownership boundaries.",
        f"- Validation: {answers['acceptance']}",
        "",
        "## Improvement",
        "",
        "- Simplify: Keep this feature independent and testable.",
        "- Automate later: Expand generated artifacts only after the spec stabilizes.",
        "- Open question: Which implementation stack will consume the final outputs?",
        "",
        "## Synthesis",
        "",
        "- Decision: Review and strengthen the generated spec before running the pipeline.",
        "- Required artifacts: spec.md, technical-design.md, tests, contracts, and implementation-output.md.",
        "- Stop condition: Do not start code implementation while Critical or Major Grill Me findings remain.",
        "",
    ])


def _spec_markdown(feature_slug: str, answers: dict[str, str]) -> str:
    title = _feature_title(feature_slug)
    today = date.today().isoformat()
    return "\n".join([
        f"# Feature Specification: {title}",
        "",
        f"**Created**: {today}",
        "**Status**: Draft",
        "**Source**: `discovery.md`",
        "",
        "## User Scenarios & Testing",
        "",
        "### Primary User Story",
        "",
        f"As {answers['users']}, I need {answers['problem']} so that {answers['outcomes']}.",
        "",
        "### Acceptance Scenarios",
        "",
        f"1. Given the primary flow, when {title} runs, then {answers['acceptance']}.",
        "2. Given invalid or unauthorized input, when the feature runs, then the request is rejected with a clear error.",
        "",
        "### Edge Cases",
        "",
        f"- {answers['risks']}",
        "- Empty, duplicate, malformed, and unauthorized requests are handled explicitly.",
        "",
        "## Requirements",
        "",
        "### Functional Requirements",
        "",
        f"- The system must support the main flows: {answers['flows']}.",
        f"- The system must respect these constraints: {answers['constraints']}.",
        f"- The system must handle these data and entity concerns: {answers['data']}.",
        f"- The system must account for these dependencies: {answers['dependencies']}.",
        f"- The system must reject or block these risks: {answers['risks']}.",
        "",
        "## Acceptance Criteria",
        "",
        f"- [ ] {answers['acceptance']}.",
        "- [ ] The primary user story can be tested independently.",
        "- [ ] Invalid, unauthorized, and ambiguous behavior is rejected.",
        "",
        "## Error Cases",
        "",
        "- Missing required input",
        "- Invalid state",
        "- Unauthorized access",
        f"- {answers['risks']}",
        "",
        "## Key Entities",
        "",
        f"- Feature: {title}",
        f"- Data: {answers['data']}",
        "- Actor: User, caller, or system component that triggers the feature.",
        "",
        "## Out of Scope",
        "",
        f"- {answers['out_of_scope']}",
        "",
        "## Review & Acceptance Checklist",
        "",
        "- [ ] Requirements are written from user and system intent.",
        "- [ ] Acceptance criteria are independently testable.",
        "- [ ] Error cases are explicit.",
        "- [ ] Implementation details are deferred to `technical-design.md`.",
        "",
    ])


def initialize_specs(root: Path, answers: dict[str, str], force: bool = False) -> CheckResult:
    result = CheckResult("SpecGuard Discovery")
    specs_root = root / "specs"
    develop_root = root / "develop"
    specs_root.mkdir(parents=True, exist_ok=True)
    develop_root.mkdir(parents=True, exist_ok=True)
    (develop_root / ".gitkeep").touch(exist_ok=True)

    features = _split_features(answers["feature_names"])
    if not features:
        result.add_error("Discovery must provide at least one feature name.")
        return result

    for feature_slug in features:
        feature_dir = specs_root / feature_slug
        feature_dir.mkdir(parents=True, exist_ok=True)

        discovery_path = feature_dir / "discovery.md"
        spec_path = feature_dir / "spec.md"

        if discovery_path.exists() and not force:
            result.add_info(f"Kept existing discovery artifact: {discovery_path}")
        else:
            discovery_path.write_text(_discovery_markdown(feature_slug, answers), encoding="utf-8")
            result.add_info(f"Generated discovery artifact: {discovery_path}")

        if spec_path.exists() and not force:
            result.add_info(f"Kept existing draft spec: {spec_path}")
        else:
            spec_path.write_text(_spec_markdown(feature_slug, answers), encoding="utf-8")
            result.add_info(f"Generated draft spec: {spec_path}")

        result.add_next_step(f"Review and strengthen the generated spec: {spec_path}")
        result.add_next_step(f"Run the validation workflow: python -m cli.specguard run {feature_dir}")

    result.add_info(f"Prepared implementation output root: {develop_root}")
    return result
