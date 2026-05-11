![SpecGuard banner](assets/spec_guard_banner.png)

# SpecGuard

**SpecGuard blocks weak specs before AI coding agents turn them into defective code.**

SpecGuard is a Validation-First Workflow (VFW) for AI-assisted development.
It turns specs into reviewed, testable, implementation-ready packages before AI coding begins.

It is not a prompt-to-code generator. SpecGuard helps you prepare an approved spec package before an external Codex, Claude Code, or another coding agent writes application code.

## Demo Video

![SpecGuard demo walkthrough](assets/specguard-demo-v0.3.0.gif)

[Watch the full-resolution MP4 demo](assets/specguard-demo-v0.3.0.mp4)

The demo follows this flow:

1. Install SpecGuard with `pip install spec-guard`.
2. Copy the example spec with `specguard example copy your-feature-name --force`.
3. Insert a vulnerable spec. In v0.3.0, the packaged example intentionally includes a vulnerable spec by default so users can see a blocking SpecGuard Review.
4. Review the SpecGuard findings.
5. Fix the weak areas directly, or ask an AI assistant to strengthen the spec by giving it the SpecGuard Review findings.
6. Run SpecGuard Review again and confirm it reaches READY or READY_WITH_WARNINGS before implementation handoff.

Step 2 is for testing the example package. In real development, write your own product spec under `specs/<your-feature-name>/` instead of relying on the example package.

After your real spec passes, give `implementation-output.md` to your AI coding agent to start spec-based implementation.

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
specguard auth setup --mode codex --model gpt-5.4
specguard init your-feature-name

# Optional: test with the packaged example spec before writing your own.
specguard example copy your-feature-name --force

specguard run specs/your-feature-name
```

Write or replace the draft spec under `specs/your-feature-name/`. If you want to test with the packaged sample first, copy the example spec with `specguard example copy your-feature-name --force`, then run SpecGuard.

SpecGuard guards spec validation. When the spec is safe enough, `specguard run` exits with PASS and reports READY or READY_WITH_WARNINGS. At that point, give `implementation-output.md` to an external AI coding agent to start spec-based implementation.

After implementation, SpecGuard PR Review can compare GitHub PR code against the approved spec requirements and leave a comment when the PR appears to drift from the spec. To install it, run:

```bash
specguard actions install-pr-review
```

Then configure the GitHub Actions secret and repository variable:

```text
SPECGUARD_OPENAI_API_KEY=sk-...
SPECGUARD_PR_REVIEW_MODEL=gpt-5.4-mini
```

For Codex setup, example packages, LLM review options, follow-up menus, implementation handoff, and PR review setup, see [Setup To User Flow](docs/setup-to-user-flow.md).

## Benchmark Summary

A controlled benchmark used Codex `gpt-5.5` and SpecGuard's local `--no-llm` gate to measure defect exposure before and after the SpecGuard handoff. The v0.3.1 refresh uses an 18-case task-service impact suite plus a 50-case supplemental gate-only suite across auth, billing, document sharing, webhooks, payments, inventory, support, admin roles, data export, search, upload, orders, workspace invites, notifications, and profile updates.

The primary question is now: how much does SpecGuard reduce exposed implementation defects from weak specs?

| Metric | Result |
| --- | ---: |
| Raw weak-spec average contract defect rate from #136 | 25.0% |
| Raw weak specs with contract defects from #136 | 11/12 |
| Post-#138 weak specs blocked in original 18-case gate | 11/12 |
| Post-#138 prevented exposure rate against #136 raw defects | 90.9% |
| Prevented exposure improvement vs #136 | +63.6 points |
| Post-#138 false positive rate on original ready specs | 0.0% |
| Post-#138 false negative rate on original weak specs | 8.3% |
| Supplemental 50-case weak block rate | 97.1% |
| Supplemental 50-case false positive rate | 40.0% |
| Supplemental 50-case false negative rate | 2.9% |

### Weak-Spec Before And After

Before the #129 heuristic calibration, raw AI implementation from weak specs exposed contract defects in 11 of 12 weak cases, and the local gate blocked 3 weak specs. After #129 and #138, the same 18-case gate-only rerun blocks 11 of 12 weak specs, prevents 10 of the 11 raw defective weak-spec exposures, and still produces no false positives on the 6 ready specs.

The broader supplemental suite is deliberately harder and more varied. It now blocks 34 of 35 weak cases after #138, while also blocking 6 of 15 ready-reference cases. That means the next benchmark-facing calibration should focus on reducing false positives in safe non-task contracts without reopening the blocked weak-spec paths.

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
