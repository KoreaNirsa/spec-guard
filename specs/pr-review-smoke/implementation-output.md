# Implementation Output: PR Review Smoke

SpecGuard stops at an approved implementation handoff. It does not invoke Codex, Claude Code, or another coding agent as an internal pipeline stage.

Use this feature folder as external handoff context for a coding agent only after the machine-readable readiness status below is `ready`.

## Machine-Readable Handoff

```json
{
  "schema_version": "0.1",
  "implementation_boundary": "external_handoff",
  "readiness_status": "ready",
  "implementation_allowed": true,
  "readiness_report": "readiness-review.json",
  "approved_artifacts": [
    "spec.md",
    "technical-design.md",
    "tests/verification-contract.md",
    "contracts/openapi.yaml"
  ],
  "verification": {
    "kind": "accepted_contract",
    "artifact": "tests/verification-contract.md",
    "command": "python -m pytest tests/test_notes_contract.py",
    "strict_ready": true
  }
}
```

## Agent Input Artifacts

- `spec.md`
- `technical-design.md`
- `tests/verification-contract.md`
- `contracts/openapi.yaml`

## Verification

- Kind: `accepted_contract`
- Artifact: `tests/verification-contract.md`
- Command: `python -m pytest tests/test_notes_contract.py`

## Implementation Rules

- Keep note reads scoped to the authenticated owner id.
- Do not return cross-owner notes.
- Missing owner id must return the documented unauthorized error.
