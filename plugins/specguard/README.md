# SpecGuard Codex Plugin

This plugin is a Codex workflow scaffold for SpecGuard. It helps Codex locate spec packages, run the existing `specguard` CLI, read generated readiness artifacts, and summarize the next action for the user.

## Scope

- Use the existing `specguard` CLI as the canonical engine.
- Keep the default gate as `specguard run <package>` with heuristic low-mode SpecGuard Review.
- Treat Codex-assisted detail review as optional and advisory unless explicitly requested.
- Provide summaries and suggestions only; do not rewrite spec files or apply fixes automatically.
- Do not duplicate readiness review, benchmark, PR review, artifact-generation, or contract-validation logic inside the plugin.

## Typical Workflow

1. Identify the current issue, repository state, and target spec package.
2. Detect `specguard` with `specguard --help`, or use `python -m cli.specguard --help` from a source checkout.
3. Locate the target package from the user path, the current directory, or `specs/*/spec.md`.
4. Run `specguard run <package> --no-llm --no-follow-up` for the default heuristic gate.
5. Read `readiness-review.json` and `readiness-review.md` when they are produced.
6. If the package is `READY` or `READY_WITH_WARNINGS`, point the user to `implementation-output.md` when it exists.
7. If the package is `NOT_READY`, summarize the blockers and propose scoped spec edits for user review.

For the stable JSON fields and file-based states that plugin workflows can rely on, see [Plugin Result Contract](../../docs/plugin-result-contract.md).

## Result Handling

The plugin workflow reports from structured files, not terminal log scraping. It should summarize:

- readiness status and review level
- Critical, Major, and Minor finding counts
- top readiness findings
- `readiness-review.json` and `readiness-review.md` paths
- whether implementation handoff is allowed
- `implementation-output.md` path when available
- failure category when a normal readiness result is unavailable

Common failure categories are `missing_cli`, `missing_spec_package`, `validation_failed_before_review`, `stale_review`, `missing_provider_for_llm`, `timeout`, and `cli_execution_failed`.

Detail Review is opt-in. When the user asks for it, use the existing CLI follow-up menu path with `specguard run <package> --llm --follow-up`, choose the review-only Detail Review action, and read `readiness-review-detail.json` plus `readiness-review-detail.md`. Do not treat Detail Review as the default gate or as a replacement for `readiness-review.json`.

## Spec Refinement Safety Boundary

The MVP plugin is suggestion-only. It can help users understand findings and draft proposed wording, but it does not automatically modify `spec.md`, `plan.md`, `tasks.md`, `technical-design.md`, or other spec package files.

Every proposed change should include:

- the addressed finding severity and title
- `SpecGuard evidence` from the readiness report or current spec
- `Codex suggestion` as proposed wording, not an applied patch
- the target artifact and section
- a scope check that explains whether the suggestion is supported by current intent or needs a user decision
- a next step to manually edit the spec and rerun `specguard run <package> --no-llm --no-follow-up`

The plugin must not invent fields, requirements, states, error behavior, ownership rules, or product behavior that are not supported by the user's spec or SpecGuard findings. If the evidence is insufficient, the plugin should say `Needs user decision` instead of filling the gap.

Codex suggestions are not implementation input until the user approves them, edits the spec package, and reruns SpecGuard. Existing experimental CLI auto-revision remains outside the plugin MVP and must not be invoked by the plugin workflow.

## Supported CLI Commands

```bash
specguard init <feature>
specguard run specs/<feature>
specguard run specs/<feature> --no-llm --no-follow-up
specguard run specs/<feature> --llm
specguard actions install-pr-review
```

Use `--llm` only when the user explicitly asks for provider-backed review. Use PR Review setup only after confirming that the repository should install the advisory GitHub Actions workflow.

## Non-Goals

- Moving SpecGuard engine logic into the Codex plugin.
- Replacing the CLI with MCP or a native Codex UI.
- Running automatic spec rewrites.
- Applying file edits without user approval.
