# Tasks: Team Invite

## Spec Package

- [x] Define invite creation, revocation, and acceptance behavior.
- [x] Define authorization, invited-email ownership, and workspace boundaries.
- [x] Define token lifecycle, expiration, revocation, and replay behavior.
- [x] Define duplicate invite and idempotency behavior.
- [x] Define email provider timeout and no-retry behavior for v1.
- [x] Define stable error codes and correlation id behavior.

## Design And Validation

- [ ] Run `specguard run specs/team-invite --force`.
- [ ] Convert every blocking Readiness Finding into a spec, plan, task, checklist, or design update.
- [ ] Re-run SpecGuard until SpecGuard Review reports implementation-ready status.
- [ ] Confirm `technical-design.md` has no unresolved Implementation Blockers before handoff.

## Implementation Handoff

- [ ] Confirm React screens cover admin invite creation, sign-in redirect, invite token acceptance, and rejected token states.
- [ ] Confirm Spring Boot services enforce authorization, invited-email matching, token lifecycle, duplicate invite handling, idempotency, email timeout behavior, concurrency, and audit writes.
- [ ] Confirm contract includes invite creation, revoke, and acceptance endpoints with shared response schemas.
- [ ] Confirm tests cover valid invite, duplicate pending invite, invalid role, idempotency replay, expired token, revoked token, accepted token replay, wrong workspace, email mismatch, concurrent acceptance, and email timeout.
- [ ] Confirm implementation guide references `spec.md`, `plan.md`, `tasks.md`, `constitution.md`, checklist, tests, and contracts.
- [ ] Hand `implementation-output.md` to Codex or Claude Code only after SpecGuard passes.
