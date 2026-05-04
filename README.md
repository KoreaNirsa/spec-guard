# SpecGuard

SpecGuard is a validation-first framework for **Spec-Driven Development (SDD)** in AI-assisted software projects.

SpecGuard is not a prompt-to-code generator. It does not try to replace developers or create complete applications from a single instruction. Instead, it provides the structure required to turn human-written specs into reviewed, testable, implementation-ready outputs.

```text
Discovery -> Spec -> Technical Design -> Grill -> Test -> Contract -> Implementation Outputs
```

## What Is SpecGuard?

SpecGuard helps teams validate specs before they become code.

In AI-assisted development, the quality of the final implementation depends heavily on the quality of the input artifacts: the spec, technical design, test expectations, contracts, and known failure modes. SpecGuard makes those artifacts explicit and checks them before implementation work begins.

The core principle is simple:

> Humans write the spec. SpecGuard validates, strengthens, and operationalizes it.

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

### 1. The User Writes The Spec

SpecGuard assumes that the user, team, or product owner writes the initial spec. The framework does not hide product intent behind generated prose. Instead, it gives that spec a validation path.

### 2. Discovery Comes Before Technical Design

Discovery helps expose goals, constraints, assumptions, mechanisms, stress points, feasibility risks, and stop conditions before the technical design is written.

### 3. The Full Artifact Set Must Be Challenged

Grill Me is an adversarial validation step for the full SDD artifact set: discovery, spec, technical design, tests, and contracts. It does not approve artifacts; it looks for reasons the implementation basis can fail.

### 4. Tests And Contracts Are Implementation Inputs

TDD scenarios and contracts are not afterthoughts. They are part of the implementation boundary.

### 5. Implementation Outputs Come Last

Implementation outputs should be generated or written only after the SDD pipeline has produced validated artifacts.

## Workflow

```text
1. Discovery
   Capture goals, assumptions, constraints, mechanisms, risks, and stop conditions.

2. Spec
   Write requirements, acceptance criteria, and error cases.

3. Technical Design
   Define architecture, data flow, state, dependencies, and failure handling.

4. Grill
   Run adversarial validation against the full SDD artifact set.

5. Test
   Generate or preserve TDD scenarios from the spec.

6. Contract
   Validate API contract basics.

7. Implementation Outputs
   Use the validated artifacts to guide implementation, scaffolding, or downstream code output.
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
|-- tests/
`-- contracts/
```

These files define whether a feature is ready to produce implementation outputs.

## Discovery

Discovery is the pre-spec exploration step. It is adapted from a sequential self-interrogation technique, but SpecGuard uses a focused 24-question version for practical project work.

Discovery asks:

- What problem are we actually solving?
- Which assumptions are we making too early?
- What components and data flows are involved?
- What breaks first under stress?
- What should we intentionally not build?
- What would make us stop or redesign?

See [docs/deep-discovery.md](docs/deep-discovery.md).

Naming note: SpecGuard uses `Discovery` as the product workflow term. `Deep Discovery` can remain the name of the underlying technique, but the public artifact should stay simple: `discovery.md`.

## Grill Me

Grill Me is the pre-implementation adversarial validation step.

It reviews the full SDD artifact set and looks for weaknesses such as:

- missing token lifecycle rules
- weak ownership or authorization boundaries
- unsafe delete semantics
- placeholder or contradictory artifact content
- undefined retry, timeout, or rollback behavior
- incomplete state transitions
- tests that do not cover stated acceptance criteria
- contracts that do not match the intended behavior

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

Run a passing example:

```bash
python -m cli.specguard run examples/user-auth
```

Run a risk example:

```bash
python -m cli.specguard run examples/risk/todo-api
```

The risk example is expected to fail because SpecGuard detects Critical and Major implementation-basis issues.

## CLI

SpecGuard intentionally keeps the public CLI small:

```bash
python -m cli.specguard init
python -m cli.specguard run <feature-folder>
```

Default target:

```bash
python -m cli.specguard run specs
```

## Example Output

```text
[FAIL] SpecGuard pipeline
- Discovery, spec, technical design, and test scenario checks passed.
- Generated concrete grill report: examples/risk/todo-api/grill.md
- Generated machine-readable grill report: examples/risk/todo-api/grill.json
- Blocked by Grill Me findings: 1 critical, 1 major

Next steps:
- Open the human report: examples/risk/todo-api/grill.md
- Use the machine-readable report for automation: examples/risk/todo-api/grill.json
- Fix discovery.md, spec.md, technical-design.md, tests, or contracts so Critical and Major issues become explicit requirements or verified constraints.
- Run again: specguard run examples/risk/todo-api
```

## Examples

```text
examples/
|-- user-auth/
`-- risk/
    `-- todo-api/
```

- `examples/user-auth` is a passing SDD example.
- `examples/risk/todo-api` is intentionally incomplete and should be blocked by Grill Me.

## CI

The GitHub Actions workflow is split into explicit jobs:

- `Tests`: runs the pytest suite
- `Passing Example`: confirms `examples/user-auth` passes
- `Risk Example`: confirms `examples/risk/todo-api` is blocked

This makes both expected outcomes visible: a validated SDD flow should pass, and a risky implementation basis should fail.

## Development

Run tests:

```bash
pytest
```

Run local pipeline checks:

```bash
python -m cli.specguard run examples/user-auth
python -m cli.specguard run examples/risk/todo-api
```

The test suite covers:

- passing example behavior
- blocked risk example behavior
- `grill.json` generation
- non-destructive TDD generation
- placeholder validation
- invalid OpenAPI contract detection
- required Discovery artifacts

## Current Capabilities

- Discovery artifacts
- Spec and Technical Design validation
- local heuristic Grill Me engine
- human and JSON Grill reports
- TDD scenario generation
- basic OpenAPI contract checks
- CI coverage for passing and blocked flows

## Future Scope

SpecGuard may support implementation outputs after validation, but only as downstream products of the SDD pipeline.

Potential future areas:

- guided code output from validated artifacts
- implementation scaffolding
- implementation-plan generation
- model-backed Grill Me review
- richer OpenAPI and JSON Schema validation
- package publishing
- editor integrations

The intent is not prompt-to-code automation. The intent is validated implementation readiness.

## Contributing

Contributions should preserve the SDD workflow:

```text
Discovery -> Spec -> Technical Design -> Grill -> Test -> Contract -> Implementation Outputs
```

Before opening a pull request, make sure:

- discovery, spec, and technical design artifacts are included for feature work
- Critical and Major Grill Me findings are resolved or intentionally documented
- tests are included or updated
- `pytest` passes

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
