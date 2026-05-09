# SpecGuard Impact Benchmark

## Primary Question

How much does SpecGuard reduce exposed implementation defects from weak specs?

This benchmark no longer treats Spec Kit, OpenSpec, and SpecGuard as directly competing layers. Spec Kit and OpenSpec help structure specification work. SpecGuard is measured here as an implementation-readiness gate that runs before an AI coding agent turns a spec package into code.

## Executive Summary

The v0.3.1 benchmark refresh ran an expanded in-memory Python `TaskService` suite with 18 cases:

- 6 ready-reference specs with explicit ownership, validation, idempotency, and deleted-state contracts.
- 12 weak specs covering ownership leaks, incomplete idempotency, deleted-state drift, freeform errors, client-side filtering, and missing acceptance evidence.

Codex `gpt-5.5` generated code for every raw AI case. SpecGuard's local `--no-llm` gate evaluated every package before implementation. Codex then generated code only for packages that SpecGuard marked `READY` or `READY_WITH_WARNINGS`.

| Metric | Result |
| --- | ---: |
| Raw weak-spec average contract defect rate | 25.0% |
| Raw weak specs with contract defects | 11/12 |
| Weak specs blocked before code generation | 3/12 |
| Prevented exposure rate | 27.3% |
| False positive rate on ready specs | 0.0% |
| False negative rate on weak specs | 75.0% |
| Post-gate generated cases | 15 |
| Post-gate average contract defect rate | 14.0% |
| Post-gate weak cases still exposing defects | 8 |

The result is intentionally conservative. The local low gate prevented three weak specs from becoming code, but it allowed nine weak specs through as `READY_WITH_WARNINGS`. Those allowed weak specs still produced contract-defective code in eight cases. The benchmark therefore supports a narrower and more useful claim:

> SpecGuard's current local low gate reduces defect exposure for some Critical weak-spec patterns without blocking ready specs, but it does not yet catch enough semantic weak-spec cases to be treated as a complete defect-prevention layer.

## Benchmark Metadata

| Item | Value |
| --- | --- |
| Result JSON | [`docs/benchmark-results/specguard-impact-v0.3.0.json`](benchmark-results/specguard-impact-v0.3.0.json) |
| Result schema | `specguard-impact-benchmark/v2` |
| Benchmark script | `tools/spec_driven_ai_benchmark.py` version `2` |
| Run timestamp | `2026-05-09T13:02:31Z` to `2026-05-09T13:13:42Z` |
| SpecGuard package version | `0.3.0` |
| Git commit | `13218f58b9f1354b8fc059490c26f4a2a0b43c6a` |
| Git dirty | `false` |
| Codex package | `@openai/codex@0.128.0` |
| Model | `gpt-5.5` |
| Reasoning effort | `low` |
| SpecGuard gate | `python -m cli.specguard run <package> --no-llm --no-follow-up` |
| Hidden contract checks | 10 per generated implementation |
| Temporary workspace cleanup | `temp_removed=true` |

## Modes

| Mode | Purpose | v0.3.1 Status |
| --- | --- | --- |
| `raw_ai` | Codex generates implementation directly from authored `spec.md` and `technical-design.md`. | Executed |
| `specguard_gate` | SpecGuard local no-LLM gate reviews the package before implementation. | Executed |
| `specguard_handoff_ai` | Codex generates implementation only after SpecGuard reports `READY` or `READY_WITH_WARNINGS`. | Executed |
| `future_llm_specguard_review` | Compare local heuristic gate with LLM-backed SpecGuard Review. | Reserved |
| `future_strict_e2e` | Measure whether Strict E2E can revise blocked specs into safer implementation inputs. | Reserved |

## Methodology

Each case uses the same target API:

```text
TaskError
TaskService.create_task(user_id, title, idempotency_key=None, correlation_id=None)
TaskService.list_tasks(user_id, correlation_id=None)
TaskService.complete_task(user_id, task_id, correlation_id=None)
TaskService.delete_task(user_id, task_id, correlation_id=None)
```

Generated implementations are scored with hidden runtime contract checks:

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

The benchmark records structure quality checks separately from contract checks. The headline defect rates use only contract checks because the primary question is exposed behavior, not code style.

## Aggregate Results

| Workflow | Generated Cases | Mean Contract Defect Rate | Median | Std Dev | Cases With Contract Defects |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw AI | 18 | 16.7% | 15.0% | 15.6% | 11 |
| SpecGuard handoff AI | 15 | 14.0% | 10.0% | 15.8% | 8 |

| Gate Metric | Result |
| --- | ---: |
| Evaluated cases | 18 |
| Blocked before code generation | 3 |
| Blocked weak cases | 3 |
| Blocked good cases | 0 |
| Overall block rate | 16.7% |

## Case Results

| Case | Type | Raw Defect Rate | SpecGuard Gate | Handoff Defect Rate | Exposure Prevented |
| --- | --- | ---: | --- | ---: | --- |
| `ready_canonical_task_service` | ready | 0.0% | `ready_with_warnings` | 0.0% | No |
| `ready_trimmed_validation_contract` | ready | 0.0% | `ready_with_warnings` | 0.0% | No |
| `ready_audit_soft_delete` | ready | 0.0% | `ready_with_warnings` | 0.0% | No |
| `ready_idempotency_contract` | ready | 0.0% | `ready_with_warnings` | 0.0% | No |
| `ready_state_machine_detail` | ready | 0.0% | `ready_with_warnings` | 0.0% | No |
| `ready_support_view_out_of_scope` | ready | 0.0% | `ready_with_warnings` | 0.0% | No |
| `fault_ownership_leak` | weak | 30.0% | `not_ready` | N/A | Yes |
| `fault_deleted_visible` | weak | 20.0% | `ready_with_warnings` | 20.0% | No |
| `fault_external_dependency` | weak | 0.0% | `ready_with_warnings` | 0.0% | No |
| `incomplete_error_contract` | weak | 30.0% | `not_ready` | N/A | Yes |
| `incomplete_idempotency` | weak | 30.0% | `ready_with_warnings` | 40.0% | No |
| `incomplete_state_transition` | weak | 20.0% | `ready_with_warnings` | 20.0% | No |
| `fault_client_side_filtering` | weak | 10.0% | `ready_with_warnings` | 10.0% | No |
| `fault_idempotency_conflict_allows_new_task` | weak | 40.0% | `ready_with_warnings` | 40.0% | No |
| `fault_error_schema_freeform` | weak | 30.0% | `ready_with_warnings` | 30.0% | No |
| `fault_title_no_trim` | weak | 40.0% | `ready_with_warnings` | 40.0% | No |
| `fault_deleted_mutable` | weak | 10.0% | `ready_with_warnings` | 10.0% | No |
| `incomplete_acceptance_missing` | weak | 40.0% | `not_ready` | N/A | Yes |

## Interpretation

The ready-reference cases show that complete implementation input remains safe for the target task: raw AI and SpecGuard handoff AI both produced code with 0.0% contract defect rate across all six ready specs.

The weak-spec cases show the failure mode this benchmark is designed to expose. Raw AI produced contract-defective code in 11 of 12 weak cases. SpecGuard blocked three of those defective paths before code generation, which prevented 3 of 11 observed raw weak-spec exposures.

The remaining nine weak specs were not blocked by the local low gate. They were marked `READY_WITH_WARNINGS`, so the handoff path still generated implementation code. Eight of those post-gate weak cases exposed contract defects. This is the main product signal for follow-up work: the local low gate is calibrated to block Critical findings only, and several semantic defects currently land as warnings.

## Spec Kit And OpenSpec Reference

Older benchmark material compared Spec Kit, OpenSpec, and SpecGuard prompts directly. That comparison is now treated as historical reference context, not the primary claim.

The current v2 harness does not execute the official Spec Kit or OpenSpec CLIs, and it does not claim that SpecGuard replaces either tool. The more defensible framing is:

- Spec Kit and OpenSpec can structure planning artifacts.
- A coding model can implement well when a spec is complete.
- SpecGuard should be judged by whether it blocks or improves unsafe implementation inputs before code generation.

Future benchmark versions may add reference prompt wrappers again, but they should remain secondary to defect-exposure metrics.

## Complete-Spec Baseline

The complete-spec baseline is now reproducible in the harness through the six `ready_reference` cases. Each ready case is run through raw AI, SpecGuard gate, and SpecGuard handoff AI. All ready cases produced 0.0% contract defect rate in both generation modes, and SpecGuard produced no false positives.

The previous Spec Kit/OpenSpec complete-spec table is not reproduced by the v2 harness. Treat it as historical/manual evidence only.

## Limitations

- The benchmark uses one service domain: an in-memory Python task service.
- Each case uses one Codex generation, so this is not a statistical confidence interval.
- The SpecGuard gate is local `--no-llm` low mode. It does not measure LLM-backed SpecGuard Review.
- `READY_WITH_WARNINGS` is treated as implementation-allowed because that is the current low-mode contract.
- Hidden checks cover the benchmark contract, not all possible production risks.
- The benchmark does not measure PR drift review, strict E2E revision, multi-agent UX, official Spec Kit CLI execution, official OpenSpec CLI execution, or multi-domain defect rates.

## v0.3.2 Benchmark Roadmap

| Area | Planned Expansion |
| --- | --- |
| More domains | Add auth/session, API contract, persistence, and async side-effect suites. |
| Repeated runs | Run multiple generations per case and report confidence intervals. |
| Gate comparison | Compare local low, medium/high, and LLM-backed SpecGuard Review. |
| Strict E2E | Measure whether blocked specs can be revised into safer ready specs. |
| PR drift | Measure SpecGuard PR Review against implementation diffs. |
| False negatives | Promote recurring warning-only semantic blockers into deterministic Critical checks where justified. |
| Reference tools | Keep Spec Kit/OpenSpec as secondary context with clearly separated layer claims. |
