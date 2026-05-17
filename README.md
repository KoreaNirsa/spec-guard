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

## Language Support

SpecGuard documentation supports Korean by default and also supports English for open-source users, contributors, and cross-language review.

한국어 문서는 기본 지원 대상이며, 영어 문서도 함께 지원합니다.

The current Korean benchmark claim is limited to deterministic low-mode coverage for explicit unsafe Korean wording, not full Korean production support.

For the documentation language policy, required doc status, and Korean benchmark claim boundaries, see [Language Support](docs/language-support.md).

## Codex App Plugin

SpecGuard includes a local Codex plugin scaffold under `plugins/specguard/`. The plugin does not replace the CLI; it helps Codex run the existing `specguard` command, read structured review artifacts, and summarize the next action.

To try it in the Codex app, add the local plugin directory from this repository checkout and make sure `specguard --help` works in the target workspace. The default plugin path remains the heuristic CLI gate: `specguard run <package> --no-llm --no-follow-up`.

For setup details, validation scenarios, and plugin boundaries, see [Codex Plugin Guide](docs/codex-plugin.md).

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
SPECGUARD_PR_REVIEW_MODEL=gpt-5.4-nano
```

For Codex setup, example packages, LLM review options, follow-up menus, implementation handoff, and PR review setup, see [Setup To User Flow](docs/setup-to-user-flow.md).

## Benchmark Summary

The calibrated gate-only benchmark evaluates 98 English spec packages across practical domains such as auth, billing, document sharing, webhooks, payments, inventory, support, admin roles, privacy, API keys, SSO, cache, returns, ledger, promotions, and background jobs. The v0.3.2 benchmark path adds 98 corresponding Korean gate-only cases and reports English and Korean metrics separately.

The benchmark asks one practical question: how much of the implementation handoff can SpecGuard guard before an AI coding agent starts writing code?

| Gate-Only Guard Signal | English 98 | Korean 98 |
| --- | ---: | ---: |
| Weak specs blocked before implementation | 63/65 | 65/65 |
| Weak-spec block rate | 96.9% | 100.0% |
| Ready specs incorrectly blocked | 0/33 | 0/33 |
| False positive rate | 0.0% | 0.0% |
| Weak specs missed | 2/65 | 0/65 |
| False negative rate | 3.1% | 0.0% |

In the original #136 code-generation baseline, raw weak specs exposed contract defects in 11 of 12 cases. With the calibrated local gate, SpecGuard now blocks 10 of those 11 observed exposure paths before implementation handoff, increasing prevented exposure from 27.3% to 90.9%.

This means SpecGuard is acting as a strong pre-implementation guard layer: it stops most unsafe or underspecified inputs before code generation, while leaving all ready-reference specs implementation-allowed in the current English and Korean gate-only runs.

The remaining known English gate-only misses are `fault_title_no_trim` and `weak_document_share_client_enforced`. Korean support is currently a deterministic low-mode claim for explicit unsafe wording, not a full Korean production-support claim. Full methodology, suite breakdown, case-level results, version metadata, and limitations are available in the [Spec-Driven Benchmark](docs/spec-driven-benchmark.md).

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
- [Language Support](docs/language-support.md): Korean default documentation support, English support, doc status, and Korean benchmark claim boundaries.
- [Codex Plugin Guide](docs/codex-plugin.md): local Codex app plugin setup, MVP workflow, validation scenarios, and plugin boundaries.
- [Plugin Result Contract](docs/plugin-result-contract.md): stable `readiness-review.json` fields and file-based states for Codex plugin consumers.
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
