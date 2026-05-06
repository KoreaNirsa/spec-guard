# SpecGuard Workflow

SpecGuard is not a code generator. It is a spec refinement and validation workflow for AI-assisted development.

The intended user experience is:

```text
Setup -> Discovery -> User Spec Refinement -> SpecGuard Run
-> READY Implementation Handoff -> External AI Implementation
-> GitHub PR -> SpecGuard PR Review
```

SpecGuard owns the spec validation path. Codex, Claude Code, or another coding agent owns the implementation after SpecGuard produces an approved handoff.

## 0. Setup

Clone and install from the repository root:

```bash
git clone https://github.com/KoreaNirsa/spec-guard.git
cd spec-guard
python -m pip install -r requirements.txt
```

Optional editable install:

```bash
python -m pip install -e .
```

SpecGuard supports two LLM provider modes today:

- `codex`: local Codex CLI installed on the machine.
- `openai`: OpenAI Platform Responses API.

Claude Code provider integration is not an internal SpecGuard provider today. Use Claude Code externally after SpecGuard writes the approved implementation handoff.

Configure local Codex:

```bash
codex login
python -m cli.specguard auth setup --mode codex --model gpt-5.4
python -m cli.specguard auth status
```

Use `--skip-login` when Codex is already logged in and setup should not offer to launch `codex login`:

```bash
python -m cli.specguard auth setup --mode codex --model gpt-5.4 --skip-login
```

Configure OpenAI Platform:

```bash
python -m cli.specguard auth setup --mode openai
```

Inspect or reset configuration:

```bash
python -m cli.specguard auth status
python -m cli.specguard auth logout
```

For OpenAI Platform mode, provide an API key through the configured environment variable or local ignored config. The default environment variable is `OPENAI_API_KEY`.

## 1. Init Runs Discovery

Run:

```bash
python -m cli.specguard init my-feature
```

If no provider is configured, interactive `init` offers to run provider setup first.

In LLM mode, Discovery is a guided conversation. SpecGuard asks for the feature goal, users, flows, data, dependencies, risks, out-of-scope boundaries, and acceptance evidence. The configured LLM then synthesizes draft artifacts from those answers.

You can also run deterministic local Discovery without an LLM:

```bash
python -m cli.specguard init my-feature --no-llm
```

SpecGuard creates draft specs under `specs/`:

```text
specs/my-feature/
|-- discovery.md
|-- spec.md
|-- plan.md
|-- tasks.md
|-- constitution.md
`-- checklists/spec-readiness.md
```

## 2. User Refines The Spec

The generated package is a draft. Before running validation, the user should review and strengthen:

```text
specs/my-feature/discovery.md
specs/my-feature/spec.md
specs/my-feature/plan.md
specs/my-feature/tasks.md
specs/my-feature/constitution.md
specs/my-feature/checklists/spec-readiness.md
```

The spec should contain real implementation input: requirements, acceptance criteria, API or UI expectations, data ownership, authorization rules, state transitions, error cases, non-goals, and verification expectations.

If the default Discovery answers are mostly unchanged, `run` can stop early and ask the user to edit the spec package first. This prevents a generic sample draft from being treated as implementation-ready.

## 3. Optional Example Specs

Use authored examples when you want to test SpecGuard behavior before writing a real feature spec.

Quick local checks:

```bash
python -m cli.specguard run examples/example --no-llm --no-follow-up
python -m cli.specguard run examples/risk/todo-api --no-llm --no-follow-up
```

The first example should pass. The risk example should remain blocked.

To test the normal `init -> run` folder shape with authored example files:

PowerShell:

```powershell
python -m cli.specguard init your-feature-name
Copy-Item -Recurse -Force example\* specs\your-feature-name\
python -m cli.specguard run specs\your-feature-name --no-llm
```

Bash:

```bash
python -m cli.specguard init your-feature-name
cp -R example/. specs/your-feature-name/
python -m cli.specguard run specs/your-feature-name --no-llm
```

After this test, replace the copied files with your own feature's product and engineering intent.

## 4. Run Builds The Implementation Basis

Run:

```bash
python -m cli.specguard run specs/my-feature
```

`run` uses the configured LLM provider for Technical Design and SpecGuard Review. Use `--force` when regenerated derived artifacts are needed:

```bash
python -m cli.specguard run specs/my-feature --force
```

SpecGuard performs:

```text
Technical Design -> SpecGuard Review -> Test -> Contract -> Implementation Handoff
```

Generated or reused artifacts:

```text
specs/my-feature/
|-- technical-design.md
|-- readiness-review.md
|-- readiness-review.json
|-- tests/
|-- contracts/
`-- implementation-output.md
```

SpecGuard Review inspects authored spec documents and generated technical design. It excludes generated review reports, implementation-output handoffs, and test scenario files from the review input.

Readiness threshold:

- Critical: 0
- Major: 0
- Minor: 5 or fewer

Critical and Major findings block Test, Contract, and Implementation Handoff. Minor findings are allowed only when they do not hide missing requirements or implementation ambiguity.

## 5. Iterate Until READY

Interactive refinement uses this loop:

```text
Initial SpecGuard Review -> Spec Regeneration -> Verification Review -> READY or NOT READY
```

When `run` returns NOT READY, the continuation menu can:

- print the latest Readiness Findings;
- regenerate `spec.md` from those findings;
- automatically rerun Verification Review.

The initial review is broad and adversarial. Verification Review checks previous findings against the regenerated spec package and only introduces new Critical or Major findings when there is direct implementation-blocking evidence.

Strict E2E mode automates this loop for LLM-enabled runs:

```bash
python -m cli.specguard run specs/my-feature --strict-e2e --strict-max-iterations 3
```

Strict E2E records every review attempt and regeneration in:

```text
specs/my-feature/strict-e2e-trace.json
```

The final result is READY only when the normal readiness gate passes. Otherwise strict E2E reports that the configured iteration limit was exhausted.

## 6. Contract And Verification Rules

For API features, OpenAPI contracts must include at least one concrete path. An empty `paths: {}` scaffold remains a contract blocker and prevents implementation handoff until the API surface is specified.

Generated contracts derive a first-pass operation, success response, documented error responses, request and response schemas, and `x-specguard-coverage` links from acceptance criteria and error cases.

Non-API features can use:

```text
contracts/contract-exemption.md
```

The exemption must clearly state that an API contract is not applicable and include the reason.

Strict E2E does not treat markdown TDD scenarios alone as executable verification. Before implementation handoff, the package must include executable tests under `tests/` or an accepted:

```text
tests/verification-contract.md
```

The verification contract must name the expected command or machine-verifiable artifact.

## 7. External AI Implementation

After SpecGuard reports READY, hand the implementation basis to Codex, Claude Code, or another coding agent outside the SpecGuard pipeline.

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

SpecGuard does not invoke or supervise implementation while Critical or Major blockers remain.

## 8. GitHub PR And SpecGuard PR Review

After external implementation, the user opens a GitHub pull request with the completed code.

The optional `SpecGuard PR Review` workflow runs a read-only Codex-compatible review against the approved spec package and PR diff. It asks `SpecGuard PR Reviewer` to focus on spec conformance, security, reliability, API contracts, data ownership, testability, and operational risk.

Default GitHub Actions credential:

```text
SPECGUARD_OPENAI_API_KEY
```

Optional repository variables:

```text
SPECGUARD_PR_REVIEW_MODEL
SPECGUARD_REVIEW_SPEC_PATHS
```

`SPECGUARD_REVIEW_SPEC_PATHS` is important when the PR changes only implementation files under `develop/<stack>/`. Without changed files under `specs/`, the reviewer cannot infer the correct spec package unless this variable is set. It accepts comma-separated paths, for example:

```text
specs/billing-export,specs/team-invites
```

The workflow:

- checks credentials before assembling review context;
- skips safely in advisory mode when `SPECGUARD_OPENAI_API_KEY` is unavailable;
- refuses to invoke the reviewer when the selected spec package is NOT READY or stale;
- sends approved artifacts, tests, contracts, `implementation-output.md`, and the PR diff to the reviewer prompt;
- updates one PR comment with a stable hidden marker instead of creating duplicates;
- uses workflow concurrency to cancel stale review runs for the same PR.

The first version is advisory. Maintainers can make the check required later after confirming credential handling, bot identity, and review quality for their repository.

## 9. PR Readiness Gate

Pull request CI includes a stable required-check candidate named:

```text
SpecGuard Readiness Gate
```

It discovers changed SpecGuard packages under `specs/`, fails when a changed package is NOT READY, and fails when source artifacts are stale relative to `readiness-review.json`.

This gate is distinct from `SpecGuard PR Review`:

- `SpecGuard Readiness Gate` checks whether changed spec packages are READY before merge.
- `SpecGuard PR Review` checks whether implementation code appears aligned with an approved spec package.
