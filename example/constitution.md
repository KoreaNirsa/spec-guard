# Constitution: Team Invite

## Principles

- Spec-first: implementation must follow the approved spec package, not inferred intent.
- Review-first: Critical and Major Grill Review findings block implementation readiness.
- Authorization-first: invite creation, revocation, and acceptance must enforce workspace boundaries before durable membership changes.
- Token safety: every invite token is single-purpose, workspace-scoped, versioned, expiring, and invalid after acceptance or revocation.
- Auditability: every write path and rejected write attempt produces an audit event with a correlation id.

## Boundaries

- User boundary: only workspace admins create or revoke invites.
- Workspace boundary: an invite token can create membership only in its encoded workspace.
- Data boundary: invitee email is normalized for duplicate checks and stored only as needed for invite lifecycle and audit.
- Dependency boundary: email provider failure does not decide membership state.
- Exclusion boundary: billing, SCIM, bulk import, and template management are not part of v1.

## Change Control

- Update spec artifacts before changing generated implementation outputs.
- Re-run SpecGuard after changing invite lifecycle, token shape, authorization, duplicate behavior, or error codes.
- Do not ask coding agents to decide token expiry, duplicate invite semantics, or authorization behavior by assumption.

