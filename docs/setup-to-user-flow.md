# Setup To User Flow

This is the shortest path from installation to a reviewed implementation PR.

## 1. Install

SpecGuard expects Python 3.11 or newer.

```bash
pip install spec-guard
specguard --help
```

## 2. Configure Codex

Configure Codex only when you want LLM-backed steps such as LLM Discovery, LLM Technical Design, `specguard run --llm`, follow-up detailed LLM SpecGuard Review, experimental Spec Revision, Strict E2E, or SpecGuard PR Review setup. The default low `specguard run` still works without a provider by using deterministic generation and fast heuristic SpecGuard Review.

To use local Codex:

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

## 3. Create A Feature Spec

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

## 4. Write Specs Or Try The Example Package

After `init`, either replace the draft with your real feature spec or copy the packaged authored example into the same feature package:

```bash
specguard example copy your-feature-name --force
```

The example is for trying the full `run` pipeline before authoring your own production spec. It replaces the init draft with a complete sample package under `specs/your-feature-name/`.

## 5. Run And Iterate Until READY Or READY_WITH_WARNINGS

```bash
specguard run specs/your-feature-name
```

The default SpecGuard Review level is `low`. Low mode is a practical safety gate: Critical findings block, while Major and Minor findings are reported as warnings so users are not forced into long cleanup loops for non-critical improvements. In the default low path, SpecGuard uses fast heuristic review first so the first run is not blocked on a live LLM provider.

`run` builds and validates the implementation basis:

```text
Technical Design -> Initial SpecGuard Review -> Test -> Contract -> Implementation Handoff
```

SpecGuard Review reads authored Markdown under the feature package: `discovery.md`, `spec.md`, `plan.md`, `tasks.md`, `constitution.md`, checklists, `technical-design.md`, and any additional user-authored `.md` spec notes. It excludes generated SpecGuard artifacts such as readiness reports, implementation handoff output, generated tests, generated contracts, and `.specguard/` cache or audit files.

`run` also prints per-feature performance timings and records SpecGuard Review input size so slow stages and oversized review contexts can be diagnosed without exposing artifact contents. For live LLM review, review JSON includes cache diagnostics such as hit/miss, miss reason, provider/model, prompt version, token budget, and non-sensitive input fingerprints.

If SpecGuard returns NOT READY, review the findings, edit the spec intentionally, and rerun `specguard run`:

```text
[1] View Readiness Findings
[2] Run the LLM for a detailed spec review. This can take a few minutes.
[u] I updated spec.md; rerun SpecGuard
[q] Exit
```

Repeat until SpecGuard reports READY or READY_WITH_WARNINGS. In the default low mode, Critical findings require user revision before implementation; Major and Minor findings remain visible as warnings. The follow-up detailed LLM review is review-only: it writes `readiness-review-detail.md/json` and does not rewrite `spec.md`. After an implementation-ready result, the default CLI prints a short Next Action guide instead of opening another cleanup loop.

Automatic Spec Revision is experimental and disabled by default. To opt in, run with `--experimental-auto-revise --follow-up`; SpecGuard can then generate a revised `spec.md` from blocked Readiness Findings and rerun Verification Review. Spec revision is guarded by an Intent Preservation Check. In low mode, obvious out-of-scope additions such as retry queues, bulk import, or cross-workspace invite variants are auto-demoted back out of implementation scope when they match documented non-goals. If the proposed `spec.md` appears to drop existing acceptance coverage, change the original problem intent, weaken safety-critical requirements, or still move out-of-scope work into implementation scope, SpecGuard updates the working `spec.md` for in-place review, writes the original spec and unified diff under `.specguard/spec-revisions/`, and stops before Verification Review.

For experimental LLM-enabled strict automation:

```bash
specguard run specs/your-feature-name --strict-e2e --strict-max-iterations 3
```

Strict E2E runs Initial SpecGuard Review first, regenerates `spec.md` from blockers, runs the same Intent Preservation Check, reruns Verification Review, and stops only when READY or when the iteration limit is exhausted. It writes `strict-e2e-trace.json` for traceability.

## 6. Implement With An External AI Coding Agent

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

`implementation-output.md` lists the Agent Input Artifacts. It includes every authored Markdown spec artifact reviewed by SpecGuard, including `discovery.md` and additional `.md` notes, then adds generated tests and contracts as implementation and verification inputs. It excludes SpecGuard review reports, cache files, revision audit files, and other generated validation outputs.

Artifact priority in the handoff:

- Primary implementation basis: `spec.md`, `technical-design.md`, `tests/`, and `contracts/`.
- Intent context: `discovery.md`, `plan.md`, `tasks.md`, `constitution.md`, `checklists/`, and additional authored Markdown notes.
- If artifacts conflict or required behavior is missing, stop implementation, update the spec package, and rerun SpecGuard.

## 7. Open A Pull Request And Run SpecGuard PR Review

After implementation, open a PR in your GitHub repository with the completed code.

The optional `SpecGuard PR Review` workflow compares the approved spec package to the PR diff and posts one advisory PR comment headed `SpecGuard PR Reviewer`.

A live SpecGuard PR Review example is available in [PR #32](https://github.com/KoreaNirsa/spec-guard/pull/32).

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
SPECGUARD_PR_REVIEW_MODEL=gpt-5.4-mini
SPECGUARD_REVIEW_SPEC_PATHS=specs/your-feature-name
```

`SPECGUARD_OPENAI_API_KEY` must be stored as a GitHub Actions secret, not committed to the repository. Use `SPECGUARD_REVIEW_SPEC_PATHS` when an implementation PR changes only `develop/<stack>/` files and does not modify files under `specs/`.

The workflow is advisory by default. If credentials are unavailable, if the selected spec package is NOT READY, or if the readiness report is stale, the workflow skips or reports the blocker instead of invoking the reviewer.
