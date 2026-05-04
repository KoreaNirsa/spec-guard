from __future__ import annotations

from argparse import Namespace
import json
import os
import shutil
import time
from pathlib import Path

from tools.contract_checker import check_contracts
from tools.discovery_engine import collect_llm_answers, initialize_specs
from tools.grill_engine import run_grill
from tools.llm_client import (
    LLMSettings,
    _extract_codex_error_text,
    _extract_codex_event_text,
    _iter_response_text_deltas,
    load_llm_settings,
    save_llm_settings,
)
from tools.post_run import (
    apply_spec_revision,
    feature_grill_reports,
    generate_spec_revision,
    grill_report_stale_reason,
    render_grill_summary,
)
from tools.result import CheckResult
from tools.runner import run_pipeline
from tools.spec_validator import validate_feature
from tools.tdd_generator import generate_tests
import cli.specguard as specguard_cli
from cli.specguard import _progress_line, _should_offer_follow_up


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


class FakeRevisionLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        assert "spec refinement assistant" in instructions
        assert "## Acceptance Criteria" in instructions
        assert "Do not rename ## Acceptance Criteria" in instructions
        assert "Grill Me findings" in input_text
        assert max_output_tokens == 3000
        return "\n".join([
            "# Feature Specification: Todo API",
            "",
            "## Requirements",
            "",
            "- The system must scope every todo read and write by owner.",
            "",
            "## Acceptance Criteria",
            "",
            "- [ ] Cross-user todo access is rejected.",
            "",
            "## Error Cases",
            "",
            "- Unauthorized todo access",
            "",
        ])


class FencedRevisionLLM(FakeRevisionLLM):
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        return "```markdown\n" + super().generate_text(instructions, input_text, max_output_tokens) + "\n```"


class TimeoutRevisionLLM:
    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        from tools.llm_client import LLMRequestError

        raise LLMRequestError("Codex request timed out.")


class SixMinorGrillLLM:
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


class CaptureVerificationGrillLLM:
    def __init__(self) -> None:
        self.instructions = ""
        self.input_text = ""

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 2500) -> str:
        self.instructions = instructions
        self.input_text = input_text
        return '{"issues":[]}'


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
    assert payload["review_mode"] == "initial"
    assert payload["readiness"]["implementation_ready"] is True
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
    assert any("python -m cli.specguard run specs" in step for step in result.next_steps)


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
    assert settings.timeout == 180


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
    assert any("full SpecGuard spec package" in call for call in llm.calls)


def test_risk_todo_example_is_blocked_by_grill(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")

    result = run_pipeline(feature)

    assert not result.ok
    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    assert payload["blocked"] is True
    assert payload["readiness"]["implementation_ready"] is False
    assert payload["summary"]["critical"] == 1
    assert payload["summary"]["major"] == 1
    assert "Todo ownership boundary is unclear" in {issue["title"] for issue in payload["issues"]}
    assert any("Open the human report" in step for step in result.next_steps)
    assert any("specguard run" in step for step in result.next_steps)


def test_grill_reviews_full_spec_package_artifacts(tmp_path: Path) -> None:
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

    pipeline = run_pipeline(feature)

    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    reviewed_paths = {artifact["path"] for artifact in payload["input"]["artifacts"]}
    assert pipeline.ok
    assert {"discovery.md", "spec.md", "plan.md", "tasks.md", "constitution.md", "checklists/spec-readiness.md", "technical-design.md"} <= reviewed_paths


def test_grill_blocks_when_minor_findings_exceed_readiness_threshold(tmp_path: Path) -> None:
    feature = write_feature(tmp_path)

    result = run_grill(feature, llm_client=SixMinorGrillLLM())

    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    assert not result.ok
    assert payload["blocked"] is True
    assert payload["readiness"]["implementation_ready"] is False
    assert payload["summary"]["minor"] == 6
    assert any("[NOT READY]" in message for message in result.messages)


def test_grill_verification_mode_uses_previous_findings(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)
    llm = CaptureVerificationGrillLLM()

    result = run_grill(feature, llm_client=llm, review_mode="verification")

    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    assert result.ok
    assert payload["review_mode"] == "verification"
    assert "Verification Review board" in llm.instructions
    assert "Previous Grill Review Findings" in llm.input_text
    assert "Todo ownership boundary is unclear" in llm.input_text


def test_post_run_grill_summary_supports_review_menu(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)

    reports = feature_grill_reports(feature)
    rendered = render_grill_summary(*reports[0])

    assert len(reports) == 1
    assert "blocked: True" in rendered
    assert "Todo ownership boundary is unclear" in rendered
    assert "Require owner-scoped queries" in rendered


def test_post_run_detects_stale_grill_report_after_spec_change(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)
    spec_path = feature / "spec.md"
    spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\n- Added later.\n", encoding="utf-8")
    future = time.time() + 2
    os.utime(spec_path, (future, future))

    reason = grill_report_stale_reason(feature)

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


def test_post_run_strips_markdown_fences_from_spec_revision(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    run_pipeline(feature)

    revised = generate_spec_revision(feature, FencedRevisionLLM())

    assert revised.startswith("# Feature Specification")
    assert "```" not in revised


def test_post_run_spec_revision_timeout_keeps_menu_available(tmp_path: Path, capsys) -> None:
    feature = copy_example(tmp_path, "risk/todo-api")
    result = run_pipeline(feature)

    returned = specguard_cli._revise_spec_from_grill(
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
    captured = {"force": False, "grill_mode": ""}

    def fake_rerun_pipeline(args, llm_client, *, force: bool, grill_mode: str = "initial"):
        captured["force"] = force
        captured["grill_mode"] = grill_mode
        return rerun_result

    monkeypatch.setattr(specguard_cli, "_rerun_pipeline", fake_rerun_pipeline)

    returned = specguard_cli._revise_spec_from_grill(
        feature,
        Namespace(force=False),
        FakeRevisionLLM(),
        result,
    )

    spec = feature.joinpath("spec.md").read_text(encoding="utf-8")
    assert returned is rerun_result
    assert captured["force"]
    assert captured["grill_mode"] == "verification"
    assert "scope every todo read and write by owner" in spec


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
    assert "running Grill Me" in line


def test_rerun_pipeline_uses_activity_progress(monkeypatch) -> None:
    captured = {"label": ""}

    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False, grill_mode: str = "initial") -> CheckResult:
        assert force
        assert grill_mode == "initial"
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
        Namespace(path="specs/example", force=False),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "No action selected" in rendered


def test_follow_up_menu_uses_grill_review_actions(monkeypatch, capsys) -> None:
    result = CheckResult("SpecGuard pipeline")

    monkeypatch.setattr("builtins.input", lambda _prompt: "q")

    returned = specguard_cli._run_follow_up_loop(
        Namespace(path="specs/example", force=False),
        llm_client=None,
        result=result,
    )

    rendered = capsys.readouterr().out
    assert returned is result
    assert "[1] View Grill Me review" in rendered
    assert "[2] Regenerate spec from Grill Me review (auto-runs Grill Me review after)" in rendered
    assert "Run Grill Me review" not in rendered
    assert "[q] Exit" in rendered


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


def test_run_invokes_follow_up_loop_when_forced(monkeypatch) -> None:
    called = {"value": False}

    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False) -> CheckResult:
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
    ))

    assert exit_code == 0
    assert called["value"]


def test_run_uses_activity_progress_for_initial_pipeline(monkeypatch) -> None:
    captured = {"label": ""}

    def fake_run_pipeline(path: Path, llm_client=None, force: bool = False) -> CheckResult:
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
    ))

    assert exit_code == 0
    assert captured["label"] == "Running pipeline"


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
