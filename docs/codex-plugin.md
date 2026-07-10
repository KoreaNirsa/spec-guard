# Codex Plugin Guide

This guide documents the SpecGuard Codex plugin MVP. The plugin is a Codex workflow wrapper around the existing `specguard` CLI. The CLI is the canonical engine for review, artifact generation, validation, and implementation handoff.

The MVP does not provide a native SpecGuard engine inside Codex, does not expose a full MCP interface, and does not automatically rewrite specs.

Supported versions: Python 3.11, 3.12, or 3.13, and a Codex CLI version that supports `codex plugin marketplace`. This setup has been verified with Codex CLI 0.130.0.

## Install From The SpecGuard Marketplace

The SpecGuard repository exposes a repo-scoped Codex plugin marketplace at:

```text
.agents/plugins/marketplace.json
```

Add it to Codex with:

```bash
codex plugin marketplace add KoreaNirsa/spec-guard --ref main
```

This is a custom repository marketplace, not the official OpenAI Plugin Directory. Official public plugin publishing is outside the MVP scope.

After adding the marketplace:

1. Restart or refresh Codex if the plugin directory does not update immediately.
2. Open the Codex plugin directory.
3. Select the `SpecGuard Plugins` marketplace source.
4. Install the `SpecGuard` plugin.
5. Prepare your target project folder. If you do not have a project yet, create one first:

   ```bash
   mkdir your-codex-project-folder
   cd your-codex-project-folder
   ```

6. Prepare a spec package. To test SpecGuard with the sample package, run:

   ```bash
   specguard example copy specs/your-feature-name --force
   ```

7. Open `your-codex-project-folder` in Codex, then ask it to run SpecGuard on the package:

   ```text
   Run SpecGuard on specs/your-feature-name.
   ```

   A target project can also keep packages in nested modules, for example `services/api/specs/your-feature-name/`.

Installing the plugin does not install the `specguard` CLI. Before using the plugin in a target workspace, confirm:

```bash
specguard --help
```

If that command is unavailable, install SpecGuard first:

```bash
pip install spec-guard
```

From this repository checkout, this fallback is also valid:

```bash
python -m cli.specguard --help
```

## Add The Local Plugin To Codex App

The repository-local plugin bundle lives at:

```text
plugins/specguard/
```

The required plugin manifest is:

```text
plugins/specguard/.codex-plugin/plugin.json
```

To add it from a repository checkout:

1. Install SpecGuard or use a source checkout where the CLI fallback works.
2. Confirm the CLI is available in the target workspace:

   ```bash
   specguard --help
   ```

   From this repository checkout, this fallback is also valid:

   ```bash
   python -m cli.specguard --help
   ```

3. In the Codex app local plugin flow, add the `plugins/specguard/` directory from this checkout.
4. Start a Codex session in the repository that contains the target spec package.
5. Ask Codex to run SpecGuard on a package, for example:

   ```text
   Run SpecGuard on specs/your-feature-name.
   ```

If a Codex workspace uses repo-local marketplace metadata instead of direct local plugin selection, the entry should point to the same plugin directory:

```json
{
  "name": "specguard",
  "source": {
    "source": "local",
    "path": "./plugins/specguard"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Developer Tools"
}
```

The checked-in repo marketplace already provides this entry through `.agents/plugins/marketplace.json`.

## Expected User Flow

1. Create or select a spec package under `specs/<feature>/` or a nested module `specs/<feature>/`.
2. Ask Codex to run the default SpecGuard plugin workflow.
3. The plugin previews package discovery before running review:

   ```bash
   specguard discover <path>
   ```

   The command returns stable JSON and does not write readiness reports or generated artifacts.

4. The plugin runs:

   ```bash
   specguard run <package> --no-llm --no-follow-up
   ```

5. The plugin reads `readiness-review.json` and `readiness-review.md`.
6. The plugin summarizes status, review level, Critical/Major/Minor counts, top findings, report paths, handoff availability, and next action from structured files.
7. If the package is `NOT_READY`, inspect the Critical findings first, manually edit the spec package, and rerun SpecGuard.
8. After the user edits authored spec artifacts, the plugin treats the previous report as `stale_review`, restates old findings as suggestions only, and asks the user to rerun `specguard run <package> --no-llm --no-follow-up`.
9. When the previous and fresh reports have unique stable `(severity, title)` issue keys, compare those keys and report resolved, remaining, deferred, and newly introduced findings without using generated report prose or terminal output. Report `deferred` only for findings the user explicitly deferred.
10. If the fresh rerun is `READY` or `READY_WITH_WARNINGS`, use `implementation-output.md` as the implementation handoff when it exists.
11. After implementation, install and use SpecGuard PR Review only when the repository wants the advisory pull request workflow.

Package resolution follows the CLI rule: use an explicit path when it contains `spec.md`; otherwise search non-excluded `**/specs/*/spec.md` candidates. The read-only `specguard discover <path>` preview exposes `schema_version: "specguard.discovery_preview.v1"`, `status`, `reason`, `candidate_count`, `selection_required`, `review_allowed`, `candidates[].index`, `candidates[].path`, `candidates[].spec_path`, and `candidates[].review_command` for plugin prompts before review starts. Exactly one candidate can be used automatically. Multiple candidates must be listed in preview order for the user and require an explicit package path; the plugin must not run every candidate automatically. Candidate discovery skips hidden, dependency, build, and generated directories, including `.git`, `.venv`, `node_modules`, `vendor`, `build`, `dist`, `target`, `out`, `coverage`, `htmlcov`, `generated`, `__generated__`, and `__pycache__`.

## Architecture

The plugin orchestrates the CLI. It must not embed, fork, or reimplement SpecGuard review logic.

- CLI command execution remains the source of truth.
- `readiness-review.json` is the machine-readable result.
- `readiness-review.md` is the human-readable report.
- `implementation-output.md` is the implementation handoff when the gate allows it.
- `docs/specguard-report.mmd` and `docs/specguard-report.html` are optional report-only presentation artifacts.
- Terminal output is not the readiness contract.

For stable fields and file-based states, see [Plugin Result Contract](plugin-result-contract.md).

For packaged examples and contributor-only scenario fixtures, see [Plugin Examples And Contributor Fixtures](plugin-examples.md).

For the v0.4.x plugin hardening backlog and missing contracts, see [Codex Plugin Hardening Roadmap](codex-plugin-hardening-roadmap.md).

For the CLI-driven Grill me loop, see [CLI-Driven Grill Me Loop](cli-grill-me-loop.md). That workflow uses companion `grill.json`/`grill.md` files, stores user answers in `decisions/specguard-decisions.jsonl`, applies only `user-confirmed` `update-spec` decisions to supported spec targets, and requires a follow-up `specguard run <package> --no-llm --no-follow-up` before implementation handoff.

For the suggestion-only spec refinement boundary, see [SpecGuard Codex Plugin: Spec Refinement Safety Boundary](../plugins/specguard/README.md#spec-refinement-safety-boundary).

## Default Gate

The default plugin gate is heuristic SpecGuard Review:

```bash
specguard run <package> --no-llm --no-follow-up
```

This path does not require Codex or OpenAI provider setup. It should be used first unless the user explicitly asks for provider-backed review.

## Optional Human-Readable Reports

When a user asks for a visual SpecGuard report, Mermaid diagram, HTML report, or decision-review summary, use the `specguard-spec-report` skill after a spec package has existing readiness artifacts. The skill reads the selected package and existing `readiness-review.json`, `readiness-review.md`, and `implementation-output.md` availability, then writes:

```text
<package>/docs/specguard-report.mmd
<package>/docs/specguard-report.html
```

From this repository checkout, the helper command is:

```bash
python plugins/specguard/skills/specguard-spec-report/scripts/spec_report.py <package>
```

The generated reports include the spec package path, readiness status, finding summary, key evidence, handoff status, and next action. They are presentation artifacts only: do not use them as readiness source inputs, implementation requirements, or replacements for the default SpecGuard Review or Grill me loop.

## Optional Detail Review

Codex-backed Detail Review is optional and advisory. It is not the default gate and it does not replace `readiness-review.json`.

Use it only when the user explicitly asks for provider-backed detail review. Before attempting it, check provider setup:

```bash
specguard auth status
```

If no provider is configured, report `missing_provider_for_llm` and tell the user to configure a provider before retrying. Do not pretend Detail Review ran.

When provider setup is available and the user requested Detail Review, use the existing CLI follow-up menu path:

```bash
specguard run <package> --llm --follow-up
```

Then choose the review-only Detail Review action and read `readiness-review-detail.json` plus `readiness-review-detail.md`.

## Codex-Assisted PR Review Setup

After implementation, a user can ask Codex to guide optional SpecGuard PR Review setup:

```text
@SpecGuard PR Review를 설정해줘.
```

This setup path still uses the CLI as the source of truth. Installing the Codex plugin does not install the `specguard` CLI and does not configure GitHub secrets automatically.

The plugin workflow should:

1. Check repository state with `git status --short --branch`.
2. Detect the GitHub remote with `git remote -v` or equivalent repository metadata when available.
3. Check whether `specguard --help` works, with `python -m cli.specguard --help` as the source-checkout fallback.
4. If the CLI is missing, report `missing_cli`; when the environment allows it, ask before helping the user run `pip install spec-guard`.
5. Ask before writing repository workflow files.
6. After confirmation, run:

   ```bash
   specguard actions install-pr-review
   ```

7. Confirm whether `.github/workflows/specguard-pr-review.yml` was created, updated, or already existed.
8. Explain that the workflow file must be committed and pushed before GitHub Actions can use it.

Required secret setup is separate from workflow installation:

```text
SPECGUARD_OPENAI_API_KEY
```

Optional repository variables:

```text
SPECGUARD_PR_REVIEW_MODEL
SPECGUARD_REVIEW_SPEC_PATHS
```

The plugin must not invent, generate, store, print, or commit API keys. If `gh` is installed and authenticated, Codex may offer a user-approved registration path that uses `gh secret set SPECGUARD_OPENAI_API_KEY --repo <owner/name>` so the user can enter the key through GitHub CLI without echoing it. Optional variables can be set with `gh variable set` after the user confirms the values.

When GitHub integration or `gh` authentication is unavailable, stop before secret handling and give manual setup instructions: open GitHub repository Settings > Secrets and variables > Actions, add `SPECGUARD_OPENAI_API_KEY` as a repository secret, and add `SPECGUARD_PR_REVIEW_MODEL` or `SPECGUARD_REVIEW_SPEC_PATHS` as repository variables only when needed.

## Validation Scenarios

Contributor fixture metadata for these scenarios lives in `tests/fixtures/plugin-workflow-scenarios/scenarios.json`.
Those fixtures are not packaged resources; they protect stable commands, file names, failure categories, and safety boundaries without pinning exact Markdown report sentences.

| Scenario | Plugin action | Expected result |
| --- | --- | --- |
| missing `specguard` CLI | Run `specguard --help`, then source fallback `python -m cli.specguard --help` when in this checkout. | Report `missing_cli` and ask the user to install SpecGuard or run from a source checkout. |
| missing spec package | Resolve the user path, current directory, or non-excluded `**/specs/*/spec.md` candidates before running the CLI. | Report `missing_spec_package` and ask for a package directory that contains `spec.md`. |
| ambiguous spec package selection | Read `specguard discover <path>` JSON with `selection_required: true`, list ordered `candidates[]`, and ask the user to choose one package. | Report `ambiguous_spec_package`; do not run every candidate automatically; after selection run `specguard run <selected-path> --no-llm --no-follow-up`. |
| existing spec package reaches `ready` | Run the default heuristic gate and read structured result files. | Report `ready`, finding counts, report paths, and `implementation-output.md` when present. |
| existing spec package is `not_ready` with Critical findings | Read `readiness-review.json` and `readiness-review.md`. | Summarize Critical findings first by severity and title, link to full reports, and provide suggestion-only spec refinement proposals without editing files. |
| `ready_with_warnings` handoff guidance | Read structured result files and check handoff availability. | Report warnings, explain implementation is allowed only when `implementation-output.md` exists, and point to that file when present. |
| edited spec package rerun loop | Compare current authored Markdown source files to `input.artifacts[]`, then compare source mtimes to `readiness-review.json`. | Report `stale_review`, restate previous findings and clarifications as suggestions only, require `Needs user decision` for unclear behavior, and ask the user to rerun `specguard run <package> --no-llm --no-follow-up`. |
| fresh rerun result | After the user updates the spec package, run the default heuristic gate and read the newly generated structured result files. | Report current status, Critical/Major/Minor counts, current report paths, handoff availability, and next action; when unique `(severity, title)` keys are available, compare previous and fresh findings as resolved, remaining, deferred, and newly introduced without relying on unstable report prose; treat `deferred` as user-explicit deferrals only; report fresh `not_ready` as still blocked. |
| human-readable report requested | Read an existing spec package and structured SpecGuard readiness artifacts, then generate report-only presentation files. | Write `<package>/docs/specguard-report.mmd` and `<package>/docs/specguard-report.html`; include package path, readiness status, finding summary, key evidence, handoff status, and next action without patching specs or creating implementation requirements. |
| stale readiness report | Compare current authored Markdown source files to `input.artifacts[]`, then compare source mtimes to `readiness-review.json`. | Report `stale_review`, do not reuse the old report as the current result, and ask the user to rerun SpecGuard. |
| validation failure before review | Read `.specguard/run-state.json` when present; otherwise treat a missing or not-updated readiness JSON after a non-zero run as pre-review failure. | Report `validation_failed_before_review`, include `failure_category`, `failed_stage`, validation messages, actionable next steps, and ask the user to fix validation errors before rerunning; do not point to `implementation-output.md`. |
| optional detail review requested without provider setup | Run `specguard auth status` before detail review. | Report `missing_provider_for_llm`; do not run or claim provider-backed review. |
| CLI timeout | Keep the attempted command, timeout context, and existing generated files as diagnostics. | Report `timeout`, list known files only, and tell the user to retry after checking provider status or increasing timeout. |
| unclassified CLI failure | Use this only when no fresh `not_ready`, stale report, timeout, missing provider, or pre-review validation state applies. | Report `cli_execution_failed`, include the command, known files, and the next safe rerun action. |
| PR Review setup requested | Check repository state, remote, and CLI availability; ask before running `specguard actions install-pr-review`; explain required secret and optional variables. | Confirm `.github/workflows/specguard-pr-review.yml` status and provide safe `gh` or manual GitHub Settings instructions without exposing API keys. |
| CLI-driven Grill me loop | Read `grill.json` findings, ask Critical/Major questions first, store answers in `decisions/specguard-decisions.jsonl`, and patch only confirmed `update-spec` decisions. | Deferred or rejected answers remain visible but do not modify spec content; after patching, rerun `specguard run <package> --no-llm --no-follow-up` and compare resolved, unresolved, deferred, and new findings. |

## Non-Goals

- Do not claim native plugin engine support.
- Do not document full MCP support until it exists.
- Do not document automatic spec rewriting as a supported plugin behavior.
- Do not claim that PR Review setup creates or stores API keys automatically.
- Do not treat Codex suggestions as implementation input until the user approves and updates the spec.
- Do not treat generated report-only `docs/specguard-report.mmd` or `docs/specguard-report.html` files as authored spec inputs.
