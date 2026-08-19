# SpecGuard Impact Benchmark

## Primary Question

How much does SpecGuard reduce exposed implementation defects from weak specs?

This benchmark does not treat Spec Kit, OpenSpec, and SpecGuard as directly competing layers. Spec Kit and OpenSpec help structure specification work. SpecGuard is measured here as an implementation-readiness gate that runs before an AI coding agent turns a spec package into code.

## Executive Summary

The calibrated benchmark now has six evidence layers:

- The original #136 18-case in-memory Python `TaskService` impact suite: 6 ready-reference specs and 12 weak specs. This suite includes raw Codex generation, SpecGuard gate evaluation, and SpecGuard handoff generation from the pre-#129 run.
- A v0.3.1 gate-only rerun with the same 18 cases plus 50 supplemental and 30 extended real-world-style gate cases across auth/session, billing export, document sharing, webhooks, payments, inventory, support, admin roles, audit, data export, search, file upload, orders, workspace invites, notifications, profile updates, API keys, SSO, privacy, cache, returns, ledger, promotions, and background jobs.
- A v0.3.2 Korean gate-only layer with 98 corresponding Korean cases: `impact_v2_ko`, `gate_only_supplemental_v1_ko`, and `gate_only_extended_v2_ko`. These are realistic Korean product-prose fixtures, not code-generation runs.
- A v0.4.0 gate-only calibration run for #172 with the same English/Korean 196-case matrix. This run resolves the two previously documented English false negatives while preserving zero ready-reference false positives.
- A v0.4.1 stabilization refresh for #186 with the recorded 198-case English/Korean result after #181-#185 stabilization work.
- A v0.4.3 benchmark refresh for #241 and #280 with the current 220-case English/Korean fixture set. This run blocks all 134 evaluated weak cases, records no ready-reference false positives, persists Critical evidence, and reports English and Korean metrics separately.

The original #136 full generation run found that raw AI implementation from weak specs exposed contract defects in 11 of 12 weak cases. Before #129, SpecGuard blocked 3 of those weak specs. In the calibrated v0.4.3 local `--no-llm` gate, the same original suite blocks 12 of 12 weak specs.

| Metric | #136 Baseline | v0.4.3 Gate-Only | Change |
| --- | ---: | ---: | ---: |
| Weak specs blocked before code generation | 3/12 | 12/12 | +9 cases |
| Weak-spec block rate | 25.0% | 100.0% | +75.0 points |
| Prevented exposure rate against #136 raw defects | 27.3% | 100.0% | +72.7 points |
| False positive rate on original ready specs | 0.0% | 0.0% | 0.0 points |
| False negative rate on original weak specs | 75.0% | 0.0% | -75.0 points |

The original impact suite now has no false negatives in the local gate.

The supplemental and extended gate-only suites are intentionally broader than the original task-service benchmark. They are not used to claim post-gate code defect rates because no Codex generation was run for these cases. They measure only local readiness gate behavior.

| Supplemental Gate Metric | Result |
| --- | ---: |
| Evaluated supplemental cases | 51 |
| Ready-reference supplemental cases | 16 |
| Weak supplemental cases | 35 |
| Weak supplemental cases blocked | 35/35 |
| Supplemental weak block rate | 100.0% |
| Supplemental false positive rate | 0.0% |
| Supplemental false negative rate | 0.0% |

| Extended Gate Metric | Result |
| --- | ---: |
| Evaluated extended cases | 41 |
| Ready-reference extended cases | 21 |
| Weak extended cases | 20 |
| Weak extended cases blocked | 20/20 |
| Extended weak block rate | 100.0% |
| Extended false positive rate | 0.0% |
| Extended false negative rate | 0.0% |

The reproduced 69-case run confirms the improved local gate is strong on the deterministic patterns added through #172 and #182: it blocks 47 of 47 weak cases with no ready-reference false positives. The refreshed extended calibration blocks all 20 weak practical-domain cases with no ready-reference false positives across the 21 extended ready-reference cases.

The recorded v0.4.3 English/Korean layer reports language metrics separately. In this run, both the English and Korean 110-case layers block 67/67 weak specs, and neither language layer records a ready-reference false positive.

## Benchmark Metadata

| Item | Value |
| --- | --- |
| Original full impact JSON | [`docs/benchmark-results/specguard-impact-v0.3.0.json`](benchmark-results/specguard-impact-v0.3.0.json) |
| v0.3.1 gate-only JSON | [`docs/benchmark-results/specguard-gate-only-v0.3.1.json`](benchmark-results/specguard-gate-only-v0.3.1.json) |
| v0.3.2 English/Korean gate-only JSON | [`docs/benchmark-results/specguard-gate-only-v0.3.2.json`](benchmark-results/specguard-gate-only-v0.3.2.json) |
| v0.4.0 #172 calibration JSON | [`docs/benchmark-results/specguard-gate-only-v0.4.0.json`](benchmark-results/specguard-gate-only-v0.4.0.json) |
| v0.4.1 #186 stabilization JSON | [`docs/benchmark-results/specguard-gate-only-v0.4.1.json`](benchmark-results/specguard-gate-only-v0.4.1.json) |
| v0.4.3 #241 refresh JSON | [`docs/benchmark-results/specguard-gate-only-v0.4.3.json`](benchmark-results/specguard-gate-only-v0.4.3.json) |
| Result schema | `specguard-impact-benchmark/v2` |
| Benchmark script | `tools/spec_driven_ai_benchmark.py` version `8` |
| Original full run timestamp | `2026-05-09T13:02:31Z` to `2026-05-09T13:13:42Z` |
| v0.3.1 gate-only timestamp | `2026-05-11T14:18:22.699591+00:00` to `2026-05-11T14:18:28.946457+00:00` |
| v0.3.2 English/Korean gate-only timestamp | `2026-05-15T09:07:50.369407+00:00` to `2026-05-15T09:07:57.964756+00:00` |
| v0.4.0 #172 calibration timestamp | `2026-05-19T07:21:02.678393+00:00` to `2026-05-19T07:21:10.262730+00:00` |
| v0.4.1 #186 stabilization timestamp | `2026-05-24T07:53:47.799456+00:00` to `2026-05-24T07:54:00.966492+00:00` |
| v0.4.3 #241 refresh timestamp | `2026-07-08T00:51:14.068533+00:00` to `2026-07-08T00:51:24.032371+00:00` |
| Original full run package version | `0.3.0` |
| v0.3.1 gate-only package version | `0.3.0` |
| v0.3.2 English/Korean gate-only package version | `0.3.1` |
| v0.4.0 #172 calibration package version | `0.4.0` |
| v0.4.1 #186 stabilization package version | `0.4.0` |
| v0.4.3 #241 refresh package version | `0.4.2` |
| Original full run commit | `13218f58b9f1354b8fc059490c26f4a2a0b43c6a` |
| v0.3.1 gate-only commit | `d06824784f023993094d239346a8c52d81af1396` |
| v0.3.2 English/Korean gate-only commit | `f97f5f32faf894105dd770a78df626d86cadb18b` |
| v0.4.0 #172 calibration commit | `725415045dfd2fce6cf914db40420271a53cb678` |
| v0.4.1 #186 stabilization commit | `931779f1192718516f44a64dc5eef9f5f3b3fda0` |
| v0.4.3 #241 refresh commit | `b798e980fc01a3f6eea48ccc3f9a05fe9c2cf6af` |
| v0.3.1 gate-only git dirty | `true` |
| v0.3.2 English/Korean gate-only git dirty | `true` |
| v0.4.0 #172 calibration git dirty | `true` |
| v0.4.1 #186 stabilization git dirty | `true` |
| v0.4.3 #241 refresh git dirty | `false` |
| v0.4.3 #241 refresh git tag | None recorded (`git_tag` is empty) |
| v0.4.1 Python | `CPython 3.11.9` on `Windows-10-10.0.26200-SP0` |
| v0.4.3 Python | `CPython 3.12.10` on `Windows-11-10.0.26200-SP0` |
| Codex package | `@openai/codex@0.128.0` |
| Model | `gpt-5.5` |
| Reasoning effort | `low` |
| SpecGuard gate | `python -m cli.specguard run <package> --no-llm --no-follow-up` |
| Supplemental and extended run command | `python tools/spec_driven_ai_benchmark.py --skip-codex --include-gate-only-extra-cases --max-workers 6 --output docs/benchmark-results/specguard-gate-only-v0.3.1.json` |
| English/Korean run command | `python tools/spec_driven_ai_benchmark.py --skip-codex --include-gate-only-extra-cases --include-korean-cases --max-workers 6 --output docs/benchmark-results/specguard-gate-only-v0.3.2.json` |
| #172 calibration run command | `python tools/spec_driven_ai_benchmark.py --skip-codex --include-gate-only-extra-cases --include-korean-cases --max-workers 6 --output docs/benchmark-results/specguard-gate-only-v0.4.0.json` |
| #186 stabilization run command | `python tools/spec_driven_ai_benchmark.py --skip-codex --include-gate-only-extra-cases --include-korean-cases --max-workers 6 --output docs/benchmark-results/specguard-gate-only-v0.4.1.json` |
| #241 refresh run command | `python -m tools.spec_driven_ai_benchmark --skip-codex --include-gate-only-extra-cases --include-korean-cases --max-workers 6 --output docs/benchmark-results/specguard-gate-only-v0.4.3.json` |
| Determinism check command | `python -m tools.spec_driven_ai_benchmark --determinism-check --determinism-repeats 3 --determinism-workers 1,6 --include-gate-only-extra-cases --include-korean-cases --output docs/benchmark-results/specguard-gate-only-v0.4.3.json` |
| Readiness coverage matrix command | `python -m tools.spec_driven_ai_benchmark --coverage-matrix --coverage-matrix-results docs/benchmark-results/specguard-gate-only-v0.4.3.json --include-gate-only-extra-cases --include-korean-cases --output docs/benchmark-results/readiness-coverage-matrix.json` |

The v0.3.1, v0.3.2, v0.4.0, and v0.4.1 gate-only runs are intentionally recorded as working-tree runs because their benchmark result artifacts and benchmark case expansion are part of their PR updates. The v0.4.3 #241 refresh was run from a clean source checkout state (`git_dirty=false`) before writing the new artifact. A separate release-quality validation can still rerun from a clean tag or fresh clone before release claims are finalized.

## Determinism Verification

The benchmark can run the same gate-only fixture set at least three times with each configured worker count. The release command uses worker counts `1` and `6`, then records the result under the top-level `determinism` object in the benchmark artifact using schema `specguard-benchmark-determinism/v1`.

Determinism comparisons retain semantic fields for readiness status, blocked state, finding severity, title, stable finding identifier, and evidence. The comparison removes only documented execution metadata: timestamps, durations, temporary roots, diagnostic stdout/stderr tails, traceback text, environment identity, cleanup status, and the intentionally different worker-count setting. Result lists are sorted by workflow and case before comparison.

Each reported difference contains `case_id`, `field_path`, `prior_value`, and `new_value`. The command exits non-zero when repeat counts are insufficient, normalized semantics drift, Critical finding evidence is missing without an explicit exception, or gate metrics differ between worker counts. The artifact also records `critical_finding_evidence`, including the count of evidence-backed Critical findings and any documented exceptions.

## Modes

| Mode | Purpose | Recorded Status |
| --- | --- | --- |
| `raw_ai` | Codex generates implementation directly from authored `spec.md` and `technical-design.md`. | Executed in original #136 run |
| `specguard_gate` | SpecGuard local no-LLM gate reviews the package before implementation. | Executed in original, v0.3.1, v0.3.2, v0.4.0, v0.4.1, and v0.4.3 gate-only runs |
| `specguard_handoff_ai` | Codex generates implementation only after SpecGuard reports `READY` or `READY_WITH_WARNINGS`. | Executed in original #136 run |
| `gate_only_supplemental_v1` | Multi-domain local gate-only supplemental suite. | Executed in v0.3.1, v0.4.0, v0.4.1, and v0.4.3 reruns |
| `gate_only_extended_v2` | Additional practical gate-only suite across less-covered business domains. | Executed in v0.3.1, v0.4.0, v0.4.1, and v0.4.3 reruns |
| `impact_v2_ko` | Korean gate-only variants corresponding to the original 18 impact cases. | Executed in v0.3.2, v0.4.0, v0.4.1, and v0.4.3 reruns |
| `gate_only_supplemental_v1_ko` | Korean gate-only variants corresponding to the supplemental 51-case suite. | Executed in v0.3.2, v0.4.0, v0.4.1, and v0.4.3 reruns |
| `gate_only_extended_v2_ko` | Korean gate-only variants corresponding to the extended suite. The recorded v0.4.3 artifact evaluates 41 extended English cases and 41 corresponding Korean cases after #213 and #242. | Executed in v0.3.2, v0.4.0, v0.4.1, and v0.4.3 reruns |
| `future_llm_specguard_review` | Compare local heuristic gate with LLM-backed SpecGuard Review. | Reserved |
| `future_strict_e2e` | Measure whether Strict E2E can revise blocked specs into safer implementation inputs. | Reserved |

## Methodology

The original 18-case impact suite uses a fixed target API:

```text
TaskError
TaskService.create_task(user_id, title, idempotency_key=None, correlation_id=None)
TaskService.list_tasks(user_id, correlation_id=None)
TaskService.complete_task(user_id, task_id, correlation_id=None)
TaskService.delete_task(user_id, task_id, correlation_id=None)
```

Generated implementations from the original #136 run are scored with hidden runtime contract checks:

| Check | Contract Risk |
| --- | --- |
| `create_exact_success` | Valid create response and title normalization |
| `blank_title_error` | Blank title rejection |
| `blank_user_error` | Blank user rejection |
| `idempotent_replay` | Same key and same title returns original task |
| `idempotency_conflict` | Same key and different title raises `TaskError` |
| `owner_scoped_list` | A user lists only their own active tasks |
| `cross_user_complete_hidden` | Cross-user mutation is blocked without changing owner data |
| `complete_idempotent` | Repeated complete remains completed |
| `delete_hides_task` | Deleted tasks disappear from normal lists |
| `deleted_task_blocked` | Deleted tasks cannot be completed |

The gate-only reruns do not execute Codex and do not produce new post-gate code defect rates. Their improvement calculation uses the raw defective weak cases from #136 as the exposure baseline, then asks whether the improved local gate now blocks those same weak inputs before code generation.

The supplemental 51-case suite and refreshed extended 41-case suite add practical specification shapes that are not limited to the TaskService hidden contract. The current source and v0.4.3 artifact include the #213 paired payment and inbound-webhook phrasing variants and the #242 ready/reference guards for former weak-only domains. These cases measure readiness gate behavior only.

The recorded v0.4.3 Korean layer adds corresponding gate-only fixtures for the same 110 evaluated English source cases. The Korean cases keep the benchmark domains and expected ready/weak classification, but rewrite the implementation-risk prose in realistic Korean wording. The #213 source expansion adds explicit Korean phrasing variants for inbound webhook URL-secret trust and payment idempotency post-settlement cleanup, each paired with a ready/reference guard. The #242 source expansion adds ready/reference guards for the former weak-only `device_trust`, `ledger`, `promotions`, `rate_limits`, `sso`, and `todo` domains. The benchmark output carries `language`, `source_case_id`, `suite_counts`, `language_counts`, `gate_by_suite`, and `gate_by_language` so English and Korean results can be compared without merging their claims.

For stabilization triage, the `--coverage-matrix` command emits deterministic fixture metadata without running SpecGuard, Codex, or any LLM provider. The matrix includes domain, language, case id, expectation, source case mapping, nullable readiness-result fields, and coverage gap categories for English-only, Korean-only, weak-only, and ready-only coverage gaps. The current English/Korean coverage audit is recorded in [`readiness-coverage-audit.md`](readiness-coverage-audit.md).

Use the [Readiness Calibration Triage Protocol](readiness-calibration-triage.md)
before tuning deterministic readiness rules. It defines the required baseline
recording, paired fixture guards, evidence checks, Korean counterpart review,
and benchmark-refresh decision points.

The lightweight fixture drift guard compares stable benchmark fixture metadata
against `tests/fixtures/readiness-fixture-drift-summary.json`. It catches
unintended changes to fixture count, language split, expectation split,
domain/language coverage, and English/Korean source-case mappings without
running the full benchmark. Intentional fixture expansion should update that
summary snapshot in the same PR and record whether #186 needs a benchmark
artifact refresh.

## Aggregate Results

### Original Full Impact Run From #136

| Workflow | Generated Cases | Mean Contract Defect Rate | Median | Std Dev | Cases With Contract Defects |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw AI | 18 | 16.7% | 15.0% | 15.6% | 11 |
| SpecGuard handoff AI | 15 | 14.0% | 10.0% | 15.8% | 8 |

| #136 Gate Metric | Result |
| --- | ---: |
| Evaluated cases | 18 |
| Blocked before code generation | 3 |
| Blocked weak cases | 3 |
| Blocked good cases | 0 |
| Overall block rate | 16.7% |

### v0.4.3 Gate-Only Calibration

| Gate Suite | Evaluated | Weak Blocked | Ready Blocked | Weak Block Rate | False Positive Rate | False Negative Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original 18-case impact suite | 18 | 12/12 | 0/6 | 100.0% | 0.0% | 0.0% |
| Supplemental 51-case gate suite | 51 | 35/35 | 0/16 | 100.0% | 0.0% | 0.0% |
| Reproduced 69-case subtotal | 69 | 47/47 | 0/22 | 100.0% | 0.0% | 0.0% |
| Extended 41-case gate suite | 41 | 20/20 | 0/21 | 100.0% | 0.0% | 0.0% |
| Combined English gate-only run | 110 | 67/67 | 1/43 | 100.0% | 2.3% | 0.0% |

### v0.4.3 English/Korean Gate-Only Calibration

| Language | Evaluated | Weak Blocked | Ready Blocked | Weak Block Rate | False Positive Rate | False Negative Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| English | 110 | 67/67 | 1/43 | 100.0% | 2.3% | 0.0% |
| Korean | 110 | 67/67 | 0/43 | 100.0% | 0.0% | 0.0% |

| Korean Gate Suite | Evaluated | Weak Blocked | Ready Blocked | Weak Block Rate | False Positive Rate | False Negative Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `impact_v2_ko` | 18 | 12/12 | 0/6 | 100.0% | 0.0% | 0.0% |
| `gate_only_supplemental_v1_ko` | 51 | 35/35 | 0/16 | 100.0% | 0.0% | 0.0% |
| `gate_only_extended_v2_ko` | 41 | 20/20 | 0/21 | 100.0% | 0.0% | 0.0% |

## Original Case Results

These rows combine the #136 raw AI defect evidence with the calibrated v0.4.3 gate-only status.

| Case | Type | #136 Raw Defect Rate | v0.4.3 Gate | Exposure Prevented Against #136 Raw Defects |
| --- | --- | ---: | --- | --- |
| `ready_canonical_task_service` | ready | 0.0% | `ready_with_warnings` | No |
| `ready_trimmed_validation_contract` | ready | 0.0% | `ready_with_warnings` | No |
| `ready_audit_soft_delete` | ready | 0.0% | `ready_with_warnings` | No |
| `ready_idempotency_contract` | ready | 0.0% | `ready_with_warnings` | No |
| `ready_state_machine_detail` | ready | 0.0% | `ready_with_warnings` | No |
| `ready_support_view_out_of_scope` | ready | 0.0% | `ready_with_warnings` | No |
| `fault_ownership_leak` | weak | 30.0% | `not_ready` | Yes |
| `fault_deleted_visible` | weak | 20.0% | `not_ready` | Yes |
| `fault_external_dependency` | weak | 0.0% | `not_ready` | No |
| `incomplete_error_contract` | weak | 30.0% | `not_ready` | Yes |
| `incomplete_idempotency` | weak | 30.0% | `not_ready` | Yes |
| `incomplete_state_transition` | weak | 20.0% | `not_ready` | Yes |
| `fault_client_side_filtering` | weak | 10.0% | `not_ready` | Yes |
| `fault_idempotency_conflict_allows_new_task` | weak | 40.0% | `not_ready` | Yes |
| `fault_error_schema_freeform` | weak | 30.0% | `not_ready` | Yes |
| `fault_title_no_trim` | weak | 40.0% | `not_ready` | Yes |
| `fault_deleted_mutable` | weak | 10.0% | `not_ready` | Yes |
| `incomplete_acceptance_missing` | weak | 40.0% | `not_ready` | Yes |

## Gate-Only Findings

The supplemental suite uses 16 ready-reference specs and 35 weak specs. The refreshed extended suite adds 21 ready-reference specs and 20 weak specs in domains that were either absent or underrepresented in the earlier coverage.

Strong deterministic coverage:

- Original impact weak cases: 12/12 blocked.
- Supplemental auth/session weak cases: 5/5 blocked.
- Supplemental todo weak cases: 2/2 blocked.
- Supplemental TaskService weak cases: 8/8 blocked.
- Supplemental billing export weak cases: 2/2 blocked.
- Supplemental webhook, payment, and inventory weak cases: 6/6 blocked.
- Supplemental support, admin role, audit, data export, search, file upload, order, workspace invite, notification, profile, and document-sharing weak cases: 12/12 blocked.
- Extended practical-domain weak cases: 20/20 blocked.

Remaining false negatives:

- None in the recorded v0.4.3 English/Korean 220-case gate-only run.

False positives:

- None in the recorded v0.4.3 English or Korean 110-case gate-only layers.

The previously documented false negatives, `fault_title_no_trim` and `weak_document_share_client_enforced`, are now blocked by deterministic heuristic findings with source evidence excerpts.

## Interpretation

The #129, #138, #140/#141, #142, #172, and #181-#185 stabilization work materially improves the original benchmark target. Against the #136 raw AI exposure baseline, the local low gate now prevents 11 of 11 observed weak-spec exposure paths, up from 3 of 11. The original ready-reference cases still produce no false positives.

The reproduced 69-case run changes the interpretation from "the gate is conservative" to "the gate is precise for the currently calibrated deterministic patterns." The refreshed extended 41-case run blocks every weak practical-domain case without blocking a ready/reference case. The benchmark limitations still apply because supplemental and extended suites are gate-only.

The Korean layer supports a narrower claim: deterministic low-mode checks now recognize explicit Korean unsafe wording for ownership and tenant scope, idempotency and replay, expiry and revocation, client-side delegation, external side effects, state transitions, audit mutability, privacy retention, webhook signature/retry policy, cache scope, rate limits, coupons, background job retries, and mixed Korean prose with common English identifiers in the recorded v0.4.3 110-case Korean result layer. This measured fixture behavior does not imply that every Korean phrasing of these risks is covered.

## Language Support Levels

| Spec Language | Current Support Claim |
| --- | --- |
| English specs | Calibrated against the recorded v0.4.3 110-case gate-only suite and the original 18-case impact history. The current artifact blocks 67/67 English weak cases with no ready-reference false positives. |
| Mixed Korean/English specs | Supported when Korean product prose is paired with common contract identifiers such as `tenant_id`, `idempotency_key`, `expires_at`, `revoked_at`, `event_id`, or service names. |
| Korean-only product prose | Initial deterministic low-mode support for explicit unsafe wording in the recorded v0.4.3 Korean 110-case layer. Product prose is Korean, while benchmark section headings remain compatible with the current spec parser. The current artifact blocks 67/67 Korean weak cases with no known Korean false positives. |
| Korean production completeness | Not claimed. The benchmark covers explicit unsafe wording, not all idioms, subtle legal/privacy variants, or model-backed Korean review quality. |

## Spec Kit And OpenSpec Reference

Older benchmark material compared Spec Kit, OpenSpec, and SpecGuard prompts directly. That comparison is now treated as historical reference context, not the primary claim.

The current v2/v3 harness does not execute the official Spec Kit or OpenSpec CLIs, and it does not claim that SpecGuard replaces either tool. The more defensible framing is:

- Spec Kit and OpenSpec can structure planning artifacts.
- A coding model can implement well when a spec is complete.
- SpecGuard should be judged by whether it blocks or improves unsafe implementation inputs before code generation.

Future benchmark versions may add reference prompt wrappers again, but they should remain secondary to defect-exposure metrics.

## Complete-Spec Baseline

The complete-spec baseline remains reproducible in the original six `ready_reference` TaskService cases. Each ready case ran through raw AI, SpecGuard gate, and SpecGuard handoff AI in #136. All ready cases produced 0.0% contract defect rate in both generation modes.

The supplemental and extended ready-reference cases are gate-only. They are useful for false-positive calibration, but they do not yet provide code-generation defect rates.

## Limitations

- The original code-generation benchmark still uses one implementation domain: an in-memory Python task service.
- The supplemental 51-case and refreshed extended 41-case suites are gate-only and do not measure raw AI or post-gate implementation defect rates.
- Each generated-code case in #136 used one Codex generation, so the full impact results are not statistical confidence intervals.
- The SpecGuard gate is local `--no-llm` low mode. It does not measure LLM-backed SpecGuard Review.
- The Korean layer is gate-only and deterministic. It does not measure raw AI generation, LLM-backed Korean review, or full Korean production support.
- The v0.4.3 artifact covers the current 220-case fixture matrix, but it is still a local provider-free gate-only run rather than a broad production-support or statistical benchmark.
- The deterministic v0.4.3 refresh records no English or Korean ready-reference false positives.
- `READY_WITH_WARNINGS` is treated as implementation-allowed because that is the current low-mode contract.
- Hidden checks cover the original benchmark contract, not all possible production risks.
- The v0.3.1, v0.3.2, v0.4.0, and v0.4.1 gate-only runs were executed from working trees containing benchmark changes, so `git_dirty=true` is expected in those result JSON files. The v0.4.3 refresh records `git_dirty=false` before the new artifact is written.
- The benchmark does not measure PR drift review, strict E2E revision, multi-agent UX, official Spec Kit CLI execution, official OpenSpec CLI execution, or post-gate multi-domain code defect rates.

## Benchmark Roadmap

| Area | Planned Expansion |
| --- | --- |
| Clean release run | Rerun the refreshed gate-only artifact from a clean tag or fresh clone before final release claims. |
| More codegen domains | Add auth/session, API contract, persistence, payments, webhooks, and async side-effect suites with hidden checks. |
| Repeated runs | Run multiple generations per case and report confidence intervals. |
| Gate comparison | Compare local low, medium/high, and LLM-backed SpecGuard Review. |
| Strict E2E | Measure whether blocked specs can be revised into safer ready specs. |
| PR drift | Measure SpecGuard PR Review against implementation diffs. |
| False negatives | Keep known FN/FP examples documented before future rule changes and promote justified gaps into deterministic Critical checks. |
| False positives | Preserve paired ready/weak guards and rerun the deterministic check before claiming zero ready-reference false positives for a future fixture set. |
| Korean coverage | Add more Korean phrasing variants and rerun from a clean tag before making broader Korean support claims. |
| Reference tools | Keep Spec Kit/OpenSpec as secondary context with clearly separated layer claims. |
