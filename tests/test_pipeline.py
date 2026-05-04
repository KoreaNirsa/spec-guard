from __future__ import annotations

from argparse import Namespace
import json
import os
import shutil
import time
from pathlib import Path

from tools.contract_checker import check_contracts
from tools.discovery_engine import collect_llm_answers, initialize_specs
from tools.llm_client import _iter_response_text_deltas
from tools.runner import run_pipeline
from tools.spec_validator import validate_feature
from tools.tdd_generator import generate_tests


ROOT = Path(__file__).resolve().parents[1]


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        self.calls.append(instructions)
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


def copy_example(tmp_path: Path, example: str) -> Path:
    source = ROOT / "examples" / example
    target = tmp_path / example.replace("/", "-")
    shutil.copytree(source, target)
    return target


def write_feature(base: Path, *, placeholder: bool = False, bad_contract: bool = False) -> Path:
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

    requirement = "pending behavior definition." if placeholder else "The system must accept valid input."
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
    contract = "openapi: 3.1.0\npaths: {}\n" if bad_contract else (
        "openapi: 3.1.0\n"
        "info:\n"
        "  title: Feature API\n"
        "  version: 0.1.0\n"
        "paths: {}\n"
    )
    feature.joinpath("contracts", "openapi.yaml").write_text(contract, encoding="utf-8")
    return feature


def test_example_passes_and_emits_grill_json(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "example")

    result = run_pipeline(feature)

    assert result.ok
    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    assert payload["blocked"] is False
    assert payload["summary"]["critical"] == 0
    assert payload["summary"]["major"] == 0


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
    assert "User Scenarios & Testing" in feature.joinpath("spec.md").read_text(encoding="utf-8")


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


def test_llm_discovery_streams_conversation_into_spec(tmp_path: Path) -> None:
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
    assert "LLM Discovery Conversation" in discovery.read_text(encoding="utf-8")
    assert "What problem should the spec solve?" in "".join(output)
    assert any("반드시 스펙을 검토하고 보완하라" in step for step in result.next_steps)


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


def test_run_generates_supporting_artifacts_from_spec_basis(tmp_path: Path) -> None:
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
    assert feature.joinpath("contracts", "openapi.yaml").exists()
    assert feature.joinpath("implementation-output.md").exists()


def test_run_can_use_llm_for_design_and_grill(tmp_path: Path) -> None:
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
    llm = FakeLLM()

    result = run_pipeline(feature, llm_client=llm)

    assert result.ok
    assert "API layer calls an export service" in feature.joinpath("technical-design.md").read_text(encoding="utf-8")
    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    assert payload["blocked"] is False
    assert any("technical design generator" in call.lower() for call in llm.calls)


def test_risk_todo_example_is_blocked_by_grill(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")

    result = run_pipeline(feature)

    assert not result.ok
    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    assert payload["blocked"] is True
    assert payload["summary"]["critical"] == 1
    assert payload["summary"]["major"] == 1
    assert "Todo ownership boundary is unclear" in {issue["title"] for issue in payload["issues"]}
    assert any("Open the human report" in step for step in result.next_steps)
    assert any("specguard run" in step for step in result.next_steps)


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
