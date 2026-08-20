# Frozen Readiness Holdout

The frozen readiness holdout estimates how well the provider-free deterministic
readiness gate generalizes beyond the calibrated regression fixtures. It is a
separate corpus and must not be used to tune heuristic rules in the same change
that updates its expectations.

## Corpus

The source is [`tools/resources/holdout/readiness-holdout-v1.json`](../tools/resources/holdout/readiness-holdout-v1.json).
The checked-in baseline result is
[`docs/benchmark-results/readiness-holdout-v1.json`](benchmark-results/readiness-holdout-v1.json).

The corpus contains 57 independent semantic pairs (114 cases) across eight
minimum-risk domains:

- server-side ownership scope
- payment idempotency and timeout reconciliation
- webhook signature and replay protection
- token expiry and revocation
- delete, audit, and restore policy
- tenant-scoped cache keys
- terminal state transitions
- bounded retry and backoff

Pairs use English, Korean, and realistic mixed-language product prose. A Korean
or mixed-language case is a distinct scenario; translations are not counted as
independent pairs. Each pair records the minimum unsafe mutation, provenance,
two independent `ready`/`weak` labels, and the final expected label. A label
disagreement has to include an adjudication record before execution; the corpus
contains one resolved disagreement as a schema guard.

The corpus freeze policy requires explicit review for expectation changes and
forbids using holdout failures as heuristic-tuning inputs. Unexpected results
are reported without mutating the corpus.

The calibrated suite remains separate. The holdout runner does not import or
mutate `benchmark_cases`, and its result records the calibrated suite as an
excluded source for traceability.

## Validate and run

Validate the frozen schema and labels without invoking an LLM:

```bash
python -m tools.readiness_holdout --validate
```

Run the low-mode provider-free gate and write a machine-readable report:

```bash
python -m tools.readiness_holdout \
  --run \
  --max-workers 6 \
  --output docs/benchmark-results/readiness-holdout-v1.json
```

The runner evaluates both variants of every pair, reports metamorphic pair
outcomes, and keeps the results separate from the calibrated suite. It does not
rewrite corpus labels or expectations when a result is unexpected.

## Metrics

The result reports overall, per-domain, and per-language metrics:

- weak recall: blocked weak cases / all expected weak cases
- ready specificity: allowed ready cases / all expected ready cases
- false-positive rate: blocked ready cases / all expected ready cases
- false-negative rate: allowed weak cases / all expected weak cases

Every rate includes successes, trials, the fraction, percentage, and a 95%
Wilson confidence interval. A zero-failure sample is still accompanied by the
following limitation: zero observed failures do not imply zero production risk.

## Checked-in baseline

The current deterministic baseline is intentionally recorded as evidence rather
than tuned in the same change:

| Scope | Weak recall | Ready specificity | False-positive rate | False-negative rate |
|---|---:|---:|---:|---:|
| Overall | 28.07% | 80.70% | 19.30% | 71.93% |
| English | 35.71% | 78.57% | 21.43% | 64.29% |
| Korean | 40.00% | 73.33% | 26.67% | 60.00% |
| Mixed | 17.86% | 85.71% | 14.29% | 82.14% |

Seven of 57 metamorphic pairs passed the initial baseline. The unexpected
outcomes remain visible in the JSON report by pair, with domain and language
breakdowns and confidence intervals, so follow-up heuristic work can be
reviewed separately from this frozen corpus.
