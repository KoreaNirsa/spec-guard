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

## Workflow

1. Confirm the current issue, requested scope, repository state, and target spec package before running commands.
2. Check that the `specguard` CLI is available with `specguard --help` or `python -m cli.specguard --help`.
3. Run `specguard run <package>` for the default readiness gate unless the user explicitly requests another mode.
4. Use `--no-llm --no-follow-up` for deterministic scripted checks when automation or CI-style output is needed.
5. Use `--llm` only when the user explicitly asks for provider-backed review.
6. Read generated artifacts, especially `readiness-review.json`, `readiness-review.md`, and `implementation-output.md`.
7. Report the readiness status, blocking findings, generated artifact paths, and the next action.
8. For `NOT_READY`, summarize blockers and propose scoped edits for user review. Do not apply the edits automatically.
9. For `READY` or `READY_WITH_WARNINGS`, summarize warnings and direct implementation work to the generated handoff.

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
- paths to generated reports
- next action
- suggested spec changes, if any, as suggestions only
