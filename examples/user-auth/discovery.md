# Discovery: user-auth

## Foundation

- Goal: Build a secure token-based login flow before protected APIs exist.
- User impact: Users cannot safely access private resources without authentication.
- Constraints: Keep the initial API small, avoid leaking credential details, and preserve auditability.
- Assumption to test: Token issuance is not enough unless token expiry, refresh, replay, and lockout behavior are explicit.

## Mechanisms

- Components: API layer, auth service, token service, user store, refresh token store, rate limiter, audit logger.
- Data flow: Credentials enter through login, validation checks shape, auth verifies identity, token service issues token pair, audit logger records outcome.
- Dependencies: User store can timeout, token signing can fail, refresh token store can contain replayed token families.
- State: Anonymous, authenticated, refreshable, locked, rejected.

## Stress Test

- Bad input break: Missing email or password should stop before credential verification.
- Concurrency break: Simultaneous refresh requests can replay or rotate the same refresh token family.
- Security boundary: Refresh token replay and brute-force login are the primary bypass paths.
- Hard recovery: Token family compromise requires revocation and audit traceability.

## Differentiation

- Existing option: A simple login endpoint can issue tokens quickly.
- Difference: SpecGuard forces token lifecycle, replay, lockout, and failure behavior into the design before implementation.
- Non-goal: Full OAuth provider support is outside the initial scope.

## Feasibility

- Initial scope: Login, refresh, token rotation, lockout, audit events, and contract examples.
- Blocker: Token storage and replay detection must be designed before code generation.
- Validation: Grill Me can verify lifecycle and brute-force controls before implementation.

## Improvement

- Simplify: Keep access token payload minimal.
- Automate later: Model-based Grill Me can expand security review beyond local heuristics.
- Open question: Exact lockout thresholds may need product/security policy input.

## Synthesis

- Decision: Proceed only with explicit token lifecycle and replay controls.
- Required artifacts: spec.md, design.md, grill.md, grill.json, tests, and OpenAPI contract.
- Stop condition: Missing refresh token rotation or lockout behavior should block implementation.
