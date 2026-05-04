# SpecGuard

SpecGuard is an early-stage framework for **Spec-Driven Development (SDD)** in AI-assisted software projects.

It does not generate application code. Instead, it makes the development process harder to misuse:

```text
Discovery -> Spec -> Design -> Grill -> Test -> Contract
```

SpecGuard helps teams define intent, expose weak assumptions, block risky designs, and produce testable implementation inputs before code generation begins.

## Why SpecGuard?

AI coding tools can produce useful code quickly, but they also make it easy to skip the steps that keep software reliable:

- unclear requirements
- missing design decisions
- untested edge cases
- weak authorization boundaries
- undocumented failure behavior
- contracts that do not match intended behavior

SpecGuard treats those steps as first-class artifacts. A feature is not ready for implementation until its discovery, spec, design, risk review, test scenarios, and contract checks are in place.

## Core Concepts

### Spec-Driven Development

Spec-Driven Development, or SDD, is the practice of treating the spec as the control surface for implementation.

In SpecGuard, a feature folder contains the artifacts that define whether implementation is allowed to proceed:

```text
feature/
|-- discovery.md
|-- spec.md
|-- design.md
|-- grill.md
|-- grill.json
|-- tests/
`-- contracts/
```

### Deep Discovery

Deep Discovery is the pre-spec exploration step. It is adapted from a 100-question sequential self-interrogation technique, but the MVP uses 24 focused questions so the workflow stays practical.

Use Deep Discovery to uncover goals, constraints, assumptions, mechanisms, failure modes, and stop conditions before writing `spec.md`.

See [docs/deep-discovery.md](docs/deep-discovery.md).

### Grill Me

Grill Me is the post-design risk review step. It does not approve the design. It attacks it.

The local MVP engine looks for issues such as missing token lifecycle rules, weak ownership boundaries, unsafe delete semantics, placeholder design content, and undefined failure behavior.

Outputs:

- `grill.md`: human-readable risk report
- `grill.json`: machine-readable report for CI and automation

Critical or Major Grill Me findings fail the pipeline.

## Quick Start

Clone the repository and install dependencies:

```bash
git clone https://github.com/KoreaNirsa/spec-guard.git
cd spec-guard
pip install -r requirements.txt
```

Run the passing example:

```bash
python -m cli.specguard run examples/user-auth
```

Run the intentionally risky example:

```bash
python -m cli.specguard run examples/risk/todo-api
```

The risk example should fail. That failure is expected: it demonstrates that SpecGuard can block a design with Critical or Major findings.

## Example Output

```text
[FAIL] SpecGuard pipeline
- Discovery, spec, design, and test scenario checks passed.
- Generated concrete grill report: examples/risk/todo-api/grill.md
- Generated machine-readable grill report: examples/risk/todo-api/grill.json
- Blocked by Grill Me findings: 1 critical, 1 major

Next steps:
- Open the human report: examples/risk/todo-api/grill.md
- Use the machine-readable report for automation: examples/risk/todo-api/grill.json
- Fix spec.md or design.md so Critical and Major issues become explicit requirements.
- Run again: specguard run examples/risk/todo-api
```

## Workflow

```text
1. Discover
   Write discovery.md using the Deep Discovery phases.

2. Specify
   Write spec.md with requirements, acceptance criteria, and error cases.

3. Design
   Write design.md with architecture, data flow, state, dependencies, and failure handling.

4. Grill
   Run SpecGuard. Critical and Major findings block the pipeline.

5. Test
   Generate or preserve TDD scenarios under tests/.

6. Contract
   Validate OpenAPI basics under contracts/.
```

## CLI

SpecGuard intentionally keeps the public CLI small:

```bash
python -m cli.specguard init
python -m cli.specguard run <feature-folder>
```

Default run target:

```bash
python -m cli.specguard run specs
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

This keeps the two expected outcomes visible in CI: a good spec-driven flow should pass, and a risky design should fail.

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

The test suite currently covers:

- passing example behavior
- blocked risk example behavior
- `grill.json` generation
- non-destructive TDD generation
- placeholder validation
- invalid OpenAPI contract detection
- required Deep Discovery artifacts

## Project Status

SpecGuard is in MVP development.

Current scope:

- Deep Discovery artifacts
- Spec and Design validation
- local heuristic Grill Me engine
- human and JSON Grill reports
- TDD scenario generation
- basic OpenAPI contract checks
- CI coverage for passing and blocked flows

Not in scope yet:

- application code generation
- model-backed Grill Me execution
- package publishing
- VS Code extension
- full OpenAPI or JSON Schema validation

## Contributing

Contributions should preserve the SDD workflow:

```text
Discovery -> Spec -> Design -> Grill -> Test -> Contract
```

Before opening a pull request, make sure:

- discovery/spec/design artifacts are included for feature work
- Critical and Major Grill Me findings are resolved or intentionally documented
- tests are included or updated
- `pytest` passes

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
