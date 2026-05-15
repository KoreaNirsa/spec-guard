# Constitution: Team Invite

## Principles

- Spec-first: implementation must follow the approved spec package, not inferred intent.
- Review-first: the active SpecGuard Review level decides whether findings block implementation readiness.
- Authorization-first: invite creation, revocation, and acceptance must enforce workspace boundaries before durable membership changes.
- Ownership-first: invite acceptance requires the authenticated user's verified email to match the normalized invitee email.
- Token safety: every invite token is single-purpose, workspace-scoped, versioned, expiring, and invalid after acceptance or revocation.
- Idempotency: retries must not create extra active tokens, extra invites, or duplicate memberships.
- Auditability: every write path and rejected write attempt produces an audit event with a correlation id.

## Boundaries

- User boundary: only workspace admins create or revoke invites.
- Acceptance boundary: unauthenticated users cannot accept invites through the API; browser flows must complete sign-in or sign-up first.
- Workspace boundary: an invite token can create membership only in its encoded workspace.
- Data boundary: invitee email is normalized for duplicate checks and stored only as needed for invite lifecycle and audit.
- Dependency boundary: email provider failure does not decide membership state.
- Transaction boundary: token acceptance and membership creation happen in one serialized state transition.
- Exclusion boundary: billing, SCIM, bulk import, retry queues, and template management are not part of v1.

## Change Control

- Update spec artifacts before changing generated implementation outputs.
- Re-run SpecGuard after changing invite lifecycle, token shape, authorization, ownership checks, duplicate behavior, idempotency, or error codes.
- Do not ask coding agents to decide token expiry, duplicate invite semantics, email mismatch behavior, or authorization behavior by assumption.
