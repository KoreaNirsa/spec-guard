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

For API features, `contracts/openapi.yaml` must define at least one concrete path before SpecGuard can produce an implementation handoff. `paths: {}` is treated as a blocker, not a ready contract. Generated contracts include spec-derived success and error responses, request and response schemas, and `x-specguard-coverage` links back to acceptance criteria and error cases.

Strict E2E also requires executable verification before handoff. Add tests such as `tests/test_*.py`, or document an accepted `tests/verification-contract.md` with the command or artifact that a coding agent must preserve.
