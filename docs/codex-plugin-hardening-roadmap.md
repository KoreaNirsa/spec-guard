# Codex Plugin Hardening Roadmap

This roadmap tracks the v0.4.x work needed to make the SpecGuard Codex plugin a reliable OSS workflow instead of a local MVP. The plugin remains a workflow wrapper around the existing `specguard` CLI. The CLI is the canonical engine for review, artifact generation, validation, PR review setup, and implementation handoff.

The roadmap is intentionally contract-first. Each item names the user problem, expected behavior, non-goals, and missing contracts that must be resolved before implementation grows beyond documentation or workflow guidance.

## Scope Boundaries

- Keep `specguard run <package> --no-llm --no-follow-up` as the default plugin gate.
- Use `readiness-review.json` as the machine-readable readiness contract.
- Treat terminal output as user-facing logs only, not as the plugin result contract.
- Keep Codex-assisted Detail Review optional and advisory.
- Keep SpecGuard PR Review optional and advisory after implementation.
- Do not move SpecGuard engine logic into the plugin.
- Do not make automatic spec rewriting a plugin behavior.
- Do not make LLM review the default gate.
- Do not promise official plugin directory publication unless that path is specified separately.

## Immediate v0.4.1

### Guided PR Review Setup

Related issue: #174

User problem: A user can install the SpecGuard plugin but still has to discover the manual steps for installing the advisory PR Review workflow, configuring `SPECGUARD_OPENAI_API_KEY`, and setting optional repository variables.

Expected behavior:

- The plugin workflow can guide a request such as `PR Review setup`.
- The workflow checks repository state and CLI availability before writing files.
- The workflow asks before running `specguard actions install-pr-review`.
- The workflow confirms `.github/workflows/specguard-pr-review.yml` exists or was generated.
- The workflow clearly separates the required `SPECGUARD_OPENAI_API_KEY` secret from optional `SPECGUARD_PR_REVIEW_MODEL` and `SPECGUARD_REVIEW_SPEC_PATHS` variables.
- When authenticated GitHub tooling is unavailable, the workflow reports exact manual setup steps instead of pretending the secret was configured.

Missing contracts:

- Safe secret registration contract for Codex-assisted GitHub tooling, including how to avoid echoing API keys in logs or final output.
- Idempotency expectations when the PR Review workflow already exists.
- The exact failure categories for missing `gh` auth, missing repository remote, and insufficient repository permissions.

Non-goals:

- Do not install PR Review during plugin installation.
- Do not generate, store, print, or commit API keys.
- Do not make PR Review a required status check by default.
- Do not replace the existing CLI-backed PR Review workflow.

### Korean Finding Quality

Related issue: #175

User problem: Korean spec packages can produce readiness findings that are less precise or less actionable than the English/general heuristic findings, even when the gate decision is useful.

Expected behavior:

- Korean regression fixtures cover `READY`, `READY_WITH_WARNINGS`, and `NOT_READY`.
- Known Korean false positive and false negative examples are documented before rule changes.
- Korean findings point to concrete missing or ambiguous spec content.
- Finding wording separates observed spec evidence from inferred risk.
- Severity stays consistent with the English/general heuristic rules.

Missing contracts:

- Fixture naming and assertion conventions for Korean readiness quality.
- Which Korean phrases are stable public behavior and which should be tested only by decision, severity, evidence, and actionable shape.
- Before/after reporting format for Korean calibration changes.

Non-goals:

- Do not claim full Korean localization of all CLI output.
- Do not make LLM review mandatory for Korean spec quality.
- Do not weaken Critical blockers to reduce Korean-language noise.
- Do not rewrite user specs automatically.

### Plugin Run And Recovery States

User problem: When the default plugin run cannot produce a normal readiness result, users need a precise next action rather than a generic command failure.

Expected behavior:

- The workflow reports from structured files and file mtimes, not terminal scraping.
- The workflow handles at least `ready`, `ready_with_warnings`, `not_ready`, `stale_review`, and `validation_failed_before_review`.
- The workflow reports `missing_cli`, `missing_spec_package`, `missing_provider_for_llm`, `timeout`, and `cli_execution_failed` when those states apply.
- The workflow points to `readiness-review.json`, `readiness-review.md`, and `implementation-output.md` only when those files are current and relevant.

Missing contracts:

- Timeout handling expectations for long local runs and provider-backed optional review.
- Whether plugin-facing failure categories should become a dedicated JSON schema or remain documented workflow states.
- A durable way to display stale review reasons outside the Python codebase.

Non-goals:

- Do not parse terminal text for readiness state.
- Do not infer implementation readiness from report prose.
- Do not treat old reports as current after source artifacts change.

### Plugin Install Smoke Validation

User problem: Marketplace installation can succeed while the target workspace still lacks the `specguard` CLI or a runnable sample package.

Expected behavior:

- The setup guide keeps saying that plugin installation does not install the CLI.
- The workflow checks `specguard --help` and, in a source checkout, `python -m cli.specguard --help`.
- The guide offers a minimal sample-package smoke path using `specguard example copy`.
- Failure output tells the user which environment needs the CLI.

Missing contracts:

- Whether a future `specguard plugin doctor` command is needed or whether documented checks are enough for v0.4.x.
- Which installation checks belong in the plugin skill versus CLI documentation.

Non-goals:

- Do not run package installation automatically during plugin installation.
- Do not assume the user's target project is the SpecGuard source checkout.

## Should-Have v0.4.x

### Result Summary UX

User problem: Raw readiness findings can be too verbose for quick Codex plugin feedback.

Expected behavior:

- The plugin summarizes status, review level, Critical/Major/Minor counts, top findings, handoff availability, and next action from `readiness-review.json`.
- `NOT_READY` summaries prioritize Critical findings.
- `READY_WITH_WARNINGS` summaries explain that implementation may proceed while warning cleanup remains optional.
- Summary wording avoids exact-prose coupling to heuristic finding descriptions.

Missing contracts:

- Stable summary fields beyond the existing readiness JSON contract, if richer UX needs them.
- How many findings to show before linking to the full Markdown report.

Non-goals:

- Do not introduce a native UI contract before the CLI and file contract are stable.
- Do not make terminal output parsing part of summary generation.

### Guided Rerun Loop

User problem: After a user edits a spec package, the plugin should make it easy to rerun SpecGuard without accidentally treating suggestions as approved requirements.

Expected behavior:

- The workflow detects stale reports after edits and instructs the user to rerun the heuristic gate.
- The workflow can restate previous findings and proposed spec wording as suggestions only.
- The workflow says when a missing requirement needs a user decision instead of inventing product behavior.
- The workflow does not use suggestions as implementation input until the user edits the spec package and SpecGuard runs again.

Missing contracts:

- Approval language for user-reviewed spec edits.
- How to connect previous suggestions to a later fresh readiness report without relying on unstable prose.

Non-goals:

- Do not modify `spec.md`, `technical-design.md`, or related spec files automatically.
- Do not invoke experimental auto-revision from the plugin workflow.

### Plugin Examples And Contributor Fixtures

User problem: Contributors need durable examples that cover install, run, blocked, warning, handoff, and recovery paths without depending on screenshots or brittle prose.

Expected behavior:

- Documentation includes a compact set of plugin validation scenarios.
- Tests assert durable commands, file names, failure categories, and safety boundaries.
- Example fixtures show both allowed handoff and blocked readiness paths.

Missing contracts:

- Fixture layout for plugin-specific examples outside the core benchmark suite.
- Which examples should be packaged and which should remain contributor-only.

Non-goals:

- Do not add a full sample application just to test plugin documentation.
- Do not pin exact Markdown sentences unless the phrase is a documented public contract.

## Later v0.4.x

### Native Plugin Or MCP Exploration

User problem: A CLI-orchestrated plugin may eventually limit richer Codex UX, but moving too early would duplicate engine logic and create versioning risk.

Expected behavior:

- Any native plugin or MCP direction starts with an explicit contract proposal.
- The contract covers auth, versioning, failure categories, structured result fields, and migration from the CLI file contract.
- The CLI remains the canonical engine unless a separate approved design changes that boundary.

Missing contracts:

- Protocol surface and versioning policy.
- Compatibility strategy for existing CLI users and GitHub Actions workflows.
- Failure-mode mapping between native integration and current file-based states.

Non-goals:

- Do not move the SpecGuard engine into the plugin as part of v0.4.1.
- Do not expose a partial MCP API without a stable consumer contract.

### Rich PR Review Interpretation

User problem: After PR Review runs, users may want Codex to interpret the advisory result and connect it back to the approved spec package.

Expected behavior:

- The plugin can explain that PR Review is advisory and separate from the readiness gate.
- The workflow can point users to the GitHub Actions run, review comment, and relevant spec package.
- Interpretation stays focused on spec conformance, security, reliability, contracts, data ownership, testability, and operational risk.

Missing contracts:

- Machine-readable PR Review result schema, if plugin consumption needs more than a GitHub review comment.
- Stable mapping from PR Review comments back to spec artifacts.

Non-goals:

- Do not make PR Review required for merge by default.
- Do not treat PR Review as a replacement for repository tests, code review, or branch protection.

## Work Order

1. Finish the immediate v0.4.1 documentation and workflow gaps before adding new plugin capabilities.
2. Use #174 for guided PR Review setup and #175 for Korean finding quality.
3. Open separate follow-up issues for run/recovery state hardening, result summary UX, guided rerun loops, and native integration only when implementation is ready to start.
4. Keep each follow-up issue small enough to state user problem, expected behavior, non-goals, validation, and rollback or fallback behavior.
