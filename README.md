# SpecGuard

Spec -> Design -> Grill -> Test -> Code

SpecGuard is not a code generator. It is a small control system for AI-driven development: write the spec, force the design, grill the weak points, generate test scenarios, then implement.

## Start With Examples

The MVP is example-first. Run the pipeline against real feature folders before creating new abstractions.

```bash
python -m cli.specguard run examples/user-auth
python -m cli.specguard run examples/risk/todo-api
```

`examples/user-auth` is the passing example. `examples/risk/todo-api` is intentionally risky and should be blocked by Grill Me findings.

Each example contains:

```text
examples/user-auth/
|-- spec.md
|-- design.md
|-- grill.md
|-- grill.json
|-- tests/
|   `-- user-auth.test.md
`-- contracts/
    `-- openapi.yaml
```

## Minimal CLI

The public CLI should stay small while the project is young.

```bash
# prepare local folders
python -m cli.specguard init

# run the full guardrail pipeline
python -m cli.specguard run examples/user-auth
```

Advanced commands exist for development, but the product should feel like one command: `run`.

## Tests

```bash
pytest
```

The test suite checks the passing example, the blocked risk example, non-destructive TDD generation, placeholder validation, and invalid contract detection.

## What Run Does

```text
Spec Validation
  -> Design Validation
  -> Grill Me
  -> TDD Scenario Generation
  -> Contract Check
```

Critical or Major Grill Me findings stop the pipeline before tests and contract checks continue.

When the pipeline is blocked, the CLI prints the report paths and the next command to run:

```text
Next steps:
- Open the human report: examples/risk/todo-api/grill.md
- Use the machine-readable report for automation: examples/risk/todo-api/grill.json
- Fix spec.md or design.md so Critical and Major issues become explicit requirements.
- Run again: specguard run examples/risk/todo-api
```

## Grill Me

Grill Me is the core differentiator. It should feel uncomfortable in a useful way.

Instead of saying "looks good", it asks what can break:

- Is token expiration missing?
- Can one user access another user's data?
- Are state transitions invalid or vague?
- Are retry, timeout, and rollback rules testable?
- Can duplicate requests create duplicate side effects?

Current MVP behavior:

- Local heuristic grill reports concrete issues without an AI dependency.
- Critical and Major findings fail `specguard run`.
- `grill.md` is for humans and `grill.json` is for CI or later automation.
- The prompt is embedded in the report so a model-based review can be added next.
- Critical and Major findings should become acceptance criteria before implementation.

## Project Structure

```text
spec-guard/
|-- examples/
|   |-- user-auth/
|   `-- risk/
|       `-- todo-api/
|-- specs/
|   `-- user-auth/
|-- tools/
|   |-- spec_validator.py
|   |-- grill_engine.py
|   |-- tdd_generator.py
|   |-- contract_checker.py
|   `-- runner.py
|-- templates/
|-- cli/
`-- .github/workflows/
```

## MVP Scope

- Examples first
- Minimal CLI: `init`, `run`
- Grill results that expose real implementation risk
- TDD scenarios generated from spec folders

## Why SpecGuard?

| Problem | Common AI Workflow | SpecGuard |
| --- | --- | --- |
| Missing requirements | Frequent | Blocked |
| Missing design | Common | Required |
| Weak tests | Common | Generated before code |
| AI mistakes | Hard to detect | Grilled before implementation |

## License

MIT
