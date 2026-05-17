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
2. Run `specguard run <package>` for the default readiness gate.
3. Read `readiness-review.json` and `readiness-review.md` when they are produced.
4. If the package is `READY` or `READY_WITH_WARNINGS`, point the user to `implementation-output.md`.
5. If the package is `NOT_READY`, summarize the blockers and propose scoped spec edits for user review.

For the stable JSON fields and file-based states that plugin workflows can rely on, see [Plugin Result Contract](../../docs/plugin-result-contract.md).

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
