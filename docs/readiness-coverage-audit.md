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
| Total fixtures | 196 |
| English fixtures | 98 |
| Korean fixtures | 98 |
| Ready/reference fixtures | 66 |
| Weak/blocking fixtures | 130 |

## Baseline

The v0.4.0 gate-only result used for this audit reports:

| Scope | Evaluated | Weak Blocked | Ready Blocked | False Positive Rate | False Negative Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Combined | 196 | 130/130 | 0/66 | 0.0% | 0.0% |
| English | 98 | 65/65 | 0/33 | 0.0% | 0.0% |
| Korean | 98 | 65/65 | 0/33 | 0.0% | 0.0% |

The matrix emits these FP/FN baseline fields only when the supplied gate results
cover the full selected fixture set. This audit uses complete 196/196 coverage.

All 66 ready/reference rows have actual readiness status `ready_with_warnings`.
All 130 weak rows have actual readiness status `not_ready`. Critical counts are
present in the recorded benchmark artifact: 66 rows have 0 Critical findings,
123 rows have 1 Critical finding, and 7 rows have 2 Critical findings.

The historical v0.4.0 JSON does not persist full finding evidence payloads, so
the matrix keeps `evidence_present` as `null` for every row. Detailed Critical
evidence shape is tracked separately in #185.

## Coverage Gaps

No English-only or Korean-only source-case gaps are present in the current
196-case matrix. No ready-only domain/language gaps are present.

The remaining coverage imbalance is weak-only domain/language coverage. These
domains have weak/blocking fixtures in both English and Korean, but no paired
ready/reference fixture yet:

| Domain | English Weak Cases | Korean Weak Cases | Follow-up |
| --- | ---: | ---: | --- |
| `audit` | 1 | 1 | #182 |
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
| Privacy deletion, audit, and ledger | `privacy`, `audit`, `ledger` | Covered, but `audit` and `ledger` are weak-only. |
| Inventory, notification, coupon, jobs | `inventory`, `notifications`, `promotions`, `background_jobs` | Covered, but `promotions` and `background_jobs` are weak-only. |

## Follow-up Use

- Use #182 to add paired ready/reference fixtures for weak-only domains before
  changing heuristics in those areas.
- Use #183 only if a future matrix or benchmark run reports ready/reference rows
  blocked by SpecGuard.
- Use #184 only if a future matrix or benchmark run reports weak rows allowed by
  SpecGuard.
- Use #185 to make detailed Critical evidence presence machine-checkable.
- Use #186 to refresh benchmark metrics after fixture or heuristic changes land.
