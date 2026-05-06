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
python -m cli.specguard auth setup --mode codex --model gpt-5.4
```

Codex mode defaults to `gpt-5.4` when setup asks for a model. Use `--model` to make the choice explicit, and use `--skip-login` when Codex is already logged in.

Configure OpenAI Platform:

```bash
python -m cli.specguard auth setup --mode openai
```

Inspect or reset configuration:

```bash
python -m cli.specguard auth status
python -m cli.specguard auth logout
```

## 1. Init Runs Discovery

Run:

```bash
python -m cli.specguard init my-feature
```

If no provider is configured, interactive `init` offers to run provider setup first.

In LLM mode, Discovery is a short guided conversation. SpecGuard shows each question immediately, includes a visible default, and waits for user input without blocking on an LLM response. The user answers naturally, presses Enter to accept a default, or types `done` / `complete` when the conversation is ready to become a draft spec. The configured LLM then synthesizes the draft `spec.md` from the guided answers.

For OpenAI Platform mode, set an API key or store it in the local ignored config:

```bash
export OPENAI_API_KEY=...
export SPECGUARD_LLM_MODEL=gpt-5.1
python -m cli.specguard auth setup --mode openai
```

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
`-- checklists/
```

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

The repository includes `example/`, a pre-run authored spec package. Treat it as the state after `init` has created draft files and a user has replaced those drafts with real development requirements.

The package is for testing SpecGuard behavior, not for implementing SpecGuard itself. It uses the same Spec Kit-inspired structure expected from real feature planning:

```text
example/
|-- discovery.md
|-- spec.md
|-- plan.md
|-- tasks.md
|-- constitution.md
`-- checklists/spec-readiness.md
```

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

After this test, replace the copied files with your own feature's product behavior, API or UI expectations, data ownership, authorization rules, state transitions, error cases, and acceptance criteria.

## 3. Run Builds The Implementation Basis

Run:

```bash
python -m cli.specguard run specs/my-feature
```

`run` uses the configured LLM provider for Technical Design and SpecGuard Review. Use `--force` when regenerated derived artifacts are needed:

```bash
python -m cli.specguard run specs/my-feature --force
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

Strict E2E mode automates that loop for LLM-enabled runs:

```bash
python -m cli.specguard run specs/my-feature --strict-e2e --strict-max-iterations 3
```

Strict E2E records every review attempt and every spec regeneration in `strict-e2e-trace.json`. Regeneration uses the previous Readiness Findings as the required backlog, then reruns Verification Review. The final result is READY only when the normal readiness gate passes; otherwise strict E2E reports that the configured iteration limit was exhausted.

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

`implementation-output.md` is an external handoff guide. It includes machine-readable readiness status, the `external_handoff` implementation boundary, and the approved artifact list for coding agents.

SpecGuard generates missing artifacts and refreshes stale tests and contracts when `spec.md` has changed. Use `--force` when derived artifacts, including `technical-design.md`, should be regenerated even if SpecGuard does not detect them as stale.
For API features, OpenAPI contracts must include at least one concrete path. An empty `paths: {}` scaffold remains a contract blocker and prevents implementation handoff until the API surface is specified or the feature documents a non-API contract path in a later workflow.

In an interactive terminal, `run` opens a continuation menu after the pipeline. The user can inspect the latest Readiness Findings or ask the configured LLM to regenerate `spec.md` from the findings and automatically run Verification Review so SpecGuard Review checks whether the regenerated spec is ready. Initial pipeline, LLM follow-up, and rerun requests show an activity bar with elapsed time. Press `q` to exit the menu. Use `--follow-up` to force this menu when terminal detection fails. Scripts can disable it with `--no-follow-up`.

If a local Codex follow-up request times out, check `python -m cli.specguard auth status` and increase the timeout:

```bash
python -m cli.specguard auth setup --mode codex --timeout 240 --skip-login
```

Use `--no-llm` only for deterministic local checks or CI examples:

```bash
python -m cli.specguard run specs/my-feature --no-llm
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
python -m cli.specguard run specs/my-feature
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
