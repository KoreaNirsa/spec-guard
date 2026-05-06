from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from tools.contract_checker import has_openapi_paths


@dataclass(frozen=True)
class ArtifactWrite:
    path: Path
    created: bool


def _section(content: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _bullets(content: str, heading: str) -> list[str]:
    section = _section(content, heading)
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            items.append(stripped[5:].strip())
        elif stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _paragraph(content: str, heading: str, fallback: str) -> str:
    section = _section(content, heading)
    for line in section.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped.lstrip("- ").strip()
    return fallback


def _title(path: Path, spec: str) -> str:
    first_line = next((line for line in spec.splitlines() if line.startswith("# ")), "")
    if ":" in first_line:
        return first_line.split(":", 1)[1].strip()
    if first_line:
        return first_line.lstrip("# ").strip()
    return " ".join(part.capitalize() for part in path.name.split("-"))


def _supporting_spec_artifacts(path: Path) -> str:
    candidates = [
        path / "plan.md",
        path / "tasks.md",
        path / "constitution.md",
        path / "checklists" / "spec-readiness.md",
    ]
    sections: list[str] = []
    for candidate in candidates:
        if candidate.exists():
            relative = candidate.relative_to(path)
            relative_path = str(relative).replace("\\", "/")
            sections.append(f"# {relative_path}\n\n{candidate.read_text(encoding='utf-8')}")
    return "\n\n".join(sections) if sections else "No supporting spec package artifacts were provided."


def generate_technical_design(path: Path, force: bool = False) -> ArtifactWrite:
    output = path / "technical-design.md"
    if output.exists() and not force:
        return ArtifactWrite(output, created=False)

    spec_path = path / "spec.md"
    spec = spec_path.read_text(encoding="utf-8")
    title = _title(path, spec)
    requirements = _bullets(spec, "Requirements") or _bullets(spec, "Functional Requirements")
    acceptance = _bullets(spec, "Acceptance Criteria")
    errors = _bullets(spec, "Error Cases")
    entities = _bullets(spec, "Key Entities")
    problem = _paragraph(spec, "Problem", f"Implement {title} according to the approved spec.")

    requirement_summary = "; ".join(requirements[:3]) if requirements else "Use the spec requirements as the implementation boundary."
    acceptance_summary = "; ".join(acceptance[:3]) if acceptance else "Acceptance criteria define readiness."
    error_summary = "; ".join(errors[:3]) if errors else "Invalid input and invalid state are rejected."
    entity_summary = "; ".join(entities[:3]) if entities else "Feature state and request data are explicit implementation inputs."

    content = "\n".join([
        f"# Technical Design: {title}",
        "",
        "## Architecture",
        "",
        f"- Feature boundary: {title}.",
        f"- Intent source: {problem}",
        f"- Application layer: Coordinates validation, state changes, and responses for {title}.",
        "- Validation layer: Converts acceptance criteria and error cases into executable checks.",
        "- Contract boundary: API or integration shape is captured under `contracts/`.",
        "",
        "## Data Flow",
        "",
        "1. Caller sends a request for the feature.",
        "2. The system validates required input, authorization, and state.",
        "3. The application layer performs the operation defined by the spec.",
        "4. The system returns a success response or a documented error.",
        f"5. Acceptance focus: {acceptance_summary}",
        "",
        "## State",
        "",
        "- Initial state: Request received and not yet validated.",
        "- Valid states: Accepted, rejected, completed, failed.",
        "- Invalid states: Unauthorized, malformed, conflicting, or unsupported request.",
        "- Terminal state: Success response, documented error response, or blocked implementation issue.",
        "",
        "## Dependencies",
        "",
        "- Source spec: `spec.md`.",
        f"- Requirement focus: {requirement_summary}",
        f"- Entity focus: {entity_summary}",
        "- Test scenarios: Generated under `tests/` after SpecGuard Review passes.",
        "- Contract: Generated under `contracts/` after SpecGuard Review passes.",
        "",
        "## Failure Handling",
        "",
        f"- Expected failures: {error_summary}",
        "- Invalid input returns a clear error.",
        "- Unauthorized access is rejected before state change.",
        "- Ambiguous behavior becomes a spec update instead of implementation guesswork.",
        "- Critical or Major Readiness Findings block implementation handoff.",
        "",
    ])
    output.write_text(content, encoding="utf-8")
    return ArtifactWrite(output, created=True)


def generate_llm_technical_design(path: Path, llm_client: object, force: bool = False) -> ArtifactWrite:
    output = path / "technical-design.md"
    if output.exists() and not force:
        return ArtifactWrite(output, created=False)

    discovery = (path / "discovery.md").read_text(encoding="utf-8")
    spec = (path / "spec.md").read_text(encoding="utf-8")
    supporting_artifacts = _supporting_spec_artifacts(path)
    instructions = "\n".join([
        "You are SpecGuard's technical design generator.",
        "Generate a technical design from the full SpecGuard spec package.",
        "SpecGuard is not a code generator. Do not write application code.",
        "Return ONLY Markdown.",
        "Do not resolve contradictions by inventing behavior or filling gaps with assumptions.",
        "When discovery.md, spec.md, plan.md, tasks.md, constitution.md, or checklists conflict or omit implementation-critical details, mark the item as a blocker that must be clarified in the spec package before implementation.",
        "Use TODO or Blocker language only for unresolved clarification needs, and do not present unresolved blockers as implementation-ready design decisions.",
        "Use this exact section structure:",
        f"# Technical Design: {path.name}",
        "## Architecture",
        "## Data Flow",
        "## State",
        "## Dependencies",
        "## Failure Handling",
        "## Implementation Blockers",
        "Keep the design implementation-ready, testable, and explicit about ownership, state, and failure boundaries.",
    ])
    input_text = "\n\n".join([
        "# Discovery",
        discovery,
        "# Spec",
        spec,
        "# Supporting Spec Package Artifacts",
        supporting_artifacts,
    ])
    output.write_text(llm_client.generate_text(instructions, input_text, max_output_tokens=3000), encoding="utf-8")
    return ArtifactWrite(output, created=True)


def ensure_contract(path: Path, force: bool = False) -> ArtifactWrite:
    contracts_dir = path / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    output = contracts_dir / "openapi.yaml"
    if output.exists():
        if not force or _has_concrete_contract_paths(output):
            return ArtifactWrite(output, created=False)

    spec = (path / "spec.md").read_text(encoding="utf-8")
    title = _title(path, spec)
    content = "\n".join([
        "openapi: 3.1.0",
        "info:",
        f"  title: {title} API",
        "  version: 0.1.0",
        "x-specguard-blocker: Define concrete API paths, operations, responses, and error schemas before implementation.",
        "paths: {}",
        "",
    ])
    output.write_text(content, encoding="utf-8")
    return ArtifactWrite(output, created=True)


def _has_concrete_contract_paths(output: Path) -> bool:
    try:
        return has_openapi_paths(output)
    except Exception:
        return False


def generate_implementation_output(path: Path, force: bool = True) -> ArtifactWrite:
    output = path / "implementation-output.md"
    if output.exists() and not force:
        return ArtifactWrite(output, created=False)

    test_files = sorted((path / "tests").glob("*.md")) if (path / "tests").exists() else []
    contract_files = sorted((path / "contracts").glob("*")) if (path / "contracts").exists() else []
    agent_artifacts = [
        "spec.md",
        "plan.md",
        "tasks.md",
        "constitution.md",
        "checklists/spec-readiness.md",
        "technical-design.md",
    ]
    approved_artifacts = [artifact for artifact in agent_artifacts if (path / artifact).exists()]
    approved_artifacts.extend(f"tests/{test.name}" for test in test_files)
    approved_artifacts.extend(f"contracts/{contract.name}" for contract in contract_files if contract.is_file())
    handoff_metadata = _implementation_handoff_metadata(path, approved_artifacts)
    lines = [
        f"# Implementation Output: {path.name}",
        "",
        "SpecGuard stops at an approved implementation handoff. It does not invoke Codex, Claude Code, or another coding agent as an internal pipeline stage.",
        "",
        "Use this feature folder as external handoff context for a coding agent only after the machine-readable readiness status below is `ready`.",
        "",
        "## Machine-Readable Handoff",
        "",
        "```json",
        *json.dumps(handoff_metadata, indent=2).splitlines(),
        "```",
        "",
        "## Agent Input Artifacts",
        "",
    ]
    lines.extend(f"- `{artifact}`" for artifact in approved_artifacts)
    lines.extend([
        "",
        "## SpecGuard-Only Artifacts",
        "",
        "- `discovery.md` is for SpecGuard discovery and user refinement.",
        "- `readiness-review.md` and `readiness-review.json` are for SpecGuard adversarial validation.",
        "- Coding agents should treat the agent input artifacts as the implementation basis only after SpecGuard reports READY.",
        "",
        "## Output Location",
        "",
        "- Put generated application code under `develop/<stack>/`.",
        "- Examples: `develop/spring/`, `develop/react/`, `develop/fastapi/`.",
        "",
        "## Implementation Rules",
        "",
        "- Keep code aligned with `spec.md` and `technical-design.md`.",
        "- Implement or preserve the behavior described in `tests/`.",
        "- Keep API shape compatible with files under `contracts/`.",
        "- When implementation reveals missing behavior, update the spec and rerun SpecGuard.",
        "- Do not ask the coding agent to resolve Critical or Major readiness blockers by assumption.",
        "",
    ])
    output.write_text("\n".join(lines), encoding="utf-8")
    return ArtifactWrite(output, created=True)


def _implementation_handoff_metadata(path: Path, approved_artifacts: list[str]) -> dict[str, object]:
    report_path = path / "readiness-review.json"
    report: dict[str, object] = {}
    if report_path.exists():
        try:
            loaded = json.loads(report_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                report = loaded
        except json.JSONDecodeError:
            report = {}

    readiness = report.get("readiness", {})
    readiness_status = "unknown"
    implementation_ready = False
    if isinstance(readiness, dict):
        readiness_status = str(readiness.get("status") or "unknown")
        implementation_ready = bool(readiness.get("implementation_ready"))

    return {
        "schema_version": "0.1",
        "implementation_boundary": "external_handoff",
        "readiness_status": readiness_status,
        "implementation_allowed": implementation_ready and readiness_status == "ready",
        "readiness_report": "readiness-review.json" if report_path.exists() else None,
        "approved_artifacts": approved_artifacts,
    }
