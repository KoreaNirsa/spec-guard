# Plugin Result Contract

This page defines the structured SpecGuard result contract that Codex plugin workflows can rely on. It is intentionally scoped to files produced by the existing `specguard` CLI. Plugin consumers must not scrape terminal output to determine readiness state.

## Consumer Flow

1. Record the time before invoking the CLI.
2. Run `specguard run <package>` with the requested flags.
3. Load `<package>/readiness-review.json` as the machine-readable result.
4. Treat `<package>/readiness-review.md` as the human report for display or links.
5. Treat `<package>/implementation-output.md` as the implementation handoff only when the JSON report says implementation is ready and the file exists.
6. If the CLI exits before producing a fresh readiness JSON report, handle it as a validation or pre-review pipeline failure instead of parsing terminal text.

## Stable Readiness JSON Fields

`readiness-review.json` currently uses `schema_version: "0.1"`. Plugin consumers may rely on the fields below for `0.1` reports.

| JSON path | Required | Stable use |
| --- | --- | --- |
| `schema_version` | yes | Contract version for the readiness report shape. |
| `review_mode` | yes | Review phase. Current values are `initial` and `verification`. |
| `review_level` | yes | Gate depth. Current values are `low`, `medium`, and `high`. |
| `blocked` | yes | Boolean convenience flag. `true` means implementation must not proceed. |
| `readiness.status` | yes | Canonical readiness status: `ready`, `ready_with_warnings`, or `not_ready`. |
| `readiness.implementation_ready` | yes | Boolean readiness decision for implementation handoff. |
| `readiness.criteria` | yes | Threshold metadata for the active review level. |
| `summary.critical` | yes | Critical finding count. |
| `summary.major` | yes | Major finding count. |
| `summary.minor` | yes | Minor finding count. |
| `issues[]` | yes | Ordered readiness findings for user-facing summaries. |
| `input.artifact_count` | yes | Count of authored source artifacts reviewed by SpecGuard. |
| `input.total_characters` | yes | Total character count of the reviewed source artifacts. |
| `input.artifacts[]` | yes | Reviewed source artifact paths and character counts. |
| `review_input` | no | LLM or compact-review input summary when available. |
| `cache` | no | LLM readiness-review cache diagnostics when cache is enabled. |

Each `issues[]` item exposes the stable fields `severity`, `title`, `description`, `impact`, and `fix`. `severity` is one of `Critical`, `Major`, or `Minor`. An issue may also include optional `evidence[]` excerpts when a deterministic finding is grounded in specific authored source text.

`prompt_mode`, exact character counts, cache fingerprints, cache keys, and local cache directories are diagnostic fields. They are safe to display for troubleshooting, but plugin UX must not require exact values or path formats from those diagnostics.

## Status Interpretation

| `readiness.status` | `blocked` | Handoff rule |
| --- | --- | --- |
| `ready` | `false` | Implementation may proceed when `implementation-output.md` exists. |
| `ready_with_warnings` | `false` | Implementation may proceed when `implementation-output.md` exists; show warning findings from `issues[]`. |
| `not_ready` | `true` | Implementation is blocked; summarize Critical findings first and propose user-reviewed spec edits. |

Handoff availability is derived, not read from terminal output:

```text
handoff_available =
  readiness.status in {ready, ready_with_warnings}
  and readiness.implementation_ready is true
  and <package>/implementation-output.md exists
```

If the report is ready but `implementation-output.md` is missing, the plugin should tell the user to rerun the full `specguard run <package>` pipeline. This can happen when a readiness review was run without completing the implementation handoff stage.

## Plugin Readiness Summary UX

Plugin-facing summaries should be concise and generated only from stable readiness JSON fields plus generated file existence. They should not parse terminal output or depend on exact prose inside finding descriptions.

A summary should include:

- readiness status from `readiness.status`
- review level from `review_level`
- Critical, Major, and Minor counts from `summary`
- handoff availability from the derived rule above
- top findings using each issue's `severity` and `title`
- report references for `readiness-review.json` and `readiness-review.md` when present
- `implementation-output.md` only when handoff is available
- a next action derived from the resolved readiness state

For `not_ready`, show Critical findings first even when the JSON issue order includes other severities first. For `ready_with_warnings`, explain that implementation may proceed only when `implementation-output.md` exists and the JSON has `readiness.implementation_ready: true`; otherwise tell the user to rerun the full pipeline before implementation starts.

The full Markdown and JSON reports remain the source for detailed finding prose, impacts, fixes, and evidence. Plugin tests should assert the summary fields and ordering rules, not full-prose snapshots of individual findings.

## Guided Plugin Rerun Loop

When a user edits authored spec artifacts after a readiness report was generated, the plugin must treat the old report as stale until SpecGuard runs again. The plugin may restate previous findings and `fix` text from `issues[]`, but only as suggestions for the user's next spec edit.

The stale rerun guidance should include:

- `state: stale_review`
- the stale reason from the source/report comparison
- previous `readiness-review.json` and `readiness-review.md` paths when present
- previous findings by severity and title
- suggested clarification text from the previous finding `fix`
- a scope check that says `Needs user decision` when product behavior is unclear
- the rerun command: `specguard run <package> --no-llm --no-follow-up`

Previous findings, suggested clarification text, and Codex-authored wording are not implementation input. They become implementation input only after the user updates the spec package and a fresh `specguard run <package> --no-llm --no-follow-up` result confirms the current readiness state.

After rerun, the plugin should ignore stale guidance as the current result and report the fresh `readiness-review.json` state. Rerun output should include the current status, Critical/Major/Minor counts, current report paths, handoff availability, and next action. A fresh `readiness.status: "not_ready"` should be reported as still blocked.

## Grill Me Finding And Decision Contract

`specguard run <package>` writes companion Grill me artifacts without replacing `readiness-review.json`:

- `<package>/grill.json`
- `<package>/grill.md`

Plugin consumers may rely on these `grill.json` fields for schema version `0.1`:

| JSON path | Stable use |
| --- | --- |
| `schema_version` | Contract version for the Grill me companion artifact. |
| `source_report` | Path to the `readiness-review.json` report used to build the findings. |
| `decision_record_path` | Path where user decisions are stored. |
| `readiness_status` | Readiness status from the source report. |
| `readiness_summary` | Short status, Critical/Major/Minor counts, and a concise problem summary for `not_ready` chats. |
| `resolution_prompts` | Copy-ready example prompts for `update-spec`, `mark-intentional`, `defer`, and `reject`. |
| `findings[]` | Structured findings ordered for Grill me consumption. |
| `question_order[]` | Finding ids in the order the CLI should ask questions. |

Each `findings[]` item includes a stable `id`, `type`, `severity`, `title`, `evidence[]`, `source_location`, `question`, `suggested_clarification`, and `allowed_resolution[]`. `source_location.review_path` links back to the original `readiness-review.json#/issues/<index>` entry. The CLI asks Critical and Major findings before Minor findings.

Question text should be written for a Codex chat: specific enough to use API terms such as validation, authorization, ownership, error response, timeout, idempotency, or state transition, but short enough that the user can answer directly. When `readiness_status` is `not_ready`, plugin consumers should show `readiness_summary.problem` before asking the first Grill me question.

User answers are append-only JSONL records at:

```text
<package>/decisions/specguard-decisions.jsonl
```

A decision may patch spec content only when `source: "user-confirmed"` and `resolution: "update-spec"`. Deferred, rejected, unconfirmed, or suggestion-only answers must remain visible in the decision record but must not modify spec files. Patch plans are written to `decisions/specguard-patch-plan.json`, and rerun comparisons are written to `decisions/specguard-rerun-comparison.json`.

Every applied Markdown spec edit must include the originating `SG-*` review id in the inserted text. After patching, the workflow must rerun:

```bash
specguard run <package> --no-llm --no-follow-up
```

The comparison must report resolved, unresolved, deferred, and new finding ids before implementation handoff can proceed.

## Validation Failure vs Readiness Failure

A readiness failure has a fresh `readiness-review.json` with `readiness.status: "not_ready"`. In that case, the plugin should read `summary` and `issues[]`.

A validation or pre-review pipeline failure occurs before SpecGuard Review can write a fresh readiness report. Examples include invalid `discovery.md`, invalid `spec.md`, or invalid `technical-design.md`. The plugin should identify this without terminal parsing:

- if no `readiness-review.json` exists after the run, treat the package as `validation_failed_before_review`;
- if `readiness-review.json` exists but is older than reviewed source artifacts, treat it as `stale_review`;
- if the CLI exits non-zero and the report was not updated during the run, do not reuse the old readiness status as the current result.

When running inside the SpecGuard Python codebase, `tools.post_run.readiness_report_stale_reason(feature_dir)` implements the source stale check. External plugin consumers should use the same rule:

1. Rebuild the current source artifact set by scanning authored Markdown under the package and excluding generated paths listed below.
2. Compare that current source set to `input.artifacts[].path`; any new or removed source artifact means `stale_review`.
3. Compare `readiness-review.json` mtime with every current source artifact mtime; any newer source artifact means `stale_review`.

Do not rely only on `input.artifacts[].path` for stale detection because that list comes from the previous review and cannot include newly added source files.

## Source Artifacts

`input.artifacts[]` contains authored Markdown source artifacts reviewed by SpecGuard. Generated SpecGuard artifacts are not source inputs for review and must not be treated as implementation requirements.

Generated outputs excluded from review input include:

- `readiness-review.md`
- `readiness-review.json`
- `readiness-review-detail.md`
- `readiness-review-detail.json`
- `implementation-output.md`
- `spec.proposed.md`
- `grill.md`
- `grill.json`
- `.specguard/`
- `contracts/`
- `tests/`

Plugin consumers should display generated outputs as reports or handoff files only. They should not merge those paths into the reviewed source artifact list.

## Cache Diagnostics

The optional `cache` object appears for LLM-backed SpecGuard Review runs. Stable display fields are:

- `enabled`
- `hit`
- `stored`
- `miss_reason`
- `review_mode`
- `review_level`
- `provider`
- `model`
- `prompt_version`

Fields such as `cache_key`, `cache_key_prefix`, `input_fingerprint`, `instructions_fingerprint`, `artifact_fingerprint`, and `cache_dir` are internal diagnostics. They can explain why a review was reused or refreshed, but plugin flows must not depend on their exact values.

## Review Input Diagnostics

The optional `review_input` object explains how much source context was sent to the active review path. Stable display fields are:

- `mode`
- `review_level`
- `artifact_count`
- `total_characters`
- `artifacts[]`
- `fallback_reason`, when present

Plugin consumers should use `input.artifacts[]` as the reviewed source artifact list. `review_input.artifacts[]` can be a compact or delta subset and is not the complete source contract.

## Minimum Consumer States

Plugin consumers should handle these states without terminal output parsing:

- `ready`
- `ready_with_warnings`
- `not_ready`
- `stale_review`
- `validation_failed_before_review`

The first three states come from a fresh `readiness-review.json`. The last two are derived from file presence and mtimes around the CLI invocation.

## Plugin Run State Resolution

Plugin workflows should resolve run state in this order:

1. Preflight failures: `missing_cli`, `missing_spec_package`, or `missing_provider_for_llm`.
2. Command timeout: `timeout`.
3. Missing fresh readiness JSON after a run: `validation_failed_before_review`.
4. Source/report mismatch from the stale check above: `stale_review`.
5. Fresh readiness JSON states: `ready`, `ready_with_warnings`, or `not_ready`.
6. Any other non-zero CLI exit that is not represented by a fresh `not_ready` report or known pre-review state: `cli_execution_failed`.

The run state payload should include:

- `state`: the plugin-facing state.
- `command`: the exact command attempted.
- `known_files`: generated SpecGuard files that exist, even when they are stale or incomplete.
- `relevant_files`: generated SpecGuard files that are current and relevant to the resolved state.
- `next_action`: the safest user action after the state is resolved.

For `timeout` and `cli_execution_failed`, include the attempted command, known generated files, and a next safe action. Do not point to `implementation-output.md` unless the run resolved to `ready` or `ready_with_warnings`, the JSON has `readiness.implementation_ready: true`, and the file exists.

| State | Trigger | Relevant files |
| --- | --- | --- |
| `ready` | Fresh JSON has `readiness.status: "ready"`. | `readiness-review.json`, `readiness-review.md` when present, and `implementation-output.md` only when handoff is available. |
| `ready_with_warnings` | Fresh JSON has `readiness.status: "ready_with_warnings"`. | Same as `ready`; also show warning findings from `issues[]`. |
| `not_ready` | Fresh JSON has `readiness.status: "not_ready"` or `blocked: true`. | `readiness-review.json` and `readiness-review.md` when present. Never use `implementation-output.md` as current handoff. |
| `stale_review` | Current authored source files differ from `input.artifacts[]`, or a current source file is newer than the JSON report. | No current result files. Existing generated files are known files only. |
| `validation_failed_before_review` | The CLI exits before a fresh readiness JSON exists or updates. | No current result files. Existing generated files are known files only. |
| `missing_cli` | Neither `specguard --help` nor the source checkout fallback works. | None. |
| `missing_spec_package` | No package directory with `spec.md` is available. | Existing generated files are known files only, if any. |
| `missing_provider_for_llm` | Provider-backed review was explicitly requested but `specguard auth status` is not usable. | Existing generated files are known files only, if any. |
| `timeout` | The active CLI command exceeds the configured timeout. | Existing generated files are known files only until a fresh run completes. |
| `cli_execution_failed` | The CLI exits non-zero for a reason not covered by the states above. | Existing generated files are known files only until a fresh run completes. |
