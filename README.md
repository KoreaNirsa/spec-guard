# SpecGuard

SpecGuard is a validation-first framework for **Spec-Driven Development (SDD)** in AI-assisted software projects.

SpecGuard is not a prompt-to-code generator. It does not try to replace developers or create complete applications from a single instruction. Instead, it provides the structure required to turn human-written specs into reviewed, testable, implementation-ready outputs.

```text
Discovery -> Spec Refinement -> Technical Design -> Grill -> Test -> Contract -> Implementation Outputs -> AI Implementation
```

## What Is SpecGuard?

SpecGuard helps teams validate specs before they become code.

In AI-assisted development, the quality of the final implementation depends heavily on the quality of the input artifacts: the spec, technical design, test expectations, contracts, and known failure modes. SpecGuard makes those artifacts explicit and checks them before implementation work begins.

The core principle is simple:

> The user owns the spec. SpecGuard generates and validates the supporting implementation basis around it.

SpecGuard is for teams that want AI-assisted development without skipping engineering discipline.

## Why Spec-Driven Development?

Spec-Driven Development, or SDD, is the practice of treating the spec as the source of implementation control.

In SpecGuard, the spec is not a loose prompt. It is a structured artifact that must be supported by discovery, technical design, risk review, tests, and contracts. The goal is to produce implementation outputs that are grounded in validated intent rather than improvised from an underspecified request.

SpecGuard focuses on the steps that often fail in AI-assisted development:

- unclear requirements
- implicit assumptions
- missing technical design decisions
- weak authorization boundaries
- untested edge cases
- undefined failure behavior
- contracts that do not match intended behavior

## Core Principles

### 1. The User Owns The Spec

SpecGuard starts with Discovery and creates a draft spec, but the user is responsible for reviewing, correcting, and strengthening that spec. The framework does not hide product intent behind generated prose.

### 2. Discovery Comes Before Technical Design

Discovery helps expose goals, constraints, assumptions, mechanisms, stress points, feasibility risks, and stop conditions before the technical design is written.

### 3. The Implementation Basis Must Be Challenged

Grill Me is an adversarial validation step for the implementation basis produced from discovery, spec, and technical design. It does not approve artifacts; it looks for reasons the implementation basis can fail.

### 4. Tests And Contracts Are Implementation Inputs

TDD scenarios and contracts are not afterthoughts. They are part of the implementation boundary.

### 5. Implementation Outputs Come Last

Implementation outputs should be generated only after the SDD pipeline has produced validated artifacts. Application code is written later by the user, Codex, Claude Code, or another coding agent.

## Workflow

```text
1. Discovery
   Run `specguard init`, answer discovery questions, and generate draft specs under `specs/`.

2. Spec Refinement
   Review and strengthen the generated `spec.md` files.

3. Technical Design
   Run `specguard run`; SpecGuard generates or reuses `technical-design.md`.

4. Grill
   SpecGuard runs adversarial validation against discovery, spec, and technical design.

5. Test
   SpecGuard generates or preserves TDD scenarios from the spec.

6. Contract
   SpecGuard generates or reuses API contract scaffolds and validates contract basics.

7. Implementation Outputs
   SpecGuard generates `implementation-output.md` for downstream coding agents.

8. AI Implementation
   Use Codex, Claude Code, or another coding agent to implement under `develop/<stack>/`.
```

## Feature Folder

A SpecGuard feature is represented as a folder of development artifacts:

```text
feature/
|-- discovery.md
|-- spec.md
|-- technical-design.md
|-- grill.md
|-- grill.json
|-- implementation-output.md
|-- tests/
`-- contracts/
```

These files define whether a feature is ready to produce implementation outputs.

## Discovery

Discovery is the init-time exploration step that produces draft specs. It is adapted from a sequential self-interrogation technique, but SpecGuard uses a focused question set for practical project work.

Discovery asks:

- What problem are we actually solving?
- Which assumptions are we making too early?
- What components and data flows are involved?
- What breaks first under stress?
- What should we intentionally not build?
- What would make us stop or redesign?

See [docs/deep-discovery.md](docs/deep-discovery.md).

Naming note: SpecGuard uses `Discovery` as the product workflow term. `Deep Discovery` can remain the name of the underlying technique, but the public artifact should stay simple: `discovery.md`.

See [docs/workflow.md](docs/workflow.md) for the end-to-end user workflow.

## Grill Me

Grill Me is the pre-implementation adversarial validation step.

It reviews Discovery, `spec.md`, and `technical-design.md`, then looks for weaknesses such as:

- missing token lifecycle rules
- weak ownership or authorization boundaries
- unsafe delete semantics
- placeholder or contradictory artifact content
- undefined retry, timeout, or rollback behavior
- incomplete state transitions
- acceptance criteria that are too weak to test
- contract behavior that is implied but not specified

Outputs:

- `grill.md`: human-readable risk report
- `grill.json`: machine-readable report for CI and automation

Critical or Major Grill Me findings block the pipeline.

## Quick Start

Clone and install:

```bash
git clone https://github.com/KoreaNirsa/spec-guard.git
cd spec-guard
pip install -r requirements.txt
```

Configure an LLM provider. Local Codex is the recommended first mode when Codex is already installed and logged in:

```bash
python -m cli.specguard auth setup --mode codex
```

OpenAI Platform mode is also supported:

```bash
python -m cli.specguard auth setup --mode openai
```

Start discovery and generate draft specs:

```bash
python -m cli.specguard init my-feature
```

If you run `init` without answers, each Discovery question shows a default. Press Enter to accept it:

```bash
python -m cli.specguard init
```

To inspect the defaults from the CLI:

```bash
python -m cli.specguard init --help
```

Review and strengthen the generated spec:

```text
specs/my-feature/spec.md
```

Run the validation and artifact workflow:

```bash
python -m cli.specguard run specs/my-feature
```

In an interactive terminal, `run` stays open after the pipeline and offers follow-up actions:

- run Grill Me review from the current files
- inspect the latest Grill Me review
- regenerate `spec.md` from Grill Me findings and automatically rerun Grill Me

Use the generated implementation guide with a coding agent:

```text
specs/my-feature/implementation-output.md
develop/<stack>/
```

## CLI

SpecGuard intentionally keeps the public CLI small:

```bash
python -m cli.specguard init [feature-name]
python -m cli.specguard run <feature-folder>
```

Interactive `init` accepts Enter for every default answer.

## LLM Provider Modes

SpecGuard uses an LLM to synthesize the draft spec after guided Discovery answers are collected, and for technical design generation and Grill Me during the normal CLI workflow.

Supported modes:

- `codex`: uses the local Codex CLI installed on the machine.
- `openai`: uses the OpenAI Platform Responses API.

Claude Code support is planned for a future provider mode.

Configure or reconfigure the provider:

```bash
python -m cli.specguard auth setup
python -m cli.specguard auth status
python -m cli.specguard auth logout
```

Use local Codex:

```bash
python -m cli.specguard auth setup --mode codex
```

If a local Codex request times out during a larger Grill Me follow-up, increase the provider timeout:

```bash
python -m cli.specguard auth setup --mode codex --timeout 240 --skip-login
```

Use OpenAI Platform with an environment variable:

Set an API key:

```bash
export OPENAI_API_KEY=...
```

Optionally choose a model:

```bash
export SPECGUARD_LLM_MODEL=gpt-5.1
```

Or store an API key in the local ignored `.specguard/config.json` file:

```bash
python -m cli.specguard auth setup --mode openai --api-key sk-...
```

Generate a draft spec from guided Discovery:

```bash
python -m cli.specguard init my-feature
```

SpecGuard shows Discovery questions immediately so the terminal is always ready for input. Press Enter to accept a visible default, or type `done` when the answers are ready to become a draft spec. The configured LLM is used after the guided answers are collected to synthesize the draft `spec.md`.

Generate or regenerate LLM-backed technical design and Grill Me output:

```bash
python -m cli.specguard run specs/my-feature --force
```

After `run`, SpecGuard shows a continuation menu in interactive terminals. Use it to run Grill Me review from the current files, inspect the latest review, or regenerate `spec.md` from Grill Me findings and automatically rerun the pipeline so Grill Me is refreshed. Initial pipeline, LLM follow-up, and rerun requests show an activity bar with elapsed time so the CLI does not appear frozen. Press `q` to exit the menu. Use `--follow-up` to force the menu in terminals such as Git Bash if auto-detection fails. Use `--no-follow-up` when a script should exit immediately after the pipeline.

Notes:

- `--no-llm` is available for local deterministic checks and CI examples.
- `--follow-up` forces the interactive post-run action menu.
- `--no-follow-up` disables the interactive post-run action menu.
- `run` generates missing artifacts and refreshes stale tests and contracts when `spec.md` changes.
- `auth status` shows the configured provider timeout.
- `--force` is useful when you want to regenerate derived artifacts even if SpecGuard does not detect them as stale.
- `SPECGUARD_LLM_MODEL` can be overridden per command with `--llm-model`.
- `--llm-mode codex` and `--llm-mode openai` can override the configured mode for one command.
- The OpenAI adapter uses the Responses API through standard HTTP; no SDK dependency is required.

For scripted or CI setup:

```bash
python -m cli.specguard init billing-export --non-interactive --no-llm
```

Run all initialized specs:

```bash
python -m cli.specguard run specs --no-llm --no-follow-up
```

## Example Output

```text
  ____                  ____                     _
 / ___| _ __   ___  ___/ ___|_   _  __ _ _ __ __| |
 \___ \| '_ \ / _ \/ __| |  _| | | |/ _` | '__/ _` |
  ___) | |_) |  __/ (__| |_| | |_| | (_| | | | (_| |
 |____/| .__/ \___|\___|\____|\__,_|\__,_|_|  \__,_|
       |_|

[FAIL] SpecGuard pipeline
- Discovery and spec checks passed.
- Reused technical design: examples/risk/todo-api/technical-design.md
- Technical design checks passed.
- Generated heuristic grill report: examples/risk/todo-api/grill.md
- Generated heuristic machine-readable grill report: examples/risk/todo-api/grill.json
- Blocked by Grill Me findings: 1 critical, 1 major

Next steps:
- Open the human report: examples/risk/todo-api/grill.md
- Use the machine-readable report for automation: examples/risk/todo-api/grill.json
- Fix discovery.md, spec.md, or technical-design.md so Critical and Major issues become explicit requirements or verified constraints.
- Run again: specguard run examples/risk/todo-api
```

## Examples

```text
examples/
|-- example/
`-- risk/
    `-- todo-api/
```

- `examples/example` is a passing SDD example.
- `examples/risk/todo-api` is intentionally incomplete and should be blocked by Grill Me.

## CI

The GitHub Actions workflow is split into explicit jobs:

- `Tests`: runs the pytest suite
- `Passing Example`: confirms `examples/example` passes
- `Risk Example`: confirms `examples/risk/todo-api` is blocked

CI uses explicit `--no-llm` checks because repository CI should not require a personal Codex login or OpenAI API key. This makes both expected outcomes visible: a validated SDD flow should pass, and a risky implementation basis should fail.

## Development

Run tests:

```bash
pytest
```

Run local pipeline checks:

```bash
python -m cli.specguard run examples/example --no-llm
python -m cli.specguard run examples/risk/todo-api --no-llm
```

The test suite covers:

- passing example behavior
- blocked risk example behavior
- Discovery-based init behavior
- supporting artifact generation from spec basis
- `grill.json` generation
- non-destructive TDD generation
- placeholder validation
- invalid OpenAPI contract detection
- required Discovery artifacts

## Current Capabilities

- Discovery artifacts
- guided LLM Discovery conversation
- draft spec generation from Discovery
- Spec and Technical Design validation
- LLM-backed Grill Me engine
- interactive post-run review and spec revision loop
- local heuristic fallback for `--no-llm` and CI examples
- human and JSON Grill reports
- TDD scenario generation
- basic OpenAPI contract checks
- implementation output guide generation
- CI coverage for passing and blocked flows

## Future Scope

SpecGuard may support implementation outputs after validation, but only as downstream products of the SDD pipeline.

Potential future areas:

- richer agent handoff templates
- implementation output conventions for `develop/<stack>/`
- implementation-plan generation
- model-backed Grill Me review
- richer OpenAPI and JSON Schema validation
- package publishing
- editor integrations

The intent is not prompt-to-code automation. The intent is validated implementation readiness.

Generated application code should live outside the specs package, typically under:

```text
develop/spring/
develop/react/
develop/fastapi/
```

## Contributing

Contributions should preserve the SDD workflow:

```text
Discovery -> Spec Refinement -> Technical Design -> Grill -> Test -> Contract -> Implementation Outputs
```

Before opening a pull request, make sure:

- discovery, spec, and technical design artifacts are included for feature work
- Critical and Major Grill Me findings are resolved or intentionally documented
- tests are included or updated
- `pytest` passes

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
