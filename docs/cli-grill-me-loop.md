# CLI-Driven Grill Me Loop Design

This document defines the planned workflow shape for a CLI-driven Grill me loop. It is a design contract for future implementation, not a current supported plugin feature.

Related issue: #194

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

## Review Finding Contract

Future implementation should expose a stable structured review format for Grill me consumption. This can be a schema-versioned extension of `readiness-review.json` or a companion file. The current `readiness-review.json` contract is not changed by this design.

Minimum finding shape:

```json
{
  "id": "SG-001",
  "type": "missing-validation",
  "severity": "blocker",
  "spec_file": "openapi.yaml",
  "location": {
    "path": "/users",
    "method": "post",
    "field": "email"
  },
  "evidence": "The email field exists in requestBody, but required and format constraints are not defined.",
  "question": "Is email required? Which validation rule should be used for its format?",
  "allowed_resolution": ["update-spec", "mark-intentional", "defer"]
}
```

Required properties:

- `id` must be stable for the same finding in a given review result so decisions can link back to it.
- `severity` must preserve the review priority used by SpecGuard. The Codex skill should ask blocker and high-severity questions first.
- `spec_file` and `location` must point to the reviewed artifact or contract location when known.
- `evidence` must quote or summarize the reviewed source that caused the finding.
- `question` must ask for a spec-contract decision, not an implementation design.
- `allowed_resolution` must constrain whether the user can update the spec, mark the gap intentional, or defer it.

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

## Decision Record Contract

User answers must be stored as decisions before they can drive a patch. A future implementation should use a durable record under the spec package, for example `decisions/specguard-decisions.jsonl` or another explicit reviewed decision artifact.

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

## Non-Goals

- Do not implement the CLI command or Codex skill in this design issue.
- Do not make LLM review the default gate.
- Do not replace `readiness-review.json` without a schema migration.
- Do not make automatic spec rewriting part of the plugin MVP.
- Do not treat Grill me answers as implementation requirements until they are recorded and patched into the spec.

## Implementation Prerequisites

Before implementing this workflow, define and test:

- The schema version and file path for Grill me review findings.
- Stable review id generation rules.
- The decision record storage path and schema.
- How to represent OpenAPI, YAML, and Markdown target locations.
- How a patch plan maps confirmed decisions to file edits.
- How rerun results map resolved, unresolved, deferred, and new findings.
