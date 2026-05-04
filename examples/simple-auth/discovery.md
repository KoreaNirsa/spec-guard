# Discovery: simple-auth

## Foundation

- Goal: Demonstrate a minimal authentication example.
- User impact: Users need a basic way to authenticate before accessing protected resources.
- Constraints: Keep this example intentionally small.
- Assumption to test: A simple token response may hide missing lifecycle and abuse controls.

## Mechanisms

- Components: API layer, auth service, user store, token signer.
- Data flow: Client sends credentials, API validates shape, auth service verifies credentials, token signer issues access token.
- Dependencies: User store and token signer.
- State: Unauthenticated, authenticated, rejected.

## Stress Test

- Bad input break: Missing credentials should return a validation error.
- Concurrency break: Repeated login attempts can pressure auth dependencies.
- Security boundary: Brute-force login and long-lived tokens are likely risks.
- Hard recovery: A leaked token cannot be revoked without lifecycle design.

## Differentiation

- Existing option: A trivial login endpoint can be scaffolded quickly.
- Difference: The example shows why Grill Me should attack even simple authentication designs.
- Non-goal: Refresh token rotation is not implemented in this minimal example.

## Feasibility

- Initial scope: Basic login behavior and contract.
- Blocker: Security hardening is incomplete by design.
- Validation: Grill Me should surface token expiry and brute-force gaps.

## Improvement

- Simplify: Keep the example focused on authentication basics.
- Automate later: Convert this into a risk example if simple-auth remains intentionally incomplete.
- Open question: Whether to keep this example alongside the primary passing example.

## Synthesis

- Decision: Keep as a simple demonstration, not the primary passing example.
- Required artifacts: spec.md, technical-design.md, grill.md, tests, and OpenAPI contract.
- Stop condition: Do not present this as production-ready authentication.
