# TDD Scenarios: Team Invite

## Source

- Spec: `spec.md`
- Contract: `contracts/openapi.yaml`

## Success Cases

- [ ] Admin invite creation with a valid email returns `201 Created`, a pending invite id, `expires_at`, `delivery_status`, and a correlation id.
- [ ] Duplicate pending invite creation returns `200 OK` with the existing invite id and does not issue another active token.
- [ ] Same idempotency key and same request body returns the original response within 24 hours.
- [ ] Valid invite acceptance by an authenticated user with a matching verified email returns `201 Created`, creates one membership, and marks the invite accepted.
- [ ] Admin revocation changes a pending invite to revoked and invalidates its token.

## Failure Cases

- [ ] Missing or invalid email returns `INVALID_EMAIL` and creates no invite.
- [ ] Missing authentication returns `UNAUTHENTICATED`.
- [ ] Non-admin create or revoke returns `FORBIDDEN`.
- [ ] Already-member invite returns `ALREADY_MEMBER`.
- [ ] Reused idempotency key with a different body returns `IDEMPOTENCY_KEY_REUSED`.
- [ ] Expired token returns `INVITE_EXPIRED`.
- [ ] Revoked token returns `INVITE_REVOKED`.
- [ ] Accepted token reuse returns `INVITE_ALREADY_ACCEPTED`.
- [ ] Malformed token returns `INVALID_INVITE_TOKEN`.
- [ ] Authenticated user email mismatch returns `INVITEE_EMAIL_MISMATCH`.
- [ ] Wrong-workspace token returns `WRONG_WORKSPACE`.
- [ ] Email provider timeout leaves the invite pending with `delivery_status=failed` and no automatic retry.

## Boundary Cases

- [ ] Email normalization trims whitespace and lowercases the full address for duplicate checks.
- [ ] Concurrent acceptance attempts create exactly one membership.
- [ ] Workspace archived or deleted between creation and acceptance returns `WORKSPACE_NOT_ACTIVE`.
- [ ] Every write path emits an audit event and correlation id.

## Notes

These scenarios are intentionally implementation-language neutral. The accepted verification contract defines the executable checks expected from the coding agent.
