# Readiness Coverage Audit

This audit records the English and Korean readiness fixture coverage after the
v0.4.3 benchmark refresh. It is derived from checked-in benchmark fixture source
and the recorded v0.4.3 gate-only benchmark result, not manual memory.

## Regeneration

```bash
python -m tools.spec_driven_ai_benchmark --coverage-matrix --coverage-matrix-results docs/benchmark-results/specguard-gate-only-v0.4.3.json --include-gate-only-extra-cases --include-korean-cases --output docs/benchmark-results/readiness-coverage-matrix.json
```

| Item | Value |
| --- | --- |
| Matrix output | [`docs/benchmark-results/readiness-coverage-matrix.json`](benchmark-results/readiness-coverage-matrix.json) |
| Fixture source | `tools/spec_driven_ai_benchmark.py` `benchmark_cases` |
| Result source | [`docs/benchmark-results/specguard-gate-only-v0.4.3.json`](benchmark-results/specguard-gate-only-v0.4.3.json) |
| Total fixtures | 220 |
| English fixtures | 110 |
| Korean fixtures | 110 |
| Ready/reference fixtures | 86 |
| Weak/blocking fixtures | 134 |

## Baseline

The v0.4.3 gate-only result used for this audit reports 220 evaluated cases:

| Scope | Evaluated | Weak Blocked | Ready Blocked | False Positive Rate | False Negative Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Combined | 220 | 134/134 | 0/86 | 0.0% | 0.0% |
| English | 110 | 67/67 | 0/43 | 0.0% | 0.0% |
| Korean | 110 | 67/67 | 0/43 | 0.0% | 0.0% |

The current matrix contains 220 selected fixture-source cases. The supplied
v0.4.3 gate result covers all of them, so the matrix records
`missing_cases=0` and `is_complete=true`.

In the v0.4.3 result artifact, all 86 ready/reference rows have actual readiness
status `ready_with_warnings`, and all 134 weak rows have actual readiness status
`not_ready`.
Critical counts are present in the recorded benchmark artifact: 86 rows have 0
Critical findings, 127 rows have 1 Critical finding, and 7 rows have 2 Critical
findings.

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

The v0.4.3 deterministic benchmark JSON persists stable Critical finding
identifiers, severity, titles, and actionable evidence. The matrix reports
`evidence_present=true` for the 134 weak rows with Critical findings and
`evidence_present=false` for the 86 ready/reference rows without Critical
findings.

## Coverage Gaps

No English-only, Korean-only, ready-only, or weak-only source-case gaps are
present in the current 220-case matrix.

The #213 fixture-source expansion adds paired ready/weak English and Korean
cases for explicit Korean phrasing variants in `inbound_webhooks` and
`payments`, so it does not introduce new counterpart or ready-only gaps. The
#242 fixture-source expansion adds ready/reference guards in English and Korean
for the former weak-only `device_trust`, `ledger`, `promotions`, `rate_limits`,
`sso`, and `todo` domain/language pairs. The refreshed artifact now evaluates
those cases, and the matrix records all cases as `coverage_complete` at both the
fixture-metadata and result-coverage levels.

## Risk-Domain Notes

| Risk Area | Current Fixture Domains | Audit State |
| --- | --- | --- |
| Auth and session lifecycle | `auth_session`, `password_reset`, `oauth_consent`, `device_trust`, `sso` | Paired ready/weak coverage exists. |
| Ownership and tenant isolation | `task_service`, `todo`, `document_sharing`, `data_export`, `support` | Paired ready/weak coverage exists. |
| Idempotency and duplicate effects | `task_service`, `payments`, `webhook_delivery` | Paired ready/weak coverage exists. |
| Payment, refund, subscription, booking | `payments`, `returns`, `subscriptions`, `booking` | Paired ready/weak coverage exists. |
| Webhook, cache, and rate limit | `webhook_delivery`, `inbound_webhooks`, `cache`, `rate_limits` | Paired ready/weak coverage exists. |
| Privacy deletion, audit, and ledger | `privacy`, `audit`, `ledger` | Paired ready/weak coverage exists. |
| Inventory, notification, coupon, jobs | `inventory`, `notifications`, `promotions`, `background_jobs` | Paired ready/weak coverage exists. |

## Follow-up Use

- Use the
  [Readiness Calibration Triage Protocol](readiness-calibration-triage.md) to
  classify fixture gaps, false positives, false negatives, evidence-quality
  issues, documentation gaps, and Korean counterpart gaps before changing rules.
- Use #242 as the fixture-balance baseline for former weak-only domains before
  changing heuristics in those areas.
- Use #183 to triage any future ready/reference row blocked by SpecGuard.
- Use #184 only if a future matrix or benchmark run reports weak rows allowed by
  SpecGuard.
- Use the benchmark `critical_finding_evidence` summary and deterministic
  comparison output to keep Critical evidence machine-checkable.
- Use #241 as the refreshed 220-case benchmark baseline before publishing
  updated gate-only metrics.
