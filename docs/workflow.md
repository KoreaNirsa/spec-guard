# SpecGuard Workflow

SpecGuard is not a code generator. It is a spec refinement and validation workflow for AI-assisted development.

The intended user experience is:

```text
Discovery -> Draft Specs -> User Refinement -> Technical Design -> Grill Me -> Test -> Contract -> Implementation Outputs
```

After that, the user can run Codex, Claude Code, or another coding agent against the generated spec package.

## 1. Init Runs Discovery

Run:

```bash
python -m cli.specguard init example
```

SpecGuard asks Discovery questions and creates draft specs under `specs/`:

```text
specs/example/
|-- discovery.md
`-- spec.md
```

The generated `spec.md` follows a Spec Kit-inspired shape:

- user scenarios and testing
- functional requirements
- acceptance criteria
- error cases
- key entities
- out-of-scope boundaries
- review checklist

## 2. User Refines The Spec

The user reviews and edits:

```text
specs/example/spec.md
```

This is the main human-owned artifact. SpecGuard can draft it, but it should not replace product or engineering judgment.

## 3. Run Builds The Implementation Basis

Run:

```bash
python -m cli.specguard run specs/example
```

SpecGuard then performs:

```text
Technical Design -> Grill Me -> Test -> Contract -> Implementation Outputs
```

Generated or reused artifacts:

```text
specs/example/
|-- technical-design.md
|-- grill.md
|-- grill.json
|-- tests/
|-- contracts/
`-- implementation-output.md
```

SpecGuard does not overwrite existing technical design, tests, or contracts by default.

## 4. User Refines And Repeats

If Grill Me blocks the workflow, update:

```text
discovery.md
spec.md
technical-design.md
```

Then run:

```bash
python -m cli.specguard run specs/example
```

Repeat until Critical and Major findings are resolved.

## 5. Coding Agents Implement Later

After SpecGuard passes, hand the implementation basis to Codex, Claude Code, or another coding agent.

Coding agents should focus on:

```text
spec.md
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
