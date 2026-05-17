# SpecGuard Impact Benchmark

## Primary Question

How much does SpecGuard reduce exposed implementation defects from weak specs?

This benchmark does not treat Spec Kit, OpenSpec, and SpecGuard as directly competing layers. Spec Kit and OpenSpec help structure specification work. SpecGuard is measured here as an implementation-readiness gate that runs before an AI coding agent turns a spec package into code.

## Executive Summary

The calibrated benchmark now has three evidence layers:

- The original #136 18-case in-memory Python `TaskService` impact suite: 6 ready-reference specs and 12 weak specs. This suite includes raw Codex generation, SpecGuard gate evaluation, and SpecGuard handoff generation from the pre-#129 run.
- A v0.3.1 gate-only rerun with the same 18 cases plus 50 supplemental and 30 extended real-world-style gate cases across auth/session, billing export, document sharing, webhooks, payments, inventory, support, admin roles, audit, data export, search, file upload, orders, workspace invites, notifications, profile updates, API keys, SSO, privacy, cache, returns, ledger, promotions, and background jobs.
- A v0.3.2 Korean gate-only layer with 98 corresponding Korean cases: `impact_v2_ko`, `gate_only_supplemental_v1_ko`, and `gate_only_extended_v2_ko`. These are realistic Korean product-prose fixtures, not code-generation runs.

The original #136 full generation run found that raw AI implementation from weak specs exposed contract defects in 11 of 12 weak cases. Before #129, SpecGuard blocked 3 of those weak specs. In the calibrated v0.3.1 local `--no-llm` gate, the same original suite blocks 11 of 12 weak specs.

| Metric | #136 Baseline | v0.3.1 Gate-Only | Change |
| --- | ---: | ---: | ---: |
| Weak specs blocked before code generation | 3/12 | 11/12 | +8 cases |
| Weak-spec block rate | 25.0% | 91.7% | +66.7 points |
| Prevented exposure rate against #136 raw defects | 27.3% | 90.9% | +63.6 points |
| False positive rate on original ready specs | 0.0% | 0.0% | 0.0 points |
| False negative rate on original weak specs | 75.0% | 8.3% | -66.7 points |

The remaining original false negative is `fault_title_no_trim`.

The supplemental and extended gate-only suites are intentionally broader than the original task-service benchmark. They are not used to claim post-gate code defect rates because no Codex generation was run for these cases. They measure only local readiness gate behavior.

| Supplemental Gate Metric | Result |
| --- | ---: |
| Evaluated supplemental cases | 50 |
| Ready-reference supplemental cases | 15 |
| Weak supplemental cases | 35 |
| Weak supplemental cases blocked | 34/35 |
| Supplemental weak block rate | 97.1% |
| Supplemental false positive rate | 0.0% |
| Supplemental false negative rate | 2.9% |

| Extended Gate Metric | Result |
| --- | ---: |
| Evaluated extended cases | 30 |
| Ready-reference extended cases | 12 |
| Weak extended cases | 18 |
| Weak extended cases blocked | 18/18 |
| Extended weak block rate | 100.0% |
| Extended false positive rate | 0.0% |
| Extended false negative rate | 0.0% |

The reproduced 68-case run confirms the improved local gate is strong on the deterministic patterns added in #129, #138, and #140: it blocks 45 of 47 weak cases with no ready-reference false positives. The #142 extended calibration blocks all 18 weak practical-domain cases while preserving zero false positives across the 12 extended ready-reference cases.

The v0.3.2 Korean layer reports English and Korean gate-only metrics separately. In this working-tree run, the English 98-case baseline remains at 63/65 weak specs blocked with 0 ready-reference false positives. The Korean 98-case layer blocks 65/65 weak specs with 0 ready-reference false positives.

## Benchmark Metadata

| Item | Value |
| --- | --- |
| Original full impact JSON | [`docs/benchmark-results/specguard-impact-v0.3.0.json`](benchmark-results/specguard-impact-v0.3.0.json) |
| v0.3.1 gate-only JSON | [`docs/benchmark-results/specguard-gate-only-v0.3.1.json`](benchmark-results/specguard-gate-only-v0.3.1.json) |
| v0.3.2 English/Korean gate-only JSON | [`docs/benchmark-results/specguard-gate-only-v0.3.2.json`](benchmark-results/specguard-gate-only-v0.3.2.json) |
| Result schema | `specguard-impact-benchmark/v2` |
| Benchmark script | `tools/spec_driven_ai_benchmark.py` version `4` |
| Original full run timestamp | `2026-05-09T13:02:31Z` to `2026-05-09T13:13:42Z` |
| v0.3.1 gate-only timestamp | `2026-05-11T14:18:22.699591+00:00` to `2026-05-11T14:18:28.946457+00:00` |
| v0.3.2 English/Korean gate-only timestamp | `2026-05-15T09:07:50.369407+00:00` to `2026-05-15T09:07:57.964756+00:00` |
| Original full run package version | `0.3.0` |
| v0.3.1 gate-only package version | `0.3.0` |
| v0.3.2 English/Korean gate-only package version | `0.3.1` |
| Original full run commit | `13218f58b9f1354b8fc059490c26f4a2a0b43c6a` |
| v0.3.1 gate-only commit | `d06824784f023993094d239346a8c52d81af1396` |
| v0.3.2 English/Korean gate-only commit | `f97f5f32faf894105dd770a78df626d86cadb18b` |
| v0.3.1 gate-only git dirty | `true` |
| v0.3.2 English/Korean gate-only git dirty | `true` |
| Codex package | `@openai/codex@0.128.0` |
| Model | `gpt-5.5` |
| Reasoning effort | `low` |
| SpecGuard gate | `python -m cli.specguard run <package> --no-llm --no-follow-up` |
| Supplemental and extended run command | `python tools/spec_driven_ai_benchmark.py --skip-codex --include-gate-only-extra-cases --max-workers 6 --output docs/benchmark-results/specguard-gate-only-v0.3.1.json` |
| English/Korean run command | `python tools/spec_driven_ai_benchmark.py --skip-codex --include-gate-only-extra-cases --include-korean-cases --max-workers 6 --output docs/benchmark-results/specguard-gate-only-v0.3.2.json` |

The v0.3.1 and v0.3.2 gate-only runs are intentionally recorded as working-tree runs because their benchmark result artifacts and benchmark case expansion are part of their PR updates. A later release-quality benchmark can rerun from a clean tag after the benchmark changes merge.

## Modes

| Mode | Purpose | v0.3.1 Status |
| --- | --- | --- |
| `raw_ai` | Codex generates implementation directly from authored `spec.md` and `technical-design.md`. | Executed in original #136 run |
| `specguard_gate` | SpecGuard local no-LLM gate reviews the package before implementation. | Executed in original and v0.3.1 gate-only runs |
| `specguard_handoff_ai` | Codex generates implementation only after SpecGuard reports `READY` or `READY_WITH_WARNINGS`. | Executed in original #136 run |
| `gate_only_supplemental_v1` | Multi-domain local gate-only supplemental suite. | Executed in v0.3.1 rerun |
| `gate_only_extended_v2` | Additional practical gate-only suite across less-covered business domains. | Executed in v0.3.1 rerun |
| `impact_v2_ko` | Korean gate-only variants corresponding to the original 18 impact cases. | Executed in v0.3.2 rerun |
| `gate_only_supplemental_v1_ko` | Korean gate-only variants corresponding to the supplemental 50-case suite. | Executed in v0.3.2 rerun |
| `gate_only_extended_v2_ko` | Korean gate-only variants corresponding to the extended 30-case suite. | Executed in v0.3.2 rerun |
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

The v0.3.1 gate-only rerun does not execute Codex and does not produce new post-gate code defect rates. Its improvement calculation uses the raw defective weak cases from #136 as the exposure baseline, then asks whether the improved local gate now blocks those same weak inputs before code generation.

The supplemental 50-case suite and extended 30-case suite add practical specification shapes that are not limited to the TaskService hidden contract. They measure readiness gate behavior only.

The Korean layer adds corresponding gate-only fixtures for the same 98 cases. The Korean cases keep the benchmark domains and expected ready/weak classification, but rewrite the implementation-risk prose in realistic Korean wording. The benchmark output carries `language`, `source_case_id`, `suite_counts`, `language_counts`, `gate_by_suite`, and `gate_by_language` so English and Korean results can be compared without merging their claims.

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

### v0.3.1 Gate-Only Rerun

| Gate Suite | Evaluated | Weak Blocked | Ready Blocked | Weak Block Rate | False Positive Rate | False Negative Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original 18-case impact suite | 18 | 11/12 | 0/6 | 91.7% | 0.0% | 8.3% |
| Supplemental 50-case gate suite | 50 | 34/35 | 0/15 | 97.1% | 0.0% | 2.9% |
| Reproduced 68-case subtotal | 68 | 45/47 | 0/21 | 95.7% | 0.0% | 4.3% |
| Extended 30-case gate suite | 30 | 18/18 | 0/12 | 100.0% | 0.0% | 0.0% |
| Combined gate-only run | 98 | 63/65 | 0/33 | 96.9% | 0.0% | 3.1% |

### v0.3.2 English/Korean Gate-Only Rerun

| Language | Evaluated | Weak Blocked | Ready Blocked | Weak Block Rate | False Positive Rate | False Negative Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| English | 98 | 63/65 | 0/33 | 96.9% | 0.0% | 3.1% |
| Korean | 98 | 65/65 | 0/33 | 100.0% | 0.0% | 0.0% |

| Korean Gate Suite | Evaluated | Weak Blocked | Ready Blocked | Weak Block Rate | False Positive Rate | False Negative Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `impact_v2_ko` | 18 | 12/12 | 0/6 | 100.0% | 0.0% | 0.0% |
| `gate_only_supplemental_v1_ko` | 50 | 35/35 | 0/15 | 100.0% | 0.0% | 0.0% |
| `gate_only_extended_v2_ko` | 30 | 18/18 | 0/12 | 100.0% | 0.0% | 0.0% |

## Original Case Results

These rows combine the #136 raw AI defect evidence with the calibrated v0.3.1 gate-only status.

| Case | Type | #136 Raw Defect Rate | v0.3.1 Gate | Exposure Prevented Against #136 Raw Defects |
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
| `fault_title_no_trim` | weak | 40.0% | `ready_with_warnings` | No |
| `fault_deleted_mutable` | weak | 10.0% | `not_ready` | Yes |
| `incomplete_acceptance_missing` | weak | 40.0% | `not_ready` | Yes |

## Gate-Only Findings

The supplemental suite uses 15 ready-reference specs and 35 weak specs. The extended suite adds 12 ready-reference specs and 18 weak specs in domains that were either absent or underrepresented in the earlier coverage.

Strong deterministic coverage:

- Original impact weak cases: 11/12 blocked.
- Supplemental auth/session weak cases: 5/5 blocked.
- Supplemental todo weak cases: 2/2 blocked.
- Supplemental TaskService weak cases: 8/8 blocked.
- Supplemental billing export weak cases: 2/2 blocked.
- Supplemental webhook, payment, and inventory weak cases: 6/6 blocked.
- Supplemental support, admin role, audit, data export, search, file upload, order, workspace invite, notification, and profile weak cases: 10/10 blocked.
- Extended practical-domain weak cases: 18/18 blocked.

Remaining false negatives:

- Original impact suite: `fault_title_no_trim`.
- Supplemental suite: `weak_document_share_client_enforced`.

False positives:

- None in the 98-case gate-only run.
- None in the v0.3.2 Korean 98-case gate-only layer.

The remaining false negatives are intentionally left visible instead of being hidden by benchmark narrowing. They are now limited to the original title-normalization ambiguity and the supplemental document-sharing ownership gap.

## Interpretation

The #129, #138, #140/#141, and #142 heuristic calibration materially improves the original benchmark target. Against the #136 raw AI exposure baseline, the local low gate now prevents 10 of 11 observed weak-spec exposure paths, up from 3 of 11. The original ready-reference cases still produce no false positives.

The reproduced 68-case run changes the interpretation from "the gate is conservative" to "the gate is precise for the currently calibrated deterministic patterns." The extended 30-case run now supports the same interpretation across the added practical-domain cases, while the benchmark limitations still apply because supplemental and extended suites are gate-only.

The Korean layer supports a narrower claim: deterministic low-mode checks now recognize explicit Korean unsafe wording for ownership and tenant scope, idempotency and replay, expiry and revocation, client-side delegation, external side effects, state transitions, audit mutability, privacy retention, webhook signature/retry policy, cache scope, rate limits, coupons, and background job retries. It does not claim that every Korean phrasing of these risks is covered.

## Language Support Levels

| Spec Language | Current Support Claim |
| --- | --- |
| English specs | Calibrated against the 98-case gate-only suite and the original 18-case impact history. |
| Mixed Korean/English specs | Supported when Korean product prose is paired with common contract identifiers such as `tenant_id`, `idempotency_key`, `expires_at`, `revoked_at`, `event_id`, or service names. |
| Korean-only product prose | Initial deterministic low-mode support for explicit unsafe wording in the v0.3.2 Korean 98-case layer. Product prose is Korean, while benchmark section headings remain compatible with the current spec parser. |
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
- The supplemental 50-case and extended 30-case suites are gate-only and do not measure raw AI or post-gate implementation defect rates.
- Each generated-code case in #136 used one Codex generation, so the full impact results are not statistical confidence intervals.
- The SpecGuard gate is local `--no-llm` low mode. It does not measure LLM-backed SpecGuard Review.
- The Korean layer is gate-only and deterministic. It does not measure raw AI generation, LLM-backed Korean review, or full Korean production support.
- `READY_WITH_WARNINGS` is treated as implementation-allowed because that is the current low-mode contract.
- Hidden checks cover the original benchmark contract, not all possible production risks.
- The v0.3.1 gate-only run was executed from a working tree containing benchmark changes, so `git_dirty=true` is expected in the result JSON.
- The benchmark does not measure PR drift review, strict E2E revision, multi-agent UX, official Spec Kit CLI execution, official OpenSpec CLI execution, or post-gate multi-domain code defect rates.

## v0.3.2 Benchmark Roadmap

| Area | Planned Expansion |
| --- | --- |
| Clean release run | Rerun gate-only and full impact benchmark from a clean tag after v0.3.1 benchmark changes merge. |
| More codegen domains | Add auth/session, API contract, persistence, payments, webhooks, and async side-effect suites with hidden checks. |
| Repeated runs | Run multiple generations per case and report confidence intervals. |
| Gate comparison | Compare local low, medium/high, and LLM-backed SpecGuard Review. |
| Strict E2E | Measure whether blocked specs can be revised into safer ready specs. |
| PR drift | Measure SpecGuard PR Review against implementation diffs. |
| False negatives | Promote the remaining title-normalization and document-sharing ownership gaps into deterministic Critical checks where justified. |
| False positives | Keep ready-reference false positives at 0 across the gate-only suite while expanding future domains. |
| Korean coverage | Add more Korean phrasing variants and rerun from a clean v0.3.2 tag before making broader Korean support claims. |
| Reference tools | Keep Spec Kit/OpenSpec as secondary context with clearly separated layer claims. |
