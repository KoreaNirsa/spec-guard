![SpecGuard verification-first workflow](assets/spec_guard_logo.png)

# SpecGuard

SpecGuard is a validation-first workflow for AI-assisted software development.

It is not a prompt-to-code generator. SpecGuard helps you turn an idea into a reviewed, testable, implementation-ready spec package before Codex, Claude Code, or another coding agent starts writing application code.

```text
Discovery -> Spec Package -> Technical Design -> Initial Grill Review
-> Spec Regeneration -> Verification Review -> Test -> Contract
-> Implementation Outputs -> AI Implementation
```

## Core Value

AI coding works best when the implementation input is explicit. SpecGuard focuses on the parts that often fail before code is written:

- unclear requirements
- hidden assumptions
- missing authorization or ownership rules
- weak acceptance criteria
- undefined errors, retries, timeouts, and state transitions
- contracts that do not match the intended behavior

The user owns the spec. SpecGuard drafts, challenges, and validates the implementation basis around it.

## Installation

```bash
git clone https://github.com/KoreaNirsa/spec-guard.git
cd spec-guard
pip install -r requirements.txt
```

## LLM Provider Setup

Local Codex mode:

```bash
python -m cli.specguard auth setup --mode codex --model gpt-5.4
```

Codex mode defaults to `gpt-5.4` during setup. Pass `--model` again to change it later, or use `--llm-model` on `init` / `run` for a one-off override.

OpenAI Platform mode:

```bash
python -m cli.specguard auth setup --mode openai
```

Useful auth commands:

```bash
python -m cli.specguard auth status
python -m cli.specguard auth logout
```

If local Codex requests time out, increase the timeout:

```bash
python -m cli.specguard auth setup --mode codex --timeout 240 --skip-login
```

If `codex login` is already complete but setup cannot launch the login command, use:

```bash
python -m cli.specguard auth setup --mode codex --model gpt-5.4 --skip-login
```

You can also point SpecGuard at a full Codex executable path:

```bash
python -m cli.specguard auth setup --mode codex --model gpt-5.4 --codex-command "C:\path\to\codex.cmd"
```

## Recommended User Flow

Use a real feature name. Running `init` without a name creates a default sample feature and is mostly useful for trying the CLI.

### 1. Initialize A Spec

```bash
python -m cli.specguard init your-feature-name
```

After running this command, participate in the 8-step Discovery process. Answer with the actual goal, users, flows, data, dependencies, risks, and acceptance evidence for the feature.

SpecGuard creates a draft spec package under:

```text
specs/your-feature-name/
|-- discovery.md
|-- spec.md
|-- plan.md
|-- tasks.md
|-- constitution.md
`-- checklists/spec-readiness.md
```

Review and edit these files before continuing. The generated text is a draft, not a final product decision.

This is where the real development spec is written. Add the actual product behavior, API or UI expectations, data ownership, authorization rules, state transitions, error cases, and acceptance criteria before running validation.

If the default Discovery answers are mostly unchanged, `run` stops early and asks you to edit the spec package first. This prevents a generic sample draft from being treated as an implementation-ready feature.

### Try SpecGuard With Authored Example Specs

The `example/` directory contains a realistic authored spec package. It represents the point after a user has run `init`, reviewed the generated draft, and written the real development intent before running `run`.

Use it only to test SpecGuard behavior. It is not product guidance for this repository, but the files are intentionally structured like production specs so the review workflow exercises a real package shape.

PowerShell:

```powershell
python -m cli.specguard init your-feature-name
Copy-Item -Recurse -Force example\* specs\your-feature-name\
```

Bash:

```bash
python -m cli.specguard init your-feature-name
cp -R example/. specs/your-feature-name/
```

This replaces the initial draft with the authored example package and lets you verify the full pipeline before writing your own feature specs.

### 2. Run SpecGuard

```bash
python -m cli.specguard run specs/your-feature-name
```

This starts the implementation-readiness pipeline:

```text
Technical Design -> Initial Grill Review -> READY or NOT READY
```

Grill Review inspects the full spec package and generated technical design. It looks for blockers before implementation begins.

Run is a validator, not the place where product intent is invented. Use it after the spec package has enough real detail to review.

### 3. Iterate Until Ready

If Grill Review returns NOT READY, use the continuation menu:

```text
[1] View Grill Me review
[2] Regenerate spec from Grill Me review (auto-runs Grill Me review after)
[q] Exit
```

The loop is:

```text
Initial Grill Review -> Spec Regeneration -> Verification Review -> READY or NOT READY
```

The initial review is broad and adversarial. After spec regeneration, Verification Review checks whether previous blockers were resolved and only adds new Critical or Major findings when there is direct implementation-blocking evidence.

Repeat until SpecGuard reports READY.

### 4. Start Implementation

When the spec package is ready, SpecGuard continues through:

```text
Test -> Contract -> Implementation Outputs
```

Then use:

```text
specs/your-feature-name/implementation-output.md
develop/<stack>/
```

Give the implementation output guide to Codex, Claude Code, or another coding agent, and place application code under `develop/<stack>/`.

## Grill Review Readiness

SpecGuard uses this readiness threshold:

- Critical: 0
- Major: 0
- Minor: 5 or fewer

Critical and Major findings block implementation. Minor findings are allowed only when they do not hide missing requirements or implementation ambiguity.

CLI output highlights READY states in green and NOT READY states in red.

## CLI Reference

```bash
python -m cli.specguard init <spec-name>
python -m cli.specguard run specs/<spec-name>
```

Useful options:

- `--force`: regenerate derived artifacts such as technical design.
- `--follow-up`: force the interactive continuation menu.
- `--no-follow-up`: exit immediately after the pipeline.
- `--no-llm`: use local deterministic checks and heuristic Grill Review.

CI or scripted example:

```bash
python -m cli.specguard init billing-export --non-interactive --no-llm
python -m cli.specguard run specs/billing-export --no-llm --no-follow-up
```

## Development

Run tests:

```bash
pytest
```

Run local example checks:

```bash
python -m cli.specguard run examples/example --no-llm
python -m cli.specguard run examples/risk/todo-api --no-llm
```

## Contributing

Contributions should preserve the SpecGuard workflow:

```text
Discovery -> Spec Package -> Technical Design -> Grill Review
-> Test -> Contract -> Implementation Outputs
```

Before opening a pull request:

- keep generated application code outside `specs/`
- resolve or intentionally document Critical and Major Grill Review findings
- include or update tests
- run `pytest`

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
