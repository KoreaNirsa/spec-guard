from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from tools.result import CheckResult
from tools.ux import bold, cyan, dim, yellow


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

GUIDED_DISCOVERY_TURNS = (
    ("problem", "Problem", "What problem should these specs solve?"),
    ("users", "Users", "Who is affected by this feature, and who needs to use or maintain it?"),
    ("constraints", "Constraints", "What constraints are non-negotiable for the first implementation?"),
    ("flows", "Flows", "What are the main user or system flows from start to finish?"),
    ("data", "Data Ownership", "What input, output, and state data does this feature use, and who owns each piece?"),
    ("dependencies", "Dependencies", "Which external systems, contracts, storage, or services does this feature depend on?"),
    ("risks", "Risks", "What can fail, be abused, or become ambiguous if the spec is incomplete?"),
    ("acceptance", "Acceptance", "What would prove this spec is ready for technical design, tests, and contracts?"),
)

SPEC_PACKAGE_FILES = (
    "discovery.md",
    "spec.md",
    "plan.md",
    "tasks.md",
    "constitution.md",
    "checklists/spec-readiness.md",
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
    print(cyan(bold("SpecGuard Discovery")))
    print(dim("Answer the questions below. Press Enter to accept the default."))
    print("")

    for key, prompt, _default in DISCOVERY_PROMPTS:
        default = defaults[key]
        try:
            value = input(f"{bold(prompt)} {yellow('[' + default + ']')}: ").strip()
        except EOFError:
            value = ""
        answers[key] = value or default
    return answers


def _write_default(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def _write_line(write_func: Callable[[str], None], text: str = "") -> None:
    write_func(f"{text}\n")


def _finish_requested(value: str) -> bool:
    return value.strip().lower() in {"done", "end", "finish", "exit", "quit", "complete", "완료", "끝", "종료"}


def _conversation_text(transcript: list[tuple[str, str]]) -> str:
    if not transcript:
        return "No additional LLM Discovery conversation was provided."
    lines: list[str] = []
    for role, content in transcript:
        lines.append(f"{role}: {content.strip()}")
    return "\n\n".join(lines)


def collect_llm_answers(
    args: argparse.Namespace,
    llm_client: object,
    *,
    max_turns: int = 8,
    input_func: Callable[[str], str] = input,
    write_func: Callable[[str], None] = _write_default,
) -> dict[str, str]:
    _ = llm_client
    answers = answers_from_args(args)
    transcript: list[tuple[str, str]] = []
    turns = GUIDED_DISCOVERY_TURNS[:max_turns]

    _write_line(write_func, cyan(bold("SpecGuard LLM Discovery")))
    _write_line(write_func, dim("Answer naturally. Press Enter to accept the default."))
    _write_line(write_func, dim("Questions are shown instantly; the configured LLM generates the draft spec after your answers."))
    _write_line(write_func, "Type 'done' or '완료' to finish early and generate the draft spec.")
    _write_line(write_func, "")

    for index, (key, label, question) in enumerate(turns, start=1):
        default = answers[key]
        assistant_message = f"{label}: {question}"
        _write_line(write_func, cyan(bold(f"SpecGuard ({index}/{len(turns)}) {label}")))
        _write_line(write_func, question)
        _write_line(write_func, yellow(f"Default: {default}"))
        transcript.append(("assistant", assistant_message))

        try:
            user_message = input_func("You: ").strip()
        except EOFError:
            user_message = "done"

        if _finish_requested(user_message):
            transcript.append(("user", user_message))
            break

        if user_message:
            answers[key] = user_message
            transcript.append(("user", user_message))
        else:
            transcript.append(("user", f"(accepted default: {default})"))
            _write_line(write_func, cyan(f"> Using default: {default}"))
        _write_line(write_func, "")
    else:
        _write_line(write_func, "")
        _write_line(write_func, "> Discovery turn limit reached. Generating the draft spec from the conversation.")

    answers["conversation"] = _conversation_text(transcript)
    return answers


def _discovery_markdown(feature_slug: str, answers: dict[str, str]) -> str:
    title = _feature_title(feature_slug)
    lines = [
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
        "- Stop condition: Do not start code implementation while Critical or Major Readiness Findings remain.",
        "",
    ]
    conversation = answers.get("conversation", "").strip()
    if conversation:
        lines.extend([
            "## LLM Discovery Conversation",
            "",
            conversation,
            "",
        ])
    return "\n".join(lines)


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


def _plan_markdown(feature_slug: str, answers: dict[str, str]) -> str:
    title = _feature_title(feature_slug)
    return "\n".join([
        f"# Implementation Plan: {title}",
        "",
        "## Objective",
        "",
        f"- Deliverable: {answers['problem']}",
        f"- Success outcome: {answers['outcomes']}",
        "- Implementation may start only after SpecGuard Review reports an implementation-ready result.",
        "",
        "## Scope",
        "",
        f"- In scope: {answers['flows']}",
        f"- Out of scope: {answers['out_of_scope']}",
        f"- Non-negotiable constraints: {answers['constraints']}",
        "",
        "## Technical Context",
        "",
        f"- Data and entities: {answers['data']}",
        f"- Dependencies: {answers['dependencies']}",
        "- Required downstream artifacts: `technical-design.md`, `tests/`, `contracts/`, and `implementation-output.md`.",
        "",
        "## Quality Gates",
        "",
        "- Discovery and spec validation pass.",
        "- Technical design is regenerated after meaningful spec changes.",
        "- SpecGuard Readiness Gate is implementation-ready before tests, contracts, and implementation output are trusted.",
        "- Coding agents consume only the approved implementation package.",
        "",
    ])


def _tasks_markdown(feature_slug: str, answers: dict[str, str]) -> str:
    title = _feature_title(feature_slug)
    return "\n".join([
        f"# Tasks: {title}",
        "",
        "## Spec Package",
        "",
        "- [ ] Review `discovery.md` for goal, users, constraints, flows, data, dependencies, risks, and acceptance evidence.",
        "- [ ] Review `spec.md` for explicit requirements, acceptance criteria, and error cases.",
        "- [ ] Review `plan.md` for scope, quality gates, and implementation boundary.",
        "- [ ] Review `constitution.md` for project rules that must not be violated.",
        "- [ ] Complete `checklists/spec-readiness.md` before implementation starts.",
        "",
        "## Design And Validation",
        "",
        f"- [ ] Run `python -m cli.specguard run specs/{feature_slug} --force`.",
        "- [ ] Convert every Critical or Major Readiness Finding into a spec, plan, task, or design update.",
        "- [ ] Re-run SpecGuard until SpecGuard Review reports implementation-ready status.",
        "",
        "## Implementation Handoff",
        "",
        f"- [ ] Confirm the primary flow is covered: {answers['flows']}.",
        f"- [ ] Confirm risk handling is covered: {answers['risks']}.",
        f"- [ ] Confirm acceptance evidence is testable: {answers['acceptance']}.",
        "- [ ] Hand `implementation-output.md` to Codex or Claude Code only after SpecGuard passes.",
        "",
    ])


def _constitution_markdown(feature_slug: str, answers: dict[str, str]) -> str:
    title = _feature_title(feature_slug)
    return "\n".join([
        f"# Constitution: {title}",
        "",
        "## Principles",
        "",
        "- Spec-first: implementation must follow the approved spec package, not inferred intent.",
        "- Review-first: Critical and Major Readiness Findings block implementation readiness.",
        "- Testability: every meaningful requirement needs acceptance evidence or an explicit deferral.",
        "- Safety: authorization, data ownership, failure handling, and abuse cases must be explicit.",
        "- Determinism: generated artifacts must be reproducible enough for audit and review.",
        "",
        "## Boundaries",
        "",
        f"- User and maintainer boundary: {answers['users']}",
        f"- Data boundary: {answers['data']}",
        f"- Dependency boundary: {answers['dependencies']}",
        f"- Exclusion boundary: {answers['out_of_scope']}",
        "",
        "## Change Control",
        "",
        "- Update spec artifacts before changing generated implementation outputs.",
        "- Re-run SpecGuard after any requirement, risk, contract, or state-flow change.",
        "- Do not ask coding agents to fill missing requirements by assumption.",
        "",
    ])


def _readiness_checklist_markdown(feature_slug: str, answers: dict[str, str]) -> str:
    title = _feature_title(feature_slug)
    return "\n".join([
        f"# Spec Readiness Checklist: {title}",
        "",
        "## Requirements",
        "",
        "- [ ] Requirements describe observable behavior, not implementation wishes.",
        "- [ ] Acceptance criteria cover success, rejection, and edge behavior.",
        "- [ ] Error cases include missing, invalid, unauthorized, conflicting, and dependency-failure paths where relevant.",
        "",
        "## Architecture Inputs",
        "",
        "- [ ] Data ownership and privacy boundaries are explicit.",
        "- [ ] External dependencies and contracts are named.",
        "- [ ] State transitions, idempotency, retry, timeout, and rollback behavior are defined when relevant.",
        "",
        "## SpecGuard Readiness Gate",
        "",
        "- [ ] Critical findings: 0.",
        "- [ ] Major findings: 0.",
        "- [ ] Minor findings: 5 or fewer, with no unresolved ambiguity that blocks coding.",
        f"- [ ] Acceptance evidence is clear: {answers['acceptance']}.",
        "",
    ])


def _answers_text(feature_slug: str, answers: dict[str, str]) -> str:
    lines = [f"Feature: {feature_slug}", ""]
    for key, value in answers.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _llm_spec_markdown(feature_slug: str, answers: dict[str, str], llm_client: object) -> str:
    instructions = "\n".join([
        "You are SpecGuard, a principal product/specification architect.",
        "Generate a human-reviewable spec.md from the user's Discovery answers.",
        "The complete SpecGuard package also includes discovery.md, plan.md, tasks.md, constitution.md, and checklists/spec-readiness.md.",
        "Write spec.md so it can stand beside those package files without contradiction.",
        "SpecGuard is not prompt-to-code. Do not generate application code.",
        "Return ONLY Markdown.",
        "Make every requirement explicit, testable, versionable, and reviewable by SpecGuard Review.",
        "Prefer precise contracts, state, ownership, authorization, failure, and determinism language over broad product prose.",
        "Use this exact section structure:",
        "# Feature Specification: <Feature Title>",
        "**Status**: Draft",
        "**Source**: `discovery.md`",
        "## User Scenarios & Testing",
        "### Primary User Story",
        "### Acceptance Scenarios",
        "### Edge Cases",
        "## Requirements",
        "### Functional Requirements",
        "## Acceptance Criteria",
        "## Error Cases",
        "## Key Entities",
        "## Out of Scope",
        "## Review & Acceptance Checklist",
        "Each required section must contain concrete content derived from Discovery answers.",
        "Acceptance Criteria and Error Cases must each contain at least one Markdown checklist or bullet item.",
    ])
    return llm_client.generate_text(instructions, _answers_text(feature_slug, answers), max_output_tokens=3000)


def _write_text_if_needed(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def initialize_specs(root: Path, answers: dict[str, str], force: bool = False, llm_client: object | None = None) -> CheckResult:
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
        package_artifacts = {
            "plan.md": _plan_markdown(feature_slug, answers),
            "tasks.md": _tasks_markdown(feature_slug, answers),
            "constitution.md": _constitution_markdown(feature_slug, answers),
            "checklists/spec-readiness.md": _readiness_checklist_markdown(feature_slug, answers),
        }

        if not _write_text_if_needed(discovery_path, _discovery_markdown(feature_slug, answers), force):
            result.add_info(f"Kept existing discovery artifact: {discovery_path}")
        else:
            result.add_info(f"Generated discovery artifact: {discovery_path}")

        if spec_path.exists() and not force:
            result.add_info(f"Kept existing draft spec: {spec_path}")
        else:
            if llm_client is None:
                spec = _spec_markdown(feature_slug, answers)
                result.add_info(f"Generated draft spec: {spec_path}")
            else:
                spec = _llm_spec_markdown(feature_slug, answers, llm_client)
                result.add_info(f"Generated LLM draft spec: {spec_path}")
            spec_path.write_text(spec, encoding="utf-8")

        for relative_path, content in package_artifacts.items():
            artifact_path = feature_dir / relative_path
            if _write_text_if_needed(artifact_path, content, force):
                result.add_info(f"Generated spec package artifact: {artifact_path}")
            else:
                result.add_info(f"Kept existing spec package artifact: {artifact_path}")

    result.add_info(f"Prepared implementation output root: {develop_root}")
    result.add_next_step("Review and refine generated specs under specs/: discovery, spec, plan, tasks, constitution, and checklists.")
    result.add_next_step("After spec review, run: python -m cli.specguard run specs (or target one feature with specs/<feature-name>)")
    return result
