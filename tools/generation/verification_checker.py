from __future__ import annotations

import re
from pathlib import Path

from tools.result import CheckResult


EXECUTABLE_TEST_SUFFIXES = {".py", ".js", ".ts", ".sh", ".ps1"}
VERIFICATION_CONTRACT_NAME = "verification-contract.md"
NON_ACTIONABLE_CONTRACT_VALUES = {"", "-", "none", "n/a", "na", "tbd", "todo", "pending"}


def verification_metadata(path: Path) -> dict[str, object]:
    tests_dir = path / "tests"
    executable = _executable_tests(tests_dir)
    if executable:
        artifact = executable[0]
        return {
            "kind": "executable",
            "artifact": _relative(path, artifact),
            "command": _verification_command(path, artifact),
            "strict_ready": True,
        }

    contract = tests_dir / VERIFICATION_CONTRACT_NAME
    if _accepted_verification_contract(contract):
        text = contract.read_text(encoding="utf-8")
        return {
            "kind": "accepted_contract",
            "artifact": _relative(path, contract),
            "command": _contract_command(text),
            "strict_ready": True,
        }

    markdown = sorted(tests_dir.glob("*.md")) if tests_dir.exists() else []
    return {
        "kind": "markdown_scenarios" if markdown else "missing",
        "artifact": _relative(path, markdown[0]) if markdown else None,
        "command": None,
        "strict_ready": False,
    }


def check_verification_artifacts(path: Path) -> CheckResult:
    result = CheckResult("Executable verification validation")
    metadata = verification_metadata(path)
    if metadata["strict_ready"]:
        result.add_info(f"Strict verification artifact accepted: {metadata['artifact']}")
        if metadata.get("command"):
            result.add_info(f"Expected verification command: {metadata['command']}")
        return result

    result.add_error(
        f"{path} must include executable verification artifacts or tests/{VERIFICATION_CONTRACT_NAME} before strict implementation handoff"
    )
    result.add_next_step(f"Add executable tests under {path / 'tests'} or an accepted {VERIFICATION_CONTRACT_NAME}.")
    return result


def _executable_tests(tests_dir: Path) -> list[Path]:
    if not tests_dir.exists():
        return []
    return sorted(
        candidate
        for candidate in tests_dir.rglob("*")
        if candidate.is_file() and candidate.suffix.lower() in EXECUTABLE_TEST_SUFFIXES
    )


def _accepted_verification_contract(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return _has_accepted_status(text) and (
        _actionable_contract_value(text, "command") is not None
        or _actionable_contract_value(text, "artifact") is not None
    )


def _contract_command(text: str) -> str | None:
    return _actionable_contract_value(text, "command")


def _has_accepted_status(text: str) -> bool:
    return re.search(r"^status:[ \t]*accepted[ \t]*$", text, flags=re.IGNORECASE | re.MULTILINE) is not None


def _actionable_contract_value(text: str, field: str) -> str | None:
    match = re.search(rf"^{re.escape(field)}:[ \t]*(.*)$", text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    if value.lower() in NON_ACTIONABLE_CONTRACT_VALUES:
        return None
    return value


def _verification_command(root: Path, artifact: Path) -> str:
    relative = _relative(root, artifact)
    suffix = artifact.suffix.lower()
    if suffix == ".py":
        return f"python -m pytest {relative}"
    if suffix == ".js":
        return f"node {relative}"
    if suffix == ".ts":
        return f"npx tsx {relative}"
    if suffix == ".sh":
        return f"bash {relative}"
    if suffix == ".ps1":
        return f"pwsh -File {relative}"
    return relative


def _relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")
