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

Each `issues[]` item exposes the stable fields `severity`, `title`, `description`, `impact`, and `fix`. `severity` is one of `Critical`, `Major`, or `Minor`.

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
