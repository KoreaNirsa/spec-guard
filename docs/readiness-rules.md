# Readiness Rules

SpecGuard supports three review levels:

- `low` is the default for `specguard run`. It is optimized for first-run usability and minimum safety gating. It blocks only Critical findings. Major and Minor findings are warnings.
- `medium` preserves the stricter v0.2.5-style readiness gate. Use it when you want deeper SpecGuard Review before implementation.
- `high` keeps the medium gate in this release while asking for stricter review attention. It may take longer and should be used when review depth matters more than latency.

Choose a level per run:

```bash
specguard run specs/your-feature-name --review-level medium
SPECGUARD_REVIEW_LEVEL=medium specguard run specs/your-feature-name
```

Strict E2E defaults to `medium` because it is explicitly an automated refinement loop.

Readiness states are interpreted by the selected review level:

- Low: READY when Critical=0 and no warnings exist; READY_WITH_WARNINGS when Critical=0 and Major or Minor warnings exist; NOT_READY only when Critical>=1.
- Medium: READY when Critical=0, Major=0, Minor<=5; READY_WITH_WARNINGS when Critical=0, Major<=2, Minor<=10; NOT_READY when Critical>=1, Major>=3, or Minor>10.
- High: uses the medium gate thresholds introduced in v0.2.7 with stricter review attention.

Critical findings always block implementation. Major findings should represent an implementation-critical product, security, state, contract, persistence, or ownership decision. Best-practice suggestions, optional hardening, future extensibility, broad reliability improvements, and weakly evidenced risks should be Minor or omitted.

## Critical Evidence Quality

Deterministic Critical findings must include `evidence[]` excerpts when authored source artifacts contain the triggering text. The excerpts must be non-empty, bounded, and derived from reviewed source artifacts rather than generated report prose. Their `impact` text must explain why implementation should stop before handoff, and their `fix` text must point to an actionable spec change direction without inventing product behavior.

There are currently no deterministic Critical exceptions that are allowed to omit `evidence[]`. The public `readiness-review.json` contract still treats `evidence[]` as optional so existing plugin consumers remain compatible, but deterministic local rules are held to this internal quality bar.

For heuristic calibration work, use the
[Readiness Calibration Triage Protocol](readiness-calibration-triage.md) before
changing deterministic rules. The protocol defines how to classify false
positives, false negatives, evidence-quality issues, fixture gaps, documentation
gaps, and Korean counterpart gaps.

## Language Coverage

The deterministic low-mode gate is calibrated primarily on English specs. The recorded v0.4.1 gate-only artifact includes a Korean benchmark layer for explicit unsafe Korean wording around ownership and tenant scope, idempotency and replay, expiry and revocation, client-side delegation, external side effects, state transitions, audit mutability, privacy retention, webhook policy, cache scope, rate limits, coupons, and background job retries. The current fixture source also includes #213 Korean phrasing variants for inbound webhook URL-secret trust and payment idempotency post-settlement cleanup; those variants are pending benchmark artifact refresh.

Current support levels:

- English specs: calibrated against the recorded v0.4.1 99-case gate-only benchmark. The current fixture source contains 104 selected English cases, with 5 fixture results pending the next benchmark refresh.
- Mixed Korean/English specs: supported when Korean product prose includes common contract identifiers such as `tenant_id`, `idempotency_key`, `expires_at`, `revoked_at`, or `event_id`.
- Korean-only product prose: initial deterministic support for explicit unsafe wording in the recorded v0.4.1 Korean 99-case layer. The current fixture source contains 104 selected Korean cases, with 5 fixture results pending the next benchmark refresh. This is not a full Korean production-support claim.

For API features, `contracts/openapi.yaml` must define at least one concrete path before SpecGuard can produce an implementation handoff. `paths: {}` is treated as a blocker, not a ready contract. Generated contracts include spec-derived success and error responses, request and response schemas, and `x-specguard-coverage` links back to acceptance criteria and error cases.

Strict E2E also requires executable verification before handoff. Add tests such as `tests/test_*.py`, or document an accepted `tests/verification-contract.md` with the command or artifact that a coding agent must preserve.
