# Core Reviews

SpecGuard centers on two review steps: SpecGuard Review before implementation, and SpecGuard PR Review after implementation.

## SpecGuard Review

SpecGuard Review runs before code generation. It checks whether the spec package has important gaps in product behavior, contracts, data ownership, authorization, state transitions, error cases, or executable verification before an implementation agent starts coding.

Current default behavior:

- `low` is the default review level. It blocks Critical findings only; Major and Minor findings remain visible as warnings.
- `READY` means SpecGuard generated Test, Contract, and Implementation Handoff artifacts. Start external implementation from `implementation-output.md`.
- `READY_WITH_WARNINGS` means implementation can proceed, but warning findings are available in `readiness-review.md` if the user wants to strengthen the spec first.
- `NOT READY` means implementation is blocked. Review the findings, edit `spec.md` intentionally, and rerun `specguard run`.
- Default low-mode `specguard run` uses fast heuristic SpecGuard Review first, even when a provider is configured. Run `specguard run <path> --llm` when you want provider-backed review in the main pipeline, or choose the detailed LLM spec review action from the follow-up menu when you want an on-demand review after the fast result.
- SpecGuard Review reads authored Markdown under the feature package, including `discovery.md` and additional `.md` spec notes, while excluding generated SpecGuard artifacts.
- In low mode, the first live LLM review may compact supporting authored Markdown for speed. The follow-up detailed LLM spec review sends full authored Markdown and writes `readiness-review-detail.md/json` without rewriting `spec.md`.
- Live LLM review checks the SpecGuard Review cache before waiting on a provider. Cache hit/miss status and concise miss reasons are printed and written to the review JSON.
- Default `specguard run` does not rewrite `spec.md`. Automatic Spec Revision is experimental opt-in with `--experimental-auto-revise --follow-up`.

When experimental Spec Revision is enabled, low mode focuses the revision and Verification Review backlog on Critical blockers so warning cleanup does not create a long pre-implementation loop. The CLI prints Spec Revision step messages for context assembly, provider wait, intent preservation, file writes, and Verification Review reruns.

## SpecGuard PR Review

SpecGuard PR Review runs after code is implemented. It compares the approved spec package, implementation handoff, and pull request diff, then posts an advisory PR comment when the implementation appears to drift from the spec, tests, contracts, security expectations, or operational requirements.
