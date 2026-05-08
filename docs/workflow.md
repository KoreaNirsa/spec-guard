# SpecGuard Workflow

SpecGuard is not a code generator. It is a spec refinement and validation workflow for AI-assisted development.

The intended user experience is:

```text
Discovery -> Spec Package -> Technical Design -> SpecGuard Review
-> Test -> Contract -> Implementation Handoff
-> External AI Implementation -> Pull Request -> SpecGuard PR Review
```

SpecGuard owns the validation path through Implementation Handoff. After that, the user can run Codex, Claude Code, or another coding agent outside the SpecGuard pipeline against the approved handoff package, then optionally run SpecGuard PR Review on the pull request.

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

Each run records per-feature stage timings for validation, design generation, SpecGuard Review, test generation, contract work, and implementation handoff. The readiness report also records artifact count and total review input characters so slow reviews can be tied to concrete input size without logging secret values or artifact contents.

SpecGuard Review inspects the feature package according to the selected review level. The default `low` level focuses on minimum safety gating and uses fast heuristic review first, even when a provider is configured. Use `--llm` or the follow-up `SpecGuard Review (Detail)` action when the user wants live LLM review. `medium` preserves the stricter v0.2.5-style gate. `high` uses the medium gate thresholds in this release while asking for stricter review attention.

```bash
specguard run specs/my-feature --llm
specguard run specs/my-feature --review-level medium
SPECGUARD_REVIEW_LEVEL=medium specguard run specs/my-feature
```

Readiness has three states, interpreted by review level:

- Low: READY when Critical=0 and no warnings exist; READY_WITH_WARNINGS when Critical=0 and Major or Minor warnings exist; NOT_READY only when Critical>=1.
- Medium: READY when Critical=0, Major=0, Minor<=5; READY_WITH_WARNINGS when Critical=0, Major<=2, Minor<=10; NOT_READY when Critical>=1, Major>=3, or Minor>10.
- High: uses the medium gate thresholds in v0.2.6 with stricter review attention.

Critical findings always block implementation. READY results are highlighted in green, READY_WITH_WARNINGS results are highlighted as warning output, and NOT_READY results are highlighted in red and block Test, Contract, and Implementation Handoff.

After review, the CLI prints a concise Next Action guide:

- READY: Test, Contract, and Implementation Handoff artifacts are ready. Hand `implementation-output.md` and the approved spec package to the external coding agent.
- READY_WITH_WARNINGS: implementation can proceed at the active review level. Warning findings remain available in `readiness-review.md` if the user wants to strengthen the spec first.
- NOT_READY: implementation is blocked. Edit `spec.md` using the Readiness Findings, then rerun `specguard run`.

Default interactive refinement is review-only:

```text
Initial SpecGuard Review -> user edits spec.md -> rerun -> READY, READY_WITH_WARNINGS, or NOT_READY
```

In low mode, the initial review is a practical heuristic safety gate and does not try to perform a complete architecture or security audit. In medium/high, or when `--llm` is explicitly requested, the review is broader and provider-backed. When the default run is NOT READY, SpecGuard reports actionable Readiness Findings and stops. The user owns the spec edits, then reruns `specguard run`.

Automatic Spec Revision is experimental and disabled by default. Users can opt in with `--experimental-auto-revise --follow-up`. In that explicit path, SpecGuard can regenerate `spec.md` from blocked findings and run Verification Review. In low mode, the revision prompt and Verification Review backlog focus on previous Critical blockers so Major and Minor warnings do not expand implementation scope. In medium/high, Verification Review remains broader and can keep or introduce Critical/Major blockers only when there is direct implementation-blocking evidence.

Before a regenerated `spec.md` proceeds to Verification Review, SpecGuard runs an Intent Preservation Check. In low mode, obvious out-of-scope additions are removed from implementation sections and preserved under Out of Scope when they match documented non-goals. The check still blocks obvious intent drift: a changed feature title/problem, dropped acceptance coverage, removed out-of-scope boundaries, weakened safety requirements, or out-of-scope items that still remain promoted into Requirements, Acceptance Criteria, or Error Cases. When it blocks, SpecGuard still updates the working `spec.md` for in-place review, writes the original spec and unified diff under `.specguard/spec-revisions/`, and asks the user to review the applied diff before rerunning.

During experimental Spec Revision, the CLI prints stable step messages for context loading, LLM revision request, intent preservation, audit/spec writes, design refresh checks, and Verification Review reruns. The live progress line also announces current activities such as context assembly, provider wait, and revised-spec parsing without printing prompts, generated specs, secrets, or environment values.

Experimental Strict E2E mode automates that loop for LLM-enabled runs:

```bash
specguard run specs/my-feature --strict-e2e --strict-max-iterations 3
```

Strict E2E records every review attempt and every spec regeneration in `strict-e2e-trace.json`. Regeneration uses the previous Readiness Findings as the required backlog, checks intent preservation, then reruns Verification Review. The final result is READY only when the normal readiness gate passes; otherwise strict E2E reports that the configured iteration limit was exhausted or that intent preservation blocked Verification Review after writing an audited in-place spec update.
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

In an interactive terminal, `run` opens the default continuation menu only when the result still needs user attention, or when the user explicitly passes `--follow-up`. The default menu lets the user inspect the latest Readiness Findings, run `SpecGuard Review (Detail)` with the configured LLM on demand, or choose `[u] I updated spec.md; rerun SpecGuard` after editing the spec in another editor. Detail review writes `readiness-review-detail.md` and `readiness-review-detail.json` so it does not replace the fast review report. The menu does not rewrite user specs unless `--experimental-auto-revise` is set. With that opt-in, blocked Critical findings expose an experimental auto-revision action that regenerates `spec.md` and automatically runs Verification Review so SpecGuard Review checks whether the regenerated spec is ready. If low mode auto-demotes documented out-of-scope additions, the CLI says so and saves the original/diff under `.specguard/spec-revisions/`. If Intent Preservation Check fails, the regenerated text is applied to `spec.md`, the original and diff are saved under `.specguard/spec-revisions/`, and Verification Review is skipped until the user reviews the applied diff. Initial pipeline, experimental LLM follow-up, and rerun requests show an activity bar with elapsed time. Press `q` to exit the menu. Use `--follow-up` to force this menu when terminal detection fails. Scripts can disable it with `--no-follow-up`.

If a local Codex request times out, check `specguard auth status` and increase the timeout:

```bash
specguard auth setup --mode codex --timeout 600 --skip-login
```

Use `--llm` for live LLM detail review. Use `--no-llm` to force deterministic local checks or CI examples:

```bash
specguard run specs/my-feature --llm
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

Repeat until the SpecGuard Readiness Gate threshold is met. Automatic Spec Revision remains available only as an experimental opt-in with `--experimental-auto-revise --follow-up`; the default flow keeps spec editing under user control.

## 5. Coding Agents Implement Later

After SpecGuard reports READY or READY_WITH_WARNINGS, hand the implementation basis to Codex, Claude Code, or another coding agent outside the SpecGuard pipeline. SpecGuard does not invoke or supervise implementation while the package is NOT_READY.

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
- skips safely in advisory mode when `SPECGUARD_OPENAI_API_KEY` is unavailable;
- refuses to invoke Codex when the selected spec package is NOT READY or stale;
- sends approved artifacts, tests, contracts, `implementation-output.md`, and the PR diff to the reviewer prompt;
- asks `SpecGuard PR Reviewer` to focus on spec conformance, security, reliability, API contracts, data ownership, testability, and operational risk;
- updates one PR comment with a stable hidden marker instead of creating duplicates;
- uses workflow concurrency to cancel stale review runs for the same PR.

The first version is advisory. Maintainers can make the check required later after confirming credential handling, bot identity, and review quality for their repository.
