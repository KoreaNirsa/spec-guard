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
12. Report readiness status, review level, Critical/Major/Minor finding counts, top findings by severity and title, report paths, handoff availability, and next action.
13. For `not_ready`, summarize Critical findings first and propose scoped edits using the suggestion-only spec refinement format. Do not apply the edits automatically.
14. For `ready` or `ready_with_warnings`, summarize warnings and direct implementation work to the generated handoff only when `implementation-output.md` exists.
15. If authored spec artifacts changed after the last report, report `stale_review`, restate previous findings and suggested clarifications as suggestions only, mark unclear behavior as `Needs user decision`, and ask the user to rerun `specguard run <path> --no-llm --no-follow-up`.
16. After the rerun completes, report only the fresh readiness result as current: ready, ready with warnings, or still blocked.

## Failure Categories

- `missing_cli`: `specguard --help` and the source checkout fallback both fail. Tell the user to install SpecGuard or run from a checkout that supports `python -m cli.specguard`.
- `missing_spec_package`: no usable package path with `spec.md` was provided or discovered.
- `validation_failed_before_review`: the CLI exits before writing a fresh `readiness-review.json`.
- `stale_review`: the readiness JSON is older than current source artifacts or its reviewed artifact set differs from current authored Markdown.
- `missing_provider_for_llm`: the user requested `--llm`, but `specguard auth status` shows no usable provider.
- `timeout`: the CLI run exceeds the active command timeout. Report the command, whether it was heuristic or provider-backed, and the files that exist.
- `cli_execution_failed`: the CLI exits non-zero for a reason that is not represented by a fresh `not_ready` report or a known pre-review state.

For `timeout` and `cli_execution_failed`, report `known_files` as diagnostics only, include the exact command, and give the next safe action. Report `relevant_files` only for current state files; do not direct users to `implementation-output.md` unless a fresh `ready` or `ready_with_warnings` JSON says implementation is allowed and the handoff file exists.

## Guided Rerun Loop

Use this loop after a user edits `spec.md`, `technical-design.md`, or another authored Markdown artifact:

1. Recheck stale status using the Plugin Result Contract before using any previous report.
2. If the report is stale, do not present it as the current readiness result.
3. Restate previous findings by severity and title, and show previous `fix` text only as a suggested clarification.
4. For unclear product behavior, say `Needs user decision` instead of inventing fields, states, ownership, error behavior, or acceptance criteria.
5. Tell the user that suggestions are not implementation input until the user updates the spec package and SpecGuard runs again.
6. Rerun `specguard run <path> --no-llm --no-follow-up` after the user updates the spec package.
7. Read the fresh `readiness-review.json` and report current status, finding counts, current report paths, handoff availability, and next action.
8. If the fresh result is `not_ready`, report it as still blocked and continue using the suggestion-only refinement boundary.

## CLI-Driven Grill Me Loop

Use this loop when the user asks to turn readiness findings into explicit product decisions:

1. Run or confirm `specguard run <path> --no-llm --no-follow-up` first.
2. Read `grill.json` and `grill.md`; do not scrape terminal output for finding data.
3. Ask questions in `question_order`, which starts with Critical and Major findings.
4. Store each user answer in `decisions/specguard-decisions.jsonl` before any patch step.
5. Treat only `source: user-confirmed` and `resolution: update-spec` as patchable.
6. Keep `defer`, `reject`, `mark-intentional`, and unconfirmed suggestions visible in the decision record, but do not modify spec content from them.
7. Use `specguard grill <path> plan` and `specguard grill <path> apply` for confirmed Markdown target patches; every applied edit must include the `SG-*` review id.
8. Run `specguard grill <path> verify` after patching. Report resolved, unresolved, deferred, and new findings from `decisions/specguard-rerun-comparison.json`.
9. Do not treat Grill me answers as implementation-ready requirements until they are recorded, patched into the spec, and the follow-up run reports a fresh `ready` or `ready_with_warnings` state.

## PR Review Setup Workflow

Use this workflow when the user asks for SpecGuard PR Review setup, for example `PR Review를 설정해줘` or `set up SpecGuard PR Review`.

1. Confirm repository context before making changes:
   - run `git status --short --branch`;
   - inspect `git remote -v` or equivalent repository metadata when available;
   - tell the user when no GitHub remote can be detected.
2. Confirm CLI availability:
   - run `specguard --help`;
   - when working from a SpecGuard source checkout, fall back to `python -m cli.specguard --help`;
   - if both fail, report `missing_cli` and explain that installing the Codex plugin does not install the SpecGuard CLI;
   - if the environment allows package installation and the user wants Codex to help, ask before running `pip install spec-guard`.
3. Ask before writing repository workflow files. State that `specguard actions install-pr-review` writes or keeps `.github/workflows/specguard-pr-review.yml`.
4. After the user confirms, run:

   ```bash
   specguard actions install-pr-review
   ```

5. Confirm whether `.github/workflows/specguard-pr-review.yml` was created, updated, or already existed. If it already exists and the user did not ask to overwrite it, do not force replacement.
6. Report the required secret separately from optional variables:
   - Required GitHub Actions secret: `SPECGUARD_OPENAI_API_KEY`
   - Optional repository variables: `SPECGUARD_PR_REVIEW_MODEL`, `SPECGUARD_REVIEW_SPEC_PATHS`
7. Preserve the secret boundary:
   - do not invent, generate, store, print, or commit API keys;
   - do not ask the user to put API keys in files;
   - do not echo an API key in terminal commands, logs, or final output;
   - if the user provides a key in chat, do not repeat it back.
8. When `gh` is installed and authenticated, offer a safe, user-approved registration path:
   - run `gh auth status` before proposing write commands;
   - for the secret, prefer `gh secret set SPECGUARD_OPENAI_API_KEY --repo <owner/name>` so the user can enter the value through GitHub CLI without the key appearing in command history;
   - for optional variables, use `gh variable set SPECGUARD_PR_REVIEW_MODEL --body <model> --repo <owner/name>` and `gh variable set SPECGUARD_REVIEW_SPEC_PATHS --body <paths> --repo <owner/name>` only after the user confirms the values;
   - if safe registration is not possible, stop before secret handling and give manual setup instructions.
9. When GitHub integration or `gh` authentication is unavailable, provide manual setup instructions:
   - commit and push `.github/workflows/specguard-pr-review.yml`;
   - open GitHub repository Settings > Secrets and variables > Actions;
   - add `SPECGUARD_OPENAI_API_KEY` as a repository secret;
   - optionally add `SPECGUARD_PR_REVIEW_MODEL` and `SPECGUARD_REVIEW_SPEC_PATHS` as repository variables.
10. End by reporting workflow path, repository remote if known, whether secret registration was completed or deferred, and the next commit/push step. Keep SpecGuard PR Review advisory and do not tell the user to make it required by default.

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
- top findings by severity and title, with Critical findings first for `not_ready`
- handoff allowed: yes/no
- paths to generated reports
- failure category when the run cannot produce a normal readiness result
- next action
- suggested spec changes, if any, as suggestions only
