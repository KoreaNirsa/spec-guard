from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from tools.contract_checker import CONTRACT_EXEMPTION_NAME, has_contract_exemption, has_openapi_paths
from tools.generation.verification_checker import verification_metadata
from tools.llm_client import describe_llm_client
from tools.progress import progress_activity
from tools.readiness_engine import review_artifact_paths
from tools.report_language import report_language_from_payload

LOW_TECHNICAL_DESIGN_MAX_OUTPUT_TOKENS = 1800
DEFAULT_TECHNICAL_DESIGN_MAX_OUTPUT_TOKENS = 3000
LOW_SUPPORTING_ARTIFACT_LIMITS = {
    "plan.md": 1200,
    "tasks.md": 800,
    "constitution.md": 800,
    "checklists/spec-readiness.md": 800,
}


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


def _supporting_spec_artifacts(path: Path, *, compact: bool = False) -> str:
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
            content = candidate.read_text(encoding="utf-8")
            if compact:
                content = _compact_supporting_artifact(relative_path, content)
            sections.append(f"# {relative_path}\n\n{content}")
    return "\n\n".join(sections) if sections else "No supporting spec package artifacts were provided."


def _compact_supporting_artifact(relative_path: str, content: str) -> str:
    limit = LOW_SUPPORTING_ARTIFACT_LIMITS.get(relative_path, 600)
    if len(content) <= limit:
        return content
    omitted = len(content) - limit
    return "\n".join([
        content[:limit].rstrip(),
        "",
        f"[SpecGuard low-mode technical design excerpt: {omitted} character(s) omitted. Use medium or high review level for full supporting context.]",
    ])


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
        "- NOT_READY SpecGuard Review findings block implementation handoff.",
        "",
    ])
    output.write_text(content, encoding="utf-8")
    return ArtifactWrite(output, created=True)


def generate_llm_technical_design(
    path: Path,
    llm_client: object,
    force: bool = False,
    review_level: str = "low",
) -> ArtifactWrite:
    output = path / "technical-design.md"
    if output.exists() and not force:
        return ArtifactWrite(output, created=False)

    discovery = (path / "discovery.md").read_text(encoding="utf-8")
    spec = (path / "spec.md").read_text(encoding="utf-8")
    low_mode = review_level.strip().lower() == "low"
    supporting_artifacts = _supporting_spec_artifacts(path, compact=low_mode)
    if low_mode:
        instructions = "\n".join([
            "You are SpecGuard's low-mode technical design generator.",
            "Generate a concise technical design for minimum implementation safety gating.",
            "SpecGuard is not a code generator. Do not write application code.",
            "Return ONLY Markdown.",
            "Do not perform broad architecture consulting or add future-scope design work.",
            "Only mark a blocker when the supplied spec package contains a concrete contradiction, missing ownership/auth decision, impossible state behavior, destructive side-effect ambiguity, or security hole that prevents safe implementation.",
            "Use this exact section structure:",
            f"# Technical Design: {path.name}",
            "## Architecture",
            "## Data Flow",
            "## State",
            "## Dependencies",
            "## Failure Handling",
            "## Implementation Blockers",
            "Keep the design compact, testable, and explicit about ownership, state, and failure boundaries.",
        ])
        max_output_tokens = LOW_TECHNICAL_DESIGN_MAX_OUTPUT_TOKENS
    else:
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
        max_output_tokens = DEFAULT_TECHNICAL_DESIGN_MAX_OUTPUT_TOKENS
    input_text = "\n\n".join([
        "# Discovery",
        discovery,
        "# Spec",
        spec,
        "# Supporting Spec Package Artifacts",
        supporting_artifacts,
    ])
    activity = (
        f"waiting for LLM technical design "
        f"({describe_llm_client(llm_client)}, {review_level.strip().lower() or 'low'}, {len(input_text)} chars)"
    )
    with progress_activity(activity):
        content = llm_client.generate_text(instructions, input_text, max_output_tokens=max_output_tokens)
    output.write_text(content, encoding="utf-8")
    return ArtifactWrite(output, created=True)


def ensure_contract(path: Path, force: bool = False) -> ArtifactWrite:
    contracts_dir = path / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    exemption = contracts_dir / CONTRACT_EXEMPTION_NAME
    if has_contract_exemption(contracts_dir):
        return ArtifactWrite(exemption, created=False)
    output = contracts_dir / "openapi.yaml"
    if output.exists():
        if not force or _has_concrete_contract_paths(output):
            return ArtifactWrite(output, created=False)

    spec = (path / "spec.md").read_text(encoding="utf-8")
    title = _title(path, spec)
    content = _spec_derived_openapi(path, spec, title)
    output.write_text(content, encoding="utf-8")
    return ArtifactWrite(output, created=True)


def _has_concrete_contract_paths(output: Path) -> bool:
    try:
        return has_openapi_paths(output)
    except Exception:
        return False


def _spec_derived_openapi(path: Path, spec: str, title: str) -> str:
    acceptance = _bullets(spec, "Acceptance Criteria")
    errors = _bullets(spec, "Error Cases")
    success_status = _success_status(acceptance)
    error_statuses = _error_statuses(errors)
    schema_prefix = _schema_prefix(title)

    lines = [
        "openapi: 3.1.0",
        "info:",
        f"  title: {_yaml_string(title + ' API')}",
        "  version: 0.1.0",
        "paths:",
        f"  /{path.name}:",
        "    post:",
        f"      summary: {_yaml_string('Execute ' + title)}",
        "      x-specguard-coverage:",
        "        acceptanceCriteria:",
    ]
    lines.extend(f"          - {_yaml_string(item)}" for item in (acceptance or ["Primary happy path satisfies acceptance criteria."]))
    lines.extend([
        "        errorCases:",
    ])
    lines.extend(f"          - {_yaml_string(item)}" for item in (errors or ["Invalid input is rejected with a documented error."]))
    lines.extend([
        "      requestBody:",
        "        required: true",
        "        content:",
        "          application/json:",
        "            schema:",
        f"              $ref: '#/components/schemas/{schema_prefix}Request'",
        "      responses:",
        f"        \"{success_status}\":",
        "          description: Success response for the approved acceptance criteria",
        "          content:",
        "            application/json:",
        "              schema:",
        f"                $ref: '#/components/schemas/{schema_prefix}Response'",
    ])
    for status, description in error_statuses:
        lines.extend([
            f"        \"{status}\":",
            f"          description: {_yaml_string(description)}",
            "          content:",
            "            application/json:",
            "              schema:",
            "                $ref: '#/components/schemas/ErrorResponse'",
        ])
    lines.extend([
        "components:",
        "  schemas:",
        f"    {schema_prefix}Request:",
        "      type: object",
        "      additionalProperties: true",
        f"    {schema_prefix}Response:",
        "      type: object",
        "      additionalProperties: true",
        "    ErrorResponse:",
        "      type: object",
        "      required:",
        "        - error_code",
        "        - message",
        "      properties:",
        "        error_code:",
        "          type: string",
        "        message:",
        "          type: string",
        "",
    ])
    return "\n".join(lines)


def _success_status(acceptance: list[str]) -> str:
    joined = " ".join(acceptance)
    match = re.search(r"\b(200|201|202|204)\b", joined)
    return match.group(1) if match else "200"


def _error_statuses(errors: list[str]) -> list[tuple[str, str]]:
    if not errors:
        return [("400", "Invalid input")]

    statuses: dict[str, str] = {}
    for error in errors:
        lowered = error.lower()
        if any(marker in lowered for marker in ("forbidden", "non-admin", "ownership", "wrong-workspace")):
            status = "403"
        elif any(marker in lowered for marker in ("unauthorized", "unknown user", "invalid password", "token")):
            status = "401"
        elif any(marker in lowered for marker in ("duplicate", "already", "conflict")):
            status = "409"
        elif "not found" in lowered:
            status = "404"
        elif any(marker in lowered for marker in ("rate", "too many", "throttle")):
            status = "429"
        else:
            status = "400"
        statuses.setdefault(status, error)
    return sorted(statuses.items())


def _schema_prefix(title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", title).title().replace(" ", "")
    return cleaned or "Feature"


def _yaml_string(text: str) -> str:
    return json.dumps(text)


def generate_implementation_output(path: Path, force: bool = True) -> ArtifactWrite:
    output = path / "implementation-output.md"
    if output.exists() and not force:
        return ArtifactWrite(output, created=False)

    approved_artifacts = _implementation_agent_artifacts(path)
    handoff_metadata = _implementation_handoff_metadata(path, approved_artifacts)
    report_language = handoff_metadata.get("report_language", {})
    if isinstance(report_language, dict) and report_language.get("code") == "ko":
        lines = _korean_implementation_output_lines(path, approved_artifacts, handoff_metadata)
        output.write_text("\n".join(lines), encoding="utf-8")
        return ArtifactWrite(output, created=True)

    lines = [
        f"# Implementation Output: {path.name}",
        "",
        "SpecGuard stops at an approved implementation handoff. It does not invoke Codex, Claude Code, or another coding agent as an internal pipeline stage.",
        "",
        "Use this feature folder as external handoff context for a coding agent only after the machine-readable readiness status below is `ready` or `ready_with_warnings`.",
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
        "## Artifact Priority",
        "",
        "- Primary implementation basis: `spec.md`, `technical-design.md`, `tests/`, and `contracts/`.",
        "- Intent context: `discovery.md`, `plan.md`, `tasks.md`, `constitution.md`, `checklists/`, and additional authored Markdown notes.",
        "- If input artifacts conflict or required behavior is missing, stop implementation, update the spec package, and rerun SpecGuard.",
        "",
        "## Copy/Paste Agent Prompt",
        "",
        "```text",
        f"You are implementing the approved SpecGuard package at {path.as_posix()}.",
        "Use implementation-output.md as the handoff entrypoint, then read every Agent Input Artifact listed in it before editing code.",
        "Implement only behavior that is specified by spec.md, technical-design.md, tests/, contracts/, or the listed authored intent artifacts.",
        "Do not invent missing product behavior, ownership rules, retries, errors, persistence details, or API fields. If required behavior is missing or contradictory, stop and ask for a spec update.",
        "Put generated application code under develop/<stack>/.",
        f"Run the verification command named in the handoff: {handoff_metadata['verification']['command'] or 'use the accepted verification artifact named in the handoff'}",
        "```",
        "",
        "## Verification",
        "",
        f"- Kind: `{handoff_metadata['verification']['kind']}`",
        f"- Artifact: `{handoff_metadata['verification']['artifact']}`",
        f"- Command: `{handoff_metadata['verification']['command'] or 'not specified'}`",
        "",
        "## SpecGuard-Only Artifacts",
        "",
        "- `readiness-review.md` and `readiness-review.json` are SpecGuard validation outputs, not implementation requirements.",
        "- `readiness-review-detail.md` and `readiness-review-detail.json` are optional detailed review outputs, not implementation requirements.",
        "- `.specguard/` cache and revision audit files are SpecGuard operational records.",
        "- Coding agents should treat the agent input artifacts as the implementation basis only after SpecGuard reports READY or READY_WITH_WARNINGS.",
        "",
        "## Output Location",
        "",
        "- Put generated application code under `develop/<stack>/`.",
        "- Examples: `develop/spring/`, `develop/react/`, `develop/fastapi/`.",
        "",
        "## Implementation Rules",
        "",
        "- Read every Agent Input Artifact before implementation.",
        "- Keep code aligned with `spec.md`, `technical-design.md`, `tests/`, and `contracts/`.",
        "- Use discovery and additional authored Markdown as intent context; do not override explicit spec or contract behavior with assumptions.",
        "- Implement or preserve the behavior described in `tests/`.",
        "- Keep API shape compatible with files under `contracts/`.",
        "- When implementation reveals missing behavior, update the spec and rerun SpecGuard.",
        "- Do not ask the coding agent to resolve blocking readiness findings or warning items by assumption.",
        "",
    ])
    output.write_text("\n".join(lines), encoding="utf-8")
    return ArtifactWrite(output, created=True)


def _korean_implementation_output_lines(
    path: Path,
    approved_artifacts: list[str],
    handoff_metadata: dict[str, object],
) -> list[str]:
    verification = handoff_metadata["verification"]
    assert isinstance(verification, dict)
    lines = [
        f"# 구현 인계: {path.name}",
        "",
        "SpecGuard는 승인된 구현 인계에서 멈추며 내부 pipeline 단계에서 별도의 코딩 에이전트를 호출하지 않습니다.",
        "",
        "아래 기계 판독 준비 상태가 `ready` 또는 `ready_with_warnings`인 경우에만 이 기능 폴더를 외부 구현 컨텍스트로 사용하세요.",
        "",
        "## 기계 판독 구현 인계",
        "",
        "```json",
        *json.dumps(handoff_metadata, indent=2, ensure_ascii=False).splitlines(),
        "```",
        "",
        "## 에이전트 입력 산출물",
        "",
    ]
    lines.extend(f"- `{artifact}`" for artifact in approved_artifacts)
    lines.extend([
        "",
        "## 산출물 우선순위",
        "",
        "- 주요 구현 기준: `spec.md`, `technical-design.md`, `tests/`, `contracts/`.",
        "- 의도 컨텍스트: `discovery.md`, `plan.md`, `tasks.md`, `constitution.md`, `checklists/`, 추가 authored Markdown.",
        "- 입력 산출물이 충돌하거나 필수 동작이 누락되면 구현을 중단하고 스펙 패키지를 수정한 뒤 SpecGuard를 다시 실행하세요.",
        "",
        "## 복사해서 사용할 에이전트 프롬프트",
        "",
        "```text",
        f"{path.as_posix()}의 승인된 SpecGuard 패키지를 구현하세요.",
        "implementation-output.md를 구현 인계 시작점으로 사용하고 파일을 수정하기 전에 모든 에이전트 입력 산출물을 읽으세요.",
        "spec.md, technical-design.md, tests/, contracts/ 또는 목록에 포함된 authored intent 파일에 명시된 동작만 구현하세요.",
        "누락된 제품 동작, 소유권 규칙, 재시도, 오류, 영속성 세부 사항 또는 API 필드를 추측하지 마세요. 필수 동작이 누락되거나 모순되면 중단하고 스펙 수정을 요청하세요.",
        "생성한 애플리케이션 코드는 develop/<stack>/ 아래에 두세요.",
        f"구현 인계에 지정된 검증 명령을 실행하세요: {verification.get('command') or '구현 인계에 지정된 검증 산출물을 사용하세요'}",
        "```",
        "",
        "## 검증",
        "",
        f"- 유형: `{verification.get('kind')}`",
        f"- 산출물: `{verification.get('artifact')}`",
        f"- 명령: `{verification.get('command') or '지정되지 않음'}`",
        "",
        "## SpecGuard 전용 산출물",
        "",
        "- `readiness-review.md`와 `readiness-review.json`은 검증 결과이며 구현 요구사항이 아닙니다.",
        "- `readiness-review-detail.md`와 `readiness-review-detail.json`은 선택적 상세 검토 결과이며 구현 요구사항이 아닙니다.",
        "- `.specguard/` 캐시와 revision audit 파일은 운영 기록입니다.",
        "- READY 또는 READY_WITH_WARNINGS인 경우에만 에이전트 입력 산출물을 구현 기준으로 사용하세요.",
        "",
        "## 출력 위치",
        "",
        "- 생성한 애플리케이션 코드는 `develop/<stack>/` 아래에 두세요.",
        "- 예: `develop/spring/`, `develop/react/`, `develop/fastapi/`.",
        "",
        "## 구현 규칙",
        "",
        "- 구현 전에 모든 에이전트 입력 산출물을 읽으세요.",
        "- 코드를 `spec.md`, `technical-design.md`, `tests/`, `contracts/`와 일치시키세요.",
        "- discovery와 추가 authored Markdown은 의도 컨텍스트로만 사용하고 명시적 스펙이나 계약을 추측으로 덮어쓰지 마세요.",
        "- `tests/`에 설명된 동작을 구현하거나 유지하세요.",
        "- API 형태를 `contracts/` 아래 파일과 호환되게 유지하세요.",
        "- 구현 중 동작 누락을 발견하면 스펙을 수정하고 SpecGuard를 다시 실행하세요.",
        "- 차단 항목이나 경고를 구현 에이전트가 추측으로 해결하도록 요청하지 마세요.",
        "",
    ])
    return lines


def _implementation_agent_artifacts(path: Path) -> list[str]:
    artifacts: list[str] = []
    seen: set[str] = set()

    def add(relative: Path) -> None:
        rendered = relative.as_posix()
        if rendered not in seen:
            seen.add(rendered)
            artifacts.append(rendered)

    for relative in review_artifact_paths(path):
        add(relative)

    tests_dir = path / "tests"
    if tests_dir.exists():
        for test in sorted(test for test in tests_dir.rglob("*.md") if test.is_file()):
            add(test.relative_to(path))

    contracts_dir = path / "contracts"
    if contracts_dir.exists():
        for contract in sorted(contract for contract in contracts_dir.rglob("*") if contract.is_file()):
            add(contract.relative_to(path))

    return artifacts


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

    readiness_summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    warning_findings = _handoff_warning_findings(report)
    allowed_statuses = {"ready", "ready_with_warnings"}
    return {
        "schema_version": "0.1",
        "implementation_boundary": "external_handoff",
        "readiness_status": readiness_status,
        "implementation_allowed": implementation_ready and readiness_status in allowed_statuses,
        "readiness_summary": readiness_summary,
        "readiness_warnings": warning_findings,
        "readiness_report": "readiness-review.json" if report_path.exists() else None,
        "report_language": report_language_from_payload(report).as_dict(),
        "approved_artifacts": approved_artifacts,
        "verification": verification_metadata(path),
    }


def _handoff_warning_findings(report: dict[str, object]) -> list[dict[str, object]]:
    issues = report.get("issues", [])
    if not isinstance(issues, list):
        return []

    warnings: list[dict[str, object]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity", ""))
        if severity not in {"Major", "Minor"}:
            continue
        warnings.append({
            "severity": severity,
            "title": issue.get("title", "Untitled issue"),
            "impact": issue.get("impact", "Not specified."),
            "fix": issue.get("fix", "Not specified."),
        })
    return warnings
