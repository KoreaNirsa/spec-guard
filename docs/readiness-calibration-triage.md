# Readiness Calibration Triage Protocol

This protocol defines how to triage readiness calibration findings before
changing deterministic heuristic rules. It keeps stabilization work reproducible,
provider-free by default, and tied to the fixture and benchmark evidence that
supports each change.

Use this protocol for false positives, false negatives, evidence-quality issues,
fixture gaps, documentation gaps, and Korean counterpart coverage gaps.

## Triage Inputs

Start from checked-in artifacts or a reproducible local fixture. Do not tune a
rule from memory or from a single unrecorded manual run.

Recommended inputs:

- The generated coverage audit in
  [`docs/readiness-coverage-audit.md`](readiness-coverage-audit.md).
- The generated coverage matrix in
  [`docs/benchmark-results/readiness-coverage-matrix.json`](benchmark-results/readiness-coverage-matrix.json).
- A benchmark fixture from `tools/spec_driven_ai_benchmark.py`.
- A realistic spec package that can be committed as a focused regression
  fixture.
- The produced `readiness-review.json` and `readiness-review.md`.

The default triage path must not require an LLM provider. LLM-backed detail
review can provide additional context, but deterministic low-mode behavior must
be reproducible without provider credentials.

## Classification

Classify each finding before changing code.

| Classification | Use When | Primary Follow-up |
| --- | --- | --- |
| False positive | A ready or READY_WITH_WARNINGS reference spec is blocked by a Critical finding even though the spec states a safe contract. | #183 |
| False negative | A weak or underspecified spec is implementation-allowed even though direct spec evidence shows an implementation-blocking gap. | #184 |
| Evidence-quality issue | A deterministic Critical finding blocks correctly, but lacks concrete excerpts, actionable impact, or a fix direction that stays within the spec. | #185 |
| Fixture gap | A domain/language lacks paired ready and weak fixtures, or lacks an English/Korean counterpart needed for safe calibration. | #182 |
| Documentation gap | Product support claims, benchmark claims, or readiness-rule docs do not match measured behavior. | #186 or #190 |
| Non-issue | The finding is expected behavior under the current review level and documented thresholds. | No rule change |

If a case fits more than one category, handle the blocking dependency first. For
example, add paired fixtures before tuning a heuristic for a weak-only
domain/language pair.

## Baseline Recording

Before a rule or fixture change, record the current behavior in the PR body or
the issue comment.

Minimum baseline:

- Case id or spec package path.
- Language and domain.
- Expected readiness outcome.
- Actual readiness status.
- Critical finding title or stable classification.
- Evidence availability: present, missing, or unknown.
- Exact command used to reproduce the result.

For benchmark fixture coverage, regenerate or inspect the matrix with:

```bash
python -m tools.spec_driven_ai_benchmark --coverage-matrix --coverage-matrix-results docs/benchmark-results/specguard-gate-only-v0.4.3.json --include-gate-only-extra-cases --include-korean-cases --output docs/benchmark-results/readiness-coverage-matrix.json
```

For a targeted fixture, prefer the existing readiness calibration tests when
available. If a new realistic package is needed, keep it narrow enough to prove
the specific classification.

## Required Guards Before Rule Changes

Do not add or broaden a deterministic Critical rule unless the PR includes guard
coverage for both sides of the behavior.

Minimum guards:

- A weak case that remains or becomes NOT_READY for the intended blocking gap.
- A ready or READY_WITH_WARNINGS case that remains implementation-allowed.
- Assertions on stable fields such as readiness status, severity,
  implementation readiness, evidence presence, and actionable fix shape.
- English and Korean coverage when the same risk exists in both languages and
  the current fixture set supports a paired counterpart.

Avoid exact generated prose snapshots unless the prose is a documented public
contract. Prefer structural assertions over wording-sensitive assertions.

## Heuristic Change Workflow

Use this sequence for false-positive, false-negative, and evidence-quality work:

1. Reproduce the current behavior with a checked-in fixture or realistic spec
   package.
2. Classify the issue using the table above.
3. Record the baseline before editing rules.
4. Add or identify paired ready/weak guards.
5. Make the smallest deterministic rule or evidence-shape change required by
   direct spec evidence.
6. Re-run the targeted tests for the changed domain.
7. Re-run paired guard tests for the same domain.
8. Decide whether the benchmark artifact or documentation needs a follow-up
   refresh.

The rule must be based on implementation risk visible in the spec. Do not block
based on generic best-practice advice, inferred product behavior, or an
unwritten policy.

## Korean Counterpart Workflow

Korean calibration must distinguish measured deterministic fixture support from
broader Korean production support.

When a Korean issue is found:

- Check whether the English source case has a Korean counterpart in the coverage
  matrix.
- Check whether the Korean fixture expresses the same implementation risk, not
  merely a translation-like title.
- Preserve common contract identifiers such as `tenant_id`, `idempotency_key`,
  `expires_at`, `revoked_at`, and `event_id` when they are part of the risk.
- Keep support claims limited to measured fixture behavior.
- Use #190 when documentation claims need to change after fixture or benchmark
  updates.

Do not broaden Korean support claims from a single fixture or from LLM-backed
review behavior.

## Domain-specific Follow-up Issues

Open a separate domain-specific issue when a finding cannot be fixed safely
inside the current PR.

Open a follow-up when:

- The domain lacks paired ready/weak fixtures.
- The issue affects multiple unrelated domains.
- The rule needs new public contract fields or report schema changes.
- The benchmark artifact needs a refresh after fixture or heuristic changes.
- Documentation support claims need updates after measured behavior changes.

The follow-up should include the baseline command, affected case ids, current
readiness result, expected readiness result, and the reason the work was split.

## Issue Flow

Use the v0.4.1 stabilization issues in this order:

| Issue | Role |
| --- | --- |
| #181 | Establish the English/Korean coverage matrix and current baseline. |
| #182 | Add paired English/Korean fixtures for missing domains. |
| #183 | Reduce documented false positives after paired guards exist. |
| #184 | Reduce documented false negatives with paired ready/reference guards. |
| #185 | Require actionable evidence shape for deterministic Critical findings. |
| #186 | Refresh benchmark artifacts and published metrics after stabilization. |
| #190 | Keep Korean support claims synchronized with benchmark coverage changes. |

Use #186 only after fixture and heuristic changes settle. Refreshing benchmark
claims before stabilization can publish stale or misleading readiness metrics.

## Minimum Validation

For documentation-only triage updates:

- Confirm links and issue references are correct.
- Run documentation-oriented tests if the touched docs have test coverage.

For fixture changes:

- Run targeted readiness calibration tests.
- Run `pytest tests/readiness/test_readiness_fixture_drift.py` when fixture counts,
  language splits, expectation splits, or source-case mappings change.
- Update `tests/fixtures/readiness-fixture-drift-summary.json` in the same PR
  only when the fixture metadata drift is intentional.
- Run benchmark metadata tests when coverage-matrix metadata or checked-in
  benchmark artifacts are touched.

For heuristic changes:

- Run targeted false-positive or false-negative regression tests.
- Run paired weak/ready tests for the same domain.
- Run plugin result contract tests if report fields or evidence shape are
  touched.
- Run the full test suite before merge.

For benchmark refreshes:

- Run the documented benchmark command.
- Record the command, fixture count, language split, output path, and known
  remaining misses or noisy cases in the PR.
