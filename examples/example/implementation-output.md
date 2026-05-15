# Implementation Output: example

SpecGuard stops at an approved implementation handoff. It does not invoke Codex, Claude Code, or another coding agent as an internal pipeline stage.

Use this feature folder as external handoff context for a coding agent only after the machine-readable readiness status below is `ready` or `ready_with_warnings`.

## Machine-Readable Handoff

```json
{
  "schema_version": "0.1",
  "implementation_boundary": "external_handoff",
  "readiness_status": "ready_with_warnings",
  "implementation_allowed": true,
  "readiness_summary": {
    "critical": 0,
    "major": 0,
    "minor": 1
  },
  "readiness_warnings": [
    {
      "severity": "Minor",
      "title": "No obvious readiness triggers found",
      "impact": "Subtle domain-specific bugs may still exist.",
      "fix": "Run the strict SpecGuard Review prompt with a model and add human review before implementation."
    }
  ],
  "readiness_report": "readiness-review.json",
  "approved_artifacts": [
    "discovery.md",
    "spec.md",
    "technical-design.md",
    "tests/example.test.md",
    "contracts/openapi.yaml"
  ],
  "verification": {
    "kind": "markdown_scenarios",
    "artifact": "tests/example.test.md",
    "command": null,
    "strict_ready": false
  }
}
```

## Agent Input Artifacts

- `discovery.md`
- `spec.md`
- `technical-design.md`
- `tests/example.test.md`
- `contracts/openapi.yaml`

## Artifact Priority

- Primary implementation basis: `spec.md`, `technical-design.md`, `tests/`, and `contracts/`.
- Intent context: `discovery.md`, `plan.md`, `tasks.md`, `constitution.md`, `checklists/`, and additional authored Markdown notes.
- If input artifacts conflict or required behavior is missing, stop implementation, update the spec package, and rerun SpecGuard.

## Copy/Paste Agent Prompt

```text
You are implementing the approved SpecGuard package at examples/example.
Use implementation-output.md as the handoff entrypoint, then read every Agent Input Artifact listed in it before editing code.
Implement only behavior that is specified by spec.md, technical-design.md, tests/, contracts/, or the listed authored intent artifacts.
Do not invent missing product behavior, ownership rules, retries, errors, persistence details, or API fields. If required behavior is missing or contradictory, stop and ask for a spec update.
Put generated application code under develop/<stack>/.
Run the verification command named in the handoff: use the accepted verification artifact named in the handoff
```

## Verification

- Kind: `markdown_scenarios`
- Artifact: `tests/example.test.md`
- Command: `not specified`

## SpecGuard-Only Artifacts

- `readiness-review.md` and `readiness-review.json` are SpecGuard validation outputs, not implementation requirements.
- `readiness-review-detail.md` and `readiness-review-detail.json` are optional detailed review outputs, not implementation requirements.
- `.specguard/` cache and revision audit files are SpecGuard operational records.
- Coding agents should treat the agent input artifacts as the implementation basis only after SpecGuard reports READY or READY_WITH_WARNINGS.

## Output Location

- Put generated application code under `develop/<stack>/`.
- Examples: `develop/spring/`, `develop/react/`, `develop/fastapi/`.

## Implementation Rules

- Read every Agent Input Artifact before implementation.
- Keep code aligned with `spec.md`, `technical-design.md`, `tests/`, and `contracts/`.
- Use discovery and additional authored Markdown as intent context; do not override explicit spec or contract behavior with assumptions.
- Implement or preserve the behavior described in `tests/`.
- Keep API shape compatible with files under `contracts/`.
- When implementation reveals missing behavior, update the spec and rerun SpecGuard.
- Do not ask the coding agent to resolve blocking readiness findings or warning items by assumption.
