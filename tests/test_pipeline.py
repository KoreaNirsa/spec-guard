from __future__ import annotations

from argparse import Namespace
import builtins
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tools.contract_checker import check_contracts
from tools.discovery_engine import answers_from_args, collect_llm_answers, initialize_specs
from tools.readiness_engine import run_readiness_review
from tools.llm_client import (
    DEFAULT_CODEX_TIMEOUT,
    CodexExecClient,
    LLMConfigError,
    LLMSettings,
    _build_codex_prompt,
    _build_prompt,
    _extract_codex_error_text,
    _extract_codex_event_text,
    _iter_response_text_deltas,
    load_llm_settings,
    save_llm_settings,
)
from tools.post_run import (
    apply_spec_revision,
    feature_readiness_reports,
    generate_spec_revision,
    readiness_report_stale_reason,
    render_readiness_summary,
    soften_low_mode_spec_revision,
    validate_spec_revision_intent,
)
from tools.progress import current_progress_activity, progress_activity
from tools.result import CheckResult
from tools.runner import run_pipeline
from tools.spec_validator import validate_feature
from tools.strict_e2e import run_strict_e2e_pipeline
from tools.tdd_generator import generate_tests
import cli.specguard as specguard_cli
import tools.llm_client as llm_client_module
from cli.specguard import _progress_line, _should_offer_follow_up


ROOT = Path(__file__).resolve().parents[1]


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.inputs: list[str] = []
        self.max_output_tokens: list[int] = []

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        self.calls.append(instructions)
        self.inputs.append(input_text)
        self.max_output_tokens.append(max_output_tokens)
        if "feature specification" in instructions.lower():
            return "\n".join([
                "# Feature Specification: Billing Export",
                "",
                "**Status**: Draft",
                "**Source**: `discovery.md`",
                "",
                "## User Scenarios & Testing",
                "",
                "### Primary User Story",
                "",
                "As Finance users, I need exports.",
                "",
                "### Acceptance Scenarios",
                "",
                "1. Given authorized access, exports succeed.",
                "",
                "### Edge Cases",
                "",
                "- Unauthorized access",
                "",
                "## Requirements",
                "",
                "### Functional Requirements",
                "",
                "- The system must export owned billing records.",
                "",
                "## Acceptance Criteria",
                "",
                "- [ ] Authorized users export owned records.",
                "",
                "## Error Cases",
                "",
                "- Unauthorized access",
                "",
                "## Key Entities",
                "",
                "- Billing record",
                "",
                "## Out of Scope",
                "",
                "- Scheduled exports",
                "",
                "## Review & Acceptance Checklist",
                "",
                "- [ ] Requirements are testable.",
                "",
            ])
        if "technical design generator" in instructions.lower():
            return "\n".join([
                "# Technical Design: billing-export",
                "",
                "## Architecture",
                "",
                "- API layer calls an export service.",
                "",
                "## Data Flow",
                "",
                "1. User requests an export.",
                "2. Service checks authorization.",
                "3. Export file is created.",
                "",
                "## State",
                "",
                "- Initial state: requested.",
                "- Terminal state: completed or rejected.",
                "",
                "## Dependencies",
                "",
                "- Billing database.",
                "",
                "## Failure Handling",
                "",
                "- Unauthorized access returns 403.",
                "",
            ])
        return '{"issues":[]}'

    def stream_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500):
        self.calls.append(instructions)
        yield "What problem should the spec solve?"


class FakeRevisionLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        assert "spec refinement assistant" in instructions
        assert "## Acceptance Criteria" in instructions
        assert "Do not rename ## Acceptance Criteria" in instructions
        assert "Readiness Findings" in input_text
        assert max_output_tokens == 3000
        return "\n".join([
            "# Feature Specification: Todo API",
            "",
            "## Problem",
            "",
            "Authenticated users need to create, list, update, and delete their own todo items with explicit owner scope.",
            "",
            "## Requirements",
            "",
            "- The system must allow authenticated users to create todos.",
            "- The system must list only todos owned by the current user.",
            "- The system must allow users to mark their own todos as completed.",
            "- The system must allow users to delete their own todos.",
            "- The system must scope every todo read and write by owner.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Creating a todo stores the current user as owner.",
            "- [ ] Listing todos returns only the current user's todos.",
            "- [ ] Updating another user's todo returns `404 Not Found` or `403 Forbidden`.",
            "- [ ] Deleting a todo records an audit event.",
            "- [ ] Cross-user todo access is rejected.",
            "",
            "## Error Cases",
            "",
            "- Missing title",
            "- Empty title",
            "- Duplicate create request",
            "- Unauthorized request",
            "- Unauthorized todo access",
            "- Delete request for a missing todo",
            "",
        ])


class FencedRevisionLLM(FakeRevisionLLM):
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        return "```markdown\n" + super().generate_text(instructions, input_text, max_output_tokens) + "\n```"


class AcceptanceOnlyRevisionLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        assert "spec refinement assistant" in instructions
        return "\n".join([
            "# Spec: feature",
            "",
            "## Requirements",
            "",
            "- The system must accept valid input.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Valid input succeeds.",
            "- [ ] Valid input returns a success confirmation.",
            "",
            "## Error Cases",
            "",
            "- Invalid input",
            "",
        ])


class OutOfScopePromotionRevisionLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        assert "spec refinement assistant" in instructions
        return "\n".join([
            "# Spec: feature",
            "",
            "## Requirements",
            "",
            "- The system must accept valid input.",
            "- The system must implement billing automation.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Valid input succeeds.",
            "- [ ] Billing automation succeeds.",
            "",
            "## Error Cases",
            "",
            "- Invalid input",
            "",
        ])


class TimeoutRevisionLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        from tools.llm_client import LLMRequestError

        raise LLMRequestError("Codex request timed out.")


class IntentDriftRevisionLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        assert "spec refinement assistant" in instructions
        return "\n".join([
            "# Feature Specification: SSO Provisioning",
            "",
            "## Problem",
            "",
            "Administrators need a full SSO provisioning system.",
            "",
            "## Requirements",
            "",
            "- The system must configure SAML identity providers.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] SAML login succeeds.",
            "",
            "## Error Cases",
            "",
            "- Invalid SAML metadata",
            "",
        ])


class SixMinorReadinessLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        issues = [
            {
                "severity": "Minor",
                "title": f"Minor cleanup {index}",
                "description": "Non-blocking cleanup.",
                "impact": "Small clarity gap.",
                "fix": "Clarify the wording.",
            }
            for index in range(6)
        ]
        return json.dumps({"issues": issues})


class TwoMajorReadinessLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        issues = [
            {
                "severity": "Major",
                "title": f"Implementation decision {index}",
                "description": "A required state transition requires guessing.",
                "impact": "Implementation cannot proceed without an explicit state transition decision.",
                "fix": "Clarify the required state transition.",
            }
            for index in range(2)
        ]
        return json.dumps({"issues": issues})


class CountingReadinessLLM(TwoMajorReadinessLLM):
    def __init__(self, model: str = "gpt-test") -> None:
        self.model = model
        self.calls = 0

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        self.calls += 1
        return super().generate_text(instructions, input_text, max_output_tokens)


class AlternateCountingReadinessLLM(CountingReadinessLLM):
    pass


class ThreeMajorReadinessLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        issues = [
            {
                "severity": "Major",
                "title": f"Missing required behavior {index}",
                "description": "Required behavior is missing and requires guessing.",
                "impact": "Implementation cannot proceed without a required decision.",
                "fix": "Add the missing requirement.",
            }
            for index in range(3)
        ]
        return json.dumps({"issues": issues})


class OptionalMajorReadinessLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        return json.dumps({
            "issues": [{
                "severity": "Major",
                "title": "Optional future extensibility cleanup",
                "description": "This is optional future extensibility and best-practice cleanup.",
                "impact": "Could improve polish later, but does not block implementation.",
                "fix": "Consider this optional cleanup in a future iteration.",
            }]
        })


class LowCalibrationMajorReadinessLLM:
    def __init__(self) -> None:
        self.instructions = ""

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        self.instructions = instructions
        return json.dumps({
            "issues": [
                {
                    "severity": "Major",
                    "title": "Automatic retry queues for failed email delivery",
                    "description": "The spec does not define retries after the email handoff.",
                    "impact": "Implementation can ship the core invite flow without retry queues.",
                    "fix": "Consider adding retry queue behavior in a later iteration.",
                },
                {
                    "severity": "Major",
                    "title": "Bulk invite import is not specified",
                    "description": "The spec covers single invites but not CSV or bulk import.",
                    "impact": "The current feature can still be implemented without bulk import.",
                    "fix": "Document bulk import separately when it enters scope.",
                },
                {
                    "severity": "Major",
                    "title": "Cross-workspace invites from one token are not specified",
                    "description": "The spec only describes invites within the current workspace.",
                    "impact": "The one-workspace invite path remains implementable.",
                    "fix": "Keep cross-workspace invites out of scope or define them separately.",
                },
            ]
        })


class CriticalReadinessLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        return json.dumps({
            "issues": [{
                "severity": "Critical",
                "title": "Authorization contradiction",
                "description": "The spec contradicts authorization requirements.",
                "impact": "Implementation would be unsafe.",
                "fix": "Resolve the authorization contradiction.",
            }]
        })


class CaptureVerificationReadinessLLM:
    def __init__(self) -> None:
        self.instructions = ""
        self.input_text = ""

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        self.instructions = instructions
        self.input_text = input_text
        return '{"issues":[]}'


class CaptureSpecRevisionLLM:
    def __init__(self, revised_spec: str) -> None:
        self.revised_spec = revised_spec
        self.instructions = ""
        self.input_text = ""

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        self.instructions = instructions
        self.input_text = input_text
        return self.revised_spec


class ActivityCaptureSpecRevisionLLM(CaptureSpecRevisionLLM):
    def __init__(self, revised_spec: str) -> None:
        super().__init__(revised_spec)
        self.activity_during_generate: str | None = None

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        self.activity_during_generate = current_progress_activity()
        return super().generate_text(instructions, input_text, max_output_tokens)


class LowModeConvergingWarningLLM:
    def __init__(self) -> None:
        self.revision_inputs: list[str] = []
        self.verification_inputs: list[str] = []

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        lowered = instructions.lower()
        if "technical design generator" in lowered:
            return "\n".join([
                "# Technical Design: feature",
                "",
                "## Architecture",
                "",
                "- API layer calls a service layer with owner-scoped validation.",
                "",
                "## Data Flow",
                "",
                "1. Request arrives.",
                "2. Service validates owner scope and input.",
                "3. Response is returned.",
                "",
                "## State",
                "",
                "- Initial state: request received but not validated.",
                "- Terminal state: completed or rejected.",
                "",
                "## Failure Handling",
                "",
                "- Unauthorized owner access returns 403.",
                "- Invalid input returns 400.",
                "",
            ])
        if "spec refinement assistant" in lowered:
            self.revision_inputs.append(input_text)
            return "\n".join([
                "# Spec: feature",
                "",
                "## Requirements",
                "",
                "- The system must accept valid input.",
                "- The system must scope every request to the authenticated owner.",
                "",
                "## Acceptance Criteria",
                "",
                "- [ ] Valid input succeeds.",
                "- [ ] Cross-owner access is rejected.",
                "",
                "## Error Cases",
                "",
                "- Invalid input",
                "- Unauthorized owner access",
                "",
            ])
        if "verification review board" in lowered:
            self.verification_inputs.append(input_text)
            return json.dumps({
                "issues": [{
                    "severity": "Major",
                    "title": "Contract examples can be more explicit",
                    "description": "The regenerated spec is implementable, but examples could be clearer.",
                    "impact": "Implementation can proceed in low mode.",
                    "fix": "Add richer examples later if desired.",
                }]
            })
        return json.dumps({
            "issues": [
                {
                    "severity": "Critical",
                    "title": "Owner scope missing",
                    "description": "The spec does not state how owner scope is enforced.",
                    "impact": "Implementation would need to guess authorization behavior.",
                    "fix": "Add owner-scoped requirements and acceptance criteria.",
                },
                {
                    "severity": "Major",
                    "title": "Bulk import missing",
                    "description": "Bulk import behavior is not specified.",
                    "impact": "This is useful follow-up but not required for the current implementation.",
                    "fix": "Define bulk import later if it enters scope.",
                },
            ]
        })


class StrictE2EConvergingLLM:
    def __init__(self) -> None:
        self.verification_inputs: list[str] = []

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        lowered = instructions.lower()
        if "technical design generator" in lowered:
            return "\n".join([
                "# Technical Design: feature",
                "",
                "## Architecture",
                "",
                "- API layer calls a service layer with owner-scoped validation.",
                "",
                "## Data Flow",
                "",
                "1. Request arrives.",
                "2. Service validates owner scope and input.",
                "3. Response is returned.",
                "",
                "## State",
                "",
                "- Initial state: request received but not validated.",
                "- Terminal state: completed or rejected.",
                "",
                "## Dependencies",
                "",
                "- Feature database.",
                "",
                "## Failure Handling",
                "",
                "- Unauthorized owner access returns 403.",
                "",
                "## Implementation Blockers",
                "",
                "- None.",
                "",
            ])
        if "spec refinement assistant" in lowered:
            assert "Owner scope missing" in input_text
            return "\n".join([
                "# Spec: feature",
                "",
                "## Requirements",
                "",
                "- The system must accept valid input.",
                "- The system must scope every request to the authenticated owner.",
                "",
                "## Acceptance Criteria",
                "",
                "- [ ] Valid owner-scoped input succeeds.",
                "- [ ] Cross-owner access is rejected.",
                "",
                "## Error Cases",
                "",
                "- Invalid input",
                "- Unauthorized owner access",
                "",
            ])
        if "verification review board" in lowered:
            self.verification_inputs.append(input_text)
            return '{"issues":[]}'
        return json.dumps({
            "issues": [{
                "severity": "Critical",
                "title": "Owner scope missing",
                "description": "The spec does not state how ownership is enforced.",
                "impact": "Implementation would need to guess authorization behavior.",
                "fix": "Add owner-scoped requirements and acceptance criteria.",
            }]
        })


class StrictE2EAlwaysBlockingLLM(StrictE2EConvergingLLM):
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        if "verification review board" in instructions.lower():
            self.verification_inputs.append(input_text)
            return json.dumps({
                "issues": [{
                    "severity": "Critical",
                    "title": "Verification blocker remains",
                    "description": "The regenerated spec still leaves implementation-critical behavior unclear.",
                    "impact": "Implementation would still need to guess.",
                    "fix": "Clarify the remaining behavior before implementation.",
                }]
            })
        return super().generate_text(instructions, input_text, max_output_tokens)


class StrictE2EIntentDriftLLM(StrictE2EConvergingLLM):
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        if "spec refinement assistant" in instructions.lower():
            return IntentDriftRevisionLLM().generate_text(instructions, input_text, max_output_tokens)
        return super().generate_text(instructions, input_text, max_output_tokens)


def copy_example(tmp_path: Path, example: str) -> Path:
    source = ROOT / "examples" / example
    target = tmp_path / example.replace("/", "-")
    shutil.copytree(source, target)
    return target


def _relative_files(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def read_handoff_metadata(feature: Path) -> dict:
    text = feature.joinpath("implementation-output.md").read_text(encoding="utf-8")
    start = text.index("```json") + len("```json")
    end = text.index("```", start)
    return json.loads(text[start:end].strip())


def run_cli_smoke(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(ROOT) if not existing_pythonpath else f"{ROOT}{os.pathsep}{existing_pythonpath}"
    env["CI"] = "true"
    return subprocess.run(
        [sys.executable, "-m", "cli.specguard", *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def write_feature(
    base: Path,
    *,
    placeholder: bool = False,
    bad_contract: bool = False,
    empty_contract: bool = False,
) -> Path:
    feature = base / "feature"
    (feature / "tests").mkdir(parents=True)
    (feature / "contracts").mkdir()

    feature.joinpath("discovery.md").write_text(
        "\n".join([
            "# Discovery: feature",
            "",
            "## Foundation",
            "",
            "- Goal: Validate a small feature safely.",
            "- Constraints: Keep the API simple.",
            "",
            "## Mechanisms",
            "",
            "- Components: API, service, contract.",
            "- Data flow: Request to validation to response.",
            "",
            "## Stress Test",
            "",
            "- First break: Invalid input.",
            "- Edge cases: Missing fields.",
            "",
            "## Synthesis",
            "",
            "- Decision: Build only after validation passes.",
            "- Output: Spec, technical design, tests, and contract.",
            "",
        ]),
        encoding="utf-8",
    )

    requirement = "pending" if placeholder else "The system must accept valid input."
    feature.joinpath("spec.md").write_text(
        "\n".join([
            "# Spec: feature",
            "",
            "## Requirements",
            "",
            f"- {requirement}",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Valid input succeeds.",
            "",
            "## Error Cases",
            "",
            "- Invalid input",
            "",
        ]),
        encoding="utf-8",
    )
    feature.joinpath("technical-design.md").write_text(
        "\n".join([
            "# Technical Design: feature",
            "",
            "## Architecture",
            "",
            "API layer calls a service layer.",
            "",
            "## Data Flow",
            "",
            "1. Request arrives.",
            "2. Service validates input.",
            "3. Response is returned.",
            "",
            "## State",
            "",
            "- Initial state: request received but not validated",
            "- Terminal state: completed",
            "",
            "## Failure Handling",
            "",
            "- Invalid input returns 400.",
            "",
        ]),
        encoding="utf-8",
    )
    feature.joinpath("tests", "feature.test.md").write_text("# Existing tests\n", encoding="utf-8")
    if bad_contract:
        contract = "openapi: 3.1.0\npaths: {}\n"
    elif empty_contract:
        contract = (
            "openapi: 3.1.0\n"
            "info:\n"
            "  title: Feature API\n"
            "  version: 0.1.0\n"
            "paths: {}\n"
        )
    else:
        contract = (
            "openapi: 3.1.0\n"
            "info:\n"
            "  title: Feature API\n"
            "  version: 0.1.0\n"
            "paths:\n"
            "  /feature:\n"
            "    post:\n"
            "      responses:\n"
            "        \"200\":\n"
            "          description: Feature accepted\n"
            "        \"400\":\n"
            "          description: Invalid input\n"
        )
    feature.joinpath("contracts", "openapi.yaml").write_text(contract, encoding="utf-8")
    return feature


def test_example_passes_and_emits_readiness_json(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "example")

    result = run_pipeline(feature)

    assert result.ok
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert payload["blocked"] is False
    assert payload["review_mode"] == "initial"
    assert payload["readiness"]["implementation_ready"] is True
    assert payload["summary"]["critical"] == 0
    assert payload["summary"]["major"] == 0
    assert payload["input"]["artifact_count"] >= 3
    assert payload["input"]["total_characters"] >= payload["input"]["spec_characters"]


def test_ready_pipeline_writes_external_handoff_metadata(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "example")

    result = run_pipeline(feature, force=True)

    output = feature.joinpath("implementation-output.md").read_text(encoding="utf-8")
    metadata = read_handoff_metadata(feature)
    assert result.ok
    assert metadata["implementation_boundary"] == "external_handoff"
    assert metadata["readiness_status"] == "ready_with_warnings"
    assert metadata["implementation_allowed"] is True
    assert "spec.md" in metadata["approved_artifacts"]
    assert "technical-design.md" in metadata["approved_artifacts"]
    assert "contracts/openapi.yaml" in metadata["approved_artifacts"]
    assert "SpecGuard stops at an approved implementation handoff" in output
    assert any("External AI implementation handoff ready" in message for message in result.messages)
    assert any("Performance timings for" in message for message in result.messages)
    assert any(key.endswith(".readiness_review_ms") for key in result.details)
    assert any("external coding agent" in step for step in result.next_steps)


def test_blocked_pipeline_does_not_recommend_ai_implementation(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_pipeline(feature, llm_client=CriticalReadinessLLM())

    assert not result.ok
    assert not feature.joinpath("implementation-output.md").exists()
    assert any("Do not start external AI implementation" in step for step in result.next_steps)
    assert not any("Hand this approved guide" in step for step in result.next_steps)


def test_root_example_matches_packaged_example_resource() -> None:
    root_example = ROOT / "example"
    packaged_example = ROOT / "tools" / "resources" / "example"
    relative_files = _relative_files(root_example)

    assert relative_files == _relative_files(packaged_example)
    for relative_path in relative_files:
        assert root_example.joinpath(relative_path).read_bytes() == packaged_example.joinpath(relative_path).read_bytes()


def test_authored_example_specs_can_be_copied_and_run(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "team-invite"
    shutil.copytree(ROOT / "example", feature)

    result = run_pipeline(feature)

    assert result.ok
    assert feature.joinpath("technical-design.md").exists()
    assert feature.joinpath("tests", "team-invite.test.md").exists()
    assert feature.joinpath("contracts", "openapi.yaml").exists()
    assert feature.joinpath("implementation-output.md").exists()
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert payload["readiness"]["implementation_ready"] is True
    assert payload["summary"]["critical"] == 0
    assert payload["summary"]["major"] == 0


def test_pipeline_regenerates_stale_technical_design(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    design_path = feature / "technical-design.md"
    spec_path = feature / "spec.md"
    old_design = design_path.read_text(encoding="utf-8")
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n- The system must keep the design synchronized with the spec.\n",
        encoding="utf-8",
    )
    old_time = time.time() - 20
    newer_time = time.time() - 10
    os.utime(design_path, (old_time, old_time))
    os.utime(spec_path, (newer_time, newer_time))

    result = run_pipeline(feature)

    regenerated_design = design_path.read_text(encoding="utf-8")
    assert result.ok
    assert regenerated_design != old_design
    assert "keep the design synchronized with the spec" in regenerated_design
    assert design_path.stat().st_mtime > spec_path.stat().st_mtime
    assert any("Generated technical design" in message for message in result.messages)
    assert not any("stale technical design" in step.lower() for step in result.next_steps)


def test_pipeline_can_reuse_stale_technical_design_when_refresh_disabled(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    design_path = feature / "technical-design.md"
    spec_path = feature / "spec.md"
    old_design = design_path.read_text(encoding="utf-8")
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n- The system must add an acceptance-only clarification.\n",
        encoding="utf-8",
    )
    os.utime(design_path, (time.time() - 20, time.time() - 20))
    os.utime(spec_path, (time.time() - 10, time.time() - 10))
    llm = FakeLLM()

    result = run_pipeline(
        feature,
        llm_client=llm,
        force=True,
        review_mode="verification",
        refresh_technical_design=False,
    )

    assert result.ok
    assert design_path.read_text(encoding="utf-8") == old_design
    assert not any("technical design generator" in call.lower() for call in llm.calls)
    assert any("Reused technical design" in message for message in result.messages)


def test_cli_init_smoke_generates_spec_package(tmp_path: Path) -> None:
    completed = run_cli_smoke(
        tmp_path,
        "init",
        "billing-export",
        "--non-interactive",
        "--no-llm",
        "--problem",
        "Finance users need scoped billing exports.",
        "--users",
        "Finance operators",
        "--outcomes",
        "Auditable scoped CSV exports",
        "--constraints",
        "CSV only; tenant isolation required",
        "--flows",
        "Request export, authorize tenant, create CSV, audit result",
        "--data",
        "Billing records, tenant, user, export file",
        "--dependencies",
        "Billing database and object storage",
        "--risks",
        "Cross-tenant data exposure",
        "--out-of-scope",
        "Scheduled exports",
        "--acceptance",
        "Authorized users can export only owned tenant records",
    )

    feature = tmp_path / "specs" / "billing-export"
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "[PASS] SpecGuard Discovery" in completed.stdout
    assert "Generating spec draft completed" in completed.stdout
    assert feature.joinpath("discovery.md").exists()
    assert feature.joinpath("spec.md").exists()
    assert feature.joinpath("plan.md").exists()
    assert feature.joinpath("tasks.md").exists()
    assert feature.joinpath("constitution.md").exists()
    assert feature.joinpath("checklists", "spec-readiness.md").exists()


def test_cli_run_smoke_executes_pipeline_from_authored_specs(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "team-invite"
    shutil.copytree(ROOT / "example", feature)

    completed = run_cli_smoke(
        tmp_path,
        "run",
        "specs/team-invite",
        "--no-llm",
        "--no-follow-up",
        "--force",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "[PASS] SpecGuard pipeline" in completed.stdout
    assert "Running pipeline completed" in completed.stdout
    assert "External AI implementation handoff ready" in completed.stdout
    assert feature.joinpath("technical-design.md").exists()
    assert feature.joinpath("tests", "team-invite.test.md").exists()
    assert feature.joinpath("contracts", "openapi.yaml").exists()
    assert feature.joinpath("implementation-output.md").exists()
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert payload["readiness"]["implementation_ready"] is True


def test_cli_example_copy_points_to_default_low_mode_run(tmp_path: Path) -> None:
    completed = run_cli_smoke(tmp_path, "example", "copy", "team-invite", "--force")
    expected_run = f"Run: specguard run {tmp_path / 'specs' / 'team-invite'} --no-follow-up"

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "[PASS] Copied authored example specs." in completed.stdout
    assert expected_run in completed.stdout
    assert "Use --no-llm only for deterministic local smoke checks" in completed.stdout
    assert (tmp_path / "specs" / "team-invite" / "spec.md").exists()


def test_discovery_init_generates_feature_spec(tmp_path: Path) -> None:
    result = initialize_specs(tmp_path, {
        "feature_names": "billing-export",
        "problem": "Export billing records safely.",
        "users": "Finance users",
        "outcomes": "Exports are scoped and auditable",
        "constraints": "CSV only for the first pass",
        "flows": "Request export, validate ownership, create file",
        "data": "Billing record, owner, export file",
        "dependencies": "Billing database",
        "risks": "Cross-tenant export",
        "out_of_scope": "Scheduled exports",
        "acceptance": "An authorized user can export only owned records",
    })

    feature = tmp_path / "specs" / "billing-export"

    assert result.ok
    assert feature.joinpath("discovery.md").exists()
    assert feature.joinpath("spec.md").exists()
    assert feature.joinpath("plan.md").exists()
    assert feature.joinpath("tasks.md").exists()
    assert feature.joinpath("constitution.md").exists()
    assert feature.joinpath("checklists", "spec-readiness.md").exists()
    assert "User Scenarios & Testing" in feature.joinpath("spec.md").read_text(encoding="utf-8")
    assert "Quality Gates" in feature.joinpath("plan.md").read_text(encoding="utf-8")
    assert "Spec Package" in feature.joinpath("tasks.md").read_text(encoding="utf-8")
    assert "Spec-first" in feature.joinpath("constitution.md").read_text(encoding="utf-8")
    assert "Critical findings: 0" in feature.joinpath("checklists", "spec-readiness.md").read_text(encoding="utf-8")


def test_discovery_init_can_use_llm_for_spec(tmp_path: Path) -> None:
    llm = FakeLLM()
    result = initialize_specs(tmp_path, {
        "feature_names": "billing-export",
        "problem": "Export billing records safely.",
        "users": "Finance users",
        "outcomes": "Exports are scoped and auditable",
        "constraints": "CSV only for the first pass",
        "flows": "Request export, validate ownership, create file",
        "data": "Billing record, owner, export file",
        "dependencies": "Billing database",
        "risks": "Cross-tenant export",
        "out_of_scope": "Scheduled exports",
        "acceptance": "An authorized user can export only owned records",
    }, llm_client=llm)

    spec = tmp_path / "specs" / "billing-export" / "spec.md"

    assert result.ok
    assert "Billing Export" in spec.read_text(encoding="utf-8")
    assert any("feature specification" in call.lower() for call in llm.calls)
    assert any("plan.md" in call and "tasks.md" in call and "constitution.md" in call for call in llm.calls)


def test_run_blocks_unedited_default_init_draft(tmp_path: Path) -> None:
    answers = answers_from_args(Namespace(feature="my-feature"))
    init_result = initialize_specs(tmp_path, answers)
    feature = tmp_path / "specs" / "my-feature"

    result = run_pipeline(feature)

    assert init_result.ok
    assert not result.ok
    assert not feature.joinpath("technical-design.md").exists()
    assert any("mostly default init draft" in message for message in result.messages)
    assert any("Edit the generated spec package" in step for step in result.next_steps)


def test_llm_discovery_uses_fast_guided_questions_for_conversation(tmp_path: Path) -> None:
    llm = FakeLLM()
    inputs = iter(["Finance users need scoped exports.", "done"])
    output: list[str] = []
    args = Namespace(feature="billing-export")

    answers = collect_llm_answers(
        args,
        llm,
        max_turns=3,
        input_func=lambda _prompt: next(inputs),
        write_func=output.append,
    )
    result = initialize_specs(tmp_path, answers, llm_client=llm)

    discovery = tmp_path / "specs" / "billing-export" / "discovery.md"
    assert result.ok
    assert "Finance users need scoped exports." in answers["conversation"]
    assert answers["problem"] == "Finance users need scoped exports."
    assert "LLM Discovery Conversation" in discovery.read_text(encoding="utf-8")
    assert "Questions are shown instantly" in "".join(output)
    assert "What problem should these specs solve?" in "".join(output)
    assert "Empty answer recorded" not in "".join(output)
    assert any("Review and refine generated specs under specs/" in step for step in result.next_steps)
    assert any("specguard run specs" in step for step in result.next_steps)


def test_llm_discovery_empty_answer_accepts_visible_default() -> None:
    llm = FakeLLM()
    output: list[str] = []
    args = Namespace(feature="billing-export")

    answers = collect_llm_answers(
        args,
        llm,
        max_turns=1,
        input_func=lambda _prompt: "",
        write_func=output.append,
    )

    rendered = "".join(output)
    assert answers["problem"] == "Capture the intended behavior before implementation."
    assert "Default: Capture the intended behavior before implementation." in rendered
    assert "> Using default: Capture the intended behavior before implementation." in rendered
    assert "Empty answer recorded" not in rendered


def test_response_stream_parser_reads_output_text_delta() -> None:
    lines = [
        b"event: response.output_text.delta\n",
        b'data: {"type":"response.output_text.delta","delta":"Hello"}\n',
        b"\n",
        b'data: {"type":"response.output_text.delta","delta":" world"}\n',
        b"\n",
        b"data: [DONE]\n",
        b"\n",
    ]

    assert "".join(_iter_response_text_deltas(lines)) == "Hello world"


def test_llm_settings_round_trip_openai_mode(tmp_path: Path) -> None:
    save_llm_settings(tmp_path, LLMSettings(
        mode="openai",
        model="gpt-5.1",
        api_key="local-test-key",
        api_key_env="OPENAI_API_KEY",
    ))

    settings = load_llm_settings(tmp_path)

    assert settings is not None
    assert settings.mode == "openai"
    assert settings.model == "gpt-5.1"
    assert settings.api_key == "local-test-key"


def test_codex_settings_raise_legacy_timeout_floor(tmp_path: Path) -> None:
    save_llm_settings(tmp_path, LLMSettings(mode="codex", model="gpt-5.4", timeout=60))

    settings = load_llm_settings(tmp_path)

    assert settings is not None
    assert settings.mode == "codex"
    assert settings.timeout == DEFAULT_CODEX_TIMEOUT


def test_codex_settings_preserve_explicit_non_legacy_timeout(tmp_path: Path) -> None:
    save_llm_settings(tmp_path, LLMSettings(mode="codex", model="gpt-5.4", timeout=300))

    settings = load_llm_settings(tmp_path)

    assert settings is not None
    assert settings.mode == "codex"
    assert settings.timeout == 300


def test_codex_settings_round_trip_execution_tuning(tmp_path: Path) -> None:
    save_llm_settings(tmp_path, LLMSettings(
        mode="codex",
        model="gpt-5.4",
        timeout=300,
        codex_profile="specguard-fast",
        codex_reasoning_effort="medium",
    ))

    settings = load_llm_settings(tmp_path)

    assert settings is not None
    assert settings.codex_profile == "specguard-fast"
    assert settings.codex_reasoning_effort == "medium"


def test_codex_prompt_constrains_provider_to_supplied_input() -> None:
    prompt = _build_codex_prompt("Return JSON.", "# Artifact: spec.md\n\nBody", 2500)

    assert "Use only the Input section below as the review context." in prompt
    assert "Do not inspect the repository, read files, or execute shell commands." in prompt
    assert "# Input" in prompt
    assert "# Artifact: spec.md" in prompt


def test_codex_exec_uses_ephemeral_read_only_command(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(llm_client_module, "_codex_supports_ephemeral", lambda _command: True)
    client = CodexExecClient(LLMSettings(mode="codex", codex_command=sys.executable), root=tmp_path)

    command = client._base_command()

    assert "--sandbox" in command
    assert "read-only" in command
    assert "--ephemeral" in command


def test_codex_exec_omits_ephemeral_when_cli_does_not_support_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(llm_client_module, "_codex_supports_ephemeral", lambda _command: False)
    client = CodexExecClient(LLMSettings(mode="codex", codex_command=sys.executable), root=tmp_path)

    command = client._base_command()

    assert "--ephemeral" not in command
    assert "--color" in command


def test_codex_exec_includes_reasoning_effort_when_supported(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(llm_client_module, "_codex_supports_ephemeral", lambda _command: False)
    monkeypatch.setattr(llm_client_module, "_codex_supports_reasoning_effort", lambda _command: True)
    client = CodexExecClient(
        LLMSettings(mode="codex", codex_command=sys.executable, codex_reasoning_effort="medium"),
        root=tmp_path,
    )

    command = client._base_command()

    assert "--reasoning-effort" in command
    assert command[command.index("--reasoning-effort") + 1] == "medium"


def test_codex_exec_rejects_reasoning_effort_when_unsupported(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(llm_client_module, "_codex_supports_reasoning_effort", lambda _command: False)

    with pytest.raises(LLMConfigError, match="does not support `--reasoning-effort`"):
        CodexExecClient(
            LLMSettings(mode="codex", codex_command=sys.executable, codex_reasoning_effort="medium"),
            root=tmp_path,
        )


def test_codex_setup_defaults_model_and_skips_missing_login(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(specguard_cli, "ROOT", tmp_path)
    monkeypatch.setattr(specguard_cli, "codex_available", lambda _command="codex": True)
    monkeypatch.setattr(specguard_cli, "_resolve_local_command", lambda _command: "missing-codex")
    monkeypatch.setattr("builtins.input", lambda prompt: "y" if "codex login" in prompt else "")

    def missing_command(*_args, **_kwargs):
        raise FileNotFoundError("missing-codex")

    monkeypatch.setattr(specguard_cli.subprocess, "run", missing_command)

    exit_code = specguard_cli._setup_llm(Namespace(
        mode="codex",
        model=None,
        timeout=None,
        codex_command="codex",
        codex_profile=None,
        codex_reasoning_effort=None,
        skip_login=False,
    ))

    settings = load_llm_settings(tmp_path)
    rendered = capsys.readouterr().out
    assert exit_code == 0
    assert settings is not None
    assert settings.mode == "codex"
    assert settings.model == "gpt-5.4"
    assert settings.timeout == DEFAULT_CODEX_TIMEOUT
    assert "could not be launched" in rendered
    assert "provider config is still saved" in rendered


def test_codex_setup_saves_and_status_reports_execution_tuning(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(specguard_cli, "ROOT", tmp_path)
    monkeypatch.setattr(specguard_cli, "codex_available", lambda _command="codex": True)

    exit_code = specguard_cli._setup_llm(Namespace(
        mode="codex",
        model="gpt-5.4",
        timeout=300,
        codex_command="codex",
        codex_profile="specguard-fast",
        codex_reasoning_effort="medium",
        skip_login=True,
    ))
    status_code = specguard_cli.auth(Namespace(auth_command="status"))

    settings = load_llm_settings(tmp_path)
    rendered = capsys.readouterr().out
    assert exit_code == 0
    assert status_code == 0
    assert settings is not None
    assert settings.codex_profile == "specguard-fast"
    assert settings.codex_reasoning_effort == "medium"
    assert "Codex profile: specguard-fast" in rendered
    assert "Codex reasoning effort: medium" in rendered


def test_codex_json_event_parser_reads_deltas_only() -> None:
    delta = '{"type":"agent_message_delta","delta":"Question?"}'
    final = '{"type":"agent_message","message":"Question?"}'

    assert _extract_codex_event_text(delta, delta_only=True) == "Question?"
    assert _extract_codex_event_text(final, delta_only=True) == ""
    assert _extract_codex_event_text(final) == "Question?"


def test_codex_json_event_parser_reads_error_message() -> None:
    line = (
        '{"type":"error","message":"{\\"type\\":\\"error\\",\\"status\\":400,'
        '\\"error\\":{\\"type\\":\\"invalid_request_error\\",'
        '\\"message\\":\\"The model requires a newer Codex version.\\"}}"}'
    )

    assert _extract_codex_error_text(line) == "The model requires a newer Codex version."


def test_codex_error_parser_reads_nested_raw_json_string() -> None:
    raw = (
        '{"type":"error","status":400,"error":{"type":"invalid_request_error",'
        '"message":"The selected model requires a newer Codex version."}}'
    )

    assert _extract_codex_error_text(f'ERROR: {raw}') == "The selected model requires a newer Codex version."


def test_codex_error_parser_reads_escaped_raw_json_string() -> None:
    raw = (
        r'{\"type\":\"error\",\"status\":400,\"error\":{\"type\":\"invalid_request_error\",'
        r'\"message\":\"The escaped model error is readable.\"}}'
    )

    assert _extract_codex_error_text(f"ERROR: {raw}") == "The escaped model error is readable."


def test_run_generates_spec_derived_contract_from_spec_basis(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "profile-update"
    feature.mkdir(parents=True)
    feature.joinpath("discovery.md").write_text(
        "\n".join([
            "# Discovery: profile-update",
            "",
            "## Foundation",
            "",
            "- Goal: Update profile data safely.",
            "",
            "## Mechanisms",
            "",
            "- Components: API, profile service, profile store.",
            "",
            "## Stress Test",
            "",
            "- Failure: Invalid profile data is rejected.",
            "",
            "## Synthesis",
            "",
            "- Decision: Proceed after validation.",
            "",
        ]),
        encoding="utf-8",
    )
    feature.joinpath("spec.md").write_text(
        "\n".join([
            "# Feature Specification: profile-update",
            "",
            "## Requirements",
            "",
            "- The system must update valid profile fields.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Valid profile updates are saved.",
            "",
            "## Error Cases",
            "",
            "- Invalid profile data",
            "",
        ]),
        encoding="utf-8",
    )

    result = run_pipeline(feature)

    assert result.ok
    assert feature.joinpath("technical-design.md").exists()
    assert feature.joinpath("tests", "profile-update.test.md").exists()
    contract = feature.joinpath("contracts", "openapi.yaml")
    assert contract.exists()
    contract_text = contract.read_text(encoding="utf-8")
    assert "paths:" in contract_text
    assert "/profile-update:" in contract_text
    assert "x-specguard-coverage:" in contract_text
    assert "Valid profile updates are saved." in contract_text
    assert "Invalid profile data" in contract_text
    assert "requestBody:" in contract_text
    assert "ErrorResponse:" in contract_text
    assert feature.joinpath("implementation-output.md").exists()


def test_run_can_use_llm_for_design_and_review(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "billing-export"
    feature.mkdir(parents=True)
    feature.joinpath("discovery.md").write_text(
        "\n".join([
            "# Discovery: billing-export",
            "",
            "## Foundation",
            "",
            "- Goal: Export billing records.",
            "",
            "## Mechanisms",
            "",
            "- Components: API, export service.",
            "",
            "## Stress Test",
            "",
            "- Failure: Unauthorized export.",
            "",
            "## Synthesis",
            "",
            "- Decision: Validate before implementation.",
            "",
        ]),
        encoding="utf-8",
    )
    feature.joinpath("spec.md").write_text(
        "\n".join([
            "# Feature Specification: billing-export",
            "",
            "## Requirements",
            "",
            "- The system must export owned billing records.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Authorized users export owned records.",
            "",
            "## Error Cases",
            "",
            "- Unauthorized access",
            "",
        ]),
        encoding="utf-8",
    )
    feature.joinpath("plan.md").write_text(
        "# Plan\n\n" + "\n".join(f"- Implementation planning detail {index}" for index in range(200)),
        encoding="utf-8",
    )
    feature.joinpath("contracts").mkdir()
    feature.joinpath("contracts", "openapi.yaml").write_text(
        "\n".join([
            "openapi: 3.1.0",
            "info:",
            "  title: Billing Export API",
            "  version: 0.1.0",
            "paths:",
            "  /billing-exports:",
            "    post:",
            "      responses:",
            "        \"200\":",
            "          description: Billing export created",
            "        \"403\":",
            "          description: Unauthorized export",
            "",
        ]),
        encoding="utf-8",
    )
    llm = FakeLLM()

    result = run_pipeline(feature, llm_client=llm)

    assert result.ok
    assert "API layer calls an export service" in feature.joinpath("technical-design.md").read_text(encoding="utf-8")
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert payload["blocked"] is False
    assert any("technical design generator" in call.lower() for call in llm.calls)
    assert any("low-mode technical design generator" in call for call in llm.calls)
    assert any("minimum implementation safety gating" in call for call in llm.calls)
    assert not any("full SpecGuard spec package" in call for call in llm.calls)
    assert payload["review_input"]["mode"] == "low_compact"
    assert payload["review_input"]["total_characters"] < payload["review_input"]["source_total_characters"]
    assert 1800 in llm.max_output_tokens
    assert 1400 in llm.max_output_tokens
    assert not any("safest explicit design assumption" in call for call in llm.calls)


def test_medium_review_level_uses_full_llm_prompt_context(tmp_path: Path) -> None:
    result = initialize_specs(tmp_path, {
        "feature_names": "billing-export",
        "problem": "Export billing records safely.",
        "users": "Finance users",
        "outcomes": "Exports are scoped and auditable",
        "constraints": "CSV only for the first pass",
        "flows": "Request export, validate ownership, create file",
        "data": "Billing record, owner, export file",
        "dependencies": "Billing database",
        "risks": "Cross-tenant export",
        "out_of_scope": "Scheduled exports",
        "acceptance": "An authorized user can export only owned records",
    })
    assert result.ok
    feature = tmp_path / "specs" / "billing-export"
    llm = FakeLLM()

    pipeline = run_pipeline(feature, llm_client=llm, review_level="medium")

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert pipeline.ok
    assert payload["review_level"] == "medium"
    assert payload["review_input"]["mode"] == "full"
    assert any("full SpecGuard spec package" in call for call in llm.calls)
    assert any("Do not resolve contradictions by inventing behavior" in call for call in llm.calls)
    assert any("mark the item as a blocker" in call for call in llm.calls)
    assert 3000 in llm.max_output_tokens
    assert 2500 in llm.max_output_tokens


def test_risk_todo_example_is_ready_with_warnings(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")

    result = run_pipeline(feature)

    assert result.ok
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert payload["blocked"] is False
    assert payload["readiness"]["implementation_ready"] is True
    assert payload["readiness"]["status"] == "ready_with_warnings"
    assert payload["summary"]["critical"] == 0
    assert payload["summary"]["major"] == 1
    assert "Delete semantics are unsafe" in {issue["title"] for issue in payload["issues"]}
    assert any("Review warning findings" in step for step in result.next_steps)
    assert feature.joinpath("implementation-output.md").exists()
    metadata = read_handoff_metadata(feature)
    assert metadata["readiness_status"] == "ready_with_warnings"
    assert metadata["implementation_allowed"] is True
    assert metadata["readiness_summary"]["major"] == 1
    assert metadata["readiness_warnings"][0]["title"] == "Delete semantics are unsafe"


def test_readiness_reviews_full_spec_package_artifacts(tmp_path: Path) -> None:
    result = initialize_specs(tmp_path, {
        "feature_names": "billing-export",
        "problem": "Export billing records safely.",
        "users": "Finance users",
        "outcomes": "Exports are scoped and auditable",
        "constraints": "CSV only for the first pass",
        "flows": "Request export, validate ownership, create file",
        "data": "Billing record, owner, export file",
        "dependencies": "Billing database",
        "risks": "Cross-tenant export",
        "out_of_scope": "Scheduled exports",
        "acceptance": "An authorized user can export only owned records",
    })
    assert result.ok
    feature = tmp_path / "specs" / "billing-export"
    feature.joinpath("contracts").mkdir()
    feature.joinpath("contracts", "openapi.yaml").write_text(
        "\n".join([
            "openapi: 3.1.0",
            "info:",
            "  title: Billing Export API",
            "  version: 0.1.0",
            "paths:",
            "  /billing-exports:",
            "    post:",
            "      responses:",
            "        \"200\":",
            "          description: Billing export created",
            "        \"403\":",
            "          description: Unauthorized export",
            "",
        ]),
        encoding="utf-8",
    )

    pipeline = run_pipeline(feature)

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    reviewed_paths = {artifact["path"] for artifact in payload["input"]["artifacts"]}
    assert pipeline.ok
    assert {"discovery.md", "spec.md", "plan.md", "tasks.md", "constitution.md", "checklists/spec-readiness.md", "technical-design.md"} <= reviewed_paths
    assert "generated-artifacts.md" in reviewed_paths
    assert {"contracts/openapi.yaml", "tests/billing-export.test.md"}.isdisjoint(reviewed_paths)
    assert any("SpecGuard Review input size" in message for message in pipeline.messages)
    assert payload["input"]["artifact_count"] == len(payload["input"]["artifacts"])
    assert payload["input"]["total_characters"] == sum(artifact["characters"] for artifact in payload["input"]["artifacts"])


def test_codex_prompt_constrains_repository_exploration() -> None:
    prompt = _build_prompt("Review this.", "Only this input.", 500)

    assert "Use only the supplied input below" in prompt
    assert "Do not inspect local repository files" in prompt
    assert "Maximum output tokens: 500" in prompt


def test_readiness_excludes_current_and_legacy_generated_review_artifacts(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    stale_generated_text = "# Generated report\n\nStale todo delete finding from an older run.\n"
    feature.joinpath("readiness-review.md").write_text(stale_generated_text, encoding="utf-8")
    feature.joinpath("implementation-output.md").write_text(stale_generated_text, encoding="utf-8")
    feature.joinpath("spec.proposed.md").write_text(stale_generated_text, encoding="utf-8")
    feature.joinpath("grill.md").write_text(stale_generated_text, encoding="utf-8")
    feature.joinpath("grill.json").write_text('{"issues": ["stale todo delete finding"]}\n', encoding="utf-8")

    result = run_readiness_review(feature)

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    reviewed_paths = {artifact["path"] for artifact in payload["input"]["artifacts"]}
    assert result.ok
    assert {"readiness-review.md", "implementation-output.md", "spec.proposed.md", "grill.md", "grill.json"}.isdisjoint(reviewed_paths)
    assert payload["summary"]["critical"] == 0
    assert payload["summary"]["major"] == 0


def test_readiness_reports_ready_with_warnings_for_six_minor_findings(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_readiness_review(feature, llm_client=SixMinorReadinessLLM())

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert result.ok
    assert payload["blocked"] is False
    assert payload["readiness"]["implementation_ready"] is True
    assert payload["readiness"]["status"] == "ready_with_warnings"
    assert payload["summary"]["minor"] == 6
    assert any("[READY_WITH_WARNINGS]" in message for message in result.messages)


def test_readiness_reports_ready_with_warnings_for_two_major_findings(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_readiness_review(feature, llm_client=TwoMajorReadinessLLM())

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert result.ok
    assert payload["blocked"] is False
    assert payload["review_level"] == "low"
    assert payload["readiness"]["status"] == "ready_with_warnings"
    assert payload["summary"]["major"] == 2


def test_readiness_defaults_to_low_review_level(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_readiness_review(feature, llm_client=ThreeMajorReadinessLLM())

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert result.ok
    assert payload["blocked"] is False
    assert payload["review_level"] == "low"
    assert payload["readiness"]["implementation_ready"] is True
    assert payload["readiness"]["status"] == "ready_with_warnings"
    assert payload["readiness"]["criteria"]["review_level"] == "low"
    assert payload["readiness"]["criteria"]["ready_with_warnings"]["major_max"] is None
    assert payload["summary"]["major"] == 3
    assert any("SpecGuard Review level: low" in message for message in result.messages)


def test_readiness_review_reuses_cached_llm_report_for_unchanged_artifacts(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    llm = CountingReadinessLLM()

    first = run_readiness_review(feature, llm_client=llm)
    second = run_readiness_review(feature, llm_client=llm)

    cache_root = tmp_path / ".specguard" / "readiness-cache" / "feature"
    cache_dirs = [path for path in cache_root.iterdir() if path.is_dir()]
    assert first.ok
    assert second.ok
    assert llm.calls == 1
    assert first.details["cache_hit"] is False
    assert second.details["cache_hit"] is True
    assert first.details["cache_miss_reason"] == "no cache entry for this feature"
    assert any("SpecGuard Review cache check: miss" in message for message in first.messages)
    assert any("no cache entry for this feature" in message for message in first.messages)
    assert any("SpecGuard Review cache check: hit" in message for message in second.messages)
    assert any("SpecGuard Review cache hit" in message for message in second.messages)
    first_payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert first_payload["cache"]["hit"] is True
    assert first_payload["cache"]["cache_key_prefix"] == second.details["cache_key"][:12]
    assert "input_fingerprint" in first_payload["cache"]
    assert cache_dirs
    assert cache_dirs[0].joinpath("readiness-review.md").exists()
    assert cache_dirs[0].joinpath("readiness-review.json").exists()


def test_readiness_review_cache_invalidates_when_artifact_changes(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    llm = CountingReadinessLLM()

    run_readiness_review(feature, llm_client=llm)
    feature.joinpath("spec.md").write_text(
        feature.joinpath("spec.md").read_text(encoding="utf-8") + "\n- The system must reject duplicate requests.\n",
        encoding="utf-8",
    )
    result = run_readiness_review(feature, llm_client=llm)

    assert result.details["cache_hit"] is False
    assert result.details["cache_miss_reason"] == "artifact hash changed: spec.md"
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert payload["cache"]["miss_reason"] == "artifact hash changed: spec.md"
    assert llm.calls == 2


def test_readiness_review_cache_ignores_generated_artifact_content_changes(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    llm = CountingReadinessLLM()

    run_readiness_review(feature, llm_client=llm)
    feature.joinpath("tests", "feature.test.md").write_text(
        "# Existing tests\n\n- Generated test details changed after review.\n",
        encoding="utf-8",
    )
    feature.joinpath("contracts", "openapi.yaml").write_text(
        feature.joinpath("contracts", "openapi.yaml").read_text(encoding="utf-8")
        + "\ncomponents:\n  schemas:\n    Extra:\n      type: object\n",
        encoding="utf-8",
    )
    result = run_readiness_review(feature, llm_client=llm)

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert result.details["cache_hit"] is True
    assert payload["cache"]["hit"] is True
    assert llm.calls == 1


def test_readiness_review_cache_invalidates_by_provider_model_and_review_mode(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    initial = CountingReadinessLLM(model="gpt-a")
    different_model = CountingReadinessLLM(model="gpt-b")
    different_provider = AlternateCountingReadinessLLM(model="gpt-a")
    verification = CountingReadinessLLM(model="gpt-a")
    medium = CountingReadinessLLM(model="gpt-a")

    run_readiness_review(feature, llm_client=initial)
    model_result = run_readiness_review(feature, llm_client=different_model)
    provider_result = run_readiness_review(feature, llm_client=different_provider)
    verification_result = run_readiness_review(feature, llm_client=verification, review_mode="verification")
    medium_result = run_readiness_review(feature, llm_client=medium, review_level="medium")

    assert initial.calls == 1
    assert different_model.calls == 1
    assert different_provider.calls == 1
    assert verification.calls == 1
    assert medium.calls == 1
    assert model_result.details["cache_hit"] is False
    assert model_result.details["cache_miss_reason"] == "model changed: gpt-a -> gpt-b"
    assert provider_result.details["cache_hit"] is False
    assert provider_result.details["cache_miss_reason"] == "provider changed: CountingReadinessLLM -> AlternateCountingReadinessLLM"
    assert verification_result.details["cache_hit"] is False
    assert verification_result.details["cache_miss_reason"] == "review mode changed: initial -> verification"
    assert medium_result.details["cache_hit"] is False
    assert medium_result.details["cache_miss_reason"] == "review level changed: low -> medium"
    assert medium_result.details["review_level"] == "medium"


def test_readiness_review_records_llm_call_timing(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_readiness_review(feature, llm_client=TwoMajorReadinessLLM())

    assert result.details["initial_llm_review_ms"] >= 0
    assert any("LLM initial SpecGuard Review call" in message for message in result.messages)
    assert any("TwoMajorReadinessLLM" in message for message in result.messages)


def test_readiness_blocks_three_major_findings(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_readiness_review(feature, llm_client=ThreeMajorReadinessLLM(), review_level="medium")

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert not result.ok
    assert payload["blocked"] is True
    assert payload["review_level"] == "medium"
    assert payload["readiness"]["implementation_ready"] is False
    assert payload["readiness"]["status"] == "not_ready"
    assert payload["summary"]["major"] == 3
    assert any("[NOT READY]" in message for message in result.messages)


def test_readiness_blocks_critical_findings(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_readiness_review(feature, llm_client=CriticalReadinessLLM())

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert not result.ok
    assert payload["blocked"] is True
    assert payload["readiness"]["status"] == "not_ready"
    assert payload["summary"]["critical"] == 1


def test_readiness_downgrades_non_blocking_major_findings(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_readiness_review(feature, llm_client=OptionalMajorReadinessLLM())

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert result.ok
    assert payload["readiness"]["status"] == "ready_with_warnings"
    assert payload["summary"]["major"] == 0
    assert payload["summary"]["minor"] == 1
    assert payload["issues"][0]["severity"] == "Minor"


def test_low_review_level_uses_minimum_safety_gate_prompt_and_calibration(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    llm = LowCalibrationMajorReadinessLLM()

    result = run_readiness_review(feature, llm_client=llm)

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    report = feature.joinpath("readiness-review.md").read_text(encoding="utf-8")
    assert result.ok
    assert payload["review_level"] == "low"
    assert payload["readiness"]["status"] == "ready_with_warnings"
    assert payload["summary"]["major"] == 0
    assert payload["summary"]["minor"] == 3
    assert all(issue["severity"] == "Minor" for issue in payload["issues"])
    assert "minimum safety gate" in llm.instructions
    assert "Do not perform a broad architecture" in llm.instructions
    assert "Warnings: Major=0, Minor=3 (non-blocking in low mode)" in report
    assert any("SpecGuard low gate: 0 blocker(s); 3 warning finding(s)" in message for message in result.messages)


def test_medium_review_level_preserves_deeper_major_calibration(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    llm = LowCalibrationMajorReadinessLLM()

    result = run_readiness_review(feature, llm_client=llm, review_level="medium")

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert not result.ok
    assert payload["review_level"] == "medium"
    assert payload["readiness"]["status"] == "not_ready"
    assert payload["summary"]["major"] == 3
    assert payload["summary"]["minor"] == 0
    assert "break it before Codex" in llm.instructions


def test_readiness_verification_mode_uses_previous_findings(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature, review_level="medium")
    llm = CaptureVerificationReadinessLLM()

    result = run_readiness_review(feature, llm_client=llm, review_mode="verification", review_level="medium")

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert result.ok
    assert payload["review_mode"] == "verification"
    assert payload["review_input"]["mode"] == "delta"
    assert payload["review_input"]["total_characters"] < payload["input"]["total_characters"]
    assert "Verification Review board" in llm.instructions
    assert "Previous SpecGuard Review Findings" in llm.input_text
    assert "Verification Review Delta Evidence" in llm.input_text
    assert "Delete semantics are unsafe" in llm.input_text


def test_low_verification_mode_uses_previous_critical_backlog_only(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    for name in ("spec.md", "technical-design.md"):
        path = feature / name
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\nOwner scope missing closure: owner scope is now required for authorization behavior.\n",
            encoding="utf-8",
        )
    feature.joinpath("readiness-review.json").write_text(
        json.dumps({
            "review_level": "low",
            "blocked": True,
            "readiness": {"status": "not_ready", "implementation_ready": False},
            "summary": {"critical": 1, "major": 1, "minor": 0},
            "issues": [
                {
                    "severity": "Critical",
                    "title": "Owner scope missing",
                    "description": "The spec does not state how owner scope is enforced.",
                    "impact": "Implementation would need to guess authorization behavior.",
                    "fix": "Add owner-scoped requirements and acceptance criteria.",
                },
                {
                    "severity": "Major",
                    "title": "Bulk import missing",
                    "description": "Bulk import behavior is not specified.",
                    "impact": "This warning should not drive low-mode verification.",
                    "fix": "Define bulk import later if it enters scope.",
                },
            ],
        }),
        encoding="utf-8",
    )
    llm = CaptureVerificationReadinessLLM()

    result = run_readiness_review(feature, llm_client=llm, review_mode="verification", review_level="low")

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert result.ok
    assert payload["review_input"]["mode"] == "delta"
    assert payload["review_input"]["previous_finding_count"] == 1
    assert "Use these previous Critical blockers as the verification backlog." in llm.input_text
    assert "Owner scope missing" in llm.input_text
    assert "Bulk import missing" not in llm.input_text


def test_readiness_verification_mode_falls_back_without_previous_findings(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    llm = CaptureVerificationReadinessLLM()

    result = run_readiness_review(feature, llm_client=llm, review_mode="verification")

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert result.ok
    assert payload["review_input"]["mode"] == "full"
    assert payload["review_input"]["fallback_reason"] == "missing previous findings"
    assert "Current Spec Package Artifacts" in llm.input_text


def test_strict_e2e_converges_after_spec_regeneration(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    feature.joinpath("tests", "test_feature.py").write_text("def test_owner_scope_contract():\n    assert True\n", encoding="utf-8")
    llm = StrictE2EConvergingLLM()

    result = run_strict_e2e_pipeline(feature, llm, max_iterations=2)

    trace = json.loads(feature.joinpath("strict-e2e-trace.json").read_text(encoding="utf-8"))
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert result.ok
    assert payload["review_mode"] == "verification"
    assert payload["blocked"] is False
    assert trace["final"] == {"status": "ready", "iterations": 1}
    assert trace["regenerations"][0]["source_findings"][0]["title"] == "Owner scope missing"
    assert "Owner scope missing" in llm.verification_inputs[0]
    assert "Previous SpecGuard Review Findings" in llm.verification_inputs[0]
    assert "scope every request to the authenticated owner" in feature.joinpath("spec.md").read_text(encoding="utf-8")


def test_strict_e2e_intent_drift_applies_audited_revision_before_stop(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    original = feature.joinpath("spec.md").read_text(encoding="utf-8")
    llm = StrictE2EIntentDriftLLM()

    result = run_strict_e2e_pipeline(feature, llm, max_iterations=1)

    trace = json.loads(feature.joinpath("strict-e2e-trace.json").read_text(encoding="utf-8"))
    spec = feature.joinpath("spec.md").read_text(encoding="utf-8")
    diff_files = list(tmp_path.joinpath(".specguard", "spec-revisions").rglob("spec.diff"))
    assert not result.ok
    assert trace["final"] == {"status": "failed_intent_preservation", "iterations": 0}
    assert trace["regenerations"][0]["intent_preservation"] == "failed"
    assert "SSO Provisioning" in spec
    assert spec != original
    assert len(diff_files) == 1
    assert trace["regenerations"][0]["audit_diff"] == str(diff_files[0])
    assert diff_files[0].with_name("spec.original.md").read_text(encoding="utf-8") == original
    assert "+# Feature Specification: SSO Provisioning" in diff_files[0].read_text(encoding="utf-8")
    assert any("Review diff:" in step for step in result.next_steps)


def test_strict_e2e_fails_markdown_only_verification(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_strict_e2e_pipeline(feature, FakeLLM(), max_iterations=1)

    assert not result.ok
    assert any("executable verification artifacts" in message for message in result.messages)
    assert not feature.joinpath("implementation-output.md").exists()


def test_strict_e2e_accepts_executable_verification(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    feature.joinpath("tests", "test_feature.py").write_text("def test_feature_contract():\n    assert True\n", encoding="utf-8")

    result = run_strict_e2e_pipeline(feature, FakeLLM(), max_iterations=1)

    metadata = read_handoff_metadata(feature)
    assert result.ok
    assert metadata["verification"]["kind"] == "executable"
    assert metadata["verification"]["command"] == "python -m pytest tests/test_feature.py"


def test_strict_e2e_accepts_verification_contract(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    feature.joinpath("tests", "verification-contract.md").write_text(
        "\n".join([
            "# Verification Contract",
            "",
            "Status: accepted",
            "Command: make verify-feature",
            "Artifact: CI job `verify-feature`",
            "",
        ]),
        encoding="utf-8",
    )

    result = run_strict_e2e_pipeline(feature, FakeLLM(), max_iterations=1)

    metadata = read_handoff_metadata(feature)
    assert result.ok
    assert metadata["verification"]["kind"] == "accepted_contract"
    assert metadata["verification"]["command"] == "make verify-feature"


def test_strict_e2e_fails_after_max_iterations(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    llm = StrictE2EAlwaysBlockingLLM()

    result = run_strict_e2e_pipeline(feature, llm, max_iterations=1)

    trace = json.loads(feature.joinpath("strict-e2e-trace.json").read_text(encoding="utf-8"))
    assert not result.ok
    assert trace["final"] == {"status": "max_iterations_exhausted", "iterations": 1}
    assert len(trace["attempts"]) == 2
    assert len(trace["regenerations"]) == 1
    assert any("Strict E2E failed after 1 verification iteration" in message for message in result.messages)
    assert any("strict-e2e-trace.json" in step for step in result.next_steps)


def test_post_run_readiness_review_summary_supports_review_menu(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)

    reports = feature_readiness_reports(feature)
    rendered = render_readiness_summary(*reports[0])

    assert len(reports) == 1
    assert "blocked: False" in rendered
    assert "status: ready_with_warnings" in rendered
    assert "Delete semantics are unsafe" in rendered
    assert "Choose hard or soft delete explicitly" in rendered


def test_post_run_detects_stale_readiness_report_after_spec_change(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)
    spec_path = feature / "spec.md"
    spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\n- Added later.\n", encoding="utf-8")
    future = time.time() + 2
    os.utime(spec_path, (future, future))

    reason = readiness_report_stale_reason(feature)

    assert reason is not None
    assert "spec.md" in reason


def test_post_run_can_generate_and_apply_spec_revision(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)

    revised = generate_spec_revision(feature, FakeRevisionLLM())
    spec_path = apply_spec_revision(feature, revised)

    spec = spec_path.read_text(encoding="utf-8")
    assert "scope every todo read and write by owner" in spec
    assert "Cross-user todo access is rejected" in spec


def test_intent_preservation_check_accepts_coverage_preserving_revision(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)
    revised = generate_spec_revision(feature, FakeRevisionLLM())

    result = validate_spec_revision_intent(feature, revised)

    assert result.ok


def test_intent_preservation_check_blocks_dropped_acceptance_coverage(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)
    revised = IntentDriftRevisionLLM().generate_text("spec refinement assistant", "")

    result = validate_spec_revision_intent(feature, revised)

    assert not result.ok
    assert any("acceptance coverage" in message for message in result.messages)


def test_intent_preservation_check_blocks_out_of_scope_promotion(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    spec_path = feature / "spec.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8")
        + "\n## Out of Scope\n\n- Billing automation\n",
        encoding="utf-8",
    )
    revised = "\n".join([
        "# Spec: feature",
        "",
        "## Requirements",
        "",
        "- The system must accept valid input.",
        "- The system must implement billing automation.",
        "",
        "## Acceptance Criteria",
        "",
        "- [ ] Valid input succeeds.",
        "- [ ] Billing automation succeeds.",
        "",
        "## Error Cases",
        "",
        "- Invalid input",
        "",
    ])

    result = validate_spec_revision_intent(feature, revised)

    assert not result.ok
    assert any("out-of-scope" in message for message in result.messages)


def test_low_mode_softens_out_of_scope_promotions_before_intent_check(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    spec_path = feature / "spec.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8")
        + "\n## Out of Scope\n\n- Billing automation\n",
        encoding="utf-8",
    )
    revised = "\n".join([
        "# Spec: feature",
        "",
        "## Requirements",
        "",
        "- The system must accept valid input.",
        "- The system must implement billing automation.",
        "",
        "## Acceptance Criteria",
        "",
        "- [ ] Valid input succeeds.",
        "- [ ] Billing automation succeeds.",
        "",
        "## Error Cases",
        "",
        "- Invalid input",
        "",
    ])

    softened = soften_low_mode_spec_revision(feature, revised)
    result = validate_spec_revision_intent(feature, softened.revised_spec)

    assert softened.demoted_items == ("Billing automation",)
    assert result.ok
    assert "The system must implement billing automation" not in softened.revised_spec
    assert "Billing automation succeeds" not in softened.revised_spec
    assert "## Out of Scope" in softened.revised_spec
    assert "- Billing automation" in softened.revised_spec


def test_low_mode_softening_does_not_hide_unsafe_intent_changes(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)
    revised = IntentDriftRevisionLLM().generate_text("spec refinement assistant", "")

    softened = soften_low_mode_spec_revision(feature, revised)
    result = validate_spec_revision_intent(feature, softened.revised_spec)

    assert softened.demoted_items == ()
    assert not result.ok
    assert any("acceptance coverage" in message for message in result.messages)


def test_post_run_strips_markdown_fences_from_spec_revision(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)

    revised = generate_spec_revision(feature, FencedRevisionLLM())

    assert revised.startswith("# Feature Specification")
    assert "```" not in revised


def test_post_run_spec_revision_timeout_keeps_menu_available(tmp_path: Path, capsys) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    result = run_pipeline(feature)

    returned = specguard_cli._revise_spec_from_readiness(
        feature,
        Namespace(force=False),
        TimeoutRevisionLLM(),
        result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "Codex request timed out" in rendered
    assert "follow-up menu is still open" in rendered


def test_post_run_spec_revision_applies_and_reruns_pipeline(tmp_path: Path, monkeypatch) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    result = run_pipeline(feature)
    rerun_result = CheckResult("SpecGuard pipeline")
    captured = {"force": False, "review_mode": "", "refresh_technical_design": None}

    def fake_rerun_pipeline(
        args,
        llm_client,
        *,
        force: bool,
        review_mode: str = "initial",
        refresh_technical_design: bool | None = None,
    ):
        captured["force"] = force
        captured["review_mode"] = review_mode
        captured["refresh_technical_design"] = refresh_technical_design
        return rerun_result

    monkeypatch.setattr(specguard_cli, "_rerun_pipeline", fake_rerun_pipeline)

    returned = specguard_cli._revise_spec_from_readiness(
        feature,
        Namespace(force=False),
        FakeRevisionLLM(),
        result,
    )

    spec = feature.joinpath("spec.md").read_text(encoding="utf-8")
    assert returned is rerun_result
    assert captured["force"]
    assert captured["review_mode"] == "verification"
    assert captured["refresh_technical_design"] is True
    assert "scope every todo read and write by owner" in spec


def test_post_run_spec_revision_builds_llm_lazily_after_fast_initial_review(tmp_path: Path, monkeypatch) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    result = run_pipeline(feature)
    rerun_result = CheckResult("SpecGuard pipeline")
    revision_llm = FakeRevisionLLM()
    captured = {"built": False, "llm_client": None}

    def fake_build_llm(*_args, **_kwargs):
        captured["built"] = True
        return revision_llm

    def fake_rerun_pipeline(
        args,
        llm_client,
        *,
        force: bool,
        review_mode: str = "initial",
        refresh_technical_design: bool | None = None,
    ):
        captured["llm_client"] = llm_client
        return rerun_result

    monkeypatch.setattr(specguard_cli, "_build_llm_client", fake_build_llm)
    monkeypatch.setattr(specguard_cli, "_rerun_pipeline", fake_rerun_pipeline)

    returned = specguard_cli._revise_spec_from_readiness(
        feature,
        Namespace(path=str(feature), force=False, no_llm=False),
        None,
        result,
    )

    assert returned is rerun_result
    assert captured["built"] is True
    assert captured["llm_client"] is revision_llm


def test_post_run_low_mode_revision_prompt_uses_critical_backlog_only(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    feature.joinpath("readiness-review.json").write_text(
        json.dumps({
            "review_level": "low",
            "blocked": True,
            "readiness": {"status": "not_ready", "implementation_ready": False},
            "summary": {"critical": 1, "major": 1, "minor": 0},
            "issues": [
                {
                    "severity": "Critical",
                    "title": "Owner scope missing",
                    "description": "The spec does not state how owner scope is enforced.",
                    "impact": "Implementation would need to guess authorization behavior.",
                    "fix": "Add owner-scoped requirements and acceptance criteria.",
                },
                {
                    "severity": "Major",
                    "title": "Bulk import missing",
                    "description": "Bulk import behavior is not specified.",
                    "impact": "This warning should not drive low-mode revision.",
                    "fix": "Define bulk import later if it enters scope.",
                },
            ],
        }),
        encoding="utf-8",
    )
    llm = CaptureSpecRevisionLLM(feature.joinpath("spec.md").read_text(encoding="utf-8"))

    generate_spec_revision(feature, llm, review_level="low")

    assert "Prioritize Critical Readiness Findings." in llm.instructions
    assert "Use these Critical Readiness Findings as the required revision backlog." in llm.input_text
    assert "Owner scope missing" in llm.input_text
    assert "Bulk import missing" not in llm.input_text
    assert "Major and Minor findings are intentionally omitted" in llm.input_text


def test_generate_spec_revision_marks_provider_wait_activity(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    llm = ActivityCaptureSpecRevisionLLM(feature.joinpath("spec.md").read_text(encoding="utf-8"))

    generate_spec_revision(feature, llm, review_level="low")

    assert llm.activity_during_generate == "waiting for LLM Spec Revision response"


def test_post_run_low_mode_revision_converges_to_ready_with_warnings(tmp_path: Path, capsys) -> None:
    feature = write_feature(tmp_path)
    llm = LowModeConvergingWarningLLM()
    result = run_pipeline(feature, llm_client=llm, review_level="low")

    returned = specguard_cli._revise_spec_from_readiness(
        feature,
        Namespace(path=str(feature), force=False, review_level="low"),
        llm,
        result,
    )

    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    assert not result.ok
    assert returned.ok
    assert payload["review_mode"] == "verification"
    assert payload["readiness"]["status"] == "ready_with_warnings"
    assert payload["summary"] == {"critical": 0, "major": 1, "minor": 0}
    assert feature.joinpath("implementation-output.md").exists()
    assert "Owner scope missing" in llm.revision_inputs[0]
    assert "Bulk import missing" not in llm.revision_inputs[0]
    assert "Owner scope missing" in llm.verification_inputs[0]
    assert "Bulk import missing" not in llm.verification_inputs[0]
    rendered = capsys.readouterr().out
    assert "Spec Revision step" in rendered
    assert "checking intent preservation" in rendered
    assert "writing updated spec.md" in rendered
    assert "starting Verification Review rerun" in rendered


def test_post_run_low_mode_revision_auto_demotes_out_of_scope_additions(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    feature = write_feature(tmp_path)
    feature.joinpath("spec.md").write_text(
        feature.joinpath("spec.md").read_text(encoding="utf-8")
        + "\n## Out of Scope\n\n- Billing automation\n",
        encoding="utf-8",
    )
    result = run_pipeline(feature)
    rerun_result = CheckResult("SpecGuard pipeline")

    def fake_rerun_pipeline(*args, **kwargs):
        return rerun_result

    monkeypatch.setattr(specguard_cli, "_rerun_pipeline", fake_rerun_pipeline)

    returned = specguard_cli._revise_spec_from_readiness(
        feature,
        Namespace(force=False, review_level="low"),
        OutOfScopePromotionRevisionLLM(),
        result,
    )

    rendered = capsys.readouterr().out
    spec = feature.joinpath("spec.md").read_text(encoding="utf-8")
    diff_files = list(tmp_path.joinpath(".specguard", "spec-revisions").rglob("spec.diff"))
    assert returned is rerun_result
    assert "auto-demoted out-of-scope additions" in rendered
    assert "Original spec and unified diff written to" in rendered
    assert "The system must implement billing automation" not in spec
    assert "- Billing automation" in spec
    assert len(diff_files) == 1
    assert diff_files[0].exists()


def test_post_run_spec_revision_reuses_technical_design_when_revision_is_acceptance_only(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    feature = write_feature(tmp_path)
    result = run_pipeline(feature)
    rerun_result = CheckResult("SpecGuard pipeline")
    captured = {"refresh_technical_design": None}

    def fake_rerun_pipeline(
        args,
        llm_client,
        *,
        force: bool,
        review_mode: str = "initial",
        refresh_technical_design: bool | None = None,
    ):
        captured["refresh_technical_design"] = refresh_technical_design
        return rerun_result

    monkeypatch.setattr(specguard_cli, "_rerun_pipeline", fake_rerun_pipeline)

    returned = specguard_cli._revise_spec_from_readiness(
        feature,
        Namespace(force=False),
        AcceptanceOnlyRevisionLLM(),
        result,
    )

    rendered = capsys.readouterr().out
    assert returned is rerun_result
    assert captured["refresh_technical_design"] is False
    assert "Reusing existing technical-design.md" in rendered


def test_post_run_spec_revision_applies_intent_drift_with_top_level_audit(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "repo"
    specs_dir = project / "specs"
    specs_dir.mkdir(parents=True)
    feature = copy_example(specs_dir, "risk/todo-api")
    result = run_pipeline(feature)
    original = feature.joinpath("spec.md").read_text(encoding="utf-8")

    def fail_rerun(*args, **kwargs):
        raise AssertionError("Verification Review should not run after intent preservation failure")

    monkeypatch.setattr(specguard_cli, "_rerun_pipeline", fail_rerun)

    returned = specguard_cli._revise_spec_from_readiness(
        feature,
        Namespace(force=False),
        IntentDriftRevisionLLM(),
        result,
    )

    rendered = capsys.readouterr().out
    spec = feature.joinpath("spec.md").read_text(encoding="utf-8")
    diff_files = list(project.joinpath(".specguard", "spec-revisions").rglob("spec.diff"))
    assert returned is result
    assert spec != original
    assert "SSO Provisioning" in spec
    assert not feature.joinpath("spec.proposed.md").exists()
    assert not feature.joinpath(".specguard").exists()
    assert len(diff_files) == 1
    audit_dir = diff_files[0].parent
    assert audit_dir.joinpath("spec.original.md").read_text(encoding="utf-8") == original
    diff_text = diff_files[0].read_text(encoding="utf-8")
    assert "--- specs/risk-todo-api/spec.md (original)" in diff_text
    assert "+++ specs/risk-todo-api/spec.md (updated)" in diff_text
    assert "+# Feature Specification: SSO Provisioning" in diff_text
    assert "Intent Preservation Check" in rendered
    assert "Updated working spec.md for in-place review" in rendered
    assert "Original spec and unified diff written to" in rendered


def test_progress_line_shows_elapsed_time_and_phase() -> None:
    line = _progress_line("Revising spec.md", elapsed_seconds=25, tick=3)

    assert "Revising spec.md" in line
    assert "25s" in line
    assert "waiting for LLM provider response" in line
    assert "[" in line and "]" in line


def test_spec_draft_progress_line_uses_init_phase() -> None:
    line = _progress_line("Generating spec draft", elapsed_seconds=25, tick=4)

    assert "Generating spec draft" in line
    assert "generating spec package" in line


def test_pipeline_progress_line_uses_pipeline_phase() -> None:
    line = _progress_line("Running pipeline", elapsed_seconds=45, tick=5)

    assert "Running pipeline" in line
    assert "running SpecGuard Review" in line


def test_pipeline_progress_line_prefers_active_activity() -> None:
    activity = "waiting for LLM SpecGuard Review (codex model=gpt-5.4, initial, 7 artifacts, 27087 chars)"

    line = _progress_line("Running pipeline", elapsed_seconds=615, tick=5, activity=activity)

    assert activity in line
    assert "building tests, contracts, and outputs" not in line


def test_run_with_progress_announces_activity_changes(capsys) -> None:
    def operation() -> str:
        with progress_activity("assembling Spec Revision context"):
            time.sleep(0.35)
        with progress_activity("waiting for LLM Spec Revision response"):
            time.sleep(0.35)
        return "done"

    result = specguard_cli._run_with_progress("Revising spec.md", operation, announce_activity=True)

    rendered = capsys.readouterr().out
    assert result == "done"
    assert "Current step: assembling Spec Revision context." in rendered
    assert "Current step: waiting for LLM Spec Revision response." in rendered
    assert "Revising spec.md completed" in rendered


def test_rerun_pipeline_uses_activity_progress(monkeypatch) -> None:
    captured = {"label": ""}

    def fake_run_pipeline(
        path: Path,
        llm_client=None,
        force: bool = False,
        review_mode: str = "initial",
        review_level: str = "low",
        refresh_technical_design: bool | None = None,
    ) -> CheckResult:
        assert force
        assert review_mode == "initial"
        assert review_level == "low"
        assert refresh_technical_design is None
        return CheckResult("SpecGuard pipeline")

    def fake_run_with_progress(label, operation):
        captured["label"] = label
        return operation()

    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", fake_run_with_progress)

    result = specguard_cli._rerun_pipeline(
        Namespace(path="specs/example"),
        llm_client=None,
        force=True,
    )

    assert result.ok
    assert captured["label"] == "Running pipeline"


def test_follow_up_empty_input_keeps_menu_open(monkeypatch, capsys) -> None:
    choices = iter(["", "q"])
    result = CheckResult("SpecGuard pipeline")

    monkeypatch.setattr("builtins.input", lambda _prompt: next(choices))

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False, no_llm=True),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "Choose 1 to view findings, u after editing spec.md, or q to exit." in rendered


def test_follow_up_menu_hides_spec_regeneration_without_blocked_findings(monkeypatch, capsys) -> None:
    result = CheckResult("SpecGuard pipeline")

    monkeypatch.setattr("builtins.input", lambda _prompt: "q")

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False, no_llm=True),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "[1] View Readiness Findings" in rendered
    assert "[u] I updated spec.md; rerun SpecGuard" in rendered
    assert "[2] Regenerate spec from Readiness Findings" not in rendered
    assert "Spec regeneration is hidden because no blocked Readiness Findings were found." in rendered
    assert "[q] Exit" in rendered


def test_follow_up_menu_hides_spec_regeneration_by_default_with_blocked_findings(monkeypatch, capsys) -> None:
    result = CheckResult("SpecGuard pipeline")

    monkeypatch.setattr(specguard_cli, "blocked_feature_reports", lambda _path: [(Path("specs/example"), {})])
    monkeypatch.setattr("builtins.input", lambda _prompt: "q")

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False, no_llm=True),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "[1] View Readiness Findings" in rendered
    assert "[2] Experimental auto-revise spec from Readiness Findings" not in rendered
    assert "Automatic Spec Revision is experimental and disabled by default." in rendered
    assert "Edit spec.md using the findings, then rerun SpecGuard." in rendered
    assert "[q] Exit" in rendered


def test_follow_up_menu_shows_experimental_spec_regeneration_when_enabled(monkeypatch, capsys) -> None:
    result = CheckResult("SpecGuard pipeline")

    monkeypatch.setattr(specguard_cli, "blocked_feature_reports", lambda _path: [(Path("specs/example"), {})])
    monkeypatch.setattr("builtins.input", lambda _prompt: "q")

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False, experimental_auto_revise=True),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "[1] View Readiness Findings" in rendered
    assert "[2] Run SpecGuard Review (Detail) with the configured LLM" in rendered
    assert "[3] Experimental auto-revise spec from Readiness Findings" in rendered
    assert "[q] Exit" in rendered


def test_follow_up_menu_runs_detail_review_without_replacing_fast_report(monkeypatch, capsys) -> None:
    choices = iter(["2", "q"])
    result = CheckResult("SpecGuard pipeline")
    detail_result = CheckResult("SpecGuard Review")
    detail_client = object()
    captured = {"report_stem": "", "llm_client": None}
    report = {
        "blocked": False,
        "readiness": {"status": "ready_with_warnings", "implementation_ready": True},
        "summary": {"critical": 0, "major": 0, "minor": 1},
        "issues": [],
    }

    def fake_detail_review(path: Path, *, llm_client=None, review_mode: str = "initial", review_level: str = "low", report_stem: str = "readiness-review"):
        captured["report_stem"] = report_stem
        captured["llm_client"] = llm_client
        assert path == Path("specs/example")
        assert review_mode == "initial"
        assert review_level == "low"
        return detail_result

    monkeypatch.setattr(specguard_cli, "feature_readiness_reports", lambda _path: [(Path("specs/example"), report)])
    monkeypatch.setattr(specguard_cli, "_build_llm_client", lambda *_args, **_kwargs: detail_client)
    monkeypatch.setattr(specguard_cli, "run_readiness_review", fake_detail_review)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", lambda _label, operation: operation())
    monkeypatch.setattr("builtins.input", lambda _prompt: next(choices))

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False, review_level="low"),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "SpecGuard Review (Detail)" in rendered
    assert "does not replace the fast readiness review" in rendered
    assert captured["report_stem"] == "readiness-review-detail"
    assert captured["llm_client"] is detail_client


def test_follow_up_menu_reruns_after_user_edits_spec(monkeypatch, capsys) -> None:
    choices = iter(["u", "q"])
    result = CheckResult("SpecGuard pipeline")
    rerun_result = CheckResult("SpecGuard pipeline")
    captured = {"force": None, "llm_client": object()}

    def fake_rerun(args, llm_client, *, force: bool, review_mode: str = "initial", refresh_technical_design=None):
        captured["force"] = force
        captured["llm_client"] = llm_client
        return rerun_result

    monkeypatch.setattr(specguard_cli, "_rerun_pipeline", fake_rerun)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(choices))

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False, no_llm=True),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is rerun_result
    assert "Spec was updated. Re-running SpecGuard from the current spec package." in rendered
    assert captured["force"] is False
    assert captured["llm_client"] is None


def test_follow_up_menu_for_pre_review_validation_failure_hides_stale_review(monkeypatch, capsys) -> None:
    choices = iter(["q"])
    result = CheckResult("SpecGuard pipeline")
    result.add_error("spec.md must include section: Requirements")
    result.details["failed_before_readiness_review"] = True

    monkeypatch.setattr("builtins.input", lambda _prompt: next(choices))

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False, no_llm=False),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "Pipeline stopped before SpecGuard Review" in rendered
    assert "[u] I updated spec.md; rerun SpecGuard" in rendered
    assert "View Readiness Findings" not in rendered
    assert "SpecGuard Review (Detail)" not in rendered


def test_follow_up_menu_rejects_spec_regeneration_when_experimental_flag_is_missing(monkeypatch, capsys) -> None:
    choices = iter(["3", "q"])
    result = CheckResult("SpecGuard pipeline")

    monkeypatch.setattr(specguard_cli, "blocked_feature_reports", lambda _path: [(Path("specs/example"), {})])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(choices))

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False, no_llm=True),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "Automatic Spec Revision is experimental and disabled by default." in rendered
    assert "To opt in, rerun with --experimental-auto-revise." in rendered


def test_follow_up_menu_rejects_spec_regeneration_without_blocked_findings(monkeypatch, capsys) -> None:
    choices = iter(["3", "q"])
    result = CheckResult("SpecGuard pipeline")

    monkeypatch.setattr("builtins.input", lambda _prompt: next(choices))

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "Spec regeneration is available only when SpecGuard Review is blocked." in rendered


def test_follow_up_menu_detects_git_bash_environment(monkeypatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("MSYSTEM", "MINGW64")

    assert _should_offer_follow_up(Namespace(no_follow_up=False, follow_up=False))


def test_follow_up_menu_can_be_forced_or_disabled(monkeypatch) -> None:
    monkeypatch.delenv("MSYSTEM", raising=False)
    monkeypatch.setenv("CI", "true")

    assert _should_offer_follow_up(Namespace(no_follow_up=False, follow_up=True))
    assert not _should_offer_follow_up(Namespace(no_follow_up=True, follow_up=True))
    assert not _should_offer_follow_up(Namespace(no_follow_up=False, follow_up=False))


def test_follow_up_menu_is_not_default_after_ready_result(monkeypatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("MSYSTEM", "MINGW64")

    assert not _should_offer_follow_up(Namespace(no_follow_up=False, follow_up=False), CheckResult("SpecGuard pipeline"))


def test_run_invokes_follow_up_loop_when_forced(monkeypatch) -> None:
    called = {"value": False}

    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, review_level: str = "low") -> CheckResult:
        assert review_level == "low"
        return CheckResult("SpecGuard pipeline")

    def fake_follow_up(args, llm_client, result):
        called["value"] = True
        return result

    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_follow_up_loop", fake_follow_up)

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=False,
        no_llm=True,
        no_follow_up=False,
        follow_up=True,
        review_level=None,
    ))

    assert exit_code == 0
    assert called["value"]


def test_run_ready_result_does_not_open_default_follow_up_menu(monkeypatch) -> None:
    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, review_level: str = "low") -> CheckResult:
        return CheckResult("SpecGuard pipeline")

    def fail_follow_up(args, llm_client, result):
        raise AssertionError("READY results should not open the default follow-up menu")

    monkeypatch.setenv("MSYSTEM", "MINGW64")
    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", lambda _label, operation: operation())
    monkeypatch.setattr(specguard_cli, "_run_follow_up_loop", fail_follow_up)

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=False,
        no_llm=True,
        no_follow_up=False,
        follow_up=False,
        review_level=None,
        strict_e2e=False,
        strict_max_iterations=3,
    ))

    assert exit_code == 0


def test_run_validation_failure_does_not_open_default_follow_up_menu(monkeypatch, capsys) -> None:
    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, review_level: str = "low") -> CheckResult:
        result = CheckResult("SpecGuard pipeline")
        result.add_error("spec.md must include section: Requirements")
        result.details["failed_before_readiness_review"] = True
        return result

    def fail_follow_up(args, llm_client, result):
        raise AssertionError("Validation failures before SpecGuard Review should not show the default follow-up menu")

    monkeypatch.setenv("MSYSTEM", "MINGW64")
    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", lambda _label, operation: operation())
    monkeypatch.setattr(specguard_cli, "_run_follow_up_loop", fail_follow_up)

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=False,
        llm=False,
        llm_mode=None,
        llm_model=None,
        no_llm=True,
        no_follow_up=False,
        follow_up=False,
        review_level=None,
        strict_e2e=False,
        strict_max_iterations=3,
    ))

    rendered = capsys.readouterr().out
    assert exit_code == 1
    assert "Spec package validation failed before SpecGuard Review" in rendered
    assert "Existing readiness-review.md/json may be stale" in rendered
    assert "SpecGuard Review passed, but a later pipeline gate failed" not in rendered


def test_default_low_run_uses_fast_heuristic_review_even_with_provider_configured(monkeypatch) -> None:
    captured = {"llm_client": object()}

    def fail_build_llm(*_args, **_kwargs):
        raise AssertionError("default low run should not build a live LLM client")

    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, review_level: str = "low") -> CheckResult:
        captured["llm_client"] = llm_client
        assert review_level == "low"
        return CheckResult("SpecGuard pipeline")

    monkeypatch.setattr(specguard_cli, "_build_llm_client", fail_build_llm)
    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", lambda _label, operation: operation())

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=False,
        llm=False,
        llm_mode=None,
        llm_model=None,
        no_llm=False,
        no_follow_up=True,
        follow_up=False,
        review_level=None,
        strict_e2e=False,
        strict_max_iterations=3,
    ))

    assert exit_code == 0
    assert captured["llm_client"] is None


def test_run_llm_flag_requests_live_initial_review(monkeypatch) -> None:
    live_client = object()
    captured = {"llm_client": None}

    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, review_level: str = "low") -> CheckResult:
        captured["llm_client"] = llm_client
        return CheckResult("SpecGuard pipeline")

    monkeypatch.setattr(specguard_cli, "_build_llm_client", lambda *_args, **_kwargs: live_client)
    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", lambda _label, operation: operation())

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=False,
        llm=True,
        llm_mode=None,
        llm_model=None,
        no_llm=False,
        no_follow_up=True,
        follow_up=False,
        review_level=None,
        strict_e2e=False,
        strict_max_iterations=3,
    ))

    assert exit_code == 0
    assert captured["llm_client"] is live_client


def test_run_not_ready_guides_manual_spec_revision(monkeypatch, capsys) -> None:
    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, review_level: str = "low") -> CheckResult:
        result = CheckResult("SpecGuard pipeline")
        result.add_error("SpecGuard Review found Critical readiness blockers.")
        return result

    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", lambda _label, operation: operation())

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=False,
        no_llm=True,
        no_follow_up=True,
        follow_up=False,
        review_level=None,
        strict_e2e=False,
        strict_max_iterations=3,
    ))

    rendered = capsys.readouterr().out
    assert exit_code == 1
    assert "Manual Spec Revision" in rendered
    assert "SpecGuard did not rewrite spec.md automatically." in rendered
    assert "specguard run specs/example" in rendered
    assert "--experimental-auto-revise" in rendered


def test_post_review_guidance_for_not_ready_report(monkeypatch, capsys) -> None:
    report = {
        "blocked": True,
        "readiness": {"status": "not_ready", "implementation_ready": False},
        "summary": {"critical": 1, "major": 2, "minor": 3},
        "issues": [
            {"severity": "Major", "title": "Minor ordering should not win"},
            {"severity": "Critical", "title": "Missing rollback and failure handling details"},
        ],
    }
    result = CheckResult("SpecGuard pipeline")
    result.add_error("SpecGuard Review found blockers.")
    monkeypatch.setattr(specguard_cli, "feature_readiness_reports", lambda _path: [(Path("specs/example"), report)])

    specguard_cli._print_post_review_guidance(Namespace(path="specs/example"), result)

    rendered = capsys.readouterr().out
    assert "Next Action" in rendered
    assert "blocking readiness gaps: Missing rollback and failure handling details" in rendered
    assert "Current findings: Critical 1, Major 2, Minor 3." in rendered
    assert "SpecGuard Review (Detail)" in rendered
    assert "specs/example/readiness-review.md" in rendered
    assert "specguard run specs/example" in rendered
    assert "--experimental-auto-revise" in rendered


def test_post_review_guidance_for_ready_with_warnings(monkeypatch, capsys) -> None:
    report = {
        "blocked": False,
        "readiness": {"status": "ready_with_warnings", "implementation_ready": True},
        "summary": {"critical": 0, "major": 1, "minor": 1},
        "issues": [
            {"severity": "Minor", "title": "Observability signal names can be tighter"},
            {"severity": "Major", "title": "Contract examples are incomplete"},
        ],
    }
    monkeypatch.setattr(specguard_cli, "feature_readiness_reports", lambda _path: [(Path("specs/example"), report)])

    specguard_cli._print_post_review_guidance(Namespace(path="specs/example"), CheckResult("SpecGuard pipeline"))

    rendered = capsys.readouterr().out
    assert "Next Action" in rendered
    assert "implementation-ready with warnings: Contract examples are incomplete" in rendered
    assert "You can proceed now; warnings are not blocking at this review level." in rendered
    assert "specs/example/readiness-review.md" in rendered
    assert "specs/example/implementation-output.md" in rendered


def test_post_review_guidance_for_ready(monkeypatch, capsys) -> None:
    report = {
        "blocked": False,
        "readiness": {"status": "ready", "implementation_ready": True},
        "summary": {"critical": 0, "major": 0, "minor": 0},
        "issues": [],
    }
    monkeypatch.setattr(specguard_cli, "feature_readiness_reports", lambda _path: [(Path("specs/example"), report)])

    specguard_cli._print_post_review_guidance(Namespace(path="specs/example"), CheckResult("SpecGuard pipeline"))

    rendered = capsys.readouterr().out
    assert "Summary: Spec is ready for implementation." in rendered
    assert "Test, Contract, and Implementation Handoff artifacts are generated." in rendered
    assert "specs/example/implementation-output.md" in rendered
    assert "develop/<stack>" in rendered


def test_run_uses_activity_progress_for_initial_pipeline(monkeypatch) -> None:
    captured = {"label": ""}

    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, review_level: str = "low") -> CheckResult:
        assert review_level == "low"
        return CheckResult("SpecGuard pipeline")

    def fake_run_with_progress(label, operation):
        captured["label"] = label
        return operation()

    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", fake_run_with_progress)

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=True,
        no_llm=True,
        no_follow_up=True,
        follow_up=False,
        review_level=None,
    ))

    assert exit_code == 0
    assert captured["label"] == "Running pipeline"


def test_run_passes_review_level_override(monkeypatch) -> None:
    captured = {"review_level": ""}

    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, review_level: str = "low") -> CheckResult:
        captured["review_level"] = review_level
        return CheckResult("SpecGuard pipeline")

    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", lambda _label, operation: operation())

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=False,
        no_llm=True,
        no_follow_up=True,
        follow_up=False,
        review_level="medium",
        strict_e2e=False,
        strict_max_iterations=3,
    ))

    assert exit_code == 0
    assert captured["review_level"] == "medium"


def test_run_uses_env_review_level(monkeypatch) -> None:
    captured = {"review_level": ""}

    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, review_level: str = "low") -> CheckResult:
        captured["review_level"] = review_level
        return CheckResult("SpecGuard pipeline")

    monkeypatch.setenv("SPECGUARD_REVIEW_LEVEL", "high")
    monkeypatch.setattr(specguard_cli, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", lambda _label, operation: operation())

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=False,
        no_llm=True,
        no_follow_up=True,
        follow_up=False,
        review_level=None,
        strict_e2e=False,
        strict_max_iterations=3,
    ))

    assert exit_code == 0
    assert captured["review_level"] == "high"


def test_strict_e2e_defaults_to_medium_review_level(monkeypatch) -> None:
    captured = {"review_level": ""}

    def fake_strict(path: Path, llm_client, *, force: bool = False, max_iterations: int = 3, review_level: str = "medium") -> CheckResult:
        captured["review_level"] = review_level
        return CheckResult("SpecGuard strict e2e pipeline")

    monkeypatch.setattr(specguard_cli, "_build_llm_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(specguard_cli, "run_strict_e2e_pipeline", fake_strict)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", lambda _label, operation: operation())

    exit_code = specguard_cli.run(Namespace(
        path="specs/example",
        force=False,
        no_llm=False,
        no_follow_up=True,
        follow_up=False,
        review_level=None,
        strict_e2e=True,
        strict_max_iterations=2,
    ))

    assert exit_code == 0
    assert captured["review_level"] == "medium"


def test_init_uses_activity_progress_for_spec_draft(monkeypatch) -> None:
    captured = {"label": ""}

    def fake_initialize_specs(root: Path, answers: dict[str, str], force: bool = False, llm_client=None) -> CheckResult:
        assert force
        assert answers["feature_names"] == "billing-export"
        return CheckResult("SpecGuard Discovery")

    def fake_run_with_progress(label, operation):
        captured["label"] = label
        return operation()

    monkeypatch.setattr(specguard_cli, "initialize_specs", fake_initialize_specs)
    monkeypatch.setattr(specguard_cli, "_run_with_progress", fake_run_with_progress)

    exit_code = specguard_cli.init_project(Namespace(
        feature="billing-export",
        force=True,
        no_llm=True,
        non_interactive=True,
    ))

    assert exit_code == 0
    assert captured["label"] == "Generating spec draft"


def test_tdd_generator_does_not_overwrite_existing_tests(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    test_file = feature / "tests" / "feature.test.md"
    original = "# Hand-written scenarios\n\n- [ ] Preserve me\n"
    test_file.write_text(original, encoding="utf-8")

    output = generate_tests(feature)

    assert output == test_file
    assert test_file.read_text(encoding="utf-8") == original


def test_run_refreshes_derived_artifacts_when_spec_is_newer(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    test_file = feature / "tests" / "feature.test.md"
    original = test_file.read_text(encoding="utf-8")
    now = time.time()
    os.utime(test_file, (now - 100, now - 100))
    os.utime(feature / "spec.md", (now, now))

    result = run_pipeline(feature)

    assert result.ok
    assert test_file.read_text(encoding="utf-8") != original
    assert "TDD Scenarios" in test_file.read_text(encoding="utf-8")


def test_validator_rejects_placeholder_content(tmp_path: Path) -> None:
    feature = write_feature(tmp_path, placeholder=True)

    result = validate_feature(feature)

    assert not result.ok
    assert any("placeholder" in message for message in result.messages)


def test_validator_allows_pending_as_domain_language(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    spec_path = feature / "spec.md"
    spec = spec_path.read_text(encoding="utf-8")
    spec_path.write_text(
        spec.replace("- Invalid input", "- Pending jobs time out with a stable error code."),
        encoding="utf-8",
    )

    result = validate_feature(feature)

    assert result.ok


def test_validator_requires_discovery(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    feature.joinpath("discovery.md").unlink()

    result = validate_feature(feature)

    assert not result.ok
    assert any("discovery.md" in message for message in result.messages)


def test_contract_checker_rejects_invalid_openapi(tmp_path: Path) -> None:
    feature = write_feature(tmp_path, bad_contract=True)

    result = check_contracts(feature)

    assert not result.ok
    assert any("info.title" in message for message in result.messages)


def test_contract_checker_rejects_empty_openapi_paths(tmp_path: Path) -> None:
    feature = write_feature(tmp_path, empty_contract=True)

    result = check_contracts(feature)

    assert not result.ok
    assert any("at least one API path" in message for message in result.messages)


def test_contract_checker_rejects_operations_without_error_responses(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)
    feature.joinpath("contracts", "openapi.yaml").write_text(
        "\n".join([
            "openapi: 3.1.0",
            "info:",
            "  title: Feature API",
            "  version: 0.1.0",
            "paths:",
            "  /feature:",
            "    post:",
            "      responses:",
            "        \"200\":",
            "          description: Feature accepted",
            "",
        ]),
        encoding="utf-8",
    )

    result = check_contracts(feature)

    assert not result.ok
    assert any("documented error response" in message for message in result.messages)


def test_contract_checker_accepts_non_api_exemption(tmp_path: Path) -> None:
    feature = tmp_path / "feature"
    contracts = feature / "contracts"
    contracts.mkdir(parents=True)
    contracts.joinpath("contract-exemption.md").write_text(
        "\n".join([
            "# Contract Exemption",
            "",
            "Status: accepted",
            "Contract: not applicable",
            "Reason: This feature produces an internal batch report and has no API boundary.",
            "",
        ]),
        encoding="utf-8",
    )

    result = check_contracts(feature)

    assert result.ok
    assert any("Accepted non-API contract exemption" in message for message in result.messages)


def test_contract_checker_fallback_rejects_empty_openapi_paths(tmp_path: Path, monkeypatch) -> None:
    feature = write_feature(tmp_path, empty_contract=True)
    original_import = builtins.__import__

    def block_yaml(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("yaml unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_yaml)

    result = check_contracts(feature)

    assert not result.ok
    assert any("at least one API path" in message for message in result.messages)


def test_contract_checker_fallback_accepts_defined_openapi_paths(tmp_path: Path, monkeypatch) -> None:
    feature = write_feature(tmp_path)
    original_import = builtins.__import__

    def block_yaml(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("yaml unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_yaml)

    result = check_contracts(feature)

    assert result.ok
