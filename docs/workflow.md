# SpecGuard Workflow

SpecGuard is not a code generator. It is a spec refinement and validation workflow for AI-assisted development.

The intended user experience is:

```text
Discovery -> Draft Specs -> User Refinement -> Technical Design -> Grill Me -> Test -> Contract -> Implementation Outputs
```

After that, the user can run Codex, Claude Code, or another coding agent against the generated spec package.

## 0. Configure LLM Provider

SpecGuard supports two LLM provider modes today:

- `codex`: local Codex CLI installed on the machine.
- `openai`: OpenAI Platform Responses API.

Claude Code provider integration is planned later. For now, Claude Code should be used separately after SpecGuard produces implementation outputs.

Configure local Codex:

```bash
python -m cli.specguard auth setup --mode codex
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

## 3. Run Builds The Implementation Basis

Run:

```bash
python -m cli.specguard run specs/my-feature
```

`run` uses the configured LLM provider for Technical Design and Grill Me. Use `--force` when regenerated derived artifacts are needed:

```bash
python -m cli.specguard run specs/my-feature --force
```

SpecGuard then performs:

```text
Technical Design -> Grill Me -> Test -> Contract -> Implementation Outputs
```

Grill Me reviews every authored spec document in the feature folder, excluding generated Grill Me reports, implementation-output handoffs, and test scenario files. The implementation-ready threshold is Critical=0, Major=0, and Minor<=5. Ready results are highlighted in green in the CLI. Not-ready results are highlighted in red and block Test, Contract, and Implementation Outputs.

Generated or reused artifacts:

```text
specs/my-feature/
|-- technical-design.md
|-- grill.md
|-- grill.json
|-- tests/
|-- contracts/
`-- implementation-output.md
```

SpecGuard generates missing artifacts and refreshes stale tests and contracts when `spec.md` has changed. Use `--force` when derived artifacts, including `technical-design.md`, should be regenerated even if SpecGuard does not detect them as stale.

In an interactive terminal, `run` opens a continuation menu after the pipeline. The user can run Grill Me review from the current files, inspect the latest Grill Me review, or ask the configured LLM to regenerate `spec.md` from the findings and automatically rerun the pipeline so Grill Me is refreshed. Initial pipeline, LLM follow-up, and rerun requests show an activity bar with elapsed time. Press `q` to exit the menu. Use `--follow-up` to force this menu when terminal detection fails. Scripts can disable it with `--no-follow-up`.

If a local Codex follow-up request times out, check `python -m cli.specguard auth status` and increase the timeout:

```bash
python -m cli.specguard auth setup --mode codex --timeout 240 --skip-login
```

Use `--no-llm` only for deterministic local checks or CI examples:

```bash
python -m cli.specguard run specs/my-feature --no-llm
```

## 4. User Refines And Repeats

If Grill Me blocks the workflow, update:

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

Or stay in the post-run menu and choose the LLM spec revision action. Repeat until the Grill Me readiness threshold is met.

## 5. Coding Agents Implement Later

After SpecGuard passes, hand the implementation basis to Codex, Claude Code, or another coding agent.

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
grill.md
grill.json
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
