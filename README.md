![SpecGuard banner](assets/spec_guard_banner.png)

# SpecGuard

**SpecGuard blocks weak specs before AI coding agents turn them into defective code.**

SpecGuard is a Validation-First Workflow (VFW) for AI-assisted development.
It turns specs into reviewed, testable, implementation-ready packages before AI coding begins.

It is not a prompt-to-code generator. SpecGuard helps you prepare an approved spec package before an external Codex, Claude Code, or another coding agent writes application code.

## Workflow At A Glance

```text
Discovery -> Spec Package -> Technical Design -> SpecGuard Review
-> Test -> Contract -> Implementation Handoff
-> External AI Implementation -> Pull Request -> SpecGuard PR Review
```

SpecGuard owns the validation path through Implementation Handoff. The user or an external coding agent owns implementation after the handoff, then SpecGuard PR Review can compare the pull request back to the approved spec package.

## Core Reviews

SpecGuard centers on two review steps:

### SpecGuard Review

SpecGuard Review runs before code generation. It checks whether the spec package has important gaps in product behavior, contracts, data ownership, authorization, state transitions, error cases, or executable verification before an implementation agent starts coding.

Current default behavior:

- `low` is the default review level. It blocks Critical findings only; Major and Minor findings remain visible as warnings.
- `READY` means SpecGuard generated Test, Contract, and Implementation Handoff artifacts. Start external implementation from `implementation-output.md`.
- `READY_WITH_WARNINGS` means implementation can proceed, but warning findings are available in `readiness-review.md` if the user wants to strengthen the spec first.
- `NOT READY` means implementation is blocked. Review the findings, edit `spec.md` intentionally, and rerun `specguard run`.
- Default low-mode `specguard run` uses fast heuristic SpecGuard Review first. Run `specguard run <path> --llm` or choose `SpecGuard Review (Detail)` from the forced follow-up menu when you want live LLM review.
- Live LLM review checks the SpecGuard Review cache before waiting on a provider. Cache hit/miss status and concise miss reasons are printed and written to `readiness-review.json`.
- Default `specguard run` does not rewrite `spec.md`. Automatic Spec Revision is experimental opt-in with `--experimental-auto-revise --follow-up`.

When experimental Spec Revision is enabled, low mode focuses the revision and Verification Review backlog on Critical blockers so warning cleanup does not create a long pre-implementation loop. The CLI prints Spec Revision step messages for context assembly, provider wait, intent preservation, file writes, and Verification Review reruns.

### SpecGuard PR Review

SpecGuard PR Review runs after code is implemented. It compares the approved spec package, implementation handoff, and pull request diff, then posts an advisory PR comment when the implementation appears to drift from the spec, tests, contracts, security expectations, or operational requirements.

## Current Support Status

Currently, local Codex mode is the recommended and release-tested path for live SpecGuard Review. OpenAI Platform mode is implemented for the Responses API, including PR Review execution, but the clean end-to-end release test has not been completed yet. Treat OpenAI Platform mode as experimental until published-install validation is finished.

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

Codex mode uses a 600-second request timeout by default because `run` can ask Codex to review the full spec package. `auth status` confirms the saved configuration and local Codex command availability; the first full provider request happens during `init`, `run`, or experimental follow-up regeneration.

For a faster local review profile, configure an explicit Codex reasoning effort or a Codex profile:

```bash
specguard auth setup --mode codex --model gpt-5.4 --codex-reasoning-effort medium --skip-login
specguard auth status
```

Lower reasoning effort can reduce latency, while higher effort may improve review depth. SpecGuard keeps Codex defaults unless you opt in.

If Codex is already logged in and you do not want setup to offer `codex login`:

```bash
specguard auth setup --mode codex --model gpt-5.4 --skip-login
```


### 3. Create A Feature Spec

```bash
specguard init your-feature-name
```

SpecGuard writes draft artifacts and the default readiness workflow:

```text
specs/your-feature-name/
|-- discovery.md
|-- spec.md
|-- plan.md
|-- tasks.md
|-- constitution.md
`-- checklists/spec-readiness.md
.github/
`-- workflows/specguard-readiness-gate.yml
```

For real work, this is where the user writes the actual development spec. Strengthen `specs/your-feature-name/` with product behavior, API or UI expectations, data ownership, authorization rules, state transitions, error cases, and acceptance criteria before running validation.

`init` installs the default `SpecGuard Readiness Gate` GitHub Actions workflow so changed spec packages can be checked on pull requests. Use `--no-actions` when you do not want SpecGuard to write `.github/workflows`.

### 4. Write Specs Or Try The Example Package

After `init`, either replace the draft with your real feature spec or copy the packaged authored example into the same feature package:

```bash
specguard example copy your-feature-name --force
```

The example is for trying the full `run` pipeline before authoring your own production spec. It replaces the init draft with a complete sample package under `specs/your-feature-name/`.

### 5. Run And Iterate Until READY Or READY_WITH_WARNINGS

```bash
specguard run specs/your-feature-name
```

The default SpecGuard Review level is `low`. Low mode is a practical safety gate: Critical findings block, while Major and Minor findings are reported as warnings so users are not forced into long cleanup loops for non-critical improvements. In the default low path, SpecGuard uses fast heuristic review first so the first run is not blocked on a live LLM provider.

`run` builds and validates the implementation basis:

```text
Technical Design -> Initial SpecGuard Review -> Test -> Contract -> Implementation Handoff
```

`run` also prints per-feature performance timings and records SpecGuard Review input size so slow stages and oversized review contexts can be diagnosed without exposing artifact contents. For live LLM review, `readiness-review.json` includes cache diagnostics such as hit/miss, miss reason, provider/model, prompt version, token budget, and non-sensitive input fingerprints.

If SpecGuard returns NOT READY, review the findings, edit the spec intentionally, and rerun `specguard run`:

```text
[1] View Readiness Findings
[2] Run SpecGuard Review (Detail) with the configured LLM
[u] I updated spec.md; rerun SpecGuard
[q] Exit
```

Repeat until SpecGuard reports READY or READY_WITH_WARNINGS. In the default low mode, Critical findings require user revision before implementation; Major and Minor findings remain visible as warnings. After an implementation-ready result, the default CLI prints a short Next Action guide instead of opening another cleanup loop.

Automatic Spec Revision is experimental and disabled by default. To opt in, run with `--experimental-auto-revise --follow-up`; SpecGuard can then generate a revised `spec.md` from blocked Readiness Findings and rerun Verification Review. Spec revision is guarded by an Intent Preservation Check. In low mode, obvious out-of-scope additions such as retry queues, bulk import, or cross-workspace invite variants are auto-demoted back out of implementation scope when they match documented non-goals. If the proposed `spec.md` appears to drop existing acceptance coverage, change the original problem intent, weaken safety-critical requirements, or still move out-of-scope work into implementation scope, SpecGuard updates the working `spec.md` for in-place review, writes the original spec and unified diff under `.specguard/spec-revisions/`, and stops before Verification Review.

For experimental LLM-enabled strict automation:

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

Install it explicitly when you want AI-assisted review comments:

```bash
specguard actions install-pr-review
```

After the command completes, commit and push the workflow file, then add this repository secret in GitHub repository settings:

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

Full methodology, case breakdown, version metadata, and limitations are available in the [Spec-Driven Benchmark](docs/spec-driven-benchmark.md).

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

SpecGuard supports three review levels:

- `low` is the default for `specguard run`. It is optimized for first-run usability and minimum safety gating. It blocks only Critical findings. Major and Minor findings are warnings.
- `medium` preserves the stricter v0.2.5-style readiness gate. Use it when you want deeper SpecGuard Review before implementation.
- `high` keeps the medium gate in this release while asking for stricter review attention. It may take longer and should be used when review depth matters more than latency.

Choose a level per run:

```bash
specguard run specs/your-feature-name --review-level medium
SPECGUARD_REVIEW_LEVEL=medium specguard run specs/your-feature-name
```

Strict E2E defaults to `medium` because it is explicitly an automated refinement loop.

Readiness states are interpreted by the selected review level:

- Low: READY when Critical=0 and no warnings exist; READY_WITH_WARNINGS when Critical=0 and Major or Minor warnings exist; NOT_READY only when Critical>=1.
- Medium: READY when Critical=0, Major=0, Minor<=5; READY_WITH_WARNINGS when Critical=0, Major<=2, Minor<=10; NOT_READY when Critical>=1, Major>=3, or Minor>10.
- High: uses the medium gate thresholds in v0.2.6 with stricter review attention.

Critical findings always block implementation. Major findings should represent an implementation-critical product, security, state, contract, persistence, or ownership decision. Best-practice suggestions, optional hardening, future extensibility, broad reliability improvements, and weakly evidenced risks should be Minor or omitted.

For API features, `contracts/openapi.yaml` must define at least one concrete path before SpecGuard can produce an implementation handoff. `paths: {}` is treated as a blocker, not a ready contract. Generated contracts include spec-derived success and error responses, request and response schemas, and `x-specguard-coverage` links back to acceptance criteria and error cases.

Strict E2E also requires executable verification before handoff. Add tests such as `tests/test_*.py`, or document an accepted `tests/verification-contract.md` with the command or artifact that a coding agent must preserve.

## CI And PR Gates

Pull request CI includes a stable required-check candidate named `SpecGuard Readiness Gate`. It inspects changed packages under `specs/`, fails when a changed package is NOT_READY, and fails when source artifacts are stale relative to `readiness-review.json`.

`specguard init <feature>` installs `.github/workflows/specguard-readiness-gate.yml` by default. Use `specguard init <feature> --no-actions` to opt out, or `specguard actions install-readiness-gate` to install the workflow later.

Repositories that want merge-time enforcement should add `SpecGuard Readiness Gate` to branch protection or ruleset required status checks.

`SpecGuard PR Review` is separate from the readiness gate. It is a post-implementation advisory review that checks whether code appears aligned with the approved spec package.

## CLI Reference

```bash
specguard init <spec-name>
specguard example copy <spec-name> --force
specguard actions install-pr-review
specguard run specs/<spec-name>
specguard auth status
```

Useful `run` options:

- `--force`: regenerate derived artifacts such as technical design.
- `--follow-up`: force the interactive continuation menu.
- `--no-follow-up`: exit immediately after the pipeline.
- `--llm`: run live LLM SpecGuard Review instead of the default fast heuristic low-mode review.
- `--no-llm`: force local deterministic checks and heuristic SpecGuard Review.
- `--review-level {low,medium,high}`: choose the SpecGuard Review depth; defaults to `low`, or `medium` for `--strict-e2e`.
- `--experimental-auto-revise`: allow the follow-up menu to rewrite blocked specs and rerun Verification Review.
- `--strict-e2e`: experimental strict automation that uses an LLM to regenerate blocked specs and rerun Verification Review.
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
