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
specs/my-feature/spec.md
```

This is the main human-owned artifact. SpecGuard can draft it, but it should not replace product or engineering judgment.

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

Use `--no-llm` only for deterministic local checks or CI examples:

```bash
python -m cli.specguard run specs/my-feature --no-llm
```

## 4. User Refines And Repeats

If Grill Me blocks the workflow, update:

```text
discovery.md
spec.md
technical-design.md
```

Then run:

```bash
python -m cli.specguard run specs/my-feature
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
