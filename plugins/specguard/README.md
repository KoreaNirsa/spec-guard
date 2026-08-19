# SpecGuard Codex Plugin

This plugin is a Codex workflow scaffold for SpecGuard. It helps Codex locate spec packages, run the existing `specguard` CLI, read generated readiness artifacts, and summarize the next action for the user.

## Scope

- Use the existing `specguard` CLI as the canonical engine.
- Keep the default gate as `specguard run <package>` with heuristic low-mode SpecGuard Review.
- Treat Codex-assisted detail review as optional and advisory unless explicitly requested.
- Generate report-only Mermaid and HTML summaries only from existing structured readiness artifacts.
- Provide summaries and suggestions only; do not rewrite spec files or apply fixes automatically.
- Do not duplicate readiness review, benchmark, PR review, implementation artifact-generation, or contract-validation logic inside the plugin.

## Codex App Setup

Install this plugin from the repo-scoped SpecGuard marketplace with:

```bash
codex plugin marketplace add KoreaNirsa/spec-guard --ref main
```

Then select the `SpecGuard Plugins` marketplace source in Codex and install `SpecGuard`. This is a custom repository marketplace, not the official OpenAI Plugin Directory.

You can also add this local plugin from the repository checkout by selecting the `plugins/specguard/` directory in the Codex app local plugin flow. The directory contains the required `.codex-plugin/plugin.json` manifest, the `specguard-workflow` skill, and the `specguard-spec-report` skill.

Installing the plugin does not install the SpecGuard CLI. Before using the plugin in a target workspace, confirm `specguard --help` works there. If it is unavailable, install SpecGuard with `pip install spec-guard`. From a SpecGuard source checkout, `python -m cli.specguard --help` is an acceptable fallback.

For the full MVP setup, expected user flow, and validation scenarios, see [Codex Plugin Guide](../../docs/codex-plugin.md).
For packaged examples and contributor-only scenario fixtures, see [Plugin Examples And Contributor Fixtures](../../docs/plugin-examples.md).
For the v0.4.x hardening backlog, see [Codex Plugin Hardening Roadmap](../../docs/codex-plugin-hardening-roadmap.md).

## Typical Workflow

1. Identify the current issue, repository state, and target spec package.
2. Detect `specguard` with `specguard --help`, or use `python -m cli.specguard --help` from a source checkout.
3. Preview the target package with `specguard discover <path>` before running review.
4. Locate the target package from the user path, the current directory, or non-excluded `**/specs/*/spec.md` candidates.
5. Run `specguard run <package> --no-llm --no-follow-up` for the default heuristic gate.
6. Read `readiness-review.json` and `readiness-review.md` when they are produced.
7. If the package is `READY` or `READY_WITH_WARNINGS`, point the user to `implementation-output.md` when it exists.
8. If the package is `NOT_READY`, summarize the blockers and propose scoped spec edits for user review.
9. If the command stops before SpecGuard Review, read `.specguard/run-state.json` when present and report `validation_failed_before_review` from that structured state.

For the stable JSON fields and file-based states that plugin workflows can rely on, see [Plugin Result Contract](../../docs/plugin-result-contract.md).

Package discovery supports root packages such as `specs/your-feature-name/` and nested module packages such as `services/api/specs/your-feature-name/`. The read-only `specguard discover <path>` command returns stable JSON with `schema_version: "specguard.discovery_preview.v1"`, `status`, `reason`, `candidate_count`, `selection_required`, `review_allowed`, `candidates[].index`, `candidates[].path`, `candidates[].spec_path`, and `candidates[].review_command` before any review runs. If discovery finds exactly one package, the plugin can use it. If it finds multiple candidates, the plugin must list them in preview order and ask for one explicit package path; it must not run every candidate automatically. If discovery reports `missing_spec_package`, show supported examples such as `specs/<feature>/spec.md` and `backend/specs/<feature>/spec.md`, then ask the user to create or point to a package without implying any review has run. When no package exists, `draft_sources[]` may list likely requirement documents and `next_action.type: offer_draft_package` requires explicit user approval before any file creation. Existing package candidates always take precedence, and discovery never imports or reviews draft sources automatically. Candidate discovery skips hidden, dependency, build, and generated directories, including `.git`, `.venv`, `node_modules`, `vendor`, `build`, `dist`, `target`, `out`, `coverage`, `htmlcov`, `generated`, `__generated__`, and `__pycache__`.

If the resolved package has a non-empty `spec.md` but is missing normal package files or required spec sections, run `specguard run <package> --allow-partial --no-llm --no-follow-up`. This review-only mode writes the normal readiness JSON and Markdown reports with Critical structure findings. It never generates technical design, tests, contracts, or implementation handoff, and it does not weaken the default strict run.

## Result Handling

The plugin workflow reports from structured files, not terminal log scraping. It should summarize:

- readiness status and review level
- Critical, Major, and Minor finding counts
- top readiness findings by severity and title, with Critical findings first for `not_ready`
- `readiness-review.json` and `readiness-review.md` paths
- whether implementation handoff is allowed
- `implementation-output.md` path when available
- failure category when a normal readiness result is unavailable
- `.specguard/run-state.json` for validation failures that stop before SpecGuard Review
- attempted command, known generated files, and next safe action for timeout or CLI execution failures
- reviewed authored Markdown from `input.artifacts[]`, with additional notes such as `domain-rules.md` or `api-notes.md` highlighted separately and long lists truncated with an overflow count

Common failure categories are `missing_cli`, `missing_spec_package`, `validation_failed_before_review`, `pipeline_failed`, `stale_review`, `missing_provider_for_llm`, `timeout`, and `cli_execution_failed`.

Report generated files in two groups: `known_files` are files that exist for diagnostics, while `relevant_files` are current files for the resolved state. For `validation_failed_before_review` and `pipeline_failed`, use `.specguard/run-state.json` as the relevant state file and do not point to `implementation-output.md`. Do not point to `implementation-output.md` as relevant unless `readiness-review.json` is fresh, implementation is allowed, and the handoff file exists.

Keep the concise summary separate from full finding prose. Use the Markdown and JSON report paths for detailed descriptions, impacts, fixes, and evidence instead of coupling the plugin UX to exact finding text.

Human-facing report language is automatic. The plugin passes `ko` or `en` through the process-only `SPECGUARD_CONVERSATION_LANGUAGE` environment variable only when that language clearly dominates the active conversation. Without a clear hint, SpecGuard inspects authored package content; mixed or inconclusive content falls back to English. The resolved code and source are recorded under `report_language` in `readiness-review.json`. Stable JSON keys and enums are never translated.

The human `readiness-review.md` report begins with a concise `## Summary` block containing status, counts, top finding, report context, edit target, conditional handoff guidance, and rerun command. It is safe to display, but `readiness-review.json` remains authoritative for machine decisions.

Render one primary Next Action block with separate status, counts, top finding, report path, handoff path, edit target, and rerun command fields. Do not repeat report or rerun lines through secondary guidance. A handoff path is valid only when the readiness JSON allows implementation and `implementation-output.md` actually exists; pre-review failures have no fresh report or handoff path.

When authored spec artifacts change after a report was generated, treat the report as `stale_review`. Restate previous findings and suggested clarifications as suggestions only, mark unclear product behavior as `Needs user decision`, keep previous readiness reports as historical context only, do not expose `implementation-output.md` as a handoff, and ask the user to rerun `specguard run <package> --no-llm --no-follow-up`. After rerun, report only the fresh readiness result as the current status, including finding counts, current report paths, handoff availability, and next action. When a stable comparison is possible, compare previous and fresh `issues[]` entries only by unique `(severity, title)` keys and report `resolved`, `remaining`, `deferred`, and `newly_introduced` findings. Do not rely on generated report prose, `fix` wording, evidence excerpts, or terminal output for that comparison. Report `deferred` only for findings the user explicitly deferred, and keep deferred decisions out of implementation input until the spec is updated and SpecGuard reruns.

Detail Review is opt-in. When the user asks for it, use the existing CLI follow-up menu path with `specguard run <package> --llm --follow-up`, choose the review-only Detail Review action, and read `readiness-review-detail.json` plus `readiness-review-detail.md`. Do not treat Detail Review as the default gate or as a replacement for `readiness-review.json`.

## Human-Readable Spec Reports

When the user asks for a visual report, Mermaid diagram, HTML report, decision-review report, or human-readable summary of an existing SpecGuard package, use the `specguard-spec-report` skill. The report skill reads existing source-backed artifacts and writes only generated presentation files under the package `docs/` directory:

```text
<package>/docs/specguard-report.mmd
<package>/docs/specguard-report.html
```

From this repository checkout, the helper script is:

```bash
python plugins/specguard/skills/specguard-spec-report/scripts/spec_report.py <package>
```

The reports include the spec package path, readiness status, finding summary, key evidence, handoff status, report paths, and next action. They must keep source spec evidence, readiness findings, and report-only presentation separate. They must not patch spec files, create implementation requirements, replace the Grill me loop, or reimplement SpecGuard Review.

Generated `docs/specguard-report.mmd` and `docs/specguard-report.html` files are report-only outputs. They are not authored spec inputs and must not be added to future readiness source artifact sets.

## PR Review Setup

PR Review setup is opt-in and advisory. A user can ask:

```text
@SpecGuard PR Review를 설정해줘.
```

The plugin should check the current repository and branch, detect the GitHub remote when possible, and verify `specguard --help` before installing anything. Installing this plugin does not install the SpecGuard CLI; if the CLI is missing, report `missing_cli` and ask before helping with `pip install spec-guard`.

Before writing repository workflow files, ask for confirmation. After confirmation, run:

```bash
specguard actions install-pr-review
```

Then confirm whether `.github/workflows/specguard-pr-review.yml` was created, updated, or already existed.

Required GitHub Actions secret:

```text
SPECGUARD_OPENAI_API_KEY
```

Optional repository variables:

```text
SPECGUARD_PR_REVIEW_MODEL
SPECGUARD_REVIEW_SPEC_PATHS
```

The plugin must not invent, generate, store, echo, or commit API keys. If `gh auth status` succeeds, Codex can offer a user-approved `gh secret set SPECGUARD_OPENAI_API_KEY --repo <owner/name>` path so the user enters the key through GitHub CLI without putting it in command history. If GitHub integration is missing or unsafe, stop before secret handling and tell the user to add the secret and optional variables in GitHub Settings > Secrets and variables > Actions.

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

## CLI-Driven Grill Me Loop

When the user asks for the Grill me loop, use `grill.json` findings from the CLI. If the package is `not_ready`, show the short `readiness_summary.problem` and counts first so the user can see the blocking issue before answering. Ask Critical and Major questions first, using the generated question text and `resolution_prompts` examples so the user can answer with `update-spec`, `mark-intentional`, `defer`, or `reject` directly. Store answers in `decisions/specguard-decisions.jsonl`, and apply only `user-confirmed` `update-spec` decisions. Deferred, rejected, or unconfirmed answers remain visible but must not modify spec content. After applying confirmed Markdown edits, rerun `specguard run <package> --no-llm --no-follow-up` and report resolved, unresolved, deferred, and new findings from `decisions/specguard-rerun-comparison.json`.

## Supported CLI Commands

```bash
specguard init <feature>
specguard run specs/<feature>
specguard run specs/<feature> --no-llm --no-follow-up
specguard grill specs/<feature> findings
specguard grill specs/<feature> ask
specguard grill specs/<feature> plan
specguard grill specs/<feature> apply
specguard grill specs/<feature> verify
specguard run specs/<feature> --llm
specguard actions install-pr-review
```

Use `--llm` only when the user explicitly asks for provider-backed review. Use PR Review setup only after confirming that the repository should install the advisory GitHub Actions workflow.

## Non-Goals

- Moving SpecGuard engine logic into the Codex plugin.
- Replacing the CLI with MCP or a native Codex UI.
- Running automatic spec rewrites.
- Applying file edits without user approval.
