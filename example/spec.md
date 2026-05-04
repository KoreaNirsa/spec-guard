# Feature Specification: Team Invite

**Status**: Draft
**Source**: `discovery.md`

## User Scenarios & Testing

### Primary User Story

As a workspace admin, I want to invite a teammate by email so that the teammate can join the correct workspace without manual account setup.

### Acceptance Scenarios

1. Given an active workspace admin and a valid non-member email, when the admin creates an invite, then the system creates one pending invite, sends an invite email, writes an audit event, and returns the invite id and status.
2. Given an invited person with a valid unexpired token, when they accept the invite, then the system creates a workspace membership, marks the invite as accepted, invalidates further token use, and returns the membership id.
3. Given a duplicate invite request for the same workspace and normalized email while a pending invite exists, when the admin creates another invite, then the system returns the existing pending invite instead of creating a second active token.
4. Given an expired, revoked, accepted, malformed, or wrong-workspace token, when acceptance is attempted, then the system rejects the request and creates no membership.

### Edge Cases

- Invitee email differs only by case or surrounding whitespace.
- Invitee is already a workspace member.
- Workspace is archived or deleted after invite creation.
- Email delivery provider times out after the invite record is created.
- Acceptance is submitted twice with the same token.
- Non-admin attempts to create or revoke an invite.

## Requirements

### Functional Requirements

- The system must require an authenticated workspace admin to create or revoke an invite.
- The system must normalize invitee email by trimming whitespace and lowercasing the domain and local part for duplicate checks.
- The system must create invites with status `pending`, `accepted`, `revoked`, or `expired`.
- The system must issue a signed invite token with `schema_version=team_invite.v1`, invite id, workspace id, invitee email, issued-at timestamp, and expires-at timestamp.
- The system must expire invite tokens after 7 days.
- The system must enforce one active pending invite per workspace and normalized email.
- The system must treat invite creation as idempotent for the same workspace, normalized email, and requester within a 24-hour window.
- The system must create an audit event for invite created, invite accepted, invite revoked, duplicate invite returned, and invalid acceptance attempt.
- The system must reject invite acceptance if the workspace is archived, deleted, or does not match the token workspace id.
- The system must never create membership before token validation, workspace validation, and duplicate membership checks complete.
- The system must return stable machine-readable error codes for all documented errors.

## Acceptance Criteria

- [ ] Admin invite creation with a valid email returns `201 Created` with `status=pending`, `schema_version=team_invite.response.v1`, and an invite id.
- [ ] Duplicate pending invite creation returns `200 OK` with the existing invite id and does not issue a second active token.
- [ ] Non-admin invite creation returns `403 Forbidden` and does not persist an invite.
- [ ] Valid invite acceptance returns `201 Created`, creates exactly one membership, marks the invite accepted, and rejects subsequent token reuse.
- [ ] Expired, revoked, accepted, malformed, or wrong-workspace tokens return stable error codes and create no membership.
- [ ] Email provider timeout leaves the invite pending with `delivery_status=failed` and an audit event, without retrying automatically in v1.
- [ ] Every successful and rejected write path emits a correlation id and audit event.

## Error Cases

- Missing or invalid email returns `INVALID_EMAIL`.
- Authenticated user without workspace admin role returns `FORBIDDEN`.
- Workspace is archived or deleted returns `WORKSPACE_NOT_ACTIVE`.
- Duplicate pending invite returns existing invite with `DUPLICATE_PENDING_INVITE`.
- Invitee is already a member returns `ALREADY_MEMBER`.
- Expired token returns `INVITE_EXPIRED`.
- Revoked token returns `INVITE_REVOKED`.
- Accepted token reuse returns `INVITE_ALREADY_ACCEPTED`.
- Token signature or schema version mismatch returns `INVALID_INVITE_TOKEN`.
- Email provider timeout returns success for invite creation with `delivery_status=failed`; no automatic retry occurs in v1.

## Key Entities

- Workspace: tenant boundary for invite and membership.
- Admin user: authenticated actor with permission to invite teammates.
- Invite: pending access grant for one workspace and normalized email.
- Invite token: signed acceptance credential scoped to one invite and workspace.
- Membership: durable relationship between user and workspace.
- Audit event: immutable record of invite lifecycle and rejected write attempts.

## Out of Scope

- Bulk invite import.
- SCIM or directory sync.
- Billing seat purchase or payment enforcement.
- Custom email template editing.
- Automatic retry queues for failed email delivery.
- Cross-workspace invites from one token.

## Review & Acceptance Checklist

- [ ] Requirements are observable and testable.
- [ ] Authorization, ownership, and workspace boundaries are explicit.
- [ ] Invite token lifecycle is deterministic.
- [ ] Duplicate, expired, revoked, and replay cases are covered.
- [ ] Implementation details are deferred to `technical-design.md`.

