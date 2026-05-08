# Discovery: PR Review Smoke

## Foundation

- Goal: Validate that SpecGuard PR Reviewer catches implementation drift from an approved spec.
- Users: Workspace members who can only read their own private notes.

## Mechanisms

- Components: HTTP API, notes service, in-memory repository for the smoke implementation.
- Data flow: Authenticated user requests notes, service filters by owner, response returns only owned notes.

## Stress Test

- First break: A user receives notes owned by another user.
- Edge cases: Missing owner id, unknown owner id, and empty note list.

## Synthesis

- Decision: Implementation must enforce owner-scoped reads before returning notes.
- Output: READY smoke spec with a deliberately flawed implementation diff for reviewer testing.
