![SpecGuard banner](assets/spec_guard_banner.png)

# SpecGuard

SpecGuard is a Validation-First Workflow (VFW) for AI-assisted development.
It turns specs into reviewed, testable, implementation-ready packages before AI coding begins.

It is not a prompt-to-code generator. SpecGuard helps you prepare an approved spec package before an external Codex, Claude Code, or another coding agent writes application code.

```text
Discovery -> Spec Package -> Technical Design -> SpecGuard Review
-> Test -> Contract -> Implementation Handoff
-> External AI Implementation -> Pull Request -> SpecGuard PR Review
```

## Setup To User Flow

This is the shortest path from installation to a reviewed implementation PR.

### 1. Install

SpecGuard expects Python 3.11 or newer.

```bash
pip install spec-guard
specguard --help
```

### 2. Configure Codex

Then configure SpecGuard to use local Codex:

```bash
specguard auth setup --mode codex --model gpt-5.4
specguard auth status
```

Codex mode uses a 600-second request timeout by default because `run` can ask Codex to review the full spec package. `auth status` confirms the saved configuration and local Codex command availability; the first full provider request happens during `init`, `run`, or follow-up regeneration.

If Codex is already logged in and you do not want setup to offer `codex login`:

```bash
specguard auth setup --mode codex --model gpt-5.4 --skip-login
```


### 3. Create A Feature Spec

```bash
specguard init your-feature-name
```

SpecGuard writes draft artifacts under:

```text
specs/your-feature-name/
|-- discovery.md
|-- spec.md
|-- plan.md
|-- tasks.md
|-- constitution.md
`-- checklists/spec-readiness.md
```

For real work, this is where the user writes the actual development spec. Strengthen `specs/your-feature-name/` with product behavior, API or UI expectations, data ownership, authorization rules, state transitions, error cases, and acceptance criteria before running validation.

### 4. Write Specs Or Try The Example Package

After `init`, either replace the draft with your real feature spec or copy the packaged authored example into the same feature package:

```bash
specguard example copy your-feature-name --force
```

The example is for trying the full `run` pipeline before authoring your own production spec. It replaces the init draft with a complete sample package under `specs/your-feature-name/`.

### 5. Run And Iterate Until READY

```bash
specguard run specs/your-feature-name
```

`run` builds and validates the implementation basis:

```text
Technical Design -> Initial SpecGuard Review -> Test -> Contract -> Implementation Handoff
```

If SpecGuard returns NOT READY, use the continuation menu:

```text
[1] View Readiness Findings
[2] Regenerate spec from Readiness Findings (auto-runs SpecGuard Review after)
[q] Exit
```

Repeat until SpecGuard reports READY.

Spec regeneration is guarded by an Intent Preservation Check. If the proposed `spec.md` appears to drop existing acceptance coverage, change the original problem intent, or move out-of-scope work into implementation scope, SpecGuard keeps the original `spec.md`, writes `spec.proposed.md`, and stops before Verification Review.

For LLM-enabled strict automation:

```bash
specguard run specs/your-feature-name --strict-e2e --strict-max-iterations 3
```

Strict E2E runs Initial SpecGuard Review first, regenerates `spec.md` from blockers, runs the same Intent Preservation Check, reruns Verification Review, and stops only when READY or when the iteration limit is exhausted. It writes `strict-e2e-trace.json` for traceability.

### 6. Implement With An External AI Coding Agent

When READY, SpecGuard writes:

```text
specs/your-feature-name/implementation-output.md
```

SpecGuard stops here. It does not invoke Codex, Claude Code, or another coding agent as an internal implementation stage.

Give the approved spec package and `implementation-output.md` to your external coding agent. The generated application code should live under `develop/<stack>/`, for example:

```text
develop/spring/
develop/react/
develop/fastapi/
```

### 7. Open A Pull Request And Run SpecGuard PR Review

After implementation, open a PR in your GitHub repository with the completed code.

The optional `SpecGuard PR Review` workflow compares the approved spec package to the PR diff and posts one advisory PR comment headed `SpecGuard PR Reviewer`.

To enable the default GitHub Actions path, add this repository secret in GitHub repository settings:

```text
SPECGUARD_OPENAI_API_KEY=sk-...
```

Add optional repository variables when you want to choose the review model or force the reviewer to use a specific spec package:

```text
SPECGUARD_PR_REVIEW_MODEL=gpt-5.4-nano
SPECGUARD_REVIEW_SPEC_PATHS=specs/your-feature-name
```

`SPECGUARD_OPENAI_API_KEY` must be stored as a GitHub Actions secret, not committed to the repository. Use `SPECGUARD_REVIEW_SPEC_PATHS` when an implementation PR changes only `develop/<stack>/` files and does not modify files under `specs/`.

The workflow is advisory by default. If credentials are unavailable, if the selected spec package is NOT READY, or if the readiness report is stale, the workflow skips or reports the blocker instead of invoking the reviewer.

## Benchmark Summary

A controlled benchmark used Codex `gpt-5.5` for code generation and SpecGuard's local no-LLM gate for weak-spec blocking.

With a complete and explicit spec, all workflows generated code that passed the hidden contract checks. With defective or incomplete specs, Spec Kit and OpenSpec still generated runnable Codex code, but every generated implementation exposed contract defects. SpecGuard blocked the same defective inputs before implementation using local deterministic and heuristic validation.

| Workflow | Generated code from defective specs | Average exposed contract defect rate | Blocked before implementation |
| --- | ---: | ---: | ---: |
| Spec Kit | 6 | 77.2% | 0/6 |
| OpenSpec | 6 | 63.6% | 0/6 |
| SpecGuard | 0 | 0% exposed | 6/6 |

### Weak-Spec Before And After

Before SpecGuard, the benchmark passed the same six defective or incomplete specs into Spec Kit and OpenSpec prompts. Both workflows still produced runnable Codex `gpt-5.5` implementations, and every weak-spec case exposed hidden contract defects.

After SpecGuard, the same weak specs were checked by the local no-LLM gate before implementation. SpecGuard marked all six packages NOT READY, produced no implementation handoff, and blocked the bad inputs before an AI coding agent could turn them into code.

Full methodology, case breakdown, and limitations are available in the [Spec-Driven Benchmark](docs/spec-driven-benchmark.md).

## Core Value

AI coding works best when the implementation input is explicit. SpecGuard focuses on the parts that often fail before code is written:

- unclear requirements
- hidden assumptions
- missing authorization or ownership rules
- weak acceptance criteria
- undefined errors, retries, timeouts, and state transitions
- contracts that do not match the intended behavior

The user owns the spec. SpecGuard drafts, challenges, and validates the implementation basis around it.

## Readiness Rules

SpecGuard uses this readiness threshold:

- Critical: 0
- Major: 0
- Minor: 5 or fewer

Critical and Major findings block implementation. Minor findings are allowed only when they do not hide missing requirements or implementation ambiguity.

For API features, `contracts/openapi.yaml` must define at least one concrete path before SpecGuard can produce an implementation handoff. `paths: {}` is treated as a blocker, not a ready contract. Generated contracts include spec-derived success and error responses, request and response schemas, and `x-specguard-coverage` links back to acceptance criteria and error cases.

Strict E2E also requires executable verification before handoff. Add tests such as `tests/test_*.py`, or document an accepted `tests/verification-contract.md` with the command or artifact that a coding agent must preserve.

## CI And PR Gates

Pull request CI includes a stable required-check candidate named `SpecGuard Readiness Gate`. It inspects changed packages under `specs/`, fails when a changed package is NOT READY, and fails when source artifacts are stale relative to `readiness-review.json`.

Repositories that want merge-time enforcement should add `SpecGuard Readiness Gate` to branch protection or ruleset required status checks.

`SpecGuard PR Review` is separate from the readiness gate. It is a post-implementation advisory review that checks whether code appears aligned with the approved spec package.

## CLI Reference

```bash
specguard init <spec-name>
specguard example copy <spec-name> --force
specguard run specs/<spec-name>
specguard auth status
```

Useful `run` options:

- `--force`: regenerate derived artifacts such as technical design.
- `--follow-up`: force the interactive continuation menu.
- `--no-follow-up`: exit immediately after the pipeline.
- `--no-llm`: use local deterministic checks and heuristic SpecGuard Review.
- `--strict-e2e`: use an LLM to automatically regenerate blocked specs and rerun Verification Review.
- `--strict-max-iterations`: bound the number of strict E2E verification iterations.

CI or scripted example:

```bash
specguard init billing-export --non-interactive --no-llm
specguard example copy billing-export --force
specguard run specs/billing-export --no-llm --no-follow-up
```

## Development

For contributors or local source testing:

```bash
git clone https://github.com/KoreaNirsa/spec-guard.git
cd spec-guard
python -m pip install -e ".[test]"
```

Run tests:

```bash
python -m pytest
```

Use the packaged example when you want to exercise SpecGuard without authoring a new spec first:

```bash
specguard init sample-run --non-interactive --no-llm
specguard example copy sample-run --force
specguard run specs/sample-run --no-llm --no-follow-up
```

## Documentation

- [Workflow Guide](docs/workflow.md)
- [Discovery Guide](docs/deep-discovery.md)
- [Spec-Driven Benchmark](docs/spec-driven-benchmark.md)
- [Contributing](CONTRIBUTING.md)

## License

Apache License 2.0
