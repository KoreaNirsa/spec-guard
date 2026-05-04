# Tasks: Team Invite

## Spec Package

- [x] Define invite creation and acceptance behavior.
- [x] Define authorization and workspace ownership boundaries.
- [x] Define token lifecycle, expiration, revocation, and replay behavior.
- [x] Define duplicate invite behavior.
- [x] Define stable error codes.

## Design And Validation

- [ ] Run `python -m cli.specguard run specs/team-invite --force`.
- [ ] Convert every Critical or Major Grill Review finding into a spec, plan, task, checklist, or design update.
- [ ] Re-run SpecGuard until Grill Review reports implementation-ready status.

## Implementation Handoff

- [ ] Confirm React screens cover admin invite creation and invite token acceptance.
- [ ] Confirm Spring Boot services enforce authorization, token lifecycle, duplicate invite handling, email timeout behavior, and audit writes.
- [ ] Confirm contract includes invite creation, revoke, and acceptance endpoints.
- [ ] Confirm tests cover valid invite, duplicate pending invite, invalid role, expired token, revoked token, replay, wrong workspace, and email timeout.
- [ ] Confirm implementation guide references `spec.md`, `plan.md`, `tasks.md`, `constitution.md`, checklist, tests, and contracts.
- [ ] Hand `implementation-output.md` to Codex or Claude Code only after SpecGuard passes.
