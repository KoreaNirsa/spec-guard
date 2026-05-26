# CLI-Driven Grill Me Loop

This document defines the supported workflow shape for a CLI-driven Grill me loop.

Related issue: #211
Related design: #194

## Purpose

SpecGuard already produces readiness findings before implementation. The Grill me loop should turn those findings into focused clarification questions, record user-confirmed decisions, patch only the confirmed spec content, and then rerun the CLI review.

Target loop:

```text
spec review -> Grill me questions -> decision record -> spec patch -> spec review rerun
```

## Responsibilities

| Layer | Responsibility |
| --- | --- |
| SpecGuard CLI | Produce deterministic review findings with stable machine fields. |
| Codex skill | Convert findings into focused spec-contract questions. |
| User | Confirm, defer, or reject each proposed decision. |
| Decision record | Store user-confirmed answers with traceability back to review findings. |
| Codex patch step | Update only spec content backed by confirmed decisions. |
| CLI rerun | Verify whether the patched spec resolves the original findings. |

The CLI remains the canonical review engine. The Codex skill must not duplicate SpecGuard review logic. Stable review ids are required so later decisions and reruns can point back to the same finding.

## CLI Commands

The current CLI loop is:

```bash
specguard run <package> --no-llm --no-follow-up
specguard grill <package> findings
specguard grill <package> ask
specguard grill <package> plan
specguard grill <package> apply
specguard grill <package> verify
```

`specguard run` also writes the companion Grill me finding artifacts described below. The `grill` commands are deterministic local commands and do not make LLM review the default gate.

## Review Finding Contract

SpecGuard exposes Grill me findings as companion files:

- `<package>/grill.json`
- `<package>/grill.md`

The current `readiness-review.json` contract is not replaced or migrated by this workflow.

The top-level `grill.json` payload includes a short `readiness_summary` so Codex can quickly explain why a package is `not_ready`, and `resolution_prompts` so users see copy-ready examples for each response type.

Minimum `grill.json` finding shape:

```json
{
  "id": "SG-001",
  "type": "missing-validation",
  "severity": "Critical",
  "source_location": {
    "path": "openapi.yaml",
    "line": 42,
    "review_path": "readiness-review.json#/issues/0"
  },
  "evidence": [
    "The email field exists in requestBody, but required and format constraints are not defined."
  ],
  "question": "SpecGuard found a spec-contract gap: \"Missing validation\". Please decide the rule the implementation must follow, using concrete API terms such as validation, authorization, ownership, error response, timeout, idempotency, or state transition when they apply. Suggested clarification: Define whether email is required and which format rule applies.",
  "suggested_clarification": "Define whether email is required and which format rule applies.",
  "allowed_resolution": ["update-spec", "mark-intentional", "defer", "reject"]
}
```

Required properties:

- `id` must be stable for the same finding in a given review result so decisions can link back to it.
- `severity` must preserve the review priority used by SpecGuard. The CLI asks Critical and Major questions first.
- `source_location` must point to the reviewed artifact and line when evidence can be mapped, and always includes `review_path` back to the source `readiness-review.json` issue.
- `evidence` must quote or summarize the reviewed source that caused the finding.
- `question` must be suitable for a Codex chat: not terse, not long, and technical enough to name API concepts while still explaining what the user needs to decide.
- `allowed_resolution` must constrain whether the user can update the spec, mark the gap intentional, defer it, or reject it.

## Grill Me Question Rules

The Codex skill should read structured findings and ask questions that resolve contract ambiguity. It should not invent missing behavior.

Good question areas:

- Required input fields.
- Validation rules.
- Response status codes.
- Error response shape.
- Authorization and ownership conditions.
- State transition rules.
- Retry, timeout, idempotency, or replay behavior.
- Conflicts with existing API contracts.

Questions must stay tied to a finding id. If one finding requires multiple decisions, the skill should ask separate questions and keep each answer linked to the same review id.

For every question, the chat should show response examples like:

- `update-spec`: `update-spec -> Server must enforce owner-scoped todo reads and writes. -> spec.md#Requirements`
- `mark-intentional`: `mark-intentional -> Public read access is intentional for this endpoint.`
- `defer`: `defer -> Product owner must decide the retention policy later.`
- `reject`: `reject -> This finding does not apply because the endpoint is internal-only.`

When the package is `not_ready`, the chat should also show the short problem summary before asking the first question, for example:

```text
Readiness: not_ready
Problem: Blocking readiness issue: Todo ownership boundary is unclear
Counts: Critical 1, Major 1, Minor 0
```

## Decision Record Contract

User answers must be stored as decisions before they can drive a patch. SpecGuard stores durable decision records at:

```text
<package>/decisions/specguard-decisions.jsonl
```

Minimum decision shape:

```json
{
  "review_id": "SG-001",
  "decision": "email is required and must be validated with RFC 5322-compatible email format rules.",
  "source": "user-confirmed",
  "resolution": "update-spec",
  "target": "openapi.yaml#/paths/~1users/post/requestBody"
}
```

Rules:

- `source` must be `user-confirmed` before the decision can patch a spec.
- `review_id` must match a finding id from the latest review result or an explicitly carried-forward unresolved finding.
- `target` must identify the artifact and location to patch.
- `resolution` must be one of the finding's allowed resolutions.
- Deferred or rejected answers must remain visible but must not modify spec content.

## Patch Rules

Codex may patch spec files only from confirmed decisions.

Patch requirements:

1. Read the decision record.
2. Select only decisions with `source: "user-confirmed"` and `resolution: "update-spec"`.
3. Patch only the target artifact and location named by the decision.
4. Preserve existing unrelated spec content.
5. Show the before/after diff.
6. Leave unresolved findings as unresolved decisions or TODOs instead of guessing.

The current `specguard grill apply` command applies confirmed `update-spec` decisions only to targeted Markdown headings such as `spec.md#Requirements`. Decisions for other targets remain in the decision record and patch plan until explicit target support exists.

Patch plans are written to:

```text
<package>/decisions/specguard-patch-plan.json
```

Forbidden patch behavior:

- Do not add fields, status codes, states, or product behavior that the user did not confirm.
- Do not convert deferred findings into requirements.
- Do not use broad Codex suggestions as implementation input.
- Do not skip the follow-up CLI review.

## Rerun And Verification

After patching, the workflow must rerun SpecGuard:

```bash
specguard run <package> --no-llm --no-follow-up
```

The rerun should compare the new review result with the decision record:

- Findings resolved by confirmed decisions should disappear or downgrade in the new review result.
- Remaining blockers should stay linked to the original or new finding ids.
- Deferred findings should remain documented and should not be treated as implementation-ready decisions.
- Implementation handoff can proceed only when the rerun reports `READY` or `READY_WITH_WARNINGS` under the active review level.

The rerun comparison is written to:

```text
<package>/decisions/specguard-rerun-comparison.json
```

## Non-Goals

- Do not make LLM review the default gate.
- Do not replace `readiness-review.json` without a schema migration.
- Do not patch OpenAPI or YAML targets without explicit target support.
- Do not treat Grill me answers as implementation requirements until they are recorded and patched into the spec.

## Current Guarantees

- `grill.json` uses schema version `0.1`.
- Stable review ids are generated from finding title, description, impact, fix, and evidence, not from display order alone.
- Decision records are append-only JSONL under `decisions/specguard-decisions.jsonl`.
- Deferred or rejected decisions are kept visible and excluded from spec patches.
- Every applied Markdown edit includes the originating `SG-*` review id in the inserted text.
- `specguard grill verify` reruns `specguard run <package> --no-llm --no-follow-up` and records resolved, unresolved, deferred, and new finding ids.
