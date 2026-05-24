# Readiness Coverage Audit

This audit records the English and Korean readiness fixture coverage before new
heuristic tuning work. It is derived from checked-in benchmark fixture source and
the recorded v0.4.0 gate-only benchmark result, not manual memory.

## Regeneration

```bash
python tools/spec_driven_ai_benchmark.py --coverage-matrix --coverage-matrix-results docs/benchmark-results/specguard-gate-only-v0.4.0.json --include-gate-only-extra-cases --include-korean-cases --output docs/benchmark-results/readiness-coverage-matrix.json
```

| Item | Value |
| --- | --- |
| Matrix output | [`docs/benchmark-results/readiness-coverage-matrix.json`](benchmark-results/readiness-coverage-matrix.json) |
| Fixture source | `tools/spec_driven_ai_benchmark.py` `benchmark_cases` |
| Result source | [`docs/benchmark-results/specguard-gate-only-v0.4.0.json`](benchmark-results/specguard-gate-only-v0.4.0.json) |
| Total fixtures | 198 |
| English fixtures | 99 |
| Korean fixtures | 99 |
| Ready/reference fixtures | 68 |
| Weak/blocking fixtures | 130 |

## Baseline

The v0.4.0 gate-only result used for this audit reports:

| Scope | Evaluated | Weak Blocked | Ready Blocked | False Positive Rate | False Negative Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Combined | 196 | 130/130 | 0/66 | 0.0% | 0.0% |
| English | 98 | 65/65 | 0/33 | 0.0% | 0.0% |
| Korean | 98 | 65/65 | 0/33 | 0.0% | 0.0% |

The matrix emits these FP/FN baseline fields only when the supplied gate results
cover the full selected fixture set. The original #181 audit used complete
196/196 coverage. After the #182 audit-domain fixture pair, the checked-in
matrix has 198 fixtures while the v0.4.0 result artifact still covers 196
cases, so the matrix baseline fields stay `null` until #186 refreshes the
benchmark artifact.

In the v0.4.0 result artifact, all 66 evaluated ready/reference rows have
actual readiness status `ready_with_warnings`. All 130 weak rows have actual
readiness status `not_ready`. Critical counts are present in the recorded
benchmark artifact: 66 rows have 0 Critical findings, 123 rows have 1 Critical
finding, and 7 rows have 2 Critical findings.

The matrix also records domain/language summary fields so future fixture and
heuristic work can triage gaps without scanning every case row:

- `ready_case_count` and `weak_case_count` show fixture balance for each
  domain/language pair.
- `actual_readiness_status_counts` shows whether the recorded gate result
  produced `ready_with_warnings` or `not_ready` for that domain/language pair.
- `critical_case_count` shows how many cases in that domain/language pair
  produced at least one Critical finding.
- `evidence_present_counts` shows whether detailed Critical evidence was
  present, absent, or unknown in the available benchmark artifact.
- `source_counterpart_gap_count` shows missing English/Korean source-case
  counterparts.

The historical v0.4.0 JSON does not persist full finding evidence payloads, so
the matrix keeps `evidence_present` as `null` for every row. Detailed Critical
evidence shape is tracked separately in #185. The domain/language summaries
therefore report those evidence counts as `unknown` for this baseline.

## Coverage Gaps

No English-only or Korean-only source-case gaps are present in the current
198-case matrix. No ready-only domain/language gaps are present.

The remaining coverage imbalance is weak-only domain/language coverage. These
domains have weak/blocking fixtures in both English and Korean, but no paired
ready/reference fixture yet:

| Domain | English Weak Cases | Korean Weak Cases | Follow-up |
| --- | ---: | ---: | --- |
| `background_jobs` | 1 | 1 | #182 |
| `device_trust` | 1 | 1 | #182 |
| `ledger` | 1 | 1 | #182 |
| `promotions` | 1 | 1 | #182 |
| `rate_limits` | 1 | 1 | #182 |
| `sso` | 1 | 1 | #182 |
| `todo` | 2 | 2 | #182 |

Before adding new heuristic rules for these domains, add paired ready/reference
fixtures so false-positive protection exists in both English and Korean.

## Risk-Domain Notes

| Risk Area | Current Fixture Domains | Audit State |
| --- | --- | --- |
| Auth and session lifecycle | `auth_session`, `password_reset`, `oauth_consent`, `device_trust`, `sso` | Covered, but `device_trust` and `sso` are weak-only. |
| Ownership and tenant isolation | `task_service`, `todo`, `document_sharing`, `data_export`, `support` | Covered, but `todo` is weak-only. |
| Idempotency and duplicate effects | `task_service`, `payments`, `webhook_delivery` | Paired ready/weak coverage exists. |
| Payment, refund, subscription, booking | `payments`, `returns`, `subscriptions`, `booking` | Paired ready/weak coverage exists. |
| Webhook, cache, and rate limit | `webhook_delivery`, `inbound_webhooks`, `cache`, `rate_limits` | Covered, but `rate_limits` is weak-only. |
| Privacy deletion, audit, and ledger | `privacy`, `audit`, `ledger` | Covered, but `ledger` is weak-only. |
| Inventory, notification, coupon, jobs | `inventory`, `notifications`, `promotions`, `background_jobs` | Covered, but `promotions` and `background_jobs` are weak-only. |

## Follow-up Use

- Use the
  [Readiness Calibration Triage Protocol](readiness-calibration-triage.md) to
  classify fixture gaps, false positives, false negatives, evidence-quality
  issues, documentation gaps, and Korean counterpart gaps before changing rules.
- Use #182 to add paired ready/reference fixtures for weak-only domains before
  changing heuristics in those areas.
- Use #183 only if a future matrix or benchmark run reports ready/reference rows
  blocked by SpecGuard.
- Use #184 only if a future matrix or benchmark run reports weak rows allowed by
  SpecGuard.
- Use #185 to make detailed Critical evidence presence machine-checkable.
- Use #186 to refresh benchmark metrics after fixture or heuristic changes land.
