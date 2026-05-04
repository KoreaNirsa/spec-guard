from __future__ import annotations

import json
import shutil
from pathlib import Path

from tools.contract_checker import check_contracts
from tools.runner import run_pipeline
from tools.spec_validator import validate_feature
from tools.tdd_generator import generate_tests


ROOT = Path(__file__).resolve().parents[1]


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
            "# Deep Discovery: feature",
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
            "- Output: Spec, design, tests, and contract.",
            "",
        ]),
        encoding="utf-8",
    )

    requirement = "Describe the required behavior." if placeholder else "The system must accept valid input."
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
    feature.joinpath("design.md").write_text(
        "\n".join([
            "# Design: feature",
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
            "- Initial state: pending",
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


def test_user_auth_example_passes_and_emits_grill_json(tmp_path: Path) -> None:
    feature = copy_example(tmp_path, "user-auth")

    result = run_pipeline(feature)

    assert result.ok
    payload = json.loads(feature.joinpath("grill.json").read_text(encoding="utf-8"))
    assert payload["blocked"] is False
    assert payload["summary"]["critical"] == 0
    assert payload["summary"]["major"] == 0


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
