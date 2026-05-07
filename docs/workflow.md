# SpecGuard Workflow

SpecGuard is not a code generator. It is a spec refinement and validation workflow for AI-assisted development.

The intended user experience is:

```text
Discovery -> Draft Specs -> User Refinement -> Technical Design -> SpecGuard Review -> Test -> Contract -> Implementation Handoff
```

After that, the user can run Codex, Claude Code, or another coding agent outside the SpecGuard pipeline against the approved handoff package.

## 0. Configure LLM Provider

SpecGuard supports two LLM provider modes today:

- `codex`: local Codex CLI installed on the machine.
- `openai`: OpenAI Platform Responses API.

Claude Code provider integration is planned later. For now, Claude Code should be used separately after SpecGuard produces an approved implementation handoff.

Configure local Codex:

```bash
specguard auth setup --mode codex --model gpt-5.4
```

Codex mode defaults to `gpt-5.4` and a 600-second request timeout. Use `--model` to make the choice explicit, and use `--skip-login` when Codex is already logged in. `auth status` confirms saved configuration and local Codex command availability; it does not run a full live model request.

Configure OpenAI Platform:

```bash
specguard auth setup --mode openai
```

Inspect or reset configuration:

```bash
specguard auth status
specguard auth logout
```

## 1. Init Runs Discovery

Run:

```bash
specguard init my-feature
```

If no provider is configured, interactive `init` offers to run provider setup first.

In LLM mode, Discovery is a short guided conversation. SpecGuard shows each question immediately, includes a visible default, and waits for user input without blocking on an LLM response. The user answers naturally, presses Enter to accept a default, or types `done` / `complete` when the conversation is ready to become a draft spec. The configured LLM then synthesizes the draft `spec.md` from the guided answers.

For OpenAI Platform mode, set an API key or store it in the local ignored config:

```bash
export OPENAI_API_KEY=...
export SPECGUARD_LLM_MODEL=gpt-5.1
specguard auth setup --mode openai
```

You can also run deterministic local Discovery without an LLM:

```bash
specguard init my-feature --no-llm
```

SpecGuard creates draft specs under `specs/` and installs the default readiness workflow:

```text
specs/my-feature/
|-- discovery.md
|-- spec.md
|-- plan.md
|-- tasks.md
|-- constitution.md
`-- checklists/
.github/
`-- workflows/specguard-readiness-gate.yml
```

Use `specguard init my-feature --no-actions` when you do not want SpecGuard to write `.github/workflows`. Existing workflow files are kept unless you explicitly use the workflow force option.

The generated spec package follows a Spec Kit-inspired shape:

- user scenarios and testing
- functional requirements
- acceptance criteria
- error cases
- key entities
- out-of-scope boundaries
- implementation plan
- task breakdown
- constitution and readiness checklist

## 2. User Refines The Spec

The user reviews and edits:

```text
specs/my-feature/spec.md
specs/my-feature/plan.md
specs/my-feature/tasks.md
specs/my-feature/constitution.md
specs/my-feature/checklists/spec-readiness.md
```

These are human-owned artifacts. SpecGuard can draft them, but it should not replace product or engineering judgment.

The CLI intentionally reminds the user to review and strengthen the generated spec before continuing. The next command should be run only after the spec has been checked and edited.

### Optional: Try The Authored Example Package

SpecGuard includes a packaged authored example spec package. Treat it as the state after `init` has created draft files and a user has replaced those drafts with real development requirements.

The package is for testing SpecGuard behavior, not for implementing SpecGuard itself. It uses the same Spec Kit-inspired structure expected from real feature planning:

```text
packaged example
|-- discovery.md
|-- spec.md
|-- plan.md
|-- tasks.md
|-- constitution.md
`-- checklists/spec-readiness.md
```

```bash
specguard init your-feature-name --no-llm
specguard example copy your-feature-name --force
specguard run specs/your-feature-name --no-llm
```

After this test, replace the copied example files with your own feature's product behavior, API or UI expectations, data ownership, authorization rules, state transitions, error cases, and acceptance criteria.

## 3. Run Builds The Implementation Basis

Run:

```bash
specguard run specs/my-feature
```

`run` uses the configured LLM provider for Technical Design and SpecGuard Review. Use `--force` when regenerated derived artifacts are needed:

```bash
specguard run specs/my-feature --force
```

SpecGuard then performs:

```text
Technical Design -> SpecGuard Review -> Test -> Contract -> Implementation Handoff
```

SpecGuard Review inspects every authored spec document in the feature folder, excluding generated SpecGuard Review reports, implementation-output handoffs, and test scenario files. The implementation-ready threshold is Critical=0, Major=0, and Minor<=5. Ready results are highlighted in green in the CLI. Not-ready results are highlighted in red and block Test, Contract, and Implementation Handoff.

Interactive refinement uses this loop:

```text
Initial SpecGuard Review -> Spec Regeneration -> Verification Review -> READY or NOT READY
```

The initial review is broad and adversarial. The verification review is narrower: it checks previous findings against the regenerated spec package and only introduces new Critical or Major findings when there is direct implementation-blocking evidence.

Before a regenerated `spec.md` is applied, SpecGuard runs an Intent Preservation Check. The check blocks obvious intent drift: a changed feature title/problem, dropped acceptance coverage, removed out-of-scope boundaries, or out-of-scope items promoted into Requirements, Acceptance Criteria, or Error Cases. When it blocks, SpecGuard leaves the original `spec.md` unchanged, writes the proposal to `spec.proposed.md`, and asks the user to review the diff manually.

Strict E2E mode automates that loop for LLM-enabled runs:

```bash
specguard run specs/my-feature --strict-e2e --strict-max-iterations 3
```

Strict E2E records every review attempt and every spec regeneration in `strict-e2e-trace.json`. Regeneration uses the previous Readiness Findings as the required backlog, checks intent preservation, then reruns Verification Review. The final result is READY only when the normal readiness gate passes; otherwise strict E2E reports that the configured iteration limit was exhausted or that intent preservation blocked automatic overwrite.
Strict E2E does not treat markdown TDD scenarios alone as executable verification. Before implementation handoff, the package must include executable tests under `tests/` or an accepted `tests/verification-contract.md` that names the expected command or machine-verifiable artifact.

Generated or reused artifacts:

```text
specs/my-feature/
|-- technical-design.md
|-- readiness-review.md
|-- readiness-review.json
|-- tests/
|-- contracts/
|-- strict-e2e-trace.json
`-- implementation-output.md
```

`implementation-output.md` is an external handoff guide. It includes machine-readable readiness status, the `external_handoff` implementation boundary, the approved artifact list, and the expected verification command or accepted verification artifact for coding agents.

SpecGuard generates missing artifacts and refreshes stale tests and contracts when `spec.md` has changed. Use `--force` when derived artifacts, including `technical-design.md`, should be regenerated even if SpecGuard does not detect them as stale.
For API features, OpenAPI contracts must include at least one concrete path. Generated contracts derive a first-pass operation, success response, documented error responses, request/response schemas, and `x-specguard-coverage` from the spec's acceptance criteria and error cases. An empty `paths: {}` scaffold remains a contract blocker and prevents implementation handoff until the API surface is specified. Non-API features can use `contracts/contract-exemption.md` when it clearly states that an API contract is not applicable and gives the reason.

In an interactive terminal, `run` opens a continuation menu after the pipeline. The user can inspect the latest Readiness Findings or ask the configured LLM to regenerate `spec.md` from the findings and automatically run Verification Review so SpecGuard Review checks whether the regenerated spec is ready. If Intent Preservation Check fails, the regenerated text is saved as `spec.proposed.md` and Verification Review is skipped until the user resolves the diff. Initial pipeline, LLM follow-up, and rerun requests show an activity bar with elapsed time. Press `q` to exit the menu. Use `--follow-up` to force this menu when terminal detection fails. Scripts can disable it with `--no-follow-up`.

If a local Codex request times out, check `specguard auth status` and increase the timeout:

```bash
specguard auth setup --mode codex --timeout 600 --skip-login
```

Use `--no-llm` only for deterministic local checks or CI examples:

```bash
specguard run specs/my-feature --no-llm
```

## 4. User Refines And Repeats

If SpecGuard Review blocks the workflow, update:

```text
discovery.md
spec.md
plan.md
tasks.md
constitution.md
checklists/spec-readiness.md
technical-design.md
```

Then run:

```bash
specguard run specs/my-feature
```

Or stay in the post-run menu and choose the LLM spec revision action. Repeat until the SpecGuard Readiness Gate threshold is met.

## 5. Coding Agents Implement Later

After SpecGuard passes, hand the implementation basis to Codex, Claude Code, or another coding agent outside the SpecGuard pipeline. SpecGuard does not invoke or supervise implementation while Critical or Major blockers remain.

Coding agents should focus on:

```text
spec.md
plan.md
tasks.md
constitution.md
checklists/spec-readiness.md
technical-design.md
tests/
contracts/
implementation-output.md
```

Coding agents should not treat these as implementation input:

```text
discovery.md
readiness-review.md
readiness-review.json
```

Those files are SpecGuard validation artifacts.

Generated application code should go under:

```text
develop/<stack>/
```

Examples:

```text
develop/spring/
develop/react/
develop/fastapi/
```

## 6. Pull Request Gates And Advisory Review

`specguard init` installs the `SpecGuard Readiness Gate` workflow by default. The gate runs on pull requests, checks changed packages under `specs/`, and fails when the package is not READY or when `readiness-review.json` is stale relative to source spec artifacts.

For merge-time enforcement, add `SpecGuard Readiness Gate` as a required status check in GitHub branch protection or rulesets.

After external implementation opens a pull request, the optional `SpecGuard PR Review` workflow can run a read-only Codex-compatible review against the approved spec package and PR diff.

Install PR Review only when you want AI-assisted advisory comments:

```bash
specguard actions install-pr-review
```

After installing it, commit and push `.github/workflows/specguard-pr-review.yml`, then add this GitHub Actions secret:

```text
SPECGUARD_OPENAI_API_KEY=sk-...
```

Optional repository variables:

```text
SPECGUARD_PR_REVIEW_MODEL=gpt-5.4-nano
SPECGUARD_REVIEW_SPEC_PATHS=specs/your-feature-name
```

Use `SPECGUARD_REVIEW_SPEC_PATHS` when an implementation PR changes only files under `develop/` and does not modify files under `specs/`.

The workflow:

- checks credentials before assembling review context;
- skips safely in advisory mode when `SPECGUARD_OPENAI_API_KEY` or `SPECGUARD_PR_REVIEW_COMMAND` is unavailable;
- refuses to invoke Codex when the selected spec package is NOT READY or stale;
- sends approved artifacts, tests, contracts, `implementation-output.md`, and the PR diff to the reviewer prompt;
- asks `SpecGuard PR Reviewer` to focus on spec conformance, security, reliability, API contracts, data ownership, testability, and operational risk;
- updates one PR comment with a stable hidden marker instead of creating duplicates;
- uses workflow concurrency to cancel stale review runs for the same PR.

The first version is advisory. Maintainers can make the check required later after confirming credential handling, bot identity, and review quality for their repository.
