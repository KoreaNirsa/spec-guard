---
name: specguard-workflow
description: Use when a user asks Codex to run or interpret SpecGuard workflows, including init, readiness review, implementation handoff, or optional PR Review setup. This skill orchestrates the existing specguard CLI and keeps heuristic low-mode SpecGuard Review as the default gate.
---

# SpecGuard Workflow

## Role

Act as a Codex workflow assistant around the existing `specguard` CLI. Treat the CLI as the source of truth for readiness review, benchmark behavior, PR review setup, artifact generation, test generation, contract generation, and implementation handoff.

## Boundaries

- Do not embed, fork, or reimplement SpecGuard engine logic in the plugin.
- Do not duplicate readiness review, benchmark, PR review, artifact-generation, test-generation, or contract-validation logic.
- Do not rewrite `spec.md` or other spec package files automatically.
- Do not run experimental auto-revision flows from the plugin workflow.
- Use Codex-assisted detail review only when the user explicitly requests it, and present it as advisory.
- Keep the default gate as the CLI heuristic path: `specguard run <package>`.

## Suggestion-Only Spec Refinement

The MVP plugin must not modify spec package files. When a user asks for help resolving readiness findings, provide proposals only:

1. Read findings from `readiness-review.json` or `readiness-review.md`.
2. Summarize Critical findings first without broadening feature scope.
3. For every suggested change, identify the addressed finding by severity and title.
4. Separate `SpecGuard evidence` from `Codex suggestion` so the user can see what came from the report and what is a proposed refinement.
5. Suggest target artifact and section, for example `spec.md` `## Acceptance Criteria`, but do not write the file.
6. Keep wording limited to behavior supported by the current spec package or by the finding. If a requirement, field, state, or error behavior is not supported by evidence, mark it as `Needs user decision` instead of inventing it.
7. Tell the user they must approve and make any product requirement changes before the suggestion can become implementation input.
8. After the user edits the spec manually, recommend rerunning `specguard run <path> --no-llm --no-follow-up`.

Use this proposal shape:

```text
Addressed finding: <Severity> - <Finding title>
SpecGuard evidence: <short evidence from readiness report or current spec>
Target: <artifact and section>
Codex suggestion: <plain-language proposed wording, not an applied patch>
Scope check: <why this stays within current intent, or Needs user decision>
Next step: User reviews/edits the spec, then reruns SpecGuard.
```

Do not emit an applied patch, call an edit tool, or invoke SpecGuard's experimental auto-revision flow from the plugin. Existing CLI auto-revision remains an explicit experimental CLI path with its own safeguards; it is not part of the plugin MVP.

## Heuristic-First Workflow

1. Confirm the current issue, requested scope, repository state, and target spec package before running commands.
2. Detect CLI availability with `specguard --help`. When working from the SpecGuard source checkout, `python -m cli.specguard --help` is an acceptable fallback.
3. Resolve the target package:
   - use the user-provided path when it contains `spec.md`;
   - otherwise use the current directory when it contains `spec.md`;
   - otherwise scan `specs/*/spec.md` and use the only match;
   - when multiple candidate packages exist, list them and ask the user to choose;
   - when no candidate package exists, report `missing_spec_package`.
4. Record the current time before invoking the run command so stale or missing reports can be distinguished after execution.
5. Run the default plugin command as `specguard run <path> --no-llm --no-follow-up`. This preserves the heuristic low-mode gate and avoids requiring a Codex or OpenAI provider.
6. If the user explicitly asks for provider-backed initial review, run `specguard run <path> --llm --no-follow-up` after confirming provider availability with `specguard auth status`.
7. If the user explicitly asks for Detail Review, use the CLI follow-up menu path: run `specguard run <path> --llm --follow-up`, choose the review-only Detail Review action, then read `readiness-review-detail.json` and `readiness-review-detail.md`. Detail Review is advisory and must not replace the default fast readiness report.
8. If an interactive follow-up menu cannot be driven in the current environment, report that Detail Review currently requires the CLI follow-up menu instead of pretending it ran.
9. Do not add `--llm`, run detail review, or install PR Review workflows unless the user explicitly asks for that behavior.
10. Read the result from structured files only. Use `readiness-review.json` as the machine result, `readiness-review.md` as the human report, and `implementation-output.md` as the handoff file when allowed.
11. Derive stale, validation-failure, and handoff states from the Plugin Result Contract. Do not scrape terminal logs for readiness state.
12. Report readiness status, Critical/Major/Minor finding counts, top findings, report paths, handoff availability, and next action.
13. For `not_ready`, summarize Critical findings first and propose scoped edits using the suggestion-only spec refinement format. Do not apply the edits automatically.
14. For `ready` or `ready_with_warnings`, summarize warnings and direct implementation work to the generated handoff when `implementation-output.md` exists.

## Failure Categories

- `missing_cli`: `specguard --help` and the source checkout fallback both fail. Tell the user to install SpecGuard or run from a checkout that supports `python -m cli.specguard`.
- `missing_spec_package`: no usable package path with `spec.md` was provided or discovered.
- `validation_failed_before_review`: the CLI exits before writing a fresh `readiness-review.json`.
- `stale_review`: the readiness JSON is older than current source artifacts or its reviewed artifact set differs from current authored Markdown.
- `missing_provider_for_llm`: the user requested `--llm`, but `specguard auth status` shows no usable provider.
- `timeout`: the CLI run exceeds the active command timeout. Report the command, whether it was heuristic or provider-backed, and the files that exist.
- `cli_execution_failed`: the CLI exits non-zero for a reason that is not represented by a fresh `not_ready` report or a known pre-review state.

## Commands

```bash
specguard init <feature>
specguard run specs/<feature>
specguard run specs/<feature> --no-llm --no-follow-up
specguard run specs/<feature> --llm
specguard actions install-pr-review
```

Ask before installing PR Review workflows because they write repository CI files. Treat `SpecGuard PR Review` as optional and advisory after implementation, not as the default readiness gate.

## Output

Return concise, user-facing results:

- command executed
- readiness status
- critical, major, and minor finding counts when available
- handoff allowed: yes/no
- paths to generated reports
- failure category when the run cannot produce a normal readiness result
- next action
- suggested spec changes, if any, as suggestions only
