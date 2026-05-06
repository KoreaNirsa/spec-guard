![SpecGuard verification-first workflow](assets/spec_guard_logo.png)

# SpecGuard

SpecGuard is a validation-first workflow for AI-assisted software development.

It is not a prompt-to-code generator. SpecGuard helps you turn an idea into a reviewed, testable, implementation-ready spec package before an external Codex, Claude Code, or another coding agent starts writing application code.

```text
Discovery -> Spec Package -> Technical Design -> Initial SpecGuard Review
-> Spec Regeneration -> Verification Review -> Test -> Contract
-> Implementation Handoff -> External AI Implementation
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
Technical Design -> Initial SpecGuard Review -> READY or NOT READY
```

SpecGuard Review inspects the full spec package and generated technical design. It looks for blockers before implementation begins.

Run is a validator, not the place where product intent is invented. Use it after the spec package has enough real detail to review.
For API features, `contracts/openapi.yaml` must define at least one concrete path before SpecGuard can produce an implementation handoff; `paths: {}` is treated as a blocker, not a ready contract. Generated contracts include spec-derived success/error responses, request/response schemas, and `x-specguard-coverage` links back to acceptance criteria and error cases.

### 3. Iterate Until Ready

If SpecGuard Review returns NOT READY, use the continuation menu:

```text
[1] View Readiness Findings
[2] Regenerate spec from Readiness Findings (auto-runs SpecGuard Review after)
[q] Exit
```

The loop is:

```text
Initial SpecGuard Review -> Spec Regeneration -> Verification Review -> READY or NOT READY
```

The initial review is broad and adversarial. After spec regeneration, Verification Review checks whether previous blockers were resolved and only adds new Critical or Major findings when there is direct implementation-blocking evidence.

Repeat until SpecGuard reports READY.

LLM-enabled runs can automate this bounded loop:

```bash
python -m cli.specguard run specs/your-feature-name --strict-e2e --strict-max-iterations 3
```

Strict E2E always runs Initial SpecGuard Review first. When it receives NOT READY, it regenerates `spec.md` from the readiness findings, reruns Verification Review with those findings as the backlog, and stops only when READY or the iteration limit is exhausted. Each run writes `strict-e2e-trace.json` so regeneration attempts can be traced back to the findings that caused them.
Strict E2E also requires executable verification before handoff: add tests such as `tests/test_*.py`, or document an accepted `tests/verification-contract.md` with the command or artifact that a coding agent must preserve.

### 4. External Implementation Handoff

When the spec package is ready, SpecGuard continues through:

```text
Test -> Contract -> Implementation Handoff
```

Then use:

```text
specs/your-feature-name/implementation-output.md
develop/<stack>/
```

SpecGuard does not invoke Codex, Claude Code, or another coding agent as an internal pipeline stage. Give the approved implementation output guide to an external coding agent, and place application code under `develop/<stack>/`.
The guide includes machine-readable readiness status and the approved artifact list that the coding agent may use.

## SpecGuard Readiness Gate

SpecGuard uses this readiness threshold:

- Critical: 0
- Major: 0
- Minor: 5 or fewer

Critical and Major findings block implementation. Minor findings are allowed only when they do not hide missing requirements or implementation ambiguity.

CLI output highlights READY states in green and NOT READY states in red.

Pull request CI includes a stable required-check candidate named `SpecGuard Readiness Gate`. It inspects changed packages under `specs/`, fails when a changed package is NOT READY, and fails when source artifacts are stale relative to `readiness-review.json` or changed without an updated readiness report. Repositories that want merge-time enforcement should add `SpecGuard Readiness Gate` to branch protection or ruleset required status checks.

## Advisory PR Review

After READY and external implementation, repositories can enable the optional `SpecGuard PR Review` workflow. It builds a compact context from approved spec artifacts plus the PR diff, asks a Codex-compatible reviewer to check spec-to-implementation alignment, and updates a single PR comment headed `SpecGuard PR Reviewer`.

The workflow is advisory by default. If `SPECGUARD_OPENAI_API_KEY` or `SPECGUARD_PR_REVIEW_COMMAND` is unavailable, it skips without exposing secrets. It does not run secret-bearing review calls on fork PRs unless maintainers explicitly provide a safe credential strategy. The comment includes the reviewed head SHA, mode, reviewed spec package paths, coverage summary, and any findings.

## CLI Reference

```bash
python -m cli.specguard init <spec-name>
python -m cli.specguard run specs/<spec-name>
```

Useful options:

- `--force`: regenerate derived artifacts such as technical design.
- `--follow-up`: force the interactive continuation menu.
- `--no-follow-up`: exit immediately after the pipeline.
- `--no-llm`: use local deterministic checks and heuristic SpecGuard Review.
- `--strict-e2e`: use an LLM to automatically regenerate blocked specs and rerun Verification Review.
- `--strict-max-iterations`: bound the number of strict E2E verification iterations.

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
Discovery -> Spec Package -> Technical Design -> SpecGuard Review
-> Test -> Contract -> Implementation Handoff
```

Before opening a pull request:

- keep generated application code outside `specs/`
- resolve or intentionally document Critical and Major Readiness Findings
- include or update tests
- run `pytest`

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache License 2.0
