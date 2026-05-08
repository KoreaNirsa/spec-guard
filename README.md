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

SpecGuard has two review checkpoints:

- `SpecGuard Review` runs before implementation. Default low mode uses a fast heuristic review, blocks Critical findings, and reports Major or Minor findings as warnings.
- `SpecGuard PR Review` runs after implementation. It compares the approved spec package and implementation handoff against a pull request diff, then posts an advisory review comment.

For review levels, LLM detail review, cache behavior, and experimental Spec Revision, see [Core Reviews](docs/core-reviews.md).

## Current Support Status

Currently, local Codex mode is the recommended and release-tested path for live SpecGuard Review. OpenAI Platform mode is implemented for the Responses API, including PR Review execution, but the clean end-to-end release test has not been completed yet. Treat OpenAI Platform mode as experimental until published-install validation is finished.

## Setup To User Flow

This is the shortest path from installation to a reviewed implementation PR:

```bash
pip install spec-guard
specguard init your-feature-name
specguard run specs/your-feature-name
```

Write or replace the draft spec under `specs/your-feature-name/`, rerun until SpecGuard reports READY or READY_WITH_WARNINGS, then give `implementation-output.md` to an external coding agent for implementation. After implementation, open a PR and optionally run SpecGuard PR Review.

For Codex setup, example packages, LLM review options, follow-up menus, implementation handoff, and PR review setup, see [Setup To User Flow](docs/setup-to-user-flow.md).

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

## Documentation

- [Setup To User Flow](docs/setup-to-user-flow.md): installation, Codex setup, example packages, validation loops, implementation handoff, and PR review setup.
- [Core Reviews](docs/core-reviews.md): SpecGuard Review, SpecGuard PR Review, LLM detail review, cache behavior, and experimental Spec Revision.
- [Readiness Rules](docs/readiness-rules.md): review levels, READY thresholds, contract requirements, and Strict E2E verification rules.
- [CI And PR Gates](docs/ci-and-pr-gates.md): readiness gate installation, required-check guidance, and PR review separation.
- [CLI Reference](docs/cli-reference.md): common commands, `run` options, and CI-friendly examples.
- [Development](docs/development.md): local source setup, tests, and packaged-example smoke testing.
- [Workflow Guide](docs/workflow.md)
- [Discovery Guide](docs/deep-discovery.md)
- [Spec-Driven Benchmark](docs/spec-driven-benchmark.md)
- [Contributing](CONTRIBUTING.md)

## License

Apache License 2.0
